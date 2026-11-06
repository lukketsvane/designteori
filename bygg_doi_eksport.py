#!/usr/bin/env python3
"""Build a reproducible DOI retrieval input from the published research catalog.

Metadata-only operation, no network and no PDFs. A repeated DOI is a single
retrieval target with *all* source IDs retained; it is NOT a verified same-work
match. Only individually verified licence rights allow public PDF mirroring.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from hent_doi_csv import normalize_doi
from hent_oa_pdf import allowed_url, direct_pdf_hint, safe_public_link

ROOT = Path(__file__).resolve().parent
EXPORT = ROOT / "results" / "doi_eksport.csv"
SUMMARY = ROOT / "results" / "doi_eksport_status.json"
COLUMNS = ("doi", "title", "oa_url", "source_layer", "source_ids",
           "scope", "kind", "candidate_count", "review_status", "priority")

def tier(entry: dict) -> tuple:
    """Prioritise discoverable, relevant scholarly OA, never inferred validity."""
    scope = entry.get("scope") or ""
    kind = entry.get("kind") or ""
    loc = entry.get("oa_url") or ""
    return (0 if direct_pdf_hint(loc) else 1 if loc else 2,
            0 if kind in ("article", "review", "proceedings-article") else 1,
            0 if scope == "automatic-title-inclusion" else 1,
            0 if entry["layer"] == "openalex" else 1,
            str(entry.get("id") or ""))

def make_export(base: list[dict], nordic: list[dict],
                historical: list[dict]) -> tuple[list[dict], dict]:
    layers = [("openalex", base), ("nordic-candidate", nordic),
              ("historical-candidate", historical)]
    grouped = defaultdict(list)
    skipped = Counter()
    seen_ids = set()
    for layer, items in layers:
        for w in items:
            work_id = w.get("id")
            if not work_id or work_id in seen_ids:
                raise ValueError("Missing or duplicated source record ID")
            seen_ids.add(work_id)
            short = normalize_doi(w.get("doi"))
            if not short:
                skipped[layer] += 1
                continue
            url = w.get("oa_url") or ""
            if not url and w.get("origin") == "external":
                # Institutional repository landing pages are leads, not PDFs.
                url = w.get("source_url") or ""
            if not safe_public_link(url):
                url = ""
            grouped[short].append({
                "id": work_id, "layer": layer, "title": w.get("title") or "",
                "kind": w.get("kind") or "unknown", "scope": w.get("scope") or "",
                "oa_url": url,
            })
    output = []
    with_oa = with_pdf_hint = duplicated = 0
    source_references = Counter()
    for doi, candidates in grouped.items():
        ordered = sorted(candidates, key=tier)
        chosen = ordered[0]
        linked = sorted({c["id"] for c in candidates})
        n = len(linked)
        if n > 1:
            duplicated += 1
        oa = chosen["oa_url"]
        if oa:
            with_oa += 1
        if direct_pdf_hint(oa):
            with_pdf_hint += 1
        source_references.update(set(c["layer"] for c in candidates))
        group_status = "possible-duplicate-doi-needs-review" if n > 1 else "metadata-unreviewed"
        priority = ("direct-oa-url" if direct_pdf_hint(oa) else
                    "oa-landing-or-url" if oa else "doi-only")
        output.append({
            "doi": "https://doi.org/" + doi,
            "title": chosen["title"], "oa_url": oa,
            "source_layer": chosen["layer"], "source_ids": ";".join(linked),
            "scope": chosen["scope"], "kind": chosen["kind"],
            "candidate_count": n, "review_status": group_status,
            "priority": priority,
        })
    rank = {"direct-oa-url": 0, "oa-landing-or-url": 1, "doi-only": 2}
    output.sort(key=lambda r: (
        rank[r["priority"]],
        0 if r["kind"] in ("article", "review", "proceedings-article") else 1,
        0 if r["scope"] == "automatic-title-inclusion" else 1,
        r["doi"],
    ))
    status = {
        "source": "docs/data/publications.json + nordic_additions.json + theory_additions.json",
        "registration_count": sum(len(r) for _, r in layers),
        "unique_valid_doi_retrieval_targets": len(output),
        "registrations_with_valid_doi": sum(len(v) for v in grouped.values()),
        "doi_keys_with_multiple_source_records": duplicated,
        "doi_with_oa_url": with_oa,
        "doi_with_direct_pdf_shaped_url": with_pdf_hint,
        "doi_only": len(output) - with_oa,
        "doi_keys_seen_per_layer": dict(sorted(source_references.items())),
        "registrations_without_valid_doi": dict(sorted(skipped.items())),
        "semantic_limit": (
            "Every row is an unreviewed retrieval candidate, not proof of a Nordic "
            "design-research publication, available full text or redistribution permission. "
            "DOI collisions require manual identity/version checks."
        ),
    }
    return output, status

def safe_csv(value) -> str:
    s = str(value if value is not None else "")
    return "'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s

def build(root: Path = ROOT) -> dict:
    root = Path(root)
    public = root / "docs" / "data"
    def load(name):
        return json.loads((public / name).read_text(encoding="utf-8"))
    records, status = make_export(
        load("publications.json"), load("nordic_additions.json"),
        load("theory_additions.json"))
    out = root / "results"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "doi_eksport.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in records:
            writer.writerow({key: safe_csv(row[key]) for key in COLUMNS})
    (out / "doi_eksport_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("DOI_EXPORT", json.dumps(status, ensure_ascii=False))
    return status

if __name__ == "__main__":
    build()
