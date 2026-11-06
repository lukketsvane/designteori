"""Offline import of existing PDF reading copies into the new legal OA harvester.

Hard-links local files when source/cache share a filesystem, avoiding a second
multi-gigabyte copy. All results are private, never published by this script.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
LOCAL_DEFAULT=ROOT.parent/"FORML-RE-datascience"/"research"/"nordisk-designforsking"/"data"/"oa_fulltexts_private"
CACHE_DEFAULT=Path.home()/"Documents"/"designteori-pdf-cache"

def pdf_is_valid(path):
    with path.open("rb") as fp:
        if not fp.read(512).lstrip().startswith(b"%PDF-"):
            return False
        fp.seek(max(0,path.stat().st_size-8192))
        if b"%%EOF" not in fp.read():
            return False
    try:
        import fitz
    except ImportError:
        return True
    with fitz.open(path) as doc:
        return doc.page_count>0 and not doc.is_encrypted

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=LOCAL_DEFAULT)
    parser.add_argument("--cache",type=Path,default=CACHE_DEFAULT)
    args=parser.parse_args()
    source=args.source.resolve()
    cache=args.cache.expanduser().resolve()
    if not source.is_dir():
        raise SystemExit("Missing local source directory: "+str(source))
    if cache.is_relative_to(ROOT):
        raise SystemExit("Refusing to keep private PDFs inside the public Git repo")
    by_id={r["id"]:r for r in json.loads((ROOT/"docs/data/publications.json").read_text(encoding="utf-8"))}
    cache.mkdir(parents=True,exist_ok=True)
    (cache/"pdf").mkdir(exist_ok=True)
    progress_path=cache/"progress.json"
    progress=json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.is_file() else {}
    copied=linked=existing=skipped=0
    now=datetime.now(timezone.utc).isoformat()
    for src in sorted(source.glob("W*.pdf")):
        id=src.stem
        if id not in by_id or not re.fullmatch(r"W\d+",id):
            skipped+=1
            continue
        if not pdf_is_valid(src):
            print("SKIP_INVALID",id)
            skipped+=1
            continue
        sha=hashlib.sha256(src.read_bytes()).hexdigest()
        name=hashlib.sha256(id.encode("utf-8")).hexdigest()[:24]+".pdf"
        target=cache/"pdf"/name
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest()!=sha:
                raise SystemExit("Existing PDF hash mismatch for "+id+". Manual review required.")
            existing+=1
        else:
            try:
                os.link(src,target)
                linked+=1
            except OSError:
                shutil.copy2(src,target)
                copied+=1
            assert hashlib.sha256(target.read_bytes()).hexdigest()==sha
        url=by_id[id].get("oa_url") or by_id[id].get("doi") or ""
        progress[id]={
            "status":"pdf-confirmed",
            "url":url if str(url).startswith("https://") else "",
            "sha256":sha,
            "bytes":src.stat().st_size,
            "checked_at":now,
            "note":"Imported from an earlier private local reading copy; redistribution rights not inferred."
        }
    tmp=cache/"progress.tmp"
    tmp.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(tmp,progress_path)
    count=sum(v.get("status")=="pdf-confirmed" for v in progress.values())
    print("LOCAL_PDF_IMPORT",{
        "source_count":len(list(source.glob("W*.pdf"))),
        "hardlinked_without_duplicate_disk_usage":linked,
        "copied":copied,
        "already_there":existing,
        "skipped":skipped,
        "verified_private_cache_entries":count,
        "cache_dir":str(cache),
        "rights": "NOT cleared for public redistribution"
    })

if __name__=="__main__":
    main()
