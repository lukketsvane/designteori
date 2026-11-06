#!/usr/bin/env python3
"""Reconcile Nordic repository exports with the existing OpenAlex and editorial corpus.

Exact OpenAlex ID / unambiguous DOI links are matched automatically.
Title/year is only a review hint, never an automatic merge.
Metadata candidates are NOT verified Nordic theory articles.
All outputs are deterministic and contain no publisher full texts.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "docs" / "data"
AUDIT = ROOT / "results" / "nordic_source_audit.csv"
OUTPUT = PUBLIC / "nordic_additions.json"
STATUS = PUBLIC / "nordic_status.json"


def normalized_title(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^\w]+", " ", s, flags=re.UNICODE).strip()


def normalized_doi(s):
    return re.sub(r"^https?://(?:dx\.)?doi\.org/|^doi:\s*", "",
                  str(s or "").strip(), flags=re.I).lower().rstrip("/")


def load_json(path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def editorial_candidates():
    raw = load_json(PUBLIC / "bibliografiar.json")
    for item in raw["items"]:
        if item.get("origin") != "editorial":
            continue
        yield {
            "id": item["id"], "origin": "editorial",
            "title": item["title"], "year": item["year"],
            "doi": item.get("doi", ""), "authors": [item.get("authors", "")],
            "source_id": item.get("source_id", ""),
            "source_name": "Nordisk bibliografi",
            "source_url": item.get("url", ""),
            "kind": "editorial-candidate",
        }


def reconcile():
    works = load_json(PUBLIC / "publications.json")
    indexed_ids = {w["id"] for w in works}
    doi_index = defaultdict(set)
    title_index = defaultdict(set)
    for w in works:
        if d := normalized_doi(w.get("doi")):
            doi_index[d].add(w["id"])
        title_index[(normalized_title(w.get("title")), str(w.get("year")))].add(w["id"])

    candidates = list(editorial_candidates()) + load_json(ROOT / "data" / "nordic_imports.json")
    candidates.sort(key=lambda r: (r["origin"] if "origin" in r else "external", r["id"]))
    ids = set()
    audit = []
    new_candidates = []
    stage_doi = {}
    stage_title = defaultdict(list)
    link_map = defaultdict(list)
    for raw in candidates:
        cid = raw["id"]
        if cid in ids:
            raise ValueError("Source ID used twice: " + cid)
        ids.add(cid)
        title = str(raw.get("title") or "").strip()
        if not title:
            raise ValueError("Empty title: " + cid)
        year = str(raw.get("year") or "").strip()
        d = normalized_doi(raw.get("doi"))
        typed_id = raw.get("source_id", "")
        origin = raw.get("origin", "external")
        match = ""
        match_status = "new-candidate"
        reason = "No identical registered ID or DOI"
        if typed_id and typed_id in indexed_ids:
            match, match_status, reason = typed_id, "matched-id", "Exact OpenAlex work ID"
        elif d and len(doi_index[d]) == 1:
            match, match_status, reason = next(iter(doi_index[d])), "matched-doi", "Exact, unique DOI"
        elif d and len(doi_index[d]) > 1:
            match_status, reason = "ambiguous-doi", "DOI points to several OpenAlex records"
        elif title_index.get((normalized_title(title), year)):
            match_status = "possible-duplicate"
            reason = "Title and year coincide; author/manifestation check needed"
        if match:
            link_map[match].append(cid)
        else:
            if d and d in stage_doi:
                match_status = "duplicate-staging-doi"
                reason = "Same DOI as staging record " + stage_doi[d]
            elif d:
                stage_doi[d] = cid
            title_token = (normalized_title(title), year)
            if match_status == "new-candidate" and stage_title[title_token]:
                match_status = "possible-duplicate"
                reason = "Same title and year as another source record"
            stage_title[title_token].append(cid)

        audit.append({
            "id": cid,
            "source": raw.get("source", "editorial"),
            "title": title,
            "year": year,
            "doi": raw.get("doi", ""),
            "matched_openalex_id": match,
            "status": match_status,
            "reason": reason,
            "source_url": raw.get("source_url", ""),
        })
        if match or match_status == "duplicate-staging-doi":
            continue
        original_kind = raw.get("kind") or "unknown"
        entry = {
            "id": "nordic:" + cid,
            "origin": origin,
            "title": title,
            "year": int(year) if year.isdecimal() else None,
            "doi": raw.get("doi", ""),
            "authors": raw.get("authors") or [],
            "source": raw.get("source_name", "Nordisk bibliografi"),
            "source_country": raw.get("source_country", ""),
            "countries": [],
            "kind": original_kind,
            "citations": None,
            "topic": "",
            "theme": "",
            "oa_url": "",
            "source_url": raw.get("source_url", ""),
            "scope": "editorial-candidate" if origin == "editorial" else "repository-candidate",
            "review_status": "metadata-unreviewed",
            "duplicate_status": match_status,
            "pdf": "",
            "text": "",
            "license": "",
            "review_priority": "",
            "review_score": 0,
            "venue": raw.get("venue", ""),
        }
        new_candidates.append(entry)

    counts = Counter(r["status"] for r in audit)
    source_counts = Counter(r["source"] for r in audit)
    status = {
        "openalex_records": len(works),
        "source_records_total": len(candidates),
        "editorial_records": sum(c.get("origin") == "editorial" for c in candidates),
        "repository_records": sum(c.get("origin", "external") == "external" for c in candidates),
        "matched_exact": sum(v for k, v in counts.items() if k.startswith("matched-")),
        "unlinked_candidate_records": len(new_candidates),
        "possible_duplicate_records": counts["possible-duplicate"] + counts["ambiguous-doi"],
        "source_counts": dict(source_counts),
        "match_status_counts": dict(counts),
        "note": "Neither repository exports nor title matches imply verified Nordic design theory.",
    }
    PUBLIC.mkdir(parents=True, exist_ok=True)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(new_candidates, ensure_ascii=False,
                                 separators=(",", ":")) + "\n", encoding="utf-8")
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2,
                                 sort_keys=True) + "\n", encoding="utf-8")
    with AUDIT.open("w", encoding="utf-8", newline="") as fh:
        fields = ["id", "source", "title", "year", "doi",
                  "matched_openalex_id", "status", "reason", "source_url"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(audit)
    (PUBLIC / "source_links.json").write_text(
        json.dumps(dict(sorted(link_map.items())), ensure_ascii=False,
                   separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print("NORDIC_RECONCILED", json.dumps(status, ensure_ascii=False, sort_keys=True))
    return status


if __name__ == "__main__":
    reconcile()
