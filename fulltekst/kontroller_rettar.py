"""Offline rights audit for local PDF research copies.

A phrase like Creative Commons in references is NOT proof the article is
licensed for redistribution. Only manifest-approved versions are public.
"""
from pathlib import Path
import csv
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT.parent/"FORML-RE-datascience"/"research"/"nordisk-designforsking"/"data"/"oa_fulltexts_private"
MANIFEST=ROOT/"fulltekst"/"manifest.json"
OUT=ROOT/"fulltekst"/"rettsstatus.csv"

def main():
    import fitz
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    approved={item["id"]:item for item in manifest["items"]}
    rows=[]
    for p in sorted(LOCAL.glob("W*.pdf")):
        with fitz.open(p) as doc:
            original_text="\n".join(page.get_text() for page in doc)
            pages=[]
            for i,page in enumerate(doc):
                if re.search(r"(?i)(?:this article is licensed under|creative commons|CC BY|all rights reserved|reproduced with (?:the )?author.s permission)",page.get_text()):
                    pages.append(i+1)
            page_count=len(doc)
        has_third_party_notice=bool(re.search(r"(?i)reproduced with (?:the )?author.s permission",original_text))
        right=approved.get(p.stem)
        rows.append({
            "work_id":p.stem,
            "original_pdf_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
            "original_pdf_bytes":p.stat().st_size,
            "original_pdf_pages":page_count,
            "pages_with_rights_related_words":";".join(map(str,pages)),
            "public_mirror_status":"licensed_public_file" if right else "not_mirrored_no_verified_rights",
            "public_mirror_version":("text_only_adapted_no_images" if right and right.get("derivative_notes") else "original_pdf" if right else ""),
            "individual_redistribution_license":right["license"] if right else "",
            "license_url":right["license_url"] if right else "",
            "public_pdf_sha256":right["sha256"] if right else "",
            "excluded_third_party_artwork_notice":int(has_third_party_notice),
            "fulltext_copyright_review":"checked_work_specific_license" if right else "requires_manual_review",
            "rights_search_tokens_are_not_permission":"yes"
        })
    assert len(rows)==26
    assert sum(r["public_mirror_status"]=="licensed_public_file" for r in rows)==manifest["count"]
    assert sum(r["public_mirror_version"]=="text_only_adapted_no_images" for r in rows)==1
    with OUT.open("w",newline="",encoding="utf-8") as fp:
        writer=csv.DictWriter(fp,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    pending=[x["work_id"] for x in rows if x["public_mirror_status"]!="licensed_public_file"]
    report = (
        "# Rettigheitskontroll av dei lokale PDF-ane\n\n"
        + "Lokale dokument: "+str(len(rows))+". Offentleg lisensiert PDF-utgåve: "
        + str(manifest["count"])+". Uavklarte originalar: "+str(len(pending))+".\n\n"
        + "Ein offentleg artikkel er ein tilpassa, tekstbasert PDF utan tredjepartsillustrasjonar. "
        + "Originalbiletet er berre tilgjengeleg i den private lesecachen. "
        + "Endring og CC BY 4.0-lisens er dokumenterte i manifestet.\n\n"
        + "Publisering av dei andre dokumenta krev konkret løyve for den aktuelle originalversjonen.\n\n"
        + "Uavklarte arbeids-ID-ar:\n\n"
        + "\n".join("* "+wid for wid in pending)
        + "\n\nSjå fulltekst/rettsstatus.csv for hash, sidetal og rettsstatus. "
        + "Søkjetreff i rettsstekst er ikkje tilstrekkeleg løyve.\n"
    )
    (ROOT/"results"/"PDF_RETTAR.md").write_text(report,encoding="utf-8")
    print("RIGHTS_AUDIT",{"local":len(rows),"public":len(rows)-len(pending),
                          "pending":len(pending),"adapted_without_images":1,
                          "pending_ids":pending})
if __name__=="__main__":main()
