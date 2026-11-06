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
 triage=json.loads((ROOT/"docs/data/triage.json").read_text(encoding="utf-8"))
 check(len(triage)==works,"priority signal index count")
 check(sum(d["review_priority"]=="high" for d in docs)>=150,"priority rules did not generate review list")
 check(all(d["review_score"]==triage[d["id"]]["priority_score"] for d in docs),"review priority out of sync")
 check(stats["total"]==works and stats["automatic_title_inclusion"]==incl,"statistics are out of sync")
 check(sum(d["scope"]=="awaiting-eligibility-review" for d in docs)==3571,"unreviewed scope count")
 manifest=json.loads((ROOT/"fulltekst/manifest.json").read_text(encoding="utf-8"))
 check(manifest["count"]==len(manifest["items"]),"bad fulltext count")
 check(len(manifest["items"])>=14,"lost reviewed fulltexts")
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
 check((ROOT/"docs/forsking.html").stat().st_size>5000,"hypothesis test portal missing")
 hypothesis=json.loads((ROOT/"forsking/PASTANDAR.json").read_text(encoding="utf-8"))
 claim_ids={c["id"] for c in hypothesis["claims"]}
 check(len(claim_ids)==len(hypothesis["claims"])==10,"hypothesis matrix malformed")
 web_hyp=json.loads((ROOT/"docs/data/forskingssporsmal.json").read_text(encoding="utf-8"))
 check({c["id"] for c in web_hyp["claims"]}==claim_ids,"public hypotheses out of sync")
 with (ROOT/"forsking/KJELDESPOR_PILOT.csv").open(encoding="utf-8",newline="") as fh:
  leads=list(csv.DictReader(fh))
 check(len(leads)==web_hyp["pilot_source_count"]==5,"pilot evidence count")
 check(all(set(r["claims"].split(";")).issubset(claim_ids) for r in leads),"pilot references invalid claim")
 check(all(r["human_coded"]=="false" and r["independent_replication_verified"]=="false" and r["grade"].startswith("E1_") for r in leads),"unvalidated evidence elevated to human-verified")
 with (ROOT/"forsking/OPPFOLGJANDE_SITERINGAR.csv").open(encoding="utf-8",newline="") as fh:
  next_links=list(csv.DictReader(fh))
 check(len(next_links)>=5,"followup citation queue missing")
 check(all(r["citation_function"]=="LNA" and r["citation_status"]=="metadata_link_only" for r in next_links),"unread citations falsely classified" )
 contexts=json.loads((ROOT/"docs/data/work_context.json").read_text(encoding="utf-8"))
 check(len(contexts)==works,"context index missing works")
 edge_count=sum(len(c["cites"]) for c in contexts.values())
 check(edge_count>=5500,"internal citation graph incomplete")
 check(edge_count==sum(len(c["cited_by"]) for c in contexts.values()),"internal graph direction mismatch")
 for citing,c in contexts.items():
  check(all(x in contexts for x in c["cites"]+c["cited_by"]),"internal citation to work outside sample")
 authors=json.loads((ROOT/"docs/data/authors.json").read_text(encoding="utf-8"))
 institutions=json.loads((ROOT/"docs/data/institutions.json").read_text(encoding="utf-8"))
 check(authors["count"]==len(authors["items"])>=21000,"author register missing")
 check(institutions["count"]==len(institutions["items"])>=3800,"institution register missing")
 with (ROOT/"bibliografi/avstemt_mot_openalex.csv").open(encoding="utf-8",newline="") as f:
  annotated=list(csv.DictReader(f))
 check(len(annotated)>=77,"curated bibliography missing")
 with (ROOT/"bibliografi/historiske_referansar.csv").open(encoding="utf-8",newline="") as f:
  historic=list(csv.DictReader(f))
 check(len(historic)>=430,"historic bibliographies missing")
 public_bibs=json.loads((ROOT/"docs/data/bibliografiar.json").read_text(encoding="utf-8"))
 check(len(public_bibs["items"])==len(historic)+len(annotated),"public bibliography index out of sync")
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
  check(warehouse.execute("SELECT count(*) FROM historical_bibliography").fetchone()[0]==len(historic),"warehouse historic bibliography")
  check(warehouse.execute("SELECT count(*) FROM uncrossmatched_editorial").fetchone()[0]==sum(not x["openalex_id"] for x in annotated),"warehouse identity queue")
  check(warehouse.execute("SELECT count(*) FROM fulltext_versions").fetchone()[0]==len(lic),"warehouse fulltexts")
  check(warehouse.execute("SELECT count(*) FROM theory_claims").fetchone()[0]==0,"unreviewed claims wrongly populated")
  warehouse.close()
 print(f"OK: {works} metadata, {authorships} authorship records, {references} reference edges, {len(annotated)} editorial citations, {len(lic)} licensed fulltexts.")
if __name__=="__main__":run()
