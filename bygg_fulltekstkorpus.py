#!/usr/bin/env python3
"""Incremental, private, page-citable full-text corpus for DESIGNTEORI.

Reads local PDFs only. No external requests, embeddings or public text exports.
PDFs and database stay under DESIGNTEORI_PDF_CACHE, outside the Git repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = Path(os.environ.get(
    "DESIGNTEORI_PDF_CACHE", str(ROOT / "data" / "oa_fulltexts_private")
)).expanduser().resolve()
DB = CACHE / "corpus.sqlite"
CHUNK_VERSION = "page-v1-2300-300"
PDF_MAGIC = b"%PDF"


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def normalized(text: str):
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def chunks_for_page(text: str, *, target=2300, overlap=300, minimum=80):
    """Stable, page-contained character chunks with slight context overlap."""
    if target < 200 or overlap < 0 or overlap >= target // 2:
        raise ValueError("Invalid chunk size/overlap")
    text = normalized(text)
    if len(text) < minimum:
        return []
    spans = []
    start = 0
    while start < len(text):
        end = min(len(text), start + target)
        if end < len(text):
            lower = start + int(target * .7)
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


def extract_pages(path: Path):
    """Prefer PyMuPDF where installed; fall back to pypdf."""
    try:
        import fitz
        with fitz.open(path) as pdf:
            if pdf.needs_pass:
                raise ValueError("Encrypted PDF: password needed")
            return [normalized(page.get_text(sort=True)) for page in pdf], "pymupdf"
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf: python -m pip install pypdf") from exc
    pdf = PdfReader(str(path), strict=False)
    if pdf.is_encrypted:
        raise ValueError("Encrypted PDF: password needed")
    return [normalized(page.extract_text() or "") for page in pdf.pages], "pypdf"


def connection(path=DB):
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


def metadata():
    works = {}
    for name in ("publications.json", "nordic_additions.json"):
        path = ROOT / "docs" / "data" / name
        if path.is_file():
            for row in json.loads(path.read_text(encoding="utf-8")):
                works[row["id"]] = row
    path = CACHE / "doi_csv_metadata.json"
    if path.is_file():
        extra = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(extra, dict):
            works.update({k:v for k,v in extra.items() if isinstance(v,dict)})
    manifest = ROOT / "fulltekst" / "manifest.json"
    licenses = {}
    if manifest.is_file():
        licenses = {r["id"]: r.get("license", "") for r in
                    json.loads(manifest.read_text(encoding="utf-8")).get("items", [])}
    return works, licenses


def candidates(work, manifest):
    progress = CACHE / "progress.json"
    sources = {}
    if progress.is_file():
        for wid, record in json.loads(progress.read_text(encoding="utf-8")).items():
            if record.get("status") != "pdf-confirmed":
                continue
            cache_name = hashlib.sha256(wid.encode("utf-8")).hexdigest()[:24] + ".pdf"
            path = CACHE / "pdf" / cache_name
            if path.is_file():
                sources[wid] = (path, record.get("sha256", ""),
                                record.get("url", ""))
    for row in manifest:
        wid = row["id"]
        if wid not in sources:
            path = ROOT / "fulltekst" / row["pdf"]
            if path.is_file():
                sources[wid] = (path, row.get("sha256", ""),
                                row.get("original_fulltext_url", ""))
    return sources


def index_document(db, wid, path, expected_hash, origin, info, license_name,
                   *, force=False, max_pages=1000):
    if not path.is_file() or path.stat().st_size < 500:
        raise ValueError("PDF file missing/too small")
    with path.open("rb") as fp:
        if fp.read(4) != PDF_MAGIC:
            raise ValueError("Not a PDF")
    digest = sha256(path)
    if expected_hash and digest.lower() != expected_hash.lower():
        raise ValueError("SHA-256 differs from download manifest")
    previous = db.execute(
        "SELECT chunk_version FROM documents WHERE sha256=?", (digest,)
    ).fetchone()
    needs_extract = force or previous is None or previous[0] != CHUNK_VERSION
    if needs_extract:
        pages, extractor = extract_pages(path)
        if not pages or len(pages) > max_pages:
            raise ValueError("PDF has zero or too many pages")
        n_text = sum(bool(len(page) >= 80) for page in pages)
        count = sum(len(page) for page in pages)
        quality = ("needs_ocr" if n_text < max(1, len(pages) // 2)
                   else "extracted")
        with db:
            if previous is not None:
                db.execute("DELETE FROM embeddings WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE sha256=?)", (digest,))
                db.execute("DELETE FROM chunks WHERE sha256=?", (digest,))
                db.execute("DELETE FROM pages WHERE sha256=?", (digest,))
            db.execute("""INSERT OR REPLACE INTO documents
                (sha256,file_path,bytes,pages,extracted_pages,char_count,
                 extractor,chunk_version,quality,processed_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (digest,str(path),path.stat().st_size,len(pages),n_text,
                 count,extractor,CHUNK_VERSION,quality,timestamp()))
            for p, text in enumerate(pages,1):
                db.execute("INSERT INTO pages VALUES(?,?,?)", (digest,p,text))
                for ordinal,(_,_,part) in enumerate(chunks_for_page(text)):
                    chunk_id = hashlib.sha256(
                        f"{digest}|{CHUNK_VERSION}|{p}|{ordinal}".encode()
                    ).hexdigest()
                    db.execute("""INSERT INTO chunks
                        (chunk_id,sha256,page,ordinal,chunk_version,text_hash,text)
                        VALUES(?,?,?,?,?,?,?)""",
                        (chunk_id,digest,p,ordinal,CHUNK_VERSION,
                         hashlib.sha256(part.encode()).hexdigest(),part))
    authors = info.get("authors") or []
    with db:
        db.execute("""INSERT INTO works
            (work_id,title,doi,year,authors,source,rights)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(work_id) DO UPDATE SET
              title=excluded.title,doi=excluded.doi,year=excluded.year,
              authors=excluded.authors,source=excluded.source,rights=excluded.rights""",
            (wid,info.get("title",""),info.get("doi",""),info.get("year"),
             "; ".join(authors) if isinstance(authors,list) else str(authors),
             info.get("source",""),license_name or "unreviewed"))
        db.execute("INSERT OR IGNORE INTO work_documents VALUES(?,?,?)",
                   (wid,digest,origin))
    return digest, needs_extract


def build(*, db_path=DB, force=False, limit=0):
    data, licenses = metadata()
    manifest_path = ROOT / "fulltekst" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")).get("items", [])
    sources = candidates(data, manifest)
    conn = connection(db_path)
    done=unchanged=failed=0
    for wid,(file,checksum,url) in sorted(sources.items()):
        if limit and done+unchanged+failed >= limit:
            break
        info = data.get(wid, {})
        if not info:
            source = next((item for item in manifest if item["id"] == wid), {})
            info={"title":source.get("title",""),"doi":source.get("doi",""),
                  "year":source.get("year"),"authors":source.get("authors",[])}
        try:
            digest, extracted = index_document(
                conn,wid,file,checksum,url,info,licenses.get(wid,""),
                force=force
            )
            done += int(extracted)
            unchanged += int(not extracted)
        except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
            failed += 1
            print("PDF_ERROR",wid,type(exc).__name__,str(exc)[:150],flush=True)
    summary = dict(conn.execute(
        "SELECT quality,COUNT(*) FROM documents GROUP BY quality"
    ).fetchall())
    totals = {
        "new_or_reprocessed":done,"already_indexed":unchanged,"failed":failed,
        "distinct_pdfs":conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
        "linked_works":conn.execute("SELECT COUNT(*) FROM work_documents").fetchone()[0],
        "pages":conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0],
        "chunks":conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
        "quality":summary,"db_path":str(db_path)
    }
    print(json.dumps(totals,ensure_ascii=False,indent=2))
    conn.close()
    return totals


def search(term, *, db_path=DB, limit=10):
    db = connection(db_path)
    safe = re.findall(r"[\w]{2,}",term,flags=re.UNICODE)
    if not safe:
        raise ValueError("Enter a search term")
    query = " AND ".join('"' + x.replace('"','') + '"' for x in safe)
    rows = db.execute("""SELECT c.chunk_id,c.sha256,c.page,
         snippet(chunks_fts,0,'[',']',' … ',24) AS excerpt,
         bm25(chunks_fts) AS score
       FROM chunks_fts JOIN chunks c ON c.rowid=chunks_fts.rowid
       WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?""",(query,limit)).fetchall()
    for cid,sha,page,excerpt,score in rows:
        refs=db.execute("""SELECT w.work_id,w.title,w.doi
          FROM work_documents wd JOIN works w ON wd.work_id=w.work_id
          WHERE wd.sha256=? ORDER BY w.work_id""",(sha,)).fetchall()
        print(json.dumps(dict(chunk_id=cid,page=page,score=round(score,5),
              works=[{"id":w,"title":t,"doi":doi} for w,t,doi in refs],
              excerpt=excerpt),ensure_ascii=False))
    db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group()
    group.add_argument("--build",action="store_true")
    group.add_argument("--search")
    p.add_argument("--force",action="store_true")
    p.add_argument("--limit",type=int,default=0)
    args=p.parse_args()
    if args.search:
        search(args.search,limit=args.limit or 10)
    else:
        build(force=args.force,limit=args.limit)


if __name__=="__main__":
    main()
