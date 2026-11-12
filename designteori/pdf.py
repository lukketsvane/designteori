"""Lawful Open Access PDF discovery, retrieval, cache audit, and rights-aware catalog."""
from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import os
import re
import shutil
import socket
import sqlite3
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

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

from . import (
    DOCS_DATA_DIR,
    PDF_DIR,
    PRIVATE_CACHE,
    RAW_SQLITE,
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
    "10.3390/", "10.3389/", "10.1371/", "10.1186/", "10.55612/",
)
QUEUE_FIELDS = (
    "id", "doi", "title", "year", "kind", "source", "oa_url",
    "scope", "priority", "archived", "candidate_status",
)
DEFAULT_UNPAYWALL_EMAIL = "designteori-research@outlook.com"
DSPACE_API_HOSTS = (
    "aaltodoc.aalto.fi",
    "gupea.ub.gu.se",
    "helda.helsinki.fi",
    "erepo.uef.fi",
    "taju.uniarts.fi",
)
API_HOST_MIN_DELAYS = {
    "api.semanticscholar.org": 15.0,
    "api.core.ac.uk": 1.0,
    "api.openaire.eu": 0.4,
    "api.nva.unit.no": 0.25,
    "api.unpaywall.org": 0.15,
    "www.diva-portal.org": 0.5,
}
BLOCK_EXEMPT_REDIRECTORS = {
    "doi.org",
    "dx.doi.org",
    "hdl.handle.net",
    "urn.kb.se",
    "www.urn.kb.se",
    "nva.sikt.no",
    "api.nva.unit.no",
}
NO_DOI_PREFIXES = ("10.7577/", "10.5617/", "10.5324/", "10.15845/", "10.23865/", "10.18261/")


class BotChallengeError(Exception):
    """Raised when a remote host presents a CAPTCHA, PoW, or anti-bot gate."""


def is_bot_challenge_html(data: bytes) -> bool:
    head = data[:8192].decode("utf-8", "ignore").lower()
    markers = (
        "/.within.website/",
        "making sure you're not a bot",
        "challenges.cloudflare.com",
        "cf-browser-verification",
        "<title>just a moment...</title>",
        "_cf_chl_opt",
    )
    return any(m in head for m in markers)


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
                r"(?:\.pdf(?:[?#]|$)|/download[-_a-z]*(?:[/?#]|$)|/bitstreams?/|/smash/get/|"
                r"viewcontent\.cgi|/ws/(?:portal)?files/|/files/\d+/|/document(?:[/?#]|$)|"
                r"/doi/pdf(?:direct)?/|/content/pdf/)",
                href, re.I,
            ):
                self.body_urls.append(href)


def safely_encoded_url(link: object) -> str:
    value = str(link or "")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("control characters in URL")
    return quote(value, safe=":/?#[]@!$&'()*+,;=%-._~")


def safe_request(
    url: str,
    limit: int = 90_000_000,
    accept: str = "application/pdf,*/*;q=0.5",
    timeout: int = 45,
    data: bytes | None = None,
    content_type: str = "",
) -> tuple[bytes, str, str]:
    opener = build_opener(NoRedirect, HTTPCookieProcessor(CookieJar()))
    visited: dict[str, int] = defaultdict(int)
    for _ in range(MAX_REDIRECTS + 1):
        url = safely_encoded_url(url)
        if not allowed_url(url) or not public_dns(urlsplit(url).hostname) or visited[url] >= 2:
            raise ValueError("unsafe URL or redirect")
        visited[url] += 1
        headers = {"User-Agent": USER_AGENT, "Accept": accept}
        if content_type:
            headers["Content-Type"] = content_type
        req = Request(url, data=data, headers=headers)
        try:
            response = opener.open(req, timeout=timeout)
        except HTTPError as error:
            if error.code in (301, 302, 303, 307, 308):
                target = error.headers.get("Location")
                error.close()
                if not target:
                    raise ValueError("redirect without Location") from error
                url = candidate_https_url(urljoin(url, target))
                continue
            cf_mit = (error.headers.get("cf-mitigated") or "").lower()
            if cf_mit == "challenge":
                error.close()
                raise BotChallengeError(f"Cloudflare challenge on {urlsplit(url).hostname}") from error
            raise
        with response:
            status = getattr(response, "status", 200)
            if status == 202:
                raise BotChallengeError(f"HTTP 202 anti-bot gate on {urlsplit(url).hostname}")
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


def unwrap_pdf_payload(data: bytes) -> bytes:
    """Strip HTTP multipart wrapper that older DSpace instances saved around PDF bitstreams."""
    if pdf_data(data):
        return data
    if b"Content-Disposition:" not in data[:1024]:
        return data
    idx = data.find(b"%PDF-", 0, 2048)
    end = data.rfind(b"%%EOF", idx) if idx > 0 else -1
    if idx <= 0 or end <= idx:
        return data
    nl = data.find(b"\n", end)
    stop = nl + 1 if 0 <= nl - end <= 16 else end + 5
    inner = data[idx:stop]
    return inner if pdf_data(inner) else data


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
        lic = str(rec.get("license") or "")[:120]
        manifest_items[wid] = {
            "file": f"pdf/{fname}",
            "sha256": digest,
            "bytes": sz,
            "source_url": url,
            "license": lic,
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


def extract_nva_uuid(link: object) -> str:
    m = re.search(
        r"^https://(?:nva\.sikt\.no/registration|api\.nva\.unit\.no/publication)/([0-9a-f]+(?:-[0-9a-f]+){3,})(?:[/?#]|$)",
        str(link or "").strip(),
        re.I,
    )
    return m.group(1) if m else ""


def parse_nva_publication_artifacts(pub: dict) -> tuple[list[dict], list[str]]:
    if not isinstance(pub, dict):
        return [], []
    files: list[dict] = []
    links: list[str] = []
    for art in pub.get("associatedArtifacts") or []:
        if not isinstance(art, dict):
            continue
        atype = art.get("type")
        if atype == "OpenFile" and "download" in (art.get("allowedOperations") or []) and not art.get("administrativeAgreement"):
            mime = str(art.get("mimeType") or "").lower()
            name = str(art.get("name") or "").lower()
            if "pdf" not in mime and not name.endswith(".pdf") and mime:
                continue
            fid = str(art.get("identifier") or "").strip()
            if not fid:
                continue
            lic_obj = art.get("license") or {}
            lic = str(lic_obj.get("value") or lic_obj.get("name") or "").strip() if isinstance(lic_obj, dict) else ""
            files.append({"identifier": fid, "license": lic, "is_pdf": ("pdf" in mime or name.endswith(".pdf"))})
        elif atype == "AssociatedLink":
            u = candidate_https_url(art.get("id"))
            if allowed_url(u) and (direct_pdf_hint(u) or "doi.org/" in u or "handle.net/" in u) and u not in links:
                links.append(u)
    files.sort(key=lambda item: not item["is_pdf"])
    return files, links


def _nva_resolve_files(pub_uuid: str, pub: dict, pause_fn=None) -> list[dict]:
    files, links = parse_nva_publication_artifacts(pub)
    cands: list[dict] = []
    for f in files[:4]:
        if pause_fn:
            pause_fn("api.nva.unit.no")
        ep = f"https://api.nva.unit.no/publication/{quote(pub_uuid, safe='')}/filelink/{quote(f['identifier'], safe='')}"
        payload, _, _ = safe_request(ep, limit=500_000, accept="application/json")
        fl = json.loads(payload.decode("utf-8"))
        presigned = candidate_https_url(fl.get("id") if isinstance(fl, dict) else "")
        alias = candidate_https_url(fl.get("alias") if isinstance(fl, dict) else "")
        pub_url = alias if safe_public_link(alias) else f"https://nva.sikt.no/registration/{pub_uuid}"
        fetch_u = presigned if allowed_url(presigned) else (alias if allowed_url(alias) else "")
        if fetch_u:
            cands.append({"url": fetch_u, "public_url": pub_url, "license": f["license"]})
    for u in links[:4]:
        cands.append({"url": u, "public_url": u, "license": ""})
    return cands


def nva_publication_candidates(pub_uuid: str, pause_fn=None) -> list[dict]:
    if not pub_uuid:
        return []
    if pause_fn:
        pause_fn("api.nva.unit.no")
    ep = f"https://api.nva.unit.no/publication/{quote(pub_uuid, safe='')}"
    payload, _, _ = safe_request(ep, limit=1_500_000, accept="application/json")
    return _nva_resolve_files(pub_uuid, json.loads(payload.decode("utf-8")), pause_fn=pause_fn)


def nva_search_candidates(doi: str, pause_fn=None) -> list[dict]:
    short = normalize_doi(doi)
    if not short:
        return []
    ep = f"https://api.nva.unit.no/search/resources?query={quote(short, safe='')}&results=5"
    payload, _, _ = safe_request(ep, limit=1_500_000, accept="application/json")
    data = json.loads(payload.decode("utf-8"))
    out: list[dict] = []
    for hit in (data.get("hits") or []) if isinstance(data, dict) else []:
        if not isinstance(hit, dict):
            continue
        ref_doi = normalize_doi(((hit.get("entityDescription") or {}).get("reference") or {}).get("doi"))
        if ref_doi != short:
            continue
        pub_uuid = str(hit.get("identifier") or "").strip()
        if pub_uuid:
            out.extend(_nva_resolve_files(pub_uuid, hit, pause_fn=pause_fn))
    return out[:6]


def extract_dspace_handle(link: object) -> tuple[str, str, str]:
    text = candidate_https_url(link)
    if not allowed_url(text):
        return "", "", ""
    u = urlsplit(text)
    host = (u.hostname or "").lower()
    if host not in DSPACE_API_HOSTS:
        return "", "", ""
    m_item = re.search(r"/items/([0-9a-f]{8}-[0-9a-f-]{27,})(?:[/?#]|$)", u.path or "", re.I)
    if m_item:
        return host, "", m_item.group(1)
    m_hdl = re.search(r"/handle/(\d+/[^/?#]+)(?:[/?#]|$)", u.path or "", re.I)
    if m_hdl:
        return host, m_hdl.group(1), ""
    return "", "", ""


def parse_dspace_bitstream_urls(bitstreams_json: dict, host: str) -> list[str]:
    if not isinstance(bitstreams_json, dict):
        return []
    bs = ((bitstreams_json.get("_embedded") or {}).get("bitstreams")) or []
    ranked: list[tuple[bool, int, str]] = []
    for bit in bs:
        if not isinstance(bit, dict):
            continue
        name = str(bit.get("name") or "").lower()
        size = int(bit.get("sizeBytes") or 0)
        if name.endswith((".txt", ".xml", ".jpg", ".png")) or "license" in name:
            continue
        href = candidate_https_url(((bit.get("_links") or {}).get("content") or {}).get("href"))
        if not allowed_url(href) or (urlsplit(href).hostname or "").lower() != host.lower():
            continue
        ranked.append((not name.endswith(".pdf"), -size, href))
    ranked.sort()
    return [href for _, _, href in ranked[:6]]


def dspace_api_urls(link: str, pause_fn=None) -> list[str]:
    host, handle, item_uuid = extract_dspace_handle(link)
    if not host:
        return []
    if pause_fn:
        pause_fn(host)
    if item_uuid:
        ep = f"https://{host}/server/api/core/items/{quote(item_uuid, safe='')}/bundles"
        b_payload, _, _ = safe_request(ep, limit=1_000_000, accept="application/json")
    else:
        ep = f"https://{host}/server/api/pid/find?id={quote(handle, safe='/')}"
        item_payload, _, _ = safe_request(ep, limit=1_000_000, accept="application/json")
        item_json = json.loads(item_payload.decode("utf-8"))
        bundles_href = candidate_https_url(((item_json.get("_links") or {}).get("bundles") or {}).get("href"))
        if not allowed_url(bundles_href) or (urlsplit(bundles_href).hostname or "").lower() != host:
            return []
        if pause_fn:
            pause_fn(host)
        b_payload, _, _ = safe_request(bundles_href, limit=1_000_000, accept="application/json")
    bundles = ((json.loads(b_payload.decode("utf-8")).get("_embedded") or {}).get("bundles")) or []
    out: list[str] = []
    for b in bundles:
        if not isinstance(b, dict) or str(b.get("name") or "").upper() != "ORIGINAL":
            continue
        bit_href = candidate_https_url(((b.get("_links") or {}).get("bitstreams") or {}).get("href"))
        if not allowed_url(bit_href) or (urlsplit(bit_href).hostname or "").lower() != host:
            continue
        if pause_fn:
            pause_fn(host)
        bs_payload, _, _ = safe_request(bit_href, limit=1_000_000, accept="application/json")
        for u in parse_dspace_bitstream_urls(json.loads(bs_payload.decode("utf-8")), host):
            if u not in out:
                out.append(u)
    return out[:6]


def _as_list(val: object) -> list:
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def parse_openaire_urls(data: dict) -> list[str]:
    results = (((data.get("response") or {}).get("results") or {}) if isinstance(data, dict) else {}).get("result")
    ranked: list[tuple[int, str]] = []
    seen: set[str] = set()
    for res in _as_list(results):
        if not isinstance(res, dict):
            continue
        oaf_res = ((res.get("metadata") or {}).get("oaf:entity") or {}).get("oaf:result") or {}
        if not isinstance(oaf_res, dict):
            continue
        containers = [oaf_res] + _as_list((oaf_res.get("children") or {}).get("result"))
        for item in containers:
            if not isinstance(item, dict):
                continue
            for inst in _as_list(item.get("instance")):
                if not isinstance(inst, dict):
                    continue
                acc = str(((inst.get("accessright") or {}).get("@classid") or "")).upper()
                if acc and acc != "OPEN":
                    continue
                raw_urls = []
                if isinstance(inst.get("url"), dict):
                    raw_urls.append(inst["url"].get("$"))
                for wr in _as_list(inst.get("webresource")):
                    if isinstance(wr, dict) and isinstance(wr.get("url"), dict):
                        raw_urls.append(wr["url"].get("$"))
                for raw_u in raw_urls:
                    c = candidate_https_url(raw_u)
                    if not allowed_url(c) or c in seen:
                        continue
                    seen.add(c)
                    h = (urlsplit(c).hostname or "").lower()
                    blocked_hint = ("dl.designresearchsociety.org" in h or "research.aalto.fi" in h)
                    rank = (2 if blocked_hint else (0 if direct_pdf_hint(c) else 1))
                    ranked.append((rank, c))
    ranked.sort()
    return [u for _, u in ranked[:8]]


def openaire_urls(doi: str) -> list[str]:
    short = normalize_doi(doi)
    if not short:
        return []
    ep = f"https://api.openaire.eu/search/publications?doi={quote(short, safe='')}&format=json"
    payload, _, _ = safe_request(ep, limit=1_500_000, accept="application/json")
    return parse_openaire_urls(json.loads(payload.decode("utf-8")))


def parse_core_urls(data: dict, short_doi: str) -> list[str]:
    if not isinstance(data, dict) or not short_doi:
        return []
    out: list[str] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        item_doi = normalize_doi(item.get("doi"))
        if item_doi != short_doi:
            id_matches = any(
                isinstance(ident, dict) and normalize_doi(ident.get("identifier")) == short_doi
                for ident in (item.get("identifiers") or [])
            )
            if not id_matches:
                continue
        cands = [item.get("downloadUrl")] + list(item.get("sourceFulltextUrls") or [])
        for l in item.get("links") or []:
            if isinstance(l, dict) and l.get("type") == "download":
                cands.append(l.get("url"))
        for raw_u in cands:
            c = candidate_https_url(raw_u)
            if allowed_url(c) and c not in out:
                out.append(c)
    return out[:6]


def core_urls(doi: str) -> list[str]:
    short = normalize_doi(doi)
    if not short:
        return []
    ep = f"https://api.core.ac.uk/v3/search/works/?q=doi%3A%22{quote(short, safe='')}%22&limit=5"
    payload, _, _ = safe_request(ep, limit=1_500_000, accept="application/json")
    return parse_core_urls(json.loads(payload.decode("utf-8")), short)


def _norm_oai_title(raw: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(raw or "").lower())).strip()


def parse_oai_ojs_records(xml_bytes: bytes) -> tuple[dict[str, list[str]], dict[str, list[str]], str]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_bytes)
    ns = {"oai": "http://www.openarchives.org/OAI/2.0/"}
    by_doi: dict[str, list[str]] = defaultdict(list)
    by_title: dict[str, list[str]] = defaultdict(list)
    for rec in root.findall(".//oai:record", ns):
        hdr = rec.find("oai:header", ns)
        if hdr is not None and hdr.attrib.get("status") == "deleted":
            continue
        titles = [e.text.strip() for e in rec.iter("{http://purl.org/dc/elements/1.1/}title") if e.text and e.text.strip()]
        ids = [e.text.strip() for e in rec.iter("{http://purl.org/dc/elements/1.1/}identifier") if e.text and e.text.strip()]
        rels = [e.text.strip() for e in rec.iter("{http://purl.org/dc/elements/1.1/}relation") if e.text and e.text.strip()]
        urls: list[str] = []
        for raw_u in rels + ids:
            cand = candidate_https_url(raw_u)
            if allowed_url(cand):
                dl = re.sub(r"/article/view/(\d+/\d+(?:[/?#].*)?)$", r"/article/download/\1", cand, flags=re.I)
                if allowed_url(dl) and dl not in urls:
                    urls.append(dl)
                if cand not in urls:
                    urls.append(cand)
        if not urls:
            continue
        for raw_id in ids:
            nd = normalize_doi(raw_id)
            if nd:
                for u in urls:
                    if u not in by_doi[nd]:
                        by_doi[nd].append(u)
        for raw_t in titles:
            nt = _norm_oai_title(raw_t)
            if len(nt) >= 18 and len(nt.split()) >= 3:
                for u in urls:
                    if u not in by_title[nt]:
                        by_title[nt].append(u)
    rt = root.find(".//oai:resumptionToken", ns)
    next_token = rt.text.strip() if rt is not None and rt.text else ""
    return dict(by_doi), dict(by_title), next_token


def oai_ojs_prefetch(
    endpoint: str = "https://archive.nordes.org/index.php/index/oai",
    pause_fn=None,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    by_doi: dict[str, list[str]] = defaultdict(list)
    by_title: dict[str, list[str]] = defaultdict(list)
    host = (urlsplit(endpoint).hostname or "").lower()
    token = ""
    for _ in range(30):
        u = f"{endpoint}?verb=ListRecords&resumptionToken={quote(token, safe='')}" if token else f"{endpoint}?verb=ListRecords&metadataPrefix=oai_dc"
        try:
            if pause_fn and host:
                pause_fn(host)
            payload, _, _ = safe_request(u, limit=6_000_000, accept="application/xml,text/xml")
            d_map, t_map, token = parse_oai_ojs_records(payload)
            for k, lst in d_map.items():
                for item in lst:
                    if item not in by_doi[k]:
                        by_doi[k].append(item)
            for k, lst in t_map.items():
                for item in lst:
                    if item not in by_title[k]:
                        by_title[k].append(item)
            if not token:
                break
        except Exception:
            break
    return dict(by_doi), dict(by_title)


def extract_diva_query(oa_url: object, ident: object = "") -> str:
    for raw in (oa_url, ident):
        s = str(raw or "").strip()
        if not s:
            continue
        m_urn = re.search(r"(urn:nbn:se:[a-z0-9_:.-]+)", s, re.I)
        if m_urn:
            return m_urn.group(1)
        m_pid = re.search(r"diva2:(\d+)", s, re.I)
        if m_pid:
            return f"diva2:{m_pid.group(1)}"
    return ""


def parse_diva_export_csv(csv_text: str, target_urn_or_pid: str = "") -> list[str]:
    if not csv_text or not csv_text.strip():
        return []
    target = str(target_urn_or_pid or "").strip().lower()
    target_pid = target.split("diva2:", 1)[1] if target.startswith("diva2:") else ""
    out: list[str] = []
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    for row in reader:
        if not isinstance(row, dict):
            continue
        if target:
            nbn = str(row.get("NBN") or "").strip().lower()
            pid = str(row.get("PID") or "").strip().lower()
            if nbn != target and (not target_pid or pid != target_pid) and pid != target:
                continue
        raw_blobs = f"{row.get('FullTextLink') or ''} ; {row.get('Urls') or ''}"
        for tok in re.split(r"[\s;]+", raw_blobs):
            c = candidate_https_url(tok)
            if allowed_url(c) and c not in out:
                out.append(c)
    return out[:6]


def diva_export_urls(oa_url: str, ident: str = "", pause_fn=None) -> list[str]:
    q = extract_diva_query(oa_url, ident)
    if not q:
        return []
    if pause_fn:
        pause_fn("www.diva-portal.org")
    aq = quote(json.dumps([[{"freeText": q}]]))
    ep = (
        "https://www.diva-portal.org/smash/export.jsf?format=csvall2&addFilename=false"
        f"&aq={aq}&aqe=[]&aq2=[[]]&onlyFullText=false&noOfRows=5"
    )
    payload, _, _ = safe_request(ep, limit=500_000, accept="text/csv,*/*")
    return parse_diva_export_csv(payload.decode("utf-8-sig", "replace"), q)


def semantic_scholar_batch_prefetch(dois: list[str], pause_fn=None) -> dict[str, list[dict[str, str]]]:
    clean = sorted({d for raw in dois if (d := normalize_doi(raw))})
    prefetched: dict[str, list[dict[str, str]]] = {}
    ep = "https://api.semanticscholar.org/graph/v1/paper/batch?fields=openAccessPdf,isOpenAccess,externalIds"
    for idx in range(0, len(clean), 100):
        chunk = clean[idx:idx + 100]
        body = json.dumps({"ids": [f"DOI:{d}" for d in chunk]}).encode("utf-8")
        for attempt in range(3):
            try:
                if pause_fn:
                    pause_fn("api.semanticscholar.org")
                payload, _, _ = safe_request(ep, limit=4_000_000, accept="application/json", data=body, content_type="application/json")
                items = json.loads(payload.decode("utf-8"))
                if not isinstance(items, list):
                    break
                for req_doi, item in zip(chunk, items):
                    prefetched[req_doi] = []
                    if not isinstance(item, dict):
                        continue
                    oa_obj = item.get("openAccessPdf") or {}
                    u = candidate_https_url(oa_obj.get("url") if isinstance(oa_obj, dict) else "")
                    if allowed_url(u):
                        lic = str((oa_obj.get("license") or "") if isinstance(oa_obj, dict) else "").strip()
                        prefetched[req_doi] = [{"url": u, "public_url": u, "license": lic}]
                break
            except Exception as exc:
                if isinstance(exc, HTTPError) and exc.code == 429 and attempt < 2:
                    time.sleep(25.0)
                    continue
                if isinstance(exc, HTTPError) and exc.code in (403, 429):
                    return prefetched
                break
    return prefetched


def core_batch_prefetch(dois: list[str], pause_fn=None, cache_path: Path | None = None) -> dict[str, list[str]]:
    high_val = ("10.21606/", "10.1080/", "10.1016/", "10.1145/", "10.1007/", "10.1386/", "10.1162/")
    clean = sorted({d for raw in dois if (d := normalize_doi(raw)) and '"' not in d}, key=lambda d: (not d.startswith(high_val), d))
    cached: dict[str, list[str]] = (read_json(cache_path, {}) or {}) if cache_path else {}
    todo = [d for d in clean if d not in cached]
    for idx in range(0, len(todo), 80):
        chunk = todo[idx:idx + 80]
        q = " OR ".join(f'doi:"{d}"' for d in chunk)
        body = json.dumps({"q": q, "limit": 100}).encode("utf-8")
        try:
            if pause_fn:
                pause_fn("api.core.ac.uk")
            payload, _, _ = safe_request(
                "https://api.core.ac.uk/v3/search/works",
                limit=4_000_000,
                accept="application/json",
                data=body,
                content_type="application/json",
            )
            data = json.loads(payload.decode("utf-8"))
            for d in chunk:
                cached[d] = parse_core_urls(data, d)
            if cache_path:
                write_json(cache_path, cached)
        except Exception as exc:
            if isinstance(exc, HTTPError) and exc.code in (403, 429):
                break
            continue
    return {d: cached[d] for d in clean if d in cached}


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
            "countries": w.get("countries") or ([w["source_country"]] if w.get("source_country") else []),
            "priority": w.get("review_priority") or "",
            "archived": "yes" if ident in archived else "no",
            "candidate_status": "archived" if ident in archived else (
                "oa-link-unchecked" if oa else "doi-only" if w.get("doi") else "no-oa-link"
            ),
        })
    rank = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda x: (
        x["archived"] == "yes",
        (("hdl.handle.net/11250/" in x["oa_url"] or "nva.sikt.no" in x["oa_url"]) and not x["doi"]),
        not (direct_pdf_hint(x["oa_url"]) or normalize_doi(x["doi"]).startswith(OA_DOI_PREFIXES)),
        not bool(x["oa_url"]),
        x["kind"] in ("dissertation", "book"),
        rank.get(x["priority"], 2),
        -(int(x["year"]) if str(x["year"]).isdigit() else 0),
        x["id"],
    ))
    return rows


def expand_registered_oa_urls(oa_url: str) -> list[str]:
    u = candidate_https_url(oa_url)
    if not allowed_url(u):
        return []
    out: list[str] = []
    m_arxiv = re.match(r"^https://arxiv\.org/abs/([0-9]+\.[0-9]+(?:v\d+)?|[a-z-]+/\d+)(?:[?#].*)?$", u, re.I)
    m_pmc = re.search(r"ncbi\.nlm\.nih\.gov/(?:pmc/)?articles/(?:PMC)?(\d+)", u, re.I)
    if m_arxiv:
        out.append(f"https://arxiv.org/pdf/{m_arxiv.group(1)}.pdf")
    elif m_pmc:
        pmcid = f"PMC{m_pmc.group(1)}"
        out.append(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/")
        out.append(f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf")
    elif ".hal.science/" in u.lower() and not u.lower().rstrip("/").endswith(("/document", ".pdf")):
        base_u = u.split("?", 1)[0].split("#", 1)[0].rstrip("/")
        out.append(f"{base_u}/document")
    if u not in out:
        out.append(u)
    return out


def load_local_openalex_urls(db_path: Path = RAW_SQLITE) -> dict[str, list[str]]:
    if not Path(db_path).is_file():
        return {}
    mapping: dict[str, list[str]] = {}
    try:
        conn = sqlite3.connect(db_path)
        for wid, rj in conn.execute("SELECT id, raw_json FROM works WHERE raw_json <> '{}'"):
            if not rj:
                continue
            try:
                raw_urls = extract_openalex_work_urls(json.loads(rj))
            except Exception:
                continue
            expanded: list[str] = []
            for raw_u in raw_urls:
                for eu in expand_registered_oa_urls(raw_u):
                    if eu not in expanded:
                        expanded.append(eu)
            if expanded:
                mapping[wid] = expanded
        conn.close()
    except Exception:
        return mapping
    return mapping


def _normalize_candidate(item: object, fallback_public: str = "") -> dict[str, str]:
    if isinstance(item, dict):
        u = candidate_https_url(item.get("url"))
        pub = candidate_https_url(item.get("public_url") or fallback_public or u)
        lic = str(item.get("license") or "").strip()[:120]
        return {"url": u, "public_url": pub, "license": lic}
    u = candidate_https_url(item)
    return {"url": u, "public_url": candidate_https_url(fallback_public or u), "license": ""}


def _deferred_retry_rank(row: dict, prev: dict) -> tuple[int, int]:
    reason = str(prev.get("reason") or "")
    url_hint = (row.get("oa_url") or "").lower()
    if any(k in reason for k in ("CERTIFICATE_VERIFY_FAILED", "timed out", "size cap", "interrupted")):
        return 0, 0
    if "11250/" in url_hint or any(h in url_hint for h in DSPACE_API_HOSTS):
        return 1, 0
    if row.get("doi") and ("403" in reason or "No direct PDF" in reason or "202" in reason):
        return 2, 0
    return 3, 1


def _discover_followup_candidates(payload: bytes, landing: str, mime: str, pause_fn=None) -> list[dict[str, str]]:
    if extract_nva_uuid(landing):
        cands = nva_publication_candidates(extract_nva_uuid(landing), pause_fn=pause_fn)
        if cands:
            return cands
    if extract_dspace_handle(landing)[0]:
        ds = dspace_api_urls(landing, pause_fn=pause_fn)
        if ds:
            return [_normalize_candidate(u) for u in ds]
    prefix = payload[:4096].lstrip().lower()
    if "html" in mime.lower() or b"<html" in prefix or b"<!doctype html" in prefix:
        return [_normalize_candidate(u) for u in pdf_candidates_from_html(payload, landing)]
    return []


def harvest_pdfs(*, limit: int = 8000, workers: int = 12, host_delay: float = 1.0,
                 email: str = DEFAULT_UNPAYWALL_EMAIL, max_mb: int = 90, max_cache_gb: float = 25.0,
                 min_free_gb: float = 6.0, retry_failed: bool = False,
                 lookup_openalex: bool = True, lookup_europepmc: bool = True,
                 lookup_crossref: bool = True, lookup_semantic_scholar: bool = True,
                 lookup_openaire: bool = True, lookup_core: bool = True,
                 lookup_nva_search: bool = True, lookup_nordes_oai: bool = True,
                 lookup_diva_export: bool = True,
                 new_sources_only: bool = False,
                 cache_dir: Path = PRIVATE_CACHE) -> int:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "pdf").mkdir(exist_ok=True)
    for stale in (cache_dir / "pdf").glob("*.partial.*"):
        stale.unlink(missing_ok=True)
    log_path = cache_dir / "progress.json"
    progress = read_json(log_path, {}) or {}
    rows = queue_rows()
    local_oa_map = load_local_openalex_urls()

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
        target_delay = max(host_delay, API_HOST_MIN_DELAYS.get(key, 0.0))
        with host_locks_guard:
            lock = host_locks.setdefault(key, threading.Lock())
        with lock:
            wait = max(0.0, target_delay - (time.monotonic() - host_last[key]))
            if wait > 0:
                time.sleep(wait)
            host_last[key] = time.monotonic()

    nordes_by_doi: dict[str, list[str]] = {}
    nordes_by_title: dict[str, list[str]] = {}
    if lookup_nordes_oai:
        print("NORDES_OAI_PREFETCH_START", flush=True)
        nordes_by_doi, nordes_by_title = oai_ojs_prefetch(pause_fn=pace_host)
        print("NORDES_OAI_PREFETCH_DONE", len(nordes_by_doi), len(nordes_by_title), flush=True)

    def _nordes_hits(row: dict) -> list[str]:
        hits: list[str] = []
        nd = normalize_doi(row.get("doi"))
        if nd and nd in nordes_by_doi:
            hits.extend(nordes_by_doi[nd])
        nt = _norm_oai_title(row.get("title"))
        if nt and nt in nordes_by_title:
            for u in nordes_by_title[nt]:
                if u not in hits:
                    hits.append(u)
        return hits

    def _row_diva_queries(row: dict) -> list[str]:
        qs: list[str] = []
        ident = row.get("id") or ""
        for cand_u in [row.get("oa_url"), *local_oa_map.get(ident, [])]:
            q = extract_diva_query(cand_u, ident)
            if q and q not in qs:
                qs.append(q)
        if not qs:
            q = extract_diva_query("", ident)
            if q:
                qs.append(q)
        return qs

    def _has_repo_retry_candidate(row: dict) -> bool:
        repo_hints = (
            "hdl.handle.net/", "trepo.tuni.fi/", "nva.sikt.no/", "helda.helsinki.fi/",
            "aaltodoc.aalto.fi/", "gupea.ub.gu.se/", "erepo.uef.fi/", "taju.uniarts.fi/",
            "ncbi.nlm.nih.gov/", "arxiv.org/", "hal.science/",
        )
        ident = row.get("id") or ""
        urls = [row.get("oa_url") or "", *local_oa_map.get(ident, [])]
        return any(h in str(u).lower() for u in urls for h in repo_hints)

    any_api = bool(
        email or lookup_openalex or lookup_europepmc or lookup_crossref
        or lookup_semantic_scholar or lookup_openaire or lookup_core or lookup_nva_search
        or lookup_nordes_oai or lookup_diva_export
    )
    untried_green_rows = []
    unvisited_rows = []
    deferred_rows = []
    for row in rows:
        ident = row["id"]
        if row["archived"] == "yes":
            continue
        prev = progress.get(ident) or {}
        st = prev.get("status")
        if st == "pdf-confirmed":
            if cached_pdf_ok(ident, prev, cache_dir) and not BOILERPLATE_PDF_RE.search(prev.get("url") or ""):
                continue
            progress.pop(ident, None)
            st = None
        has_nordes = bool(_nordes_hits(row))
        has_diva = bool(lookup_diva_export and _row_diva_queries(row))
        has_repo_retry = _has_repo_retry_candidate(row)
        if new_sources_only:
            if not has_nordes and not has_diva and not has_repo_retry and not (row.get("doi") and (lookup_semantic_scholar or lookup_core)):
                continue
        else:
            prim_oa = candidate_https_url(row["oa_url"])
            alt_local = [u for u in local_oa_map.get(ident, []) if u != prim_oa and "doi.org/" not in u]
            if (alt_local and not prev.get("local_oa_checked")) or has_nordes:
                untried_green_rows.append(row)
                if len(untried_green_rows) >= limit:
                    break
                continue
        if st == "failed" and not retry_failed:
            continue
        if not has_nordes and not has_diva and not has_repo_retry and not row["oa_url"] and not local_oa_map.get(ident) and not (any_api and row["doi"]):
            continue
        if st == "deferred" or (st == "failed" and retry_failed):
            rank = (-1, 0) if (has_nordes or has_diva or has_repo_retry) else _deferred_retry_rank(row, prev)
            deferred_rows.append((rank, row))
        else:
            unvisited_rows.append(row)
            if len(untried_green_rows) + len(unvisited_rows) >= limit:
                break
    deferred_rows.sort(key=lambda item: item[0])
    eligible = (untried_green_rows + unvisited_rows + [r for _, r in deferred_rows])[:limit]

    prefetched_oa = {}
    if lookup_openalex and not new_sources_only and eligible:
        dois = [r["doi"] for r in eligible if r.get("doi") and r["id"] not in local_oa_map]
        if dois:
            print("OPENALEX_PREFETCH_START", len(dois), flush=True)
            prefetched_oa = openalex_batch_prefetch(dois, pause_fn=pace_host)
            print("OPENALEX_PREFETCH_DONE", len(prefetched_oa), flush=True)

    prefetched_s2 = {}
    if lookup_semantic_scholar and eligible:
        all_dois = [r["doi"] for r in eligible if r.get("doi") and not _nordes_hits(r)]
        if all_dois:
            print("S2_PREFETCH_START", len(all_dois), flush=True)
            prefetched_s2 = semantic_scholar_batch_prefetch(all_dois, pause_fn=pace_host)
            print("S2_PREFETCH_DONE", len(prefetched_s2), sum(1 for v in prefetched_s2.values() if v), flush=True)

    prefetched_core = {}
    if lookup_core and eligible:
        all_dois = [r["doi"] for r in eligible if r.get("doi") and not _nordes_hits(r) and not prefetched_s2.get(normalize_doi(r["doi"]))]
        if all_dois:
            print("CORE_PREFETCH_START", len(all_dois), flush=True)
            prefetched_core = core_batch_prefetch(all_dois, pause_fn=pace_host, cache_path=cache_dir / "core_prefetch.json")
            print("CORE_PREFETCH_DONE", len(prefetched_core), sum(1 for v in prefetched_core.values() if v), flush=True)

    if new_sources_only:
        sources = ("nordes_oai", "diva_export", "local_openalex", "registered", "semantic_scholar", "core")
    else:
        sources = (
            "local_openalex",
            "nordes_oai",
            "diva_export",
            "registered",
            "unpaywall",
            "openaire",
            "openalex",
            "synthesized",
            "nva_search",
            "europepmc",
            "crossref",
            "semantic_scholar",
            "core",
        )
    api_sources = {"semantic_scholar", "unpaywall", "openalex", "europepmc", "crossref", "openaire", "core", "nva_search", "diva_export"}

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
        seen: set[str] = set()

        def _note_blocked_host(h: str) -> None:
            hl = (h or "").lower().strip()
            if not hl or hl in BLOCK_EXEMPT_REDIRECTORS or hl.endswith(".amazonaws.com"):
                return
            with state_lock:
                blocked_hosts.add(hl)

        def try_direct_fetch(cand: dict[str, str], allow_followup: bool) -> tuple[bytes, str, str] | None:
            nonlocal deferred, why
            target = cand["url"]
            if not allowed_url(target) or target in seen:
                return None
            host = (urlsplit(target).hostname or "").lower()
            with state_lock:
                if host in blocked_hosts:
                    deferred = True
                    return None
            seen.add(target)
            try:
                pace_host(host)
                payload, landing, mime = safe_request(target, limit=max_bytes)
            except BotChallengeError as exc:
                why = f"BotChallenge: {str(exc)[:120]}"
                m_bh = re.search(r"on ([a-z0-9.-]+)$", str(exc), re.I)
                _note_blocked_host(m_bh.group(1) if m_bh else host)
                deferred = True
                return None
            except Exception as exc:
                why = f"{type(exc).__name__}: {str(exc)[:140]}"
                if isinstance(exc, HTTPError) and exc.code == 429:
                    err_h = (urlsplit(getattr(exc, "url", "") or target).hostname or host).lower()
                    _note_blocked_host(err_h)
                    deferred = True
                return None

            lhost = (urlsplit(landing).hostname or "").lower()
            payload = unwrap_pdf_payload(payload)
            if pdf_data(payload):
                pub_url = cand["public_url"] if (safe_public_link(cand["public_url"]) and not safe_public_link(landing)) else landing
                return payload, pub_url, cand["license"]

            if is_bot_challenge_html(payload):
                why = f"BotChallenge: {lhost or host}"
                _note_blocked_host(lhost or host)
                deferred = True
                return None

            if not allow_followup:
                return None

            for sub in _discover_followup_candidates(payload, landing, mime, pause_fn=pace_host):
                res = try_direct_fetch(sub, allow_followup=False)
                if res:
                    return res
            return None

        for src in sources:
            if success or stop_event.is_set():
                break
            with state_lock:
                if src in blocked_sources:
                    deferred = True
                    continue
            try:
                if src == "local_openalex":
                    raw_cands = []
                    for u in local_oa_map.get(ident, []):
                        for eu in expand_registered_oa_urls(u):
                            if eu not in raw_cands:
                                raw_cands.append(eu)
                elif src == "nordes_oai":
                    raw_cands = _nordes_hits(row)
                elif src == "diva_export":
                    dqs = _row_diva_queries(row) if lookup_diva_export else []
                    if not dqs:
                        continue
                    raw_cands = []
                    for dq in dqs[:3]:
                        for u in diva_export_urls(dq, ident, pause_fn=pace_host):
                            if u not in raw_cands:
                                raw_cands.append(u)
                elif src == "registered":
                    raw_cands = expand_registered_oa_urls(row["oa_url"]) if row["oa_url"] else []
                elif src == "unpaywall":
                    if not email or not row["doi"]:
                        continue
                    pace_host("api.unpaywall.org")
                    raw_cands = unpaywall_urls(row["doi"], email)
                elif src == "openaire":
                    if not lookup_openaire or not row["doi"]:
                        continue
                    pace_host("api.openaire.eu")
                    raw_cands = openaire_urls(row["doi"])
                elif src == "openalex":
                    if not lookup_openalex or not row["doi"] or ident in local_oa_map:
                        continue
                    nd = normalize_doi(row["doi"])
                    if nd in prefetched_oa:
                        raw_cands = prefetched_oa[nd]
                    else:
                        pace_host("api.openalex.org")
                        raw_cands = openalex_urls(row["doi"])
                elif src == "synthesized":
                    raw_cands = synthesized_oa_urls(row["doi"]) if row["doi"] else []
                elif src == "nva_search":
                    nd = normalize_doi(row["doi"])
                    if not lookup_nva_search or not nd or ("NO" not in (row.get("countries") or []) and not nd.startswith(NO_DOI_PREFIXES)):
                        continue
                    pace_host("api.nva.unit.no")
                    raw_cands = nva_search_candidates(row["doi"], pause_fn=pace_host)
                elif src == "europepmc":
                    if not lookup_europepmc or not row["doi"]:
                        continue
                    pace_host("www.ebi.ac.uk")
                    raw_cands = europepmc_urls(row["doi"])
                elif src == "crossref":
                    if not lookup_crossref or not row["doi"]:
                        continue
                    pace_host("api.crossref.org")
                    raw_cands = crossref_urls(row["doi"])
                elif src == "semantic_scholar":
                    if not lookup_semantic_scholar or not row["doi"]:
                        continue
                    nd = normalize_doi(row["doi"])
                    if nd in prefetched_s2:
                        raw_cands = prefetched_s2[nd]
                    elif prefetched_s2:
                        deferred = True
                        continue
                    else:
                        pace_host("api.semanticscholar.org")
                        raw_cands = semantic_scholar_urls(row["doi"])
                elif src == "core":
                    if not lookup_core or not row["doi"]:
                        continue
                    nd = normalize_doi(row["doi"])
                    if nd in prefetched_core:
                        raw_cands = prefetched_core[nd]
                    elif prefetched_core:
                        deferred = True
                        continue
                    else:
                        pace_host("api.core.ac.uk")
                        raw_cands = core_urls(row["doi"])
            except Exception as exc:
                if isinstance(exc, HTTPError) and exc.code in (403, 429) and src in api_sources:
                    with state_lock:
                        blocked_sources.add(src)
                    deferred = True
                continue

            for raw_item in raw_cands[:10]:
                cand = _normalize_candidate(raw_item, row["oa_url"])
                res = try_direct_fetch(cand, allow_followup=True)
                if res:
                    success = res
                    break

        if success:
            payload, final_url, lic = success
            sha = hashlib.sha256(payload).hexdigest()
            pdf_file = cache_path(ident, cache_dir)
            tmp = pdf_file.with_suffix(f".pdf.partial.{threading.get_ident()}")
            tmp.write_bytes(payload)
            os.replace(tmp, pdf_file)
            with state_lock:
                progress[ident] = {
                    "status": "pdf-confirmed",
                    "url": final_url,
                    "sha256": sha,
                    "bytes": len(payload),
                    "license": lic,
                    "local_oa_checked": True,
                    "checked_at": now_iso(),
                }
                used_bytes += len(payload)
                dirty += 1
                if workers == 1 or dirty >= 15:
                    write_json(log_path, progress)
                    dirty = 0
            print("PDF_OK", ident, len(payload), sha[:12], flush=True)
        else:
            with state_lock:
                progress[ident] = {
                    "status": "deferred" if deferred else "failed",
                    "reason": why,
                    "local_oa_checked": True,
                    "checked_at": now_iso(),
                }
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
                "license": str(row.get("license") or "")[:120],
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
            "license": (rm.get("license", "") if rm else "") or (conf.get("license", "") if conf else ""),
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
