"""Tests for Google EmbeddingGemma / Gemini embeddings, int8 quantization, and RRF search."""
from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from designteori.embeddings import (
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
from designteori.search import reciprocal_rank_fusion, safe_fts_query


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


if __name__ == "__main__":
    unittest.main()

