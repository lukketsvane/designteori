"""Check provenance, SHA-256 and page-local text anchors of pilot readings.

This checks *that a quoted locator exists*, NOT its interpretation.
No metadata/AI review can be promoted to independent fulltext coding E2/E3.
"""
from __future__ import annotations
from pathlib import Path
import hashlib,json,unicodedata,re,sys
ROOT=Path(__file__).resolve().parents[1]
def normalize(s):
    # Keep punctuation, but normalize whitespace, pdf line hyphenation and ligatures.
    s=unicodedata.normalize("NFKC",s or "")
    s=re.sub(r"(?<=\w)[‐‑–-]\s*\n\s*(?=\w)","",s)
    s=re.sub(r"\s+"," ",s).lower()
    return s.strip()
def validate():
    try:
        import fitz
    except ImportError:
        fitz=None  # CI fallback: public plain-text extraction with PDF page markers
    claims=json.loads((ROOT/"forsking"/"PASTANDAR.json").read_text(encoding="utf-8"))
    assert {r["id"] for r in claims["claims"]}=={f"P{i:02d}" for i in range(1,11)}
    pilot=json.loads((ROOT/"forsking"/"PILOT_KJELDER.json").read_text(encoding="utf-8"))
    assert all(r["review_state"].startswith("AI-assistert") for r in pilot["items"])
    manifest=json.loads((ROOT/"fulltekst"/"manifest.json").read_text(encoding="utf-8"))
    by_id={r["id"]:r for r in manifest["items"]}
    counter=0
    for work in pilot["items"]:
        wid=work["work_id"]
        assert wid in by_id,(wid,"missing license manifest")
        assert set(work["targets"]).issubset({r["id"] for r in claims["claims"]})
        m=by_id[wid]; assert m["doi"]==work["doi"]
        pdf=ROOT/"fulltekst"/m["pdf"]
        assert pdf.exists(),pdf
        sha=hashlib.sha256(pdf.read_bytes()).hexdigest()
        assert sha==m["sha256"],(wid,"PDF changed without manifest update")
        if fitz is not None:
            with fitz.open(pdf) as doc:
                pages={i+1:doc[i].get_text(sort=True) for i in range(len(doc))}
        else:
            assert m["text"],(wid,"fallback requires permitted text extraction")
            raw=(ROOT/"fulltekst"/m["text"]).read_text(encoding="utf-8")
            parts=re.split(r"===== PAGE (\d+) =====",raw)
            pages={int(parts[i]):parts[i+1] for i in range(1,len(parts)-1,2)}
        for fact in work["facts"]:
            page=fact["pdf_page"]
            assert page in pages,(wid,page,"out of range")
            actual=normalize(pages[page])
            anchor=normalize(fact["anchor"])
            assert anchor in actual,(wid,page,anchor,"not found on indicated PDF page")
            assert fact["claim"] and fact["check"]
            counter+=1
        print(f"VALIDATED_LOCATORS {wid}: {len(work['facts'])} anchors; license={m['license']}")
    assert len(pilot["items"])==3 and counter>=10
    print(f"PASS: {len(pilot['items'])} CC-licensed papers, {counter} verified PDF-page anchors. Interpretations remain unvalidated.")
if __name__=="__main__":
    validate()
