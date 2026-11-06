#!/usr/bin/env python3
"""Proveniens- og dekningsoversikt for dei tre skilde metadata-laga.

Tala er deskriptive registreringstal, ikkje eit populasjonsestimat
eller eit mål på vitskapleg kvalitet. Ingen automatisk fagkoding.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def doi_key(value: str) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", s, flags=re.I)
    s = s.rstrip(".,);] /")
    return s if re.fullmatch(r"10\.\d{4,9}/\S+", s) else ""


def present(value) -> bool:
    return bool(value) if isinstance(value, (list, dict)) else bool(str(value or "").strip())


def summarize(base: list[dict], nordic: list[dict], theory: list[dict],
              nordic_status: dict, theory_status: dict) -> dict:
    layers = {
        "openalex_partial_2000_2026": base,
        "nordic_editorial_and_repository_candidates": nordic,
        "historical_global_theory_candidates": theory,
    }
    all_ids: list[str] = []
    tables: dict[str, dict] = {}
    doi_rows = defaultdict(list)
    for name, rows in layers.items():
        ids = [w.get("id") for w in rows]
        if not all(ids) or len(ids) != len(set(ids)):
            raise ValueError("Missing or repeated record ID in " + name)
        all_ids.extend(ids)
        kinds = Counter(w.get("kind") or "unknown" for w in rows)
        decades = Counter(
            str((int(w["year"]) // 10) * 10) + "s"
            for w in rows if str(w.get("year") or "").isdigit()
        )
        tables[name] = {
            "searchable_registrations": len(rows),
            "with_doi": sum(bool(doi_key(w.get("doi"))) for w in rows),
            "with_authors": sum(present(w.get("authors")) for w in rows),
            "with_year": sum(present(w.get("year")) for w in rows),
            "with_local_pdf": sum(present(w.get("pdf")) for w in rows),
            "with_open_access_url": sum(present(w.get("oa_url")) for w in rows),
            "kinds": dict(sorted(kinds.items())),
            "decades": dict(sorted(decades.items())),
        }
        for w in rows:
            if d := doi_key(w.get("doi")):
                doi_rows[d].append({"layer": name, "id": w["id"]})
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Multiple layers share a supposedly distinct search ID")
    base_scopes = Counter(w.get("scope") for w in base)
    if set(base_scopes) - {"automatic-title-inclusion", "awaiting-eligibility-review"}:
        raise ValueError("Base contains unrecognized scope")
    if any(w.get("scope") not in ("editorial-candidate", "repository-candidate") for w in nordic):
        raise ValueError("Nordic candidate promoted without verification")
    if any(w.get("scope") != "historical-reference" or present(w.get("countries")) for w in theory):
        raise ValueError("Historical references claimed Nordic affiliation")
    if len(nordic) != nordic_status.get("unlinked_candidate_records"):
        raise ValueError("Nordic source summary out of sync")
    if len(theory) != theory_status.get("unique_provisional_candidate_records"):
        raise ValueError("Historical source summary out of sync")
    shared = {k: v for k, v in doi_rows.items() if len(v) > 1}
    return {
        "schema_version": 1,
        "measurement_unit": "source registrations; NOT vetted unique research works",
        "openalex_partial_search": len(base),
        "openalex_title_gate": dict(sorted(base_scopes.items())),
        "nordic_unlinked_candidates": len(nordic),
        "historical_global_provisional_groups": len(theory),
        "historical_original_bibliography_entries": theory_status.get("raw_historical_references"),
        "total_searchable_rows_all_layers": sum(len(x) for x in layers.values()),
        "coverage_by_layer": tables,
        "cross_layer_or_within_layer_possible_doi_duplicates": {
            "duplicate_doi_keys": len(shared),
            "registrations": sum(len(v) for v in shared.values()),
            "example_groups": [
                {"doi": d, "records": v} for d, v in sorted(shared.items())[:25]
            ],
            "all_groups": [
                {"doi": d, "records": v} for d, v in sorted(shared.items())
            ],
        },
        "manual_article_eligibility_checks_completed": 0,
        "cautions": [
            "This is a relevance-ranked, incomplete OpenAlex sample, not a census.",
            "Metadata matching is not independent peer review or a study of replicability.",
            "DOI can link identity candidates but does not establish research validity.",
            "Historical references and Nordic archival records are not automatically in scope.",
            "Citations alone do not prove that an older result was tested or extended.",
        ],
    }


def build(root: Path = ROOT) -> dict:
    data = Path(root) / "docs" / "data"
    def load(name: str):
        return json.loads((data / name).read_text(encoding="utf-8"))
    out = summarize(
        load("publications.json"), load("nordic_additions.json"),
        load("theory_additions.json"), load("nordic_status.json"),
        load("theory_status.json"),
    )
    (data / "corpus_quality.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("CORPUS_COVERAGE", out["total_searchable_rows_all_layers"],
          "BASE", out["openalex_partial_search"],
          "NORDIC", out["nordic_unlinked_candidates"],
          "HISTORICAL", out["historical_global_provisional_groups"])
    return out


if __name__ == "__main__":
    build()
