"""Publish a transparent and prospective research question + evidence register.

E1 observations are source-located, tool-assisted pilot leads, not human-coded
or independently confirmed scientific results. This distinction must persist
in every format and view.
"""
from pathlib import Path
import csv
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parent
SRC = ROOT/"forsking"
OUT = ROOT/"docs"/"data"
REPORT = ROOT/"results"/"HYPOTESETEST_STATUS.md"
def main():
 claims = json.loads((SRC/"PASTANDAR.json").read_text(encoding="utf-8"))
 valid = {r["id"] for r in claims["claims"]}
 assert len(valid) == len(claims["claims"]) == 10
 raw = list(csv.DictReader((SRC/"KJELDESPOR_PILOT.csv").open(encoding="utf-8",newline="")))
 manifest = json.loads((ROOT/"fulltekst"/"manifest.json").read_text(encoding="utf-8"))
 licensed = {r["id"]:r for r in manifest["items"]}
 db=sqlite3.connect(ROOT/"data"/"nordic_design_research.sqlite")
 pilot=[]
 for r in raw:
  assert r["paper_id"] in licensed, r
  assert r["grade"] == "E1_tool_assisted_primary_source_location", r["paper_id"]
  assert r["human_coded"].lower()=="false", "Do not claim independent human coding"
  assert r["independent_replication_verified"].lower()=="false"
  assert all(c in valid for c in r["claims"].split(";"))
  assert re.fullmatch(r"[0-9]+(?:-[0-9]+)?(?:;[0-9]+(?:-[0-9]+)?)*",r["pdf_pages"])
  meta = db.execute("SELECT year,doi,title FROM works WHERE id=?",(r["paper_id"],)).fetchone()
  assert meta is not None and int(r["year"])==int(meta[0])
  assert r["doi"].rstrip("/").lower()==meta[1].rstrip("/").lower()
  first_page = int(r["pdf_pages"].split(";")[0].split("-")[0])
  assert first_page>=1
  pilot.append({
   **{k:r[k] for k in ["paper_id","title","year","doi","pdf_pages","direction","observation","limits","grade","followup"]},
   "claims":r["claims"].split(";"),
   "pdf_url":"https://github.com/lukketsvane/designteori/blob/main/fulltekst/"+licensed[r["paper_id"]]["pdf"],
   "license":licensed[r["paper_id"]]["license"],
   "human_coded":False,"independent_replication_verified":False,
  })
 output={
  "version":claims["version"],
  "created_utc":claims["created_utc"],
  "basis":claims["basis"],
  "rules":claims["rules"],
  "protocol":"https://github.com/lukketsvane/designteori/blob/main/forsking/PROTOKOLL.md",
  "claim_count":len(valid),
  "claims":claims["claims"],
  "pilot_evidence":pilot,
  "pilot_source_count":len(pilot),
  "not_validated_text":"Alle fem spor er verifiserte tekststader med verktøystøtta førstelesing. Ingen er dobbelkoda av uavhengige menneskelege kodarar; dette er ikkje eit estimat på utbreiing.",
 }
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/"forskingssporsmal.json").write_text(json.dumps(output,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
 table=[]
 for c in claims["claims"]:
  n=sum(c["id"] in r["claims"] for r in pilot)
  table.append(f"| {c['id']} | {c['key']} | {n} | Ikkje testa |")
 lines=[
 "# Test av den kritiske hypotesen: status",
 "",
 "**Status 6. november 2026.** Desse dokumenta er ein open prøveprotokoll,",
 "ikkje eit ferdig resultat eller ei ekstern førehandregistrering. Kritikken",
 "om manglande forskingsprogram, kunnskapsvekst og reell etterprøving er",
 "**arbeidshypotesar**. Testen skal søkje aktivt etter motdøme.",
 "",
 "## Protokoll og definisjonar",
 "",
 "- [Prøvingsprotokoll](../forsking/PROTOKOLL.md)",
 "- [Maskinlesbar påstandsmatrise](../forsking/PASTANDAR.json)",
 "- [Fem konkrete PDF-kjeldespor](../forsking/KJELDESPOR_PILOT.csv)",
 "- [Gjeldande kodebok](../CODEBOOK.md)",
 "",
 "## Kva er undersøkt?",
 "",
 "| Påstand | Tema | Kildespor (E1) | Fagleg status |",
 "|:--|:--|--:|:--|",
 *table,
 "",
 "## Første kjeldebaserte spor (ikkje validerte fagkodar)",
 "",
 ]
 for r in pilot:
  ident=", ".join(r["claims"])
  lines += [
   f"### {r['title']} ({r['year']})",
   "",
   f"**Påstandar:** {ident}. **PDF-sider:** {r['pdf_pages']}. "
   f"**[Original DOI]({r['doi']}) · [Arkivert PDF]({r['pdf_url']}).**",
   "",
   r["observation"],
   "",
   "**Avgrensing:** "+r["limits"],
   "",
   "**Vidare kontroll:** "+r["followup"],
   "",
  ]
 lines += [
  "## Ikkje tolka som resultat",
  "",
  "Dei fem spora er valde ut frå tilgjengelege PDF-ar og relevant innhald.",
  "Dei er ikkje eit tilfeldig utval. Sidetilvising og lesing med eit AI-verktøy",
  "er ikkje ein uavhengig menneskeleg kodar, og oppfyller ikkje E2/E3/E4.",
  "Ingen konklusjonar om representativ frekvens, institusjonell korrupsjon",
  "eller heile forskingsfeltet er tekne på dette grunnlaget.",
  "",
  "Det eldre 600-utvalet står framleis på 0 dobbelkoda fulltekstar.",
  "Nasjonale register, fleire sjangrar, kontrollfag og reelle kodarar må til",
  "før ei etterprøvbar vitskapsteoretisk generalisering.",
 ]
 REPORT.write_text("\n".join(lines)+"\n",encoding="utf-8")
 print("RESEARCH_PROTOCOL_ATLAS",len(valid),"CLAIMS",len(pilot),"SOURCE_LEADS")
if __name__=="__main__":main()
