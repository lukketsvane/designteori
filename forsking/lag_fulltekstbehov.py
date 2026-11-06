"""Generate copyright-safe work acquisition queue for two-sided citation reviews.

The URLs are original OpenAlex hints, not verified open access or permissions.
This script DOES NOT download or redistribute any copyrighted documents.
"""
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,sqlite3
ROOT=Path(__file__).resolve().parents[1]
F=ROOT/"forsking"
def readcsv(path):
 with path.open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def writecsv(path,rows,fields):
 with path.open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)
def main():
 db=sqlite3.connect(ROOT/"data/nordic_design_research.sqlite")
 works={r[0]:dict(zip(("id","doi","title","year","oa_url","kind","source"),r)) for r in db.execute("SELECT id,doi,title,year,oa_url,kind,source FROM works")}
 manifest=json.loads((ROOT/"fulltekst/manifest.json").read_text(encoding="utf-8"))
 full={r["id"]:r for r in manifest["items"]}
 q=readcsv(F/"MOTPROVEKO.csv")
 wanted=defaultdict(lambda:{"citing_pairs":0,"cited_pairs":0,"random_pairs":0,"all_pairs":[]})
 links=[]
 for row in q:
  a=row["citing_id"];b=row["cited_id"]
  wa=works[a];wb=works[b]
  a_ready=a in full;b_ready=b in full
  for wid,role in ((a,"citing"),(b,"cited")):
   if wid in full:continue
   wanted[wid][role+"_pairs"]+=1
   wanted[wid]["random_pairs"]+=int(row["random_control"])
   wanted[wid]["all_pairs"].append(row["pair_id"])
  links.append({
   "pair_id":row["pair_id"],"sampling_route":row["selection_tags"],
   "random_control":row["random_control"],
   "citing_id":a,"citing_doi":wa["doi"] or "",
   "citing_oa_url_unverified":wa["oa_url"] or "",
   "citing_local_cc_pdf":("fulltekst/"+full[a]["pdf"] if a_ready else ""),
   "cited_id":b,"cited_doi":wb["doi"] or "",
   "cited_oa_url_unverified":wb["oa_url"] or "",
   "cited_local_cc_pdf":("fulltekst/"+full[b]["pdf"] if b_ready else ""),
   "both_oa_urls_in_metadata":int(bool(wa["oa_url"] and wb["oa_url"])),
   "both_public_pdfs_ready":int(a_ready and b_ready),
   "work_to_obtain_a":"" if a_ready else a,
   "work_to_obtain_b":"" if b_ready else b,
   "verification":"untested OA links; obtain legitimate fulltexts and verify source/licence",
   "coder_data":"unreviewed"})
 links.sort(key=lambda r:(-int(r["random_control"]),-int(r["both_oa_urls_in_metadata"]),
                            -int(bool(r["citing_local_cc_pdf"] or r["cited_local_cc_pdf"])),r["pair_id"]))
 pairs_path=F/"PAR_TIL_FULLTEKST.csv"
 writecsv(pairs_path,links,list(links[0]))
 todo=[]
 for wid,data in wanted.items():
  work=works[wid]
  importance=len(set(data["all_pairs"]))
  todo.append({
   "work_id":wid,"title":work["title"],"year":work["year"],
   "doi":work["doi"] or "","oa_url_unverified":work["oa_url"] or "",
   "in_citing_pairs":data["citing_pairs"],"in_cited_pairs":data["cited_pairs"],
   "unresolved_review_pairs":importance,"random_control_pairs":data["random_pairs"],
   "url_present":int(bool(work["oa_url"])),
   "oa_licence_evidence":"unknown","rights_for_mirroring":"not reviewed",
   "public_archive_pdf_available":"no","source_version_verified":"not_checked",
   "acquisition_task":"Find lawful fulltext version, verify DOI+title+year+publisher PDF; inspect licence before any public mirroring."
  })
 todo.sort(key=lambda r:(-r["random_control_pairs"],-r["unresolved_review_pairs"],-r["url_present"],r["year"],r["work_id"]))
 work_path=F/"SAKNAR_FULLTEKST.csv"
 writecsv(work_path,todo,list(todo[0]))
 summary={
  "study_frame":"336 review citation pairs, all unclassified",
  "pairs":len(links),"both_pdfs_public_ready":sum(r["both_public_pdfs_ready"] for r in links),
  "pairs_with_both_oa_metadata_urls":sum(r["both_oa_urls_in_metadata"] for r in links),
  "unique_works_to_obtain":len(todo),
  "unique_works_to_obtain_with_openalex_oa_url":sum(r["url_present"] for r in todo),
  "unique_works_needed_by_random_controls":sum(r["random_control_pairs"]>0 for r in todo),
  "summary":"OA metadata links are not licences; outputs are acquisition tasks, not accessible/redistributable PDF claims."
 }
 (F/"FULLTEKSTBEHOV_STATUS.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("FULLTEXT_NEEDS",summary)
 print("TOP_ACQUISITIONS",[(r["work_id"],r["unresolved_review_pairs"],r["random_control_pairs"],r["title"][:65]) for r in todo[:12]])
if __name__=="__main__":main()
