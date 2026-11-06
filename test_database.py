#!/usr/bin/env python3
"""Validate the published Nordic design theory database without fixed corpus sizes.

The OpenAlex records are provisional metadata, not manually verified theory articles.
Editorial and historical bibliography entries are separate provenance layers.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import shutil
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def read_csv(path: str):
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def unpack_sqlite(archive: Path, target: Path) -> sqlite3.Connection:
    with gzip.open(archive, "rb") as source, target.open("wb") as dest:
        shutil.copyfileobj(source, dest)
    connection = sqlite3.connect(target)
    require(connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
            "SQLite integrity check failed for " + archive.name)
    return connection


def main() -> None:
    records = load("docs/data/publications.json")
    stats = load("docs/data/stats.json")
    require(isinstance(records, list) and bool(records), "empty publication catalog")

    ids = [record.get("id") for record in records]
    require(all(ids) and len(set(ids)) == len(ids), "empty or duplicate OpenAlex work IDs")
    require(all(record.get("title") for record in records), "untitled record")
    require(all("abstract" not in record and "raw_json" not in record for record in records),
            "restricted provider text exposed in public JSON")

    type_counts = Counter(record.get("kind") or "?" for record in records)
    scope_counts = Counter(record.get("scope") for record in records)
    require(dict(type_counts) == stats.get("kinds"), "publication type statistics are stale")
    require(stats.get("total") == len(records), "total metadata count is stale")
    require(stats.get("article_records") == type_counts.get("article", 0),
            "artikkelregistreringar are not equal to OpenAlex article records")
    require(stats.get("review_records") == type_counts.get("review", 0),
            "review count is stale")
    require(stats.get("automatic_title_inclusion") == scope_counts["automatic-title-inclusion"],
            "automatic title inclusion count is stale")
    require(stats.get("manual_review_queue") == scope_counts["awaiting-eligibility-review"],
            "manual eligibility queue count is stale")
    require(set(scope_counts) <= {"automatic-title-inclusion", "awaiting-eligibility-review"},
            "editorial candidates must not be added to the OpenAlex count")

    csv_records = read_csv("docs/data/publications.csv")
    require(len(csv_records) == len(records), "CSV export is incomplete")
    require({row["id"] for row in csv_records} == set(ids), "CSV and JSON work IDs disagree")

    bibliography = load("docs/data/bibliografiar.json")
    editorial = read_csv("bibliografi/avstemt_mot_openalex.csv")
    historical = read_csv("bibliografi/historiske_referansar.csv")
    items = bibliography["items"]
    require(len(items) == len(editorial) + len(historical) == bibliography["count"],
            "bibliography counts disagree")
    require(len({row["id"] for row in items}) == len(items), "duplicate bibliography IDs")
    require(sum(row["origin"] == "editorial" for row in items) == len(editorial),
            "Nordic editorial bibliography has missing records")
    require(sum(row["origin"] == "historical" for row in items) == len(historical),
            "historical bibliography has missing records")
    require(all(not row["source_id"] or row["source_id"] in set(ids)
                for row in items if row["origin"] == "editorial"),
            "editorial identity match points outside OpenAlex snapshot")

    triage = load("docs/data/triage.json")
    require(set(triage) == set(ids), "triage index out of sync with catalog")
    citations = load("docs/data/work_context.json")
    require(set(citations) == set(ids), "citation context index out of sync with catalog")
    require(all(set(ctx.get("cites", ()) + ctx.get("cited_by", ())) <= set(ids)
                for ctx in citations.values()),
            "citation context includes missing work")
    authors = load("docs/data/authors.json")
    institutions = load("docs/data/institutions.json")
    require(authors["count"] == len(authors["items"]), "author index incomplete")
    require(institutions["count"] == len(institutions["items"]), "institution index incomplete")

    manifest = load("fulltekst/manifest.json")
    require(manifest["count"] == len(manifest["items"]), "fulltext manifest count mismatch")
    rights_ids = set()
    for entry in manifest["items"]:
        require(entry["id"] in set(ids) and entry["id"] not in rights_ids,
                "fulltext has unknown or duplicated work ID")
        rights_ids.add(entry["id"])
        pdf = ROOT / "fulltekst" / entry["pdf"]
        require(pdf.is_file() and hashlib.sha256(pdf.read_bytes()).hexdigest() == entry["sha256"],
                "PDF missing or checksum mismatch for " + entry["id"])
        require(entry["license_url"].startswith("https://creativecommons.org/licenses/"),
                "missing redistributable Creative Commons license")
        if entry.get("text"):
            require((ROOT / "fulltekst" / entry["text"]).is_file(),
                    "fulltext index file missing for " + entry["id"])
            require("ND" not in entry["license"],
                    "NoDerivatives-licensed text should not be republished")
    require(sum(bool(record.get("pdf")) for record in records) == len(rights_ids),
            "public catalog has wrong PDF links")
    require(stats["local_pdf"] == len(rights_ids), "local fulltext count is stale")

    with tempfile.TemporaryDirectory() as td:
        source_db = unpack_sqlite(
            ROOT / "data/nordic_design_research.sqlite.gz", Path(td) / "openalex.sqlite")
        require(source_db.execute("SELECT count(*) FROM works").fetchone()[0] == len(records),
                "source SQLite and public index disagree")
        require(source_db.execute("SELECT count(*) FROM works WHERE in_scope=1").fetchone()[0]
                == scope_counts["automatic-title-inclusion"], "SQLite screening counts disagree")
        require(source_db.execute("SELECT count(*) FROM works WHERE coalesce(abstract,'')<>''")
                .fetchone()[0] == 0, "restricted abstracts in public source SQLite")
        source_db.close()

        combined_db = unpack_sqlite(
            ROOT / "data/designteori_hovuddatabase.sqlite.gz", Path(td) / "combined.sqlite")
        for table, expected in [
            ("works", len(records)),
            ("editorial_bibliography", len(editorial)),
            ("historical_bibliography", len(historical)),
            ("fulltext_versions", len(rights_ids)),
        ]:
            require(combined_db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    == expected, table + " is out of date in combined SQLite archive")
        combined_db.close()

    print("DATABASE OK:",
          len(records), "OpenAlex works;",
          type_counts.get("article", 0), "article records;",
          len(editorial), "Nordic editorial entries;",
          len(historical), "historical references;",
          len(rights_ids), "licensed PDFs.")


if __name__ == "__main__":
    main()
