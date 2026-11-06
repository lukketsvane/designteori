#!/usr/bin/env python3
"""Bygg eit separat, søkbart register over historiske teorireferansar.

Inga avstemming på berre lik tittel vert handsama som sikker identitet.
Historiske eller internasjonale referansar vert ikkje flytta inn i
den nordiske OpenAlex-populasjonen. Køyrer utan nettverk.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from samkoyr_norden import normalized_doi, normalized_title

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "docs" / "data"
SOURCE = ROOT / "bibliografi" / "historiske_referansar.csv"
OUTPUT = PUBLIC / "theory_additions.json"
STATUS = PUBLIC / "theory_status.json"
AUDIT = ROOT / "results" / "theory_source_audit.csv"
AUDIT_FIELDS = (
    "source", "bibtex_key", "title", "year", "doi", "candidate_id",
    "linked_id", "status", "reason"
)
KIND_MAP = {
    "article": "article", "book": "book", "incollection": "book-chapter",
    "inbook": "book-chapter", "inproceedings": "proceedings-article",
    "conference": "proceedings-article", "phdthesis": "thesis",
    "mastersthesis": "thesis", "techreport": "report", "report": "report",
    "misc": "unknown",
}


def author_key(s: str) -> str:
    """Unngå at identiske titlar med ulike førsteforfattarar blir samanslegne."""
    first = re.split(r"\s+and\s+|;|&", s or "", maxsplit=1, flags=re.I)[0]
    return normalized_title(first.split(",")[0])


def author_list(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"\s+and\s+|;", s or "", flags=re.I) if x.strip()]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build(root: Path = ROOT) -> dict:
    root = Path(root)
    public = root / "docs" / "data"
    results = root / "results"
    base = json.loads((public / "publications.json").read_text(encoding="utf-8"))
    nordic = json.loads((public / "nordic_additions.json").read_text(encoding="utf-8"))
    historical = read_csv(root / "bibliografi" / "historiske_referansar.csv")
    known_ids = {w["id"] for w in base}
    doi_known = defaultdict(set)
    title_known = defaultdict(set)
    doi_editorial = defaultdict(set)
    title_editorial = defaultdict(set)
    for w in base:
        if d := normalized_doi(w.get("doi")):
            doi_known[d].add(w["id"])
        title_known[(normalized_title(w.get("title")), str(w.get("year") or ""))].add(w["id"])
    for w in nordic:
        if d := normalized_doi(w.get("doi")):
            doi_editorial[d].add(w["id"])
        title_editorial[(normalized_title(w.get("title")), str(w.get("year") or ""))].add(w["id"])

    groups = {}
    audit = []
    for row in historical:
        title = (row.get("title") or "").strip()
        year = (row.get("year") or "").strip()
        author = (row.get("authors") or "").strip()
        d = normalized_doi(row.get("doi"))
        bid = (row.get("bibtex_key") or "").strip()
        source = (row.get("source") or "").strip()
        status, reason, linked, cid = "candidate-new", "No exact ID or DOI match", "", ""
        if not title:
            status, reason = "missing-title", "Record needs bibliographic correction"
        elif d and len(doi_known[d]) == 1:
            status, reason, linked = "matched-openalex-doi", "Exact unique DOI in base catalog", next(iter(doi_known[d]))
        elif d and len(doi_known[d]) > 1:
            status, reason = "ambiguous-openalex-doi", "Several base records share this DOI"
        elif d and len(doi_editorial[d]) == 1:
            status, reason, linked = "matched-editorial-doi", "Exact DOI in pending Nordic bibliography", next(iter(doi_editorial[d]))
        elif d and len(doi_editorial[d]) > 1:
            status, reason = "ambiguous-editorial-doi", "Several pending Nordic references share the DOI"
        else:
            # A title-year match does NOT establish identity. The retained
            # candidate must be reviewed and is kept out of proven work counts.
            guess = (normalized_title(title), year)
            if row.get("openalex_id") in known_ids:
                status, reason = "possible-openalex-id", "Earlier title/year crosswalk, unverified"
            elif title_known.get(guess):
                status, reason = "possible-openalex-title-year", "Potential same work, manual version check"
            elif title_editorial.get(guess):
                status, reason = "possible-editorial-title-year", "Potential duplicate of Nordic reference"
        if title and status not in ("matched-openalex-doi", "matched-editorial-doi"):
            # Same DOI is a strong staging identity hint. Without a DOI, only
            # identical title, year and first author are grouped PROVISIONALLY.
            # Missing year or author deliberately prevents weak automatic joins.
            key = ("doi", d) if d else (
                ("title-author-year", normalized_title(title), year, author_key(author))
                if year and author_key(author) else ("isolated", source, bid)
            )
            if key in groups and normalized_title(groups[key]["title"]) != normalized_title(title):
                key = ("doi-collision", d, normalized_title(title), source, bid)
                status, reason = "doi-collision-review", "Same DOI but different titles"
            digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:20]
            cid = "theory:" + digest
            provenance = {
                "source_file": row.get("source_file") or "",
                "bibtex_key": bid,
                "identity_match_method": row.get("match_type") or "",
            }
            if key in groups:
                item = groups[key]
                if status == "candidate-new":
                    status, reason = "provisionally-grouped", "Same title/year/author or DOI; identity unverified"
                item["provenance"].append(provenance)
                item["bibliography_entries"] += 1
            else:
                url = (row.get("url") or "").strip()
                if not url.startswith("https://"):
                    url = "https://github.com/lukketsvane/designteori/blob/main/" + (row.get("source_file") or "")
                item = {
                    "id": cid, "origin": "historical", "scope": "historical-reference",
                    "title": title, "year": int(year) if year.isdecimal() else None,
                    "authors": author_list(author),
                    "doi": "https://doi.org/" + d if d else "",
                    "kind": KIND_MAP.get((row.get("kind") or "").lower(), "unknown"),
                    "source": row.get("publisher") or "Teorireferanse",
                    "source_url": url,
                    "countries": [], "country_evidence": "not-verified",
                    "oa_url": "", "pdf": "", "text": "", "license": "",
                    "citations": None, "topic": "", "theme": "",
                    "review_status": "metadata-unreviewed",
                    "duplicate_status": status, "bibliography_entries": 1,
                    "review_priority": "", "review_score": 0,
                    "provenance": [provenance],
                }
                groups[key] = item
        audit.append({
            "source": source, "bibtex_key": bid, "title": title, "year": year,
            "doi": row.get("doi") or "", "candidate_id": cid,
            "linked_id": linked, "status": status, "reason": reason
        })

    candidates = sorted(groups.values(), key=lambda w: (
        -(w["year"] or 0), normalized_title(w["title"]), w["id"]
    ))
    counts = Counter(r["status"] for r in audit)
    stats = {
        "raw_historical_references": len(historical),
        "unique_provisional_candidate_records": len(candidates),
        "source_references_collapsed": sum(w["bibliography_entries"] - 1 for w in candidates),
        "matched_openalex_exact_doi": counts["matched-openalex-doi"],
        "matched_nordic_editorial_exact_doi": counts["matched-editorial-doi"],
        "possible_existing_title_or_id": (
            counts["possible-openalex-id"] + counts["possible-openalex-title-year"]
            + counts["possible-editorial-title-year"]
        ),
        "ambiguous_doi_records": sum(v for k, v in counts.items() if "ambiguous" in k or "collision" in k),
        "audit_rows": len(audit),
        "status_counts": dict(sorted(counts.items())),
        "warning": (
            "Provisoriske søkjepostar frå historiske og globale bibliografiar. "
            "Verken nordisk tilknyting, identitet eller fagleg relevans er verifisert. "
            "Tittel/forfattar/år-gruppering er ikkje sikker deduplisering."
        ),
    }
    public.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    (public / "theory_additions.json").write_text(
        json.dumps(candidates, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8"
    )
    (public / "theory_status.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (results / "theory_source_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(audit)
    print("THEORY_REGISTER", json.dumps(stats, ensure_ascii=False))
    return stats


if __name__ == "__main__":
    build()
