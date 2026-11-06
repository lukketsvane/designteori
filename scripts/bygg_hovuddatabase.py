"""Build a normalized, provenance-aware research database from reproducible public inputs.

Keeps the original OpenAlex extract immutable, and adds editorial theory
bibliography, manifestation rights, fulltext search, and empty/manual-only
evidence-coding tables. All 7,300 OpenAlex records retain their original
provisional scope labels.
"""
from __future__ import annotations
import csv,gzip,json,os,sqlite3,shutil,tempfile
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"data"/"nordic_design_research.sqlite.gz"
DEST=ROOT/"data"/"designteori_hovuddatabase.sqlite.gz"
def build():
 fd,tmpname=tempfile.mkstemp(prefix="designteori_publish_",suffix=".sqlite")
 os.close(fd);tmp=Path(tmpname)
 try:
  with gzip.open(BASE,"rb") as src,tmp.open("wb") as dst:shutil.copyfileobj(src,dst)
  db=sqlite3.connect(tmp)
  db.executescript("""
  CREATE TABLE IF NOT EXISTS database_info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS source_provenance (
    source_id TEXT PRIMARY KEY,name TEXT,source_type TEXT,extracted_on TEXT,
    scope_note TEXT,repository_path TEXT);
  CREATE TABLE IF NOT EXISTS editorial_bibliography (
    editorial_id INTEGER PRIMARY KEY, section TEXT,authors TEXT,year INTEGER,
    title TEXT,doi TEXT, matched_openalex_id TEXT,
    identity_match_method TEXT,review_status TEXT,source_id TEXT);
  CREATE TABLE IF NOT EXISTS historical_bibliography (
    bibliography_id INTEGER PRIMARY KEY,source_id TEXT,bibtex_key TEXT,
    kind TEXT,authors TEXT,title TEXT,year INTEGER,doi TEXT,
    publisher TEXT,isbn TEXT,url TEXT,
    openalex_id TEXT,identity_match_method TEXT,nordic_affiliation_status TEXT,
    raw_fields_json TEXT);
  CREATE TABLE IF NOT EXISTS fulltext_versions (
    work_id TEXT PRIMARY KEY,title TEXT,authors TEXT,year INTEGER,doi TEXT,
    original_url TEXT,version_type TEXT,license TEXT,license_url TEXT,
    rights_verification TEXT,checked_on TEXT,sha256 TEXT,pdf_path TEXT,
    text_path TEXT,source_id TEXT);
  CREATE TABLE IF NOT EXISTS theory_claims (
    claim_id TEXT PRIMARY KEY,work_id TEXT,statement TEXT,claim_type TEXT,
    formalized_expression TEXT,uncertainty TEXT,
    created_by TEXT,review_status TEXT,created_on TEXT);
  CREATE TABLE IF NOT EXISTS claim_evidence (
    evidence_id TEXT PRIMARY KEY,claim_id TEXT,work_id TEXT,
    manifestation_hash TEXT,page INTEGER,quote_locator TEXT,
    observation_type TEXT,annotation TEXT,reviewer_id TEXT);
  CREATE TABLE IF NOT EXISTS claim_relations (
    edge_id TEXT PRIMARY KEY,source_claim_id TEXT,target_claim_id TEXT,
    relation_type TEXT,reviewer_id TEXT,evidence_id TEXT);
  CREATE TABLE IF NOT EXISTS screening_decisions (
    decision_id TEXT PRIMARY KEY,work_id TEXT,reviewer_id TEXT,
    theory_scope TEXT,theory_category TEXT,reason TEXT,fulltext_reviewed INTEGER,
    coded_at TEXT);
  CREATE TABLE IF NOT EXISTS theory_terms (
    term_id TEXT PRIMARY KEY,label TEXT,definition TEXT,version TEXT,origin_work_id TEXT);
  CREATE VIRTUAL TABLE IF NOT EXISTS editorial_fts USING fts5(
    title,authors,section,content='editorial_bibliography',content_rowid='editorial_id');
  CREATE VIRTUAL TABLE IF NOT EXISTS fulltext_fts USING fts5(
    work_id UNINDEXED,title,authors,fulltext,tokenize='unicode61 remove_diacritics 2');
  """)
  db.executemany("INSERT OR REPLACE INTO database_info VALUES(?,?)",[
    ("schema","designteori-hovuddatabase-v1"),
    ("original_opalex_snapshot","2026-11-02"),
    ("original_works_count",str(db.execute("SELECT count(*) FROM works").fetchone()[0])),
    ("source_original_sqlite_gz","data/nordic_design_research.sqlite.gz"),
    ("bibliography_scope","editorial candidates; manual identity verification pending"),
    ("claim_coding","none, manual-only tables have no rows")
  ])
  db.executemany("INSERT INTO source_provenance VALUES(?,?,?,?,?,?)",[
   ("openalex-20261102","OpenAlex","metadata extract","2026-11-02","Search-ranked, partial; not representative","data/nordic_design_research.sqlite.gz"),
   ("curated-20261101","Nordic bibliography for FORMLÆRE","editorial citation list","2026-11-01","77 bibliographic entries, not independently peer-reviewed","bibliografi/norden-2000-2026.md"),
   ("licensed-20261106","Local licence-checked OA PDFs","licensed fulltext archive","2026-11-06","11 reviewed licenses, not all OA sources","fulltekst/manifest.json"),
   ("grunnlaust-bib-20261106","GRUNNLAUST reference bibliography","historic design theory bibliography","2026-11-06","Global and Nordic references; eligibility unverified","bibliografi/grunnlaust_referansar.bib"),
   ("formlaere-bib-20261106","FORMLÆRE academic bibliography","theoretical bibliography","2026-11-06","Global and Nordic references; eligibility unverified","bibliografi/formlaere_akademisk.bib")
  ])
  with (ROOT/"bibliografi"/"avstemt_mot_openalex.csv").open(encoding="utf-8",newline="") as f:
   for r in csv.DictReader(f):
    db.execute("INSERT INTO editorial_bibliography(section,authors,year,title,doi,matched_openalex_id,identity_match_method,review_status,source_id) VALUES(?,?,?,?,?,?,?,?,?)",(
     r["section"],r["authors_as_printed"],int(r["year"]),r["title"],r["doi"],r["openalex_id"] or None,r["match_type"],r["review_status"],"curated-20261101"))
  db.execute("INSERT INTO editorial_fts(editorial_fts) VALUES('rebuild')")
  with (ROOT/"bibliografi"/"historiske_referansar.csv").open(encoding="utf-8",newline="") as f:
   for r in csv.DictReader(f):
    source_id=("grunnlaust-bib-20261106" if r["source"]=="grunnlaust" else "formlaere-bib-20261106")
    db.execute("INSERT INTO historical_bibliography(source_id,bibtex_key,kind,authors,title,year,doi,publisher,isbn,url,openalex_id,identity_match_method,nordic_affiliation_status,raw_fields_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
     source_id,r["bibtex_key"],r["kind"],r["authors"],r["title"],
     int(r["year"]) if r["year"] else None,r["doi"],r["publisher"],
     r["isbn"],r["url"],r["openalex_id"] or None,r["match_type"],
     r["nordic_affiliation_status"],r["raw_fields_json"]))
  manifest=json.loads((ROOT/"fulltekst/manifest.json").read_text(encoding="utf-8"))["items"]
  for r in manifest:
   db.execute("INSERT INTO fulltext_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
    r["id"],r["title"],"; ".join(r["authors"]),r["year"],r["doi"],
    r["original_fulltext_url"],"published-or-repository-PDF-as-downloaded",
    r["license"],r["license_url"],r["rights_basis"],r["reviewed_on"],
    r["sha256"],"fulltekst/"+r["pdf"],("fulltekst/"+r["text"] if r["text"] else None),"licensed-20261106"
   ))
   if r["text"]:
    content=(ROOT/"fulltekst"/r["text"]).read_text(encoding="utf-8")
    db.execute("INSERT INTO fulltext_fts(work_id,title,authors,fulltext) VALUES(?,?,?,?)",(
     r["id"],r["title"],"; ".join(r["authors"]),content))
  db.executescript("""
  CREATE VIEW IF NOT EXISTS vetted_fulltexts AS
   SELECT w.id,w.title,w.year,w.doi,f.license,f.pdf_path,f.text_path,f.sha256
   FROM works AS w JOIN fulltext_versions AS f ON w.id=f.work_id;
  CREATE VIEW IF NOT EXISTS uncrossmatched_editorial AS
   SELECT * FROM editorial_bibliography WHERE matched_openalex_id IS NULL;
  """)
  db.commit()
  counts={
   "works":db.execute("SELECT count(*) FROM works").fetchone()[0],
   "authorships":db.execute("SELECT count(*) FROM authorships").fetchone()[0],
   "bibliographic_edges":db.execute("SELECT count(*) FROM references_all").fetchone()[0],
   "editorial_works":db.execute("SELECT count(*) FROM editorial_bibliography").fetchone()[0],
   "historic_bibtex_entries":db.execute("SELECT count(*) FROM historical_bibliography").fetchone()[0],
   "unmatched_editorial":db.execute("SELECT count(*) FROM uncrossmatched_editorial").fetchone()[0],
   "fulltexts":db.execute("SELECT count(*) FROM fulltext_versions").fetchone()[0],
   "searchable_fulltexts":db.execute("SELECT count(*) FROM fulltext_fts").fetchone()[0],
   "manually_coded_claims":db.execute("SELECT count(*) FROM theory_claims").fetchone()[0],
  }
  db.close()
  with tmp.open("rb") as src,gzip.open(DEST,"wb",compresslevel=9) as dst:shutil.copyfileobj(src,dst)
  print("RESEARCH_DB",counts,"MB",round(DEST.stat().st_size/1e6,2))
 finally:
  if tmp.exists():tmp.unlink()
if __name__=="__main__":build()
