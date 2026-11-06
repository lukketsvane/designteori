"""Build an auditable metadata-only public index, not a verified census.

The archive's 7,300 records include candidate works beyond automatic scope;
never relabel them as accepted theory publications.
"""
from __future__ import annotations
import csv
import gzip
import json
import re
import shutil
import sqlite3
from collections import Counter,defaultdict
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"docs"/"data"
def main():
 db=ROOT/"data"/"nordic_design_research.sqlite"
 if not db.exists():
  with gzip.open(str(db)+".gz","rb") as src,db.open("wb") as dst:shutil.copyfileobj(src,dst)
 conn=sqlite3.connect(f"file:{db.as_posix()}?mode=ro",uri=True)
 cols=[r[1] for r in conn.execute("PRAGMA table_info(works)")]
 required={"id","title","year","doi","in_scope","oa_url","countries"}
 if not required.issubset(cols):raise SystemExit(f"Missing columns: {required-set(cols)}")
 authors=defaultdict(list)
 for work_id,author_id,name,inst_id,inst_name,country,position in conn.execute(
  "SELECT work_id,author_id,author_name,institution_id,institution_name,country,author_position FROM authorships ORDER BY rowid"):
  if name and name not in authors[work_id]:authors[work_id].append(name)
 themes={}
 with (ROOT/"results"/"included_publications.csv").open(encoding="utf-8-sig",newline="") as fp:
  for r in csv.DictReader(fp):themes[r["id"]]=r.get("theme","")
 manifest=json.loads((ROOT/"fulltekst"/"manifest.json").read_text(encoding="utf-8")) if (ROOT/"fulltekst"/"manifest.json").exists() else {"items":[]}
 fulltexts={r["id"]:r for r in manifest["items"]}
 triage=json.loads((OUT/"triage.json").read_text(encoding="utf-8")) if (OUT/"triage.json").exists() else {}
 docs=[]
 countries=Counter();kind=Counter();years=Counter()
 for r in conn.execute("SELECT id,doi,title,year,kind,citations,source,countries,topic,oa_url,in_scope,language FROM works ORDER BY year DESC, citations DESC, id"):
  id,doi,title,year,kind_name,citations,source,country_json,topic,oa_url,in_scope,language=r
  try:coun=json.loads(country_json or "[]")
  except json.JSONDecodeError:coun=[]
  if not isinstance(coun,list):coun=[]
  countries.update(set(coun))
  kind[kind_name or "?"]+=1
  years[str(year)]+=1
  record={
    "id":id,"title":title or "","year":year,
    "doi":doi or "","authors":authors[id],"source":source or "",
    "countries":coun,"kind":kind_name or "","citations":citations or 0,
    "topic":topic or "","theme":themes.get(id,""),
    "oa_url":oa_url if oa_url and oa_url.startswith("https://") else "",
    "language":language or "",
    "scope":"automatic-title-inclusion" if in_scope else "awaiting-eligibility-review",
    "pdf":("https://github.com/lukketsvane/designteori/blob/main/fulltekst/"+fulltexts[id]["pdf"]) if id in fulltexts else "",
    "text":("https://github.com/lukketsvane/designteori/blob/main/fulltekst/"+fulltexts[id]["text"]) if id in fulltexts and fulltexts[id]["text"] else "",
    "license":fulltexts[id]["license"] if id in fulltexts else "",
    "review_priority":triage.get(id,{}).get("review_priority",""),
    "review_score":triage.get(id,{}).get("priority_score",0),
    "keyword_categories":triage.get(id,{}).get("keyword_categories",""),
  }
  docs.append(record)
 if len(docs)!=7300:raise SystemExit(f"Unexpected count {len(docs)}; check before publishing")
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"publications.json").write_text(json.dumps(docs,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
 (OUT/"stats.json").write_text(json.dumps({
  "generated_at":datetime.now(timezone.utc).isoformat(),
  "metadata_source":"OpenAlex, 2026-11-02 partial search extract",
  "total":len(docs),"automatic_title_inclusion":sum(x["scope"]=="automatic-title-inclusion" for x in docs),
  "manual_review_queue":sum(x["scope"]=="awaiting-eligibility-review" for x in docs),
  "article_records":kind.get("article",0),"review_records":kind.get("review",0),
  "local_pdf":sum(bool(x["pdf"]) for x in docs),"local_fulltext_text":sum(bool(x["text"]) for x in docs),
  "high_priority_for_manual_review":sum(x["review_priority"]=="high" for x in docs),
  "country_memberships":countries,"kinds":kind,"year":years,
  "warning":"Search result counts are not an estimate of the Nordic theory literature population."
 },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 with (OUT/"publications.csv").open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=["id","doi","title","year","authors","source","countries","kind","citations","topic","theme","oa_url","scope","license","pdf","text","review_priority","review_score","keyword_categories"])
  w.writeheader()
  for row in docs:w.writerow({k:", ".join(v) if isinstance(v,list) else v for k,v in row.items() if k in w.fieldnames})
 print("CATALOG_GENERATED",len(docs),"fulltext",len(fulltexts),"json_MB",round((OUT/"publications.json").stat().st_size/1e6,2))
if __name__=="__main__":main()
