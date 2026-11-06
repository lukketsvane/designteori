"""Prepare a traceable queue of later work citing source-located pilot papers.

All citation functions stay UNKNOWN until relevant passages in both fulltexts
are read. This creates *candidates* for theory-lineage studies, not evidence of
independent testing or cumulativity.
"""
from pathlib import Path
import csv, sqlite3
ROOT=Path(__file__).resolve().parent
def main():
 db=sqlite3.connect(ROOT/"data"/"nordic_design_research.sqlite")
 with (ROOT/"forsking"/"KJELDESPOR_PILOT.csv").open(newline="",encoding="utf-8") as f:
  sources=[r for r in csv.DictReader(f)]
 output=[]
 for s in sources:
  a=s["paper_id"]
  citing=db.execute("""
   SELECT w.id,w.title,w.doi,w.year,w.kind,w.oa_url
   FROM references_all AS r JOIN works w ON w.id=r.citing_id
   WHERE r.cited_id=? AND r.citing_id!=r.cited_id
   ORDER BY w.year, w.citations DESC, w.id
   """,(a,)).fetchall()
  for citing_id,title,doi,year,kind,oa in citing:
   output.append({
    "older_work_id":a,"older_title":s["title"],"older_doi":s["doi"],
    "later_work_id":citing_id,"later_title":title,"later_year":year,"later_kind":kind,
    "later_doi":doi or "","later_oa_url":oa or "",
    "citation_status":"metadata_link_only","citation_function":"LNA",
    "independent_replication":"not_evaluated",
    "specific_theory_claim_tested":"not_evaluated",
    "coding_status":"unread_fulltext",
    "review_task":"Obtain both legitimate fulltexts; inspect context of actual citation, then code L0-L7 with page evidence."
   })
 out=ROOT/"forsking"/"OPPFOLGJANDE_SITERINGAR.csv"
 cols=list(output[0]) if output else ["older_work_id","later_work_id"]
 with out.open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(output)
 print("FOLLOWUP_CITATION_QUEUE",len(output))
 for r in output:print(r["older_work_id"],"=>",r["later_work_id"],r["later_year"],r["later_title"][:70])
if __name__=="__main__":main()
