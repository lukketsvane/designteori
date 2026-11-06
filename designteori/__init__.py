"""DESIGNTEORI — Open, reproducible research corpus for Nordic design theory and research."""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import shutil
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
DOCS_DATA_DIR = DOCS_DIR / "data"
IMPORTS_DIR = ROOT / "imports"
PDF_DIR = ROOT / "pdf"

REPO_RAW_BASE = "https://raw.githubusercontent.com/lukketsvane/designteori/main"
REPO_BLOB_BASE = "https://github.com/lukketsvane/designteori/blob/main"

RAW_SQLITE = DATA_DIR / "nordic_design_research.sqlite"
RAW_SQLITE_GZ = DATA_DIR / "nordic_design_research.sqlite.gz"
UNIFIED_SQLITE_GZ = DATA_DIR / "designteori.sqlite.gz"

def _default_private_cache() -> Path:
    env_val = os.environ.get("DESIGNTEORI_PDF_CACHE")
    if env_val:
        return Path(env_val).expanduser().resolve()
    external_default = Path.home() / "Documents" / "designteori-pdf-cache"
    if external_default.is_dir():
        return external_default.resolve()
    return (DATA_DIR / "oa_fulltexts_private").resolve()


PRIVATE_CACHE = _default_private_cache()
PRIVATE_CORPUS_DB = PRIVATE_CACHE / "corpus.sqlite"
MODEL_CACHE_DIR = PRIVATE_CACHE / "models" / "embeddinggemma-300m-onnx"

NORDIC_COUNTRIES = ("NO", "SE", "DK", "FI", "IS")
USER_AGENT = "Designteori/3.0 (+https://github.com/lukketsvane/designteori)"

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;<>\"']+", re.I)
NON_ALNUM_RE = re.compile(r"[^\w]+", re.UNICODE)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_doi(value: object) -> str:
    text = str(value or "").strip().strip('"').strip("'")
    if not text:
        return ""
    text = unquote(text)
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I).strip()
    match = DOI_RE.search(text)
    if not match:
        return ""
    return match.group(0).rstrip(").,;/]").lower()


def doi_url(value: object) -> str:
    d = normalize_doi(value)
    return f"https://doi.org/{d}" if d else ""


def normalize_title(value: object) -> str:
    s = unicodedata.normalize("NFKD", str(value or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return NON_ALNUM_RE.sub(" ", s).strip()


def read_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value, *, compact: bool = False, sort_keys: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            if compact:
                json.dump(value, fh, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys)
            else:
                json.dump(value, fh, ensure_ascii=False, indent=2, sort_keys=sort_keys)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv_rows(path: Path, fieldnames: list[str] | tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def write_gzip_deterministic(source_file: Path, target_gz: Path) -> None:
    target_gz.parent.mkdir(parents=True, exist_ok=True)
    tmp = target_gz.with_suffix(target_gz.suffix + ".tmp")
    with source_file.open("rb") as src, tmp.open("wb") as raw_out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_out, mtime=0, compresslevel=9) as gz:
            shutil.copyfileobj(src, gz, 1024 * 1024)
    os.replace(tmp, target_gz)
