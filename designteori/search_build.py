"""Builds the data for the site search in docs/data/search/ (spec in the working notes, section 4).

Stages (python designteori.py build-search --stage ...):
  config   search_config.json and tests/fixtures/search/tokenizer_cases.json only
  lexical  step A: config, abstracts, access, lex, about, glossary, meta (no model, plain Python)
  embed    step B: vectors.i8 (long job; Python 3.13 with onnxruntime/tokenizers; see README)
  finish   step C: similar.bin, query_vectors.json, benchmark, quality, parity, meta

Module level imports are the standard library only so that `compileall`, the unit tests and
`designteori.py verify` run in CI without onnxruntime, tokenizers or pymupdf. numpy and the model are
imported inside the functions that need them.
"""
from __future__ import annotations

import argparse
import base64
import bisect
import collections
import hashlib
import html
import json
import math
import os
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

from . import (
    DOCS_DATA_DIR,
    PDF_DIR,
    PRIVATE_CACHE,
    PRIVATE_CORPUS_DB,
    RAW_SQLITE,
    REPO_RAW_BASE,
    ROOT,
    normalize_doi,
    normalize_title,
    now_iso,
    read_json,
    write_json,
)
from . import search_terms

# --- paths and constants (kept here; __init__.py is not touched) --------------------------------
SEARCH_DIR = DOCS_DATA_DIR / "search"
ABSTRACT_DIR = SEARCH_DIR / "abstracts"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "search"
VECTOR_CACHE = PRIVATE_CACHE / "search_doc_vectors.sqlite"

SCHEMA = 1
SHARD_SIZE = 128
DIM = 256
K_NEIGHBOURS = 20
FOLD_MAP = {"æ": "ae", "ø": "o", "ð": "d", "þ": "th", "ß": "ss", "đ": "d", "ł": "l", "œ": "oe"}
FIELD_WEIGHTS = {"title": 4, "authors": 2, "venue": 2, "affil": 2, "abstract": 1}
BM25_K1 = 1.2
BM25_B = 0.75
GLOSSARY_W = 1.0
EXTRACT_MIN, EXTRACT_MAX = 300, 2500
OA_ABSTRACT_MIN = 50
MAX_ABSTRACT_CHARS = 5000  # R8: no published abstract is longer; longer metadata abstracts are left out
MAX_FILE_BYTES = 2_000_000
LEX_MAX_BYTES = 3_000_000
LEX_MAX_GZIP = 900_000

LIBRARY_VERSION = "3.8.1"
LIBRARY_URL = f"https://cdn.jsdelivr.net/npm/@huggingface/transformers@{LIBRARY_VERSION}/dist/transformers.min.js"
MODEL_ID = "onnx-community/embeddinggemma-300m-ONNX"
# Sizes measured with HEAD requests (Content-Length) on 2026-11-13; refreshed by `--stage modelcheck`.
MODEL_FILES = {
    "huggingface.co/onnx/model_quantized.onnx_data": 308890624,
    "huggingface.co/onnx/model_quantized.onnx": 567874,
    "huggingface.co/tokenizer.json": 20323312,
    "huggingface.co/tokenizer_config.json": 1156830,
    "huggingface.co/config.json": 1765,
    "cdn.jsdelivr.net/transformers.min.js": 888173,
    "cdn.jsdelivr.net/ort-wasm-simd-threaded.jsep.wasm": 21596019,
    "cdn.jsdelivr.net/ort-wasm-simd-threaded.jsep.mjs": 44484,
}
MODEL_FILES_MEASURED = "2026-11-13"  # Hugging Face: HEAD Content-Length / X-Linked-Size; jsDelivr: file list of its package API

LANG_META = {"en": "e", "nb": "b", "nn": "n", "da": "d", "sv": "s", "fi": "f", "de": "o", "und": "u", "is": "o"}
OPENALEX_LANG = {"en": "e", "da": "d", "sv": "s", "fi": "f", "nn": "n", "no": "b", "nb": "b"}
ACC_CODES = ("h", "v", "u", "d", "0")


# --- text utilities (the spec 5.1 functions are mirrored in docs/search.js) -----------------------
def fold(text: str) -> str:
    s = str(text or "").lower()
    for k, v in FOLD_MAP.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not ("̀" <= c <= "ͯ"))


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(fold(text)) if len(t) >= 2]


def query_key(text: str) -> str:
    """Key of a stored query vector: trim, collapse whitespace, lower case. No folding, no punctuation removal."""
    return " ".join(str(text or "").split()).lower()


_BLOCK_TAGS = r"p|br|sec|title|abstract|list|list-item|ul|ol|li|div|h[1-6]"
_INLINE_TAGS = r"i|b|u|em|strong|sub|sup|span|italic|bold|ext-link|xref|a|mml:[a-z]+|math|sc|small"
_TAG_RE = re.compile(r"</?(?:jats:)?(?:(?P<block>" + _BLOCK_TAGS + r")|(?P<inline>" + _INLINE_TAGS + r"))(?:\s[^<>]*)?/?>", re.I)


def clean_abstract(raw: object) -> str:
    """HTML/JATS tags removed (only real tags, `<like this>` in running text stays), entities decoded, whitespace collapsed."""
    s = _TAG_RE.sub(lambda m: " " if m.group("block") else "", str(raw or ""))
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


_SW = {
    "en": "the of and to in a is for with that on as by this are from an be or at which we our can their it its has have was were not between how design",
    "nb": "og i er det som en til av på for med har den ikke om et fra de var å vi seg også kan skal men eller hva mellom blir ved denne disse",
    "nn": "og i er det som ein til av på for med har den ikkje om eit frå dei var å vi seg også kan skal men eller kva mellom blir ved denne desse ikkje korleis",
    "da": "og i er det som en til af på for med har den ikke om et fra de var at vi sig også kan skal men eller hvad mellem bliver ved denne disse",
    "sv": "och i är det som en till av på för med har den inte om ett från de var att vi sig också kan ska men eller vad mellan blir vid denna dessa",
    "fi": "ja on että ei se oli kuin mutta tai myös joka tämä sekä ovat kun jos vain mukaan tutkimus",
    "de": "und der die das ist nicht mit für von zu den auf ein eine auch sich",
    "is": "og er að það sem í á til með en ekki var við hefur þetta",
}
_SW = {k: set(v.split()) for k, v in _SW.items()}
_NN_MARK = {"ikkje", "ein", "eit", "korleis", "kva", "frå", "dei", "desse", "nokre", "berre", "òg"}
_NB_MARK = {"ikke", "hvordan", "hva", "fra", "disse", "noen", "bare", "også", "jeg"}
_DA_MARK = {"af", "hvad", "bliver", "mellem", "jeg", "ikke", "hvordan", "blev", "kan", "ogsaa"}


def detect_lang(text: str) -> str:
    """Stop word heuristic (the logic of the earlier measurement script sprak.py). Returns en nb nn da sv fi de is or 'ukjent'."""
    w = re.findall(r"[a-zæøåäöüéð]+", str(text or "").lower())
    if len(w) < 4:
        return "ukjent"
    sc = {k: sum(1 for x in w if x in s) / len(w) for k, s in _SW.items()}
    best = max(sc, key=sc.get)
    if sc[best] < 0.08:
        return "ukjent"
    if best in ("nb", "nn", "da"):
        wl = set(w)
        a = len(wl & _NN_MARK)
        b = len(wl & _NB_MARK)
        d = len(wl & _DA_MARK)
        if a > b and a > 0:
            return "nn"
        if d > 0 and ({"af", "hvad", "bliver", "mellem", "blev"} & wl):
            return "da"
        return "nb"
    return best


def abstract_lang(text: str) -> str:
    code = detect_lang(text[:600])
    return code if code in ("en", "nb", "nn", "da", "sv", "fi", "de") else "und"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def surname(name: str) -> str:
    n = str(name or "").strip()
    if "," in n:
        n = n.split(",", 1)[0]
    else:
        parts = n.split()
        n = parts[-1] if parts else ""
    return fold(n).strip()


def doc_prompt_parts(title: str, abstract: str) -> tuple[str, str]:
    """(title slot, text slot) of the document prompt `title: <t> | text: <x>` (spec 4.7)."""
    t = " ".join(str(title or "").split())
    a = " ".join(str(abstract or "").split())
    if a:
        return t or "none", a
    return "none", t


def doc_prompt(title: str, abstract: str) -> str:
    t, x = doc_prompt_parts(title, abstract)
    return f"title: {t} | text: {x}"


# --- loading --------------------------------------------------------------------------------------
def load_corpus() -> tuple[list[dict], list[str]]:
    """Works in canonical order (publications then nordic_additions) with a `_layer` key."""
    pubs = read_json(DOCS_DATA_DIR / "publications.json", []) or []
    nordic = read_json(DOCS_DATA_DIR / "nordic_additions.json", []) or []
    works = [dict(w, _layer="openalex") for w in pubs] + [dict(w, _layer="nordic") for w in nordic]
    return works, [w["id"] for w in works]


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)


def load_openalex_abstracts() -> dict[str, str]:
    """work id -> cleaned abstract (>= 50 chars) from the raw OpenAlex table. Read-only."""
    if not RAW_SQLITE.is_file():
        raise FileNotFoundError(f"{RAW_SQLITE} not found; the abstracts cannot be rebuilt without it")
    con = _ro(RAW_SQLITE)
    try:
        out = {}
        for wid, a in con.execute("SELECT id, abstract FROM works WHERE in_scope=1"):
            c = clean_abstract(a)
            if len(c) >= OA_ABSTRACT_MIN:
                out[wid] = c
        return out
    finally:
        con.close()


# --- access codes ---------------------------------------------------------------------------------
def _is_doi_link(url: str, doi: str) -> bool:
    u = str(url or "").strip()
    if not u:
        return False
    low = u.lower()
    if re.match(r"^https?://(?:dx\.)?doi\.org/", low):
        return True
    return bool(doi and u == doi)


def classify_access(works: list[dict], manifest: dict, found: dict) -> list[dict]:
    """Per work: {acc, url, license, ext, doi_url} following spec 4.5 and the DOI rule of amendment 1."""
    from .pdf import allowed_url, safe_public_link, HOST_DENY

    out = []
    for w in works:
        wid = w["id"]
        doi = str(w.get("doi") or "")
        rec = {"acc": "0", "url": "", "license": "", "ext": "", "doi": doi}
        if wid in manifest:
            f = found.get(wid) or {}
            rec.update(acc="h", url=f"{REPO_RAW_BASE}/pdf/{wid}.pdf", license=str(manifest[wid].get("license") or ""),
                       ext=str(f.get("url") or ""))
        elif wid in found and found[wid].get("status") == "verified-oa-link" and safe_public_link(found[wid].get("url")) \
                and not any(b in str(found[wid].get("url")).lower() for b in HOST_DENY):
            rec.update(acc="v", url=str(found[wid]["url"]))
        else:
            cand = ""
            only_doi_link = ""
            for key in ("oa_url", "source_url"):
                u = str(w.get(key) or "").strip()
                if not u:
                    continue
                if _is_doi_link(u, doi):
                    only_doi_link = only_doi_link or u
                    continue
                if allowed_url(u) and not any(b in u.lower() for b in HOST_DENY):
                    cand = u
                    break
            if cand:
                rec.update(acc="u", url=cand)
            elif doi or only_doi_link:
                rec.update(acc="d", url=("" if doi else only_doi_link))
        out.append(rec)
    return out


# --- duplicates ------------------------------------------------------------------------------------
def possible_duplicates(works: list[dict], acc: list[dict]) -> tuple[list[bool], dict]:
    """Flag d (amendment 10): the archive's own 'possible-duplicate' works, plus every non-primary member of a
    group with the same normalized title, year +/-1 and a shared author surname among the remaining works."""
    n = len(works)
    flagged = [False] * n
    archive = 0
    for i, w in enumerate(works):
        if w.get("duplicate_status") == "possible-duplicate":
            flagged[i] = True
            archive += 1
    groups: dict[str, list[int]] = collections.defaultdict(list)
    for i, w in enumerate(works):
        if flagged[i]:
            continue
        key = normalize_title(w.get("title"))
        if key:
            groups[key].append(i)
    acc_rank = {c: r for r, c in enumerate(("h", "v", "u", "d", "0"))}
    layer_rank = {"openalex": 0, "nordic": 1}
    title_extra = 0
    title_groups = 0
    cross = collections.Counter()
    for members in groups.values():
        if len(members) < 2:
            continue
        sn = {i: {surname(a) for a in (works[i].get("authors") or []) if surname(a)} for i in members}
        parent = {i: i for i in members}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a_i, a in enumerate(members):
            for b in members[a_i + 1:]:
                ya, yb = works[a].get("year"), works[b].get("year")
                if ya is None or yb is None or abs(int(ya) - int(yb)) > 1:
                    continue
                if sn[a] & sn[b]:
                    parent[find(a)] = find(b)
        comps: dict[int, list[int]] = collections.defaultdict(list)
        for i in members:
            comps[find(i)].append(i)
        for comp in comps.values():
            if len(comp) < 2:
                continue
            title_groups += 1
            comp.sort(key=lambda i: (layer_rank[works[i]["_layer"]], acc_rank[acc[i]["acc"]],
                                     -(int(works[i].get("citations") or 0)), i))
            for i in comp[1:]:
                flagged[i] = True
                title_extra += 1
                cross[(works[comp[0]]["_layer"], works[i]["_layer"])] += 1
    return flagged, {"archive_status": archive, "title_groups": title_groups, "title_extra_rows": title_extra,
                     "pairs": {f"{a}->{b}": c for (a, b), c in sorted(cross.items())}}


# --- abstract extraction -----------------------------------------------------------------------------
_HEAD = re.compile(r"^\s*(?:abstract|summary|sammendrag|samandrag|sammanfattning|resum[eé]|tiivistelm[aä]|abstrakt|resumen|zusammenfassung)\s*[:.—–-]?\s*(.*)$", re.I)
_STOP = re.compile(r"^\s*(?:key\s*words?|keywords?|n[oø]kkelord|nyckelord|index terms|emneord|asiasanat|schlagw|1[.\s]+introduc|introduction\b|innledning|inledning|johdanto|contents|innhold|table of contents|acknowledg|forord|preface|\d\.?\s+[A-Z][a-z]+)", re.I)
_KEYWORD_LINE = re.compile(r"^\s*(?:key\s*words?|keywords?|n[oø]kkelord|nyckelord|index terms|emneord|asiasanat)\b", re.I)
_INNER_HEAD = re.compile(r"^\s*(?:keywords?|key\s*words?|n[oø]kkelord|nyckelord|introduction|innledning|inledning|1\.)\s*$", re.I)
# Header/footer residue that the extraction can pick up from a page (e-mail, ISBN/ISSN, copyright, received/accepted lines, URLs, page ranges)
_RESIDUE = (
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("isbn", re.compile(r"\bIS[BS]N\b")),
    ("copyright", re.compile(r"©|\(c\)\s*(?:19|20)\d\d|\bAll rights reserved\b|\bCopyright\b", re.I)),
    ("header-status", re.compile(r"\b(?:Received|Accepted|Revised|Submitted)\b[:\s]+(?:on\s+)?(?:\d|[A-Z][a-z]+\s+\d)|ARTICLE HISTORY|Article history|Available online|Published online")),
    ("url", re.compile(r"\bwww\.|https?://|\bdoi\.org|\bdoi:", re.I)),
    ("correspondence", re.compile(r"Correspondence to|Corresponding author|Author Keywords|\b(?:Fax|Tel)\s*[:.]", re.I)),
    ("bibliographic", re.compile(r"\bpp\.\s*\d")),
    ("affiliation", re.compile(r"\bDepartment of [A-Z]\w+(?: [A-Z]\w+)*,\s+(?:[A-Z]\w+ )*University")),
    ("run-together", re.compile(r"[A-Za-z]{30,}")),
    ("author-bio", re.compile(r"\b(?:B\.A\.|M\.A\.|B\.Sc\.|M\.Sc\.|Ph\.D\.)\s+(?:in|from)\b")),
    ("noise", re.compile(r"(?:\w+!\s+){3,}|^[|!/*_\[\]<>#=~^]|^[|\s]*(?:[ivx]+\s+)?(?:Abstract|Sammendrag|Samandrag|Summary)\b")),
)
_MOJIBAKE = re.compile(r"(?:Ã[\u0080-¿]|â€|Â[ -¿])")


_HYPHEN_BREAK = re.compile(r"(?<![\w-])([^\W\d_]+)- ([^\W\d_]+)")
_COORDINATORS = {"og", "and", "or", "och", "eller", "und", "oder", "en", "ja", "sekä", "tai", "et", "ou", "y", "o"}


def fix_hyphen_breaks(text: str, vocab: set[str] | None = None) -> str:
    """De-hyphenation of text from a PDF. A line-break hyphen shows up as "word- part" ("lat- est", "network- based").
    "kunst- og" and "pre- and" (a coordinated compound) stay as written. Otherwise the break is joined without hyphen when the
    joined word is a word of the corpus (vocab), else the hyphen is kept and only the space is removed ("network-based"). A part that
    starts with a capital letter is a real compound ("Human-Centred")."""
    def rep(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        if b.lower() in _COORDINATORS:
            return m.group(0)
        if b[:1].isupper() or vocab is None:
            return a + "-" + b
        return a + b if (a + b).lower() in vocab else a + "-" + b
    return _HYPHEN_BREAK.sub(rep, text)


def extract_abstract(pages: list[str], vocab: set[str] | None = None) -> tuple[str, str]:
    """Rule from the data measurement: heading Abstract/Sammendrag/... on the first pages, text up to keywords/introduction/new heading.
    Returns (text, reason); reason is '' when the quality filter of spec 4.6 is passed, else why it was rejected.
    `vocab` (lowercase words of the metadata) is used to repair line-break hyphens (fix_hyphen_breaks)."""
    best_reason = "no-heading"
    for page_text in pages:
        lines = (page_text or "").split("\n")
        for k, ln in enumerate(lines):
            m = _HEAD.match(ln)
            if not (m and len(ln.strip()) < 200):
                continue
            buf = [m.group(1)] if m.group(1) else []
            for ln2 in lines[k + 1:]:
                if _KEYWORD_LINE.match(ln2):
                    break
                if _STOP.match(ln2) and len(" ".join(buf)) > 200:
                    break
                buf.append(ln2)
                if len(" ".join(buf)) > EXTRACT_MAX + 600:
                    break
            block = [b.strip() for b in buf if b.strip()]
            raw = "\n".join(block)
            raw = re.sub(r"(\w)-\n(?=[a-zæøåäö])", r"\1- ", raw)
            text = fix_hyphen_breaks(unicodedata.normalize("NFKC", re.sub(r"\s+", " ", raw)).strip(), vocab)
            reason = _quality_reason(block, text)
            if not reason:
                return text, ""
            best_reason = reason if best_reason == "no-heading" else best_reason
    return "", best_reason


def _quality_reason(block: list[str], text: str) -> str:
    if len(text) < 150:
        return "too-short"
    if len(text) < EXTRACT_MIN:
        return "too-short"
    if len(text) > EXTRACT_MAX:
        return "too-long"
    if "�" in text:
        return "fffd"
    if text[:1].islower():
        return "starts-lowercase"  # the block starts in the middle of a sentence
    if _MOJIBAKE.search(text):
        return "mojibake"
    for name, rx in _RESIDUE:
        if rx.search(text):
            return "residue-" + name
    if not re.search(r"[.?!][\"')”’]?$", text):
        return "bad-ending"
    for line in block:
        if _INNER_HEAD.match(line):
            return "inner-heading"
    for idx in range(len(block) - 1):
        cur, nxt = block[idx], block[idx + 1]
        if len(cur) < 25 and not re.search(r"[.!?:;]$", cur) and nxt[:1].islower():
            return "columns"
    return ""


def extract_abstracts(works: list[dict], acc: list[dict], oa: dict[str, str], found: dict, manifest: dict) -> tuple[dict, dict]:
    """Extraction of `x` abstracts. Returns ({id: text}, report). Needs the private cache; skipped when it is missing."""
    report: dict = {"candidates": 0, "no_cache_document": 0, "sha_mismatch": 0, "sha_mismatch_ids": [], "no_cache_ids": [],
                    "rejected": {}, "accepted": 0, "cache_available": PRIVATE_CORPUS_DB.is_file(),
                    "cached_not_verified_excluded": 0}
    out: dict[str, str] = {}
    if not PRIVATE_CORPUS_DB.is_file():
        return out, report
    vocab: set[str] = set()
    for w in works:
        vocab.update(re.findall(r"[^\W\d_]{3,}", (w.get("title") or "").lower()))
    for t in oa.values():
        vocab.update(re.findall(r"[^\W\d_]{3,}", t.lower()))
    con = _ro(PRIVATE_CORPUS_DB)
    try:
        docs: dict[str, set[str]] = collections.defaultdict(set)
        for wid, sha in con.execute("SELECT work_id, sha256 FROM work_documents"):
            docs[wid].add(sha)
        quality = {s: q for s, q in con.execute("SELECT sha256, quality FROM documents")}
        rejected = collections.Counter()
        v_total = v_match = v_nocache = 0
        for w, a in zip(works, acc):
            if a["acc"] in ("h", "v"):
                exp_sha = (manifest.get(w["id"]) or {}).get("sha256") if a["acc"] == "h" else (found.get(w["id"]) or {}).get("sha256")
                v_total += 1
                if w["id"] not in docs:
                    v_nocache += 1
                elif exp_sha in docs[w["id"]]:
                    v_match += 1
        report["verified_total"], report["verified_cache_sha_match"], report["verified_no_cache_document"] = v_total, v_match, v_nocache
        for w, a in zip(works, acc):
            wid = w["id"]
            if wid in oa:
                continue
            if a["acc"] not in ("h", "v"):
                if wid in docs:
                    report["cached_not_verified_excluded"] += 1
                continue
            report["candidates"] += 1
            expected = (manifest.get(wid) or {}).get("sha256") if a["acc"] == "h" else (found.get(wid) or {}).get("sha256")
            if wid not in docs:
                report["no_cache_document"] += 1
                report["no_cache_ids"].append(wid)
                continue
            if expected not in docs[wid]:
                report["sha_mismatch"] += 1
                report["sha_mismatch_ids"].append(wid)
                continue
            if quality.get(expected) != "extracted":
                rejected["not-extracted"] += 1
                continue
            pages = [t for _, t in con.execute("SELECT page, text FROM pages WHERE sha256=? AND page<=4 ORDER BY page", (expected,))]
            text, reason = extract_abstract(pages, vocab)
            if text:
                out[wid] = text
            else:
                rejected[reason] += 1
        report["rejected"] = dict(sorted(rejected.items()))
        report["accepted"] = len(out)
    finally:
        con.close()
    return out, report


# --- config -----------------------------------------------------------------------------------------
def build_stopwords() -> list[str]:
    protected = {"design", "research", "practice", "user", "service", "public", "participation", "craft", "method"}
    sw = sorted({t for word in search_terms.STOPWORDS_TEXT for t in tokenize(word)})
    clash = protected & set(sw)
    if clash:
        raise ValueError(f"protected domain words in stop word list: {sorted(clash)}")
    return sw


def parse_glossary(stopwords: list[str] | None = None) -> list[dict]:
    """GLOSSARY_LINES -> entries. Stop words are dropped from the from-phrases (a query never contains them)."""
    sw = set(stopwords or [])
    entries = []
    for line in search_terms.GLOSSARY_LINES:
        left, right = line.split("=>")
        frm: list[list[str]] = []
        for phrase in left.split("|"):
            toks = [t for t in tokenize(phrase) if t not in sw]
            if toks and toks not in frm:
                frm.append(toks)
        to: list[str] = []
        for phrase in right.split("|"):
            p = " ".join(phrase.split())
            if p and p not in to:
                to.append(p)
        entries.append({"from": frm, "to": to, "w": GLOSSARY_W})
    return entries


def check_glossary(entries: list[dict], stopwords: list[str]) -> dict:
    """Build time checks: no empty entries; single-token from-entries that equal a folded common Norwegian word are listed (amendment 22)."""
    sw = set(stopwords)
    problems = []
    collisions = []
    nofold = {fold(w): w for w in search_terms.NORWEGIAN_FOLD_CHECK if fold(w) != w.lower()}
    for e in entries:
        if not e["from"] or not e["to"]:
            problems.append(f"empty entry {e}")
        for phrase in e["from"]:
            if len(phrase) == 1 and phrase[0] in nofold:
                collisions.append({"token": phrase[0], "norwegian_word": nofold[phrase[0]], "to": e["to"]})
        for p in e["to"]:
            if not [t for t in tokenize(p) if t not in sw]:
                problems.append(f"to-phrase without content tokens: {p}")
    if problems:
        raise ValueError("; ".join(problems))
    return {"entries": len(entries), "collisions": collisions}


TOKENIZER_CASE_INPUTS = [
    "Malmö", "Malmo", "Malmø", "håndverk", "handverk", "Håndværk", "Æble", "æbler og øl", "İstanbul", "Straße", "Łódź",
    "Þórsmörk", "Đorđe", "œuvre", "co-design", "co-creation", "design-for-sustainability", "Service Design 2.0", "web3",
    "ISO 9241-210:2019", "A", "I", "a b c", "to be or not", "  leading and   trailing  ", "tabs\tand\nnewlines",
    "Zürich", "København", "Göteborg", "Tromsø", "Ålesund", "naïve café", "e-mail", "user's guide", "R&D", "UX/UI design",
    "1983", "x1 y22 z333", "Ünal Ñandú", "Kunnskap om taus kunnskap", "Research through design (RtD)", "",
    "—", "été", "ÄÖÜ äöü", "design, research & practice", "Infrastructuring Malmö 2018",
]


def build_config() -> dict:
    sw = build_stopwords()
    glossary = parse_glossary()
    check_glossary(glossary, sw)
    return {"schema": SCHEMA, "fold_map": dict(FOLD_MAP), "stopwords": sw, "glossary": glossary,
            "examples": list(search_terms.EXAMPLES)}


def write_config_and_fixtures() -> dict:
    cfg = build_config()
    write_json(SEARCH_DIR / "search_config.json", cfg, compact=True, sort_keys=True)
    cases = [{"in": s, "tokens": tokenize(s)} for s in TOKENIZER_CASE_INPUTS]
    write_json(FIXTURE_DIR / "tokenizer_cases.json", {"schema": 1, "note": "tokenize(in) per spec 5.1; generated by designteori/search_build.py", "cases": cases}, sort_keys=False)
    return {"stopwords": len(cfg["stopwords"]), "glossary": len(cfg["glossary"]), "cases": len(cases)}


# --- lexical index --------------------------------------------------------------------------------------
def build_lex(works: list[dict], abstracts: dict[str, str], contexts: dict, stopwords: set[str]) -> dict:
    n = len(works)
    postings: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
    doclen = [0] * n
    for i, w in enumerate(works):
        acc = collections.Counter()
        fields = {
            "title": w.get("title") or "",
            "authors": " ; ".join(w.get("authors") or []),
            "venue": " ; ".join(x for x in (w.get("source"), w.get("venue")) if x),
            "abstract": abstracts.get(w["id"], ""),
        }
        ctx = contexts.get(w["id"]) or {}
        seen_inst = set()
        names = []
        for a in ctx.get("authors") or []:
            for inst in a.get("institutions") or []:
                if inst.get("id") not in seen_inst:
                    seen_inst.add(inst.get("id"))
                    names.append(inst.get("name") or "")
        fields["affil"] = " ; ".join(names)
        for field, weight in FIELD_WEIGHTS.items():
            for tok in tokenize(fields.get(field, "")):
                if tok in stopwords:
                    continue
                acc[tok] += weight
        total = 0
        for tok, tf in acc.items():
            tf = min(255, tf)
            postings[tok].append((i, tf))
            total += tf
        doclen[i] = total
    terms = sorted(postings)
    post = []
    pairs = 0
    for t in terms:
        flat: list[int] = []
        prev = 0
        for d, tf in postings[t]:
            flat.append(d - prev)
            flat.append(tf)
            prev = d
        post.append(flat)
        pairs += len(postings[t])
    avgdl = sum(doclen) / n
    return {"schema": SCHEMA, "n": n, "avgdl": avgdl, "k1": BM25_K1, "b": BM25_B, "weights": dict(FIELD_WEIGHTS),
            "doclen": doclen, "terms": terms, "post": post}, {"terms": len(terms), "pairs": pairs}


# --- helpers for files and meta -----------------------------------------------------------------------------
def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


PAGE_FILES = ["search_config.json", "lex.json", "access.json", "about.json", "glossary.json", "search_quality.json",
              "vectors.i8", "similar.bin", "query_vectors.json"]


def file_entries() -> dict:
    entries = {}
    names = [f for f in PAGE_FILES if (SEARCH_DIR / f).is_file()]
    names += sorted(f"abstracts/{p.name}" for p in ABSTRACT_DIR.glob("a*.json")) if ABSTRACT_DIR.is_dir() else []
    for name in names:
        p = SEARCH_DIR / name
        entries[name] = {"bytes": p.stat().st_size, "sha256": sha256_file(p)}
    return entries


def build_id_of(files: dict) -> str:
    return hashlib.sha256("".join(files[k]["sha256"] for k in sorted(files)).encode("ascii")).hexdigest()[:10]


def browser_model_block() -> dict:
    total = sum(MODEL_FILES.values())
    return {
        "library_url": LIBRARY_URL, "library_version": LIBRARY_VERSION, "model_id": MODEL_ID, "dtype": "q8",
        "api": "AutoTokenizer.from_pretrained + AutoModel.from_pretrained(id, {dtype:'q8'}); output.sentence_embedding",
        "download_bytes": total, "download_mb_rounded": int(round(total / 10_000_000) * 10),
        "download_files": dict(sorted(MODEL_FILES.items())), "measured": MODEL_FILES_MEASURED,
        "note": "Single threaded wasm (no COOP/COEP on GitHub Pages): expect seconds per query and 10-30 s session start.",
    }


def write_meta(base: dict, built: str | None = None) -> dict:
    """meta.json is written last in every step so the page always sees a complete state."""
    old = read_json(SEARCH_DIR / "meta.json", {}) or {}
    files = file_entries()
    meta = dict(base)
    meta["schema"] = SCHEMA
    meta["built"] = built or now_iso()
    meta["files"] = files
    meta["build_id"] = build_id_of(files)
    meta["lex"] = {"file": "lex.json"}
    meta["access"] = {"file": "access.json"}
    meta["config"] = {"file": "search_config.json"}
    meta["abstracts"] = {"dir": "abstracts", "shard_size": SHARD_SIZE, "count": len([f for f in files if f.startswith("abstracts/")]),
                         "pattern": "a{NNN}.json"}
    meta["vectors"] = base.get("vectors") if "vectors" in base else old.get("vectors")
    meta["similar"] = base.get("similar") if "similar" in base else old.get("similar")
    meta["query_vectors"] = base.get("query_vectors") if "query_vectors" in base else old.get("query_vectors")
    meta["browser_model"] = browser_model_block()
    meta["about"] = {"file": "about.json"}
    meta["glossary"] = {"file": "glossary.json"}
    meta["quality"] = {"file": "search_quality.json"}
    write_json(SEARCH_DIR / "meta.json", meta, compact=True, sort_keys=True)
    return meta


def load_sources() -> dict:
    """The inputs shared by the stages."""
    works, ids = load_corpus()
    manifest = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items") or {}
    found = read_json(DOCS_DATA_DIR / "pdf_found.json", {}) or {}
    return {"works": works, "ids": ids, "manifest": manifest, "found": found}


def abstracts_from_shards() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if ABSTRACT_DIR.is_dir():
        for p in sorted(ABSTRACT_DIR.glob("a*.json")):
            out.update(read_json(p, {}) or {})
    return out


def embedding_texts(works: list[dict], shard_abs: dict[str, dict]) -> list[tuple[str, str]]:
    return [doc_prompt_parts(w.get("title") or "", (shard_abs.get(w["id"]) or {}).get("t", "")) for w in works]


def text_sha256(works: list[dict], shard_abs: dict[str, dict]) -> str:
    prompts = [f"title: {t} | text: {x}" for t, x in embedding_texts(works, shard_abs)]
    return sha256_bytes("\n".join(prompts).encode("utf-8"))


# --- step A -------------------------------------------------------------------------------------------------------
def stage_lexical() -> dict:
    t0 = time.time()
    SEARCH_DIR.mkdir(parents=True, exist_ok=True)
    cfg_info = write_config_and_fixtures()
    cfg = read_json(SEARCH_DIR / "search_config.json")
    src = load_sources()
    works, ids, manifest, found = src["works"], src["ids"], src["manifest"], src["found"]
    n = len(works)
    if n != len(set(ids)):
        raise ValueError("duplicate ids in the corpus")

    # access codes
    acc = classify_access(works, manifest, found)
    dup_flags, dup_info = possible_duplicates(works, acc)

    # abstracts
    oa = load_openalex_abstracts()
    removed_overlong = sorted(w for w, t in oa.items() if len(t) > MAX_ABSTRACT_CHARS)
    for w in removed_overlong:
        del oa[w]
    xtra, xreport = extract_abstracts(works, acc, oa, found, manifest)
    abstracts: dict[str, dict] = {}
    for w in works:
        wid = w["id"]
        if w["_layer"] == "openalex" and wid in oa:
            abstracts[wid] = {"t": oa[wid], "s": "oa", "l": abstract_lang(oa[wid])}
        elif wid in xtra:
            abstracts[wid] = {"t": xtra[wid], "s": "x", "l": abstract_lang(xtra[wid])}
    pos_of = {wid: i for i, wid in enumerate(ids)}
    for wid, rec in abstracts.items():
        if rec["s"] == "x":
            rec["u"] = acc[pos_of[wid]]["url"]
    # shards
    shards = collections.defaultdict(dict)
    for i, wid in enumerate(ids):
        if wid in abstracts:
            shards[i // SHARD_SIZE][wid] = abstracts[wid]
    nshards = (n + SHARD_SIZE - 1) // SHARD_SIZE
    ABSTRACT_DIR.mkdir(parents=True, exist_ok=True)
    for old in ABSTRACT_DIR.glob("a*.json"):
        old.unlink()
    for k in range(nshards):
        write_json(ABSTRACT_DIR / f"a{k:03d}.json", shards.get(k, {}), compact=True)
    # per-work strings
    abs_str = "".join(("o" if abstracts[w["id"]]["s"] == "oa" else "x") if w["id"] in abstracts else "0" for w in works)
    acc_str = "".join(a["acc"] for a in acc)
    flag_str = []
    for i, w in enumerate(works):
        if dup_flags[i]:
            flag_str.append("d")
        elif w["_layer"] == "nordic" and not (w.get("countries") or w.get("source_country")):
            flag_str.append("u")
        else:
            flag_str.append("0")
    flag_str = "".join(flag_str)
    lang_str = "".join(derive_lang(w, abstracts.get(w["id"])) for w in works)

    # access.json
    items = {}
    for i, a in enumerate(acc):
        wid = ids[i]
        if a["acc"] == "h":
            row = ["h", a["url"], a["license"]]
            if a["ext"]:
                row.append(a["ext"])
            items[wid] = row
        elif a["acc"] in ("v", "u"):
            items[wid] = [a["acc"], a["url"]]
        elif a["acc"] == "d" and a["url"]:
            items[wid] = ["d", a["url"]]
    write_json(SEARCH_DIR / "access.json", {"schema": SCHEMA, "items": items}, compact=True)

    # lex.json
    contexts = read_json(DOCS_DATA_DIR / "work_context.json", {}) or {}
    lex, lex_info = build_lex(works, {k: v["t"] for k, v in abstracts.items()}, contexts, set(cfg["stopwords"]))
    write_json(SEARCH_DIR / "lex.json", lex, compact=True)
    lex_bytes = (SEARCH_DIR / "lex.json").stat().st_size
    import gzip
    lex_gz = len(gzip.compress((SEARCH_DIR / "lex.json").read_bytes(), 9))

    counts = compute_counts(works, acc_str, abs_str, lang_str, flag_str, abstracts, acc)
    counts["dup"] = {"archive_possible": dup_info["archive_status"], "title_group_extra": dup_info["title_extra_rows"],
                     "title_groups": dup_info["title_groups"]}
    built = now_iso()
    about = build_about(works, counts, abstracts, acc, built, dup_info)
    write_json(SEARCH_DIR / "about.json", about, compact=True, sort_keys=True)
    write_glossary_json()

    report = {
        "schema": SCHEMA,
        "abstracts": {"oa": sum(1 for r in abstracts.values() if r["s"] == "oa"), "x": len(xtra),
                      "none": n - len(abstracts)},
        "extraction": {k: v for k, v in xreport.items()},
        "duplicates": dup_info,
        "removed_overlong": removed_overlong,
        "acc": counts["acc"],
        "note": "ids and numbers only; no text from the private cache",
    }
    write_json(SEARCH_DIR / "abstracts_report.json", report, sort_keys=True)

    base = {"n": n, "ids": ids, "lang": lang_str, "abs": abs_str, "acc": acc_str, "flag": flag_str, "counts": counts,
            "vectors": None, "similar": None, "query_vectors": None}
    meta = write_meta(base, built)
    info = {"config": cfg_info, "counts": counts, "lex": dict(lex_info, bytes=lex_bytes, gzip=lex_gz), "extraction": report["extraction"],
            "duplicates": dup_info, "seconds": round(time.time() - t0, 1), "build_id": meta["build_id"]}
    return info


def derive_lang(w: dict, abs_rec: dict | None) -> str:
    """meta.lang (amendment 18): OpenAlex language, then language of the published abstract, then the title heuristic, else u."""
    code = str(w.get("language") or "").lower()
    if code in OPENALEX_LANG:
        c = OPENALEX_LANG[code]
        if code in ("no", "nb"):
            probe = (abs_rec["t"][:600] if abs_rec else w.get("title") or "")
            if detect_lang(probe) == "nn":
                return "n"
        return c
    if code:
        return "o"
    if abs_rec:
        m = LANG_META.get(abs_rec["l"], "u")
        if m != "u":
            return m
    t = detect_lang(w.get("title") or "")
    return LANG_META.get(t, "u") if t != "ukjent" else "u"


def compute_counts(works, acc_str, abs_str, lang_str, flag_str, abstracts, acc) -> dict:
    layers = collections.Counter(w["_layer"] for w in works)
    years = [int(w["year"]) for w in works if w.get("year")]
    srcs = collections.Counter(w.get("source") or "" for w in works if w["_layer"] == "nordic")
    sources = [{"name": "OpenAlex", "n": layers["openalex"]}] + [{"name": k, "n": v} for k, v in sorted(srcs.items(), key=lambda kv: (-kv[1], kv[0]))]
    c_acc = collections.Counter(acc_str)
    c_abs = collections.Counter(abs_str)
    c_lang = collections.Counter(lang_str)
    c_flag = collections.Counter(flag_str)
    return {
        "layers": {"openalex": layers["openalex"], "nordic": layers["nordic"]},
        "acc": {k: c_acc.get(k, 0) for k in ACC_CODES},
        "abs": {"o": c_abs.get("o", 0), "x": c_abs.get("x", 0), "0": c_abs.get("0", 0)},
        "lang": {k: c_lang.get(k, 0) for k in "ebndsfou"},
        "flag": {k: c_flag.get(k, 0) for k in ("0", "d", "u")},
        "year_range": [min(years), max(years)],
        "sources": sources,
        "pdf_verified_total": c_acc.get("h", 0) + c_acc.get("v", 0),
        "pdf_hosted": c_acc.get("h", 0),
    }


def build_about(works, counts, abstracts, acc, built, dup_info) -> dict:
    decades = collections.Counter()
    countries: dict[str, dict] = {}
    kinds = collections.Counter()
    for w in works:
        if w.get("year"):
            decades[f"{(int(w['year']) // 10) * 10}s"] += 1
        for cc in w.get("countries") or []:
            countries.setdefault(cc, {"openalex": 0, "nordic": 0})[w["_layer"]] += 1
        kinds[w.get("kind") or "unknown"] += 1
    by_layer_abs = {l: {"oa": 0, "x": 0, "none": 0} for l in ("openalex", "nordic")}
    by_layer_acc = {l: {"h": 0, "v": 0, "u": 0, "d": 0, "none": 0} for l in ("openalex", "nordic")}
    for w, a in zip(works, acc):
        r = abstracts.get(w["id"])
        by_layer_abs[w["_layer"]]["oa" if r and r["s"] == "oa" else "x" if r else "none"] += 1
        by_layer_acc[w["_layer"]]["none" if a["acc"] == "0" else a["acc"]] += 1
    n_abs = len(abstracts)
    n_en = sum(1 for r in abstracts.values() if r["l"] == "en")
    n_nordic_unk = sum(1 for w in works if w["_layer"] == "nordic" and not (w.get("countries") or w.get("source_country")))
    openalex_gen = (read_json(DOCS_DATA_DIR / "stats.json", {}) or {}).get("generated_at", "")
    return {
        "schema": SCHEMA, "built": built, "openalex_generated_at": openalex_gen, "total": len(works),
        "layers": counts["layers"], "sources": counts["sources"], "year_range": counts["year_range"],
        "decades": dict(sorted(decades.items())),
        "countries": {k: countries[k] for k in sorted(countries)},
        "kinds": dict(sorted(kinds.items())),
        "languages": counts["lang"],
        "abstracts": {"oa": counts["abs"]["o"], "x": counts["abs"]["x"], "none": counts["abs"]["0"],
                      "by_layer": by_layer_abs, "share_en": round(n_en / n_abs, 4) if n_abs else 0},
        "access": {"h": counts["acc"]["h"], "v": counts["acc"]["v"], "u": counts["acc"]["u"], "d": counts["acc"]["d"],
                   "none": counts["acc"]["0"], "by_layer": by_layer_acc},
        "review": {"human_checked": 0, "automatic_title_inclusion": counts["layers"]["openalex"],
                   "metadata_unreviewed": counts["layers"]["nordic"],
                   "possible_duplicates": counts["flag"]["d"],
                   "archive_possible_duplicates": dup_info["archive_status"],
                   "title_group_duplicates": dup_info["title_extra_rows"],
                   "kind_unknown": sum(1 for w in works if w["_layer"] == "nordic" and (w.get("kind") or "unknown") == "unknown"),
                   "without_citations": sum(1 for w in works if w["_layer"] == "nordic"),
                   "affiliation_unknown": n_nordic_unk},
        "pdf_verified_total": counts["pdf_verified_total"], "pdf_hosted": counts["pdf_hosted"],
    }


def write_glossary_json() -> None:
    terms = [{"id": i, "term": t, "nn": nn, "en": en, "no": no, "q": q} for (i, t, nn, en, no, q) in search_terms.GLOSSARY_ENTRIES]
    write_json(SEARCH_DIR / "glossary.json", {"schema": SCHEMA, "terms": terms}, compact=True)


# --- step B ---------------------------------------------------------------------------------------------------------
def _cache_connect() -> sqlite3.Connection:
    VECTOR_CACHE.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(VECTOR_CACHE))
    con.execute("CREATE TABLE IF NOT EXISTS search_doc_vectors (work_id TEXT PRIMARY KEY, text_hash TEXT NOT NULL, dims INTEGER NOT NULL, vector BLOB NOT NULL)")
    return con


def _text_hash(title: str, text: str) -> str:
    return sha256_bytes(f"{title}\x1f{text}\x1f256\x1fq8".encode("utf-8"))


def stage_embed(time_only: int = 0) -> dict:
    os.environ.setdefault("DESIGNTEORI_ORT_CPU", "1")
    os.environ.setdefault("DESIGNTEORI_ORT_THREADS", "4")
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
        except Exception:  # pragma: no cover
            pass
    import numpy as np
    from . import embeddings as E

    works, ids = load_corpus()
    shard_abs = abstracts_from_shards()
    if not shard_abs:
        raise RuntimeError("abstracts/ is empty: run --stage lexical first")
    parts = embedding_texts(works, shard_abs)
    hashes = [_text_hash(t, x) for t, x in parts]
    con = _cache_connect()
    have = {wid: h for wid, h in con.execute("SELECT work_id, text_hash FROM search_doc_vectors")}
    todo = [i for i, wid in enumerate(ids) if have.get(wid) != hashes[i]]
    print(f"embed start: {len(ids)} works, {len(ids) - len(todo)} cached, {len(todo)} to compute, model {E.LOCAL_GEMMA_MODEL}", flush=True)
    t_load = time.time()
    E.ensure_local_gemma()
    print(f"model loaded in {time.time() - t_load:.1f}s", flush=True)

    def run(idx: list[int]) -> None:
        texts = [parts[i][1] for i in idx]
        titles = [parts[i][0] if parts[i][0] != "none" else "" for i in idx]
        vecs = E.embed_local_gemma(texts, dims=DIM, titles=titles, max_tokens=256, batch_size=32)
        con.executemany("INSERT OR REPLACE INTO search_doc_vectors (work_id, text_hash, dims, vector) VALUES (?,?,?,?)",
                        [(ids[i], hashes[i], DIM, np.asarray(vecs[k], dtype="<f4").tobytes()) for k, i in enumerate(idx)])
        con.commit()

    if time_only:
        step = max(1, len(todo) // time_only) if todo else 1
        sample = (todo[::step][:time_only]) if todo else list(range(0, len(ids), max(1, len(ids) // time_only)))[:time_only]
        run(sample[:4])  # warm-up
        t0 = time.time()
        run(sample)
        dt = time.time() - t0
        per = dt / len(sample) * 1000
        est = per * len(todo) / 1000
        info = {"timed_texts": len(sample), "seconds": round(dt, 2), "ms_per_text": round(per, 1),
                "remaining": len(todo), "estimated_minutes": round(est / 60, 1)}
        print("TIMING", json.dumps(info), flush=True)
        return info

    t0 = time.time()
    done0 = len(ids) - len(todo)
    CH = 200
    for s in range(0, len(todo), CH):
        run(todo[s:s + CH])
        done = min(s + CH, len(todo))
        el = time.time() - t0
        eta = el / done * (len(todo) - done) if done else 0
        print(f"embed {done0 + done}/{len(ids)} elapsed {el:.0f}s eta {eta:.0f}s", flush=True)

    # collect, check, quantize
    rows = {wid: np.frombuffer(v, dtype="<f4").copy() for wid, v in con.execute("SELECT work_id, vector FROM search_doc_vectors")}
    missing = [wid for wid in ids if wid not in rows]
    if missing:
        raise RuntimeError(f"{len(missing)} works without vector")
    V = np.stack([rows[wid] for wid in ids]).astype(np.float32)
    norms = np.linalg.norm(V, axis=1)
    q = np.clip(np.rint(V * 127.0), -127, 127).astype(np.int8)
    dq = np.linalg.norm(q.astype(np.float32) / 127.0, axis=1)
    if V.shape != (len(ids), DIM) or not np.all(norms > 0.5) or float(np.abs(dq - 1).max()) > 0.02 or np.any(np.all(q == 0, axis=1)):
        raise RuntimeError(f"vector check failed: shape {V.shape}, norm range {norms.min():.4f}-{norms.max():.4f}, dequantized {dq.min():.4f}-{dq.max():.4f}")
    _write_bytes(SEARCH_DIR / "vectors.i8", q.tobytes())
    print(f"vectors.i8 written: {q.nbytes} bytes, float norm {norms.min():.4f}-{norms.max():.4f}, dequantized {dq.min():.4f}-{dq.max():.4f}", flush=True)

    # sample: a title search finds the work itself in the top 3
    import random
    rnd = random.Random(11)
    pick = rnd.sample(range(len(ids)), 20)
    qv = E.embed_local_gemma([works[i].get("title") or "" for i in pick], dims=DIM, is_query=True, max_tokens=128)
    sims = (qv @ V.T)
    hits = 0
    ranks = []
    for k, i in enumerate(pick):
        order = np.argsort(-sims[k], kind="stable")
        r = int(np.where(order == i)[0][0]) + 1
        ranks.append(r)
        hits += r <= 3
    print(f"self-check: {hits}/20 titles find their own work in the top 3; ranks {sorted(ranks)}", flush=True)
    return {"vectors_bytes": int(q.nbytes), "self_top3": hits, "ranks": sorted(ranks),
            "float_norm": [float(norms.min()), float(norms.max())], "dequantized_norm": [float(dq.min()), float(dq.max())]}


def load_float_vectors(ids: list[str]):
    import numpy as np
    con = _cache_connect()
    rows = {wid: v for wid, v in con.execute("SELECT work_id, vector FROM search_doc_vectors")}
    con.close()
    miss = [w for w in ids if w not in rows]
    if miss:
        raise RuntimeError(f"vector cache lacks {len(miss)} works")
    return np.stack([np.frombuffer(rows[w], dtype="<f4") for w in ids]).astype(np.float32)


# --- step C ---------------------------------------------------------------------------------------------------------
def build_neighbours(V, works: list[dict], k: int = K_NEIGHBOURS):
    """k nearest neighbours by cosine on the float vectors; the work itself and works with the same normalized title are skipped.
    Ties: lowest position."""
    import numpy as np
    n = V.shape[0]
    titles = [normalize_title(w.get("title")) for w in works]
    group: dict[str, list[int]] = collections.defaultdict(list)
    for i, t in enumerate(titles):
        group[t].append(i)
    idx = np.zeros((n, k), dtype=np.uint16)
    sim = np.zeros((n, k), dtype=np.uint8)
    for s in range(0, n, 512):
        blk = V[s:s + 512] @ V.T
        for r in range(blk.shape[0]):
            i = s + r
            blk[r, i] = -9
            if titles[i]:
                for j in group[titles[i]]:
                    blk[r, j] = -9
        part = np.argpartition(-blk, k + 8, axis=1)[:, :k + 8]
        for r in range(blk.shape[0]):
            cand = part[r]
            order = sorted(cand.tolist(), key=lambda j: (-float(blk[r, j]), j))[:k]
            idx[s + r] = order
            sim[s + r] = np.clip(np.rint(np.array([blk[r, j] for j in order]) * 255), 0, 255).astype(np.uint8)
    return idx, sim


def encode_queries(keys: list[str]) -> dict[str, "np.ndarray"]:
    """Query vectors (int8, 256) for the keys; published ones are reused so the files stay stable."""
    import numpy as np
    have = {}
    qpath = SEARCH_DIR / "query_vectors.json"
    old = read_json(qpath, {}) or {}
    for k, b in (old.get("queries") or {}).items():
        have[k] = np.frombuffer(base64.b64decode(b), dtype=np.int8).copy()
    need = [k for k in keys if k not in have]
    if need:
        from . import embeddings as E
        os.environ.setdefault("DESIGNTEORI_ORT_CPU", "1")
        os.environ.setdefault("DESIGNTEORI_ORT_THREADS", "4")
        vecs = E.embed_local_gemma(need, dims=DIM, is_query=True, max_tokens=128)
        for k, v in zip(need, vecs):
            have[k] = np.clip(np.rint(v * 127.0), -127, 127).astype(np.int8)
    return {k: have[k] for k in keys}


def write_query_vectors(keys: list[str]) -> None:
    vecs = dict(encode_queries(sorted(set(keys))))
    # ASCII alias of keys that contain diacritics ("infrastructuring malmo" gets the vector of "infrastructuring malmö"),
    # so typing Malmo and Malmö gives the same answer. The alias is itself a valid query_key.
    for k in list(vecs):
        fk = query_key(fold(k))
        if fk != k and fk not in vecs:
            vecs[fk] = vecs[k]
    payload = {"schema": SCHEMA, "model": "google/embeddinggemma-300m", "dim": DIM, "scale": 127,
               "queries": {k: base64.b64encode(v.tobytes()).decode("ascii") for k, v in sorted(vecs.items())}}
    write_json(SEARCH_DIR / "query_vectors.json", payload, compact=True)


def benchmark_keys() -> list[str]:
    keys = [query_key(e["q"]) for e in search_terms.EXAMPLES]
    bq = read_json(SEARCH_DIR / "benchmark_queries.json", None)
    if bq:
        keys += [query_key(q["text"]) for q in bq["queries"]]
    return keys


def stage_finish(draft: str | None = None) -> dict:
    import numpy as np
    works, ids = load_corpus()
    n = len(ids)
    vec_path = SEARCH_DIR / "vectors.i8"
    if not vec_path.is_file() or vec_path.stat().st_size != n * DIM:
        raise RuntimeError("vectors.i8 missing or wrong size: run --stage embed first")
    V = load_float_vectors(ids)
    if not (SEARCH_DIR / "similar.bin").is_file() or os.environ.get("DESIGNTEORI_REBUILD_SIMILAR") == "1":
        idx, sim = build_neighbours(V, works)
        _write_bytes(SEARCH_DIR / "similar.bin", idx.astype("<u2").tobytes() + sim.tobytes())
        print(f"similar.bin written: {idx.nbytes + sim.nbytes} bytes", flush=True)
    meta0 = read_json(SEARCH_DIR / "meta.json", {}) or {}
    shard_abs = abstracts_from_shards()
    if draft:
        dq = read_json(Path(draft), None)
        keys = [query_key(e["q"]) for e in search_terms.EXAMPLES] + [query_key(q["text"]) for q in dq["queries"]]
        write_query_vectors(keys)
        base = _meta_base(meta0, works, shard_abs, n)
        write_meta(base, meta0.get("built"))
        return {"draft_queries": len(dq["queries"]), "query_vectors": len(set(keys))}
    if not (SEARCH_DIR / "benchmark_queries.json").is_file():
        raise RuntimeError("benchmark_queries.json is missing (use --draft to only encode draft queries)")
    write_query_vectors(benchmark_keys())
    base = _meta_base(meta0, works, shard_abs, n)
    write_meta(base, meta0.get("built"))
    from . import search_eval
    quality = search_eval.run_benchmark(write=True)
    meta0 = read_json(SEARCH_DIR / "meta.json", {}) or {}
    base = _meta_base(meta0, works, shard_abs, n)
    meta = write_meta(base, meta0.get("built"))
    return {"quality": quality["summary"], "build_id": meta["build_id"]}


def refresh_meta() -> dict:
    """Rewrite meta.json after a file changed (hashes, build_id), keeping the built date."""
    works, ids = load_corpus()
    meta0 = read_json(SEARCH_DIR / "meta.json", {}) or {}
    return write_meta(_meta_base(meta0, works, abstracts_from_shards(), len(ids)), meta0.get("built"))


def _meta_base(meta0: dict, works: list[dict], shard_abs: dict, n: int) -> dict:
    base = {k: meta0[k] for k in ("n", "ids", "lang", "abs", "acc", "flag", "counts") if k in meta0}
    base["vectors"] = {
        "file": "vectors.i8", "dim": DIM, "dtype": "int8", "scale": 127, "n": n, "model": "google/embeddinggemma-300m",
        "variant": "onnx-community model_quantized (q8)", "doc_prompt": "title: {title|none} | text: {text}",
        "query_prompt": "task: search result | query: {text}", "doc_max_tokens": 256, "query_max_tokens": 128,
        "text_sha256": text_sha256(works, shard_abs),
    }
    base["similar"] = {"file": "similar.bin", "k": K_NEIGHBOURS, "id_bytes": 2, "sim_scale": 255}
    base["query_vectors"] = {"file": "query_vectors.json"}
    return base


# --- network check (HEAD only) ----------------------------------------------------------------------------------------
def stage_modelcheck() -> dict:
    """HEAD requests for the files the browser model downloads. No body is fetched."""
    import urllib.request

    def head(url: str) -> int:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "designteori-modelcheck"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(r.headers.get("Content-Length") or 0)

    base = f"https://cdn.jsdelivr.net/npm/@huggingface/transformers@{LIBRARY_VERSION}/dist/"
    hf = f"https://huggingface.co/{MODEL_ID}/resolve/main/"
    urls = {
        "huggingface.co/onnx/model_quantized.onnx_data": hf + "onnx/model_quantized.onnx_data",
        "huggingface.co/onnx/model_quantized.onnx": hf + "onnx/model_quantized.onnx",
        "huggingface.co/tokenizer.json": hf + "tokenizer.json",
        "huggingface.co/tokenizer_config.json": hf + "tokenizer_config.json",
        "huggingface.co/config.json": hf + "config.json",
        "cdn.jsdelivr.net/transformers.min.js": base + "transformers.min.js",
        "cdn.jsdelivr.net/ort-wasm-simd-threaded.jsep.wasm": base + "ort-wasm-simd-threaded.jsep.wasm",
        "cdn.jsdelivr.net/ort-wasm-simd-threaded.jsep.mjs": base + "ort-wasm-simd-threaded.jsep.mjs",
    }
    out = {}
    for k, u in urls.items():
        if k.startswith("cdn.jsdelivr.net/"):
            continue
        try:
            out[k] = head(u)
        except Exception as err:  # noqa: BLE001
            out[k] = f"error: {err}"
    # jsDelivr answers HEAD without Content-Length (compressed); its package API lists the real file sizes.
    try:
        with urllib.request.urlopen(f"https://data.jsdelivr.com/v1/package/npm/@huggingface/transformers@{LIBRARY_VERSION}/flat", timeout=30) as r:
            listing = json.load(r)
        sizes = {f["name"]: f["size"] for f in listing.get("files", [])}
        for k, u in urls.items():
            if k.startswith("cdn.jsdelivr.net/"):
                out[k] = sizes.get("/dist/" + u.rsplit("/", 1)[1], "missing")
    except Exception as err:  # noqa: BLE001
        out["jsdelivr"] = f"error: {err}"
    print(json.dumps(out, indent=2), flush=True)
    return out


# --- command line ---------------------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build-search", description="Build docs/data/search/")
    ap.add_argument("--stage", required=True, choices=("config", "lexical", "embed", "finish", "modelcheck"))
    ap.add_argument("--time-only", type=int, default=0, help="embed: time N texts, print an estimate and stop")
    ap.add_argument("--draft", default="", help="finish: only encode the queries of this draft file (no benchmark)")
    a = ap.parse_args(argv)
    if a.stage == "config":
        res = write_config_and_fixtures()
    elif a.stage == "lexical":
        res = stage_lexical()
    elif a.stage == "embed":
        res = stage_embed(a.time_only)
    elif a.stage == "finish":
        res = stage_finish(a.draft or None)
    else:
        res = stage_modelcheck()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
