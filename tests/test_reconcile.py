"""Tests for DOI/title normalization, BibTeX parsing, and strict design-theory eligibility."""
from __future__ import annotations

import unittest

from designteori import doi_url, normalize_doi, normalize_title
from designteori.collect import evaluate_scope
from designteori.eligibility import is_strict_nordic_archive_work
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

    def test_strict_scope_rejects_all_non_design_domains(self):
        inc1, _ = evaluate_scope("Scandinavian participatory design in public services", ["NO"], "")
        self.assertEqual(inc1, 1)
        # Dedicated design venue (FormAkademisk S2764463729) passes even without "design" in title
        inc2, _ = evaluate_scope("Aesthetics of everyday Nordic wool", ["NO"], "https://openalex.org/S2764463729")
        self.assertEqual(inc2, 1)
        # Reject clinical, PRISMA, genetics, 5G, mechanical/IS methodology, nursing
        for bad_title in (
            "Randomized controlled trial study design of vaccine efficacy",
            "PRISMA Extension for Scoping Reviews (PRISMA-ScR): Checklist and Explanation",
            "FinnGen provides genetic insights from a well-phenotyped isolated population",
            "What Will 5G Be?",
            "A Comprehensive Framework for Evaluation in Design Science Research",
            "Human fear conditioning: Considerations for study design and analysis",
            "Brukermedvirkning i sykepleie og pasientbehandling",
        ):
            inc, _ = evaluate_scope(bad_title, ["SE"], "")
            self.assertEqual(inc, 0, bad_title)
            self.assertFalse(is_strict_nordic_archive_work(bad_title, "DiVA", ""))
        self.assertFalse(is_strict_nordic_archive_work("Service design for cafes", "Theseus", "Theseus"))


if __name__ == "__main__":
    unittest.main()
