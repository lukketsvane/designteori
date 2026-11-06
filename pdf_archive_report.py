#!/usr/bin/env python3
"""Verify the locally collected PDF corpus and export a private, searchable file index.

This reports actual bytes on disk. The public bibliography and OA URL counts are
not treated as downloaded files. The report and private PDF paths are never
published by CI or committed to Git.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

import hent_oa_pdf as harvest


def merge_local_cache(source: Path):
    """Consolidate an already-local PDF cache, without making network requests.

    The source may be written by a separate downloader; only fully saved and
    hash-confirmed files are imported. Never copy its failed/pending statuses.
    """
    source = Path(source).expanduser().resolve()
    dest = harvest.PRIVATE
    if source == dest:
        raise ValueError("Source and destination caches are the same")
    log = source / "progress.json"
    if not log.is_file():
        raise ValueError("Missing source progress.json: " + str(log))
    raw = harvest.read_json(log)
    if not isinstance(raw, dict):
        raise ValueError("Source progress must be a dictionary")
    progress = harvest.load_progress()
    directory = dest / "pdf"
    directory.mkdir(parents=True, exist_ok=True)
    imported, skipped, errors, conflicts = [], 0, [], []
    for ident, row in sorted(raw.items()):
        if not isinstance(ident, str) or not isinstance(row, dict):
            continue
        if row.get("status") != "pdf-confirmed":
            continue
        digest = row.get("sha256")
        size = row.get("bytes")
        if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
            errors.append([ident, "invalid sha256"]);continue
        if not isinstance(size, int) or not 500 <= size <= 50_000_000:
            errors.append([ident, "invalid PDF size"]);continue
        name = hashlib.sha256(ident.encode()).hexdigest()[:24] + ".pdf"
        old = source / "pdf" / name
        destfile = directory / name
        if not old.is_file() or old.stat().st_size != size:
            errors.append([ident, "source absent or incomplete"]);continue
        if not harvest.cached_pdf_ok(ident, progress.get(ident)):
            if progress.get(ident, {}).get("status") == "pdf-confirmed":
                conflicts.append([ident, "existing record does not match disk"]);continue
        else:
            if progress[ident]["sha256"] != digest:
                conflicts.append([ident, "same work ID, different PDF"]);continue
            skipped += 1
            continue
        with old.open("rb") as stream:
            blob = stream.read()
        if len(blob) != size or hashlib.sha256(blob).hexdigest() != digest or not harvest.pdf_data(blob):
            errors.append([ident, "source checksum or PDF structure mismatch"]);continue
        if destfile.exists():
            conflicts.append([ident, "destination file already exists"]);continue
        try:
            try:
                os.link(old, destfile)
            except OSError:
                shutil.copy2(old, destfile)
            if not destfile.is_file() or destfile.stat().st_size != size:
                raise OSError("destination changed size")
            with destfile.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise OSError("destination changed checksum")
        except OSError as error:
            destfile.unlink(missing_ok=True)
            errors.append([ident, type(error).__name__]);continue
        progress[ident] = {**row, "status": "pdf-confirmed", "source": "imported-local-cache",
                           "license_status": "not_reviewed"}
        imported.append(ident)
    if imported:
        # The live downloader must not write to the same destination simultaneously.
        harvest.write_json(harvest.LOG, progress)
    result = {"imported": len(imported), "already_present": skipped,
              "errors": errors, "conflicts": conflicts, "new_ids": imported,
              "all_statuses_in_destination": len(progress), "source": str(source)}
    print("LOCAL_CACHE_MERGE", json.dumps(result, ensure_ascii=False), flush=True)
    return result


def audit(progress):
    records = harvest.read_json(harvest.ROOT / "docs/data/publications.json", [])
    additions = harvest.read_json(harvest.ROOT / "docs/data/nordic_additions.json", [])
    metadata = {r["id"]: r for r in records + additions}
    # DOI-only works are indexed privately without changing the public corpus.
    imported = harvest.read_json(harvest.PRIVATE / "doi_csv_metadata.json", {}) or {}
    if isinstance(imported, dict):
        for ident, row in imported.items():
            if isinstance(row, dict):
                metadata.setdefault(ident, row)
    verified, missing, failed, duplicates = [], [], [], defaultdict(list)
    for ident, item in sorted(progress.items()):
        status = item.get("status")
        if status == "failed":
            failed.append({"id": ident, "reason": item.get("reason", "")})
            continue
        if status != "pdf-confirmed":
            continue
        if not harvest.cached_pdf_ok(ident, item):
            missing.append(ident)
            continue
        pdf = harvest.cache_path(ident)
        work = metadata.get(ident, {})
        verified.append({
            "id": ident, "title": work.get("title", ""),
            "authors": "; ".join(work.get("authors", [])),
            "year": work.get("year", ""), "doi": work.get("doi", ""),
            "file": str(pdf), "bytes": pdf.stat().st_size,
            "sha256": item["sha256"], "source_url": item.get("url", ""),
            "downloaded_at": item.get("checked_at", ""),
            "license_status": "not-reviewed-for-republication",
            "source_ids_from_input": ";".join(work.get("source_ids_from_input", [])),
            "catalogue_ids": ";".join(work.get("catalogue_ids", [])),
            "bibliography_review_status": work.get("source_review_status_from_input", ""),
        })
        duplicates[item["sha256"]].append(ident)
    return verified, missing, failed, {sha: ids for sha, ids in duplicates.items()
                                      if len(ids) > 1}


def write_report(verified, missing, failed, duplicates, *, base=None):
    base = base or harvest.PRIVATE
    base.mkdir(parents=True, exist_ok=True)
    csv_path = base / "pdf_local_index.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        columns = ["id", "title", "authors", "year", "doi",
                   "file", "bytes", "sha256", "source_url",
                   "downloaded_at", "license_status",
                   "source_ids_from_input", "catalogue_ids", "bibliography_review_status"]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(verified)
    total = sum(row["bytes"] for row in verified)
    summary = {
        "verified_pdfs_on_disk": len(verified),
        "unique_pdf_hashes": len({row["sha256"] for row in verified}),
        "duplicate_hash_groups": len(duplicates),
        "actual_disk_bytes": total,
        "actual_disk_gb": round(total / 1_000_000_000, 3),
        "cache_entries_missing_or_corrupt": len(missing),
        "failed_retrieval_attempts": len(failed),
        "missing_ids": missing,
        "duplicate_ids": duplicates,
        "index_path": str(csv_path),
        "rights_note": "Files are in a private cache; no redistribution licence is inferred.",
    }
    harvest.write_json(base / "pdf_local_report.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failed", action="store_true", help="Print failed retrieval IDs")
    parser.add_argument("--merge-local", type=Path, help="Import valid PDFs from another local private cache (no network)")
    args = parser.parse_args()
    if args.merge_local:
        merge_local_cache(args.merge_local)
    progress = harvest.load_progress()
    verified, missing, failed, duplicates = audit(progress)
    summary = write_report(verified, missing, failed, duplicates)
    print(json.dumps({key: val for key, val in summary.items()
                      if key not in ("missing_ids", "duplicate_ids")}, ensure_ascii=False, indent=2))
    if args.failed:
        for row in failed:
            print(row["id"], row["reason"])


if __name__ == "__main__":
    main()
