#!/usr/bin/env python3
"""Audit unverified NVA handle URLs from docs/data/pdf_katalog.json.

Follows HTTP redirects from hdl.handle.net to https://nva.sikt.no/registration/<uuid>,
queries https://api.nva.unit.no/publication/<uuid> with polite rate pacing,
and verifies open artifacts and DOI availability.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_USER_AGENT = "Designteori/3.0 (+https://github.com/lukketsvane/designteori; mailto:designteori-research@outlook.com)"
NVA_API_BASE = "https://api.nva.unit.no/publication"
NVA_REG_RE = re.compile(
    r"^https://(?:nva\.sikt\.no/registration|api\.nva\.unit\.no/publication)/([0-9a-f]+(?:-[0-9a-f]+){3,})(?:[/?#]|$)",
    re.I,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_uuid(url: str) -> str:
    m = NVA_REG_RE.search(str(url or "").strip())
    if m:
        return m.group(1)
    # Fallback: check any 36+ hex/dash UUID pattern in URL
    m2 = re.search(r"([0-9a-f]{8,}(?:-[0-9a-f]+){3,})", str(url or "").strip(), re.I)
    return m2.group(1) if m2 else ""


class RateLimiter:
    """Thread-safe polite host rate limiter."""

    def __init__(self, min_delay: float = 0.25):
        self.min_delay = min_delay
        self.last_called: dict[str, float] = {}
        self.lock = threading.Lock()

    def pace(self, host: str):
        with self.lock:
            now = time.monotonic()
            last = self.last_called.get(host, 0.0)
            elapsed = now - last
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
            self.last_called[host] = time.monotonic()


def resolve_handle_redirect(handle_url: str, user_agent: str, timeout: float = 15.0) -> tuple[str, str, str | None]:
    """Resolve handle URL and follow redirects to find final registration URL."""
    try:
        req = urllib.request.Request(
            handle_url,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            return final_url, extract_uuid(final_url), None
    except urllib.error.HTTPError as err:
        return "", "", f"HTTPError {err.code}: {err.reason}"
    except Exception as exc:
        return "", "", f"{type(exc).__name__}: {str(exc)[:120]}"


def fetch_nva_publication(
    uuid: str,
    user_agent: str,
    limiter: RateLimiter,
    timeout: float = 15.0,
) -> tuple[dict | None, str | None]:
    """Query NVA publication API endpoint for publication metadata."""
    if not uuid:
        return None, "Missing publication UUID"
    limiter.pace("api.nva.unit.no")
    ep = f"{NVA_API_BASE}/{urllib.parse.quote(uuid, safe='')}"
    try:
        req = urllib.request.Request(
            ep,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data, None
    except urllib.error.HTTPError as err:
        return None, f"HTTPError {err.code}: {err.reason}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:120]}"


def audit_item(item: dict, user_agent: str, limiter: RateLimiter, timeout: float = 15.0) -> dict:
    """Audit single catalog entry containing an unverified NVA handle."""
    wid = item.get("id") or ""
    handle_url = item.get("oa_location_unverified") or ""
    original_doi = (item.get("doi") or "").strip()
    title = item.get("title") or ""
    year = item.get("year")

    limiter.pace("hdl.handle.net")
    final_url, uuid, red_err = resolve_handle_redirect(handle_url, user_agent, timeout=timeout)

    record = {
        "id": wid,
        "handle_url": handle_url,
        "title": title,
        "year": year,
        "original_doi": original_doi,
        "resolved_registration_url": final_url,
        "nva_uuid": uuid,
        "resolution_status": "unverified",
        "open_file_count": 0,
        "open_files": [],
        "doi_found": None,
        "doi_backfilled": False,
        "audited_at": now_iso(),
        "error": None,
    }

    if red_err or not uuid:
        record["resolution_status"] = "redirect_failed"
        record["error"] = red_err or "Could not extract NVA UUID from redirect"
        return record

    pub_data, api_err = fetch_nva_publication(uuid, user_agent, limiter, timeout=timeout)
    if api_err or not pub_data:
        if "404" in str(api_err):
            record["resolution_status"] = "publication_not_found"
        else:
            record["resolution_status"] = "error"
        record["error"] = api_err
        return record

    # Check DOI in NVA publication entityDescription
    ed = pub_data.get("entityDescription") or {}
    ref = ed.get("reference") or {}
    doi = ref.get("doi")
    if doi and isinstance(doi, str):
        record["doi_found"] = doi.strip()
        if not original_doi:
            record["doi_backfilled"] = True

    # Check associatedArtifacts for open files
    artifacts = pub_data.get("associatedArtifacts") or []
    open_files = []
    for art in artifacts:
        if not isinstance(art, dict):
            continue
        atype = art.get("type")
        if atype == "OpenFile":
            fname = str(art.get("name") or "").strip()
            mime = str(art.get("mimeType") or "").lower()
            fid = str(art.get("identifier") or "").strip()
            size = art.get("size")
            lic = art.get("license")
            lic_val = lic.get("value") if isinstance(lic, dict) else str(lic or "")
            is_pdf = "pdf" in mime or fname.lower().endswith(".pdf")
            open_files.append({
                "identifier": fid,
                "name": fname,
                "mimeType": mime,
                "size": size,
                "license": lic_val,
                "is_pdf": is_pdf,
            })

    record["open_file_count"] = len(open_files)
    record["open_files"] = open_files

    if any(f.get("is_pdf") for f in open_files):
        record["resolution_status"] = "verified_oa_pdf"
    elif open_files:
        record["resolution_status"] = "verified_oa_artifact"
    else:
        record["resolution_status"] = "landing_verified_no_open_file"

    return record


def run_audit(
    catalog_path: Path = ROOT / "docs" / "data" / "pdf_katalog.json",
    output_path: Path = ROOT / "docs" / "data" / "nva_audit_report.json",
    limit: int = 0,
    workers: int = 8,
    delay: float = 0.25,
    user_agent: str = DEFAULT_USER_AGENT,
    resume: bool = True,
) -> dict:
    catalog_path = Path(catalog_path)
    output_path = Path(output_path)

    with catalog_path.open(encoding="utf-8") as f:
        catalog = json.load(f)

    items = catalog.get("items") or []
    target_items = [
        item for item in items
        if item.get("id", "").startswith("nordic:nva:")
        and "hdl.handle.net" in (item.get("oa_location_unverified") or "")
        and item.get("access_status") == "metadata_oa_location_unverified"
    ]
    target_count = len(target_items)
    print(f"Loaded catalog: found {target_count} unverified NVA handle entries.", flush=True)

    existing_items: dict[str, dict] = {}
    if resume and output_path.is_file():
        try:
            with output_path.open(encoding="utf-8") as f:
                prev_data = json.load(f)
            for prev_item in prev_data.get("items") or []:
                if prev_item.get("id") and prev_item.get("resolution_status") != "error":
                    existing_items[prev_item["id"]] = prev_item
            print(f"Resuming: found {len(existing_items)} already audited records.", flush=True)
        except Exception as e:
            print(f"Could not load resume data ({e}), starting fresh.", flush=True)

    to_audit = [item for item in target_items if item["id"] not in existing_items]
    if limit > 0:
        to_audit = to_audit[:limit]

    print(f"Items to audit in this run: {len(to_audit)} (workers={workers}, delay={delay}s)", flush=True)

    limiter = RateLimiter(min_delay=delay)
    completed_records = dict(existing_items)

    lock = threading.Lock()
    done_count = 0
    total_to_do = len(to_audit)

    def worker_fn(entry: dict):
        nonlocal done_count
        res = audit_item(entry, user_agent=user_agent, limiter=limiter)
        with lock:
            completed_records[res["id"]] = res
            done_count += 1
            if done_count % 25 == 0 or done_count == total_to_do:
                print(f"Progress: {done_count}/{total_to_do} audited ({len(completed_records)}/{target_count} total)", flush=True)
                # Incremental flush every 50 items
                if done_count % 50 == 0:
                    _save_report(output_path, catalog_path, target_count, completed_records)
        return res

    if to_audit:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(worker_fn, item) for item in to_audit]
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as exc:
                    print(f"Worker task error: {exc}", flush=True)

    report = _save_report(output_path, catalog_path, target_count, completed_records)
    print("Audit finished. Summary:", json.dumps(report["summary"], indent=2), flush=True)
    return report


def _save_report(output_path: Path, catalog_path: Path, target_count: int, completed_records: dict[str, dict]) -> dict:
    all_items = list(completed_records.values())
    all_items.sort(key=lambda x: x["id"])

    summary = {
        "landing_verified_no_open_file": sum(1 for x in all_items if x.get("resolution_status") == "landing_verified_no_open_file"),
        "verified_oa_pdf": sum(1 for x in all_items if x.get("resolution_status") == "verified_oa_pdf"),
        "verified_oa_artifact": sum(1 for x in all_items if x.get("resolution_status") == "verified_oa_artifact"),
        "doi_backfilled": sum(1 for x in all_items if x.get("doi_backfilled")),
        "redirect_failed": sum(1 for x in all_items if x.get("resolution_status") == "redirect_failed"),
        "publication_not_found": sum(1 for x in all_items if x.get("resolution_status") == "publication_not_found"),
        "error": sum(1 for x in all_items if x.get("resolution_status") == "error"),
    }

    report = {
        "audited_at": now_iso(),
        "catalog_source": str(catalog_path.relative_to(ROOT)).replace("\\", "/"),
        "target_handle_count": target_count,
        "audited_count": len(all_items),
        "summary": summary,
        "items": all_items,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    tmp_path.replace(output_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit 760 unverified NVA handle URLs from pdf_katalog.json")
    parser.add_argument("--catalog", type=Path, default=ROOT / "docs" / "data" / "pdf_katalog.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "data" / "nva_audit_report.json")
    parser.add_argument("--limit", type=int, default=0, help="Audit up to N items (0 = all)")
    parser.add_argument("--full", action="store_true", help="Audit all target items")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent workers")
    parser.add_argument("--delay", type=float, default=0.25, help="Per-host rate pacing delay")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume from existing report")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)

    args = parser.parse_args(argv)
    run_audit(
        catalog_path=args.catalog,
        output_path=args.output,
        limit=0 if args.full else args.limit,
        workers=args.workers,
        delay=args.delay,
        user_agent=args.user_agent,
        resume=not args.no_resume,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
