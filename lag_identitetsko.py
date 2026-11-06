#!/usr/bin/env python3
"""Kø for manuell identitetsrevisjon: aldri automatisk fagleg godkjenning."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COLUMNS = (
    "queue_id", "priority", "source_layer", "source_record_id",
    "matched_or_candidate_id", "title", "year", "doi", "source_url",
    "existing_status", "review_task", "decision", "reviewer", "evidence"
)
PRIORITY = {"high": 0, "medium": 1, "low": 2}


def make_queue(nordic: list[dict], historical: list[dict],
               doi_overlaps: list[dict]) -> list[dict]:
    rows = []
    for record in nordic:
        status = record.get("status") or ""
        priority = "high" if status.startswith("matched") or "duplicate" in status else (
            "medium" if record.get("doi") else "low"
        )
        rows.append({
            "queue_id": "nordic:" + record["id"],
            "priority": priority, "source_layer": "nordic",
            "source_record_id": record["id"],
            "matched_or_candidate_id": record.get("matched_openalex_id") or "",
            "title": record.get("title") or "", "year": record.get("year") or "",
            "doi": record.get("doi") or "",
            "source_url": record.get("source_url") or "",
            "existing_status": status,
            "review_task": "Verify DOI, title, author and version; check Nordic affiliation and theory scope.",
            "decision": "UNREVIEWED", "reviewer": "", "evidence": "",
        })
    for record in historical:
        status = record.get("status") or ""
        priority = "high" if (
            "possible-" in status or "collision" in status or "ambiguous" in status
        ) else ("medium" if record.get("doi") or status == "provisionally-grouped" else "low")
        rows.append({
            "queue_id": "historical:" + record.get("source", "") + ":" + record["bibtex_key"],
            "priority": priority, "source_layer": "historical",
            "source_record_id": record["bibtex_key"],
            "matched_or_candidate_id": record.get("linked_id") or record.get("candidate_id") or "",
            "title": record.get("title") or "", "year": record.get("year") or "",
            "doi": record.get("doi") or "", "source_url": "",
            "existing_status": status,
            "review_task": "Verify publication, edition and identifier; distinguish duplicate source from distinct work.",
            "decision": "UNREVIEWED", "reviewer": "", "evidence": "",
        })
    for group in doi_overlaps:
        doi = group["doi"]
        rows.append({
            "queue_id": "duplicate-doi:" + doi,
            "priority": "high", "source_layer": "openalex-duplicate-review",
            "source_record_id": ";".join(r["id"] for r in group.get("records", [])),
            "matched_or_candidate_id": "", "title": "",
            "year": "", "doi": "https://doi.org/" + doi,
            "source_url": "", "existing_status": "possible-duplicate-doi",
            "review_task": "Compare title, authors, date and manifestations for each shared DOI.",
            "decision": "UNREVIEWED", "reviewer": "", "evidence": "",
        })
    ids = [r["queue_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Non-unique review queue IDs")
    rows.sort(key=lambda r: (PRIORITY[r["priority"]], r["source_layer"],
                             str(r["title"]).casefold(), r["queue_id"]))
    return rows


def build(root: Path = ROOT) -> dict:
    root = Path(root)
    with (root / "results/nordic_source_audit.csv").open(newline="", encoding="utf-8") as f:
        nordic = list(csv.DictReader(f))
    with (root / "results/theory_source_audit.csv").open(newline="", encoding="utf-8") as f:
        history = list(csv.DictReader(f))
    quality = json.loads((root / "docs/data/corpus_quality.json").read_text(encoding="utf-8"))
    groups = quality["cross_layer_or_within_layer_possible_doi_duplicates"]["all_groups"]
    rows = make_queue(nordic, history, groups)
    out = root / "results/identity_review_queue.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    status = {
        "task_count": len(rows),
        "nordic_references": len(nordic),
        "historical_references": len(history),
        "doi_overlap_groups_included": len(groups),
        "by_priority": dict(sorted(Counter(r["priority"] for r in rows).items())),
        "manual_decisions_completed": 0,
        "warning": "Machine-constructed review tasks. No identity, scope, or quality decision has been manually verified."
    }
    (root / "results/identity_review_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("IDENTITY_REVIEW", status)
    return status


if __name__ == "__main__":
    build()
