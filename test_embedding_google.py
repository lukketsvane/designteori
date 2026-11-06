"""Offline Google embedding contract, privacy and hybrid-retrieval tests."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bygg_fulltekstkorpus as corpus
import embedding_google as google


class GoogleEmbeddingTests(unittest.TestCase):
    def test_model_and_dimensions(self):
        self.assertEqual(google.model_name("models/gemini-embedding-001"),
                         "gemini-embedding-001")
        with self.assertRaises(ValueError):
            google.model_name("../../malicious")
        self.assertEqual(len(google.pack_vector([3, 4], 2)), 8)
        self.assertAlmostEqual(sum(x*x for x in google.unpack_vector(
            google.pack_vector([3, 4], 2), 2)), 1.0, places=6)
        with self.assertRaises(ValueError):
            google.pack_vector([0, 0], 2)

    def test_google_payload_is_document_vs_query(self):
        with patch.object(google, "google_request",
                          return_value={"embeddings":[{"values":[0.1,0.2]}]}) as request:
            self.assertEqual(google.batch_embeddings(
                ["Design theory"],"gemini-embedding-001",2)[0],[0.1,0.2])
            endpoint, payload = request.call_args.args
            self.assertEqual(endpoint,"gemini-embedding-001:batchEmbedContents")
            self.assertEqual(payload["requests"][0]["taskType"],"RETRIEVAL_DOCUMENT")
            self.assertEqual(payload["requests"][0]["outputDimensionality"],2)
        with patch.object(google,"google_request",
                          return_value={"embedding":{"values":[0.5,0.2]}}) as request:
            self.assertEqual(google.query_embedding(
                "Research through design","gemini-embedding-001",2),[0.5,0.2])
            self.assertEqual(request.call_args.args[1]["taskType"],"RETRIEVAL_QUERY")

    def test_unreviewed_content_needs_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=corpus.connection(Path(tmp)/"corpus.sqlite")
            for wid,sha,rights in [("W1","a"*64,"CC BY 4.0"),
                                   ("W2","b"*64,"unreviewed"),
                                   ("W3","c"*64,"CC BY-NC-ND 4.0")]:
                db.execute("""INSERT INTO works VALUES(?,?,?,?,?,?,?)""",
                           (wid,wid,"",2021,"Author","Journal",rights))
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (sha,"doc.pdf",1500,1,1,180,"pypdf",corpus.CHUNK_VERSION,
                            "extracted",corpus.timestamp()))
                db.execute("INSERT INTO work_documents VALUES(?,?,?)",(wid,sha,""))
                txt = "An exploration of participatory design in Nordic education. " * 5
                h=hashlib.sha256(txt.encode()).hexdigest()
                db.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?,?)",
                           (wid,sha,1,0,corpus.CHUNK_VERSION,h,txt))
            db.commit()
            self.assertEqual(len(google.eligible(db,"gemini-embedding-001",768)),1)
            self.assertEqual(len(google.eligible(db,"gemini-embedding-001",768,
                                                 include_unreviewed=True)),3)
            with self.assertRaises(ValueError):
                google.embed(db_path=Path(tmp)/"corpus.sqlite",
                             consent_cloud=False)
            db.close()

    def test_embedding_idempotency_and_citation(self):
        with tempfile.TemporaryDirectory() as tmp:
            dbpath=Path(tmp)/"corpus.sqlite"
            db=corpus.connection(dbpath)
            sha="d"*64
            cid="chunk-test"
            txt="Participatory design methods are important for teaching design. " * 8
            h=hashlib.sha256(txt.encode()).hexdigest()
            db.execute("INSERT INTO works VALUES(?,?,?,?,?,?,?)",
                       ("W7","Article title","10.7777/demo",2023,"Researcher",
                        "Nordic Journal","CC BY 4.0"))
            db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (sha,"C:/corpus/paper.pdf",900,1,1,len(txt),"pypdf",
                        corpus.CHUNK_VERSION,"extracted",corpus.timestamp()))
            db.execute("INSERT INTO work_documents VALUES(?,?,?)",("W7",sha,""))
            db.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?,?)",
                       (cid,sha,2,0,corpus.CHUNK_VERSION,h,txt))
            db.commit()
            db.close()
            with patch.dict("os.environ",{"GOOGLE_API_KEY":"fake-offline-key"}),\
                 patch.object(google,"batch_embeddings",return_value=[
                     [1.0] + [0.0]*767]):
                summary=google.embed(model="gemini-embedding-001",dims=768,
                                     db_path=dbpath,limit=5,batch=5,pause=0,
                                     consent_cloud=True)
                self.assertEqual(summary["new_embeddings"],1)
                again=google.embed(model="gemini-embedding-001",dims=768,
                                   db_path=dbpath,limit=5,batch=5,pause=0,
                                   consent_cloud=True)
                self.assertEqual(again["new_embeddings"],0)
            db=corpus.connection(dbpath)
            self.assertEqual(google.dense_hits(db,[1.0]+[0.0]*767,
                                               model="gemini-embedding-001",
                                               dims=768),[cid])
            db.close()


if __name__=="__main__":
    unittest.main()
