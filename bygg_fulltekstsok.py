"""Create a portable local FTS5 index for legally archived fulltext.

This index intentionally omits CC BY-NC-ND papers (no derived text).
"""
from pathlib import Path
import gzip
import json
import sqlite3
import tempfile
import os
import shutil
ROOT=Path(__file__).resolve().parent
DEST=ROOT/"data"/"fulltekst_sok.sqlite.gz"
def main():
 manifest=json.loads((ROOT/"fulltekst"/"manifest.json").read_text(encoding="utf-8"))["items"]
 fd,temp=tempfile.mkstemp(prefix="designteori_",suffix=".sqlite")
 os.close(fd)
 tmp=Path(temp)
 try:
  con=sqlite3.connect(tmp)
  con.executescript("""
  PRAGMA journal_mode=DELETE;
  CREATE TABLE sources(id TEXT PRIMARY KEY,title TEXT,authors TEXT,year INTEGER,doi TEXT,license TEXT,pdf_path TEXT,text_path TEXT,sha256 TEXT);
  CREATE VIRTUAL TABLE fulltext_fts USING fts5(id UNINDEXED,title,authors,text,tokenize='unicode61 remove_diacritics 2');
  """)
  count=0
  for r in manifest:
   if not r["text"]:continue
   if "ND" in r["license"]:raise SystemExit("ND_NOT_ALLOWED")
   content=(ROOT/"fulltekst"/r["text"]).read_text(encoding="utf-8")
   authors=", ".join(r["authors"])
   con.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?)",(r["id"],r["title"],authors,r["year"],r["doi"],r["license"],r["pdf"],r["text"],r["sha256"]))
   con.execute("INSERT INTO fulltext_fts(id,title,authors,text) VALUES(?,?,?,?)",(r["id"],r["title"],authors,content))
   count+=1
  con.commit()
  con.close()
  with tmp.open("rb") as src,gzip.open(DEST,"wb",compresslevel=9) as dst:shutil.copyfileobj(src,dst)
  print("FULLTEXT_INDEX",count,"documents",round(DEST.stat().st_size/1048576,2),"MiB")
 finally:
  if tmp.exists():tmp.unlink()
if __name__=="__main__":main()
