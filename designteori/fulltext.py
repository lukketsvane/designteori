"""Page-citable PDF text extraction and FTS5 chunk indexing (`corpus.sqlite`)."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import threading

from . import (
    DOCS_DATA_DIR,
    PDF_DIR,
    PRIVATE_CACHE,
    PRIVATE_CORPUS_DB,
    ROOT,
    now_iso,
    read_json,
)

CHUNK_VERSION = "page-v1-2300-300"
PDF_MAGIC = b"%PDF"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def normalized(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def chunks_for_page(text: str, *, target: int = 2300, overlap: int = 300, minimum: int = 80) -> list[tuple[int, int, str]]:
    if target < 200 or overlap < 0 or overlap >= target // 2:
        raise ValueError("Invalid chunk size or overlap")
    text = normalized(text)
    if len(text) < minimum:
        return []
    spans = []
    start = 0
    while start < len(text):
        end = min(len(text), start + target)
        if end < len(text):
            lower = start + int(target * 0.7)
            cut = max(text.rfind("\n", lower, end), text.rfind(" ", lower, end))
            if cut > start + 100:
                end = cut
        part = text[start:end].strip()
        if len(part) >= minimum:
            spans.append((start, end, part))
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return spans


_FITZ_LOCK = threading.Lock()


def extract_pages(path: Path) -> tuple[list[str], str]:
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        # MuPDF C-biblioteket er ikkje trådsikkert ved samstundes ThreadPoolExecutor-opning,
        # og sort=True kan henge i O(N^2) geometri-sortering på komplekse vektor-PDF-ar.
        with _FITZ_LOCK:
            if hasattr(fitz, "TOOLS") and hasattr(fitz.TOOLS, "mupdf_display_errors"):
                fitz.TOOLS.mupdf_display_errors(False)
            with fitz.open(path) as pdf:
                if pdf.needs_pass:
                    raise ValueError("Encrypted PDF: password needed")
                return [normalized(page.get_text("text")) for page in pdf], "pymupdf"
    except ImportError:
        pass
    from pypdf import PdfReader

    pdf = PdfReader(str(path), strict=False)
    if pdf.is_encrypted:
        raise ValueError("Encrypted PDF: password needed")
    return [normalized(page.extract_text() or "") for page in pdf.pages], "pypdf"


def connection(path: Path = PRIVATE_CORPUS_DB) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS documents (
      sha256 TEXT PRIMARY KEY,
      file_path TEXT NOT NULL,
      bytes INTEGER NOT NULL,
      pages INTEGER NOT NULL,
      extracted_pages INTEGER NOT NULL,
      char_count INTEGER NOT NULL,
      extractor TEXT NOT NULL,
      chunk_version TEXT NOT NULL,
      quality TEXT NOT NULL,
      processed_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS works (
      work_id TEXT PRIMARY KEY, title TEXT, doi TEXT, year INTEGER,
      authors TEXT, source TEXT, rights TEXT
    );
    CREATE TABLE IF NOT EXISTS work_documents (
      work_id TEXT NOT NULL REFERENCES works(work_id),
      sha256 TEXT NOT NULL REFERENCES documents(sha256),
      original_url TEXT,
      PRIMARY KEY(work_id,sha256)
    );
    CREATE TABLE IF NOT EXISTS pages (
      sha256 TEXT NOT NULL REFERENCES documents(sha256) ON DELETE CASCADE,
      page INTEGER NOT NULL, text TEXT NOT NULL,
      PRIMARY KEY(sha256,page)
    );
    CREATE TABLE IF NOT EXISTS chunks (
      chunk_id TEXT PRIMARY KEY,
      sha256 TEXT NOT NULL REFERENCES documents(sha256) ON DELETE CASCADE,
      page INTEGER NOT NULL, ordinal INTEGER NOT NULL,
      chunk_version TEXT NOT NULL,
      text_hash TEXT NOT NULL, text TEXT NOT NULL,
      UNIQUE(sha256,page,ordinal,chunk_version)
    );
    CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(sha256,page);
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
      text, content='chunks', content_rowid='rowid',
      tokenize='unicode61 remove_diacritics 2'
    );
    CREATE TRIGGER IF NOT EXISTS chunk_insert AFTER INSERT ON chunks BEGIN
      INSERT INTO chunks_fts(rowid,text) VALUES (new.rowid,new.text);
    END;
    CREATE TRIGGER IF NOT EXISTS chunk_delete AFTER DELETE ON chunks BEGIN
      INSERT INTO chunks_fts(chunks_fts,rowid,text)
      VALUES('delete',old.rowid,old.text);
    END;
    CREATE TABLE IF NOT EXISTS embeddings (
      chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
      model TEXT NOT NULL, dimensions INTEGER NOT NULL,
      task_type TEXT NOT NULL, text_hash TEXT NOT NULL,
      vector BLOB NOT NULL, embedded_at TEXT NOT NULL,
      PRIMARY KEY(chunk_id,model,dimensions)
    );
    """)
    db.commit()
    return db


def _extract_worker(args: tuple[str, Path, str, int]):
    wid, path, expected_hash, max_pages = args
    if not path.is_file() or path.stat().st_size < 500:
        raise ValueError("PDF file missing/too small")
    with path.open("rb") as fp:
        if fp.read(4) != PDF_MAGIC:
            raise ValueError("Not a PDF")
    digest = sha256_file(path)
    if expected_hash and digest.lower() != expected_hash.lower():
        raise ValueError("SHA-256 differs from download manifest")
    pages, extractor = extract_pages(path)
    if not pages or len(pages) > max_pages:
        raise ValueError("PDF has zero or too many pages")
    return wid, path, digest, pages, extractor


def index_all_pdfs(*, db_path: Path = PRIVATE_CORPUS_DB, cache_dir: Path = PRIVATE_CACHE,
                   force: bool = False, limit: int = 0, workers: int = 6) -> dict:
    works_meta = {}
    for name in ("publications.json", "nordic_additions.json"):
        for row in read_json(DOCS_DATA_DIR / name, []) or []:
            works_meta[row["id"]] = row

    sources: dict[str, tuple[Path, str, str]] = {}
    licenses: dict[str, str] = {}
    progress = read_json(cache_dir / "progress.json", {}) or {}
    repo_manifest = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
    for wid, info in repo_manifest.items():
        if isinstance(info, dict):
            if info.get("license"):
                licenses[wid] = info["license"]
            cache_pdf = cache_dir / "pdf" / (hashlib.sha256(wid.encode("utf-8")).hexdigest()[:24] + ".pdf")
            repo_pdf = ROOT / info["file"] if info.get("file") else None
            chosen = cache_pdf if cache_pdf.is_file() else (repo_pdf if repo_pdf and repo_pdf.is_file() else None)
            if chosen is not None:
                expected = info.get("sha256", "")
                if chosen == repo_pdf and info.get("file_sha256"):
                    expected = info["file_sha256"]  # repo copy is compressed; original lives in cache
                sources[wid] = (chosen, expected, info.get("source_url", ""))
    for wid, rec in progress.items():
        if wid not in sources and isinstance(rec, dict) and rec.get("status") == "pdf-confirmed":
            pdf_file = cache_dir / "pdf" / (hashlib.sha256(wid.encode("utf-8")).hexdigest()[:24] + ".pdf")
            if pdf_file.is_file():
                sources[wid] = (pdf_file, rec.get("sha256", ""), rec.get("url", ""))

    conn = connection(db_path)
    existing_docs = dict(conn.execute("SELECT sha256, chunk_version FROM documents").fetchall())

    items = sorted(sources.items())
    if limit > 0:
        items = items[:limit]

    to_extract = []
    unchanged = 0
    done = 0
    failed = 0

    for wid, (pdf_file, checksum, url) in items:
        if not force and checksum and existing_docs.get(checksum) == CHUNK_VERSION:
            info = works_meta.get(wid, {})
            authors = info.get("authors") or []
            conn.execute("""
                INSERT INTO works (work_id,title,doi,year,authors,source,rights)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(work_id) DO UPDATE SET
                  title=excluded.title,doi=excluded.doi,year=excluded.year,
                  authors=excluded.authors,source=excluded.source,rights=excluded.rights
            """, (
                wid, info.get("title", ""), info.get("doi", ""), info.get("year"),
                "; ".join(authors) if isinstance(authors, list) else str(authors),
                info.get("source", ""), licenses.get(wid, "") or "open-access",
            ))
            conn.execute("INSERT OR IGNORE INTO work_documents VALUES(?,?,?)", (wid, checksum, url))
            unchanged += 1
        else:
            to_extract.append((wid, pdf_file, checksum, url))
    conn.commit()

    for batch_start in range(0, len(to_extract), 32):
        batch = to_extract[batch_start:batch_start + 32]
        tasks = [(wid, p, c, 3000) for wid, p, c, _ in batch]
        url_map = {wid: u for wid, _, _, u in batch}
        extracted_batch = []
        if workers <= 1:
            for t in tasks:
                try:
                    extracted_batch.append(_extract_worker(t))
                except Exception as exc:
                    failed += 1
                    print("PDF_EXTRACT_ERR", t[0], type(exc).__name__, str(exc)[:120], flush=True)
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [(t[0], pool.submit(_extract_worker, t)) for t in tasks]
                for wid, fut in futures:
                    try:
                        extracted_batch.append(fut.result())
                    except Exception as exc:
                        failed += 1
                        print("PDF_EXTRACT_ERR", wid, type(exc).__name__, str(exc)[:120], flush=True)

        ts = now_iso()
        with conn:
            for wid, path, digest, pages, extractor in extracted_batch:
                prev_ver = existing_docs.get(digest)
                if force or prev_ver != CHUNK_VERSION:
                    if prev_ver is not None:
                        conn.execute("DELETE FROM embeddings WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE sha256=?)", (digest,))
                        conn.execute("DELETE FROM chunks WHERE sha256=?", (digest,))
                        conn.execute("DELETE FROM pages WHERE sha256=?", (digest,))
                    n_text = sum(len(pg) >= 80 for pg in pages)
                    chars = sum(len(pg) for pg in pages)
                    quality = "needs_ocr" if n_text < max(1, len(pages) // 2) else "extracted"
                    conn.execute("""
                        INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(sha256) DO UPDATE SET
                          file_path=excluded.file_path, bytes=excluded.bytes, pages=excluded.pages,
                          extracted_pages=excluded.extracted_pages, char_count=excluded.char_count,
                          extractor=excluded.extractor, chunk_version=excluded.chunk_version,
                          quality=excluded.quality, processed_at=excluded.processed_at
                    """, (digest, path.name, path.stat().st_size, len(pages), n_text, chars, extractor, CHUNK_VERSION, quality, ts))
                    page_rows = [(digest, pno, pg) for pno, pg in enumerate(pages, 1)]
                    conn.executemany("INSERT INTO pages VALUES(?,?,?)", page_rows)
                    chunk_rows = []
                    for pno, pg in enumerate(pages, 1):
                        for ord_i, (_, _, ctext) in enumerate(chunks_for_page(pg)):
                            cid = f"{digest[:16]}:p{pno}:c{ord_i}"
                            th = hashlib.sha256(ctext.encode("utf-8")).hexdigest()
                            chunk_rows.append((cid, digest, pno, ord_i, CHUNK_VERSION, th, ctext))
                    if chunk_rows:
                        conn.executemany("INSERT INTO chunks VALUES(?,?,?,?,?,?,?)", chunk_rows)
                    existing_docs[digest] = CHUNK_VERSION
                info = works_meta.get(wid, {})
                authors = info.get("authors") or []
                conn.execute("""
                    INSERT INTO works (work_id,title,doi,year,authors,source,rights)
                    VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(work_id) DO UPDATE SET
                      title=excluded.title,doi=excluded.doi,year=excluded.year,
                      authors=excluded.authors,source=excluded.source,rights=excluded.rights
                """, (
                    wid, info.get("title", ""), info.get("doi", ""), info.get("year"),
                    "; ".join(authors) if isinstance(authors, list) else str(authors),
                    info.get("source", ""), licenses.get(wid, "") or "open-access",
                ))
                conn.execute("INSERT OR IGNORE INTO work_documents VALUES(?,?,?)", (wid, digest, url_map.get(wid, "")))
                done += 1
        print(f"PDF_INDEX_BATCH {done + failed}/{len(to_extract)} done={done} failed={failed}", flush=True)

    total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    return {
        "indexed_new": done,
        "unchanged": unchanged,
        "failed": failed,
        "total_documents": total_docs,
        "total_chunks": total_chunks,
    }
