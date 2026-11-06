"""Unified hybrid search (FTS5 + Google EmbeddingGemma vectors + PDF page chunks)."""
from __future__ import annotations

import gzip
import re
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import (
    DOCS_DATA_DIR,
    PDF_DIR,
    PRIVATE_CORPUS_DB,
    REPO_RAW_BASE,
    UNIFIED_SQLITE_GZ,
    read_json,
)
from .embeddings import (
    DEFAULT_MODEL,
    dequantize_int8,
    model_name,
    query_embedding,
)

TOKEN_RE = re.compile(r"[\w\-]{2,}", re.UNICODE)


def safe_fts_query(raw: str) -> str:
    tokens = [t.strip("-_") for t in TOKEN_RE.findall(str(raw or ""))]
    tokens = [t for t in tokens if len(t) >= 2]
    if not tokens:
        return ""
    return " ".join(f'"{t.replace(chr(34), "")}"*' for t in tokens[:12])


def reciprocal_rank_fusion(*ranked_id_lists: list[str], k: int = 60,
                           weights: list[float] | None = None) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for list_idx, id_list in enumerate(ranked_id_lists):
        w = weights[list_idx] if weights and list_idx < len(weights) else 1.0
        seen: set[str] = set()
        for rank, item_id in enumerate(id_list, start=1):
            if item_id in seen:
                continue
            seen.add(item_id)
            scores[item_id] += w / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def _load_catalog_map() -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    repo_pdfs = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
    for fname, layer in (
        ("publications.json", "openalex"),
        ("nordic_additions.json", "nordic"),
    ):
        for row in read_json(DOCS_DATA_DIR / fname, []) or []:
            wid = row["id"]
            pdf_url = row.get("pdf") or (
                f"{REPO_RAW_BASE}/{repo_pdfs[wid]['file']}" if wid in repo_pdfs else ""
            )
            catalog[wid] = {**row, "layer": layer, "pdf": pdf_url}
    return catalog


def search_corpus(
    query: str,
    *,
    mode: str = "hybrid",
    limit: int = 20,
    country: str = "",
    year_min: int | None = None,
    year_max: int | None = None,
    pdf_only: bool = False,
    fulltext: bool = True,
    model: str = DEFAULT_MODEL,
    corpus_db: Path = PRIVATE_CORPUS_DB,
) -> list[dict]:
    """Search metadata, Google work embeddings, and full-text PDF chunks with RRF."""
    q = str(query or "").strip()
    if not q:
        return []
    mode = mode.lower()
    if mode not in ("hybrid", "lexical", "semantic"):
        raise ValueError(f"Unsupported search mode: {mode!r}")

    catalog = _load_catalog_map()
    fts_q = safe_fts_query(q)

    lexical_ranked: list[str] = []
    semantic_ranked: list[str] = []
    chunk_lexical_ranked: list[str] = []
    chunk_semantic_ranked: list[str] = []
    best_excerpts: dict[str, dict] = {}
    sem_scores: dict[str, float] = {}

    # 1. Lexical metadata search
    if mode in ("hybrid", "lexical") and fts_q:
        q_terms = [t.casefold() for t in TOKEN_RE.findall(q) if len(t) >= 2]
        lex_hits = []
        for wid, w in catalog.items():
            hay = " ".join([
                str(w.get("title") or ""),
                " ".join(w.get("authors") or []) if isinstance(w.get("authors"), list) else str(w.get("authors") or ""),
                str(w.get("source") or ""),
                str(w.get("topic") or ""),
                str(w.get("keyword_categories") or ""),
            ]).casefold()
            matched = sum(1 for term in q_terms if term in hay)
            if matched:
                title_cf = str(w.get("title") or "").casefold()
                title_hits = sum(1 for term in q_terms if term in title_cf)
                exact_phrase = 2 if q.casefold() in title_cf else 0
                lex_hits.append((-(matched * 3 + title_hits * 2 + exact_phrase), -(w.get("citations") or 0), wid))
        lex_hits.sort()
        lexical_ranked = [wid for _, _, wid in lex_hits[:300]]

    # 2. Google EmbeddingGemma semantic work-vector search
    sem_meta = read_json(DOCS_DATA_DIR / "semantic_index.json", {}) or {}
    vec_bin = DOCS_DATA_DIR / "semantic_vectors.bin"
    if mode in ("hybrid", "semantic") and sem_meta and vec_bin.is_file():
        dims = int(sem_meta.get("dimensions") or 128)
        ids = sem_meta.get("ids") or []
        raw_bytes = vec_bin.read_bytes()
        if len(raw_bytes) == len(ids) * dims and len(ids) > 0:
            try:
                q_vec = np.asarray(query_embedding(q, model=model, dims=dims), dtype=np.float32)
                q_norm = float(np.linalg.norm(q_vec))
                if q_norm > 1e-12:
                    q_vec = q_vec / q_norm
                    mat = dequantize_int8(raw_bytes, dims)
                    sims = mat @ q_vec
                    top_k = min(300, len(ids))
                    top_idx = np.argpartition(-sims, top_k - 1)[:top_k]
                    top_idx = top_idx[np.argsort(-sims[top_idx])]
                    for idx in top_idx:
                        wid = ids[int(idx)]
                        semantic_ranked.append(wid)
                        sem_scores[wid] = round(float(sims[int(idx)]), 4)
            except Exception:
                pass

    # 3. Full-text PDF chunk FTS5 + dense Google chunk embeddings (`corpus.sqlite`)
    if fulltext and Path(corpus_db).is_file():
        conn = sqlite3.connect(f"file:{Path(corpus_db).as_posix()}?mode=ro", uri=True)
        try:
            if mode in ("hybrid", "lexical") and fts_q:
                rows = conn.execute("""
                    SELECT wd.work_id, c.page, snippet(chunks_fts, 0, '[', ']', ' … ', 28),
                           bm25(chunks_fts) AS rank_score
                    FROM chunks_fts
                    JOIN chunks c ON c.rowid = chunks_fts.rowid
                    JOIN work_documents wd ON wd.sha256 = c.sha256
                    WHERE chunks_fts MATCH ?
                    ORDER BY rank_score LIMIT 250
                """, (fts_q,)).fetchall()
                for wid, page, snip, _ in rows:
                    chunk_lexical_ranked.append(wid)
                    if wid not in best_excerpts:
                        best_excerpts[wid] = {"page": page, "snippet": snip, "match": "fulltext-fts"}

            if mode in ("hybrid", "semantic"):
                m_clean = model_name(model)
                dim_row = conn.execute(
                    "SELECT dimensions, COUNT(*) FROM embeddings WHERE model=? GROUP BY dimensions ORDER BY COUNT(*) DESC LIMIT 1",
                    (m_clean,),
                ).fetchone()
                if dim_row and dim_row[1] > 0:
                    c_dims = int(dim_row[0])
                    q_cvec = np.asarray(query_embedding(q, model=m_clean, dims=c_dims), dtype=np.float32)
                    qn = float(np.linalg.norm(q_cvec))
                    if qn > 1e-12:
                        q_cvec = q_cvec / qn
                        emb_rows = conn.execute("""
                            SELECT e.chunk_id, wd.work_id, c.page, substr(c.text, 1, 280), e.vector
                            FROM embeddings e
                            JOIN chunks c ON c.chunk_id = e.chunk_id
                            JOIN work_documents wd ON wd.sha256 = c.sha256
                            WHERE e.model=? AND e.dimensions=?
                        """, (m_clean, c_dims)).fetchall()
                        if emb_rows:
                            blobs = b"".join(r[4] for r in emb_rows)
                            c_mat = np.frombuffer(blobs, dtype="<f4").reshape(len(emb_rows), c_dims)
                            c_sims = c_mat @ q_cvec
                            tk = min(200, len(emb_rows))
                            t_idx = np.argpartition(-c_sims, tk - 1)[:tk]
                            t_idx = t_idx[np.argsort(-c_sims[t_idx])]
                            for i in t_idx:
                                _, wid, page, preview, _ = emb_rows[int(i)]
                                chunk_semantic_ranked.append(wid)
                                if wid not in best_excerpts:
                                    best_excerpts[wid] = {
                                        "page": page,
                                        "snippet": preview.strip() + " …",
                                        "match": "fulltext-semantic",
                                        "chunk_cosine": round(float(c_sims[int(i)]), 4),
                                    }
        finally:
            conn.close()

    fused = reciprocal_rank_fusion(
        lexical_ranked, semantic_ranked, chunk_lexical_ranked, chunk_semantic_ranked,
        k=60, weights=[1.2, 1.0, 1.3, 1.1],
    )

    results = []
    cc_upper = country.strip().upper()
    for wid, rrf_score in fused:
        w = catalog.get(wid)
        if not w:
            continue
        if cc_upper:
            w_cs = set(w.get("countries") or [])
            if w.get("source_country"):
                w_cs.add(w["source_country"])
            if cc_upper not in w_cs:
                continue
        yr = w.get("year")
        if year_min is not None and (not isinstance(yr, int) or yr < year_min):
            continue
        if year_max is not None and (not isinstance(yr, int) or yr > year_max):
            continue
        if pdf_only and not w.get("pdf"):
            continue
        results.append({
            "id": wid,
            "layer": w.get("layer", ""),
            "scope": w.get("scope", ""),
            "title": w.get("title", ""),
            "year": yr,
            "authors": w.get("authors") or [],
            "source": w.get("source", ""),
            "countries": w.get("countries") or ([w["source_country"]] if w.get("source_country") else []),
            "doi": w.get("doi", ""),
            "citations": w.get("citations"),
            "pdf": w.get("pdf", ""),
            "oa_url": w.get("oa_url", ""),
            "rrf_score": round(rrf_score, 5),
            "semantic_cosine": sem_scores.get(wid),
            "excerpt": best_excerpts.get(wid),
        })
        if len(results) >= limit:
            break
    return results

