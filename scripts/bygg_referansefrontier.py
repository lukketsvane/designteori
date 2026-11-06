#!/usr/bin/env python3
"""Prioriter publiserte kjelder som er siterte, men manglar i OpenAlex-uttrekket.

Ingen kandidat vert inkludert automatisk, og ingen bibliografisk sitering vert
koda som etterprøving, replisering eller sjølvstendig evidens. Nettverksfri.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
BIB = ROOT / "bibliografi" / "historiske_referansar.csv"
WORK_ID = re.compile(r"^W[0-9]+$")

COLUMNS = (
    "openalex_id", "openalex_url", "citing_works", "citing_title_included",
    "citing_2020_onwards", "distinct_citing_venues",
    "earliest_citing_year", "latest_citing_year", "example_citing_ids",
    "existing_bibliography_title", "existing_bibliography_doi",
    "bibliography_record_ids", "status"
)

def crosswalk(path: Path = BIB) -> dict[str, list[dict]]:
    matches = defaultdict(list)
    if not path.exists():
        return matches
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            wid = (row.get("openalex_id") or "").rsplit("/", 1)[-1].strip()
            if WORK_ID.fullmatch(wid):
                matches[wid].append(row)
    return matches


def analyze(conn: sqlite3.Connection, *, minimum: int = 2, limit: int = 5000,
            bibliography: dict | None = None) -> tuple[list[dict], dict]:
    if minimum < 1 or limit < 1:
        raise ValueError("minimum og limit må vere positive")
    bibliography = bibliography if bibliography is not None else crosswalk()
    # Venstrejoin og grouping sikrar at *berre* refererte, ukatalogiserte
    # OpenAlex-identifikatorar kjem inn i utvidingskøa.
    raw = conn.execute("""
        SELECT r.cited_id, COUNT(*) AS n,
          SUM(CASE WHEN w.in_scope=1 THEN 1 ELSE 0 END) AS n_scope,
          SUM(CASE WHEN w.year>=2020 THEN 1 ELSE 0 END) AS n_recent,
          COUNT(DISTINCT COALESCE(w.source, '')) AS venues,
          MIN(w.year) AS first_year, MAX(w.year) AS last_year
        FROM references_all r
        JOIN works w ON w.id=r.citing_id
        LEFT JOIN works known ON known.id=r.cited_id
        WHERE known.id IS NULL
        GROUP BY r.cited_id
    """).fetchall()
    eligible = [r for r in raw if WORK_ID.fullmatch(str(r[0] or ""))]
    selected = [r for r in eligible if r[1] >= minimum]
    # Primærprioritet: fleire uavhengige siterande postar innan den
    # uverifiserte tittelgaten. Dette er *ikkje* ein kumulativitetsindikator.
    selected.sort(key=lambda r: (-r[2], -r[1], -r[3], -r[4], r[0]))
    results = []
    for wid, n, n_scope, n_recent, venues, first, last in selected[:limit]:
        examples = [r[0] for r in conn.execute(
            "SELECT citing_id FROM references_all WHERE cited_id=? "
            "ORDER BY citing_id LIMIT 5", (wid,)
        ).fetchall()]
        refs = bibliography.get(wid, [])
        results.append(dict(zip(COLUMNS, (
            wid, "https://openalex.org/" + wid, n, n_scope, n_recent, venues,
            first, last, ";".join(examples),
            " | ".join(sorted({r.get("title", "") for r in refs if r.get("title")})),
            " | ".join(sorted({r.get("doi", "") for r in refs if r.get("doi")})),
            ";".join(sorted({r.get("bibtex_key", "") for r in refs if r.get("bibtex_key")})),
            "metadata-discovery-only; title-and-identity-unverified"
        ))))
    status = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "method": "OpenAlex referenced_works IDs absent from the original works table",
        "known_works": conn.execute("SELECT COUNT(*) FROM works").fetchone()[0],
        "unresolved_reference_ids": len(eligible),
        "unresolved_cited_by_at_least_2": sum(r[1] >= 2 for r in eligible),
        "unresolved_cited_by_at_least_10": sum(r[1] >= 10 for r in eligible),
        "minimum_citing_works": minimum,
        "max_export": limit,
        "exported_candidates": len(results),
        "already_crosswalked_in_historical_bibliography": sum(bool(bibliography.get(r["openalex_id"])) for r in results),
        "warning": (
            "Ingen nye unike, bibliografisk verifiserte publikasjonar vart etablerte. "
            "Ein referanse-ID seier ikkje noko sikkert om nordisk tilknyting, "
            "sjanger, sjølvstendig testing, replisering eller fagleg relevans. "
            "Føreset skeivt, avgrensa OpenAlex-uttrekk."
        )
    }
    return results, status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--min-citing", type=int, default=2)
    args = parser.parse_args()
    from database import ensure_database
    db = ensure_database()
    conn = sqlite3.connect(db)
    try:
        rows, status = analyze(conn, minimum=args.min_citing, limit=args.limit)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "reference_frontier_priority.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "reference_frontier_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("REFERENCE_FRONTIER", json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
