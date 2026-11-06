"""Expose editorial and historical references without merging them into OpenAlex counts."""
from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parent
def readcsv(path):
 with path.open(newline="",encoding="utf-8") as f:
  return list(csv.DictReader(f))
def main():
 rows=[]
 for r in readcsv(ROOT/"bibliografi"/"avstemt_mot_openalex.csv"):
  rows.append({
   "id":f"editorial:{len(rows)+1}","collection":"Nordisk redaksjonell bibliografi",
   "origin":"editorial","title":r["title"],
   "authors":r["authors_as_printed"],"year":r["year"],
   "type":"redaksjonell-kjeldeføring","doi":r["doi"],
   "url":"https://github.com/lukketsvane/designteori/blob/main/bibliografi/norden-2000-2026.md",
   "match":r["match_type"],"section":r["section"],
   "source_id":r["openalex_id"],"note":"Kjeldemerkt bibliografipost; fagleg identitet kan krevje verifikasjon."
  })
 for r in readcsv(ROOT/"bibliografi"/"historiske_referansar.csv"):
  rows.append({
   "id":r["source"]+":"+r["bibtex_key"],"collection":("GRUNNLAUST" if r["source"]=="grunnlaust" else "FORMLÆRE akademisk"),
   "origin":"historical","title":r["title"],"authors":r["authors"],
   "year":r["year"],"type":r["kind"],"doi":r["doi"],
   "url":r["url"] if r["url"].startswith("https://") else (
     "https://github.com/lukketsvane/designteori/blob/main/"+r["source_file"]
   ),"match":r["match_type"],"section":"",
   "source_id":r["openalex_id"],"note":"Historisk eller global teori-referanse; nordisk tilknyting er ikkje verifisert."
  })
 data={"count":len(rows),"disclaimer":"507 biblografiske oppføringar frå tre samlingar, ikkje 507 unike stadfesta nordiske publikasjonar.","items":rows}
 out=ROOT/"docs"/"data"/"bibliografiar.json"
 out.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
 print("PUBLIC_BIBLIOGRAPHIES",len(rows),"size",out.stat().st_size)
if __name__=="__main__":main()
