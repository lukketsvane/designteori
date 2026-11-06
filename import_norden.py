#!/usr/bin/env python3
"""Import metadata exports from Nordic research catalogues without copying full text.

Supported exports: CSV, JSON/JSONL, RIS, Dublin Core/OAI-PMH XML.
Run locally with an export obtained from the named source. No network requests.
Unreviewed imports do not change OpenAlex counts or count as verified theory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "data" / "nordic_imports.json"
SOURCES = {
    "nva": ("Nasjonalt vitenarkiv", "NO"),
    "diva": ("DiVA", "SE"),
    "aalto": ("Aalto University", "FI"),
    "chalmers": ("Chalmers Research", "SE"),
    "kgl": ("Royal Danish Academy", "DK"),
    "iris": ("IRIS Iceland", "IS"),
    "skemman": ("Skemman", "IS"),
    "nordes": ("Nordes", ""),
    "cephad": ("CEPHAD", ""),
}
DOI = re.compile(r"10\.\d{4,9}/[^\s,;<>\"']+", re.I)
LETTERS = re.compile(r"[^a-z0-9]+", re.I)


def key(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return LETTERS.sub(" ", text.casefold()).strip()


def doi(value):
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    candidate = unquote(candidate).replace("doi:", "")
    match = DOI.search(candidate)
    if not match:
        return ""
    return match.group(0).rstrip(").,;]").lower()


def text(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "; ".join(v for x in value if (v := text(x)))
    if isinstance(value, dict):
        for k in ("eng", "en", "nb", "nn", "sv", "da", "fi", "is", "value",
                  "text", "name", "display_name", "title", "fullName", "label"):
            if k in value:
                val = text(value[k])
                if val:
                    return val
        return ""
    return str(value).strip() if value is not None else ""


def field(record, *paths):
    for path in paths:
        value = record
        for segment in path.split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(segment)
        if value is not None:
            result = text(value)
            if result:
                return result
    return ""


def date_year(record):
    raw = field(record, "year", "publicationYear", "publication_year",
                "issued.date-parts", "publicationDate.year", "publicationDate",
                "issued", "date", "PY", "Y1", "DC.date")
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b", raw)
    if not match:
        return None
    year = int(match.group(0))
    return year if year <= date.today().year + 1 else None


def record_authors(raw):
    if isinstance(raw, str):
        return [part.strip() for part in re.split(r"\s*;\s*|\s+\band\b\s+", raw) if part.strip()]
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("contributors") or raw.get("creators") or [raw]
    if not isinstance(raw, list):
        return []
    names = []
    for entry in raw:
        if isinstance(entry, dict):
            name = field(entry, "identity.name", "name", "fullName", "author.name",
                         "creator", "person.name", "display_name")
            if not name and (entry.get("family") or entry.get("given")):
                name = " ".join(filter(None, [text(entry.get("given")), text(entry.get("family"))]))
        else:
            name = text(entry)
        if name and name not in names:
            names.append(name)
    return names


def kind(value):
    t = key(re.sub(r"([a-z])([A-Z])", r"\1 \2", str(value or "")))
    if not t:
        return "unknown"
    if any(x in t for x in ("review article", "review paper", "review")):
        return "review"
    if any(x in t for x in ("conference", "proceedings", "paper in proceedings")):
        return "proceedings-article"
    if any(x in t for x in ("book chapter", "chapter in book", "chapter")):
        return "book-chapter"
    if any(x in t for x in ("journal article", "academic article", "peer reviewed article",
                            "article in journal", "periodical article", "research article")):
        return "article"
    if t in ("article", "journal", "j", "jour"):
        return "article"
    if any(x in t for x in ("thesis", "dissertation", "phd")):
        return "thesis"
    if t in ("book", "monograph", "book monograph"):
        return "book"
    return "unknown"


def iter_json(value):
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                yield entry
    elif isinstance(value, dict):
        for k in ("records", "resources", "results", "items", "publications", "data", "hits", "_embedded"):
            nested = value.get(k)
            if isinstance(nested, (list, dict)):
                if k == "hits" and isinstance(nested, dict) and "hits" in nested:
                    nested = nested["hits"]
                yield from iter_json(nested)
                return
        yield value


def read_ris(source):
    entry = {}
    for line in source.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9])\s+-\s+(.*)$", line)
        if not match:
            continue
        tag, value = match.groups()
        if tag == "ER":
            if entry:
                yield entry
            entry = {}
        elif tag in ("AU", "A1"):
            entry.setdefault("authors", []).append(value)
        else:
            entry[tag] = value
    if entry:
        yield entry


def read_xml(path):
    # No external entity expansion; only the metadata of records is read.
    tree = ET.parse(path)
    root = tree.getroot()
    for node in root.iter():
        if node.tag.split("}")[-1].lower() != "record":
            continue
        item = {}
        for el in node.iter():
            label = el.tag.split("}")[-1].lower()
            if label in ("title", "creator", "author", "date", "identifier",
                         "type", "source", "publisher", "language", "subject", "url"):
                val = (el.text or "").strip()
                if val:
                    item.setdefault(label, []).append(val)
            if label == "header":
                for sub in el:
                    if sub.tag.split("}")[-1].lower() == "identifier" and sub.text:
                        item["oai_identifier"] = sub.text.strip()
        if item.get("title"):
            yield {
                "title": item["title"][0], "authors": item.get("creator") or item.get("author") or [],
                "year": (item.get("date") or [""])[0],
                "doi": next((d for ident in item.get("identifier", []) if (d := doi(ident))), ""),
                "url": next((v for v in item.get("identifier", []) if v.startswith("https://")), ""),
                "id": item.get("oai_identifier", ""),
                "kind": (item.get("type") or [""])[0],
                "venue": (item.get("source") or item.get("publisher") or [""])[0],
            }


def read_records(path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            yield from csv.DictReader(fh)
    elif suffix in (".json", ".jsonl", ".ndjson"):
        if suffix == ".json":
            yield from iter_json(json.loads(path.read_text(encoding="utf-8-sig")))
        else:
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if line.strip():
                    yield from iter_json(json.loads(line))
    elif suffix == ".ris":
        yield from read_ris(path.read_text(encoding="utf-8-sig"))
    elif suffix == ".xml":
        yield from read_xml(path)
    else:
        raise ValueError("Use .csv, .json, .jsonl, .ndjson, .ris or .xml")


def normalize(row, source):
    title = field(row, "title", "display_name", "name", "name.eng", "name.en", "TI", "T1")
    if not title:
        return None
    year = date_year(row)
    authors = record_authors(row.get("authors") or row.get("contributors")
                             or row.get("creator") or row.get("creators")
                             or row.get("author") or row.get("AU") or row.get("A1"))
    d = doi(field(row, "doi", "DOI", "DO", "doiUrl", "identifiers.doi",
                  "identifiers.DOI", "identifier"))
    ident = field(row, "id", "identifier", "record_id", "resource_id", "uuid",
                  "handle", "oai_identifier", "accession_number", "AN")
    source_url = field(row, "url", "link", "handle", "permanentLink",
                       "landing_page_url", "UR", "URL", "links.self.href")
    if not source_url.startswith("https://"):
        source_url = ""
    if not ident:
        ident = d or hashlib.sha256(
            (key(title) + "|" + str(year) + "|" + key(authors[0] if authors else "")).encode()
        ).hexdigest()[:20]
    publication_type = kind(field(row, "kind", "type", "publicationType", "publication_type",
                                  "category.type", "TY"))
    if publication_type == "unknown":
        publication_type = {"JOUR": "article", "CHAP": "book-chapter", "BOOK": "book",
                            "CONF": "proceedings-article", "THES": "thesis"}.get(
                                field(row, "TY"), "unknown")
    return {
        "id": source + ":" + hashlib.sha256(ident.encode()).hexdigest()[:20],
        "source": source, "source_name": SOURCES[source][0],
        "source_country": SOURCES[source][1],
        "source_record_id": ident, "title": title, "authors": authors,
        "year": year, "doi": "https://doi.org/" + d if d else "",
        "kind": publication_type,
        "venue": field(row, "venue", "journal", "journalTitle", "publicationName",
                       "publication.name", "source", "JO", "JF", "T2"),
        "source_url": source_url,
        "status": "metadata-unreviewed",
        "affiliation_status": "not-verified",
    }


def add(source, input_path, dest=DEST):
    if source not in SOURCES:
        raise ValueError("Unsupported source: " + source)
    current = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else []
    indexed = {r["id"]: r for r in current}
    valid = 0
    for raw in read_records(input_path):
        if not isinstance(raw, dict):
            continue
        item = normalize(raw, source)
        if item:
            valid += 1
            indexed[item["id"]] = item
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(sorted(indexed.values(), key=lambda x: x["id"]),
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return valid, len(indexed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, choices=sorted(SOURCES))
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error("Export file not found")
    found, total = add(args.source, args.input)
    print(f"STAGED {found} from {args.source}; {total} metadata records in {DEST}")


if __name__ == "__main__":
    main()
