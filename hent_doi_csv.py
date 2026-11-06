#!/usr/bin/env python3
"""Read a DOI CSV and reuse the resumable public OA PDF harvester.

No network requests without --download. PDFs and DOI-to-file mappings stay
in the gitignored private cache; OA access is not a redistribution licence.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hent_oa_pdf as oa

ROOT = Path(__file__).resolve().parent
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s<>\"']+", re.I)


def normalize_doi(value) -> str:
    text = str(value or "").strip().strip('"').strip("'")
    if text.lower().startswith(("https://", "http://")):
        uri = urlsplit(text)
        if (uri.hostname or "").lower().rstrip(".") not in ("doi.org", "dx.doi.org"):
            return ""
        text = uri.path.lstrip("/")
    text = re.sub(r"^doi:\s*", "", text, flags=re.I)
    text = unquote(text).strip().rstrip(").,;]")
    return text.lower() if DOI_PATTERN.fullmatch(text) else ""


def read_dois(path: Path) -> tuple[list[dict], dict]:
    entries, seen, invalid, repeated = [], set(), [], 0
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        doi_col = next((k for k in fields if k.strip().lower() == "doi"), None)
        if doi_col is None:
            doi_col = next((k for k in fields if "doi" in k.strip().lower()), None)
        if doi_col is None:
            raise ValueError("CSV manglar DOI-kolonne")
        title_col = next((k for k in fields if k.strip().lower() in ("title", "tittel")), None)
        ids_col = next((k for k in fields if k.strip().lower() == "source_ids"), None)
        layer_col = next((k for k in fields if k.strip().lower() == "source_layer"), None)
        status_col = next((k for k in fields if k.strip().lower() == "review_status"), None)
        scope_col = next((k for k in fields if k.strip().lower() == "scope"), None)
        oa_col = next((k for k in fields if k.strip().lower() in ("oa_url", "pdf_url")), None)
        for line, row in enumerate(reader, 2):
            raw = (row.get(doi_col) or "").strip()
            if not raw:
                continue
            doi = normalize_doi(raw)
            if not doi:
                invalid.append(line)
                continue
            if doi in seen:
                repeated += 1
                continue
            seen.add(doi)
            link = (row.get(oa_col) or "").strip() if oa_col else ""
            entries.append({
                "doi": doi, "line": line,
                "title": (row.get(title_col) or "").strip() if title_col else "",
                "oa_url": link if oa.safe_public_link(link) else "",
                "source_ids": sorted({s.strip() for s in (
                    row.get(ids_col) or "").split(";") if s.strip()}) if ids_col else [],
                "source_layer": (row.get(layer_col) or "").strip() if layer_col else "",
                "source_scope": (row.get(scope_col) or "").strip() if scope_col else "",
                "source_review_status": (row.get(status_col) or "").strip() if status_col else "",
            })
    return entries, {
        "unique_dois": len(entries), "duplicate_rows": repeated,
        "invalid_rows": len(invalid), "invalid_line_numbers_first_20": invalid[:20]
    }


def known_dois(root: Path = ROOT) -> dict[str, list[dict]]:
    index = defaultdict(list)
    for filename in ("publications.json", "nordic_additions.json"):
        for row in oa.read_json(root / "docs/data" / filename, []) or []:
            doi = normalize_doi(row.get("doi"))
            if doi and row.get("id") and not any(x["id"] == row["id"] for x in index[doi]):
                index[doi].append(row)
    return index


def make_rows(entries: list[dict], known: dict, archived: set[str] | None = None):
    archived = archived or set()
    output = []
    for item in entries:
        candidates = known.get(item["doi"], [])
        match = "unique-catalog-doi" if len(candidates) == 1 else (
            "ambiguous-catalog-doi" if candidates else "doi-not-in-catalog")
        work = candidates[0] if len(candidates) == 1 else {}
        ident = work.get("id") or "doi:" + hashlib.sha256(
            item["doi"].encode("utf-8")).hexdigest()[:24]
        url = item["oa_url"] or work.get("oa_url") or ""
        if not url and work.get("origin") == "external":
            url = work.get("source_url") or ""
        output.append({
            "id": ident, "doi": "https://doi.org/" + item["doi"],
            "title": work.get("title") or item["title"],
            "kind": work.get("kind") or "unknown",
            "oa_url": url if oa.safe_public_link(url) else "",
            "scope": work.get("scope") or "doi-csv-unreviewed",
            "archived": "yes" if ident in archived else "no",
            "source_row": item["line"], "catalog_match": match,
            "source_ids": item.get("source_ids") or [],
            "source_layer": item.get("source_layer") or "",
            "source_scope": item.get("source_scope") or "",
            "source_review_status": item.get("source_review_status") or "",
            "catalogue_ids": sorted({r.get("id", "") for r in candidates if r.get("id")}),
        })
    return output


def private_index(rows: list[dict]):
    target = oa.PRIVATE / "doi_csv_metadata.json"
    metadata = oa.read_json(target, {}) or {}
    for row in rows:
        metadata[row["id"]] = {
            "id": row["id"], "title": row["title"], "doi": row["doi"],
            "kind": row["kind"], "authors": [], "year": "",
            "catalog_match": row["catalog_match"], "source": "DOI CSV",
            "source_ids_from_input": row.get("source_ids", []),
            "source_layer_from_input": row.get("source_layer", ""),
            "source_scope_from_input": row.get("source_scope", ""),
            "source_review_status_from_input": row.get("source_review_status", ""),
            "catalogue_ids": row.get("catalogue_ids", [])
        }
    oa.write_json(target, metadata)


def write_report(rows: list[dict], progress: dict, stats: dict):
    columns = ("id", "doi", "title", "source_row", "catalog_match",
               "source_ids_from_input", "catalogue_ids", "source_review_status",
               "status", "cache_verified", "sha256", "bytes", "source_url")
    target = oa.PRIVATE / "doi_csv_report.csv"
    counts, verified = defaultdict(int), 0
    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            result = progress.get(row["id"], {})
            actual = oa.cached_pdf_ok(row["id"], result)
            verified += actual
            status = ("publicly-archived" if row["archived"] == "yes" else
                      "pdf-confirmed" if actual else result.get("status", "not-attempted"))
            counts[status] += 1
            values = {
                "id": row["id"], "doi": row["doi"], "title": row["title"],
                "source_row": row["source_row"], "catalog_match": row["catalog_match"],
                "source_ids_from_input": ";".join(row.get("source_ids", [])),
                "catalogue_ids": ";".join(row.get("catalogue_ids", [])),
                "source_review_status": row.get("source_review_status", ""),
                "status": status, "cache_verified": "yes" if actual else "no",
                "sha256": result.get("sha256", "") if actual else "",
                "bytes": result.get("bytes", "") if actual else "",
                "source_url": result.get("url", "") if actual else "",
            }
            # Guard Excel consumers of the private CSV against formula injection.
            writer.writerow({k: ("'" + str(v) if re.match(r"^\s*[=+@-]", str(v))
                                  else v) for k, v in values.items()})
    result = {**stats, "imported_rows": len(rows),
              "matched_unique_catalog_dois": sum(r["catalog_match"] == "unique-catalog-doi" for r in rows),
              "ambiguous_catalog_dois": sum(r["catalog_match"] == "ambiguous-catalog-doi" for r in rows),
              "not_in_catalog": sum(r["catalog_match"] == "doi-not-in-catalog" for r in rows),
              "verified_pdfs_in_private_cache": verified, "statuses": dict(sorted(counts.items())),
              "report": str(target),
              "rights_note": "A downloaded OA PDF is not automatically licensed for public redistribution."}
    oa.write_json(oa.PRIVATE / "doi_csv_summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "doi_liste.csv")
    parser.add_argument("--download", action="store_true", help="Explicitly access public OA sources")
    parser.add_argument("--limit", type=int, default=8000)
    parser.add_argument("--email", default="", help="Contact email for optional Unpaywall lookup")
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--max-mb", type=int, default=25)
    parser.add_argument("--max-cache-gb", type=float, default=30.0)
    parser.add_argument("--min-free-gb", type=float, default=2.0)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--no-openalex", action="store_false", dest="lookup_openalex")
    parser.add_argument("--lookup-semantic-scholar", action="store_true",
                        help="Try Semantic Scholar's public OA PDF field after other sources")
    parser.set_defaults(lookup_openalex=True)
    args = parser.parse_args()
    if (args.limit < 1 or args.delay < 0.5 or not 1 <= args.max_mb <= 50
            or args.max_cache_gb < 0.1 or args.min_free_gb < 0
            or args.shards < 1 or not 0 <= args.shard < args.shards):
        parser.error("Invalid download limits, delay or shard")
    if not args.input.is_file():
        parser.error("Manglar DOI CSV: " + str(args.input))
    try:
        entries, stats = read_dois(args.input)
    except (ValueError, UnicodeError, csv.Error) as exc:
        parser.error(str(exc))
    published = oa.read_json(ROOT / "fulltekst/manifest.json", {"items": []})
    archived = {item["id"] for item in published.get("items", [])}
    rows = make_rows(entries, known_dois(), archived)
    chosen = [r for r in rows if int(hashlib.sha256(r["id"].encode()).hexdigest()[:12], 16)
              % args.shards == args.shard]
    print("DOI_CSV", json.dumps({**stats, "shard_records": len(chosen)},
                               ensure_ascii=False), flush=True)
    if not args.download:
        print("DRY_RUN: no downloads or files written; add --download to start.")
        return
    oa.PRIVATE.mkdir(parents=True, exist_ok=True)
    private_index(rows)
    progress = oa.load_progress()
    attempts = oa.download(
        chosen, progress, limit=args.limit, email=args.email, pause=args.delay,
        max_bytes=args.max_mb * 1_000_000, retry_failed=args.retry_failed,
        lookup_openalex=args.lookup_openalex,
        lookup_semantic_scholar=args.lookup_semantic_scholar,
        max_cache_bytes=int(args.max_cache_gb * 1_000_000_000),
        min_free_bytes=int(args.min_free_gb * 1_000_000_000))
    report = write_report(rows, progress, stats)
    print("DOI_IMPORT", json.dumps({"attempts": attempts,
        "verified_private_pdfs": report["verified_pdfs_in_private_cache"],
        "statuses": report["statuses"], "report": report["report"]},
        ensure_ascii=False), flush=True)
    from pdf_archive_report import audit, write_report as report_archive
    verified, missing, failed, duplicates = audit(progress)
    report_archive(verified, missing, failed, duplicates)


if __name__ == "__main__":
    main()
