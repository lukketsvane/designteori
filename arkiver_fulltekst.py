"""Publish only locally reviewed, explicitly licensed OA fulltexts.

Run from repository root:
  python arkiver_fulltekst.py --source ../FORML-RE-datascience/research/nordisk-designforsking/data/oa_fulltexts_private
Never mirror PDFs with unknown redistribution permission.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sqlite3
from datetime import date, timezone, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LICENCES = {
 "CC BY 2.0": "https://creativecommons.org/licenses/by/2.0/",
 "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
 "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
 "CC BY-NC 4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
 "CC BY-NC-ND 4.0": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
}
# These IDs and the matching first-page licence notices were manually checked
# against the actual local PDF on 2026-11-06. Do not auto-approve from OA URLs.
APPROVED = {
 "W2126722450": ("CC BY 2.0", "Creative Commons Attribution License"),
 "W2739167865": ("CC BY 4.0", "CC BY 4.0"),
 "W2774875954": ("CC BY 4.0", "CC-BY 4.0"),
 "W2919057183": ("CC BY 4.0", "Creative Commons Attribution 4.0"),
 "W2982281212": ("CC BY 3.0", "creativecommons.org/licenses/by/3.0"),
 "W3183081787": ("CC BY 4.0", "Creative Commons Attribution License"),
 "W4311715142": ("CC BY 4.0", "Creative Commons Navn"),
 "W7155508854": ("CC BY 4.0", "Creative Commons Attribution License"),
 "W2986925238": ("CC BY-NC 4.0", "CC BY-NC 4.0"),
 "W2995635751": ("CC BY-NC 4.0", "CC BY-NC 4.0"),
 "W4307994144": ("CC BY-NC-ND 4.0", "CC BY-NC-ND 4.0"),
}
def main():
 ap = argparse.ArgumentParser()
 ap.add_argument("--source", type=Path, required=True)
 ap.add_argument("--output", type=Path, default=ROOT / "fulltekst")
 args = ap.parse_args()
 try:
  import fitz
 except ImportError as e:
  raise SystemExit("Install PyMuPDF: python -m pip install pymupdf") from e
 dbpath = ROOT/"data/nordic_design_research.sqlite"
 if not dbpath.exists():
  import gzip, shutil
  with gzip.open(str(dbpath)+".gz","rb") as src, dbpath.open("wb") as dst:
   shutil.copyfileobj(src,dst)
 db = sqlite3.connect(dbpath)
 args.output.mkdir(parents=True,exist_ok=True)
 (args.output/"pdf").mkdir(exist_ok=True)
 (args.output/"tekst").mkdir(exist_ok=True)
 rows = []
 for id, (licence, check) in APPROVED.items():
  original=args.source/(id+".pdf")
  if not original.is_file():
   raise SystemExit("MISSING: "+str(original))
  record=db.execute("SELECT id,doi,title,year,source,oa_url FROM works WHERE id=?",(id,)).fetchone()
  if record is None:
   raise SystemExit("ID_MISSING_FROM_METADATA: "+id)
  authors=[r[0] for r in db.execute("SELECT DISTINCT author_name FROM authorships WHERE work_id=? ORDER BY CASE author_position WHEN 'first' THEN 0 WHEN 'middle' THEN 1 ELSE 2 END, rowid",(id,))]
  with fitz.open(original) as doc:
   if len(doc)==0: raise SystemExit("EMPTY_PDF: "+id)
   beginning=" ".join(doc[i].get_text() for i in range(min(3,len(doc))))
   # Check first-pages license assertion, not merely a metadata "open access" flag.
   if ' '.join(check.casefold().split()) not in ' '.join(beginning.casefold().split()): raise SystemExit("NO_DOCUMENT_LICENSE: "+id+" "+check)
   if not re.search(r"\b(?:creative commons|cc[- ]by)\b|creativecommons[.]org/licenses/by/",beginning,re.I):
    raise SystemExit("MISSING_RIGHTS_STATEMENT: "+id)
   pages = [page.get_text(sort=True) for page in doc]
   if sum(map(len,pages))<400: raise SystemExit("NO_EXTRACTABLE_TEXT: "+id)
  sha=hashlib.sha256(original.read_bytes()).hexdigest()
  pdf_path=Path("pdf")/(id+".pdf")
  (args.output/pdf_path).write_bytes(original.read_bytes())
  text_path=None
  # ND explicitly prohibits adapted distributions; share verbatim PDF only.
  if "ND" not in licence:
   text_path=Path("tekst")/(id+".txt")
   attr=f"WORK: {record[2]}\nAUTHORS: {', '.join(authors)}\nYEAR: {record[3]}\nDOI: {record[1]}\nSOURCE: {record[5]}\nLICENSE: {licence}, {LICENCES[licence]}\nTRANSFORMATION: Plain-text extraction from PDF; layout lost, spelling not corrected.\n\n"
   plain=attr+"\n".join(f"\n===== PAGE {i+1} =====\n{page}" for i,page in enumerate(pages))
   (args.output/text_path).write_text(plain,encoding="utf-8")
  rows.append({
   "id":id,"title":record[2],"authors":authors,"year":record[3],
   "doi":record[1],"journal_or_source":record[4],"original_fulltext_url":record[5],
   "license":licence,"license_url":LICENCES[licence],
   "rights_basis":"Explicit Creative Commons licence statement in the first three pages of the PDF; reviewed 2026-11-06",
   "pdf":(pdf_path.as_posix()),"text":(text_path.as_posix() if text_path else None),
   "sha256":sha,"bytes":original.stat().st_size,
   "verification_status":"checked-document-licence","reviewed_on":"2026-11-06",
  })
 rows.sort(key=lambda r:r["id"])
 (args.output/"manifest.json").write_text(json.dumps({"schema_version":1,"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(rows),"items":rows},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 with (args.output/"manifest.csv").open("w",newline="",encoding="utf-8") as out:
  cols=["id","year","title","authors","doi","journal_or_source","original_fulltext_url","license","license_url","pdf","text","sha256","bytes","verification_status"]
  writer=csv.DictWriter(out,fieldnames=cols,extrasaction="ignore");writer.writeheader()
  for row in rows:writer.writerow(dict(row, authors="; ".join(row["authors"])))
 pending=[]
 for pdf in sorted(args.source.glob("*.pdf")):
  if pdf.stem in APPROVED:continue
  record=db.execute("SELECT id,doi,title,year,oa_url FROM works WHERE id=?",(pdf.stem,)).fetchone()
  if record:pending.append({"id":record[0],"doi":record[1],"title":record[2],"year":record[3],"oa_url":record[4],"status":"Licence for redistribution not yet verified; direct link only"})
 with (args.output/"andre_oa_kandidatar.csv").open("w",newline="",encoding="utf-8") as out:
  writer=csv.DictWriter(out,fieldnames=["id","doi","title","year","oa_url","status"]);writer.writeheader();writer.writerows(pending)
 print(f"READY: {len(rows)} verified licences, {len(pending)} link-only fulltext candidates, {sum(x['bytes'] for x in rows)/1048576:.2f} MB source PDFs")
if __name__=="__main__":
 main()
