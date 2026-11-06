"""Cross-check the editorial Nordic bibliography against the OpenAlex candidate corpus.

No invisible deduplication: unresolved titles are a review queue, not new verified works.
"""
from __future__ import annotations
import csv
import re
import sqlite3
from pathlib import Path
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parent
md=ROOT/"bibliografi"/"norden-2000-2026.md"
DB=ROOT/"data"/"nordic_design_research.sqlite"
OUT=ROOT/"bibliografi"/"avstemt_mot_openalex.csv"
def norm(s):
 return re.sub(r"[^a-z0-9]", "", (s or "").casefold().replace("ø","o").replace("æ","ae").replace("å","a"))
def doi_norm(s):
 s=(s or "").strip()
 s=re.sub(r"^https?://(?:dx[.])?doi[.]org/","",s,flags=re.I)
 return unquote(s).lower().rstrip(".,;)")
def main():
 conn=sqlite3.connect(f"file:{DB.as_posix()}?mode=ro",uri=True)
 ids={doi_norm(doi):id for id,doi in conn.execute("SELECT id,doi FROM works") if doi}
 titles={}
 for id,t,y in conn.execute("SELECT id,title,year FROM works"):
  if norm(t):titles[(norm(t),y)]=id
 entries=[];section="unassigned"
 for line in md.read_text(encoding="utf-8").splitlines():
  if line.startswith("### 3."):section=line.removeprefix("### ").strip();continue
  if not line.startswith("- "):continue
  match=re.match(r"- (.+?)\s+\((\d{4})\)\.\s+(.+)",line)
  if not match:continue
  author,year,rest=match.groups()
  # Titles occur inside « » for articles and * * for books.
  title_match=re.search(r"«([^»]+)»|\*([^*]+)\*",rest)
  title=(title_match.group(1) or title_match.group(2)) if title_match else ""
  doi_match=re.search(r"https?://doi[.]org/([^\s)]+)",line,flags=re.I)
  doi=doi_norm(doi_match.group(1)) if doi_match else ""
  y=int(year)
  id=ids.get(doi) if doi else None
  match_type="doi_exact" if id else ""
  if not id and title:
   id=titles.get((norm(title),y))
   if id:match_type="title_year_exact_normalised"
  if not id:match_type="requires_manual_bibliographic_check"
  entries.append({
   "section":section,"authors_as_printed":author,"year":year,
   "title":title,"doi":("https://doi.org/"+doi) if doi else "",
   "openalex_id":id or "", "match_type":match_type,
   "source_document":"bibliografi/norden-2000-2026.md",
   "review_status":"editorial-candidate; not independently verified"
  })
 if not entries:raise SystemExit("NO_EDITORIAL_ENTRIES")
 with OUT.open("w",encoding="utf-8",newline="") as out:
  wr=csv.DictWriter(out,fieldnames=list(entries[0]));wr.writeheader();wr.writerows(entries)
 from collections import Counter
 print("EDITORIAL_ENTRIES",len(entries),"MATCHES",dict(Counter(x["match_type"] for x in entries)))
 print("MISSING_EXAMPLES",[(x["authors_as_printed"],x["year"],x["title"][:75]) for x in entries if not x["openalex_id"]][:18])
if __name__=="__main__":main()
