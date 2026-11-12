"""Tests for Google EmbeddingGemma / Gemini embeddings, int8 quantization, and RRF search."""
from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from designteori.embeddings import (
    dense_hits,
    dequantize_int8,
    eligible_chunks,
    is_local_gemma,
    model_name,
    normalize_rows,
    pack_vector,
    quantize_int8,
    unpack_vector,
)
from designteori.fulltext import chunks_for_page, connection as fulltext_connection
from designteori.search import reciprocal_rank_fusion, safe_fts_query, search_corpus


class TestGoogleEmbeddingsAndSearch(unittest.TestCase):
    def test_model_validation(self):
        self.assertEqual(model_name("models/embeddinggemma-300m"), "embeddinggemma-300m")
        self.assertTrue(is_local_gemma("embeddinggemma-300m"))
        self.assertFalse(is_local_gemma("gemini-embedding-001"))
        with self.assertRaises(ValueError):
            model_name("../bad/model")

    def test_matryoshka_normalization_and_int8_roundtrip(self):
        rng = np.random.default_rng(7)
        raw = rng.normal(size=(16, 768)).astype(np.float32)
        unit_128 = normalize_rows(raw, dims=128)
        self.assertEqual(unit_128.shape, (16, 128))
        norms = np.linalg.norm(unit_128, axis=1)
        np.testing.assert_allclose(norms, np.ones(16), atol=1e-5)

        blob = quantize_int8(unit_128)
        self.assertEqual(len(blob), 16 * 128)
        restored = dequantize_int8(blob, 128)
        cos_diag = np.sum(unit_128 * restored, axis=1)
        self.assertTrue(np.all(cos_diag > 0.998))

    def test_pack_unpack_float32(self):
        blob = pack_vector([3.0, 4.0, 0.0, 0.0], 2)
        vals = unpack_vector(blob, 2)
        self.assertAlmostEqual(vals[0], 0.6, places=5)
        self.assertAlmostEqual(vals[1], 0.8, places=5)
        self.assertAlmostEqual(math.hypot(*vals), 1.0, places=5)

    def test_page_chunking(self):
        sample = ("Participatory design in Scandinavia builds workplace democracy. " * 90).strip()
        spans = chunks_for_page(sample, target=900, overlap=150)
        self.assertGreaterEqual(len(spans), 5)
        for start, end, chunk in spans:
            self.assertLess(start, end)
            self.assertGreaterEqual(len(chunk), 80)

    def test_hybrid_rrf_and_fts_escape(self):
        q = safe_fts_query('participatory design: "Utopia" (1985)?')
        self.assertIn('"participatory"*', q)
        self.assertIn('"Utopia"*', q)
        fused = reciprocal_rank_fusion(
            ["W1", "W2", "W3"],
            ["W2", "W4", "W1"],
            k=60,
            weights=[1.0, 1.0],
        )
        top_ids = [wid for wid, _ in fused[:2]]
        self.assertEqual(set(top_ids), {"W1", "W2"})

    def test_eligible_chunks_active_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = fulltext_connection(Path(tmp) / "test.sqlite")
            try:
                with db:
                    for wid, sha, title in [("W_ACTIVE", "sha_a", "Active Title"), ("W_EXCLUDED", "sha_b", "Excluded Title")]:
                        db.execute("INSERT INTO works(work_id, title, rights) VALUES (?,?,?)", (wid, title, ""))
                        db.execute(
                            "INSERT INTO documents(sha256, file_path, bytes, pages, extracted_pages, char_count, extractor, chunk_version, quality, processed_at) "
                            "VALUES (?, ?, 1024, 1, 1, 24, 'pymupdf', 'page-v1-2300-300', 'extracted', '2026-01-01T00:00:00Z')",
                            (sha, f"/tmp/{sha}.pdf"),
                        )
                        db.execute("INSERT INTO work_documents(work_id, sha256) VALUES (?, ?)", (wid, sha))
                        db.execute(
                            "INSERT INTO chunks(chunk_id, sha256, page, ordinal, chunk_version, text_hash, text) "
                            "VALUES (?,?,?,?,?,?,?)",
                            (f"{sha}:1:0", sha, 1, 0, "page-v1-2300-300", f"h_{sha}", f"Body for {title}"),
                        )
                all_rows = eligible_chunks(db, "embeddinggemma-300m", 256, include_unreviewed=True)
                self.assertEqual([r[0] for r in all_rows], ["sha_a:1:0", "sha_b:1:0"])

                act_rows = eligible_chunks(db, "embeddinggemma-300m", 256, include_unreviewed=True, active_work_ids={"W_ACTIVE"})
                self.assertEqual([(r[0], r[3]) for r in act_rows], [("sha_a:1:0", "Active Title")])
            finally:
                db.close()

    def test_dense_hits_streaming_and_corrupt_blobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = fulltext_connection(Path(tmp) / "dense.sqlite")
            try:
                dims = 128
                vecs = {
                    "c1": [1.0, 0.0] + [0.0] * (dims - 2),
                    "c2": [0.8, 0.6] + [0.0] * (dims - 2),
                    "c3": [0.0, 1.0] + [0.0] * (dims - 2),
                    "c4": [0.9, 0.1] + [0.0] * (dims - 2),
                    "c5": [0.6, 0.8] + [0.0] * (dims - 2),
                }
                with db:
                    for cid, vec in vecs.items():
                        sha = f"sha_{cid}"
                        db.execute("INSERT INTO works(work_id, title, rights) VALUES (?,?,?)", (f"W_{cid}", cid, ""))
                        db.execute(
                            "INSERT INTO documents(sha256, file_path, bytes, pages, extracted_pages, char_count, extractor, chunk_version, quality, processed_at) "
                            "VALUES (?, ?, 100, 1, 1, 10, 'pymupdf', 'v1', 'extracted', '2026-01-01T00:00:00Z')",
                            (sha, f"/tmp/{sha}.pdf"),
                        )
                        db.execute(
                            "INSERT INTO chunks(chunk_id, sha256, page, ordinal, chunk_version, text_hash, text) VALUES (?,?,?,?,?,?,?)",
                            (cid, sha, 1, 0, "v1", f"h_{cid}", f"text {cid}"),
                        )
                        db.execute(
                            "INSERT INTO embeddings(chunk_id, model, dimensions, task_type, text_hash, vector, embedded_at) VALUES (?,?,?,?,?,?,?)",
                            (cid, "embeddinggemma-300m", dims, "RETRIEVAL_DOCUMENT", f"h_{cid}", pack_vector(vec, dims), "2026-01-01T00:00:00Z"),
                        )
                    db.execute("INSERT INTO works(work_id, title, rights) VALUES (?,?,?)", ("W_bad", "bad", ""))
                    db.execute(
                        "INSERT INTO documents(sha256, file_path, bytes, pages, extracted_pages, char_count, extractor, chunk_version, quality, processed_at) "
                        "VALUES ('sha_bad', '/tmp/bad.pdf', 100, 1, 1, 10, 'pymupdf', 'v1', 'extracted', '2026-01-01T00:00:00Z')"
                    )
                    db.execute(
                        "INSERT INTO chunks(chunk_id, sha256, page, ordinal, chunk_version, text_hash, text) "
                        "VALUES ('c_bad', 'sha_bad', 1, 0, 'v1', 'h_bad', 'bad')"
                    )
                    db.execute(
                        "INSERT INTO embeddings(chunk_id, model, dimensions, task_type, text_hash, vector, embedded_at) VALUES (?,?,?,?,?,?,?)",
                        ("c_bad", "embeddinggemma-300m", dims, "RETRIEVAL_DOCUMENT", "h_bad", b"corrupt", "2026-01-01T00:00:00Z"),
                    )

                q = [1.0, 0.0] + [0.0] * (dims - 2)
                self.assertEqual(dense_hits(db, q, dims=dims, limit=0), [])
                hits = dense_hits(db, q, dims=dims, limit=3, batch_rows=2)
                self.assertEqual([cid for cid, _ in hits], ["c1", "c4", "c2"])
                self.assertAlmostEqual(hits[0][1], 1.0, places=5)
                self.assertTrue(all(cid != "c_bad" for cid, _ in hits))
            finally:
                db.close()

    def test_search_corpus_fulltext_semantic_multi_work_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "corpus.sqlite"
            db = fulltext_connection(db_path)
            dims = 128
            try:
                with db:
                    for wid in ("W1", "W2", "W3"):
                        db.execute("INSERT INTO works(work_id, title, rights) VALUES (?,?,?)", (wid, wid, ""))
                    db.execute(
                        "INSERT INTO documents(sha256, file_path, bytes, pages, extracted_pages, char_count, extractor, chunk_version, quality, processed_at) "
                        "VALUES ('sha_shared', '/tmp/shared.pdf', 100, 3, 3, 60, 'pymupdf', 'v1', 'extracted', '2026-01-01T00:00:00Z')"
                    )
                    db.execute(
                        "INSERT INTO documents(sha256, file_path, bytes, pages, extracted_pages, char_count, extractor, chunk_version, quality, processed_at) "
                        "VALUES ('sha_other', '/tmp/other.pdf', 100, 1, 1, 30, 'pymupdf', 'v1', 'extracted', '2026-01-01T00:00:00Z')"
                    )
                    db.execute("INSERT INTO work_documents(work_id, sha256) VALUES ('W1', 'sha_shared')")
                    db.execute("INSERT INTO work_documents(work_id, sha256) VALUES ('W2', 'sha_shared')")
                    db.execute("INSERT INTO work_documents(work_id, sha256) VALUES ('W3', 'sha_other')")
                    db.execute(
                        "INSERT INTO chunks(chunk_id, sha256, page, ordinal, chunk_version, text_hash, text) "
                        "VALUES ('c_shared', 'sha_shared', 3, 0, 'v1', 'hs', 'Participatory design theory in practice')"
                    )
                    db.execute(
                        "INSERT INTO chunks(chunk_id, sha256, page, ordinal, chunk_version, text_hash, text) "
                        "VALUES ('c_other', 'sha_other', 1, 0, 'v1', 'ho', 'Unrelated statistical appendix')"
                    )
                    db.execute(
                        "INSERT INTO embeddings(chunk_id, model, dimensions, task_type, text_hash, vector, embedded_at) VALUES (?,?,?,?,?,?,?)",
                        ("c_shared", "embeddinggemma-300m", dims, "RETRIEVAL_DOCUMENT", "hs", pack_vector([1.0, 0.0] + [0.0] * (dims - 2), dims), "2026-01-01T00:00:00Z"),
                    )
                    db.execute(
                        "INSERT INTO embeddings(chunk_id, model, dimensions, task_type, text_hash, vector, embedded_at) VALUES (?,?,?,?,?,?,?)",
                        ("c_other", "embeddinggemma-300m", dims, "RETRIEVAL_DOCUMENT", "ho", pack_vector([0.0, 1.0] + [0.0] * (dims - 2), dims), "2026-01-01T00:00:00Z"),
                    )
            finally:
                db.close()

            fake_catalog = {
                "W1": {"id": "W1", "title": "First Shared", "year": 2020, "authors": [], "countries": ["NO"], "layer": "openalex", "pdf": "a.pdf"},
                "W2": {"id": "W2", "title": "Second Shared", "year": 2021, "authors": [], "countries": ["SE"], "layer": "nordic", "pdf": "b.pdf"},
                "W3": {"id": "W3", "title": "Other Paper", "year": 2019, "authors": [], "countries": ["DK"], "layer": "openalex", "pdf": "c.pdf"},
            }
            q_vec = [1.0, 0.0] + [0.0] * (dims - 2)
            with (
                mock.patch("designteori.search.DOCS_DATA_DIR", tmp_path),
                mock.patch("designteori.search._load_catalog_map", return_value=fake_catalog),
                mock.patch("designteori.search.query_embedding", return_value=q_vec),
            ):
                results = search_corpus("participatory theory", mode="semantic", corpus_db=db_path, limit=10)

            self.assertEqual([r["id"] for r in results[:2]], ["W1", "W2"])
            self.assertEqual(results[0]["excerpt"]["page"], 3)
            self.assertEqual(results[0]["excerpt"]["match"], "fulltext-semantic")
            self.assertAlmostEqual(results[0]["excerpt"]["chunk_cosine"], 1.0, places=4)
            self.assertEqual(results[1]["excerpt"]["page"], 3)


if __name__ == "__main__":
    unittest.main()

