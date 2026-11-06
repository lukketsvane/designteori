#!/usr/bin/env python3
"""Import all metadata-only exports in imports/<source>/ in a reproducible order."""
from pathlib import Path
from import_norden import SOURCES, ROOT, DEST, add

EXTENSIONS = {".csv", ".ris", ".xml", ".json", ".jsonl", ".ndjson"}
INPUT = ROOT / "imports"

def main():
    paths = sorted(p for p in INPUT.glob("*/*") if p.is_file() and
                   p.parent.name in SOURCES and p.suffix.lower() in EXTENSIONS)
    totals = []
    for path in paths:
        n, count = add(path.parent.name, path)
        totals.append((path.as_posix(), n))
    if not paths and not DEST.exists():
        DEST.parent.mkdir(parents=True, exist_ok=True)
        DEST.write_text("[]\n", encoding="utf-8")
    print("INPUT_EXPORTS", len(paths), "IMPORTED", sum(x[1] for x in totals))
    for path, count in totals:
        print(path, count)

if __name__ == "__main__":
    main()
