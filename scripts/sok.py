#!/usr/bin/env python3
"""Søk i nordiske publikasjonsmetadata utan tunge analysebibliotek."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/data/publications.json"
ADDITIONS = ROOT / "docs/data/nordic_additions.json"


def search(term, kind="", country="", limit=20):
    rows = json.loads(INDEX.read_text(encoding="utf-8"))
    if ADDITIONS.exists():
        rows += json.loads(ADDITIONS.read_text(encoding="utf-8"))
    words = term.casefold().split()
    matches = []
    for row in rows:
        if kind and row.get("kind") != kind:
            continue
        if country and country not in row.get("countries", []):
            continue
        fields = [str(row.get("title") or ""), str(row.get("doi") or ""),
                  str(row.get("source") or "")] + list(row.get("authors") or [])
        if all(word in " ".join(fields).casefold() for word in words):
            matches.append(row)
    matches.sort(key=lambda row: (-(int(row.get("year") or 0)),
                                  str(row.get("title") or "")))
    return matches[:limit]


def main():
    parser = argparse.ArgumentParser(description="Søk i nordisk designteori")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--kind", default="")
    parser.add_argument("--country", choices=["", "NO", "SE", "DK", "FI", "IS"], default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit må vere positiv")
    rows = search(args.query, args.kind, args.country, args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row.get('year') or '?'}  {row.get('title')}  {row.get('doi') or row['id']}")


if __name__ == "__main__":
    main()
