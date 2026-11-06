#!/usr/bin/env python3
"""Open-access PDF harvest for the Nordic design bibliography.

Offline (default): construct a complete retrieval queue and publish coverage stats.
Opt-in --download: download freely accessible PDF files into a GITIGNORED PRIVATE
cache. Do not publish a PDF unless its particular version is licence-reviewed.
Never use paywall bypasses, shadow libraries or authentication workarounds.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import tempfile
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parent
PRIVATE = Path(os.environ.get("DESIGNTEORI_PDF_CACHE", str(ROOT / "data" / "oa_fulltexts_private"))).expanduser().resolve()
QUEUE = ROOT / "results" / "pdf_henteko.csv"
STATS = ROOT / "docs" / "data" / "pdf_status.json"
FOUND = ROOT / "docs" / "data" / "pdf_found.json"
LOG = PRIVATE / "progress.json"
USER_AGENT = "Designteori-OA-Index/1.0 (+https://github.com/lukketsvane/designteori)"
FIELDS = ("id", "doi", "title", "year", "kind", "source", "oa_url", "scope",
          "priority", "archived", "candidate_status")
HOST_DENY = ("sci-hub", "libgen", "annas-archive", "z-library")
MAX_REDIRECTS = 5


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path, value):
    """Atomic progress writes: interruptions must not destroy harvested results."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def allowed_url(link):
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


def public_dns(host):
    """Reject private, reserved or unresolvable DNS targets before HTTP requests."""
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses:
            return False
        for entry in addresses:
            ip = ipaddress.ip_address(entry[4][0])
            if not ip.is_global:
                return False
        return True
    except (socket.gaierror, ValueError, OSError):
        return False


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PDFLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name", "").lower() in (
                "citation_pdf_url", "dc.relation.ispartof", "eprints.document_url"):
            self.urls.append(attrs.get("content", ""))
        if tag == "link":
            href = attrs.get("href", "")
            mime = (attrs.get("type") or "").lower()
            rel = (attrs.get("rel") or "").lower()
            if href and (mime == "application/pdf" or (
                    "alternate" in rel and re.search(r"\.pdf(?:[?#]|$)", href, re.I))):
                self.urls.append(href)
        if tag in ("iframe", "embed", "object"):
            link = attrs.get("src") or attrs.get("data") or ""
            mime = (attrs.get("type") or "").lower()
            if link and (mime == "application/pdf" or re.search(
                    r"(?:\.pdf(?:[?#]|$)|/bitstream/|/download(?:[/?#]|$))", link, re.I)):
                self.urls.append(link)
        if tag == "a":
            href = attrs.get("href", "")
            if re.search(r"(?:\.pdf(?:[?#]|$)|/download(?:[/?#]|$)|/bitstream/)", href, re.I):
                self.urls.append(href)


def safely_encoded_url(link):
    """Encode spaces/non-ASCII in public URLs and reject control characters.

    A relative PDF href can contain spaces. Keep already percent-escaped
    URLs intact, but never permit raw control characters or weaken HTTPS.
    """
    value = str(link or "")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("control characters in URL")
    return quote(value, safe=":/?#[]@!$&'()*+,;=%-._~")

def safe_request(url, limit=26_000_000, accept="application/pdf,*/*;q=0.5"):
    """Fetch a public HTTPS resource, with each redirect checked and a strict size cap."""
    opener = build_opener(NoRedirect)
    visited = set()
    for _ in range(MAX_REDIRECTS + 1):
        url = safely_encoded_url(url)
        if not allowed_url(url) or not public_dns(urlsplit(url).hostname) or url in visited:
            raise ValueError("unsafe URL or redirect")
        visited.add(url)
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
        response = None
        try:
            response = opener.open(req, timeout=25)
        except HTTPError as error:
            if error.code in (301, 302, 303, 307, 308):
                target = error.headers.get("Location")
                if not target:
                    raise ValueError("redirect without Location") from error
                url = urljoin(url, target)
                error.close()
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


def pdf_data(data):
    """Reject HTML and visibly incomplete PDF bodies."""
    return len(data) > 500 and data.lstrip()[:4] == b"%PDF" and b"%%EOF" in data[-4096:]


def cache_path(ident):
    return PRIVATE / "pdf" / (hashlib.sha256(ident.encode()).hexdigest()[:24] + ".pdf")


def cached_pdf_ok(ident, entry):
    if not entry or entry.get("status") != "pdf-confirmed":
        return False
    file = cache_path(ident)
    if not file.is_file() or file.stat().st_size != entry.get("bytes"):
        return False
    raw = file.read_bytes()
    return pdf_data(raw) and hashlib.sha256(raw).hexdigest() == entry.get("sha256")


def cache_summary(progress):
    found = [r for r in progress.values() if r.get("status") == "pdf-confirmed"]
    return {"cached": len(found), "bytes": sum(r.get("bytes", 0) for r in found),
            "failed": sum(r.get("status") == "failed" for r in progress.values()),
            "deferred": sum(r.get("status") == "deferred" for r in progress.values())}


def pdf_candidates_from_html(data, landing):
    parser = PDFLinks()
    try:
        parser.feed(data[:1_000_000].decode("utf-8", "ignore"))
    except Exception:
        return []
    urls = []
    for value in parser.urls:
        absolute = urljoin(landing, value)
        if allowed_url(absolute) and absolute not in urls:
            urls.append(absolute)
    return urls[:5]


def unpaywall_urls(doi, email):
    """Optional legal OA discovery; requires an email supplied by the operator."""
    if not email or "@" not in email or not doi:
        return []
    normal = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip(), flags=re.I)
    url = "https://api.unpaywall.org/v2/" + quote(normal, safe="/") + "?email=" + quote(email, safe="@.")
    payload, _, _ = safe_request(url, limit=1_000_000, accept="application/json")
    data = json.loads(payload.decode("utf-8"))
    if not data.get("is_oa"):
        return []
    locs = [data.get("best_oa_location")] + (data.get("oa_locations") or [])
    result = []
    for loc in locs:
        if not isinstance(loc, dict):
            continue
        for candidate in (loc.get("url_for_pdf"), loc.get("url")):
            if allowed_url(candidate) and candidate not in result:
                result.append(candidate)
    return result[:10]


def openalex_urls(doi):
    """Find diverse OA locations. Prefer repository PDFs over landing pages."""
    if not doi:
        return []
    short = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip(), flags=re.I)
    if not short.startswith("10."):
        return []
    url = "https://api.openalex.org/works/https://doi.org/" + quote(short, safe="/")
    payload, _, _ = safe_request(url, limit=1_500_000, accept="application/json")
    data = json.loads(payload.decode("utf-8"))
    locs = [data.get("best_oa_location"), data.get("primary_location")]
    locs.extend(data.get("locations") or [])
    candidates = {}
    for pos, loc in enumerate(locs):
        if not isinstance(loc, dict) or not loc.get("is_oa", False):
            continue
        source = loc.get("source") or {}
        repository = isinstance(source, dict) and source.get("type") == "repository"
        for link in (loc.get("pdf_url"), loc.get("landing_page_url")):
            if not allowed_url(link):
                continue
            pdf_shaped = direct_pdf_hint(link)
            rank = (0 if pdf_shaped and repository else
                    1 if pdf_shaped else
                    2 if repository else 3)
            key = (rank, pos)
            if link not in candidates or key < candidates[link]:
                candidates[link] = key
    oa = data.get("open_access") or {}
    alternate = oa.get("oa_url") if oa.get("is_oa") else None
    if allowed_url(alternate) and alternate not in candidates:
        candidates[alternate] = (4, len(locs))
    return [url for url, _ in sorted(candidates.items(), key=lambda item: item[1])][:12]


def semantic_scholar_urls(doi):
    """Optional public OA PDF location from Semantic Scholar's bibliographic API.

    A returned link is only a discovery lead. No licensing rights inferred.
    """
    if not doi:
        return []
    short = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip(), flags=re.I)
    if not re.fullmatch(r"10\.\d{4,9}/\S+", short, flags=re.I):
        return []
    endpoint = ("https://api.semanticscholar.org/graph/v1/paper/DOI:"
                + quote(short, safe="") + "?fields=openAccessPdf,isOpenAccess")
    payload, _, _ = safe_request(endpoint, limit=750_000, accept="application/json")
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        return []
    oa_pdf = data.get("openAccessPdf") or {}
    if not isinstance(oa_pdf, dict):
        return []
    url = oa_pdf.get("url")
    return [url] if allowed_url(url) else []


def direct_pdf_hint(link):
    """Sorting hint only: a URL shaped like a PDF is not a verified PDF."""
    return bool(re.search(r"(?:\.pdf(?:[?#]|$)|/content/pdf/|/track/pdf/|/article/download/|/bitstream/|/download(?:[/?#]|$))",
                          str(link or ""), re.I))


def queue_rows():
    published = read_json(ROOT / "fulltekst" / "manifest.json", {"items": []})
    archived = {entry["id"] for entry in published["items"]}
    base = read_json(ROOT / "docs" / "data" / "publications.json", [])
    additions = read_json(ROOT / "docs" / "data" / "nordic_additions.json", [])
    all_rows = []
    for w in base + additions:
        ident = w.get("id")
        if not ident:
            continue
        oa = w.get("oa_url") or ""
        repository_source = w.get("origin") == "external"
        if not oa and repository_source:
            oa = w.get("source_url") or ""
        if not allowed_url(oa):
            oa = ""
        row = {
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
                "oa-link-unchecked" if oa else "doi-only" if w.get("doi") else "no-oa-link"),
        }
        all_rows.append(row)
    # All records remain searchable; prioritize articles and known OA links.
    rank = {"high": 0, "medium": 1, "low": 2}
    all_rows.sort(key=lambda x: (
        x["archived"] == "yes", x["kind"] not in ("article", "review", "proceedings-article"),
        not bool(x["oa_url"]), not direct_pdf_hint(x["oa_url"]), rank.get(x["priority"], 3),
        -(int(x["year"]) if str(x["year"]).isdigit() else 0), x["id"]))
    return all_rows, published


def load_progress():
    raw = read_json(LOG, {})
    return raw if isinstance(raw, dict) else {}


def safe_public_link(url):
    """Do not publish time-limited or credential-bearing download URLs."""
    if not allowed_url(url):
        return False
    query = urlsplit(url).query.lower()
    secrets = ("token=", "access_token=", "api_key=", "apikey=", "signature=",
               "x-amz-", "x-goog-", "authorization=", "credential=", "session=", "expires=")
    return not any(term in query for term in secrets)


def remote_links(progress, published):
    originals = {
        item["id"]: {"url": item.get("original_fulltext_url", ""),
                     "status": "archived", "license": item.get("license", ""),
                     "sha256": item.get("sha256", "")}
        for item in published.get("items", [])
    }
    # GitHub CI has no access to the private PDF cache. Retain source links
    # previously confirmed locally rather than resetting them on each push.
    previous = read_json(FOUND, {}) or {}
    if isinstance(previous, dict):
        for ident, row in previous.items():
            if (isinstance(row, dict) and row.get("status") == "private-cache-only"
                    and safe_public_link(row.get("url"))
                    and re.fullmatch(r"[a-f0-9]{64}", str(row.get("sha256", "")))):
                originals.setdefault(ident, row)
    for ident, row in progress.items():
        if row.get("status") == "pdf-confirmed" and safe_public_link(row.get("url")):
            originals.setdefault(ident, {
                "url": row["url"], "status": "private-cache-only",
                "sha256": row.get("sha256", ""), "license": "",
            })
    return originals


def publish(rows, published, progress):
    links = remote_links(progress, published)
    summary = {
        "openalex_and_nordic_candidates": len(rows),
        "archived_licensed_pdfs": len(published["items"]),
        "oa_links_unchecked": sum(r["candidate_status"] == "oa-link-unchecked" for r in rows),
        "direct_pdf_shaped_urls_unchecked": sum(r["candidate_status"] == "oa-link-unchecked" and direct_pdf_hint(r["oa_url"]) for r in rows),
        "repository_page_candidates": sum(r["scope"] == "repository-candidate" and bool(r["oa_url"]) for r in rows),
        "doi_without_oa_link": sum(r["candidate_status"] == "doi-only" for r in rows),
        "without_doi_or_oa": sum(r["candidate_status"] == "no-oa-link" for r in rows),
        "private_cached_pdfs": sum(x.get("status") == "pdf-confirmed" for x in progress.values()),
        "public_verified_pdf_links": len(links),
        "note": "Open access metadata is not proof of a readable PDF or a redistribution license.",
    }
    write_json(FOUND, links)
    write_json(STATS, summary)
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with QUEUE.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print("PDF_QUEUE", json.dumps(summary, ensure_ascii=False))
    return summary


def download(rows, progress, *, limit, email, pause, max_bytes, retry_failed, lookup_openalex,
             lookup_semantic_scholar=False, max_cache_bytes=None, min_free_bytes=0):
    PRIVATE.mkdir(parents=True, exist_ok=True)
    pdf_dir = PRIVATE / "pdf"
    pdf_dir.mkdir(exist_ok=True)
    tried = 0
    last_request = 0.0
    blocked_sources = set()
    blocked_hosts = set()

    def pace():
        nonlocal last_request
        time.sleep(max(0, pause - (time.monotonic() - last_request)))
        last_request = time.monotonic()

    for row in rows:
        ident = row["id"]
        if row["archived"] == "yes":
            continue
        if progress.get(ident, {}).get("status") == "pdf-confirmed":
            if cached_pdf_ok(ident, progress[ident]):
                continue
            print("RETRY_MISSING_OR_CORRUPT_CACHE", ident, flush=True)
            progress.pop(ident)
        if progress.get(ident, {}).get("status") == "failed" and not retry_failed:
            continue
        if tried >= limit:
            break
        if not row["oa_url"] and not ((email or lookup_openalex) and row["doi"]):
            continue
        used = sum(int(r.get("bytes", 0)) for r in progress.values()
                   if r.get("status") == "pdf-confirmed")
        available = shutil.disk_usage(PRIVATE).free
        if ((max_cache_bytes is not None and used + max_bytes > max_cache_bytes)
                or available - max_bytes < min_free_bytes):
            print("STORAGE_LIMIT", json.dumps({"cached_bytes": used,
                  "free_bytes": available, "max_bytes": max_cache_bytes}), flush=True)
            write_json(LOG, progress)
            break
        tried += 1
        success = None
        deferred = False
        why = "No direct PDF at public OA sources"
        seen = set()
        # Search the registered OA link first, and only then call outside APIs.
        # This greatly reduces traffic against OA discovery services.
        for source in ("registered", "unpaywall", "openalex", "semantic_scholar"):
            if success:
                break
            if source in blocked_sources:
                deferred = True
                continue
            if source == "registered":
                candidates = [row["oa_url"]] if row["oa_url"] else []
            elif source == "unpaywall":
                if not email or not row["doi"]:
                    continue
                try:
                    pace()
                    candidates = unpaywall_urls(row["doi"], email)
                except (ValueError, URLError, HTTPError, TimeoutError, OSError,
                        json.JSONDecodeError) as exc:
                    print("UNPAYWALL_FAIL", ident, type(exc).__name__, flush=True)
                    if isinstance(exc, HTTPError) and exc.code == 429:
                        print("RATE_LIMIT", source, "skip this API for this batch", flush=True)
                        blocked_sources.add(source)
                        deferred = True
                        why = "rate-limited API: " + source
                    continue
            elif source == "openalex":
                if not lookup_openalex or not row["doi"]:
                    continue
                try:
                    pace()
                    candidates = openalex_urls(row["doi"])
                except (ValueError, URLError, HTTPError, TimeoutError, OSError,
                        json.JSONDecodeError) as exc:
                    print("OPENALEX_FAIL", ident, type(exc).__name__, flush=True)
                    if isinstance(exc, HTTPError) and exc.code == 429:
                        print("RATE_LIMIT", source, "skip this API for this batch", flush=True)
                        blocked_sources.add(source)
                        deferred = True
                        why = "rate-limited API: " + source
                    continue
            else:
                if not lookup_semantic_scholar or not row["doi"]:
                    continue
                try:
                    pace()
                    candidates = semantic_scholar_urls(row["doi"])
                except (ValueError, URLError, HTTPError, TimeoutError, OSError,
                        json.JSONDecodeError) as exc:
                    if not isinstance(exc, HTTPError) or exc.code != 404:
                        print("SEMANTIC_SCHOLAR_FAIL", ident, type(exc).__name__, flush=True)
                    if isinstance(exc, HTTPError) and exc.code in (403, 429):
                        print("API_UNAVAILABLE", source, "skip this API for this batch", flush=True)
                        blocked_sources.add(source)
                        deferred = True
                        why = "rate-limited or restricted API: " + source
                    continue
            for target in candidates[:10]:
                if not allowed_url(target) or target in seen:
                    continue
                host = urlsplit(target).hostname
                if host in blocked_hosts:
                    deferred = True
                    continue
                seen.add(target)
                try:
                    pace()
                    payload, landing, mime = safe_request(target, limit=max_bytes)
                    if pdf_data(payload):
                        success = (payload, landing)
                        break
                    prefix = payload[:4096].lstrip().lower()
                    if ("html" not in mime.lower() and b"<html" not in prefix
                            and b"<!doctype html" not in prefix):
                        continue
                    for destination in pdf_candidates_from_html(payload, landing):
                        if destination in seen:
                            continue
                        destination_host = urlsplit(destination).hostname
                        if destination_host in blocked_hosts:
                            deferred = True
                            continue
                        seen.add(destination)
                        try:
                            pace()
                            candidate, resolved, _ = safe_request(destination, limit=max_bytes)
                            if pdf_data(candidate):
                                success = (candidate, resolved)
                                break
                        except (ValueError, URLError, HTTPError, TimeoutError, OSError) as exc:
                            why = type(exc).__name__ + ": " + str(exc)[:140]
                            if isinstance(exc, HTTPError) and exc.code == 429:
                                blocked_hosts.add(destination_host)
                                deferred = True
                                print("RATE_LIMIT", destination_host, "defer host", flush=True)
                    if success:
                        break
                except (ValueError, URLError, HTTPError, TimeoutError, OSError) as exc:
                    why = type(exc).__name__ + ": " + str(exc)[:140]
                    if isinstance(exc, HTTPError) and exc.code == 429:
                        blocked_hosts.add(host)
                        deferred = True
                        print("RATE_LIMIT", host, "defer host", flush=True)
        if success:
            payload, url = success
            sha = hashlib.sha256(payload).hexdigest()
            pdf_path = cache_path(ident)
            tmp = pdf_path.with_suffix(".pdf.partial")
            tmp.write_bytes(payload)
            os.replace(tmp, pdf_path)
            progress[ident] = {"status": "pdf-confirmed", "url": url,
                               "sha256": sha, "bytes": len(payload), "checked_at": now()}
            print("PDF_OK", ident, len(payload), sha[:12], flush=True)
        else:
            progress[ident] = {"status": "deferred" if deferred else "failed",
                               "reason": why, "checked_at": now()}
            print("PDF_DEFERRED" if deferred else "PDF_MISSING", ident, why, flush=True)
        write_json(LOG, progress)
    print("CACHE_SUMMARY", json.dumps(cache_summary(progress)), flush=True)
    return tried


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true",
                        help="Explicitly fetch legitimate OA PDFs to gitignored private cache")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--email", default="", help="Email for optional Unpaywall DOI lookup")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-mb", type=int, default=25)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--shards", type=int, default=1, help="Number of stable queue partitions")
    parser.add_argument("--shard", type=int, default=0, help="Zero-based partition to process")
    parser.add_argument("--max-cache-gb", type=float, default=30.0,
                        help="Private PDF storage budget in decimal gigabytes")
    parser.add_argument("--min-free-gb", type=float, default=2.0,
                        help="Free disk space to reserve")
    parser.add_argument("--lookup-openalex", action="store_true", help="Consult OpenAlex for additional legal OA locations")
    parser.add_argument("--lookup-semantic-scholar", action="store_true",
                        help="Optional Semantic Scholar openAccessPdf fallback")
    args = parser.parse_args()
    if (args.limit < 1 or args.delay < 0.5 or not 1 <= args.max_mb <= 50
            or args.shards < 1 or not 0 <= args.shard < args.shards
            or args.max_cache_gb < 0.1 or args.min_free_gb < 0):
        parser.error("Invalid limit, delay, max-mb, shards or storage limits")
    rows, published = queue_rows()
    progress = load_progress()
    if args.download:
        selected = [r for r in rows if
            int(hashlib.sha256(r["id"].encode()).hexdigest()[:12], 16) % args.shards == args.shard]
        print("SHARD", args.shard, "/", args.shards, "eligible", len(selected))
        tried = download(selected, progress, limit=args.limit, email=args.email,
                         pause=args.delay, max_bytes=args.max_mb * 1_000_000,
                         retry_failed=args.retry_failed, lookup_openalex=args.lookup_openalex,
                         lookup_semantic_scholar=args.lookup_semantic_scholar,
                         max_cache_bytes=int(args.max_cache_gb * 1_000_000_000),
                         min_free_bytes=int(args.min_free_gb * 1_000_000_000))
        print("ATTEMPTED", tried)
    publish(rows, published, progress)


if __name__ == "__main__":
    main()
