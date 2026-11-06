"""End-to-end integrity tests for the built DESIGNTEORI corpus."""
from __future__ import annotations

import unittest

from designteori.build import verify_all


class TestBuiltCorpusIntegrity(unittest.TestCase):
    def test_verify_all_invariants(self):
        result = verify_all(check_sqlite=True)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["openalex_works"], 12_000)
        self.assertGreater(result["nordic_candidates"], 1_000)
        self.assertGreater(result["repo_pdfs"], 2_000)
        self.assertEqual(
            result["embedded_works"],
            result["openalex_works"] + result["nordic_candidates"],
        )


if __name__ == "__main__":
    unittest.main()
