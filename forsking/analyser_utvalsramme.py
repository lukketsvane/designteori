"""Quantify selection and fulltext-access bias before testing theory claims.

Uses only the frozen public OpenAlex snapshot and existing review queue.
Rates describe the collection / review frame, NOT Nordic design research.
"""
from pathlib import Path
from collections import Counter
import csv,gzip,json,sqlite3,statistics
ROOT=Path(__file__).resolve().parents[1]
F=ROOT/"forsking"
def readcsv(p):
    with p.open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def pct(n,d):
    return round(100*n/d,1) if d else None
def source_stats(rows,works):
    gaps=[]
    nd=nd_oa=same_author=positive=negative=both_included=both_doi=both_oa=0
    for row in rows:
        a=works[row["citing_id"]];b=works[row["cited_id"]]
        if a["doi"] and b["doi"]:both_doi+=1
        if a["oa_url"] and b["oa_url"]:both_oa+=1
        if a["in_scope"] and b["in_scope"]:both_included+=1
        gap=a["year"]-b["year"]
        gaps.append(gap)
        if gap<0:negative+=1
        elif gap==0:nd+=1
        else:positive+=1
    return {
        "n":len(rows),
        "both_original_title_gate":both_included,
        "both_original_title_gate_pct":pct(both_included,len(rows)),
        "both_doi":both_doi,
        "both_doi_pct":pct(both_doi,len(rows)),
        "both_oa_metadata_url":both_oa,
        "both_oa_metadata_url_pct":pct(both_oa,len(rows)),
        "nonnegative_citation_year_gap":positive+nd,
        "citing_year_before_cited_year":negative,
        "same_year":nd,
        "median_year_gap":statistics.median(gaps) if gaps else None
    }
def main():
    db_path=ROOT/"data"/"nordic_design_research.sqlite"
    if not db_path.exists():
        with gzip.open(str(db_path)+".gz","rb") as src,db_path.open("wb") as dst:
            import shutil;shutil.copyfileobj(src,dst)
    db=sqlite3.connect(db_path)
    works={row[0]:dict(zip(("id","doi","title","year","in_scope","oa_url","kind"),row)) for row in db.execute("SELECT id,doi,title,year,in_scope,oa_url,kind FROM works")}
    raw_edges=sorted(db.execute("""SELECT r.citing_id,r.cited_id FROM references_all r
                 JOIN works w ON w.id=r.citing_id JOIN works v ON v.id=r.cited_id
                 WHERE r.citing_id<>r.cited_id""").fetchall())
    edges=[{"citing_id":a,"cited_id":b} for a,b in raw_edges]
    q=readcsv(F/"MOTPROVEKO.csv")
    control=[r for r in q if r["random_control"]=="1"]
    purposive=[r for r in q if "preexisting_counterexample_candidate" in r["selection_tags"]]
    local=[r for r in q if "licensed_citing_pdf" in r["selection_tags"]]
    assert len(works)==7300 and len(edges)==5502
    groups={
      "all_sample_internal_citations":source_stats(edges,works),
      "uniform_random_120":source_stats(control,works),
      "preexisting_purposive_150":source_stats(purposive,works),
      "licensed_citing_pdf_71":source_stats(local,works),
      "combined_review_queue_336":source_stats(q,works)
    }
    manifest=json.loads((ROOT/"fulltekst"/"manifest.json").read_text(encoding="utf-8"))
    licensed={r["id"] for r in manifest["items"]}
    coverage={
       "works_in_frozen_openalex_extract":len(works),
       "original_title_gate_included":sum(w["in_scope"]==1 for w in works.values()),
       "document_pdf_in_open_repo":len(licensed),
       "document_pdf_in_open_repo_pct":pct(len(licensed),len(works)),
       "review_pairs":len(q),
       "review_pairs_both_fulltext_pdf_public":sum(x["citing_id"] in licensed and x["cited_id"] in licensed for x in q),
       "review_pairs_at_least_one_fulltext_pdf_public":sum(x["citing_id"] in licensed or x["cited_id"] in licensed for x in q),
       "review_pairs_neither_fulltext_pdf_public":sum(x["citing_id"] not in licensed and x["cited_id"] not in licensed for x in q),
       "review_pairs_both_oa_metadata_url":groups["combined_review_queue_336"]["both_oa_metadata_url"]
    }
    # NOTE: OA metadata URL is *not* evidence a usable/licensed PDF can be obtained.
    anomalies=[]
    for r in edges:
        a=works[r["citing_id"]];b=works[r["cited_id"]]
        if a["year"]<b["year"]:
            anomalies.append({
              "citing_id":a["id"],"citing_year":a["year"],"citing_title":a["title"],
              "cited_id":b["id"],"cited_year":b["year"],"cited_title":b["title"],
              "gap_years":a["year"]-b["year"],"status":"metadata-year-anomaly; do not infer impossible citation until date versions checked"})
    anomaly_file=F/"REVISJON_ARSTAL_I_SITERINGAR.csv"
    cols=["citing_id","citing_year","citing_title","cited_id","cited_year","cited_title","gap_years","status"]
    with anomaly_file.open("w",newline="",encoding="utf-8") as out:
        w=csv.DictWriter(out,fieldnames=cols);w.writeheader();w.writerows(anomalies)
    result={"generated_on":"2026-11-06","coverage":coverage,"group_stats":groups,
        "citation_year_anomalies":len(anomalies),
        "limitations":[
          "OpenAlex-rangsortert, delvis søkt korpus; ikkje representativ populasjon.",
          "Eit DOI-felt viser identitet, ikkje kvalitet eller fullteksttilgang.",
          "OA-lenkje er ikkje automatisk eit redistribusjonsløyve.",
          "Ingen offentleg revisjonssitering i det valde pilotutvalet har PDF for begge endar.",
          "Fagleg gjenbruk, kumulativitet og replikasjon kan ikkje avleiast frå metadata.",
          "Den tilfeldig trekte kontrollgruppa er berre representativ for interne bibliografiske kantar i det frosne uttrekket."
        ]}
    (F/"DEKNING_OG_BIAS.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    stats=groups
    out=F/"DEKNING_OG_BIAS.md"
    with out.open("w",encoding="utf-8") as f:
        f.write("# Utvalsdekning og risiko for feilslutning\n\n")
        f.write("**Status 6. november 2026.** Dette er intern datakvalitet i det frosne OpenAlex-uttrekket, ikkje ei måling av korleis nordisk designforsking faktisk fungerer.\n\n")
        f.write("## Det absolutte tilgangsproblemet\n\n")
        f.write(f"Me har **{coverage['works_in_frozen_openalex_extract']:,}** registrerte kandidatverk og **{coverage['document_pdf_in_open_repo']}** lisensierte PDF-ar offentleg arkiverte. Den valde køa på **{coverage['review_pairs']}** siteringspar har **{coverage['review_pairs_both_fulltext_pdf_public']}** par med begge originalane i det offentlege fulltekstarkivet og **{coverage['review_pairs_at_least_one_fulltext_pdf_public']}** med minst éin.\n\n".replace(","," "))
        f.write("Dette er det viktigaste praktiske hinderet for å teste P02 (kumulativitet) og P04 (overføringsverdi): Me kan ikkje lese ei faktisk vidareprøving utan både eldre påstand og nyare bruk. Null dokumentert test i denne arbeidskøa er **ikkje** null forsking.\n\n")
        f.write("## Samanlikning av utvalstypar\n\n")
        f.write("| Delramme | Par | Begge i auto-tittelramma | Begge med DOI | Begge med OA-metadata-URL | Negative årsgap | Median årsgap |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|\n")
        labels={"all_sample_internal_citations":"Heile interne grafen","uniform_random_120":"Tilfeldige kontrollpar","preexisting_purposive_150":"Målretta motprøvekandidatar","licensed_citing_pdf_71":"PDF-tilgjengelege siterande","combined_review_queue_336":"Samla arbeidskø"}
        for k,label in labels.items():
            s=stats[k]
            f.write(f"| {label} | {s['n']} | {s['both_original_title_gate_pct']} % | {s['both_doi_pct']} % | {s['both_oa_metadata_url_pct']} % | {s['citing_year_before_cited_year']} | {s['median_year_gap']} |\n")
        f.write("\nTabellen viser skilnader mellom **utvalsrutene**. Målretta treff kan ikkje representere faget; tilfeldig kontroll representerer berre interne kantar i det aktuelle metadatauttrekket. Med OA-URL meiner me at ei registrert lenkje finst, ikkje at PDF er lesbar eller lovleg å spegle.\n\n")
        f.write("## Årsvask og utvalsfeil\n\n")
        f.write(f"Me fann **{len(anomalies)}** interne siteringskoplingar der OpenAlex-året for siterande verk er eldre enn året for referert verk. Desse er lagde i [revisjonskø](REVISJON_ARSTAL_I_SITERINGAR.csv). Årsskilje kan kome av online-first, bokkapittel/utgåver, feil metadata eller feil identitetskopling. Det skal ikkje automatisk tolkast som oppdikta siteringar.\n\n")
        f.write("## Konsekvens for P01–P10\n\n")
        f.write("Studie A treng fleire lovleg tilgjengelege fulltekstar i **begge endar av siteringspar**, sidan kvar vurdering krev dokumenterte sider. Studie B og C treng offentlege institusjonsdokument, oppdragsloggar, evalueringar og habilitetshistorikk; slikt kan ikkje rekonstruerast ut frå bibliometriske signal. Kravet om to uavhengige faglege kodarar står uendra, og ingen av arbeidsfelta i blinde skjema er fylte.\n")
    print("BIAS_REPORT",json.dumps({"coverage":coverage,"groups":groups,"year_anomalies":len(anomalies)},ensure_ascii=False))
if __name__=="__main__":main()
