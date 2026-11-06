"""Provenance-aware reconciliation across OpenAlex and Nordic national/institutional archives.

Maintains strict epistemic separation between:
- Primary OpenAlex Nordic-affiliated records (`automatic-title-inclusion` vs `awaiting-eligibility-review`)
- Unlinked Nordic institutional & national archive candidates (`repository-candidate`:
  Cristin/NVA, DiVA, Aaltodoc, KGL/tidsskrift.dk, IRIS/Skemman, Nordes/DRS)
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from . import (
    DOCS_DATA_DIR,
    IMPORTS_DIR,
    PDF_DIR,
    RAW_SQLITE,
    REPO_RAW_BASE,
    doi_url,
    normalize_doi,
    normalize_title,
    now_iso,
    read_json,
    write_csv_rows,
    write_json,
)
from .collect import ensure_raw_sqlite

NORDIC_SOURCES = {
    "nva": ("Nasjonalt vitenarkiv / Cristin", "NO"),
    "diva": ("DiVA", "SE"),
    "aalto": ("Aalto University / Aaltodoc", "FI"),
    "kgl": ("Det Kongelige Akademi / Danske arkiv", "DK"),
    "iris": ("IRIS / Skemman Island", "IS"),
    "nordes": ("Nordes / Design Research Society", ""),
}

POSITIVE_SIGNALS = {
    "design-theory": r"\b(?:design theory|theor(?:y|ies) of design|foundational design|design philosophy|design epistemology|designerly ways|design knowledge|design inquiry|designteori\w*)\b",
    "practice-research": r"\b(?:research through design|research by design|design research|practice(?:[- ]based|[- ]led) research|design science research|research in design|designforsk\w*|muotoilututkimus\w*)\b",
    "methods": r"\b(?:design methods?|design methodology|design process(?:es)?|participatory design|co[- ]design|codesign|design thinking|user[- ]cent(?:e)?red design|brukermedvirk\w*|brugerinddrag\w*)\b",
    "history": r"\b(?:design history|history of design|historiography of design|design discourse|scandinavian design|nordic design|brukskunst\w*)\b",
    "ethics-aesthetics": r"\b(?:design ethics|ethics of design|design aesthetics|aesthetics of design|critical design|speculative design|design justice|formgiv\w*|formgjev\w*|gestaltn\w*)\b",
    "systems-service": r"\b(?:systemic design|systems[- ]oriented design|service design|design for sustainab|ecological design|sustainable design|circular design|transition design|tjenestedesign\w*|tjänstedesign\w*)\b",
    "making": r"\b(?:design practice|design judgement|craft research|design cognition|design activity|artefact theory|artifact theory|materiality|textile design|muotoilu\w*|hönnun\w*)\b",
}

DESIGN_VENUE_KEYWORDS = (
    "design studies", "design issues", "the design journal", "formakademisk",
    "international journal of design", "design science", "co-design", "codesign",
    "nordes", "design research society", "iasdr", "artifact", "the design society",
    "she ji", "journal of design history", "design and culture", "design philosophy",
    "strategic design", "textile design", "journal of design research",
)

NEGATIVE_AMBIGUITY = re.compile(
    r"\b(?:inverter|power electronic|seismic|microstrip|antenna array|microgrid|"
    r"wind turbine|lead[- ]acid battery|biosensor|neural network architecture|"
    r"photovoltaic|cadmium|filter design|circuit design|genetic algorithm|"
    r"primer design|drug design|protein design|clinical trial)\b",
    re.I,
)


def parse_bibtex_entries(content: str):
    """Pure BibTeX parser utility supporting nested braces and quoted values."""
    pattern = re.compile(r"@([a-zA-Z]+)\s*\{\s*([^,{}]+)\s*,", re.M)
    cursor = 0
    for m in pattern.finditer(content):
        if m.start() < cursor:
            continue
        depth, in_quote, escaped, pos = 1, False, False, m.end()
        while pos < len(content):
            c = content[pos]
            if escaped:
                escaped = False
                pos += 1
                continue
            if c == "\\":
                escaped = True
                pos += 1
                continue
            if c == '"':
                in_quote = not in_quote
                pos += 1
                continue
            if not in_quote:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
            pos += 1
        if depth != 0:
            raise ValueError("Unclosed BibTeX entry " + m.group(2))
        cursor = pos + 1
        body = content[m.end():pos]
        chunks, d2, q2, e2, start = [], 0, False, False, 0
        for ix, ch in enumerate(body):
            if e2:
                e2 = False
                continue
            if ch == "\\":
                e2 = True
                continue
            if ch == '"':
                q2 = not q2
                continue
            if not q2:
                if ch == "{":
                    d2 += 1
                elif ch == "}":
                    d2 -= 1
                elif ch == "," and d2 == 0:
                    chunks.append(body[start:ix])
                    start = ix + 1
        chunks.append(body[start:])
        fields = {}
        for chunk in chunks:
            fm = re.match(r"\s*([A-Za-z][\w-]*)\s*=\s*(.*?)\s*$", chunk, re.S)
            if not fm:
                continue
            raw = fm.group(2)
            if len(raw) > 1 and ((raw[0] == "{" and raw[-1] == "}") or (raw[0] == '"' and raw[-1] == '"')):
                raw = raw[1:-1]
            fields[fm.group(1).lower()] = raw.strip()
        yield m.group(1).lower(), m.group(2).strip(), fields


def _normalize_import_kind(raw: str) -> str:
    t = normalize_title(re.sub(r"([a-z])([A-Z])", r"\1 \2", str(raw or "")))
    if not t:
        return "unknown"
    if "review" in t:
        return "review"
    if any(x in t for x in ("conference", "proceedings", "paper in proceedings")):
        return "proceedings-article"
    if "chapter" in t:
        return "book-chapter"
    if any(x in t for x in ("article", "journal", "tidsskrift")):
        return "article"
    if any(x in t for x in ("thesis", "dissertation", "phd", "doctoral")):
        return "thesis"
    if any(x in t for x in ("book", "monograph", "anthology")):
        return "book"
    return "unknown"


def _iter_import_records(path: Path):
    suf = path.suffix.lower()
    if suf == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as fh:
            yield from csv.DictReader(fh)
    elif suf == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, list):
            for x in data:
                if isinstance(x, dict):
                    yield x
        elif isinstance(data, dict):
            for k in ("records", "resources", "results", "items", "publications", "data"):
                if isinstance(data.get(k), list):
                    for x in data[k]:
                        if isinstance(x, dict):
                            yield x
                    return
            yield data
    elif suf in (".jsonl", ".ndjson"):
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                obj = json.loads(line)
                if isinstance(obj, dict):
                    yield obj
    elif suf == ".xml":
        root = ET.parse(path).getroot()
        for node in root.iter():
            if node.tag.split("}")[-1].lower() != "record":
                continue
            vals = defaultdict(list)
            oai_id = ""
            for el in node.iter():
                tag = el.tag.split("}")[-1].lower()
                txt = (el.text or "").strip()
                if txt and tag in ("title", "creator", "author", "date", "identifier", "type", "source", "publisher", "url"):
                    vals[tag].append(txt)
                if tag == "header":
                    for sub in el:
                        if sub.tag.split("}")[-1].lower() == "identifier" and sub.text:
                            oai_id = sub.text.strip()
            if vals.get("title"):
                yield {
                    "id": oai_id,
                    "title": vals["title"][0],
                    "authors": vals.get("creator") or vals.get("author") or [],
                    "year": (vals.get("date") or [""])[0],
                    "doi": next((d for raw in vals.get("identifier", []) if (d := normalize_doi(raw))), ""),
                    "url": next((u for u in vals.get("identifier", []) if u.startswith("https://")), ""),
                    "kind": (vals.get("type") or [""])[0],
                    "venue": (vals.get("source") or vals.get("publisher") or [""])[0],
                }


def stage_nordic_imports(imports_dir: Path = IMPORTS_DIR) -> list[dict]:
    indexed = {}
    max_year = date.today().year + 1
    for source in sorted(NORDIC_SOURCES):
        folder = imports_dir / source
        if not folder.is_dir():
            continue
        for file in sorted(folder.iterdir()):
            if file.suffix.lower() not in (".csv", ".json", ".jsonl", ".ndjson", ".xml"):
                continue
            for row in _iter_import_records(file):
                title = str(row.get("title") or row.get("display_name") or row.get("name") or "").strip()
                if not title:
                    continue
                raw_authors = row.get("authors") or row.get("creator") or row.get("author") or []
                if isinstance(raw_authors, str):
                    authors = [p.strip() for p in re.split(r"\s*;\s*|\s+\band\b\s+", raw_authors) if p.strip()]
                elif isinstance(raw_authors, list):
                    authors = [str(x.get("name") if isinstance(x, dict) else x).strip() for x in raw_authors if x]
                else:
                    authors = []
                ym = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(row.get("year") or row.get("date") or row.get("publicationYear") or ""))
                year = int(ym.group(1)) if ym and int(ym.group(1)) <= max_year else None
                d = normalize_doi(row.get("doi") or row.get("DOI") or "")
                raw_id = str(row.get("id") or row.get("identifier") or d or "").strip()
                if not raw_id:
                    raw_id = hashlib.sha256(f"{normalize_title(title)}|{year}|{authors[0] if authors else ''}".encode()).hexdigest()[:20]
                s_url = str(row.get("url") or row.get("source_url") or row.get("link") or "").strip()
                if s_url.startswith(("http://urn.kb.se/", "http://hdl.handle.net/", "http://urn.fi/")):
                    s_url = "https://" + s_url[7:]
                if not s_url.startswith("https://"):
                    s_url = ""
                cid = f"{source}:{hashlib.sha256(raw_id.encode()).hexdigest()[:20]}"
                indexed[cid] = {
                    "id": cid,
                    "origin": "external",
                    "source": source,
                    "source_name": NORDIC_SOURCES[source][0],
                    "source_country": NORDIC_SOURCES[source][1],
                    "source_record_id": raw_id,
                    "title": title,
                    "authors": [a for a in authors if a],
                    "year": year,
                    "doi": doi_url(d),
                    "kind": _normalize_import_kind(row.get("kind") or row.get("type") or ""),
                    "venue": str(row.get("venue") or row.get("journal") or row.get("source") or "").strip(),
                    "source_url": s_url,
                    "status": "metadata-unreviewed",
                    "affiliation_status": "not-verified",
                }
    return sorted(indexed.values(), key=lambda x: x["id"])


def build_triage_and_atlas(conn: sqlite3.Connection) -> tuple[dict, dict]:
    citation_in = Counter()
    for (cid,) in conn.execute("""
        SELECT r.cited_id FROM references_all r
        JOIN works w ON w.id=r.citing_id
        JOIN works v ON v.id=r.cited_id
        WHERE r.citing_id != r.cited_id
    """):
        citation_in[cid] += 1

    triage_catalog = {}
    for wid, doi, title, year, source, topic, kind, selected in conn.execute(
        "SELECT id, doi, title, year, source, topic, kind, in_scope FROM works"
    ):
        t = (title or "").casefold()
        s = (source or "").casefold()
        signals = [tag for tag, pat in POSITIVE_SIGNALS.items() if re.search(pat, t)]
        score = 5
        reasons = []
        if signals:
            score += 38 + min(17, 6 * (len(signals) - 1))
            reasons.extend(signals)
        if any(v in s for v in DESIGN_VENUE_KEYWORDS):
            score += 25
            reasons.append("design-venue-keyword")
        if selected:
            score += 7
            reasons.append("title-or-venue-gate")
        if citation_in[wid] >= 3:
            score += min(15, 2 * citation_in[wid])
            reasons.append("internal-nordic-citations")
        if NEGATIVE_AMBIGUITY.search(t):
            score -= 22
            reasons.append("technical-design-ambiguity")
        score = max(0, min(100, score))
        priority = "high" if score >= 60 else "medium" if score >= 35 else "low"
        triage_catalog[wid] = {
            "review_priority": priority,
            "priority_score": score,
            "keyword_categories": ";".join(signals),
            "signals": ";".join(reasons),
        }
    write_json(DOCS_DATA_DIR / "triage.json", triage_catalog, compact=True)

    works_map = {
        r[0]: {"id": r[0], "title": r[1], "year": r[2], "citations": r[3] or 0, "in_scope": r[4], "source": r[5]}
        for r in conn.execute("SELECT id, title, year, citations, in_scope, source FROM works")
    }
    context = {wid: {"authors": [], "cites": [], "cited_by": []} for wid in works_map}
    author_works = defaultdict(set)
    inst_works = defaultdict(set)
    author_name = {}
    inst_name = {}
    inst_country = {}
    affiliations = defaultdict(lambda: defaultdict(dict))

    for work_id, author_id, author, inst_id, inst, country, _ in conn.execute(
        "SELECT work_id, author_id, author_name, institution_id, institution_name, country, author_position FROM authorships ORDER BY rowid"
    ):
        if work_id not in works_map:
            continue
        aid = author_id or f"unresolved:{work_id}:{author or 'Unknown'}"
        author_name.setdefault(aid, author or "Ukjend")
        author_works[aid].add(work_id)
        rec = affiliations[work_id][aid]
        if "name" not in rec:
            rec["id"] = aid
            rec["name"] = author or "Ukjend"
            rec["institutions"] = []
        if inst or inst_id:
            iid = inst_id or f"unresolved-inst:{inst or 'Unknown'}:{country or ''}"
            inst_name.setdefault(iid, inst or "Ikkje namngjeven institusjon")
            if country and not inst_country.get(iid):
                inst_country[iid] = country
            inst_works[iid].add(work_id)
            aff = {"id": iid, "name": inst or "Ikkje namngjeven institusjon", "country": country or ""}
            if aff not in rec["institutions"]:
                rec["institutions"].append(aff)

    for wid, by_author in affiliations.items():
        context[wid]["authors"] = list(by_author.values())

    internal_edges = 0
    for citing, cited in conn.execute("""
        SELECT r.citing_id, r.cited_id FROM references_all r
        JOIN works w ON w.id=r.citing_id
        JOIN works v ON v.id=r.cited_id
        ORDER BY r.citing_id, r.cited_id
    """):
        if citing == cited:
            continue
        context[citing]["cites"].append(cited)
        context[cited]["cited_by"].append(citing)
        internal_edges += 1
    write_json(DOCS_DATA_DIR / "work_context.json", context, compact=True)

    author_rows = []
    for aid, wids in author_works.items():
        author_rows.append({
            "id": aid,
            "name": author_name[aid],
            "works": len(wids),
            "automatically_title_included": sum(works_map[x]["in_scope"] for x in wids),
            "countries": sorted({
                aff["country"] for wid in wids
                for aff in affiliations[wid][aid]["institutions"] if aff["country"]
            }),
            "institutions": sorted({
                aff["name"] for wid in wids
                for aff in affiliations[wid][aid]["institutions"] if aff["name"]
            }),
            "work_ids": sorted(wids),
            "openalex_citation_sum_on_snapshot_works": sum(works_map[x]["citations"] for x in wids),
        })
    author_rows.sort(key=lambda x: (-x["automatically_title_included"], -x["works"], x["name"]))
    write_json(DOCS_DATA_DIR / "authors.json", {"count": len(author_rows), "items": author_rows}, compact=True)

    inst_rows = []
    for iid, wids in inst_works.items():
        inst_rows.append({
            "id": iid,
            "name": inst_name[iid],
            "country": inst_country.get(iid, ""),
            "works": len(wids),
            "automatically_title_included": sum(works_map[x]["in_scope"] for x in wids),
            "work_ids": sorted(wids),
        })
    inst_rows.sort(key=lambda x: (-x["automatically_title_included"], -x["works"], x["name"]))
    write_json(DOCS_DATA_DIR / "institutions.json", {"count": len(inst_rows), "items": inst_rows}, compact=True)

    canon_rows = []
    has_canon = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cited_canon'").fetchone()
    if has_canon:
        for r in conn.execute("""
            SELECT id, doi, title, year, kind, authors, source, global_citations, nordic_citing_count, countries, oa_url
            FROM cited_canon ORDER BY nordic_citing_count DESC, global_citations DESC LIMIT 1000
        """):
            try:
                cs = json.loads(r[9] or "[]")
            except json.JSONDecodeError:
                cs = []
            canon_rows.append({
                "id": r[0], "doi": r[1] or "", "title": r[2] or "", "year": r[3],
                "kind": r[4] or "", "authors": r[5] or "", "source": r[6] or "",
                "global_citations": r[7] or 0, "nordic_citing_count": r[8] or 0,
                "countries": cs, "oa_url": r[10] or "",
                "in_primary_corpus": r[0] in works_map,
            })
    write_json(DOCS_DATA_DIR / "cited_canon.json", {"count": len(canon_rows), "items": canon_rows}, compact=True)

    return triage_catalog, {"internal_edges": internal_edges, "authors": len(author_rows), "institutions": len(inst_rows)}


def build_primary_catalog(conn: sqlite3.Connection, triage: dict) -> list[dict]:
    authors_by_work = defaultdict(list)
    for wid, name in conn.execute("SELECT work_id, author_name FROM authorships ORDER BY rowid"):
        if name and name not in authors_by_work[wid]:
            authors_by_work[wid].append(name)

    repo_pdfs = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
    docs = []
    country_counts = Counter()
    kind_counts = Counter()
    year_counts = Counter()

    for r in conn.execute("""
        SELECT id, doi, title, year, kind, citations, source, countries, topic, oa_url, in_scope, language
        FROM works ORDER BY year DESC, citations DESC, id
    """):
        wid, doi, title, year, kname, citations, source, country_json, topic, oa_url, in_scope, lang = r
        try:
            coun = json.loads(country_json or "[]")
        except json.JSONDecodeError:
            coun = []
        if not isinstance(coun, list):
            coun = []
        country_counts.update(set(coun))
        kind_counts[kname or "?"] += 1
        year_counts[str(year)] += 1
        oa_clean = str(oa_url or "")
        if oa_clean.startswith(("http://urn.kb.se/", "http://hdl.handle.net/", "http://urn.fi/")):
            oa_clean = "https://" + oa_clean[7:]
        if not oa_clean.startswith("https://"):
            oa_clean = ""
        tri = triage.get(wid, {})
        docs.append({
            "id": wid,
            "title": title or "",
            "year": year,
            "doi": doi or "",
            "authors": authors_by_work[wid],
            "source": source or "",
            "countries": coun,
            "kind": kname or "",
            "citations": citations or 0,
            "topic": topic or "",
            "theme": (tri.get("keyword_categories") or "").split(";")[0],
            "oa_url": oa_clean,
            "language": lang or "",
            "scope": "automatic-title-inclusion" if in_scope else "awaiting-eligibility-review",
            "pdf": f"{REPO_RAW_BASE}/{repo_pdfs[wid]['file']}" if wid in repo_pdfs else "",
            "license": repo_pdfs.get(wid, {}).get("license", "") if wid in repo_pdfs else "",
            "review_priority": tri.get("review_priority", ""),
            "review_score": tri.get("priority_score", 0),
            "keyword_categories": tri.get("keyword_categories", ""),
        })

    write_json(DOCS_DATA_DIR / "publications.json", docs, compact=True)
    write_json(DOCS_DATA_DIR / "stats.json", {
        "generated_at": now_iso(),
        "metadata_source": "OpenAlex (1900–2026 Nordic design corpus: flagship venues, academies, multilingual queries & citation frontier)",
        "total": len(docs),
        "automatic_title_inclusion": sum(x["scope"] == "automatic-title-inclusion" for x in docs),
        "manual_review_queue": sum(x["scope"] == "awaiting-eligibility-review" for x in docs),
        "article_records": kind_counts.get("article", 0),
        "review_records": kind_counts.get("review", 0),
        "local_pdf": sum(bool(x["pdf"]) for x in docs),
        "high_priority_for_manual_review": sum(x["review_priority"] == "high" for x in docs),
        "country_memberships": dict(country_counts),
        "kinds": dict(kind_counts),
        "year": dict(year_counts),
    })
    pub_fields = [
        "id", "doi", "title", "year", "authors", "source", "countries", "kind",
        "citations", "topic", "theme", "oa_url", "scope", "license", "pdf",
        "review_priority", "review_score", "keyword_categories",
    ]
    write_csv_rows(DOCS_DATA_DIR / "publications.csv", pub_fields, [
        {k: (", ".join(v) if isinstance(v, list) else v) for k, v in row.items() if k in pub_fields}
        for row in docs
    ])
    return docs


def reconcile_candidate_layers(works: list[dict], staged_imports: list[dict]) -> list[dict]:
    indexed_ids = {w["id"] for w in works}
    doi_index = defaultdict(set)
    title_index = defaultdict(set)
    for w in works:
        if d := normalize_doi(w.get("doi")):
            doi_index[d].add(w["id"])
        title_index[(normalize_title(w.get("title")), str(w.get("year")))].add(w["id"])

    repo_pdfs = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
    candidates = sorted(staged_imports, key=lambda r: r["id"])
    nordic_additions = []
    stage_doi = {}
    stage_title = defaultdict(list)
    link_map = defaultdict(list)
    status_counts = Counter()
    source_counts = Counter()

    for raw in candidates:
        cid = raw["id"]
        src = raw.get("source", "external")
        source_counts[src] += 1
        title = str(raw.get("title") or "").strip()
        year = str(raw.get("year") or "").strip()
        d = normalize_doi(raw.get("doi"))
        if not title:
            status_counts["missing-title"] += 1
            continue
        match, mstatus = "", "new-candidate"
        if d and len(doi_index[d]) == 1:
            match, mstatus = next(iter(doi_index[d])), "matched-doi"
        elif d and len(doi_index[d]) > 1:
            mstatus = "ambiguous-doi"
        elif title_index.get((normalize_title(title), year)):
            mstatus = "possible-duplicate"

        if match:
            link_map[match].append(cid)
            status_counts[mstatus] += 1
            continue

        if d and d in stage_doi:
            status_counts["duplicate-staging-doi"] += 1
            continue
        if d:
            stage_doi[d] = cid
        tok = (normalize_title(title), year)
        if mstatus == "new-candidate" and stage_title[tok]:
            mstatus = "possible-duplicate"
        stage_title[tok].append(cid)
        status_counts[mstatus] += 1

        nc_id = "nordic:" + cid
        nordic_additions.append({
            "id": nc_id,
            "origin": "external",
            "title": title,
            "year": int(year) if year.isdecimal() else None,
            "doi": raw.get("doi", ""),
            "authors": raw.get("authors") or [],
            "source": raw.get("source_name", "Nordisk arkiv"),
            "source_country": raw.get("source_country", ""),
            "countries": [raw["source_country"]] if raw.get("source_country") else [],
            "kind": raw.get("kind") or "unknown",
            "citations": None,
            "topic": "",
            "theme": "",
            "oa_url": raw.get("source_url", ""),
            "source_url": raw.get("source_url", ""),
            "scope": "repository-candidate",
            "review_status": "metadata-unreviewed",
            "duplicate_status": mstatus,
            "pdf": f"{REPO_RAW_BASE}/{repo_pdfs[nc_id]['file']}" if nc_id in repo_pdfs else "",
            "license": repo_pdfs.get(nc_id, {}).get("license", "") if nc_id in repo_pdfs else "",
            "review_priority": "",
            "review_score": 0,
            "venue": raw.get("venue", ""),
        })

    nordic_status = {
        "openalex_records": len(works),
        "source_records_total": len(candidates),
        "matched_exact": sum(v for k, v in status_counts.items() if k.startswith("matched-")),
        "unlinked_candidate_records": len(nordic_additions),
        "possible_duplicate_records": status_counts["possible-duplicate"] + status_counts["ambiguous-doi"],
        "source_counts": dict(source_counts),
        "match_status_counts": dict(status_counts),
    }
    write_json(DOCS_DATA_DIR / "nordic_additions.json", nordic_additions, compact=True)
    write_json(DOCS_DATA_DIR / "nordic_status.json", nordic_status, sort_keys=True)
    write_json(DOCS_DATA_DIR / "source_links.json", dict(sorted(link_map.items())), compact=True)
    return nordic_additions


def export_unified_csv_and_coverage(works: list[dict], nordic: list[dict]) -> dict:
    layers = {
        "openalex_primary_1900_2026": works,
        "nordic_national_and_institutional_archives": nordic,
    }
    tables = {}
    doi_rows = defaultdict(list)
    for lname, rows in layers.items():
        kinds = Counter(w.get("kind") or "unknown" for w in rows)
        decades = Counter(str((int(w["year"]) // 10) * 10) + "s" for w in rows if str(w.get("year") or "").isdigit())
        tables[lname] = {
            "searchable_registrations": len(rows),
            "with_doi": sum(bool(normalize_doi(w.get("doi"))) for w in rows),
            "with_authors": sum(bool(w.get("authors")) for w in rows),
            "with_year": sum(bool(w.get("year")) for w in rows),
            "with_repo_pdf": sum(bool(w.get("pdf")) for w in rows),
            "with_open_access_url": sum(bool(w.get("oa_url")) for w in rows),
            "kinds": dict(sorted(kinds.items())),
            "decades": dict(sorted(decades.items())),
        }
        for w in rows:
            if d := normalize_doi(w.get("doi")):
                doi_rows[d].append({"layer": lname, "id": w["id"]})

    shared = {k: v for k, v in doi_rows.items() if len(v) > 1}
    base_scopes = Counter(w.get("scope") for w in works)
    quality = {
        "schema_version": 3,
        "openalex_partial_search": len(works),
        "openalex_title_gate": dict(sorted(base_scopes.items())),
        "nordic_unlinked_candidates": len(nordic),
        "total_searchable_rows_all_layers": len(works) + len(nordic),
        "coverage_by_layer": tables,
        "cross_layer_or_within_layer_possible_doi_duplicates": {
            "duplicate_doi_keys": len(shared),
            "registrations": sum(len(v) for v in shared.values()),
        },
        "manual_article_eligibility_checks_completed": 0,
    }
    write_json(DOCS_DATA_DIR / "corpus_quality.json", quality, sort_keys=True)

    unified_rows = []
    for layer_key, rows in (("openalex", works), ("nordic", nordic)):
        for w in rows:
            unified_rows.append({
                "id": w["id"],
                "layer": layer_key,
                "status": w.get("scope", ""),
                "title": w.get("title") or "",
                "year": w.get("year") or "",
                "authors": "; ".join(w.get("authors") or []) if isinstance(w.get("authors"), list) else str(w.get("authors") or ""),
                "kind": w.get("kind") or "",
                "doi": w.get("doi") or "",
                "source": w.get("source") or "",
                "countries": "; ".join(w.get("countries") or []),
                "citations": "" if w.get("citations") is None else w.get("citations"),
                "pdf": w.get("pdf") or "",
                "oa_url": w.get("oa_url") or "",
            })
    unified_rows.sort(key=lambda r: (-(int(r["year"]) if str(r["year"]).isdigit() else 0), r["layer"], r["id"]))
    write_csv_rows(DOCS_DATA_DIR / "korpus.csv", [
        "id", "layer", "status", "title", "year", "authors",
        "kind", "doi", "source", "countries", "citations", "pdf", "oa_url"
    ], unified_rows)
    return quality


def run_reconciliation(db_path: Path = RAW_SQLITE) -> tuple[list[dict], list[dict]]:
    ensure_raw_sqlite(db_path)
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        staged = stage_nordic_imports()
        triage, _ = build_triage_and_atlas(conn)
        works = build_primary_catalog(conn, triage)
    finally:
        conn.close()
    nordic = reconcile_candidate_layers(works, staged)
    export_unified_csv_and_coverage(works, nordic)
    return works, nordic
