"""Offline release validation for the public research atlas (stdlib-only)."""
from pathlib import Path
import csv,gzip,hashlib,json,sqlite3,tempfile
ROOT=Path(__file__).resolve().parent
def check(cond,msg):
 if not cond:raise SystemExit("FAIL: "+msg)
def run():
 with tempfile.TemporaryDirectory() as td:
  dbpath=Path(td)/"corpus.sqlite"
  with gzip.open(ROOT/"data"/"nordic_design_research.sqlite.gz","rb") as src,dbpath.open("wb") as dst:
   import shutil;shutil.copyfileobj(src,dst)
  db=sqlite3.connect(dbpath)
  works=db.execute("select count(*) from works").fetchone()[0]
  authorships=db.execute("select count(*) from authorships").fetchone()[0]
  references=db.execute("select count(*) from references_all").fetchone()[0]
  incl=db.execute("select count(*) from works where in_scope=1").fetchone()[0]
  check(works==7300,"unexpected number of source works")
  check(incl==3729,"unexpected automatic subset")
  check(authorships>=35000,"incomplete authorship import")
  check(references>=269000,"incomplete reference graph")
  check(db.execute("select count(*) from works where coalesce(abstract,'')<>''").fetchone()[0]==0,"public metadata archive must not include unlicensed abstracts")
  db.close()
 stats=json.loads((ROOT/"docs/data/stats.json").read_text(encoding="utf-8"))
 docs=json.loads((ROOT/"docs/data/publications.json").read_text(encoding="utf-8"))
 check(len(docs)==works,"catalog count")
 check(len({d["id"] for d in docs})==works,"duplicate ID in catalog")
 check(stats["total"]==works and stats["automatic_title_inclusion"]==incl,"statistics are out of sync")
 check(sum(d["scope"]=="awaiting-eligibility-review" for d in docs)==3571,"unreviewed scope count")
 manifest=json.loads((ROOT/"fulltekst/manifest.json").read_text(encoding="utf-8"))
 check(manifest["count"]==len(manifest["items"]),"bad fulltext count")
 check(len(manifest["items"])>=11,"lost reviewed fulltexts")
 lic={r["id"]:r for r in manifest["items"]}
 for r in manifest["items"]:
  pdf=ROOT/"fulltekst"/r["pdf"]
  check(pdf.is_file() and pdf.stat().st_size>5000,"missing licensed PDF: "+r["id"])
  check(hashlib.sha256(pdf.read_bytes()).hexdigest()==r["sha256"],"PDF changed: "+r["id"])
  check(r["original_fulltext_url"].startswith("https://"),"missing original source")
  check(r["license_url"].startswith("https://creativecommons.org/licenses/"),"missing full licence link")
  if r["text"]:
   check((ROOT/"fulltekst"/r["text"]).is_file(),"missing text extraction")
   check("ND" not in r["license"],"NoDerivatives text wrongly republished")
  else:check("ND" in r["license"],"missing text without ND restriction")
 check(sum(bool(d["pdf"]) for d in docs)==len(lic),"catalog lacks PDF links")
 check((ROOT/"docs/index.html").stat().st_size>5000,"website missing")
 with (ROOT/"bibliografi/avstemt_mot_openalex.csv").open(encoding="utf-8",newline="") as f:
  annotated=list(csv.DictReader(f))
 check(len(annotated)>=77,"curated bibliography missing")
 with tempfile.TemporaryDirectory() as td:
  path=Path(td)/"search.sqlite"
  with gzip.open(ROOT/"data/fulltekst_sok.sqlite.gz","rb") as src,path.open("wb") as out:
   import shutil;shutil.copyfileobj(src,out)
  idx=sqlite3.connect(path)
  check(idx.execute("SELECT count(*) FROM sources").fetchone()[0]==sum(bool(r["text"]) for r in lic.values()),"text search index mismatch")
  check(idx.execute("SELECT count(*) FROM fulltext_fts WHERE fulltext_fts MATCH 'design'").fetchone()[0]>0,"FTS did not index")
  idx.close()
 with tempfile.TemporaryDirectory() as td:
  path=Path(td)/"warehouse.sqlite"
  with gzip.open(ROOT/"data/designteori_hovuddatabase.sqlite.gz","rb") as src,path.open("wb") as out:
   import shutil;shutil.copyfileobj(src,out)
  warehouse=sqlite3.connect(path)
  check(warehouse.execute("SELECT count(*) FROM works").fetchone()[0]==works,"warehouse base works")
  check(warehouse.execute("SELECT count(*) FROM editorial_bibliography").fetchone()[0]==len(annotated),"warehouse bibliography")
  check(warehouse.execute("SELECT count(*) FROM uncrossmatched_editorial").fetchone()[0]==sum(not x["openalex_id"] for x in annotated),"warehouse identity queue")
  check(warehouse.execute("SELECT count(*) FROM fulltext_versions").fetchone()[0]==len(lic),"warehouse fulltexts")
  check(warehouse.execute("SELECT count(*) FROM theory_claims").fetchone()[0]==0,"unreviewed claims wrongly populated")
  warehouse.close()
 print(f"OK: {works} metadata, {authorships} authorship records, {references} reference edges, {len(annotated)} editorial citations, {len(lic)} licensed fulltexts.")
if __name__=="__main__":run()
