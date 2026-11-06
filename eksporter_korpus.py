#!/usr/bin/env python3
"""Publiser eit samordna metadatauttrekk utan å skjule kjeldelag.

OpenAlex-arbeid, nordiske kandidatar og historiske referansar held eigne
statusar. Ingen uavklart post vert rekna som eit verifisert forskingsfunn.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COLUMNS = (
    "id", "source_layer", "title", "year", "authors", "type",
    "doi", "source", "countries", "status", "source_url", "oa_url", "pdf"
)


def safe_cell(value) -> str:
    if isinstance(value, list):
        value = "; ".join(str(x) for x in value)
    value = str(value if value is not None else "")
    # Bibliografiske titlar er ikkje Excel-formlar.
    if re.match(r"^\s*[=+@-]", value):
        return "'" + value
    return value


def consolidated(base: list[dict], nordic: list[dict],
                 historical: list[dict]) -> list[dict]:
    records = []
    ids = set()
    for layer, items in (("openalex", base), ("nordic-candidate", nordic),
                         ("historical-candidate", historical)):
        for work in items:
            wid = work.get("id")
            if not wid or wid in ids:
                raise ValueError("Missing or repeated catalog ID: " + str(wid))
            ids.add(wid)
            scope = work.get("scope") or ""
            if layer == "historical-candidate" and scope != "historical-reference":
                raise ValueError("Historical bibliography promoted beyond metadata")
            if layer == "nordic-candidate" and scope not in (
                "editorial-candidate", "repository-candidate"
            ):
                raise ValueError("Nordic source promoted beyond metadata")
            records.append({
                "id": wid, "source_layer": layer, "title": work.get("title") or "",
                "year": work.get("year") or "", "authors": work.get("authors") or [],
                "type": work.get("kind") or "unknown", "doi": work.get("doi") or "",
                "source": work.get("source") or "", "countries": work.get("countries") or [],
                "status": scope, "source_url": work.get("source_url") or "",
                "oa_url": work.get("oa_url") or "", "pdf": work.get("pdf") or "",
            })
    return records


def build(root: Path = ROOT) -> int:
    data = Path(root) / "docs" / "data"
    load = lambda name: json.loads((data / name).read_text(encoding="utf-8"))
    records = consolidated(
        load("publications.json"), load("nordic_additions.json"),
        load("theory_additions.json")
    )
    expected = load("corpus_quality.json")["total_searchable_rows_all_layers"]
    if len(records) != expected:
        raise ValueError("Metadata export differs from source-layer coverage report")
    dest = data / "korpus.csv"
    with dest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows({k: safe_cell(row[k]) for k in COLUMNS} for row in records)
    print("CORPUS_CSV", len(records), dest)
    return len(records)


if __name__ == "__main__":
    build()
