"""Tests for Google EmbeddingGemma / Gemini embeddings, int8 quantization, and RRF search."""
from __future__ import annotations

import math
import unittest

import numpy as np

from designteori.embeddings import (
    dequantize_int8,
    is_local_gemma,
    model_name,
    normalize_rows,
    pack_vector,
    quantize_int8,
    unpack_vector,
)
from designteori.fulltext import chunks_for_page
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


if __name__ == "__main__":
    unittest.main()

