"""End-to-end integrity and strict disciplinary purity tests for DESIGNTEORI."""
from __future__ import annotations

import unittest

from designteori import DOCS_DATA_DIR, PDF_DIR, read_json
from designteori.build import verify_all
from designteori.eligibility import FORBIDDEN_VENUES_RE, HARD_NON_DESIGN_RE


class TestBuiltCorpusIntegrity(unittest.TestCase):
    def test_verify_all_invariants(self):
        result = verify_all(check_sqlite=True)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["openalex_works"], 3_500)
        self.assertGreater(result["nordic_candidates"], 1_000)
        self.assertGreaterEqual(result["repo_pdfs"], 1_000)
        self.assertEqual(
            result["embedded_works"],
            result["openalex_works"] + result["nordic_candidates"],
        )

    def test_zero_non_design_papers_anywhere(self):
        pubs = read_json(DOCS_DATA_DIR / "publications.json", []) or []
        nordic = read_json(DOCS_DATA_DIR / "nordic_additions.json", []) or []
        manifest = (read_json(PDF_DIR / "manifest.json", {}) or {}).get("items", {}) or {}
        valid_ids = {w["id"] for w in pubs} | {w["id"] for w in nordic}

        for w in pubs:
            self.assertEqual(w.get("scope"), "automatic-title-inclusion")
            self.assertIsNone(HARD_NON_DESIGN_RE.search(w.get("title") or ""), w.get("title"))
            self.assertIsNone(FORBIDDEN_VENUES_RE.search(w.get("source") or ""), w.get("source"))

        for w in nordic:
            self.assertIsNone(HARD_NON_DESIGN_RE.search(w.get("title") or ""), w.get("title"))
            self.assertIsNone(
                FORBIDDEN_VENUES_RE.search(f"{w.get('source') or ''} {w.get('venue') or ''}"),
                w.get("title"),
            )

        # Every PDF in pdf/manifest.json must belong to a verified pure design-theory work
        self.assertTrue(set(manifest.keys()).issubset(valid_ids))


if __name__ == "__main__":
    unittest.main()
