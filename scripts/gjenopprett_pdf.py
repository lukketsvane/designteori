"""Last ned att PDF-ar som manglar på disk, men finst i korpus-databasen (documents + work_documents.original_url).

Ein fil blir godteken viss:
1. SHA-256 (rå eller etter DSpace multipart-utpakking) er lik den i `documents`-tabellen, ELLER
2. `--verify-text` er på: det er ei gyldig PDF-fil med same sidetal som `documents.pages` og teksten på
   prøvesider matchar `pages`-tabellen i `corpus.sqlite` (fangar dynamisk re-genererte PDF-ar frå Pure/VBN/LUP).

Ingenting blir overskrive. Med `--link-work-ids` lagast det i tillegg NTFS-hardlenkjer med 24-teikns
`sha256(work_id)[:24].pdf`-namn så `designteori.py` finn att alle filene utan ekstra diskplass.

Bruk: python scripts/gjenopprett_pdf.py [--workers 16] [--limit N] [--verify-text] [--link-work-ids]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from designteori import PRIVATE_CACHE, PRIVATE_CORPUS_DB, USER_AGENT  # noqa: E402
from designteori.pdf import pdf_data, unwrap_pdf_payload  # noqa: E402

OUT_DIR = PRIVATE_CACHE / "pdf"
LOG = PRIVATE_CACHE / "gjenopprett_pdf.log.jsonl"
MAX_BYTES = 200 * 1024 * 1024
WORD_RE = re.compile(r"[a-zæøåäöü0-9]{3,}", re.I)
_host_sems: dict[str, threading.Semaphore] = defaultdict(lambda: threading.Semaphore(2))
_lock = threading.Lock()


def wid_filename(work_id: str) -> str:
    return hashlib.sha256(work_id.encode("utf-8")).hexdigest()[:24] + ".pdf"


def have_hashes(db: sqlite3.Connection) -> set[str]:
    out: set[str] = set()
    by_name = {f.name: f for f in OUT_DIR.glob("*.pdf")}
    for name, f in by_name.items():
        if len(name) == 68 and name.endswith(".pdf"):
            out.add(name[:-4])
            continue
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
        out.add(h.hexdigest())
    for sha, wid in db.execute("select sha256, work_id from work_documents"):
        if wid_filename(wid) in by_name:
            out.add(sha)
    if (PRIVATE_CACHE / "gjenopprett_verified.json").is_file():
        for sha in json.loads((PRIVATE_CACHE / "gjenopprett_verified.json").read_text(encoding="utf8")):
            if (OUT_DIR / f"{sha}.pdf").is_file():
                out.add(sha)
    return out


def _words(text: str) -> set[str]:
    return set(WORD_RE.findall(text.lower())[:120])


def text_matches(data: bytes, expected_pages: int, db_pages: dict[int, str]) -> tuple[bool, str]:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        return False, "bad-pdf"
    try:
        if len(doc) != expected_pages:
            return False, f"pages-{len(doc)}vs{expected_pages}"
        best = 0.0
        checked = 0
        for pno, ref_txt in db_pages.items():
            if not (1 <= pno <= len(doc)):
                continue
            w_ref = _words(ref_txt)
            if len(w_ref) < 8:
                continue
            w_new = _words(doc[pno - 1].get_text())
            if not w_new:
                continue
            jac = len(w_ref & w_new) / max(1, len(w_ref | w_new))
            best = max(best, jac)
            checked += 1
        if checked == 0:
            return True, "pagecount-only"
        return (best >= 0.40), f"jac={best:.2f}"
    finally:
        doc.close()


def fetch(url: str, sha: str, expected_pages: int, db_pages: dict[int, str],
          verify_text: bool, timeout: float = 60.0) -> tuple[bool, str, bytes | None]:
    host = urlparse(url).netloc
    with _host_sems[host]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*;q=0.5"})
            deadline = time.time() + 150
            buf = bytearray()
            with urllib.request.urlopen(req, timeout=timeout) as r:
                while True:
                    block = r.read(1 << 18)
                    if not block:
                        break
                    buf += block
                    if len(buf) > MAX_BYTES or time.time() > deadline:
                        break
            data = bytes(buf)
            if time.time() > deadline:
                return False, "deadline", None
        except Exception as exc:  # noqa: BLE001
            return False, f"fetch-error:{type(exc).__name__}", None
        time.sleep(0.4)
    if len(data) > MAX_BYTES:
        return False, "too-large", None
    data = unwrap_pdf_payload(data)
    if not pdf_data(data):
        return False, "not-pdf", None
    if hashlib.sha256(data).hexdigest() == sha:
        return True, "sha-ok", data
    if verify_text and expected_pages > 0:
        ok, detail = text_matches(data, expected_pages, db_pages)
        if ok:
            return True, f"text-ok:{detail}", data
        return False, f"sha+text-mismatch:{detail}", None
    return False, "sha-mismatch", None


def link_work_ids(db: sqlite3.Connection) -> dict[str, int]:
    linked = skipped = missing_src = 0
    by_sha: dict[str, Path] = {}
    for f in OUT_DIR.glob("*.pdf"):
        if len(f.name) == 68 and f.name.endswith(".pdf"):
            by_sha[f.name[:-4]] = f
    for sha, wid in db.execute("select sha256, work_id from work_documents"):
        src = by_sha.get(sha)
        if not src or not src.exists():
            missing_src += 1
            continue
        dst = OUT_DIR / wid_filename(wid)
        if dst.exists():
            skipped += 1
            continue
        try:
            os.link(src, dst)
            linked += 1
        except OSError:
            skipped += 1
    return {"linked": linked, "already_or_skipped": skipped, "missing_src": missing_src}


def work(sha: str, urls: list[str], expected_pages: int, db_pages: dict[int, str], verify_text: bool) -> dict:
    last = "no-url"
    for url in urls:
        ok, why, data = fetch(url, sha, expected_pages, db_pages, verify_text)
        if ok and data is not None:
            tmp = OUT_DIR / f"{sha}.pdf.partial"
            tmp.write_bytes(data)
            tmp.replace(OUT_DIR / f"{sha}.pdf")
            return {"sha256": sha, "ok": True, "reason": why, "url": url, "bytes": len(data)}
        last = why
    return {"sha256": sha, "ok": False, "reason": last, "urls": urls[:3]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify-text", action="store_true")
    ap.add_argument("--link-work-ids", action="store_true")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(f"file:{PRIVATE_CORPUS_DB}?mode=ro", uri=True, timeout=60)

    if args.link_work_ids:
        print(json.dumps({"link_work_ids": link_work_ids(db)}, ensure_ascii=False), flush=True)

    doc_pages = {r[0]: int(r[1] or 0) for r in db.execute("select sha256, pages from documents")}
    urls: dict[str, list[str]] = defaultdict(list)
    for sha, url in db.execute("select sha256, original_url from work_documents where original_url is not null and original_url<>''"):
        if url not in urls[sha]:
            urls[sha].append(url)
    # Fallback URL-ar frå katalogen og progress.json viss original_url manglar eller feilar
    cat_file = ROOT / "docs/data/pdf_katalog.json"
    if cat_file.is_file():
        for item in json.loads(cat_file.read_text(encoding="utf8")).get("items", []):
            s = item.get("document_sha256")
            if s:
                for key in ("oa_location_unverified", "public_pdf_url"):
                    u = item.get(key)
                    if u and u not in urls[s]:
                        urls[s].append(u)

    present = have_hashes(db)
    todo = sorted(s for s in doc_pages if s not in present)
    print(json.dumps({"documents_in_db": len(doc_pages), "on_disk": len(set(doc_pages) & present),
                      "missing": len(todo), "missing_with_url": sum(1 for s in todo if urls.get(s))}), flush=True)
    if args.dry_run or not todo:
        return
    if args.limit:
        todo = todo[: args.limit]

    sample_pages: dict[str, dict[int, str]] = {}
    if args.verify_text:
        for s in todo:
            n = doc_pages[s]
            picks = sorted({1, min(2, n), max(1, n // 2)})
            sample_pages[s] = {
                p: t for p, t in db.execute(
                    f"select page, text from pages where sha256=? and page in ({','.join('?'*len(picks))})",
                    (s, *picks),
                )
            }

    verified_file = PRIVATE_CACHE / "gjenopprett_verified.json"
    verified_list = set(json.loads(verified_file.read_text(encoding="utf8"))) if verified_file.is_file() else set()
    done = ok = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex, open(LOG, "a", encoding="utf8") as log:
        futs = [ex.submit(work, s, urls.get(s, []), doc_pages[s], sample_pages.get(s, {}), args.verify_text) for s in todo]
        for fut in as_completed(futs):
            res = fut.result()
            done += 1
            if res["ok"]:
                ok += 1
                if str(res.get("reason", "")).startswith("text-ok"):
                    verified_list.add(res["sha256"])
            with _lock:
                log.write(json.dumps(res, ensure_ascii=False) + "\n")
                log.flush()
            if done % 50 == 0:
                print(json.dumps({"done": done, "ok": ok, "of": len(todo), "min": round((time.time() - t0) / 60, 1)}), flush=True)
    verified_file.write_text(json.dumps(sorted(verified_list)), encoding="utf8")
    if args.link_work_ids:
        print(json.dumps({"link_work_ids_after": link_work_ids(db)}, ensure_ascii=False), flush=True)
    print(json.dumps({"finished": True, "done": done, "restored": ok, "failed": done - ok}), flush=True)


if __name__ == "__main__":
    main()
