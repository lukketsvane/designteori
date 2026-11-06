"""Tests for DOI/title normalization, BibTeX parsing, and source provenance."""
from __future__ import annotations

import unittest

from designteori import doi_url, normalize_doi, normalize_title
from designteori.collect import evaluate_scope
from designteori.reconcile import parse_bibtex_entries


class TestReconcileAndProvenance(unittest.TestCase):
    def test_doi_and_title_normalization(self):
        self.assertEqual(normalize_doi("https://doi.org/10.7577/formakademisk.1421)."), "10.7577/formakademisk.1421")
        self.assertEqual(doi_url("DOI: 10.21606/nordes.2023.11"), "https://doi.org/10.21606/nordes.2023.11")
        self.assertEqual(
            normalize_title("Årsaker til formgivning: En nordisk studie!"),
            "arsaker til formgivning en nordisk studie",
        )

    def test_bibtex_parser_nested_braces(self):
        bib = """
        @book{ehn1988work,
          author = {Ehn, Pelle},
          title = {Work-Oriented Design of {Computer Artifacts}},
          year = {1988},
          publisher = {Arbetslivscentrum}
        }
        """
        entries = list(parse_bibtex_entries(bib))
        self.assertEqual(len(entries), 1)
        kind, key, fields = entries[0]
        self.assertEqual(kind, "book")
        self.assertEqual(key, "ehn1988work")
        self.assertEqual(fields["year"], "1988")
        self.assertIn("Computer Artifacts", fields["title"])

    def test_scope_gate_filters_clinical_noise_and_keeps_design_venues(self):
        inc1, _ = evaluate_scope("Scandinavian participatory design in public services", ["NO"], "")
        self.assertEqual(inc1, 1)
        inc2, _ = evaluate_scope("Randomized controlled trial study design of vaccine efficacy", ["SE"], "")
        self.assertEqual(inc2, 0)
        # Dedicated design venue (FormAkademisk S2764463729) passes even without "design" in title
        inc3, _ = evaluate_scope("Aesthetics of everyday Nordic wool", ["NO"], "https://openalex.org/S2764463729")
        self.assertEqual(inc3, 1)


if __name__ == "__main__":
    unittest.main()

