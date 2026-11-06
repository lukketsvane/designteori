#!/usr/bin/env python3
"""Verify the locally collected PDF corpus and export a private, searchable file index.

This reports actual bytes on disk. The public bibliography and OA URL counts are
not treated as downloaded files. The report and private PDF paths are never
published by CI or committed to Git.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import hent_oa_pdf as harvest


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
                   "downloaded_at", "license_status"]
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
    args = parser.parse_args()
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
