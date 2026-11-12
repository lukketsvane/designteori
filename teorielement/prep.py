"""Førebu inndata for teorielement-kodinga: éi tekstfil per dokument (samandrag/innleiing + konklusjon, med sidemerke).

Utdata blir liggande i den private cachen (ikkje i repoet), fordi radene inneheld korte sitat og det rettslege
grunnlaget for publisering ikkje er avklart.

Bruk: python teorielement/prep.py [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from designteori import PRIVATE_CACHE, PRIVATE_CORPUS_DB  # noqa: E402

WORK = PRIVATE_CACHE / "teorielement"
FRONT_CHARS = 14000
END_CHARS = 8000
CONCL_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s*)?(conclusions?|concluding\s+(?:remarks|discussion|reflections)|"
    r"discussion\s+and\s+conclusions?|summary\s+and\s+conclusions?|konklusjon(?:ar|er)?|avslutning|"
    r"avslutande\s+\w+|slutsats(?:er)?|sammanfattning|yhteenveto|johtop\w+|niðurstöður)\s*$",
    re.I | re.M,
)
REFS_RE = re.compile(r"^\s*(?:\d+\.?\s*)?(references|bibliography|referanser|litteratur(?:liste)?|referenser|källor|kirjallisuus|viðauki)\s*$", re.I | re.M)


def safe_filename(ident: str) -> str:
    """Sanitize identifier for cross-platform filesystem use (e.g. Windows colons)."""
    return re.sub(r'[<>:"/\\|?*]', '_', ident)


def clip(pages: list[tuple[int, str]], limit: int) -> list[tuple[int, str]]:
    out, used = [], 0
    for page, text in pages:
        if used >= limit:
            break
        room = limit - used
        out.append((page, text[:room]))
        used += min(len(text), room)
    return out


def render(parts: list[tuple[int, str]]) -> str:
    return "\n".join(f"\n===== SIDE {p} =====\n{t.strip()}" for p, t in parts if t.strip())


def build_end(pages: list[tuple[int, str]], front_last: int) -> list[tuple[int, str]]:
    n = len(pages)
    start = None
    for idx in range(n - 1, max(front_last, n // 3) - 1, -1):
        if CONCL_RE.search(pages[idx][1]):
            start = idx
            break
    if start is None:
        refs = next((i for i in range(n - 1, front_last, -1) if REFS_RE.search(pages[i][1])), n)
        start = max(front_last + 1, refs - 2)
    sel: list[tuple[int, str]] = []
    for page, text in pages[start:]:
        m = REFS_RE.search(text)
        if m:
            sel.append((page, text[: m.start()]))
            break
        sel.append((page, text))
    return clip(sel, END_CHARS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    cat = json.loads((ROOT / "docs/data/pdf_katalog.json").read_text(encoding="utf8"))["items"]
    by_sha: dict[str, list[dict]] = {}
    for item in cat:
        if item.get("document_sha256"):
            by_sha.setdefault(item["document_sha256"], []).append(item)

    (WORK / "input").mkdir(parents=True, exist_ok=True)
    (WORK / "output").mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(f"file:{PRIVATE_CORPUS_DB}?mode=ro", uri=True, timeout=60)
    docs = {r[0]: r for r in db.execute("select sha256,pages,quality from documents")}
    index: dict[str, dict] = {}
    skipped: list[dict] = []
    for sha, items in sorted(by_sha.items(), key=lambda kv: kv[1][0]["id"]):
        meta = items[0]
        safe_id = safe_filename(meta["id"])
        fname = f"{safe_id}.txt"
        d = docs.get(sha)
        if not d or d[2] != "extracted":
            skipped.append({"id": meta["id"], "safe_id": safe_id, "sha256": sha, "reason": "needs_ocr" if d else "missing"})
            continue
        target_path = WORK / "input" / fname
        if target_path.exists() and target_path.stat().st_size > 0:
            body_chars = len(target_path.read_text(encoding="utf8"))
        else:
            pages = [(p, t) for p, t in db.execute("select page,text from pages where sha256=? order by page", (sha,))]
            front = clip(pages, FRONT_CHARS)
            front_last = (front[-1][0] - 1) if front else 0
            end = [x for x in build_end(pages, front_last) if x[0] > (front[-1][0] if front else 0)]
            header = (
                f"ID: {meta['id']}\nTITTEL: {meta.get('title','')}\nÅR: {meta.get('year')}\n"
                f"DOI: {meta.get('doi','')}\nSIDER I PDF: {d[1]}\n"
            )
            body = header + "\n#### DEL A: FRAMSIDE, SAMANDRAG OG INNLEIING\n" + render(front)
            if end:
                body += "\n\n#### DEL B: KONKLUSJON / AVSLUTNING\n" + render(end)
            target_path.write_text(body, encoding="utf8")
            body_chars = len(body)
        index[safe_id] = {
            "id": meta["id"],
            "safe_id": safe_id,
            "file": fname,
            "sha256": sha,
            "chars": body_chars,
            "title": meta.get("title", ""),
            "year": meta.get("year"),
            "doi": meta.get("doi", ""),
            "license": meta.get("license", ""),
        }
        if args.limit and len(index) >= args.limit:
            break
    (WORK / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf8")
    (WORK / "skipped.json").write_text(json.dumps(skipped, ensure_ascii=False, indent=1), encoding="utf8")
    total = sum(i["chars"] for i in index.values())
    print(json.dumps({"documents": len(index), "skipped": len(skipped), "total_chars": total,
                      "avg_chars": total // max(1, len(index)), "dir": str(WORK)}, indent=1))


if __name__ == "__main__":
    main()
