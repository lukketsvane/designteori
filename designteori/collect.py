"""Harvest and update the Nordic design research corpus (1900–present).

Combines:
1. OpenAlex primary corpus (1900–present, NO/SE/DK/FI/IS):
   - Complete runs of 17 flagship design theory & research venues
   - Complete runs of 6 dedicated Nordic design & architecture academies
   - Deep multilingual queries (English, Norwegian, Swedish, Danish, Finnish, Icelandic)
     including a dedicated pre-2000 historical pass (1900–1999)
   - Citation-frontier resolution (ingesting cited Nordic works + indexing global cited canon)
2. Nordic national & institutional archives (`imports/<source>/`, metadata only, no abstracts):
   - `nva` (Norway: Cristin / NVA)
   - `diva` (Sweden: DiVA portal)
   - `aalto` (Finland: Aaltodoc OAI-PMH & Finnish OA design venues)
   - `kgl` (Denmark: tidsskrift.dk / AAU / Danish design venues)
   - `iris` (Iceland: Skemman / Icelandic design records)
   - `nordes` (Nordic Design Research Conference & Design Research Society `10.21606`)
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
import shutil
import sqlite3
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from . import (
    IMPORTS_DIR,
    NORDIC_COUNTRIES,
    RAW_SQLITE,
    RAW_SQLITE_GZ,
    UNIFIED_SQLITE_GZ,
    USER_AGENT,
    doi_url,
    normalize_doi,
    now_iso,
    write_gzip_deterministic,
    write_json,
)

OPENALEX_API = "https://api.openalex.org/works"
NORDIC_SET = set(NORDIC_COUNTRIES)
TYPES_FILTER = "type:article|book|book-chapter|conference-paper|review|dissertation"
BASE_COUNTRY_FILTER = "authorships.countries:NO|SE|DK|FI|IS," + TYPES_FILTER
SELECT_FIELDS = (
    "id,doi,display_name,publication_year,publication_date,type,cited_by_count,"
    "authorships,abstract_inverted_index,referenced_works,primary_topic,keywords,"
    "primary_location,best_oa_location,locations,open_access,language"
)

PURE_DESIGN_VENUES = {
    "S2764463729",  # FormAkademisk
    "S152445846",   # Design Studies
    "S107659597",   # Design Issues
    "S4210216195",  # International Journal of Design
    "S4210189112",  # CoDesign
    "S153469747",   # The Design Journal
    "S2898472644",  # She Ji
    "S191448683",   # Journal of Design History
    "S1509497",     # Design and Culture
    "S4210222023",  # Journal of Design Research
    "S4210182550",  # Artifact
    "S4210173131",  # Design Science
    "S4210205958",  # Proceedings of the Design Society
    "S4210174351",  # Design Philosophy Papers
    "S207009260",   # Strategic Design Research Journal
    "S4210211686",  # Journal of Textile Design Research and Practice
}

DESIGN_VENUES_ALL = sorted(PURE_DESIGN_VENUES | {
    "S196057155",   # International Journal of Technology and Design Education
})

NORDIC_DESIGN_SCHOOLS = [
    "I135606841",   # Oslo School of Architecture and Design (AHO, NO)
    "I218177685",   # Konstfack (SE)
    "I893397424",   # Design School Kolding (DK)
    "I4210128030",  # Royal Danish Academy – Architecture, Design, Conservation (DK)
    "I30867006",    # Aarhus School of Architecture (DK)
    "I2799785105",  # Iceland University of the Arts (IS)
]

QUERIES_EN = [
    "design theory", "design research", "research through design", "design methods",
    "design methodology", "design philosophy", "design epistemology", "design aesthetics",
    "design history", "history of design", "design ethics", "design justice",
    "design thinking", "critical design", "speculative design", "participatory design",
    "co-design", "user centered design", "service design", "systemic design",
    "systems oriented design", "interaction design", "industrial design",
    "product design", "design education", "design practice", "sustainable design",
    "design anthropology", "design studies", "design processes", "design and innovation",
    "design cognition", "craft research", "textile design", "transition design",
    "more-than-human design", "scandinavian design", "nordic design",
]

QUERIES_NORDIC = [
    "designteori", "designforskning", "designforsking", "formgivning", "formgiving",
    "formgjeving", "brukskunst", "industridesign", "tjenestedesign", "tjänstedesign",
    "interaksjonsdesign", "interaktionsdesign", "brukermedvirkning", "brugerinddragelse",
    "muotoilu", "muotoilututkimus", "taideteollisuus", "hönnun",
]

TITLE_TERMS = re.compile(
    r"\b(?:design\w*|formgiv\w*|formgjev\w*|gestaltn\w*|brukskunst\w*|"
    r"tjenestedesign\w*|tjänstedesign\w*|muotoilu\w*|taideteollis\w*|hönnun\w*|"
    r"co-design\w*|codesign\w*|arkitektur\w*|architectur\w*)\b",
    re.I,
)

CLINICAL_NOISE = re.compile(
    r"\b(?:trial design|study design|design of (?:a|the) (?:cohort|trial|study)|"
    r"clinical trial protocol|randomi[sz]ed controlled trial|primer design|drug design|"
    r"vaccine design|protein design|oligonucleotide|microstrip|antenna array|"
    r"power electronic|inverter|filter design|circuit design|controller design)\b",
    re.I,
)


def http_get(url: str, *, accept: str = "application/json", timeout: int = 35, retries: int = 3) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except HTTPError as err:
            if err.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise
            wait = err.headers.get("Retry-After", "")
            if wait.isdecimal() and int(wait) > 30:
                raise RuntimeError(f"Rate limit quota reached (Retry-After={wait}s)") from err
            time.sleep(float(wait) if wait.isdecimal() else min(15.0, 2.0 ** (attempt + 1)))
        except (URLError, TimeoutError, OSError):
            if attempt == retries - 1:
                raise
            time.sleep(min(15.0, 1.5 * (attempt + 1)))
    raise RuntimeError("Unreachable retry loop")


def ensure_raw_sqlite(path: Path = RAW_SQLITE) -> Path:
    path = Path(path)
    if path.exists():
        setup_schema(path)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = path.with_suffix(".sqlite.gz")
    source_gz = archive if archive.exists() else (UNIFIED_SQLITE_GZ if UNIFIED_SQLITE_GZ.exists() else None)
    if source_gz is not None:
        tmp = path.with_suffix(".restoring")
        with gzip.open(source_gz, "rb") as src, tmp.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        conn = sqlite3.connect(tmp)
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        if ok != "ok":
            tmp.unlink(missing_ok=True)
            raise RuntimeError("Corrupt SQLite archive: " + ok)
        os.replace(tmp, path)
    setup_schema(path)
    return path


def setup_schema(path: Path = RAW_SQLITE) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS works (
      id TEXT PRIMARY KEY, doi TEXT, title TEXT, year INTEGER, publication_date TEXT,
      kind TEXT, abstract TEXT, citations INTEGER, source TEXT, source_id TEXT,
      language TEXT, oa_url TEXT, countries TEXT, topic TEXT,
      in_scope INTEGER NOT NULL, decision TEXT, raw_json TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_work_year ON works(year);
    CREATE INDEX IF NOT EXISTS idx_work_doi ON works(doi);
    CREATE TABLE IF NOT EXISTS discoveries(
      id TEXT, query TEXT, page INTEGER, PRIMARY KEY(id,query));
    CREATE TABLE IF NOT EXISTS references_all(
      citing_id TEXT, cited_id TEXT, PRIMARY KEY(citing_id,cited_id));
    CREATE INDEX IF NOT EXISTS idx_ref_cited ON references_all(cited_id);
    CREATE TABLE IF NOT EXISTS authorships(
      work_id TEXT, author_id TEXT, author_name TEXT, institution_id TEXT,
      institution_name TEXT, country TEXT, author_position TEXT);
    CREATE INDEX IF NOT EXISTS idx_author_work ON authorships(work_id);
    CREATE TABLE IF NOT EXISTS query_log(
      query TEXT, page INTEGER, url TEXT, total_hits INTEGER,
      returned INTEGER, fetched_at TEXT, error TEXT, PRIMARY KEY(query,page));
    CREATE TABLE IF NOT EXISTS cited_canon(
      id TEXT PRIMARY KEY, doi TEXT, title TEXT, year INTEGER, kind TEXT,
      authors TEXT, source TEXT, global_citations INTEGER,
      nordic_citing_count INTEGER, countries TEXT, oa_url TEXT
    );
    """)
    conn.commit()
    conn.close()


def archive_raw_sqlite(path: Path = RAW_SQLITE, archive: Path = RAW_SQLITE_GZ) -> None:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    if ok != "ok":
        raise RuntimeError(ok)
    public_tmp = path.with_name("public_metadata_tmp.sqlite")
    shutil.copy2(path, public_tmp)
    try:
        safe = sqlite3.connect(public_tmp)
        safe.execute("UPDATE works SET abstract='', raw_json='{}'")
        safe.execute("DROP TABLE IF EXISTS works_fts")
        safe.execute("CREATE VIRTUAL TABLE works_fts USING fts5(title,abstract,content='works',content_rowid='rowid')")
        safe.execute("INSERT INTO works_fts(rowid,title,abstract) SELECT rowid,title,abstract FROM works")
        safe.commit()
        safe.execute("VACUUM")
        safe.close()
        write_gzip_deterministic(public_tmp, archive)
    finally:
        public_tmp.unlink(missing_ok=True)


def abstract_from_index(idx: object) -> str:
    if not idx or not isinstance(idx, dict):
        return ""
    pairs = [(pos, word) for word, positions in idx.items()
             if isinstance(positions, list) for pos in positions if isinstance(pos, int)]
    return " ".join(word for _, word in sorted(pairs))


def best_oa_link(w: dict) -> str:
    oa = w.get("open_access") or {}
    candidates = []
    for loc in [w.get("best_oa_location"), w.get("primary_location")] + (w.get("locations") or []):
        if isinstance(loc, dict) and loc.get("is_oa"):
            if loc.get("pdf_url"):
                candidates.append(loc["pdf_url"])
            if loc.get("landing_page_url"):
                candidates.append(loc["landing_page_url"])
    if oa.get("oa_url"):
        candidates.append(oa["oa_url"])
    for raw in candidates:
        s = str(raw or "").strip()
        if s.startswith("http://urn.kb.se/") or s.startswith("http://hdl.handle.net/"):
            s = "https://" + s[7:]
        if s.startswith("https://"):
            return s
    return str(oa.get("oa_url") or "")


def evaluate_scope(title: str, cs: list[str], source_id: str) -> tuple[int, str]:
    short_source = (source_id or "").rsplit("/", 1)[-1]
    in_design_venue = short_source in PURE_DESIGN_VENUES
    has_term = bool(TITLE_TERMS.search(title or ""))
    noise = bool(CLINICAL_NOISE.search(title or ""))
    include = int(bool(cs) and (has_term or in_design_venue) and not noise)
    if include:
        reason = ("Nordic affiliation and dedicated design venue"
                  if in_design_venue and not has_term
                  else "Nordic affiliation and design-related title")
    else:
        reason = "Needs manual eligibility review"
    return include, reason


def ingest_work(conn: sqlite3.Connection, w: dict, query_label: str, page: int,
                *, fallback_countries: list[str] | None = None) -> bool:
    wid = (w.get("id") or "").rsplit("/", 1)[-1]
    if not wid or not wid.startswith("W"):
        return False
    aus = w.get("authorships") or []
    cs = sorted((
        {c for a in aus for c in (a.get("countries") or []) if c}
        | {i.get("country_code") for a in aus for i in (a.get("institutions") or []) if i.get("country_code")}
    ) & NORDIC_SET)
    if not cs and fallback_countries:
        cs = sorted(set(fallback_countries) & NORDIC_SET)
    if not cs:
        return False
    title = (w.get("display_name") or "").strip() or "(untitled)"
    loc = w.get("primary_location") or {}
    source = loc.get("source") or {}
    source_id = source.get("id") or ""
    include, decision = evaluate_scope(title, cs, source_id)
    topic = w.get("primary_topic") or {}
    oa_link = best_oa_link(w)
    slim_raw = {
        k: w.get(k) for k in (
            "id", "doi", "display_name", "publication_year", "type",
            "cited_by_count", "primary_topic", "keywords", "primary_location",
            "best_oa_location", "locations", "open_access", "language",
        ) if k in w
    }
    record = (
        wid, w.get("doi"), title, w.get("publication_year"), w.get("publication_date"),
        w.get("type"), abstract_from_index(w.get("abstract_inverted_index")),
        w.get("cited_by_count", 0), source.get("display_name"), source_id,
        w.get("language"), oa_link, json.dumps(cs), topic.get("display_name"),
        include, decision, json.dumps(slim_raw, ensure_ascii=False, separators=(",", ":")),
    )
    conn.execute("""
        INSERT INTO works VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
          doi=COALESCE(excluded.doi, works.doi),
          title=excluded.title,
          year=COALESCE(excluded.year, works.year),
          publication_date=COALESCE(excluded.publication_date, works.publication_date),
          kind=COALESCE(excluded.kind, works.kind),
          abstract=CASE WHEN length(excluded.abstract)>length(COALESCE(works.abstract,''))
                        THEN excluded.abstract ELSE works.abstract END,
          citations=MAX(COALESCE(excluded.citations,0), COALESCE(works.citations,0)),
          source=COALESCE(excluded.source, works.source),
          source_id=COALESCE(excluded.source_id, works.source_id),
          language=COALESCE(excluded.language, works.language),
          oa_url=CASE WHEN excluded.oa_url<>'' THEN excluded.oa_url ELSE works.oa_url END,
          countries=excluded.countries,
          topic=COALESCE(excluded.topic, works.topic),
          in_scope=excluded.in_scope,
          decision=excluded.decision,
          raw_json=excluded.raw_json
    """, record)
    conn.execute("INSERT OR IGNORE INTO discoveries VALUES (?,?,?)", (wid, query_label, page))
    refs = [(wid, r.rsplit("/", 1)[-1]) for r in (w.get("referenced_works") or []) if r]
    if refs:
        conn.executemany("INSERT OR IGNORE INTO references_all VALUES (?,?)", refs)
    if aus:
        conn.execute("DELETE FROM authorships WHERE work_id=?", (wid,))
        rows = []
        for a in aus:
            author = a.get("author") or {}
            insts = a.get("institutions") or [{}]
            for i in insts:
                rows.append((
                    wid,
                    (author.get("id") or "").rsplit("/", 1)[-1],
                    author.get("display_name"),
                    (i.get("id") or "").rsplit("/", 1)[-1],
                    i.get("display_name"),
                    i.get("country_code"),
                    a.get("author_position"),
                ))
        conn.executemany("INSERT INTO authorships VALUES (?,?,?,?,?,?,?)", rows)
    return True


def fetch_cursor_stream(conn: sqlite3.Connection, filter_expr: str, label: str,
                        *, search: str = "", max_pages: int = 45,
                        fallback_countries: list[str] | None = None) -> int:
    added = 0
    for page in range(1, min(max_pages, 49) + 1):
        params = {"filter": filter_expr, "per_page": 200, "page": page, "select": SELECT_FIELDS}
        if search:
            params["search"] = search
        url = OPENALEX_API + "?" + urlencode(params)
        try:
            payload = json.loads(http_get(url).decode("utf-8"))
        except Exception as exc:
            conn.execute(
                "INSERT OR REPLACE INTO query_log VALUES (?,?,?,?,?,?,?)",
                (label, page, url, 0, 0, now_iso(), f"{type(exc).__name__}: {str(exc)[:160]}"),
            )
            conn.commit()
            print("OPENALEX_ERR", label, page, exc, flush=True)
            break
        results = payload.get("results") or []
        total = (payload.get("meta") or {}).get("count", 0)
        for w in results:
            if ingest_work(conn, w, label, page, fallback_countries=fallback_countries):
                added += 1
        conn.execute(
            "INSERT OR REPLACE INTO query_log VALUES (?,?,?,?,?,?,?)",
            (label, page, url, total, len(results), now_iso(), None),
        )
        conn.commit()
        print(f"OA_FETCH {label} p={page} got={len(results)} total={total}", flush=True)
        if not results or len(results) < 200 or page * 200 >= total:
            break
        time.sleep(0.15)
    return added


def refresh_existing_scope(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, title, countries, source_id FROM works").fetchall()
    updates = []
    for wid, title, countries_json, source_id in rows:
        try:
            cs = json.loads(countries_json or "[]")
        except json.JSONDecodeError:
            cs = []
        inc, dec = evaluate_scope(title or "", cs, source_id or "")
        updates.append((inc, dec, wid))
    conn.executemany("UPDATE works SET in_scope=?, decision=? WHERE id=?", updates)
    conn.commit()


def resolve_reference_frontier(conn: sqlite3.Connection, *, min_citing: int = 3, max_ids: int = 3500) -> dict:
    rows = conn.execute("""
        SELECT r.cited_id, COUNT(DISTINCT r.citing_id) AS cnt
        FROM references_all r
        JOIN works w ON w.id = r.citing_id
        LEFT JOIN works existing ON existing.id = r.cited_id
        WHERE existing.id IS NULL AND r.cited_id LIKE 'W%'
        GROUP BY r.cited_id
        HAVING cnt >= ?
        ORDER BY cnt DESC, r.cited_id ASC
        LIMIT ?
    """, (min_citing, max_ids)).fetchall()
    citing_counts = {wid: cnt for wid, cnt in rows}
    target_ids = list(citing_counts)
    ingested_nordic = 0
    canon_indexed = 0
    for idx in range(0, len(target_ids), 50):
        batch = target_ids[idx:idx + 50]
        filt = "openalex:" + "|".join(batch)
        url = OPENALEX_API + "?" + urlencode({"filter": filt, "per_page": 100, "select": SELECT_FIELDS})
        try:
            payload = json.loads(http_get(url).decode("utf-8"))
        except Exception as exc:
            print("FRONTIER_ERR", idx, exc, flush=True)
            continue
        for w in payload.get("results") or []:
            wid = (w.get("id") or "").rsplit("/", 1)[-1]
            aus = w.get("authorships") or []
            all_cs = sorted({c for a in aus for c in (a.get("countries") or []) if c})
            nordic_cs = sorted(set(all_cs) & NORDIC_SET)
            title = (w.get("display_name") or "").strip()
            loc = w.get("primary_location") or {}
            src = (loc.get("source") or {}).get("display_name") or ""
            src_id = (loc.get("source") or {}).get("id") or ""
            authors_str = "; ".join(
                (a.get("author") or {}).get("display_name") or ""
                for a in aus[:12] if (a.get("author") or {}).get("display_name")
            )
            conn.execute("""
                INSERT OR REPLACE INTO cited_canon VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                wid, w.get("doi") or "", title, w.get("publication_year"),
                w.get("type") or "", authors_str, src, w.get("cited_by_count", 0),
                citing_counts.get(wid, 0), json.dumps(all_cs), best_oa_link(w),
            ))
            canon_indexed += 1
            inc, _ = evaluate_scope(title, nordic_cs, src_id)
            if nordic_cs and (inc or citing_counts.get(wid, 0) >= 6):
                if ingest_work(conn, w, "reference_frontier", 1):
                    ingested_nordic += 1
        conn.commit()
        time.sleep(0.15)
    return {"checked": len(target_ids), "ingested_nordic": ingested_nordic, "canon_indexed": canon_indexed}


def harvest_openalex(*, pages_en: int = 5, pages_nordic: int = 5, end_year: int = 2026) -> dict:
    db_path = ensure_raw_sqlite()
    conn = sqlite3.connect(db_path)

    # 1. Complete runs of all 17 flagship design venues (Nordic-affiliated, 1900-end_year)
    venue_filter = (
        f"primary_location.source.id:{'|'.join(DESIGN_VENUES_ALL)},"
        f"publication_year:1900-{end_year},{BASE_COUNTRY_FILTER}"
    )
    fetch_cursor_stream(conn, venue_filter, "venues:flagship-design-nordic", max_pages=40)

    # Also complete run of FormAkademisk (OsloMet's Nordic design research journal, even where OpenAlex omits country metadata)
    fa_filter = f"primary_location.source.id:S2764463729,publication_year:1900-{end_year},{TYPES_FILTER}"
    fetch_cursor_stream(conn, fa_filter, "venue:formakademisk-complete", max_pages=10, fallback_countries=["NO"])

    # 2. Dedicated Nordic design & architecture academies (1900-end_year)
    school_filter = (
        f"authorships.institutions.id:{'|'.join(NORDIC_DESIGN_SCHOOLS)},"
        f"publication_year:1900-{end_year},{TYPES_FILTER}"
    )
    fetch_cursor_stream(conn, school_filter, "institutions:nordic-design-schools", max_pages=40)

    # 3. Historical pre-2000 Nordic design research & theory (1900-1999)
    hist_queries = [
        "design", "participatory design", "industrial design", "scandinavian design",
        "design history", "design theory", "design methods", "system design",
        "architecture", "formgivning", "brukskunst", "muotoilu",
    ]
    for q in hist_queries:
        filt = f"publication_year:1900-1999,{BASE_COUNTRY_FILTER}"
        fetch_cursor_stream(conn, filt, f"hist1900_1999:{q}", search=f'"{q}"', max_pages=4)

    # 4. Deep contemporary & modern queries (2000-end_year) — English + 5 Nordic languages
    for q in QUERIES_EN:
        filt = f"publication_year:2000-{end_year},{BASE_COUNTRY_FILTER}"
        fetch_cursor_stream(conn, filt, f"en:{q}", search=f'"{q}"', max_pages=pages_en)

    for q in QUERIES_NORDIC:
        filt = f"publication_year:1900-{end_year},{BASE_COUNTRY_FILTER}"
        fetch_cursor_stream(conn, filt, f"nordic_lang:{q}", search=f'"{q}"', max_pages=pages_nordic)

    # 5. Resolve heavily cited reference frontier (pre-2000 & 2000-2026 classics!)
    frontier_stats = resolve_reference_frontier(conn, min_citing=3, max_ids=3500)

    refresh_existing_scope(conn)
    total_works = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
    in_scope = conn.execute("SELECT COUNT(*) FROM works WHERE in_scope=1").fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM references_all").fetchone()[0]
    canon = conn.execute("SELECT COUNT(*) FROM cited_canon").fetchone()[0]
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    archive_raw_sqlite(db_path)
    summary = {
        "works": total_works,
        "in_scope": in_scope,
        "reference_edges": edges,
        "cited_canon": canon,
        "frontier": frontier_stats,
    }
    print("OPENALEX_SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def _crossref_item_to_record(item: dict) -> dict | None:
    titles = item.get("title") or []
    title = (titles[0] if titles else "").strip()
    if not title:
        return None
    d = normalize_doi(item.get("DOI"))
    authors = []
    for a in item.get("author") or []:
        name = " ".join(filter(None, [a.get("given"), a.get("family")])).strip() or (a.get("name") or "").strip()
        if name:
            authors.append(name)
    year = None
    for k in ("published-print", "published-online", "issued", "created"):
        parts = ((item.get(k) or {}).get("date-parts") or [[]])[0]
        if parts and isinstance(parts[0], int):
            year = parts[0]
            break
    containers = item.get("container-title") or []
    venue = (containers[0] if containers else "") or (item.get("publisher") or "")
    url = str(item.get("URL") or "")
    for link in item.get("link") or []:
        u = str((link or {}).get("URL") or "")
        if u.startswith("https://") and "api.elsevier" not in u and "api.wiley" not in u:
            url = u
            break
    return {
        "id": d or title[:60],
        "title": title,
        "authors": authors,
        "year": year,
        "doi": doi_url(d),
        "kind": item.get("type") or "article",
        "venue": venue,
        "url": url if url.startswith("https://") else doi_url(d),
    }


def harvest_nordes_crossref() -> int:
    records = {}
    for query in ("nordes", "nordic", "scandinavian", "denmark", "sweden", "norway", "finland", "iceland", "co-design", "participatory"):
        for offset in (0, 200, 400):
            url = f"https://api.crossref.org/prefixes/10.21606/works?query={quote(query)}&rows=200&offset={offset}"
            try:
                data = json.loads(http_get(url).decode("utf-8"))
            except Exception as exc:
                print("NORDES_ERR", query, offset, exc, flush=True)
                break
            items = ((data.get("message") or {}).get("items")) or []
            for it in items:
                d = normalize_doi(it.get("DOI"))
                is_nordes = "nordes" in d or "nordes" in json.dumps(it.get("container-title") or []).lower()
                affil_blob = json.dumps(it.get("author") or []).lower()
                is_nordic_affil = any(w in affil_blob for w in (
                    "norway", "sweden", "denmark", "finland", "iceland",
                    "aalto", "oslo", "kolding", "konstfack", "chalmers", "umeå", "umea",
                    "copenhagen", "gothenburg", "göteborg", "malmö", "malmo", "ntnu",
                    "helsinki", "lapland", "aarhus", "aalborg", "lund", "borås", "boras", "reykjavik",
                ))
                if is_nordes or is_nordic_affil:
                    rec = _crossref_item_to_record(it)
                    if rec and rec["id"] not in records:
                        records[rec["id"]] = rec
            if len(items) < 200:
                break
            time.sleep(0.2)
    out = IMPORTS_DIR / "nordes" / "nordes_drs.json"
    write_json(out, sorted(records.values(), key=lambda x: x["id"]))
    print("ARCHIVE_NORDES", len(records), flush=True)
    return len(records)


def harvest_nva_cristin() -> int:
    records = {}
    terms = [
        "designteori", "designforskning", "designforsking", "formgivning", "formgiving",
        "industridesign", "tjenestedesign", "interaksjonsdesign", "brukermedvirkning",
        "design theory", "design research", "research through design", "participatory design",
        "service design", "co-design", "systemic design", "sustainable design", "critical design",
    ]
    # Also harvest AHO (institution 190 / lookup dynamically)
    inst_ids = []
    for inst_q in ("arkitektur- og designhøgskolen", "kunsthøgskolen i oslo"):
        try:
            raw = json.loads(http_get("https://api.cristin.no/v2/institutions?" + urlencode({"name": inst_q})).decode("utf-8"))
            for entry in raw[:3]:
                cid = str(entry.get("cristin_institution_id") or "")
                if cid and entry.get("country") == "NO":
                    inst_ids.append(cid)
        except Exception:
            pass
    for inst_id in inst_ids:
        for page in range(1, 8):
            url = "https://api.cristin.no/v2/results?" + urlencode({"institution": inst_id, "per_page": 200, "page": page, "lang": "en"})
            try:
                items = json.loads(http_get(url).decode("utf-8"))
            except Exception:
                break
            if not isinstance(items, list) or not items:
                break
            for it in items:
                cid = str(it.get("cristin_result_id") or "")
                title_obj = it.get("title") or {}
                title = (title_obj.get("en") or title_obj.get("nb") or title_obj.get("nn") or next(iter(title_obj.values()), "") if isinstance(title_obj, dict) else str(title_obj)).strip()
                if not cid or not title:
                    continue
                links = it.get("links") or []
                d = ""
                full_url = f"https://app.cristin.no/results/show.jsf?id={cid}"
                for lnk in links:
                    u = str((lnk or {}).get("url") or "")
                    if "doi.org/" in u:
                        d = normalize_doi(u)
                    elif u.startswith("https://") and lnk.get("url_type") in ("FULLTEKST", "ARKIV"):
                        full_url = u
                contribs = it.get("contributors") or {}
                preview = contribs.get("preview") if isinstance(contribs, dict) else (contribs if isinstance(contribs, list) else [])
                authors = [
                    " ".join(filter(None, [p.get("first_name"), p.get("surname")])).strip()
                    for p in (preview or []) if isinstance(p, dict)
                ]
                cat = ((it.get("category") or {}).get("name") or {})
                kind_label = cat.get("en") if isinstance(cat, dict) else str(cat or "article")
                records[cid] = {
                    "id": "cristin:" + cid,
                    "title": title,
                    "authors": [a for a in authors if a],
                    "year": it.get("year_published"),
                    "doi": doi_url(d),
                    "kind": kind_label,
                    "venue": (it.get("journal") or {}).get("name") or "",
                    "url": full_url,
                }
            if len(items) < 200:
                break
            time.sleep(0.15)

    for term in terms:
        for page in range(1, 5):
            url = "https://api.cristin.no/v2/results?" + urlencode({"title": term, "per_page": 200, "page": page, "lang": "en"})
            try:
                items = json.loads(http_get(url).decode("utf-8"))
            except Exception:
                break
            if not isinstance(items, list) or not items:
                break
            for it in items:
                cid = str(it.get("cristin_result_id") or "")
                title_obj = it.get("title") or {}
                title = (title_obj.get("en") or title_obj.get("nb") or title_obj.get("nn") or next(iter(title_obj.values()), "") if isinstance(title_obj, dict) else str(title_obj)).strip()
                if not cid or not title or CLINICAL_NOISE.search(title):
                    continue
                links = it.get("links") or []
                d = ""
                full_url = f"https://app.cristin.no/results/show.jsf?id={cid}"
                for lnk in links:
                    u = str((lnk or {}).get("url") or "")
                    if "doi.org/" in u:
                        d = normalize_doi(u)
                    elif u.startswith("https://") and lnk.get("url_type") in ("FULLTEKST", "ARKIV"):
                        full_url = u
                contribs = it.get("contributors") or {}
                preview = contribs.get("preview") if isinstance(contribs, dict) else []
                authors = [
                    " ".join(filter(None, [p.get("first_name"), p.get("surname")])).strip()
                    for p in (preview or []) if isinstance(p, dict)
                ]
                cat = ((it.get("category") or {}).get("name") or {})
                kind_label = cat.get("en") if isinstance(cat, dict) else str(cat or "article")
                records[cid] = {
                    "id": "cristin:" + cid,
                    "title": title,
                    "authors": [a for a in authors if a],
                    "year": it.get("year_published"),
                    "doi": doi_url(d),
                    "kind": kind_label,
                    "venue": (it.get("journal") or {}).get("name") or "",
                    "url": full_url,
                }
            if len(items) < 200:
                break
            time.sleep(0.15)
    out = IMPORTS_DIR / "nva" / "cristin_design.json"
    write_json(out, sorted(records.values(), key=lambda x: x["id"]))
    print("ARCHIVE_NVA_CRISTIN", len(records), flush=True)
    return len(records)


def harvest_diva() -> int:
    records = {}
    terms = [
        "designteori", "designforskning", "tjänstedesign", "industridesign",
        "interaktionsdesign", "formgivning", "design theory", "research through design",
        "participatory design", "service design", "co-design", "critical design",
        "speculative design", "design history", "Konstfack",
    ]
    for term in terms:
        aq = quote(json.dumps([{"freeText": term}]))
        url = (
            "https://www.diva-portal.org/smash/export.jsf?format=csvall2&addFilename=false"
            f"&aq=[{aq}]&aqe=[]&aq2=[[]]&onlyFullText=false&noOfRows=250"
            "&sortOrder=dateIssued_sort_desc&sortOrder2=title_sort_asc"
        )
        try:
            raw = http_get(url, accept="text/csv,*/*", timeout=45).decode("utf-8-sig", "replace")
        except Exception as exc:
            print("DIVA_ERR", term, exc, flush=True)
            continue
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            pid = (row.get("PID") or "").strip()
            title = (row.get("Title") or "").strip()
            pub_type = (row.get("PublicationType") or "").strip()
            # Exclude student bachelor/master theses; keep peer-reviewed research, books, chapters, PhD dissertations
            if "student thesis" in pub_type.lower():
                continue
            if not pid or not title or CLINICAL_NOISE.search(title):
                continue
            names_raw = (row.get("Name") or "").strip()
            # DiVA Name format: "Ehn, Pelle (Inst...); Löwgren, Jonas (Inst...)"
            authors = []
            for chunk in names_raw.split(";"):
                clean_name = re.sub(r"\s*\[.*?\]|\s*\(.*?\)", "", chunk).strip()
                if clean_name and clean_name not in authors:
                    authors.append(clean_name)
            d = normalize_doi(row.get("DOI"))
            nbn = (row.get("NBN") or "").strip()
            fulltext_links = (row.get("FullTextLink") or row.get("Urls") or "").strip()
            best_url = ""
            for token in re.split(r"[\s;]+", fulltext_links):
                if token.startswith("http://"):
                    token = "https://" + token[7:]
                if token.startswith("https://"):
                    best_url = token
                    break
            if not best_url and nbn:
                best_url = f"https://urn.kb.se/resolve?urn={quote(nbn, safe=':-')}"
            if not best_url:
                best_url = f"https://www.diva-portal.org/smash/record.jsf?pid=diva2:{pid}"
            year_str = (row.get("Year") or "").strip()
            records[pid] = {
                "id": f"diva2:{pid}",
                "title": title,
                "authors": authors[:15],
                "year": int(year_str) if year_str.isdigit() else None,
                "doi": doi_url(d),
                "kind": pub_type or "article",
                "venue": (row.get("Journal") or row.get("HostPublication") or row.get("Publisher") or "").strip(),
                "url": best_url,
            }
        time.sleep(0.25)
    out = IMPORTS_DIR / "diva" / "diva_design.json"
    write_json(out, sorted(records.values(), key=lambda x: x["id"]))
    print("ARCHIVE_DIVA", len(records), flush=True)
    return len(records)


def harvest_finnish_danish_icelandic() -> dict:
    # 1. Finland: Aaltodoc OAI-PMH (filtered to design/muotoilu records, no abstracts) + Finnish OA Crossref prefixes
    aalto_records = {}
    for prefix in ("10.33350", "10.23995", "10.30673", "10.33134", "10.21435"):
        for q in ("design", "muotoilu", "architecture", "art", "craft"):
            url = f"https://api.crossref.org/prefixes/{prefix}/works?query={quote(q)}&rows=150"
            try:
                items = ((json.loads(http_get(url).decode("utf-8")).get("message") or {}).get("items")) or []
                for it in items:
                    rec = _crossref_item_to_record(it)
                    if rec and TITLE_TERMS.search(rec["title"]) and not CLINICAL_NOISE.search(rec["title"]):
                        aalto_records[rec["id"]] = rec
            except Exception:
                pass
            time.sleep(0.15)

    # Also harvest Aaltodoc OAI-PMH recent pages matching design/muotoilu
    token = None
    for _ in range(6):
        oai_url = (
            "https://aaltodoc.aalto.fi/server/oai/request?verb=ListRecords&resumptionToken=" + quote(token)
            if token else
            "https://aaltodoc.aalto.fi/server/oai/request?verb=ListRecords&metadataPrefix=oai_dc"
        )
        try:
            xml_bytes = http_get(oai_url, accept="application/xml,text/xml,*/*", timeout=35)
            root = ET.fromstring(xml_bytes)
        except Exception:
            break
        for node in root.iter():
            if node.tag.split("}")[-1] != "record":
                continue
            titles, creators, dates, idents, types, subjects = [], [], [], [], [], []
            oai_id = ""
            for el in node.iter():
                tag = el.tag.split("}")[-1].lower()
                val = (el.text or "").strip()
                if not val:
                    continue
                if tag == "identifier" and val.startswith("oai:"):
                    oai_id = val
                elif tag == "title":
                    titles.append(val)
                elif tag == "creator":
                    creators.append(val)
                elif tag == "date":
                    dates.append(val)
                elif tag == "identifier":
                    idents.append(val)
                elif tag == "type":
                    types.append(val)
                elif tag == "subject":
                    subjects.append(val)
            title = titles[0] if titles else ""
            kind_blob = " ".join(types).lower()
            if not title or "master" in kind_blob or "bachelor" in kind_blob:
                continue
            subj_blob = " ".join(titles + subjects)
            if not TITLE_TERMS.search(subj_blob) or CLINICAL_NOISE.search(title):
                continue
            d = next(( x for raw in idents if (x := normalize_doi(raw)) ), "")
            u = next(( ("https://" + raw[7:] if raw.startswith("http://") else raw)
                       for raw in idents if raw.startswith(("https://", "http://urn.fi/", "http://hdl.handle.net/")) ), "")
            ym = re.search(r"\b(19\d{2}|20\d{2})\b", " ".join(dates))
            key_id = oai_id or d or title[:60]
            aalto_records[key_id] = {
                "id": key_id,
                "title": title,
                "authors": creators[:12],
                "year": int(ym.group(1)) if ym else None,
                "doi": doi_url(d),
                "kind": types[0] if types else "article",
                "venue": "Aaltodoc / Aalto University",
                "url": u,
            }
        rt_el = next((el for el in root.iter() if el.tag.split("}")[-1] == "resumptionToken"), None)
        token = (rt_el.text or "").strip() if rt_el is not None else ""
        if not token:
            break
        time.sleep(0.2)

    write_json(IMPORTS_DIR / "aalto" / "aaltodoc_design.json", sorted(aalto_records.values(), key=lambda x: x["id"]))

    # 2. Denmark: Royal Danish Library tidsskrift.dk (`10.7146`) & Aalborg Open (`10.54337`)
    dk_records = {}
    for prefix in ("10.7146", "10.54337"):
        for q in ("design", "formgivning", "arkitektur", "codesign", "participatory", "artifact", "brugerinddragelse"):
            url = f"https://api.crossref.org/prefixes/{prefix}/works?query={quote(q)}&rows=200"
            try:
                items = ((json.loads(http_get(url).decode("utf-8")).get("message") or {}).get("items")) or []
                for it in items:
                    rec = _crossref_item_to_record(it)
                    if rec and TITLE_TERMS.search(rec["title"] + " " + rec["venue"]) and not CLINICAL_NOISE.search(rec["title"]):
                        dk_records[rec["id"]] = rec
            except Exception:
                pass
            time.sleep(0.15)
    write_json(IMPORTS_DIR / "kgl" / "danish_design.json", sorted(dk_records.values(), key=lambda x: x["id"]))

    # 3. Iceland: Crossref works matching Iceland / Reykjavik / Listaháskóli + design/hönnun
    is_records = {}
    for q in ("hönnun", "design iceland", "listaháskóli", "icelandic design", "reykjavik design"):
        url = f"https://api.crossref.org/works?query={quote(q)}&rows=120"
        try:
            items = ((json.loads(http_get(url).decode("utf-8")).get("message") or {}).get("items")) or []
            for it in items:
                blob = json.dumps(it).lower()
                if not any(k in blob for k in ("iceland", "ísland", "reykjavik", "reykjavík", "listaháskóli", "skemman", ".is/")):
                    continue
                rec = _crossref_item_to_record(it)
                if rec and TITLE_TERMS.search(rec["title"]) and not CLINICAL_NOISE.search(rec["title"]):
                    is_records[rec["id"]] = rec
        except Exception:
            pass
        time.sleep(0.15)
    write_json(IMPORTS_DIR / "iris" / "iceland_design.json", sorted(is_records.values(), key=lambda x: x["id"]))
    counts = {"aalto": len(aalto_records), "kgl": len(dk_records), "iris": len(is_records)}
    print("ARCHIVE_FI_DK_IS", counts, flush=True)
    return counts


def harvest_all_nordic_archives() -> dict:
    return {
        "nordes": harvest_nordes_crossref(),
        "nva": harvest_nva_cristin(),
        "diva": harvest_diva(),
        **harvest_finnish_danish_icelandic(),
    }
