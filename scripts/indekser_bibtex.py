"""Index historic BibTeX references separately from the Nordic research sampling frame.

Retains original BibTeX files and every record's provenance. Unknown regional
eligibility and duplicate identities stay unresolved, rather than being invented.
"""
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,re,sqlite3,unicodedata
ROOT=Path(__file__).resolve().parents[1]
SOURCES=[
 ("grunnlaust","bibliografi/grunnlaust_referansar.bib"),
 ("formlaere-akademisk","bibliografi/formlaere_akademisk.bib"),
]
def norm(s):
 s=(s or "").replace("\\textit","").replace("\\emph","")
 s=unicodedata.normalize("NFKD",s).casefold()
 return re.sub(r"[^a-z0-9]","",s)
def doi_norm(s):
 s=re.sub(r"^https?://(?:dx[.])?doi[.]org/","",(s or ""),flags=re.I)
 return s.strip().lower().rstrip(".,;)")
def parsed_entries(content):
 pattern=re.compile(r"@([a-zA-Z]+)\s*\{\s*([^,{}]+)\s*,",re.M)
 cursor=0
 for m in pattern.finditer(content):
  if m.start()<cursor:continue
  depth=1;quote=False;escaped=False
  pos=m.end()
  while pos<len(content):
   c=content[pos]
   if escaped:escaped=False;pos+=1;continue
   if c=="\\":escaped=True;pos+=1;continue
   if c=='"':quote=not quote;pos+=1;continue
   if not quote:
    if c=="{":depth+=1
    elif c=="}":
     depth-=1
     if depth==0:break
   pos+=1
  if depth!=0:raise ValueError("Unclosed BibTeX entry "+m.group(2))
  cursor=pos+1
  yield m.group(1).lower(),m.group(2).strip(),content[m.end():pos]
def fields_from_body(s):
 chunks=[];depth=0;quote=False;escaped=False;start=0
 for ix,c in enumerate(s):
  if escaped:escaped=False;continue
  if c=="\\":escaped=True;continue
  if c=='"':quote=not quote;continue
  if not quote:
   if c=="{":depth+=1
   elif c=="}":depth-=1
   elif c=="," and depth==0:
    chunks.append(s[start:ix]);start=ix+1
 chunks.append(s[start:])
 fields={}
 for chunk in chunks:
  match=re.match(r"\s*([A-Za-z][\w-]*)\s*=\s*(.*?)\s*$",chunk,re.S)
  if not match:continue
  raw=match.group(2)
  # Keep nested LaTeX text, normalize only enclosing delimiters.
  if len(raw)>1 and ((raw[0]=="{" and raw[-1]=="}") or (raw[0]=='"' and raw[-1]=='"')):raw=raw[1:-1]
  fields[match.group(1).lower()]=raw.strip()
 return fields
def main():
 db=sqlite3.connect(ROOT/"data/nordic_design_research.sqlite")
 by_doi={doi_norm(doi):id for id,doi in db.execute("SELECT id,doi FROM works") if doi}
 by_title={(norm(title),year):id for id,title,year in db.execute("SELECT id,title,year FROM works") if title}
 all_records=[]
 for source,relative in SOURCES:
  content=(ROOT/relative).read_text(encoding="utf-8")
  for typ,key,body in parsed_entries(content):
   f=fields_from_body(body)
   year_raw=f.get("year") or f.get("date") or ""
   ym=re.search(r"\d{4}",year_raw)
   year=int(ym.group()) if ym else None
   title=f.get("title") or f.get("booktitle") or ""
   doi=doi_norm(f.get("doi") or "")
   openalex_id=by_doi.get(doi) if doi else None
   match_type="doi" if openalex_id else ""
   if not openalex_id and title and year:
    openalex_id=by_title.get((norm(title),year))
    if openalex_id:match_type="title-year-normalized"
   if not match_type:match_type="requires-identity-check"
   all_records.append({
    "source":source,"source_file":relative,"bibtex_key":key,"kind":typ,
    "authors":f.get("author") or f.get("editor") or "",
    "title":title,"year":year or "","doi":("https://doi.org/"+doi) if doi else "",
    "publisher":f.get("publisher") or f.get("journal") or f.get("journaltitle") or "",
    "isbn":f.get("isbn") or "","url":f.get("url") or "",
    "openalex_id":openalex_id or "","match_type":match_type,
    "nordic_affiliation_status":"unverified","raw_fields_json":json.dumps(f,ensure_ascii=False)
   })
 if len(all_records)<400:raise SystemExit("Unexpected BibTeX read count: "+str(len(all_records)))
 path=ROOT/"bibliografi"/"historiske_referansar.csv"
 with path.open("w",encoding="utf-8",newline="") as out:
  wr=csv.DictWriter(out,fieldnames=list(all_records[0]))
  wr.writeheader();wr.writerows(all_records)
 groups=defaultdict(list)
 for x in all_records:
  key=doi_norm(x["doi"]) if x["doi"] else (norm(x["title"]),x["year"])
  groups[str(key)].append(x)
 duplicates=[g for g in groups.values() if len(g)>1]
 stats={
  "source_counts":dict(Counter(x["source"] for x in all_records)),
  "total_entries":len(all_records),
  "source_openalex_matches":dict(Counter(x["match_type"] for x in all_records)),
  "duplicate_bibtex_groups":len(duplicates),
  "unique_identity_candidates_within_bibliographies":len(groups),
  "description":"Historical/theoretical reference bibliographies, including global works, not a Nordic scholarly publication population."
 }
 (ROOT/"bibliografi"/"historiske_referansar_status.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("HISTORIC_BIBTEX",stats)
 print("PENDING_EXAMPLES",[(x["year"],x["title"][:55]) for x in all_records if not x["openalex_id"]][:12])
if __name__=="__main__":main()
