"""Transparent *review-priority* signals for 7,300 OpenAlex candidates.

No automatic accept/reject, no fulltext claims. A high priority means 'worth
reading soon', not 'verified design theory'. A low priority is not exclusion.
The current corpus was ranked by search phrase, with known topic contamination.
"""
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,re,sqlite3,unicodedata
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"results"/"kandidatar_triage.csv"
POSITIVE={
 "design-theory":r"\b(?:design theory|theor(?:y|ies) of design|foundational design|design philosophy|design epistemology|designerly ways|design knowledge|design inquiry)\b",
 "practice-research":r"\b(?:research through design|research by design|design research|practice(?:[- ]based|[- ]led) research|design science research|research in design)\b",
 "methods":r"\b(?:design methods?|design methodology|design process(?:es)?|participatory design|co[- ]design|design thinking|user[- ]centred design)\b",
 "history":r"\b(?:design history|history of design|historiography of design|design discourse)\b",
 "ethics-aesthetics":r"\b(?:design ethics|ethics of design|design aesthetics|aesthetics of design|critical design|speculative design|design justice)\b",
 "systems-service":r"\b(?:systemic design|systems[- ]oriented design|service design|design for sustainab|ecological design|sustainable design practice)\b",
 "making":r"\b(?:design practice|design judgement|craft research|design cognition|design activity|artefact theory|artifact theory)\b",
}
VENUES=[
 "design studies","design issues","the design journal","formakademisk","international journal of design",
 "design science","co-design","codesign","nordes","design research society","iasdr","research in design",
 "artifact","the design society","she ji","journal of design history","design for health"
]
NEGATIVE=r"\b(?:inverter|power electronic|seismic|microstrip|antenna array|microgrid|wind turbine|power factor|lead[- ]acid battery|biosensor|neural network architecture|power electronics|turbulence|photovoltaic|seismic frame|cadmium|filter design|circuit design|genetic algorithm)\b"
def norm(x):return re.sub(r"[^a-z0-9]","",unicodedata.normalize("NFKD",x or "").lower())
def normdoi(s):return re.sub(r"^https?://(?:dx[.])?doi[.]org/","",(s or "").lower().strip(),flags=re.I).rstrip(".,;")
def main():
 db=sqlite3.connect(ROOT/"data/nordic_design_research.sqlite")
 edt=set()
 with (ROOT/"bibliografi/avstemt_mot_openalex.csv").open(encoding="utf-8",newline="") as fp:
  edt.update(r["openalex_id"] for r in csv.DictReader(fp) if r["openalex_id"])
 with (ROOT/"bibliografi/historiske_referansar.csv").open(encoding="utf-8",newline="") as fp:
  edt.update(r["openalex_id"] for r in csv.DictReader(fp) if r["openalex_id"])
 citation_in=Counter()
 for (id,) in db.execute("SELECT cited_id FROM references_all r JOIN works w ON w.id=r.citing_id JOIN works v ON v.id=r.cited_id WHERE r.citing_id != r.cited_id"):
  citation_in[id]+=1
 rows=[]
 for wid,doi,title,year,source,topic,kind,selected in db.execute("SELECT id,doi,title,year,source,topic,kind,in_scope FROM works"):
  t=(title or "").casefold();s=(source or "").casefold()
  signals=[tag for tag,pattern in POSITIVE.items() if re.search(pattern,t)]
  score=5;reasons=[]
  if signals:
   score+=38+min(17,6*(len(signals)-1))
   reasons.extend(signals)
  if any(v in s for v in VENUES):
   score+=25;reasons.append("design-venue-keyword")
  if selected:score+=7;reasons.append("original-title-gate")
  if wid in edt:
   score+=38;reasons.append("editorial-bibliography-identity-match")
  if citation_in[wid]>=3:
   score+=min(12,2*citation_in[wid]);reasons.append("sample-internal-citations")
  if re.search(NEGATIVE,t):
   score-=22;reasons.append("technical-design-ambiguity")
  # 'design' as a generic synonym for configuration or study design is not a
  # sufficient reason to treat a work as theoretical.
  if re.search(r"\bdesign\b",t) and not signals and not any(v in s for v in VENUES):
   reasons.append("generic-design-word-only")
  score=max(0,min(100,score))
  priority="high" if score>=65 else "medium" if score>=35 else "low"
  rows.append({"id":wid,"year":year,"title":title or "","doi":doi or "",
   "source":source or "","original_title_gate":int(selected),
   "priority_score":score,"review_priority":priority,
   "keyword_categories":";".join(signals),"signals":";".join(reasons),
   "editorial_id_match":int(wid in edt),
   "source":"OpenAlex snapshot 2026-11-02; reproducible rules, no manual eligibility decision"})
 rows.sort(key=lambda r:(-r["priority_score"],-r["year"],r["id"]))
 with OUT.open("w",encoding="utf-8",newline="") as fp:
  w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 catalog={r["id"]:{k:r[k] for k in ("review_priority","priority_score","keyword_categories","signals")} for r in rows}
 (ROOT/"docs/data/triage.json").write_text(json.dumps(catalog,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
 stats={"all":dict(Counter(r["review_priority"] for r in rows)),
 "original-title-gate":dict(Counter(r["review_priority"] for r in rows if r["original_title_gate"])),
 "excluded-original":dict(Counter(r["review_priority"] for r in rows if not r["original_title_gate"])),
 "manual_acceptance_decisions":0,
 "warning":"Priority ranking from metadata only; not an evidence-based finding of relevance, quality, replicability or cumulative theory.",
 "high_priority_examples":[{k:r[k] for k in ("id","title","priority_score","signals")} for r in rows[:15]]}
 (ROOT/"results"/"TRIAGE_STATUS.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("TRIAGE",stats["all"],"selected",stats["original-title-gate"])
 print("HIGHEST",[(r["priority_score"],r["title"][:80]) for r in rows[:10]])
if __name__=="__main__":main()
