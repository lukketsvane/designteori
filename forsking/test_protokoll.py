"""Offline protocol integrity, frozen sample and evidence-separation tests.

Runnable with Python 3.11 stdlib only. It tests storage, not scientific truth.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from collections import Counter
import csv,gzip,json,sqlite3,hashlib,random,shutil
ROOT=Path(__file__).resolve().parents[1]
F=ROOT/"forsking"
def read_csv(path):
    with path.open("r",encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))
def check(condition, why):
    if not condition:raise SystemExit("FAIL: "+why)
def test():
    claims=json.loads((F/"PASTANDAR.json").read_text(encoding="utf-8"))
    ids={c["id"] for c in claims["claims"]}
    check(ids=={f"P{i:02d}" for i in range(1,11)},"expected ten explicit claims")
    check(all(str(c["status"]).startswith("ikkje testa") for c in claims["claims"]),"claims were promoted to findings")
    pilot=json.loads((F/"PILOT_KJELDER.json").read_text(encoding="utf-8"))
    check(len(pilot["items"])==3,"pilot case count changed without review")
    check(all(set(x["targets"])<=ids for x in pilot["items"]),"unknown claim in pilot")
    check(all("AI-assistert" in x["review_state"] for x in pilot["items"]),"pilot falsely labeled independent review")
    queue=read_csv(F/"MOTPROVEKO.csv")
    check(len(queue)>=330,"review queue too small")
    check(len({x["pair_id"] for x in queue})==len(queue),"duplicate pair ID")
    check(len({(x["citing_id"],x["cited_id"]) for x in queue})==len(queue),"duplicate pair endpoints")
    check(all(x["eligibility_assessment"]=="unreviewed" and x["citation_function"]=="unreviewed" and x["theory_test_status"]=="unreviewed" for x in queue),"unreviewed pairs promoted to findings")
    check(sum(x["random_control"]=="1" for x in queue)==120,"random control membership")
    check(sum("licensed_citing_pdf" in x["selection_tags"] for x in queue)==71,"locally accessible citation pairs changed")
    check(sum("preexisting_counterexample_candidate" in x["selection_tags"] for x in queue)==150,"historic counterexample candidates changed")
    # Check independent randomized control sample against actual graph.
    with TemporaryDirectory() as tmp:
        tmp_db=Path(tmp)/"works.sqlite"
        with gzip.open(ROOT/"data"/"nordic_design_research.sqlite.gz","rb") as src,tmp_db.open("wb") as dest:
            shutil.copyfileobj(src,dest)
        db=sqlite3.connect(tmp_db)
        edges=sorted(set(db.execute("""
            SELECT r.citing_id,r.cited_id FROM references_all r
            JOIN works a ON a.id=r.citing_id JOIN works b ON b.id=r.cited_id
            WHERE a.id<>b.id
        """).fetchall()))
        check(len(edges)==5502,"snapshot graph changed since queue was selected")
        sample=set(random.Random(20261106).sample(edges,120))
        observed={(r["citing_id"],r["cited_id"]) for r in queue if r["random_control"]=="1"}
        check(sample==observed,"random cohort reproducibility")
        check(all((r["citing_id"],r["cited_id"]) in set(edges) for r in queue),"nonexistent citation edge in queue")
        db.close()
    # The blind forms deliberately reveal neither sampling-route flag nor judgments.
    essentials=("pair_id","citing_id","cited_id","citing_doi","cited_doi")
    allrows={}
    for coder in ("A","B"):
        docs=read_csv(F/f"BLINDKODING_{coder}.csv")
        check(len(docs)==len(queue),f"blind coding {coder} length")
        check(len({x["pair_id"] for x in docs})==len(docs),f"duplicate blind {coder} ID")
        for x in docs:
            check(all(x[y] for y in ("pair_id","citing_id","cited_id")),f"missing IDs {coder}")
            check(all(not x[k] for k in x if k not in ("pair_id","citing_id","citing_title","citing_doi","cited_id","cited_title","cited_doi")),f"pre-populated coding outcome {coder}")
        allrows[coder]={r["pair_id"]:tuple(r[k] for k in essentials) for r in docs}
    check(allrows["A"]==allrows["B"],"blind coders did not receive same work identities")
    status=json.loads((F/"MOTPROVEKO_STATUS.json").read_text(encoding="utf-8"))
    check(status["unique_review_pairs"]==len(queue),"queue status report out of date")
    check(status["manually_double_coded"]==0,"fabricated reliability status")
    bias=json.loads((F/"DEKNING_OG_BIAS.json").read_text(encoding="utf-8"))
    coverage=bias["coverage"]
    check(coverage["review_pairs"]==len(queue),"review coverage report changed")
    check(coverage["review_pairs_both_fulltext_pdf_public"]==0,"public PDF-both-ends count no longer matches")
    check(bias["group_stats"]["all_sample_internal_citations"]["n"]==len(edges),"graph baseline mismatch")
    needs=json.loads((F/"FULLTEKSTBEHOV_STATUS.json").read_text(encoding="utf-8"))
    missing=read_csv(F/"SAKNAR_FULLTEKST.csv")
    pairs_to_fetch=read_csv(F/"PAR_TIL_FULLTEKST.csv")
    check(len(missing)==needs["unique_works_to_obtain"],"missing-fulltext list out of sync")
    check(len(pairs_to_fetch)==len(queue),"pair acquisition tasks out of sync")
    check(all(r["rights_for_mirroring"]=="not reviewed" for r in missing),"unlicensed PDF entries falsely cleared")
    check(needs["both_pdfs_public_ready"]==0,"PDF acquisition status changed without recalculation")
    print("PASS: 10 untested claims; 3 AI-screened PDFs; "+str(len(queue))+" unreviewed pairs; 120 reproducible random controls; 388 pending rights checks; no fabricated coding.")
if __name__=="__main__":
    test()
