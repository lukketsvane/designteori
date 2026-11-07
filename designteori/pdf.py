"""Lawful Open Access PDF discovery, retrieval, cache audit, and rights-aware catalog."""
from __future__ import annotations

import csv
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from http.client import HTTPException
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from . import (
    DOCS_DATA_DIR,
    PDF_DIR,
    PRIVATE_CACHE,
    REPO_BLOB_BASE,
    REPO_RAW_BASE,
    USER_AGENT,
    normalize_doi,
    now_iso,
    read_json,
    write_csv_rows,
    write_json,
)

HOST_DENY = ("sci-hub", "libgen", "annas-archive", "z-library", "silkstart.s3.amazonaws.com")
BOILERPLATE_PDF_RE = re.compile(
    r"(?:dataprotection|data[-_]protection|tietosuoja|privacy[-_]?policy|cookie[-_]?policy|terms[-_]and[-_]conditions)",
    re.I,
)
MAX_REDIRECTS = 8
OA_DOI_PREFIXES = (
    "10.7577/", "10.21606/", "10.3384/", "10.7146/", "10.54337/",
    "10.5617/", "10.5324/", "10.15845/", "10.23865/", "10.24834/",
    "10.33350/", "10.23995/", "10.30673/", "10.33134/", "10.16993/",
    "10.21435/", "10.1016/j.sheji.", "10.1017/pds.", "10.1017/dsi.",
    "10.3390/", "10.3389/", "10.1371/", "10.1186/",
)
QUEUE_FIELDS = (
    "id", "doi", "title", "year", "kind", "source", "oa_url",
    "scope", "priority", "archived", "candidate_status",
)


def candidate_https_url(link: object) -> str:
    text = str(link or "").strip()
    if text.lower().startswith("http://"):
        try:
            u = urlsplit(text)
            host = (u.hostname or "").lower().strip(".")
            if host and not u.username and not u.password and u.port in (None, 80):
                rebuilt = "https://" + host + (u.path or "")
                if u.query:
                    rebuilt += "?" + u.query
                if u.fragment:
                    rebuilt += "#" + u.fragment
                return rebuilt
        except (ValueError, TypeError):
            return text
    return text


def allowed_url(link: object) -> bool:
    try:
        u = urlsplit(str(link or ""))
        host = (u.hostname or "").lower().strip(".")
        if u.scheme != "https" or not host or u.username or u.password or u.port not in (None, 443):
            return False
        if host in ("localhost", "metadata.google.internal") or host.endswith((".local", ".internal", ".localhost")):
            return False
        if any(block in host for block in HOST_DENY):
            return False
        if not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host or ".." in host:
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            return True
    except (ValueError, TypeError):
        return False


def safe_public_link(url: object) -> bool:
    if not allowed_url(url):
        return False
    query = urlsplit(str(url)).query.lower()
    secrets = (
        "token=", "access_token=", "api_key=", "apikey=", "signature=",
        "x-amz-", "x-goog-", "authorization=", "credential=", "session=", "expires=",
    )
    return not any(term in query for term in secrets)


def public_dns(host: str | None) -> bool:
    if not host:
        return False
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses:
            return False
        return all(ipaddress.ip_address(entry[4][0]).is_global for entry in addresses)
    except (socket.gaierror, ValueError, OSError):
        return False


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PDFLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta_urls: list[str] = []
        self.body_urls: list[str] = []

    @property
    def urls(self) -> list[str]:
        return self.meta_urls + self.body_urls

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        meta_key = (d.get("name") or d.get("property") or "").lower()
        if tag == "meta" and meta_key in (
            "citation_pdf_url", "bepress_citation_pdf_url",
            "dc.relation.ispartof", "eprints.document_url", "wkhealth_pdf_url",
        ):
            self.meta_urls.append(d.get("content", ""))
        if tag == "link":
            href = d.get("href", "")
            mime = (d.get("type") or "").lower()
            rel = (d.get("rel") or "").lower()
            if href and (mime == "application/pdf" or ("alternate" in rel and re.search(r"\.pdf(?:[?#]|$)", href, re.I))):
                self.meta_urls.append(href)
        if tag in ("iframe", "embed", "object"):
            link = d.get("src") or d.get("data") or ""
            mime = (d.get("type") or "").lower()
            if link and (mime == "application/pdf" or re.search(
                r"(?:\.pdf(?:[?#]|$)|/bitstreams?/|/smash/get/|viewcontent\.cgi|/download(?:[/?#]|$))", link, re.I
            )):
                self.body_urls.append(link)
        if tag == "a":
            href = d.get("href", "")
            if re.search(
                r"(?:\.pdf(?:[?#]|$)|/download(?:[/?#]|$)|/bitstreams?/|/smash/get/|"
                r"viewcontent\.cgi|/ws/portalfiles/|/doi/pdf(?:direct)?/|/content/pdf/)",
                href, re.I,
            ):
                self.body_urls.append(href)


def safely_encoded_url(link: object) -> str:
    value = str(link or "")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("control characters in URL")
    return quote(value, safe=":/?#[]@!$&'()*+,;=%-._~")


def safe_request(url: str, limit: int = 26_000_000, accept: str = "application/pdf,*/*;q=0.5") -> tuple[bytes, str, str]:
    opener = build_opener(NoRedirect, HTTPCookieProcessor(CookieJar()))
    visited: dict[str, int] = defaultdict(int)
    for _ in range(MAX_REDIRECTS + 1):
        url = safely_encoded_url(url)
        if not allowed_url(url) or not public_dns(urlsplit(url).hostname) or visited[url] >= 2:
            raise ValueError("unsafe URL or redirect")
        visited[url] += 1
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
        try:
            response = opener.open(req, timeout=25)
        except HTTPError as error:
            if error.code in (301, 302, 303, 307, 308):
                target = error.headers.get("Location")
                error.close()
                if not target:
                    raise ValueError("redirect without Location") from error
                url = candidate_https_url(urljoin(url, target))
                continue
            raise
        with response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise ValueError("HTTP " + str(status))
            declared = response.headers.get("Content-Length")
            if declared and declared.isdecimal() and int(declared) > limit:
                raise ValueError("file exceeds size cap")
            chunks = []
            total = 0
            while True:
                chunk = response.read(min(65536, limit + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise ValueError("file exceeds size cap")
                chunks.append(chunk)
            return b"".join(chunks), url, response.headers.get("Content-Type", "")
    raise ValueError("too many redirects")


def pdf_data(data: bytes) -> bool:
    return len(data) > 500 and data.lstrip()[:4] == b"%PDF" and b"%%EOF" in data[-4096:]


def direct_pdf_hint(link: object) -> bool:
    return bool(re.search(
        r"(?:\.pdf(?:[?#]|$)|/content/pdf/|/track/pdf/|/article/download/|"
        r"/bitstreams?/|/smash/get/|viewcontent\.cgi|/download(?:[/?#]|$))",
        str(link or ""), re.I,
    ))


def pdf_candidates_from_html(data: bytes, landing: str) -> list[str]:
    parser = PDFLinks()
    try:
        parser.feed(data[:1_000_000].decode("utf-8", "ignore"))
    except Exception:
        return []
    urls = []
    for value in parser.urls:
        absolute = candidate_https_url(urljoin(landing, value))
        if not allowed_url(absolute) or BOILERPLATE_PDF_RE.search(absolute):
            continue
        ojs_match = re.match(r"^(https://[^?#]+/article)/view/(\d+/\d+(?:[/?#].*)?)$", absolute, re.I)
        if ojs_match:
            direct_ojs = ojs_match.group(1) + "/download/" + ojs_match.group(2)
            if allowed_url(direct_ojs) and direct_ojs not in urls:
                urls.append(direct_ojs)
        if absolute not in urls:
            urls.append(absolute)
    return urls[:10]


def cache_path(ident: str, cache_dir: Path = PRIVATE_CACHE) -> Path:
    return cache_dir / "pdf" / (hashlib.sha256(ident.encode()).hexdigest()[:24] + ".pdf")


def repo_pdf_filename(ident: str) -> str:
    ident_str = str(ident or "").strip()
    if re.fullmatch(r"W\d+", ident_str):
        return f"{ident_str}.pdf"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", ident_str).strip("._-")[:64] or "doc"
    short_hash = hashlib.sha256(ident_str.encode("utf-8")).hexdigest()[:8]
    return f"{slug}_{short_hash}.pdf"


def sync_repo_pdf_folder(cache_dir: Path = PRIVATE_CACHE, pdf_dir: Path = PDF_DIR,
                         *, max_file_mb: float = 95.0, max_repo_gb: float = 50.0) -> dict:
    """Sync all verified OA PDFs into the repository's `pdf/` directory + `pdf/manifest.json`."""
    from collections import Counter

    pdf_dir = Path(pdf_dir)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    max_file_bytes = int(max_file_mb * 1_000_000)
    max_repo_bytes = int(max_repo_gb * 1_000_000_000)

    valid_rows = queue_rows()
    valid_meta = {r["id"]: r for r in valid_rows}

    progress = read_json(cache_dir / "progress.json", {}) or {}
    source_links = read_json(DOCS_DATA_DIR / "source_links.json", {}) or {}
    migrated = False
    if isinstance(source_links, dict):
        for oa_id, cids in source_links.items():
            if oa_id not in valid_meta or not isinstance(cids, list):
                continue
            if (progress.get(oa_id) or {}).get("status") == "pdf-confirmed":
                continue
            for cid in cids:
                nid = f"nordic:{cid}"
                nrec = progress.get(nid)
                if isinstance(nrec, dict) and nrec.get("status") == "pdf-confirmed":
                    nsrc = cache_path(nid, cache_dir)
                    odst = cache_path(oa_id, cache_dir)
                    if nsrc.is_file():
                        if not odst.is_file():
                            try:
                                os.link(nsrc, odst)
                            except OSError:
                                shutil.copy2(nsrc, odst)
                        progress[oa_id] = dict(nrec)
                        migrated = True
                        break
    if migrated:
        write_json(cache_dir / "progress.json", progress)

    # Identify boilerplate site-footer hashes appearing >= 4 times across active corpus works
    sha_counts = Counter(
        rec.get("sha256")
        for wid, rec in progress.items()
        if wid in valid_meta and isinstance(rec, dict) and rec.get("status") == "pdf-confirmed" and rec.get("sha256")
    )
    boilerplate_shas = {sha for sha, cnt in sha_counts.items() if cnt >= 4}

    prev_manifest = (read_json(pdf_dir / "manifest.json", {}) or {}).get("items", {})
    manifest_items: dict[str, dict] = {}
    total_bytes = 0

    # 1. Retain existing valid files already inside `pdf/` (excluding boilerplate hashes)
    if isinstance(prev_manifest, dict):
        for wid, info in sorted(prev_manifest.items()):
            if wid not in valid_meta or not isinstance(info, dict):
                continue
            sha = info.get("sha256", "")
            if sha in boilerplate_shas or BOILERPLATE_PDF_RE.search(str(info.get("source_url") or "")):
                continue
            fname = Path(str(info.get("file", ""))).name or repo_pdf_filename(wid)
            fpath = pdf_dir / fname
            if fpath.is_file() and 500 <= fpath.stat().st_size <= max_file_bytes:
                sz = fpath.stat().st_size
                manifest_items[wid] = {
                    "file": f"pdf/{fname}",
                    "sha256": sha,
                    "bytes": sz,
                    "source_url": info.get("source_url", ""),
                    "license": info.get("license", ""),
                }
                total_bytes += sz

    # 2. Sync all verified OA PDFs from `PRIVATE_CACHE / "pdf"`
    candidates = []
    for wid, rec in progress.items():
        if wid in manifest_items or wid not in valid_meta or not isinstance(rec, dict):
            continue
        if rec.get("status") != "pdf-confirmed":
            continue
        if rec.get("sha256") in boilerplate_shas or BOILERPLATE_PDF_RE.search(str(rec.get("url") or "")):
            continue
        src = cache_path(wid, cache_dir)
        if not src.is_file():
            continue
        sz = src.stat().st_size
        if not (500 <= sz <= max_file_bytes) or sz != rec.get("bytes"):
            continue
        prio = {"high": 0, "medium": 1, "low": 2}.get(str(valid_meta[wid].get("priority") or ""), 3)
        candidates.append((prio, sz, wid, src, rec))

    candidates.sort(key=lambda t: (t[0], t[1], t[2]))
    added = 0
    for _, sz, wid, src, rec in candidates:
        if total_bytes + sz > max_repo_bytes:
            continue
        raw = src.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if not pdf_data(raw) or digest != rec.get("sha256"):
            continue
        fname = repo_pdf_filename(wid)
        dst = pdf_dir / fname
        if not dst.is_file():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
        url = rec.get("url", "") if safe_public_link(rec.get("url")) else ""
        manifest_items[wid] = {
            "file": f"pdf/{fname}",
            "sha256": digest,
            "bytes": sz,
            "source_url": url,
            "license": "",
        }
        total_bytes += sz
        added += 1

    # Remove orphaned `.pdf` files in `pdf/` not tracked in `manifest_items`
    expected_names = {Path(v["file"]).name for v in manifest_items.values()}
    for existing_file in pdf_dir.glob("*.pdf"):
        if existing_file.name not in expected_names:
            existing_file.unlink(missing_ok=True)

    manifest_payload = {
        "generated_at": now_iso(),
        "count": len(manifest_items),
        "total_bytes": total_bytes,
        "total_gb": round(total_bytes / 1e9, 3),
        "items": dict(sorted(manifest_items.items())),
    }
    write_json(pdf_dir / "manifest.json", manifest_payload, compact=True)
    return {
        "repo_pdf_count": len(manifest_items),
        "added": added,
        "total_gb": round(total_bytes / 1e9, 3),
    }


def cached_pdf_ok(ident: str, entry: dict | None, cache_dir: Path = PRIVATE_CACHE) -> bool:
    if not entry or entry.get("status") != "pdf-confirmed":
        return False
    file = cache_path(ident, cache_dir)
    if not file.is_file() or file.stat().st_size != entry.get("bytes"):
        return False
    raw = file.read_bytes()
    return pdf_data(raw) and hashlib.sha256(raw).hexdigest() == entry.get("sha256")


def extract_openalex_work_urls(data: dict) -> list[str]:
    if not isinstance(data, dict):
        return []
    locs = [data.get("best_oa_location"), data.get("primary_location")] + (data.get("locations") or [])
    candidates = {}
    for pos, loc in enumerate(locs):
        if not isinstance(loc, dict) or not loc.get("is_oa", False):
            continue
        source = loc.get("source") or {}
        repository = isinstance(source, dict) and source.get("type") == "repository"
        for raw_link in (loc.get("pdf_url"), loc.get("landing_page_url")):
            link = candidate_https_url(raw_link)
            if not allowed_url(link):
                continue
            pdf_shaped = direct_pdf_hint(link)
            rank = 0 if (pdf_shaped and repository) else (1 if pdf_shaped else (2 if repository else 3))
            key = (rank, pos)
            if link not in candidates or key < candidates[link]:
                candidates[link] = key
    oa = data.get("open_access") or {}
    alternate = candidate_https_url(oa.get("oa_url")) if oa.get("is_oa") else None
    if allowed_url(alternate) and alternate not in candidates:
        candidates[alternate] = (4, len(locs))
    return [url for url, _ in sorted(candidates.items(), key=lambda item: item[1])][:12]


def openalex_urls(doi: str) -> list[str]:
    short = normalize_doi(doi)
    if not short:
        return []
    url = "https://api.openalex.org/works/https://doi.org/" + quote(short, safe="/")
    payload, _, _ = safe_request(url, limit=1_500_000, accept="application/json")
    return extract_openalex_work_urls(json.loads(payload.decode("utf-8")))


def openalex_batch_prefetch(dois: list[str], pause_fn=None) -> dict[str, list[str]]:
    clean = sorted({d for raw in dois if (d := normalize_doi(raw)) and not any(ch in d for ch in ",|")})
    prefetched: dict[str, list[str]] = {}
    for idx in range(0, len(clean), 50):
        chunk = clean[idx:idx + 50]
        for d in chunk:
            prefetched.setdefault(d, [])
        joined = "|".join(quote(d, safe="/:()-._") for d in chunk)
        endpoint = (
            "https://api.openalex.org/works?filter=doi:" + joined
            + "&per_page=100&select=id,doi,best_oa_location,primary_location,locations,open_access"
        )
        try:
            if pause_fn:
                pause_fn("api.openalex.org")
            payload, _, _ = safe_request(endpoint, limit=5_000_000, accept="application/json")
            for item in (json.loads(payload.decode("utf-8")).get("results") or []):
                item_doi = normalize_doi(item.get("doi"))
                if item_doi:
                    prefetched[item_doi] = extract_openalex_work_urls(item)
        except Exception as exc:
            if isinstance(exc, HTTPError) and exc.code == 429:
                break
    return prefetched


def synthesized_oa_urls(doi: str) -> list[str]:
    short = normalize_doi(doi)
    if not short:
        return []
    if short.startswith("10.48550/arxiv."):
        aid = short.split("10.48550/arxiv.", 1)[1]
        u = "https://arxiv.org/pdf/" + quote(aid, safe=".") + ".pdf"
        return [u] if allowed_url(u) else []
    if short.startswith("10.5281/zenodo."):
        rid = short.split("10.5281/zenodo.", 1)[1]
        if rid.isdigit():
            return ["https://zenodo.org/records/" + rid]
    if short.startswith(OA_DOI_PREFIXES):
        u = "https://doi.org/" + quote(short, safe="/")
        return [u] if allowed_url(u) else []
    return []


def unpaywall_urls(doi: str, email: str) -> list[str]:
    short = normalize_doi(doi)
    if not email or "@" not in email or not short:
        return []
    url = f"https://api.unpaywall.org/v2/{quote(short, safe='/')}?email={quote(email, safe='@.')}"
    payload, _, _ = safe_request(url, limit=1_000_000, accept="application/json")
    data = json.loads(payload.decode("utf-8"))
    if not data.get("is_oa"):
        return []
    result = []
    for loc in [data.get("best_oa_location")] + (data.get("oa_locations") or []):
        if isinstance(loc, dict):
            for raw in (loc.get("url_for_pdf"), loc.get("url")):
                c = candidate_https_url(raw)
                if allowed_url(c) and c not in result:
                    result.append(c)
    return result[:10]


def europepmc_urls(doi: str) -> list[str]:
    short = normalize_doi(doi)
    if not short:
        return []
    endpoint = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%22{quote(short, safe='')}%22&format=json&pageSize=5"
    payload, _, _ = safe_request(endpoint, limit=750_000, accept="application/json")
    results = ((json.loads(payload.decode("utf-8")).get("resultList") or {}).get("result")) or []
    urls = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if normalize_doi(item.get("doi")) and normalize_doi(item.get("doi")) != short:
            continue
        pmcid = str(item.get("pmcid") or "").strip()
        if item.get("isOpenAccess") == "Y" and item.get("hasPDF") == "Y" and re.fullmatch(r"PMC\d+", pmcid):
            c = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
            if allowed_url(c) and c not in urls:
                urls.append(c)
    return urls


def crossref_urls(doi: str) -> list[str]:
    short = normalize_doi(doi)
    if not short:
        return []
    payload, _, _ = safe_request("https://api.crossref.org/works/" + quote(short, safe=""), limit=1_000_000, accept="application/json")
    msg = (json.loads(payload.decode("utf-8")).get("message") or {})
    urls = []
    tdm_hosts = ("api.elsevier.com", "api.wiley.com", "syndication.highwire.org")
    for entry in msg.get("link") or []:
        if not isinstance(entry, dict) or entry.get("intended-application") == "text-mining":
            continue
        c = candidate_https_url(entry.get("URL"))
        if not allowed_url(c):
            continue
        host = (urlsplit(c).hostname or "").lower()
        if any(t in host for t in tdm_hosts):
            continue
        if (entry.get("content-type") or "").lower() == "application/pdf" or direct_pdf_hint(c):
            if c not in urls:
                urls.append(c)
    return urls[:6]


def semantic_scholar_urls(doi: str) -> list[str]:
    short = normalize_doi(doi)
    if not short:
        return []
    endpoint = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(short, safe='')}?fields=openAccessPdf,isOpenAccess"
    payload, _, _ = safe_request(endpoint, limit=750_000, accept="application/json")
    data = json.loads(payload.decode("utf-8"))
    url = candidate_https_url(((data.get("openAccessPdf") or {}) if isinstance(data, dict) else {}).get("url"))
    return [url] if allowed_url(url) else []


def queue_rows() -> list[dict]:
    repo_manifest = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
    archived = set(repo_manifest.keys())
    base = read_json(DOCS_DATA_DIR / "publications.json", []) or []
    additions = read_json(DOCS_DATA_DIR / "nordic_additions.json", []) or []
    rows = []
    for w in base + additions:
        ident = w.get("id")
        if not ident:
            continue
        oa = w.get("oa_url") or (w.get("source_url") if w.get("origin") == "external" else "") or ""
        oa = candidate_https_url(oa)
        if not allowed_url(oa):
            oa = ""
        rows.append({
            "id": ident,
            "doi": w.get("doi") or "",
            "title": w.get("title") or "",
            "year": w.get("year") or "",
            "kind": w.get("kind") or "",
            "source": w.get("source") or "",
            "oa_url": oa,
            "scope": w.get("scope") or "",
            "priority": w.get("review_priority") or "",
            "archived": "yes" if ident in archived else "no",
            "candidate_status": "archived" if ident in archived else (
                "oa-link-unchecked" if oa else "doi-only" if w.get("doi") else "no-oa-link"
            ),
        })
    rank = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda x: (
        x["archived"] == "yes",
        not (direct_pdf_hint(x["oa_url"]) or normalize_doi(x["doi"]).startswith(OA_DOI_PREFIXES)),
        not bool(x["oa_url"]),
        x["kind"] in ("dissertation", "book"),
        rank.get(x["priority"], 2),
        -(int(x["year"]) if str(x["year"]).isdigit() else 0),
        x["id"],
    ))
    return rows


def harvest_pdfs(*, limit: int = 8000, workers: int = 12, host_delay: float = 1.0,
                 email: str = "", max_mb: int = 45, max_cache_gb: float = 25.0,
                 min_free_gb: float = 6.0, retry_failed: bool = False,
                 lookup_openalex: bool = True, lookup_europepmc: bool = True,
                 lookup_crossref: bool = True, lookup_semantic_scholar: bool = True,
                 cache_dir: Path = PRIVATE_CACHE) -> int:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "pdf").mkdir(exist_ok=True)
    log_path = cache_dir / "progress.json"
    progress = read_json(log_path, {}) or {}
    rows = queue_rows()

    max_bytes = max_mb * 1_000_000
    max_cache_bytes = int(max_cache_gb * 1_000_000_000)
    min_free_bytes = int(min_free_gb * 1_000_000_000)

    state_lock = threading.Lock()
    host_locks_guard = threading.Lock()
    host_locks: dict[str, threading.Lock] = {}
    host_last: dict[str, float] = defaultdict(float)
    blocked_sources: set[str] = set()
    blocked_hosts: set[str] = set()
    stop_event = threading.Event()
    tried = 0
    dirty = 0
    used_bytes = sum(int(r.get("bytes", 0)) for r in progress.values() if isinstance(r, dict) and r.get("status") == "pdf-confirmed")

    def pace_host(host_key: str = ""):
        key = (host_key or "_default_").lower()
        with host_locks_guard:
            lock = host_locks.setdefault(key, threading.Lock())
        with lock:
            wait = max(0.0, host_delay - (time.monotonic() - host_last[key]))
            if wait > 0:
                time.sleep(wait)
            host_last[key] = time.monotonic()

    any_api = bool(email or lookup_openalex or lookup_europepmc or lookup_crossref or lookup_semantic_scholar)
    unvisited_rows = []
    deferred_rows = []
    for row in rows:
        ident = row["id"]
        if row["archived"] == "yes":
            continue
        prev = progress.get(ident) or {}
        st = prev.get("status")
        if st == "pdf-confirmed":
            if cached_pdf_ok(ident, prev, cache_dir):
                continue
            progress.pop(ident, None)
            st = None
        if st == "failed" and not retry_failed:
            continue
        if not row["oa_url"] and not (any_api and row["doi"]):
            continue
        if st == "deferred":
            deferred_rows.append(row)
        else:
            unvisited_rows.append(row)
            if len(unvisited_rows) >= limit:
                break
    eligible = (unvisited_rows + deferred_rows)[:limit]

    prefetched_oa = {}
    if lookup_openalex and eligible:
        dois = [r["doi"] for r in eligible if r.get("doi")]
        if dois:
            print("OPENALEX_PREFETCH_START", len(dois), flush=True)
            prefetched_oa = openalex_batch_prefetch(dois, pause_fn=pace_host)
            print("OPENALEX_PREFETCH_DONE", len(prefetched_oa), flush=True)

    sources = ("registered", "synthesized", "unpaywall", "openalex", "europepmc", "crossref", "semantic_scholar")

    def process_one(row: dict):
        nonlocal tried, used_bytes, dirty
        ident = row["id"]
        with state_lock:
            if stop_event.is_set() or tried >= limit:
                return
            free_b = shutil.disk_usage(cache_dir).free
            if (used_bytes + max_bytes > max_cache_bytes) or (free_b - max_bytes < min_free_bytes):
                stop_event.set()
                write_json(log_path, progress)
                return
            tried += 1
            progress[ident] = {"status": "failed", "reason": "attempt interrupted before result", "checked_at": now_iso()}
            dirty += 1
            if workers == 1 or dirty >= 15:
                write_json(log_path, progress)
                dirty = 0

        success = None
        deferred = False
        why = "No direct PDF at public OA sources"
        seen = set()

        for src in sources:
            if success or stop_event.is_set():
                break
            with state_lock:
                if src in blocked_sources:
                    deferred = True
                    continue
            try:
                if src == "registered":
                    cands = [candidate_https_url(row["oa_url"])] if row["oa_url"] else []
                elif src == "synthesized":
                    cands = synthesized_oa_urls(row["doi"]) if row["doi"] else []
                elif src == "unpaywall":
                    if not email or not row["doi"]:
                        continue
                    pace_host("api.unpaywall.org")
                    cands = unpaywall_urls(row["doi"], email)
                elif src == "openalex":
                    if not lookup_openalex or not row["doi"]:
                        continue
                    nd = normalize_doi(row["doi"])
                    if nd in prefetched_oa:
                        cands = prefetched_oa[nd]
                    else:
                        pace_host("api.openalex.org")
                        cands = openalex_urls(row["doi"])
                elif src == "europepmc":
                    if not lookup_europepmc or not row["doi"]:
                        continue
                    pace_host("www.ebi.ac.uk")
                    cands = europepmc_urls(row["doi"])
                elif src == "crossref":
                    if not lookup_crossref or not row["doi"]:
                        continue
                    pace_host("api.crossref.org")
                    cands = crossref_urls(row["doi"])
                else:
                    if not lookup_semantic_scholar or not row["doi"]:
                        continue
                    pace_host("api.semanticscholar.org")
                    cands = semantic_scholar_urls(row["doi"])
            except Exception as exc:
                if isinstance(exc, HTTPError) and exc.code in (403, 429) and src in ("semantic_scholar", "unpaywall", "openalex", "europepmc", "crossref"):
                    with state_lock:
                        blocked_sources.add(src)
                    deferred = True
                continue

            for raw_target in cands[:10]:
                target = candidate_https_url(raw_target)
                if not allowed_url(target) or target in seen:
                    continue
                host = urlsplit(target).hostname
                with state_lock:
                    if host in blocked_hosts:
                        deferred = True
                        continue
                seen.add(target)
                try:
                    pace_host(host or "")
                    payload, landing, mime = safe_request(target, limit=max_bytes)
                    if pdf_data(payload):
                        success = (payload, landing)
                        break
                    prefix = payload[:4096].lstrip().lower()
                    if "html" not in mime.lower() and b"<html" not in prefix and b"<!doctype html" not in prefix:
                        continue
                    for dest in pdf_candidates_from_html(payload, landing):
                        if dest in seen:
                            continue
                        dhost = urlsplit(dest).hostname
                        with state_lock:
                            if dhost in blocked_hosts:
                                deferred = True
                                continue
                        seen.add(dest)
                        try:
                            pace_host(dhost or "")
                            cand_bytes, resolved, _ = safe_request(dest, limit=max_bytes)
                            if pdf_data(cand_bytes):
                                success = (cand_bytes, resolved)
                                break
                        except Exception as exc2:
                            why = f"{type(exc2).__name__}: {str(exc2)[:140]}"
                            if isinstance(exc2, HTTPError) and exc2.code == 429:
                                with state_lock:
                                    blocked_hosts.add(dhost or "")
                                deferred = True
                    if success:
                        break
                except Exception as exc:
                    why = f"{type(exc).__name__}: {str(exc)[:140]}"
                    if isinstance(exc, HTTPError) and exc.code == 429:
                        with state_lock:
                            blocked_hosts.add(host or "")
                        deferred = True

        if success:
            payload, final_url = success
            sha = hashlib.sha256(payload).hexdigest()
            pdf_file = cache_path(ident, cache_dir)
            tmp = pdf_file.with_suffix(f".pdf.partial.{threading.get_ident()}")
            tmp.write_bytes(payload)
            os.replace(tmp, pdf_file)
            with state_lock:
                progress[ident] = {"status": "pdf-confirmed", "url": final_url, "sha256": sha, "bytes": len(payload), "checked_at": now_iso()}
                used_bytes += len(payload)
                dirty += 1
                if workers == 1 or dirty >= 15:
                    write_json(log_path, progress)
                    dirty = 0
            print("PDF_OK", ident, len(payload), sha[:12], flush=True)
        else:
            with state_lock:
                progress[ident] = {"status": "deferred" if deferred else "failed", "reason": why, "checked_at": now_iso()}
                dirty += 1
                if workers == 1 or dirty >= 15:
                    write_json(log_path, progress)
                    dirty = 0

    try:
        if workers <= 1:
            for r in eligible:
                if stop_event.is_set():
                    break
                process_one(r)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = [pool.submit(process_one, r) for r in eligible]
                for f in as_completed(futs):
                    f.result()
    finally:
        if tried > 0:
            write_json(log_path, progress)
    return tried


def merge_local_cache(source: Path, dest: Path = PRIVATE_CACHE) -> dict:
    source = Path(source).expanduser().resolve()
    dest = Path(dest).expanduser().resolve()
    if source == dest or not (source / "progress.json").is_file():
        return {"imported": 0}
    raw = read_json(source / "progress.json", {}) or {}
    log_path = dest / "progress.json"
    progress = read_json(log_path, {}) or {}
    (dest / "pdf").mkdir(parents=True, exist_ok=True)
    imported = 0
    for ident, row in sorted(raw.items()):
        if not isinstance(row, dict) or row.get("status") != "pdf-confirmed":
            continue
        digest = row.get("sha256", "")
        size = row.get("bytes", 0)
        if not re.fullmatch(r"[a-f0-9]{64}", str(digest)) or not (500 <= int(size) <= 50_000_000):
            continue
        name = hashlib.sha256(ident.encode()).hexdigest()[:24] + ".pdf"
        old = source / "pdf" / name
        dst_file = dest / "pdf" / name
        if not old.is_file() or old.stat().st_size != size:
            continue
        if cached_pdf_ok(ident, progress.get(ident), dest):
            continue
        blob = old.read_bytes()
        if hashlib.sha256(blob).hexdigest() != digest or not pdf_data(blob):
            continue
        if not dst_file.exists():
            try:
                os.link(old, dst_file)
            except OSError:
                shutil.copy2(old, dst_file)
        progress[ident] = {**row, "status": "pdf-confirmed", "source": "imported-local-cache"}
        imported += 1
    if imported:
        write_json(log_path, progress)
    return {"imported": imported}


def audit_private_cache(cache_dir: Path = PRIVATE_CACHE) -> dict:
    progress = read_json(cache_dir / "progress.json", {}) or {}
    verified = 0
    hashes = set()
    total_bytes = 0
    for ident, item in progress.items():
        if isinstance(item, dict) and cached_pdf_ok(ident, item, cache_dir):
            verified += 1
            hashes.add(item["sha256"])
            total_bytes += int(item.get("bytes", 0))
    repo_manifest = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
    summary = {
        "verified_private_pdfs": verified,
        "unique_private_hashes": len(hashes),
        "repo_pdf_folder_count": len(repo_manifest),
        "total_verified_fulltext_pdfs": max(len(repo_manifest), verified),
        "disk_gb": round(total_bytes / 1e9, 3),
    }
    write_json(cache_dir / "pdf_local_report.json", summary)
    return summary


def publish_pdf_catalog(cache_dir: Path = PRIVATE_CACHE, *, sync_repo_pdfs: bool = True) -> dict:
    if sync_repo_pdfs:
        sync_repo_pdf_folder(cache_dir=cache_dir, pdf_dir=PDF_DIR)
    rows = queue_rows()
    valid_ids = {r["id"] for r in rows}
    progress = read_json(cache_dir / "progress.json", {}) or {}
    repo_manifest = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
    links: dict[str, dict] = {}

    for ident, info in repo_manifest.items():
        if ident in valid_ids and isinstance(info, dict) and re.fullmatch(r"[a-f0-9]{64}", str(info.get("sha256", ""))):
            src_url = info.get("source_url", "") if safe_public_link(info.get("source_url")) else ""
            links[ident] = {
                "url": src_url or f"{REPO_RAW_BASE}/{info['file']}",
                "repo_pdf": f"{REPO_RAW_BASE}/{info['file']}",
                "status": "in-repo-pdf",
                "sha256": info["sha256"],
                "license": info.get("license", ""),
            }

    for ident, row in progress.items():
        if (ident in valid_ids and ident not in links and isinstance(row, dict)
                and row.get("status") == "pdf-confirmed"
                and safe_public_link(row.get("url"))
                and not BOILERPLATE_PDF_RE.search(str(row.get("url") or ""))
                and re.fullmatch(r"[a-f0-9]{64}", str(row.get("sha256", "")))):
            links[ident] = {
                "url": row["url"],
                "repo_pdf": "",
                "status": "verified-oa-link",
                "sha256": row["sha256"],
                "license": "",
            }

    pdf_status = {
        "openalex_and_nordic_candidates": len(rows),
        "repo_pdf_count": len(repo_manifest),
        "oa_links_unchecked": sum(r["candidate_status"] == "oa-link-unchecked" for r in rows),
        "doi_without_oa_link": sum(r["candidate_status"] == "doi-only" for r in rows),
        "without_doi_or_oa": sum(r["candidate_status"] == "no-oa-link" for r in rows),
        "public_verified_pdf_links": len(links),
    }
    write_json(DOCS_DATA_DIR / "pdf_found.json", dict(sorted(links.items())))
    write_json(DOCS_DATA_DIR / "pdf_status.json", pdf_status)

    works = read_json(DOCS_DATA_DIR / "publications.json", []) or []
    nordic = read_json(DOCS_DATA_DIR / "nordic_additions.json", []) or []
    cat_rows = []
    for w in works + nordic:
        wid = w["id"]
        orig_url = w.get("oa_url") or (w.get("source_url") if w.get("origin") == "external" else "") or ""
        conf = links.get(wid)
        conf_url = (conf.get("url") or "") if isinstance(conf, dict) else ""
        if not allowed_url(conf_url):
            conf_url = ""
        rm = repo_manifest.get(wid)
        if not orig_url and not conf_url and not rm:
            continue
        in_repo = bool(rm)
        mirror_url = f"{REPO_RAW_BASE}/{rm['file']}" if rm else ""
        verified_pdf = bool(rm or (conf and conf_url and conf.get("sha256")))
        best_oa = conf_url or (orig_url if allowed_url(orig_url) else "")
        if not in_repo and not best_oa:
            continue
        cat_rows.append({
            "id": wid,
            "title": w.get("title") or "",
            "year": w.get("year"),
            "authors": w.get("authors") or [],
            "doi": w.get("doi") or "",
            "country_affiliations": w.get("countries") or ([w["source_country"]] if w.get("source_country") else []),
            "source": w.get("source") or "",
            "review_priority": w.get("review_priority") or "",
            "pdf_in_repo": in_repo,
            "verified_oa_pdf": verified_pdf,
            "public_pdf_url": mirror_url,
            "oa_location_unverified": best_oa,
            "license": rm.get("license", "") if rm else "",
            "document_sha256": rm["sha256"] if rm else (conf.get("sha256", "") if conf else ""),
            "document_bytes": rm["bytes"] if rm else 0,
            "access_status": (
                "public_repo_mirror" if in_repo else
                "verified_oa_pdf_link" if verified_pdf else
                "metadata_oa_location_unverified"
            ),
        })
    cat_rows.sort(key=lambda r: (
        not r["pdf_in_repo"],
        not r["verified_oa_pdf"],
        {"high": 0, "medium": 1, "low": 2}.get(r["review_priority"], 3),
        -int(r.get("year") or 0),
        r["id"],
    ))
    cat_stats = {
        "total_visible_entries": len(cat_rows),
        "repo_pdf_count": sum(bool(r["pdf_in_repo"]) for r in cat_rows),
        "verified_oa_pdf_count": sum(bool(r["verified_oa_pdf"]) for r in cat_rows),
        "original_oa_location_links": sum(bool(r["oa_location_unverified"]) for r in cat_rows),
        "generated_utc": now_iso(),
    }
    write_json(DOCS_DATA_DIR / "pdf_katalog.json", {"stats": cat_stats, "items": cat_rows}, compact=True)
    cat_cols = [
        "id", "title", "year", "authors", "doi", "country_affiliations", "source",
        "review_priority", "pdf_in_repo", "verified_oa_pdf", "public_pdf_url",
        "oa_location_unverified", "license", "document_sha256",
    ]
    write_csv_rows(DOCS_DATA_DIR / "pdf_katalog.csv", cat_cols, [
        {**w, "authors": "; ".join(w["authors"]), "country_affiliations": "; ".join(w["country_affiliations"])}
        for w in cat_rows
    ])
    return cat_stats
