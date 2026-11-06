"""Search fulltext across licensed public papers, with contextual FTS5 snippets.

  python sok_fulltekst.py "design theory"
  python sok_fulltekst.py '"participatory design"' --limit 20
"""
from pathlib import Path
import argparse
import gzip
import shutil
import sqlite3
ROOT=Path(__file__).resolve().parent
def run():
 p=argparse.ArgumentParser()
 p.add_argument("phrase",help="SQLite FTS5 search expression")
 p.add_argument("--limit",type=int,default=20)
 args=p.parse_args()
 archive=ROOT/"data"/"fulltekst_sok.sqlite.gz"
 db=ROOT/"data"/"fulltekst_sok.sqlite"
 if not db.exists() or db.stat().st_mtime<archive.stat().st_mtime:
  with gzip.open(archive,"rb") as src,db.open("wb") as out:shutil.copyfileobj(src,out)
 conn=sqlite3.connect(f"file:{db.as_posix()}?mode=ro",uri=True)
 query="""SELECT f.id,s.title,s.authors,s.year,s.doi,s.license,
 snippet(fulltext_fts,3,'[',']',' … ',18) AS excerpt, bm25(fulltext_fts)
 FROM fulltext_fts AS f JOIN sources AS s ON s.id=f.id
 WHERE fulltext_fts MATCH ? ORDER BY bm25(fulltext_fts) LIMIT ?"""
 try:
  results=conn.execute(query,(args.phrase,min(100,max(1,args.limit)))).fetchall()
 except sqlite3.OperationalError as e:
  raise SystemExit(f"Invalid FTS expression: {e}") from e
 print(f"{len(results)} fulltekst-treff\n")
 for id,title,authors,year,doi,licence,excerpt,score in results:
  print(f"{year} — {title}\n{authors}\n{doi} · {licence}\n{excerpt}\n")
if __name__=="__main__":run()
