"""Integrity checks of docs/data/search/ for `python designteori.py verify` (CI safe: standard library only)."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import DOCS_DATA_DIR, PDF_DIR, REPO_RAW_BASE, read_json
from .search_build import DIM, K_NEIGHBOURS, LEX_MAX_BYTES, MAX_FILE_BYTES, SEARCH_DIR, SHARD_SIZE, build_id_of

REBUILD_HINT = "Køyr `python designteori.py build-search --stage lexical` og `--stage finish`"


def verify_search_files(base: Path | None = None) -> list[str]:
    """Returns a list of problems (empty when everything is consistent)."""
    base = Path(base) if base else SEARCH_DIR
    errors: list[str] = []
    meta = read_json(base / "meta.json")
    if not isinstance(meta, dict):
        return [f"search/meta.json is missing. {REBUILD_HINT}"]
    if meta.get("schema") != 1:
        errors.append(f"search/meta.json schema {meta.get('schema')} != 1")
    pubs = read_json(DOCS_DATA_DIR / "publications.json", []) or []
    nordic = read_json(DOCS_DATA_DIR / "nordic_additions.json", []) or []
    ids = [w["id"] for w in pubs] + [w["id"] for w in nordic]
    n = len(ids)
    if meta.get("n") != n or meta.get("ids") != ids:
        return errors + [f"search/meta.json does not match the order of publications.json + nordic_additions.json. {REBUILD_HINT}"]
    for key in ("lang", "abs", "acc", "flag"):
        if len(meta.get(key) or "") != n:
            errors.append(f"search/meta.json {key} has {len(meta.get(key) or '')} characters, expected {n}")
    files = meta.get("files") or {}
    for name, info in files.items():
        p = base / name
        if not p.is_file():
            errors.append(f"search/{name} listed in meta.json but missing")
            continue
        if p.stat().st_size != info.get("bytes"):
            errors.append(f"search/{name} size {p.stat().st_size} != meta.json {info.get('bytes')}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != info.get("sha256"):
            errors.append(f"search/{name} sha256 differs from meta.json. {REBUILD_HINT}")
    if files and build_id_of(files) != meta.get("build_id"):
        errors.append("search/meta.json build_id does not match its files")
    for p in base.rglob("*"):
        if p.is_file():
            limit = LEX_MAX_BYTES if p.name == "lex.json" else MAX_FILE_BYTES
            if p.stat().st_size > limit:
                errors.append(f"search/{p.relative_to(base)} is larger than {limit} bytes")
            if p.suffix.lower() == ".pdf":
                errors.append(f"PDF file under docs/data/search: {p.name}")
    if meta.get("vectors"):
        vp = base / "vectors.i8"
        if not vp.is_file() or vp.stat().st_size != n * DIM:
            errors.append(f"search/vectors.i8 must be {n * DIM} bytes")
    if meta.get("similar"):
        sp = base / "similar.bin"
        if not sp.is_file() or sp.stat().st_size != n * K_NEIGHBOURS * 3:
            errors.append(f"search/similar.bin must be {n * K_NEIGHBOURS * 3} bytes")

    # abstracts: source recorded, rights, consistency with meta.abs
    manifest = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items") or {}
    shard_ids: dict[str, dict] = {}
    for p in sorted((base / "abstracts").glob("a*.json")):
        shard_ids.update(read_json(p, {}) or {})
    pos = {wid: i for i, wid in enumerate(ids)}
    abs_chars = meta.get("abs") or ""
    for wid, rec in shard_ids.items():
        i = pos.get(wid)
        if i is None:
            errors.append(f"abstract for unknown work {wid}")
            continue
        s = rec.get("s")
        if s not in ("oa", "x") or not rec.get("l") or not rec.get("t"):
            errors.append(f"abstract record without source/language/text: {wid}")
            continue
        if abs_chars[i] != ("o" if s == "oa" else "x"):
            errors.append(f"meta.abs disagrees with the shard for {wid}")
        if s == "oa" and not wid.startswith("W"):
            errors.append(f"metadata abstract for a non-OpenAlex work: {wid}")
        if s == "x":
            if meta["acc"][i] not in ("h", "v"):
                errors.append(f"extracted abstract without verified open PDF: {wid}")
            if not rec.get("u"):
                errors.append(f"extracted abstract without source link: {wid}")
            if not (300 <= len(rec["t"]) <= 2500) or "�" in rec["t"]:
                errors.append(f"extracted abstract fails the quality limits: {wid}")
        if len(rec["t"]) > 5000:
            errors.append(f"abstract longer than 5000 characters: {wid}")
    if sum(1 for c in abs_chars if c != "0") != len(shard_ids):
        errors.append("meta.abs and the abstract shards hold different numbers of works")

    # access links
    access = (read_json(base / "access.json", {}) or {}).get("items") or {}
    found = read_json(DOCS_DATA_DIR / "pdf_found.json", {}) or {}
    for wid, row in access.items():
        i = pos.get(wid)
        if i is None:
            errors.append(f"access entry for unknown work {wid}")
            continue
        code = row[0]
        if code != meta["acc"][i]:
            errors.append(f"access code differs from meta.acc for {wid}")
        if code == "h":
            if wid not in manifest:
                errors.append(f"hosted copy not in pdf/manifest.json: {wid}")
            if row[1] != f"{REPO_RAW_BASE}/pdf/{wid}.pdf":
                errors.append(f"hosted url is not the repository file: {wid}")
        elif code == "v":
            if row[1] != (found.get(wid) or {}).get("url"):
                errors.append(f"verified url differs from pdf_found.json: {wid}")
    return errors
