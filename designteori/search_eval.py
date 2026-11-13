"""Reference implementation of the site search (spec section 5 and the later amendments) and the quality benchmark.

The JavaScript in docs/search.js implements exactly the same functions; docs/data/search/parity.json holds the
Python answers that the JavaScript test compares with. Only numpy and the published files are needed (CI safe).

Rules as implemented (the amendments override the first version of the spec):
  5.1  fold + tokenize (search_build.fold / tokenize)
  5.2  BM25 over weighted fields; groups per core token: exact term (1.0), s/es stem (1.0), prefix terms (0.5, len <= len(q)+4,
       up to 8 by df), and for len(q) >= 8 morphology terms that start with q[:-3] (0.8, up to 8 by df).
       score = sum(group values) * (0.6 + 0.4 * dekning)
  5.3  glossary groups with weight w = 1.0; a core token also counts as covered (dekning) when a glossary group derived from a
       from-phrase containing that token has value > 0 for the document.
  5.4  semantic list from stored int8 vectors; neighbour expansion (prf) from similar.bin
  5.5  reciprocal rank fusion k = 60; w_lex 1.0, w_sem 1.0, w_prf 0.6; pool for sorts other than relevance
"""
from __future__ import annotations

import base64
import collections
import json
import math
from pathlib import Path

import numpy as np

from . import DOCS_DATA_DIR, now_iso, read_json, write_json
from .search_build import SEARCH_DIR, SCHEMA, fold, query_key, tokenize

RRF_K = 60
W_LEX, W_SEM, W_PRF = 1.0, 1.0, 0.6
TOP_N = 200
FUSED_N = 300
PREFIX_MAX = 8
PREFIX_W = 0.5
MORPH_W = 0.8
MAX_EXTRA_TOKENS = 6
POOL_CAP = 2000


def matches(q: str, t: str) -> bool:
    """From-token t matches query token q (4.3): equal, or len(t) >= 5 and q starts with t."""
    return q == t or (len(t) >= 5 and q.startswith(t))


class Index:
    """All published search data, decoded for scoring."""

    def __init__(self, base: Path | None = None, *, with_vectors: bool = True, with_works: bool = False):
        base = Path(base) if base else SEARCH_DIR
        self.base = base
        self.meta = read_json(base / "meta.json")
        self.cfg = read_json(base / "search_config.json")
        lex = read_json(base / "lex.json")
        self.n = int(lex["n"])
        self.k1, self.b, self.avgdl = float(lex["k1"]), float(lex["b"]), float(lex["avgdl"])
        self.doclen = np.asarray(lex["doclen"], dtype=np.float64)
        self.terms: list[str] = lex["terms"]
        self.term_ix = {t: j for j, t in enumerate(self.terms)}
        self._post = lex["post"]
        self._cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        self.df = np.fromiter((len(p) // 2 for p in self._post), dtype=np.int64, count=len(self._post))
        self.idf = np.log(1.0 + (self.n - self.df + 0.5) / (self.df + 0.5))
        self.stopwords = set(self.cfg["stopwords"])
        self.glossary = self.cfg["glossary"]
        self.ids: list[str] = self.meta["ids"]
        self.vectors = None
        self.similar_idx = None
        self.similar_sim = None
        self.qvec: dict[str, np.ndarray] = {}
        if with_vectors:
            vp = base / "vectors.i8"
            if vp.is_file():
                self.vectors = np.frombuffer(vp.read_bytes(), dtype=np.int8).reshape(self.n, -1)
                self._vec_f = self.vectors.astype(np.float64) / 127.0
            sp = base / "similar.bin"
            if sp.is_file():
                raw = sp.read_bytes()
                k = int((self.meta.get("similar") or {}).get("k", 20))
                half = self.n * k * 2
                self.similar_idx = np.frombuffer(raw[:half], dtype="<u2").reshape(self.n, k).astype(np.int64)
                self.similar_sim = np.frombuffer(raw[half:], dtype=np.uint8).reshape(self.n, k)
            qp = base / "query_vectors.json"
            if qp.is_file():
                for key, b64 in (read_json(qp).get("queries") or {}).items():
                    self.qvec[key] = np.frombuffer(base64.b64decode(b64), dtype=np.int8).astype(np.float64) / 127.0
        self.works = None
        if with_works:
            pubs = read_json(DOCS_DATA_DIR / "publications.json") or []
            nordic = read_json(DOCS_DATA_DIR / "nordic_additions.json") or []
            self.works = pubs + nordic
        self.acc = self.meta["acc"]
        self.flag = self.meta["flag"]
        self.lang = self.meta["lang"]

    # --- postings -------------------------------------------------------------------------------
    def postings(self, j: int) -> tuple[np.ndarray, np.ndarray]:
        c = self._cache.get(j)
        if c is None:
            flat = np.asarray(self._post[j], dtype=np.int64)
            docs = np.cumsum(flat[0::2])
            c = (docs, flat[1::2].astype(np.float64))
            self._cache[j] = c
        return c

    def term_values(self, j: int) -> tuple[np.ndarray, np.ndarray]:
        docs, tf = self.postings(j)
        norm = self.k1 * (1.0 - self.b + self.b * self.doclen[docs] / self.avgdl)
        return docs, self.idf[j] * tf * (self.k1 + 1.0) / (tf + norm)

    # --- groups (5.2) ---------------------------------------------------------------------------------
    def expand(self, q: str) -> list[tuple[int, float]]:
        """Terms of the group for core token q as (term index, weight)."""
        out: list[tuple[int, float]] = []
        seen: set[int] = set()

        def add(t: str, w: float) -> None:
            j = self.term_ix.get(t)
            if j is not None and j not in seen:
                seen.add(j)
                out.append((j, w))

        if q in self.term_ix:
            add(q, 1.0)
        elif q.endswith("s") and len(q) >= 5:
            add(q[:-1], 1.0)
        elif q.endswith("es") and len(q) >= 6:
            add(q[:-2], 1.0)
        if len(q) >= 4:
            cand = self._prefix_terms(q, lambda t: t != q and len(t) <= len(q) + 4 and self.term_ix[t] not in seen)
            for t in cand[:PREFIX_MAX]:
                add(t, PREFIX_W)
        if len(q) >= 8:
            stem = q[: len(q) - 3]
            cand = self._prefix_terms(stem, lambda t: len(t) <= len(q) + 4 and self.term_ix[t] not in seen)
            for t in cand[:PREFIX_MAX]:
                add(t, MORPH_W)
        return out

    def _prefix_terms(self, prefix: str, keep) -> list[str]:
        lo = _bisect_left(self.terms, prefix)
        res = []
        for t in self._iter_from(lo):
            if not t.startswith(prefix):
                break
            if keep(t):
                res.append(t)
        res.sort(key=lambda t: (-int(self.df[self.term_ix[t]]), t))
        return res

    def _iter_from(self, lo: int):
        terms = self.terms
        for i in range(lo, len(terms)):
            yield terms[i]

    def group_values(self, q: str) -> np.ndarray:
        g = np.zeros(self.n, dtype=np.float64)
        for j, w in self.expand(q):
            docs, val = self.term_values(j)
            g[docs] += w * val
        return g

    # --- query analysis -------------------------------------------------------------------------------
    def core_tokens(self, text: str) -> list[str]:
        toks = tokenize(text)
        kept = [t for t in toks if t not in self.stopwords]
        use = kept if kept else toks
        seen, out = set(), []
        for t in use:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def glossary_groups(self, core: list[str]) -> list[dict]:
        """Additional groups (5.3): [{'token': t, 'sources': {core index, ...}, 'w': w}], at most 6 tokens."""
        added: dict[str, dict] = {}
        order: list[str] = []
        coreset = set(core)
        for entry in self.glossary:
            sources: set[int] = set()
            hit = False
            for phrase in entry["from"]:
                ps: set[int] = set()
                ok = True
                for t in phrase:
                    m = {i for i, q in enumerate(core) if matches(q, t)}
                    if not m:
                        ok = False
                        break
                    ps |= m
                if ok:
                    hit = True
                    sources |= ps
            if not hit:
                continue
            w = float(entry.get("w", 1.0))
            for phrase in entry["to"]:
                for tok in tokenize(phrase):
                    if tok in self.stopwords or tok in coreset:
                        continue
                    if tok in added:
                        added[tok]["sources"] |= sources
                    elif len(order) < MAX_EXTRA_TOKENS:
                        added[tok] = {"token": tok, "sources": set(sources), "w": w}
                        order.append(tok)
        return [added[t] for t in order]

    # --- lists ---------------------------------------------------------------------------------------------
    def lexical_scores(self, text: str, *, glossary: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """(score, dekning) arrays over all works for the query text."""
        core = self.core_tokens(text)
        score = np.zeros(self.n)
        if not core:
            return score, np.zeros(self.n)
        covered = np.zeros((len(core), self.n), dtype=bool)
        for i, q in enumerate(core):
            g = self.group_values(q)
            score += g
            covered[i] = g > 0
        if glossary:
            for grp in self.glossary_groups(core):
                g = self.group_values(grp["token"]) * grp["w"]
                score += g
                pos = g > 0
                for i in grp["sources"]:
                    covered[i] |= pos
        dek = covered.sum(axis=0) / len(core)
        return score * (0.6 + 0.4 * dek), dek

    def top(self, score: np.ndarray, mask: np.ndarray | None, n: int = TOP_N, positive_only: bool = True) -> list[int]:
        ok = score > 0 if positive_only else np.ones(self.n, dtype=bool)
        if mask is not None:
            ok = ok & mask
        cand = np.flatnonzero(ok)
        if cand.size == 0:
            return []
        order = np.lexsort((cand, -score[cand]))
        return [int(x) for x in cand[order][:n]]

    def lexical(self, text: str, mask=None, *, glossary: bool = True, n: int = TOP_N) -> list[int]:
        score, _ = self.lexical_scores(text, glossary=glossary)
        return self.top(score, mask, n)

    def semantic(self, qv: np.ndarray, mask=None, n: int = TOP_N) -> list[int]:
        sims = self._vec_f @ qv
        return self.top(sims, mask, n, positive_only=False)

    def prf(self, lex_list: list[int], mask=None, n: int = TOP_N) -> list[int]:
        score = np.zeros(self.n)
        for r, s in enumerate(lex_list[:5], start=1):
            w = 1.0 / (1.0 + r)
            score[s] += w
            score[self.similar_idx[s]] += w * (self.similar_sim[s].astype(np.float64) / 255.0)
        return self.top(score, mask, n)

    @staticmethod
    def rrf(lists: list[tuple[list[int], float]], n: int = FUSED_N) -> list[int]:
        acc: dict[int, float] = collections.defaultdict(float)
        for lst, w in lists:
            for r, d in enumerate(lst, start=1):
                acc[d] += w / (RRF_K + r)
        order = sorted(acc, key=lambda d: (-acc[d], d))
        return order[:n]

    def key_vector(self, text: str):
        return self.qvec.get(query_key(text))

    def search(self, text: str, mask=None, qv=None, n: int = FUSED_N) -> dict:
        """The full hybrid answer. Mode: 'vector' with a query vector, 'neighbours' with similar.bin only, else 'words'."""
        if qv is None:
            qv = self.key_vector(text)
        lex = self.lexical(text, mask)
        if qv is not None and self.vectors is not None:
            mode = "vector"
            fused = self.rrf([(lex, W_LEX), (self.semantic(qv, mask), W_SEM)], n)
        elif self.similar_idx is not None:
            mode = "neighbours"
            fused = self.rrf([(lex, W_LEX), (self.prf(lex, mask), W_PRF)], n)
        else:
            mode = "words"
            fused = lex[:n]
        return {"mode": mode, "lex": lex, "fused": fused}

    def candidate_pool(self, text: str, mask=None, qv=None, cap: int = POOL_CAP) -> list[int]:
        """Pool for sorts other than relevance (5.5, amendment 3): every work with dekning == 1 after the filter mask
        (cap 2000, ordered by score) united with the 300 fused hits."""
        score, dek = self.lexical_scores(text)
        full = (dek >= 1.0 - 1e-12) & (score > 0)
        if mask is not None:
            full = full & mask
        cand = np.flatnonzero(full)
        order = np.lexsort((cand, -score[cand]))
        pool = [int(x) for x in cand[order][:cap]]
        seen = set(pool)
        for d in self.search(text, mask, qv)["fused"]:
            if d not in seen:
                pool.append(d)
                seen.add(d)
        return pool

    # --- filter mask (subset of F9; enough for the checks) ----------------------------------------------------
    def mask(self, *, hide_duplicates: bool = False, acc: str | None = None, year: tuple[int, int] | None = None,
             lang: str | None = None) -> np.ndarray:
        m = np.ones(self.n, dtype=bool)
        if hide_duplicates:
            m &= np.fromiter((c != "d" for c in self.flag), dtype=bool, count=self.n)
        if acc:
            allowed = {"pdf": "hvu", "open": "hv", "abs": ""}.get(acc, acc)
            if acc == "abs":
                m &= np.fromiter((c != "0" for c in self.meta["abs"]), dtype=bool, count=self.n)
            else:
                m &= np.fromiter((c in allowed for c in self.acc), dtype=bool, count=self.n)
        if lang:
            m &= np.fromiter((c == lang for c in self.lang), dtype=bool, count=self.n)
        if year and self.works is not None:
            lo, hi = year
            m &= np.fromiter((w.get("year") is not None and lo <= int(w["year"]) <= hi for w in self.works), dtype=bool, count=self.n)
        return m


def _bisect_left(a: list[str], x: str) -> int:
    lo, hi = 0, len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo


# --- metrics -------------------------------------------------------------------------------------------------
def recall_at(lst: list[int], relevant: set[int], k: int = 10) -> float:
    if not relevant:
        return 0.0
    hit = sum(1 for d in lst[:k] if d in relevant)
    return hit / min(len(relevant), k)


def first_rank(lst: list[int], relevant: set[int]) -> int | None:
    for r, d in enumerate(lst, start=1):
        if d in relevant:
            return r
    return None


SYSTEMS = ("lexical", "semantic", "fused", "fallback")


def system_lists(idx: Index, text: str, mask=None) -> dict[str, list[int]]:
    qv = idx.key_vector(text)
    lex_plain = idx.lexical(text, mask, glossary=False)
    lex = idx.lexical(text, mask)
    out = {"lexical": lex_plain}
    out["semantic"] = idx.semantic(qv, mask) if qv is not None else []
    out["fused"] = idx.rrf([(lex, W_LEX), (out["semantic"], W_SEM)])
    out["fallback"] = idx.rrf([(lex, W_LEX), (idx.prf(lex, mask), W_PRF)])
    return out


def run_benchmark(write: bool = True, base: Path | None = None) -> dict:
    base = Path(base) if base else SEARCH_DIR
    idx = Index(base)
    bq = read_json(base / "benchmark_queries.json")
    pos = {wid: i for i, wid in enumerate(idx.ids)}
    queries = bq["queries"]
    groups = ["all", "known-item", "topical-en", "cross-lingual", "dev", "test"]

    def agg(vals: list[tuple[dict, float]]) -> dict:
        out = {}
        for g in groups:
            sel = [v for q, v in vals if g == "all" or q["group"] == g or q["split"] == g]
            out[g] = round(sum(sel) / len(sel), 6) if sel else None
        return out

    rec: dict[str, list] = {s: [] for s in SYSTEMS}
    suc: dict[str, list] = {s: [] for s in SYSTEMS}
    per_query = []
    parity = []
    missing = [q["text"] for q in queries if idx.key_vector(q["text"]) is None]
    if missing:
        raise RuntimeError(f"no stored query vector for: {missing}")
    for q in queries:
        rel = {pos[w] for w in q["relevant"]}
        lists = system_lists(idx, q["text"])
        row = {"id": q["id"]}
        for s in SYSTEMS:
            r10 = recall_at(lists[s], rel)
            rec[s].append((q, r10))
            suc[s].append((q, 1.0 if any(d in rel for d in lists[s][:10]) else 0.0))
            row[s] = {"recall10": round(r10, 6), "first_rank": first_rank(lists[s], rel)}
        per_query.append(row)
        parity.append({"q": q["text"], "lexical": lists["lexical"][:20], "fallback": lists["fallback"][:20], "fused": lists["fused"][:20]})
    quality = {
        "schema": SCHEMA, "built": now_iso(), "n_queries": len(queries),
        "model": "google/embeddinggemma-300m (q8, 256 dim)",
        "params": {"k1": idx.k1, "b": idx.b, "rrf_k": RRF_K, "w_lex": W_LEX, "w_sem": W_SEM, "w_prf": W_PRF,
                   "gloss_w": float(idx.glossary[0].get("w", 1.0)), "top_n": TOP_N, "fused_n": FUSED_N,
                   "prefix_w": PREFIX_W, "morph_w": MORPH_W},
        "metrics": {"recall_at_10": {s: agg(rec[s]) for s in SYSTEMS}, "success_at_10": {s: agg(suc[s]) for s in SYSTEMS}},
        "per_query": per_query,
        "caveats": list(bq.get("caveats") or []) + default_caveats(bq),
    }
    summary = {"n_queries": len(queries), "recall_at_10": quality["metrics"]["recall_at_10"],
               "success_at_10": quality["metrics"]["success_at_10"]}
    if write:
        write_json(base / "search_quality.json", quality, compact=False)
        write_json(base / "parity.json", {"schema": SCHEMA, "mask": "none", "note": "positions in meta.ids; lexical = 5.2 without glossary; fallback = lex+glossary+neighbours; fused = lex+glossary+stored query vector",
                                          "queries": parity}, compact=True)
    return {"quality": quality, "summary": summary, "parity": parity}


def default_caveats(bq: dict) -> list[str]:
    return [
        "Relevansvurderinga er gjord av ein språkmodell, ikkje av ein domeneekspert (sjå judge i benchmark_queries.json).",
        "Relevansmengda er avgrensa av pooling frå ordsøk, meining og samla søk; verk utanfor puljen tel som ikkje relevante, og reservemodus var ikkje med i puljen.",
        f"Berre {len(bq['queries'])} spørjingar: usikkerheita er brei, og tala skal lesast som retning, ikkje som presise mål.",
        "Spørjevektorane er koda i Python med same modellfil som nettlesaren skal bruke; paritet i nettlesaren er ikkje målt av byggjeskriptet.",
        "Arkivverk har berre tittel i innbygginga (ingen samandrag frå metadata), så meining og likskap er svakare for dei.",
        "Alle system er målte utan filter og utan skjuling av moglege dublettar.",
    ]
