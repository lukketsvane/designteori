"""Create author/institution atlas and *internal* reference graph for offline public browsing.

Edges are metadata-level bibliographic references, not confirmed claims of
agreement, replication, or theoretical descent. Only works inside the snapshot
can appear as endpoints. Fields are indexed by OpenAlex IDs.
"""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict, Counter
import csv, json, sqlite3
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"docs"/"data"
def dump(name,obj):
 (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
def main():
 db=sqlite3.connect(ROOT/"data/nordic_design_research.sqlite")
 db.row_factory=sqlite3.Row
 works={r["id"]:dict(r) for r in db.execute("SELECT id,title,year,citations,in_scope,source FROM works")}
 # Author records, many-to-many affiliations. Preserve author identity and don't
 # infer nationality or employment from any coauthor's institution.
 context={id:{"authors":[],"cites":[],"cited_by":[]} for id in works}
 author_works=defaultdict(set);inst_works=defaultdict(set)
 author_name={};inst_name={};inst_country={}
 affiliations=defaultdict(lambda:defaultdict(dict))
 for work_id,author_id,author,inst_id,inst,country,position in db.execute(
  "SELECT work_id,author_id,author_name,institution_id,institution_name,country,author_position FROM authorships ORDER BY rowid"
 ):
  if work_id not in works:continue
  # Without an OpenAlex author ID, two identical names on different works
  # are NOT enough to establish the same person.
  aid=author_id or "unresolved:"+work_id+":"+str(author or "Unknown")
  author_name.setdefault(aid,author or "Ukjend")
  author_works[aid].add(work_id)
  rec=affiliations[work_id][aid]
  if "name" not in rec:rec.update({"id":aid,"name":author or "Ukjend","institutions":[]})
  if inst_id or inst:
   # Do not conflate institutions by display name without a stable ID.
   iid=inst_id or "unresolved:"+work_id+":"+str(inst or "")
   inst_name.setdefault(iid,inst or "Ikkje namngjeven institusjon")
   if country and iid not in inst_country:inst_country[iid]=country
   inst_works[iid].add(work_id)
   aff={"id":iid,"name":inst or "Ikkje namngjeven institusjon","country":country or ""}
   if aff not in rec["institutions"]:rec["institutions"].append(aff)
 for id,byauthor in affiliations.items():context[id]["authors"]=list(byauthor.values())
 internal=[]
 for citing,cited in db.execute("""
  SELECT r.citing_id,r.cited_id FROM references_all r
  JOIN works w ON w.id=r.citing_id JOIN works v ON v.id=r.cited_id
  ORDER BY r.citing_id,r.cited_id"""):
  if citing==cited:continue
  context[citing]["cites"].append(cited);context[cited]["cited_by"].append(citing)
  internal.append([citing,cited])
 dump("work_context.json",context)
 author_rows=[]
 for id,wids in author_works.items():
  works_count=len(wids);in_scope_count=sum(works[x]["in_scope"] for x in wids)
  citations_in_snapshot=sum(works[x]["citations"] or 0 for x in wids)
  author_rows.append({"id":id,"name":author_name[id],"works":works_count,
   "automatically_title_included":in_scope_count,
   "countries":sorted({aff["country"] for wid in wids for aff in affiliations[wid][id]["institutions"] if aff["country"]}),
   "institutions":sorted({aff["name"] for wid in wids for aff in affiliations[wid][id]["institutions"] if aff["name"]}),
   "work_ids":sorted(wids),"openalex_citation_sum_on_snapshot_works":citations_in_snapshot})
 author_rows.sort(key=lambda x:(-x["automatically_title_included"],-x["works"],x["name"]))
 dump("authors.json",{"count":len(author_rows),"items":author_rows})
 inst_rows=[]
 for iid,wids in inst_works.items():
  inst_rows.append({"id":iid,"name":inst_name[iid],"country":inst_country.get(iid,""),
   "works":len(wids),"automatically_title_included":sum(works[x]["in_scope"] for x in wids),
   "work_ids":sorted(wids)})
 inst_rows.sort(key=lambda x:(-x["automatically_title_included"],-x["works"],x["name"]))
 dump("institutions.json",{"count":len(inst_rows),"items":inst_rows})
 with (ROOT/"results"/"internal_citations_all_7300.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.writer(f);w.writerow(["citing_openalex_id","cited_openalex_id"]);w.writerows(internal)
 stats={
  "work_count":len(works),"author_ids":len(author_rows),"institution_ids":len(inst_rows),
  "internal_citation_edges":len(internal),
  "author_top_20":[{k:r[k] for k in ("id","name","works","automatically_title_included")} for r in author_rows[:20]],
  "institution_top_20":[{k:r[k] for k in ("id","name","works","automatically_title_included","country")} for r in inst_rows[:20]],
  "warning":"A bibliographic reference edge does not prove theoretical agreement, inheritance or replication; counts are restricted to sampled records."
 }
 (ROOT/"results"/"RELASJONATLAS_STATUS.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print("RELATION_ATLAS",[(k,v) for k,v in stats.items() if k not in ("author_top_20","institution_top_20","warning")])
 for name in ("work_context.json","authors.json","institutions.json"):
  print("FILE",name,round((OUT/name).stat().st_size/1048576,2),"MiB")
if __name__=="__main__":main()
