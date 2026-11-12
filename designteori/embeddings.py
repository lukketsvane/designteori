"""Google embeddings engine for DESIGNTEORI (metadata & full-text chunks).

Supports two official Google DeepMind embedding backends:
1. `embeddinggemma-300m` (default, local on-device via ONNX Runtime):
   Google DeepMind's multilingual Gemma-3 embedding model (100+ languages,
   Matryoshka 768/512/256/128 dimensions). Runs 100% locally so unreviewed
   full-text PDFs never leave the researcher's machine.
2. `gemini-embedding-001` (cloud via Google Gemini API, requires GOOGLE_API_KEY
   or GEMINI_API_KEY and explicit `consent_cloud=True`).
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import struct
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, urlretrieve

import numpy as np

from . import (
    DOCS_DATA_DIR,
    MODEL_CACHE_DIR,
    PRIVATE_CACHE,
    PRIVATE_CORPUS_DB,
    now_iso,
    read_json,
    write_json,
)

LOCAL_GEMMA_MODEL = "embeddinggemma-300m"
CLOUD_GEMINI_MODEL = "gemini-embedding-001"
DEFAULT_MODEL = os.environ.get("GOOGLE_EMBEDDING_MODEL", LOCAL_GEMMA_MODEL)
ALLOWED_DIMENSIONS = (128, 256, 512, 768, 1536, 3072)

HF_ONNX_BASE = "https://huggingface.co/onnx-community/embeddinggemma-300m-ONNX/resolve/main/"
HF_ONNX_FILES = (
    "tokenizer.json",
    "config.json",
    "onnx/model_quantized.onnx",
    "onnx/model_quantized.onnx_data",
)

_LOCAL_ENGINE_CACHE: dict[str, tuple[object, object]] = {}


def model_name(raw: str) -> str:
    value = str(raw or "").removeprefix("models/").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise ValueError(f"Invalid embedding model name: {raw!r}")
    return value


def is_local_gemma(model: str) -> bool:
    m = model_name(model).lower()
    return "embeddinggemma" in m


def normalize_rows(matrix: np.ndarray, dims: int | None = None) -> np.ndarray:
    arr = np.asarray(matrix, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[None, :]
    if dims is not None and dims < arr.shape[1]:
        arr = arr[:, :dims]
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    if np.any(~np.isfinite(norms)) or np.any(norms < 1e-15):
        raise ValueError("Zero or non-finite embedding vector")
    return arr / norms


def pack_vector(values, dimensions: int) -> bytes:
    vec = np.asarray(values, dtype=np.float32).reshape(-1)
    if vec.shape[0] < dimensions:
        raise ValueError(f"Expected at least {dimensions} values, got {vec.shape[0]}")
    vec = vec[:dimensions]
    if not np.all(np.isfinite(vec)):
        raise ValueError("Non-finite vector from embedding provider")
    norm = float(np.linalg.norm(vec))
    if norm < 1e-15:
        raise ValueError("Zero embedding vector")
    vec = vec / norm
    return struct.pack(f"<{dimensions}f", *vec.tolist())


def unpack_vector(blob: bytes, dimensions: int) -> tuple[float, ...]:
    if len(blob) != dimensions * 4:
        raise ValueError("Invalid embedding blob size")
    return struct.unpack(f"<{dimensions}f", blob)


def quantize_int8(unit_vectors: np.ndarray) -> bytes:
    """Quantize L2-normalized vectors to int8 [-127, 127] (1 byte/dim)."""
    scaled = np.clip(np.rint(unit_vectors * 127.0), -127, 127).astype(np.int8)
    return scaled.tobytes()


def dequantize_int8(blob: bytes, dims: int) -> np.ndarray:
    arr = np.frombuffer(blob, dtype=np.int8).astype(np.float32).reshape(-1, dims)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / np.maximum(norms, 1e-12)


def ensure_local_gemma(model_dir: Path = MODEL_CACHE_DIR):
    key = str(model_dir.resolve())
    if key in _LOCAL_ENGINE_CACHE:
        return _LOCAL_ENGINE_CACHE[key]
    import onnxruntime as ort
    from tokenizers import Tokenizer

    (model_dir / "onnx").mkdir(parents=True, exist_ok=True)
    for rel in HF_ONNX_FILES:
        dest = model_dir / rel
        if not dest.is_file() or dest.stat().st_size < 64:
            print(f"DOWNLOAD_MODEL {rel}", flush=True)
            urlretrieve(HF_ONNX_BASE + rel, dest)

    tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    avail = set(ort.get_available_providers())
    if "DmlExecutionProvider" in avail and os.environ.get("DESIGNTEORI_ORT_CPU") != "1":
        opts.enable_mem_pattern = False
        providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
    else:
        phys_threads = max(4, min(8, (os.cpu_count() or 8) // 2))
        opts.intra_op_num_threads = phys_threads
        opts.inter_op_num_threads = 2
        providers = ["CPUExecutionProvider"]
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(
        str(model_dir / "onnx" / "model_quantized.onnx"),
        sess_options=opts,
        providers=providers,
    )
    _LOCAL_ENGINE_CACHE[key] = (tokenizer, session)
    return tokenizer, session


def embed_local_gemma(texts: list[str], *, dims: int = 768, is_query: bool = False,
                      titles: list[str] | None = None, max_tokens: int = 256,
                      batch_size: int = 32, model_dir: Path = MODEL_CACHE_DIR) -> np.ndarray:
    if dims not in (128, 256, 512, 768):
        raise ValueError("EmbeddingGemma supports Matryoshka dimensions 128, 256, 512, or 768")
    if not texts:
        return np.zeros((0, dims), dtype=np.float32)
    tokenizer, session = ensure_local_gemma(model_dir)
    formatted = []
    for idx, txt in enumerate(texts):
        clean_txt = re.sub(r"\s+", " ", str(txt or "")).strip()
        if is_query:
            formatted.append(f"task: search result | query: {clean_txt}")
        else:
            t = re.sub(r"\s+", " ", str(titles[idx] if titles and idx < len(titles) else "")).strip() or "none"
            formatted.append(f"title: {t} | text: {clean_txt}")

    # Sort by approximate length to minimize padding waste in Transformer attention
    order = sorted(range(len(formatted)), key=lambda i: len(formatted[i]))
    out = np.zeros((len(formatted), dims), dtype=np.float32)

    tokenizer.no_padding()
    tokenizer.enable_truncation(max_length=max_tokens)

    for start in range(0, len(order), batch_size):
        batch_idx = order[start:start + batch_size]
        batch_texts = [formatted[i] for i in batch_idx]
        encodings = tokenizer.encode_batch(batch_texts)
        max_len = max(len(e.ids) for e in encodings)
        input_ids = np.zeros((len(encodings), max_len), dtype=np.int64)
        attention_mask = np.zeros((len(encodings), max_len), dtype=np.int64)
        for row_i, enc in enumerate(encodings):
            n = len(enc.ids)
            input_ids[row_i, :n] = enc.ids
            attention_mask[row_i, :n] = enc.attention_mask
        raw = session.run(
            ["sentence_embedding"],
            {"input_ids": input_ids, "attention_mask": attention_mask},
        )[0]
        normed = normalize_rows(raw, dims=dims)
        for local_i, orig_i in enumerate(batch_idx):
            out[orig_i] = normed[local_i]
    return out


def google_cloud_request(endpoint: str, body: dict, *, key: str | None = None, retries: int = 4) -> dict:
    api_key = key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY / GEMINI_API_KEY is not set.")
    req = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{endpoint}",
        data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except HTTPError as err:
            if err.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                detail = err.read(800).decode("utf-8", "replace")
                raise RuntimeError(f"Google embeddings HTTP {err.code}: {detail}") from err
            wait = err.headers.get("Retry-After", "")
            time.sleep(float(wait) if wait.isdecimal() else min(30.0, 2.0 ** attempt))
        except (URLError, TimeoutError) as err:
            if attempt == retries - 1:
                raise RuntimeError("Google embedding API unreachable") from err
            time.sleep(min(30.0, 2.0 ** attempt))
    raise RuntimeError("Unreachable retry loop")


def batch_embeddings(texts: list[str], model: str = DEFAULT_MODEL, dims: int = 768,
                     *, titles: list[str] | None = None, max_tokens: int = 256,
                     key: str | None = None) -> list[list[float]]:
    m = model_name(model)
    if is_local_gemma(m):
        arr = embed_local_gemma(texts, dims=dims, is_query=False, titles=titles, max_tokens=max_tokens)
        return arr.tolist()
    full_name = "models/" + m
    payload = {
        "requests": [{
            "model": full_name,
            "content": {"parts": [{"text": t}]},
            "taskType": "RETRIEVAL_DOCUMENT",
            "outputDimensionality": dims,
        } for t in texts]
    }
    res = google_cloud_request(f"{m}:batchEmbedContents", payload, key=key)
    vecs = res.get("embeddings") or []
    if len(vecs) != len(texts):
        raise RuntimeError(f"Expected {len(texts)} embeddings, received {len(vecs)}")
    return [item["values"] for item in vecs]


def query_embedding(text: str, model: str = DEFAULT_MODEL, dims: int = 768, *, key: str | None = None) -> list[float]:
    m = model_name(model)
    if is_local_gemma(m):
        arr = embed_local_gemma([text], dims=dims, is_query=True, max_tokens=128)
        return arr[0].tolist()
    full_name = "models/" + m
    payload = {
        "model": full_name,
        "content": {"parts": [{"text": text}]},
        "taskType": "RETRIEVAL_QUERY",
        "outputDimensionality": dims,
    }
    res = google_cloud_request(f"{m}:embedContent", payload, key=key)
    vals = (res.get("embedding") or {}).get("values")
    if not vals:
        raise RuntimeError("No query embedding returned")
    return vals


def embed_corpus_works(works: list[dict], *, dims_public: int = 128, dims_local: int = 256,
                       cache_path: Path | None = None) -> tuple[np.ndarray, dict[str, int]]:
    """Compute/update Google EmbeddingGemma vectors for every work in the corpus.

    Uses an incremental local SQLite vector cache (`work_vector_cache.sqlite` in
    PRIVATE_CACHE) keyed by `(work_id, text_hash)` so repeated builds only embed
    new or modified works!
    """
    import hashlib

    cache_db_path = cache_path or (PRIVATE_CACHE / "work_vector_cache.sqlite")
    cache_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cache_db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS work_vectors (
            work_id TEXT PRIMARY KEY,
            text_hash TEXT NOT NULL,
            dims INTEGER NOT NULL,
            vector BLOB NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()

    max_dims = max(dims_public, dims_local)
    existing = {
        wid: (th, blob)
        for wid, th, d, blob in conn.execute("SELECT work_id, text_hash, dims, vector FROM work_vectors")
        if d == max_dims and len(blob) == max_dims * 4
    }

    pending_indices = []
    pending_titles = []
    pending_texts = []
    pending_hashes = []
    vectors = np.zeros((len(works), max_dims), dtype=np.float32)

    for idx, w in enumerate(works):
        wid = w["id"]
        title = str(w.get("title") or "").strip()
        authors = ", ".join((w.get("authors") or [])[:6]) if isinstance(w.get("authors"), list) else str(w.get("authors") or "")
        parts = [
            title,
            f"Venue: {w.get('source') or w.get('venue') or ''}" if (w.get("source") or w.get("venue")) else "",
            f"Topic: {w.get('topic') or ''}" if w.get("topic") else "",
            f"Categories: {w.get('keyword_categories') or ''}" if w.get("keyword_categories") else "",
            f"Authors: {authors}" if authors else "",
            f"Year: {w.get('year')}" if w.get("year") else "",
        ]
        doc_text = " | ".join(p for p in parts if p)
        th = hashlib.sha256((title + "||" + doc_text).encode("utf-8")).hexdigest()[:24]
        cached = existing.get(wid)
        if cached and cached[0] == th:
            vectors[idx] = np.frombuffer(cached[1], dtype="<f4")
        else:
            pending_indices.append(idx)
            pending_titles.append(title)
            pending_texts.append(doc_text)
            pending_hashes.append((wid, th))

    if pending_indices:
        print(f"EMBED_WORKS computing {len(pending_indices)}/{len(works)} with Google {LOCAL_GEMMA_MODEL}...", flush=True)
        step = 512
        for offset in range(0, len(pending_indices), step):
            sub_idx = pending_indices[offset:offset + step]
            sub_titles = pending_titles[offset:offset + step]
            sub_texts = pending_texts[offset:offset + step]
            sub_hashes = pending_hashes[offset:offset + step]
            computed = embed_local_gemma(
                sub_texts, dims=max_dims, is_query=False,
                titles=sub_titles, max_tokens=48, batch_size=32,
            )
            now = now_iso()
            rows_to_save = []
            for local_i, orig_idx in enumerate(sub_idx):
                vec = computed[local_i]
                vectors[orig_idx] = vec
                wid, th = sub_hashes[local_i]
                rows_to_save.append((wid, th, max_dims, vec.astype("<f4").tobytes(), now))
            with conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO work_vectors VALUES (?,?,?,?,?)",
                    rows_to_save,
                )
            print(f"EMBED_WORKS {min(offset + step, len(pending_indices))}/{len(pending_indices)}", flush=True)

    conn.close()
    id_to_row = {w["id"]: i for i, w in enumerate(works)}
    return vectors, id_to_row


def export_public_semantic_index(works: list[dict], vectors: np.ndarray, *, dims: int = 128,
                                 out_dir: Path = DOCS_DATA_DIR) -> dict:
    """Write compact int8 Matryoshka vectors + anchor query vectors for GitHub Pages."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pub_vecs = normalize_rows(vectors, dims=dims)
    bin_bytes = quantize_int8(pub_vecs)
    bin_path = out_dir / "semantic_vectors.bin"
    bin_path.write_bytes(bin_bytes)

    # Precompute semantic query vectors for 24 key Nordic & English research themes
    # so instant zero-download concept search works in <2ms on GitHub Pages, alongside
    # full live WASM EmbeddingGemma query encoding!
    theme_queries = {
        "participatory-design": "Scandinavian participatory design, workplace democracy, user participation, brukermedvirkning",
        "codesign": "Co-design, collaborative design, samskaping, medskabelse, brugerinddragelse",
        "research-through-design": "Research through design, constructive design research, practice-based artistic design inquiry",
        "design-theory-epistemology": "Design theory, design epistemology, designerly ways of knowing, philosophy of design, designteori",
        "service-systemic-design": "Service design, systemic design, public sector innovation, tjenestedesign, tjänstedesign",
        "sustainable-circular": "Sustainable design, circular economy, ecological transition, planetary boundaries, bærekraftig design",
        "critical-speculative": "Critical design, speculative design, design fiction, discursive design, adversarial design",
        "interaction-hci-ai": "Interaction design, human-computer interaction, tangible computing, AI in design, interaksjonsdesign",
        "design-history-nordic": "Nordic design history, Scandinavian modern, brukskunst, material culture, museum studies, muotoiluhistoria",
        "craft-materiality-textile": "Craft research, materiality, textile design, formgiving, formgjeving, keramikk, sloyd",
        "aesthetics-form": "Design aesthetics, form theory, gestaltning, sensory experience, somaesthetics",
        "design-education-pedagogy": "Design education, studio pedagogy, design didactics, designdidaktikk, learning in design",
        "design-ethics-justice": "Design ethics, design justice, inclusivity, universal design, universell utforming, decolonizing design",
        "design-anthropology": "Design anthropology, ethnography in design, everyday life practices",
        "industrial-product": "Industrial design, product development, ergonomics, engineering design, industridesign, muotoilu",
        "urban-architecture": "Architectural theory, urban design, landscape, public space, arkitekturteori",
    }
    q_keys = list(theme_queries.keys())
    q_vecs = embed_local_gemma(list(theme_queries.values()), dims=dims, is_query=True, max_tokens=64)
    presets = {
        k: [round(float(x), 5) for x in q_vecs[i]]
        for i, k in enumerate(q_keys)
    }

    meta = {
        "model": f"google/{LOCAL_GEMMA_MODEL}",
        "count": len(works),
        "dimensions": dims,
        "quantization": "int8_unit_norm",
        "ids": [w["id"] for w in works],
        "presets": presets,
    }
    write_json(out_dir / "semantic_index.json", meta, compact=True)

    # Precompute compact multilingual design-theory vocabulary vectors (int8 base64)
    # so mobile browsers (iOS Safari) execute instant (<2 ms) Google EmbeddingGemma
    # semantic queries without downloading a 300 MB ONNX WASM model.
    import base64
    from collections import Counter

    token_re = re.compile(r"[a-zæøåäöüþð]{4,}")
    stop = {
        "with", "from", "into", "through", "toward", "towards", "between", "using",
        "based", "this", "that", "their", "these", "those", "have", "been", "were",
        "what", "when", "where", "which", "while", "about", "after", "before", "under",
        "over", "within", "across", "among", "beyond", "more", "most", "some", "such",
        "only", "also", "other", "both", "each", "many", "much", "very", "just",
        "eller", "ikkje", "ikke", "frå", "mellom", "gjennom", "korleis", "hvordan",
    }
    df: Counter[str] = Counter()
    for w in works:
        txt = f"{w.get('title') or ''} {w.get('topic') or ''}".lower()
        for tok in set(token_re.findall(txt)):
            if tok not in stop:
                df[tok] += 1
    seed_terms = [
        "designteori", "designforskning", "designforsking", "formgjeving", "formgivning",
        "formgiving", "brukskunst", "kunsthandverk", "kunsthåndverk", "konsthantverk",
        "tenestedesign", "tjenestedesign", "tjänstedesign", "interaksjonsdesign",
        "interaktionsdesign", "industridesign", "brukarmedverknad", "brukermedvirkning",
        "deltakande", "samskaping", "medskabelse", "berekraft", "bærekraft", "sirkulær",
        "estetikk", "etikk", "epistemologi", "ontologi", "fenomenologi", "metode",
        "metodologi", "praksis", "handverk", "tekstil", "materialitet", "arkitektur",
        "utdanning", "didaktikk", "pedagogikk", "kritisk", "spekulativ", "universell",
        "utforming", "muotoilu", "palvelumuotoilu", "muotoilututkimus", "hönnun",
        "epistemology", "ontology", "phenomenology", "somaesthetics", "affordance",
        "pluriversal", "posthuman", "infrastructuring", "prototyping", "wicked",
    ]
    vocab_words = sorted(set(seed_terms) | {w for w, _ in df.most_common(1350)})
    v_vecs = embed_local_gemma(vocab_words, dims=dims, is_query=True, max_tokens=24, batch_size=64)
    v_bytes = quantize_int8(v_vecs)
    write_json(out_dir / "semantic_vocab.json", {
        "model": f"google/{LOCAL_GEMMA_MODEL}",
        "dimensions": dims,
        "words": vocab_words,
        "vectors_b64": base64.b64encode(v_bytes).decode("ascii"),
    }, compact=True)

    return {
        "works_embedded": len(works),
        "vocab_terms": len(vocab_words),
        "dimensions": dims,
        "vector_bytes": len(bin_bytes),
        "model": f"google/{LOCAL_GEMMA_MODEL}",
    }


def _active_corpus_work_ids() -> set[str] | None:
    """Return all work IDs in the active strict corpus manifests, or None if missing."""
    ids: set[str] = set()
    for fname in ("publications.json", "nordic_additions.json"):
        rows = read_json(DOCS_DATA_DIR / fname, None)
        if isinstance(rows, list):
            ids.update(str(row["id"]) for row in rows if isinstance(row, dict) and row.get("id"))
    return ids or None


def eligible_chunks(db: sqlite3.Connection, model: str, dims: int,
                    *, include_unreviewed: bool = False,
                    active_work_ids: set[str] | list[str] | tuple[str, ...] | None = None,
                    limit: int = 0) -> list[tuple]:
    # Precompute per-document eligibility and title once per sha256 so SQLite drives
    # through idx_chunks_document(sha256, page) instead of scanning work_documents per chunk.
    db.execute("DROP TABLE IF EXISTS temp._eligible_docs")
    db.execute("DROP TABLE IF EXISTS temp._active_work_ids")
    rights_sql = "" if include_unreviewed else (
        " AND w.rights LIKE 'CC %' AND w.rights NOT LIKE '%-ND%' AND w.rights NOT LIKE '% ND%'"
    )
    if active_work_ids is not None:
        db.execute("CREATE TEMP TABLE _active_work_ids (work_id TEXT PRIMARY KEY)")
        db.executemany(
            "INSERT OR IGNORE INTO temp._active_work_ids (work_id) VALUES (?)",
            [(str(wid),) for wid in active_work_ids if wid],
        )
        source_join = (
            "FROM temp._active_work_ids aw "
            "JOIN work_documents wd ON wd.work_id = aw.work_id "
            "LEFT JOIN works w ON w.work_id = wd.work_id"
        )
        require_doc_match = True
    else:
        join_kw = "JOIN" if not include_unreviewed else "LEFT JOIN"
        source_join = f"FROM work_documents wd {join_kw} works w ON w.work_id = wd.work_id"
        require_doc_match = not include_unreviewed

    db.execute("CREATE TEMP TABLE _eligible_docs (sha256 TEXT PRIMARY KEY, title TEXT)")
    db.execute(f"""
        INSERT OR IGNORE INTO temp._eligible_docs (sha256, title)
        SELECT wd.sha256, COALESCE(MIN(NULLIF(w.title, '')), '')
        {source_join}
        WHERE 1=1{rights_sql}
        GROUP BY wd.sha256
    """)
    join_docs = (
        "JOIN temp._eligible_docs ed ON ed.sha256 = c.sha256"
        if require_doc_match else
        "LEFT JOIN temp._eligible_docs ed ON ed.sha256 = c.sha256"
    )

    sql = f"""
        SELECT c.chunk_id, c.text_hash, c.text, COALESCE(ed.title, '')
        FROM chunks c
        JOIN documents d ON d.sha256 = c.sha256
        {join_docs}
        LEFT JOIN embeddings e ON e.chunk_id = c.chunk_id AND e.model = ? AND e.dimensions = ?
        WHERE d.quality = 'extracted'
          AND (e.chunk_id IS NULL OR e.text_hash <> c.text_hash)
        ORDER BY c.chunk_id
    """
    params: list = [model_name(model), dims]
    if limit > 0:
        sql += " LIMIT ?"
        params.append(limit)
    return db.execute(sql, params).fetchall()


def embed_fulltext_chunks(*, model: str = LOCAL_GEMMA_MODEL, dims: int = 256,
                          limit: int = 0, batch: int = 64, pause: float = 0.0,
                          include_unreviewed: bool = True, active_only: bool = True,
                          consent_cloud: bool = False,
                          db_path: Path = PRIVATE_CORPUS_DB) -> dict:
    from .fulltext import connection as corpus_connection

    m = model_name(model)
    if not is_local_gemma(m):
        if not consent_cloud:
            raise ValueError("Pass consent_cloud=True to send full-text chunks to Google Cloud API.")
        if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
            raise RuntimeError("Set GOOGLE_API_KEY in the local environment first.")
    else:
        # Local on-device Google EmbeddingGemma never transmits data externally;
        # all locally cached OA fulltexts can be embedded safely on-device.
        pass

    active_ids = _active_corpus_work_ids() if active_only else None
    db = corpus_connection(db_path)
    rows = eligible_chunks(
        db,
        m,
        dims,
        include_unreviewed=include_unreviewed,
        active_work_ids=active_ids,
        limit=limit,
    )
    complete = 0
    if is_local_gemma(m):
        _, local_sess = ensure_local_gemma()
        step = max(batch * 8, 512) if "DmlExecutionProvider" in local_sess.get_providers() else max(batch, 128)
    else:
        step = batch
    for offset in range(0, len(rows), step):
        batch_rows = rows[offset:offset + step]
        texts = [r[2] for r in batch_rows]
        titles = [r[3] for r in batch_rows]
        if is_local_gemma(m):
            arr = embed_local_gemma(texts, dims=dims, is_query=False, titles=titles,
                                    max_tokens=256, batch_size=batch)
            vectors = arr.tolist()
        else:
            vectors = batch_embeddings(texts, m, dims, titles=titles)
        ts = now_iso()
        with db:
            for (cid, checksum, _, _), raw in zip(batch_rows, vectors):
                packed = pack_vector(raw, dims)
                db.execute("""
                    INSERT INTO embeddings (chunk_id, model, dimensions, task_type, text_hash, vector, embedded_at)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(chunk_id, model, dimensions) DO UPDATE SET
                      text_hash=excluded.text_hash,
                      vector=excluded.vector,
                      embedded_at=excluded.embedded_at
                """, (cid, m, dims, "RETRIEVAL_DOCUMENT", checksum, packed, ts))
                complete += 1
        print(f"CHUNK_EMBEDDED {complete}/{len(rows)} model={m} dims={dims}", flush=True)
        if pause > 0 and offset + step < len(rows):
            time.sleep(pause)

    total = db.execute(
        "SELECT COUNT(*) FROM embeddings WHERE model=? AND dimensions=?",
        (m, dims),
    ).fetchone()[0]
    db.close()
    return {
        "new_embeddings": complete,
        "all_embedding_rows": total,
        "model": m,
        "dimensions": dims,
        "database": str(db_path),
    }


def dense_hits(db: sqlite3.Connection, vector: list[float] | np.ndarray,
               *, model: str = LOCAL_GEMMA_MODEL, dims: int = 256, limit: int = 50) -> list[tuple[str, float]]:
    m = model_name(model)
    packed = pack_vector(vector, dims)
    q = np.frombuffer(packed, dtype="<f4")
    rows = db.execute(
        "SELECT chunk_id, vector FROM embeddings WHERE model=? AND dimensions=?",
        (m, dims),
    ).fetchall()
    if not rows:
        return []
    valid_ids = []
    blobs = []
    for cid, blob in rows:
        if len(blob) == dims * 4:
            valid_ids.append(cid)
            blobs.append(np.frombuffer(blob, dtype="<f4"))
    if not blobs:
        return []
    mat = np.vstack(blobs)
    scores = mat @ q
    top_idx = np.argsort(scores)[::-1][:limit]
    return [(valid_ids[i], float(scores[i])) for i in top_idx]

