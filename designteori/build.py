"""Unified deterministic build pipeline, SQLite database builder, and corpus verifier."""
from __future__ import annotations

import gzip
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

from . import (
    DOCS_DATA_DIR,
    PDF_DIR,
    RAW_SQLITE,
    REPO_RAW_BASE,
    ROOT,
    UNIFIED_SQLITE_GZ,
    now_iso,
    read_json,
    write_csv_rows,
    write_gzip_deterministic,
    write_json,
)
from .analysis import build_analysis
from .collect import ensure_raw_sqlite
from .embeddings import LOCAL_GEMMA_MODEL, embed_corpus_works, export_public_semantic_index
from .pdf import HOST_DENY, allowed_url, publish_pdf_catalog, safe_public_link
from .reconcile import export_unified_csv_and_coverage, run_reconciliation


def _stamp_repo_pdf_links(works: list[dict], nordic: list[dict]) -> None:
    repo_pdfs = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
    changed = False
    for w in works:
        wid = w["id"]
        new_pdf = f"{REPO_RAW_BASE}/{repo_pdfs[wid]['file']}" if wid in repo_pdfs else ""
        if w.get("pdf") != new_pdf:
            w["pdf"] = new_pdf
            changed = True
    for w in nordic:
        wid = w["id"]
        new_pdf = f"{REPO_RAW_BASE}/{repo_pdfs[wid]['file']}" if wid in repo_pdfs else ""
        if w.get("pdf") != new_pdf:
            w["pdf"] = new_pdf
            changed = True

    if changed:
        write_json(DOCS_DATA_DIR / "publications.json", works, compact=True)
        pub_fields = [
            "id", "doi", "title", "year", "authors", "source", "countries", "kind",
            "citations", "topic", "theme", "oa_url", "scope", "license", "pdf",
            "review_priority", "review_score", "keyword_categories",
        ]
        write_csv_rows(DOCS_DATA_DIR / "publications.csv", pub_fields, [
            {k: (", ".join(v) if isinstance(v, list) else v) for k, v in row.items() if k in pub_fields}
            for row in works
        ])
        write_json(DOCS_DATA_DIR / "nordic_additions.json", nordic, compact=True)
        stats = read_json(DOCS_DATA_DIR / "stats.json", {}) or {}
        if stats:
            stats["local_pdf"] = sum(bool(x.get("pdf")) for x in works)
            write_json(DOCS_DATA_DIR / "stats.json", stats)
        export_unified_csv_and_coverage(works, nordic)


def build_unified_sqlite(
    *,
    raw_sqlite: Path = RAW_SQLITE,
    target_gz: Path = UNIFIED_SQLITE_GZ,
) -> dict:
    """Build the single public SQLite archive `data/designteori.sqlite.gz`."""
    ensure_raw_sqlite(raw_sqlite)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "designteori.sqlite"
        src_conn = sqlite3.connect(raw_sqlite)
        src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        src_conn.close()
        shutil.copy2(raw_sqlite, tmp_db)

        db = sqlite3.connect(tmp_db)
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("UPDATE works SET abstract='', raw_json='{}'")

        db.executescript("""
            DROP TABLE IF EXISTS works_fts;
            CREATE VIRTUAL TABLE works_fts USING fts5(
                id UNINDEXED, title, source, topic,
                tokenize='unicode61 remove_diacritics 2'
            );

            DROP TABLE IF EXISTS source_candidates;
            CREATE TABLE source_candidates (
                id TEXT PRIMARY KEY,
                origin TEXT NOT NULL,
                scope TEXT NOT NULL,
                title TEXT NOT NULL,
                year INTEGER,
                doi TEXT,
                authors TEXT,
                source TEXT,
                source_country TEXT,
                kind TEXT,
                source_url TEXT,
                pdf_url TEXT,
                review_status TEXT NOT NULL,
                duplicate_status TEXT
            );

            DROP TABLE IF EXISTS source_candidates_fts;
            CREATE VIRTUAL TABLE source_candidates_fts USING fts5(
                id UNINDEXED, title, authors, source,
                tokenize='unicode61 remove_diacritics 2'
            );

            DROP TABLE IF EXISTS repo_pdfs;
            CREATE TABLE repo_pdfs (
                work_id TEXT PRIMARY KEY,
                repo_file TEXT,
                public_url TEXT NOT NULL,
                source_url TEXT,
                status TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                bytes INTEGER,
                license TEXT
            );

            DROP TABLE IF EXISTS work_embeddings;
            CREATE TABLE work_embeddings (
                work_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                vector_int8 BLOB NOT NULL
            );

            DROP TABLE IF EXISTS theory_claims;
            CREATE TABLE theory_claims (
                claim_id TEXT PRIMARY KEY,
                work_id TEXT NOT NULL,
                claim_text TEXT NOT NULL,
                coder TEXT NOT NULL,
                coded_at TEXT NOT NULL
            );

            DROP TABLE IF EXISTS claim_evidence;
            CREATE TABLE claim_evidence (
                evidence_id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL REFERENCES theory_claims(claim_id),
                page_reference TEXT NOT NULL,
                quote TEXT NOT NULL
            );

            DROP TABLE IF EXISTS screening_decisions;
            CREATE TABLE screening_decisions (
                work_id TEXT PRIMARY KEY,
                eligible INTEGER NOT NULL,
                rationale TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                decided_at TEXT NOT NULL
            );

            DROP TABLE IF EXISTS database_info;
            CREATE TABLE database_info (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        db.execute("""
            INSERT INTO works_fts(id, title, source, topic)
            SELECT id, COALESCE(title,''), COALESCE(source,''), COALESCE(topic,'') FROM works
        """)

        nordic = read_json(DOCS_DATA_DIR / "nordic_additions.json", []) or []
        db.executemany(
            "INSERT INTO source_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(
                w["id"], w.get("origin", "external"), w.get("scope", "repository-candidate"),
                w.get("title", ""), w.get("year"), w.get("doi", ""),
                "; ".join(w.get("authors") or []), w.get("source", ""),
                w.get("source_country", ""), w.get("kind", ""),
                w.get("source_url", ""), w.get("pdf", ""),
                w.get("review_status", "metadata-unreviewed"), w.get("duplicate_status", ""),
            ) for w in nordic],
        )
        db.execute("""
            INSERT INTO source_candidates_fts(id, title, authors, source)
            SELECT id, title, authors, source FROM source_candidates
        """)

        repo_manifest = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
        pdf_found = read_json(DOCS_DATA_DIR / "pdf_found.json", {}) or {}
        all_pdf_ids = sorted(set(repo_manifest) | set(pdf_found))
        pdf_db_rows = []
        for wid in all_pdf_ids:
            rm = repo_manifest.get(wid) or {}
            pf = pdf_found.get(wid) or {}
            sha = rm.get("sha256") or pf.get("sha256") or ""
            if not sha:
                continue
            rfile = rm.get("file", "")
            pub_url = (f"{REPO_RAW_BASE}/{rfile}" if rfile else "") or pf.get("repo_pdf") or pf.get("url") or ""
            if not pub_url:
                continue
            pdf_db_rows.append((
                wid,
                rfile,
                pub_url,
                rm.get("source_url") or pf.get("url") or "",
                "in-repo-pdf" if rfile else pf.get("status", "verified-link"),
                sha,
                int(rm.get("bytes") or 0),
                rm.get("license") or pf.get("license") or "",
            ))
        db.executemany("INSERT INTO repo_pdfs VALUES (?,?,?,?,?,?,?,?)", pdf_db_rows)

        sem_meta = read_json(DOCS_DATA_DIR / "semantic_index.json", {}) or {}
        vec_bin = DOCS_DATA_DIR / "semantic_vectors.bin"
        embedded_rows = 0
        if sem_meta and vec_bin.is_file():
            dims = int(sem_meta.get("dimensions") or 128)
            ids = sem_meta.get("ids") or []
            model_str = str(sem_meta.get("model") or f"google/{LOCAL_GEMMA_MODEL}")
            raw_bytes = vec_bin.read_bytes()
            if len(raw_bytes) == len(ids) * dims:
                emb_tuples = [
                    (wid, model_str, dims, raw_bytes[i * dims:(i + 1) * dims])
                    for i, wid in enumerate(ids)
                ]
                db.executemany("INSERT INTO work_embeddings VALUES (?,?,?,?)", emb_tuples)
                embedded_rows = len(emb_tuples)

        works_total = db.execute("SELECT COUNT(*) FROM works").fetchone()[0]
        info_kv = [
            ("schema_version", "3.1"),
            ("built_at", now_iso()),
            ("openalex_works", str(works_total)),
            ("nordic_candidates", str(len(nordic))),
            ("repo_pdfs", str(len(pdf_db_rows))),
            ("work_embeddings", str(embedded_rows)),
            ("embedding_model", str(sem_meta.get("model", f"google/{LOCAL_GEMMA_MODEL}"))),
        ]
        db.executemany("INSERT INTO database_info VALUES (?,?)", info_kv)
        db.commit()
        db.execute("VACUUM")
        ok = db.execute("PRAGMA integrity_check").fetchone()[0]
        db.close()
        if ok != "ok":
            raise RuntimeError(f"Unified SQLite failed integrity_check: {ok}")
        write_gzip_deterministic(tmp_db, target_gz)

    return {
        "sqlite_gz": str(target_gz.relative_to(ROOT)),
        "size_mb": round(target_gz.stat().st_size / 1e6, 2),
        "openalex_works": works_total,
        "nordic_candidates": len(nordic),
        "repo_pdfs": len(pdf_db_rows),
        "work_embeddings": embedded_rows,
    }


def build_all(*, embed: bool = True, sync_repo_pdfs: bool = True) -> dict:
    """Run the complete deterministic DESIGNTEORI corpus build pipeline."""
    works, nordic = run_reconciliation()
    pdf_stats = publish_pdf_catalog(sync_repo_pdfs=sync_repo_pdfs)
    _stamp_repo_pdf_links(works, nordic)

    all_works = works + nordic
    embed_stats = {}
    if embed:
        vectors, _ = embed_corpus_works(all_works, dims_public=128, dims_local=256)
        embed_stats = export_public_semantic_index(all_works, vectors, dims=128)

    analysis_data = build_analysis()
    db_stats = build_unified_sqlite()
    verify_stats = verify_all()
    return {
        "works": len(works),
        "nordic_candidates": len(nordic),
        "pdf_catalog": pdf_stats,
        "embeddings": embed_stats,
        "sqlite": db_stats,
        "overview": analysis_data.get("overview", {}),
        "verified": verify_stats["ok"],
    }


def verify_all(*, check_sqlite: bool = True) -> dict:
    """Strict verification of provenance, checksums, URL hygiene, SQLite, and embeddings."""
    errors: list[str] = []

    works = read_json(DOCS_DATA_DIR / "publications.json")
    nordic = read_json(DOCS_DATA_DIR / "nordic_additions.json")
    quality = read_json(DOCS_DATA_DIR / "corpus_quality.json")
    pdf_found = read_json(DOCS_DATA_DIR / "pdf_found.json")
    pdf_kat = read_json(DOCS_DATA_DIR / "pdf_katalog.json")
    sem_meta = read_json(DOCS_DATA_DIR / "semantic_index.json")
    analysis = read_json(DOCS_DATA_DIR / "analysis.json")

    if not isinstance(works, list) or len(works) < 10_000:
        errors.append(f"publications.json missing or unexpectedly small ({len(works) if isinstance(works, list) else 'nil'})")
    if not isinstance(nordic, list) or len(nordic) == 0:
        errors.append("nordic_additions.json missing or empty")
    if not isinstance(quality, dict) or quality.get("manual_article_eligibility_checks_completed") != 0:
        errors.append("corpus_quality.json provenance gate violated")
    if not isinstance(analysis, dict) or "overview" not in analysis:
        errors.append("analysis.json missing overview")

    if isinstance(works, list) and isinstance(nordic, list):
        w_ids = {w["id"] for w in works}
        n_ids = {w["id"] for w in nordic}
        if w_ids & n_ids:
            errors.append("ID collision across OpenAlex and Nordic candidate layers")
        if any(not wid.startswith("nordic:") for wid in n_ids):
            errors.append("nordic_additions IDs must start with 'nordic:'")

    if isinstance(pdf_found, dict):
        for wid, item in pdf_found.items():
            u = str(item.get("url") or "")
            if u and not safe_public_link(u):
                errors.append(f"Unsafe public URL in pdf_found.json for {wid}: {u}")
            if any(b in u.lower() for b in HOST_DENY):
                errors.append(f"Denied host in pdf_found.json for {wid}: {u}")
            if not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256") or "")):
                errors.append(f"Invalid sha256 in pdf_found.json for {wid}")

    if isinstance(pdf_kat, dict):
        for item in pdf_kat.get("items") or []:
            for field in ("public_pdf_url", "oa_location_unverified"):
                val = item.get(field) or ""
                if val and not allowed_url(val):
                    errors.append(f"Disallowed URL in pdf_katalog.json ({field}): {val}")

    repo_manifest_file = PDF_DIR / "manifest.json"
    repo_pdf_count = 0
    if repo_manifest_file.is_file():
        rm_data = read_json(repo_manifest_file, {}) or {}
        rm_items = rm_data.get("items") or {}
        repo_pdf_count = len(rm_items)
        local_pdfs = list(PDF_DIR.glob("*.pdf"))
        for wid, info in rm_items.items():
            if not re.fullmatch(r"[a-f0-9]{64}", str(info.get("sha256") or "")):
                errors.append(f"Invalid sha256 in pdf/manifest.json for {wid}")
            if int(info.get("bytes") or 0) > 98_000_000:
                errors.append(f"PDF exceeds GitHub 98 MB cap in pdf/manifest.json: {wid}")
            if local_pdfs:
                fpath = ROOT / str(info.get("file") or "")
                if not fpath.is_file() or fpath.stat().st_size != int(info.get("bytes") or -1):
                    errors.append(f"Missing or size-mismatched file in pdf/: {wid} -> {fpath}")

    vec_bin = DOCS_DATA_DIR / "semantic_vectors.bin"
    if isinstance(sem_meta, dict) and vec_bin.is_file():
        dims = int(sem_meta.get("dimensions") or 0)
        ids = sem_meta.get("ids") or []
        expected_total = len(works or []) + len(nordic or [])
        if len(ids) != expected_total:
            errors.append(f"semantic_index.json count ({len(ids)}) != total searchable works ({expected_total})")
        if vec_bin.stat().st_size != len(ids) * dims:
            errors.append(f"semantic_vectors.bin byte size ({vec_bin.stat().st_size}) != {len(ids)} * {dims}")
    else:
        errors.append("Missing Google semantic_index.json or semantic_vectors.bin")

    if check_sqlite:
        if not UNIFIED_SQLITE_GZ.is_file():
            errors.append("Missing data/designteori.sqlite.gz")
        elif UNIFIED_SQLITE_GZ.stat().st_size > 95_000_000:
            errors.append("data/designteori.sqlite.gz exceeds 95 MB GitHub limit")
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_db = Path(tmpdir) / "check.sqlite"
                with gzip.open(UNIFIED_SQLITE_GZ, "rb") as src, tmp_db.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                conn = sqlite3.connect(tmp_db)
                try:
                    ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
                    if ok != "ok":
                        errors.append(f"SQLite integrity_check failed: {ok}")
                    leaked_abs = conn.execute("SELECT COUNT(*) FROM works WHERE COALESCE(abstract,'') <> ''").fetchone()[0]
                    if leaked_abs != 0:
                        errors.append(f"Public SQLite leaked {leaked_abs} non-empty abstracts")
                    leaked_raw = conn.execute("SELECT COUNT(*) FROM works WHERE COALESCE(raw_json,'{}') <> '{}'").fetchone()[0]
                    if leaked_raw != 0:
                        errors.append(f"Public SQLite leaked {leaked_raw} raw_json blobs")
                    claims_n = conn.execute("SELECT COUNT(*) FROM theory_claims").fetchone()[0]
                    if claims_n != 0:
                        errors.append("theory_claims must remain unpopulated until manual coding")
                    w_cnt = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
                    if isinstance(works, list) and w_cnt != len(works):
                        errors.append(f"SQLite works ({w_cnt}) != publications.json ({len(works)})")
                finally:
                    conn.close()

    if errors:
        raise AssertionError("DESIGNTEORI verification failed:\n - " + "\n - ".join(errors))

    return {
        "ok": True,
        "openalex_works": len(works or []),
        "nordic_candidates": len(nordic or []),
        "repo_pdfs": repo_pdf_count,
        "embedded_works": len((sem_meta or {}).get("ids") or []),
    }
