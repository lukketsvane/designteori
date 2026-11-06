#!/usr/bin/env python3
"""Nettverksfritt SQLite-søk i både primærkorpus og uavklarte kjeldelag.

Bruk: python sok_korpus.py "participatory design" --layer all --limit 20
Resultata er bibliografiske registreringar, ikkje verifiserte funn.
"""
from __future__ import annotations

import argparse
import gzip
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "data" / "designteori_hovuddatabase.sqlite.gz"
VALID_LAYERS = ("all", "openalex", "nordic", "historical")


def match_query(text: str) -> str:
    words = re.findall(r"[^\W_]+", text, flags=re.UNICODE)[:16]
    if not words:
        raise ValueError("Søkjeteksten må innehalde minst eitt ord")
    return " AND ".join('"' + w.replace('"', "") + '"' for w in words)


def search(conn: sqlite3.Connection, query: str, layer: str = "all",
           limit: int = 20) -> list[dict]:
    if layer not in VALID_LAYERS:
        raise ValueError("Ugyldig kjeldelag")
    if not 1 <= limit <= 500:
        raise ValueError("Limit må vere mellom 1 og 500")
    q = match_query(query)
    conn.row_factory = sqlite3.Row
    found = []
    if layer in ("all", "openalex"):
        rows = conn.execute("""
            SELECT w.id,w.title,w.year,w.doi,'openalex' AS layer,
                   CASE WHEN w.in_scope=1 THEN 'automatic-title-inclusion'
                        ELSE 'awaiting-eligibility-review' END AS scope
            FROM works_fts f JOIN works w ON w.rowid=f.rowid
            WHERE works_fts MATCH ?
            ORDER BY bm25(works_fts),w.id LIMIT ?
        """, (q, limit)).fetchall()
        found.extend(dict(r) for r in rows)
    if layer != "openalex":
        where = " AND c.source_layer=?" if layer != "all" else ""
        params = (q, layer, limit) if layer != "all" else (q, limit)
        rows = conn.execute("""
            SELECT c.id,c.title,c.year,c.doi,c.source_layer AS layer,c.scope
            FROM source_candidates_fts f
            JOIN source_candidates c ON c.rowid=f.rowid
            WHERE source_candidates_fts MATCH ?
        """ + where + """
            ORDER BY bm25(source_candidates_fts),c.id LIMIT ?
        """, params).fetchall()
        found.extend(dict(r) for r in rows)
    # FTS rank er ikkje direkte samanliknbar på tvers av to ulike indeksar.
    # Når begge kjeldelag er valde, vert treff ordna etter publikasjonsår.
    if layer == "all":
        found.sort(key=lambda r: (-(r["year"] or 0), r["title"], r["id"]))
    return found[:limit]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", help="Ord i tittel eller registrerte forfattarnamn")
    p.add_argument("--layer", choices=VALID_LAYERS, default="all")
    p.add_argument("--limit", type=int, default=20)
    args = p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        sqlite_path = Path(tmp) / "catalog.sqlite"
        with gzip.open(ARCHIVE, "rb") as source, sqlite_path.open("wb") as dest:
            shutil.copyfileobj(source, dest)
        conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
        try:
            results = search(conn, args.query, args.layer, args.limit)
        finally:
            conn.close()
    for w in results:
        print(f'{w["year"] or "u.å."} | {w["layer"]} | '
              f'{w["title"]} | {w["doi"] or w["id"]} | {w["scope"]}')
    print(f"{len(results)} søkjetreff; registreringsstatus er ikkje fagleg verifikasjon.")


if __name__ == "__main__":
    main()
