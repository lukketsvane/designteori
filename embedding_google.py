#!/usr/bin/env python3
"""Google Gemini embeddings for the private DESIGNTEORI PDF corpus.

- Default model is a conservative configurable baseline, not a claim of "latest".
- No API calls without --embed or --search and a GOOGLE_API_KEY.
- No unreviewed texts are sent off-device without --include-unreviewed.
- Vectors are stored locally and versioned by chunk, model, and dimensions.
- Original PDFs, extracted fulltexts, and vectors are never pushed to GitHub.
"""
from __future__ import annotations

import argparse
from array import array
import json
import math
import os
import re
import sqlite3
import struct
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import bygg_fulltekstkorpus as corpus

DEFAULT_MODEL = os.environ.get("GOOGLE_EMBEDDING_MODEL", "gemini-embedding-001")
DEFAULT_DIM = 768
ALLOWED_DIMENSIONS = (768, 1536, 3072)


def model_name(raw):
    value = raw.removeprefix("models/").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise ValueError("Invalid embedding model name")
    return value


def google_request(endpoint, body, *, key=None, retries=4):
    key = key or os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY is not set. Do not store it in Git.")
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{endpoint}",
        data=json.dumps(body,ensure_ascii=False,separators=(",",":")).encode("utf-8"),
        headers={"x-goog-api-key":key,"Content-Type":"application/json"},
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urlopen(request,timeout=90) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in (429,500,502,503,504) or attempt==retries-1:
                detail = error.read(800).decode("utf-8","replace")
                raise RuntimeError(f"Google embeddings HTTP {error.code}: {detail}") from error
            wait = error.headers.get("Retry-After", "")
            delay = float(wait) if wait.isdecimal() else min(30,2 ** attempt)
            print(f"GOOGLE_RETRY {error.code}, pause {delay}s",flush=True)
            time.sleep(delay)
        except (URLError,TimeoutError) as error:
            if attempt==retries-1:
                raise RuntimeError("Google embedding API unreachable") from error
            time.sleep(min(30,2 ** attempt))
    raise RuntimeError("Unreachable retry loop")


def batch_embeddings(texts, model, dims, *, key=None):
    name = "models/" + model_name(model)
    request = {
        "requests": [{
            "model": name,
            "content": {"parts":[{"text":text}]},
            "taskType":"RETRIEVAL_DOCUMENT",
            "outputDimensionality":dims
        } for text in texts]
    }
    result = google_request(f"{model_name(model)}:batchEmbedContents",request,key=key)
    vectors = result.get("embeddings") or []
    if len(vectors)!=len(texts):
        raise RuntimeError(f"Expected {len(texts)} embeddings; Google returned {len(vectors)}")
    return [item["values"] for item in vectors]


def query_embedding(text, model, dims, *, key=None):
    m = "models/" + model_name(model)
    request = {
        "model":m, "content":{"parts":[{"text":text}]},
        "taskType":"RETRIEVAL_QUERY",
        "outputDimensionality":dims
    }
    result = google_request(f"{model_name(model)}:embedContent",request,key=key)
    values = (result.get("embedding") or {}).get("values")
    if not values:
        raise RuntimeError("No query embedding returned")
    return values


def pack_vector(values, dimensions):
    if len(values)!=dimensions:
        raise ValueError("Unexpected vector dimensions")
    values = [float(v) for v in values]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Non-finite vector from embedding provider")
    norm = math.sqrt(sum(v*v for v in values))
    if norm<1e-15:
        raise ValueError("Zero embedding vector")
    return struct.pack("<"+str(dimensions)+"f",*[v/norm for v in values])


def unpack_vector(blob, dimensions):
    if len(blob)!=dimensions*4:
        raise ValueError("Invalid embedding blob")
    return struct.unpack("<"+str(dimensions)+"f",blob)


def eligible(db, model, dims, *, include_unreviewed=False, limit=0):
    restriction = "" if include_unreviewed else """
      AND EXISTS (
        SELECT 1 FROM work_documents wd JOIN works w ON w.work_id=wd.work_id
        WHERE wd.sha256=c.sha256 AND w.rights LIKE 'CC %'
          AND w.rights NOT LIKE '%-ND%' AND w.rights NOT LIKE '% ND%'
      )"""
    sql = """SELECT c.chunk_id,c.text_hash,c.text
         FROM chunks c JOIN documents d ON d.sha256=c.sha256
         LEFT JOIN embeddings e ON e.chunk_id=c.chunk_id AND e.model=? AND e.dimensions=?
         WHERE d.quality='extracted'
           AND (e.chunk_id IS NULL OR e.text_hash <> c.text_hash)""" + restriction + """
         ORDER BY c.chunk_id"""
    params = [model,dims]
    if limit:
        sql+=" LIMIT ?"
        params.append(limit)
    return db.execute(sql,params).fetchall()


def embed(*, model=DEFAULT_MODEL, dims=DEFAULT_DIM, limit=100, batch=12,
          pause=1.0, include_unreviewed=False, consent_cloud=False, db_path=corpus.DB):
    if not consent_cloud:
        raise ValueError("Pass --consent-cloud to send full-text excerpts to Google.")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError("Set GOOGLE_API_KEY in the local environment first.")
    db=corpus.connection(db_path)
    model=model_name(model)
    rows=eligible(db,model,dims,include_unreviewed=include_unreviewed,limit=limit)
    complete=0
    for offset in range(0,len(rows),batch):
        batch_rows=rows[offset:offset+batch]
        vectors=batch_embeddings([r[2] for r in batch_rows],model,dims)
        with db:
            for (cid,checksum,_),raw in zip(batch_rows,vectors):
                packed=pack_vector(raw,dims)
                db.execute("""INSERT INTO embeddings
                  (chunk_id,model,dimensions,task_type,text_hash,vector,embedded_at)
                  VALUES(?,?,?,?,?,?,?)
                  ON CONFLICT(chunk_id,model,dimensions) DO UPDATE SET
                    text_hash=excluded.text_hash,vector=excluded.vector,
                    embedded_at=excluded.embedded_at""",
                  (cid,model,dims,"RETRIEVAL_DOCUMENT",checksum,packed,
                   corpus.timestamp()))
                complete+=1
        print(f"GOOGLE_EMBEDDED {complete}/{len(rows)} model={model} dims={dims}",flush=True)
        if offset+batch<len(rows):
            time.sleep(pause)
    summary={"new_embeddings":complete,"model":model,"dimensions":dims,
             "all_embedding_rows":db.execute(
               "SELECT COUNT(*) FROM embeddings WHERE model=? AND dimensions=?",
               (model,dims)).fetchone()[0],"database":str(db_path)}
    db.close()
    print(json.dumps(summary,ensure_ascii=False))
    return summary


def lexical_hits(db,query,limit=50):
    tokens=re.findall(r"[\w]{2,}",query,flags=re.UNICODE)
    if not tokens:
        return []
    expr=" OR ".join('"'+part.replace('"','')+'"' for part in tokens)
    rows=db.execute("""SELECT c.chunk_id
      FROM chunks_fts f JOIN chunks c ON c.rowid=f.rowid
      WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?""",
      (expr,limit)).fetchall()
    return [r[0] for r in rows]


def dense_hits(db, vector, *, model, dims, limit=50):
    """Exact cosine scan; model/dimension-safe. Replace with ANN at larger scale."""
    packed=pack_vector(vector,dims)
    query=unpack_vector(packed,dims)
    ranked=[]
    # Optional NumPy accelerates large corpora, but is not needed to build one.
    try:
        import numpy as np
    except ImportError:
        np=None
    cursor=db.execute("""SELECT chunk_id,vector FROM embeddings
                        WHERE model=? AND dimensions=?""",(model,dims))
    for cid,blob in cursor:
        if len(blob)!=4*dims:
            continue
        if np is None:
            values=unpack_vector(blob,dims)
            score=sum(a*b for a,b in zip(query,values))
        else:
            values=np.frombuffer(blob,dtype="<f4")
            score=float(np.dot(values,np.asarray(query,dtype="<f4")))
        ranked.append((score,cid))
    ranked.sort(reverse=True)
    return [cid for _,cid in ranked[:limit]]


def hybrid(query, *, model=DEFAULT_MODEL,dims=DEFAULT_DIM,limit=10,
           db_path=corpus.DB,weight_dense=1.0):
    """Reciprocal-rank fusion, with exact page and source attribution."""
    db=corpus.connection(db_path)
    model=model_name(model)
    lexical=lexical_hits(db,query,limit=max(100,limit*8))
    dense=[]
    n=db.execute("SELECT COUNT(*) FROM embeddings WHERE model=? AND dimensions=?",
                 (model,dims)).fetchone()[0]
    if n:
        vec=query_embedding(query,model,dims)
        dense=dense_hits(db,vec,model=model,dims,limit=max(100,limit*8))
    scores={}
    for group,scale in [(lexical,1.0),(dense,weight_dense)]:
        for rank,cid in enumerate(group):
            scores[cid]=scores.get(cid,0)+scale/(60+rank+1)
    winners=sorted(scores,key=lambda cid:-scores[cid])[:limit]
    for cid in winners:
        chunk=db.execute("SELECT sha256,page,text FROM chunks WHERE chunk_id=?",
                         (cid,)).fetchone()
        if not chunk:
            continue
        sha,page,text=chunk
        docs=db.execute("""SELECT w.work_id,w.title,w.doi,d.file_path,w.rights
          FROM work_documents wd
          JOIN works w ON wd.work_id=w.work_id
          JOIN documents d ON d.sha256=wd.sha256
          WHERE wd.sha256=? ORDER BY w.work_id""",(sha,)).fetchall()
        print(json.dumps({"score":round(scores[cid],6),"chunk_id":cid,
          "page":page,"text_excerpt":text[:480],
          "sources":[{"work_id":wid,"title":title,"doi":doi,"pdf":file,"rights":rights}
                     for wid,title,doi,file,rights in docs]},ensure_ascii=False))
    print(json.dumps({"lexical_candidates":len(lexical),"semantic_candidates":len(dense),
        "google_embeddings_indexed":n,"model":model,"dimensions":dims},ensure_ascii=False))
    db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan",action="store_true")
    group.add_argument("--embed",action="store_true")
    group.add_argument("--search")
    p.add_argument("--model",default=DEFAULT_MODEL)
    p.add_argument("--dims",type=int,choices=ALLOWED_DIMENSIONS,default=DEFAULT_DIM)
    p.add_argument("--limit",type=int,default=100)
    p.add_argument("--batch",type=int,default=12)
    p.add_argument("--pause",type=float,default=1.0)
    p.add_argument("--consent-cloud",action="store_true")
    p.add_argument("--include-unreviewed",action="store_true")
    args=p.parse_args()
    if args.limit<1 or not 1<=args.batch<=32 or args.pause<0:
        p.error("Invalid limit, batch or pause")
    model=model_name(args.model)
    if args.plan:
        db=corpus.connection()
        rows=eligible(db,model,args.dims,include_unreviewed=args.include_unreviewed)
        print(json.dumps({"pending_chunks":len(rows),"model":model,"dimensions":args.dims,
          "unreviewed_included":args.include_unreviewed,
          "cloud_key_present":bool(os.environ.get("GOOGLE_API_KEY")),
          "note":"No text sent. API requests incur provider terms, cost and data-handling policies."},
          ensure_ascii=False,indent=2))
        db.close()
    elif args.embed:
        embed(model=model,dims=args.dims,limit=args.limit,batch=args.batch,
              pause=args.pause,include_unreviewed=args.include_unreviewed,
              consent_cloud=args.consent_cloud)
    else:
        hybrid(args.search,model=model,dims=args.dims,limit=args.limit)


if __name__=="__main__":
    main()
