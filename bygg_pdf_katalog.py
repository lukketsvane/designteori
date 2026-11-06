"""Build a public index of legally mirrored PDFs and original OA locations.

Archive rights are taken only from the file-specific, audited manifest.
OpenAlex OA locations are discoverability hints, not licence confirmations.
Never download, copy or infer redistribution permission in this builder.
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv, json, urllib.parse

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/"fulltekst"/"manifest.json"
PUBLIC=ROOT/"docs"/"data"
def good_url(url):
    try:
        p=urllib.parse.urlsplit(str(url or "").strip())
        return p.scheme=="https" and bool(p.netloc) and not p.username and not p.password
    except ValueError:
        return False
def main():
    works=json.loads((PUBLIC/"publications.json").read_text(encoding="utf8"))
    nordic=json.loads((PUBLIC/"nordic_additions.json").read_text(encoding="utf8")) if (PUBLIC/"nordic_additions.json").exists() else []
    manifest=json.loads(MANIFEST.read_text(encoding="utf8"))
    found=json.loads((PUBLIC/"pdf_found.json").read_text(encoding="utf8")) if (PUBLIC/"pdf_found.json").exists() else {}
    licensed={r["id"]:r for r in manifest["items"]}
    rows=[]
    for w in works + nordic:
        id=w["id"]
        original_url=w.get("oa_url") or (w.get("source_url") if w.get("origin")=="external" else "") or ""
        confirmed=found.get(id) if isinstance(found,dict) else None
        confirmed_url=(confirmed.get("url") or "") if isinstance(confirmed,dict) else ""
        if not good_url(confirmed_url):
            confirmed_url=""
        r=licensed.get(id)
        if not original_url and not confirmed_url and not r:
            continue
        mirror_url=("https://github.com/lukketsvane/designteori/blob/main/fulltekst/"+r["pdf"]) if r else ""
        text_url=("https://github.com/lukketsvane/designteori/blob/main/fulltekst/"+r["text"]) if r and r["text"] else ""
        verified_pdf=bool(r or (confirmed and confirmed_url and confirmed.get("sha256")))
        best_oa=confirmed_url or (original_url if good_url(original_url) else "")
        rows.append({
            "id":id,
            "title":w["title"],
            "year":w["year"],
            "authors":w.get("authors",[]),
            "doi":w.get("doi") or "",
            "country_affiliations":w.get("countries") or ([w["source_country"]] if w.get("source_country") else []),
            "source":w.get("source") or "",
            "review_priority":w.get("review_priority") or "",
            "pdf_in_repo":bool(r),
            "verified_oa_pdf":verified_pdf,
            "public_pdf_url":mirror_url,
            "public_text_url":text_url,
            "oa_location_unverified":best_oa,
            "license":r["license"] if r else "",
            "license_url":r["license_url"] if r else "",
            "document_sha256":(r["sha256"] if r else (confirmed.get("sha256","") if confirmed else "")),
            "document_bytes":r["bytes"] if r else 0,
            "adapted_text_only":bool(r and r.get("derivative_notes")),
            "adaptation":r.get("derivative_notes") if r else "",
            "rights_status":"document_specific_license_checked" if r else "rights_not_reviewed",
            "access_status":("public_repo_mirror" if r else
                             "verified_oa_pdf_link" if verified_pdf else
                             "metadata_oa_location_unverified"),
        })
    rows.sort(key=lambda r:(not r["pdf_in_repo"],
                            not r["verified_oa_pdf"],
                            {"high":0,"medium":1,"low":2}.get(r["review_priority"],3),
                            -int(r.get("year") or 0),r["id"]))
    assert all(r["pdf_in_repo"] or r["oa_location_unverified"] for r in rows)
    assert sum(x["pdf_in_repo"] for x in rows)==manifest["count"]
    stats={
      "total_visible_entries":len(rows),
      "mirrored_licensed_pdf_count":manifest["count"],
      "verified_oa_pdf_count":sum(bool(r["verified_oa_pdf"]) for r in rows),
      "original_oa_location_links":sum(bool(r["oa_location_unverified"]) for r in rows),
      "original_oa_location_links_only":sum(not r["pdf_in_repo"] for r in rows),
      "rights_unreviewed_count":sum(r["rights_status"]=="rights_not_reviewed" for r in rows),
      "text_only_adapted_pdf_count":sum(r["adapted_text_only"] for r in rows),
      "metadata_sample":"OpenAlex + Nordic repository corpus",
      "generated_utc":datetime.now(timezone.utc).isoformat(),
      "disclaimer":"OA URL is a metadata hint unless marked verified_oa_pdf (SHA-256 checked at retrieval time), and does not imply permission to republish. Only manifest-listed, licensed files are mirrored."
    }
    PUBLIC.mkdir(parents=True,exist_ok=True)
    (PUBLIC/"pdf_katalog.json").write_text(json.dumps({"stats":stats,"items":rows},ensure_ascii=False,separators=(",",":")),encoding="utf8")
    cols=["id","title","year","authors","doi","country_affiliations","source","review_priority","pdf_in_repo","public_pdf_url","oa_location_unverified","license","license_url","document_sha256","adapted_text_only","rights_status"]
    with (PUBLIC/"pdf_katalog.csv").open("w",newline="",encoding="utf8") as f:
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore")
        writer.writeheader()
        for w in rows:
            writer.writerow({**w,"authors":"; ".join(w["authors"]),"country_affiliations":"; ".join(w["country_affiliations"])})
    (ROOT/"results"/"PDF_KATALOG_STATUS.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("PDF_CATALOG",json.dumps(stats,ensure_ascii=False))
if __name__=="__main__":main()
