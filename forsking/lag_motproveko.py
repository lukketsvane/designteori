"""Reproducible, bias-aware citation-pair review queue.

Three *overlapping* entry routes: (1) licensed citing fulltexts,
(2) historic purposive counterexample screen, (3) uniform random control
of all internal citation edges. The random part is a probability sample
of the frozen 7,300-record internal graph, NOT the Nordic discipline.
No unreviewed pair is classified as positive or negative evidence.
"""
from pathlib import Path
import csv,hashlib,json,random,sqlite3
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]
SEED=20261106
N_RANDOM=120
def read_csv(path):
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def write_csv(path,items,fields):
    with path.open("w",encoding="utf-8",newline="") as out:
        w=csv.DictWriter(out,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(items)
def main():
    db=sqlite3.connect(ROOT/"data"/"nordic_design_research.sqlite")
    docs={r[0]:{"title":r[1],"doi":r[2] or "","year":r[3],"selected":r[4]} for r in db.execute("SELECT id,title,doi,year,in_scope FROM works")}
    edges=sorted(set((a,b) for a,b in db.execute("""
        SELECT r.citing_id, r.cited_id FROM references_all r
        JOIN works a ON r.citing_id=a.id JOIN works b ON r.cited_id=b.id
        WHERE r.citing_id<>r.cited_id
    """)))
    assert len(edges)>=5500
    rng=random.Random(SEED)
    random_edges=set(rng.sample(edges,N_RANDOM))
    legacy={(r["citing_id"],r["cited_id"]) for r in read_csv(ROOT/"results"/"possible_counterexamples_to_non_cumulative_design.csv")}
    manifest=json.loads((ROOT/"fulltekst/manifest.json").read_text(encoding="utf-8"))
    licensed={x["id"]:x for x in manifest["items"]}
    local_citing={(a,b) for a,b in edges if a in licensed}
    # Only use graph-confirmed citation pairs, never inject invalid/mismatched IDs.
    selected=sorted((random_edges|legacy|local_citing)&set(edges))
    rows=[]
    provenance=Counter()
    for a,b in selected:
        tags=[]
        if (a,b) in random_edges:tags.append("random_internal_control")
        if (a,b) in legacy:tags.append("preexisting_counterexample_candidate")
        if (a,b) in local_citing:tags.append("licensed_citing_pdf")
        provenance.update(tags)
        wa=docs[a];wb=docs[b]
        key=hashlib.sha256((a+"|"+b).encode()).hexdigest()[:14]
        rows.append({
            "pair_id":"PAIR-"+key,
            "citing_id":a,"cited_id":b,
            "citing_year":wa["year"],"cited_year":wb["year"],
            "citing_title":wa["title"],"cited_title":wb["title"],
            "citing_doi":wa["doi"],"cited_doi":wb["doi"],
            "citing_original_title_gate":int(wa["selected"]),
            "cited_original_title_gate":int(wb["selected"]),
            "citing_pdf":("fulltekst/"+licensed[a]["pdf"]) if a in licensed else "",
            "cited_pdf":("fulltekst/"+licensed[b]["pdf"]) if b in licensed else "",
            "selection_tags":";".join(tags),
            "random_control":int((a,b) in random_edges),
            "needs_both_fulltexts":int(not (a in licensed and b in licensed)),
            "possible_publication_year_mismatch":int(wa["year"]<wb["year"]),
            "eligibility_assessment":"unreviewed",
            "citation_function":"unreviewed",
            "theory_test_status":"unreviewed",
            "coder_status":"0 independent manual codings"
        })
    columns=list(rows[0])
    out=ROOT/"forsking"
    write_csv(out/"MOTPROVEKO.csv",rows,columns)
    # Deliver only work identity and blank outcome columns, with no selection
    # scores/tags or assertion the pair may be a counterexample.
    blind_fields=[
        "pair_id","citing_id","citing_title","citing_doi",
        "cited_id","cited_title","cited_doi",
        "eligible_design_theory","document_a_available","document_b_available",
        "pdf_citing_page","pdf_cited_page",
        "claim_older_work","what_newer_work_did","observation_and_result",
        "L0","L1","L2","L3","L4","L5","L6","L7",
        "H1","H2","H3","E1","E2","E3",
        "verdict","limitations","reviewer_id","review_date","evidence_quality_notes"
    ]
    blind=[]
    for r in rows:
        d={k:"" for k in blind_fields}
        for k in ("pair_id","citing_id","citing_title","citing_doi","cited_id","cited_title","cited_doi"):
            d[k]=r[k]
        blind.append(d)
    rng.shuffle(blind)
    for label in ("A","B"):
        write_csv(out/f"BLINDKODING_{label}.csv",blind,blind_fields)
    stats={
        "dataset":"Frozen 2026-11-02 OpenAlex candidate corpus",
        "sampling_seed":SEED,
        "random_draw_n":N_RANDOM,
        "eligible_internal_pairs":len(edges),
        "random_selection_probability":N_RANDOM/len(edges),
        "legacy_candidate_count_raw":len(legacy),
        "legacy_candidates_eligible":len(legacy&set(edges)),
        "licensed_citing_pairs":len(local_citing),
        "unique_review_pairs":len(rows),
        "provenance_memberships":dict(provenance),
        "both_pdfs_in_public_archive":sum(1 for r in rows if r["citing_pdf"] and r["cited_pdf"]),
        "some_pdf_in_public_archive":sum(1 for r in rows if r["citing_pdf"] or r["cited_pdf"]),
        "manually_double_coded":0,
        "notes":[
            "The 120 random controls are drawn uniformly from all sample-internal citation pairs, independent of keyword ranking.",
            "Purposive candidates and local-PDF pairs are not a probability sample and cannot estimate prevalence.",
            "No observed citation link, irrespective of text similarity, is classified as validation, replication, refutation or theory inheritance.",
            "The two coding sheets are intentionally independent; reviewers must save distinct responses before any reconciliation.",
            "Screening/eligibility and source PDF versions must be checked before citation function coding."
        ]
    }
    (out/"MOTPROVEKO_STATUS.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Data integrity and non-overlapping handling, not substantive inference.
    assert len({r["pair_id"] for r in rows})==len(rows)
    assert sum(r["random_control"] for r in rows)==N_RANDOM
    assert all(r["citation_function"]=="unreviewed" for r in rows)
    assert all(not r["L4"] and not r["verdict"] for r in blind)
    print("REVIEW_QUEUE",stats)
if __name__=="__main__":main()
