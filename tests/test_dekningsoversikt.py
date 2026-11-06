"""Offline assertions for coverage denominators and duplicate-source cautions."""
import unittest
from bygg_dekningsoversikt import summarize, doi_key


class CoverageTests(unittest.TestCase):
    def test_separate_populations_and_cross_layer_overlap(self):
        base = [
            dict(id="W1", title="Design", year=2020, kind="article",
                 doi="https://doi.org/10.1234/a", authors=["A"],
                 scope="automatic-title-inclusion", countries=["NO"]),
            dict(id="W2", title="Other", year=2010, kind="book",
                 scope="awaiting-eligibility-review", countries=["SE"]),
        ]
        nordic = [
            dict(id="nordic:1", title="Nordic candidate", year=2000,
                 kind="article", doi="10.5678/b", authors=["B"],
                 scope="editorial-candidate"),
        ]
        historical = [
            dict(id="theory:1", title="Historical", year=1896, kind="book",
                 doi="https://doi.org/10.1234/a", countries=[],
                 scope="historical-reference"),
        ]
        report = summarize(
            base, nordic, historical,
            {"unlinked_candidate_records": 1},
            {"raw_historical_references": 2, "unique_provisional_candidate_records": 1},
        )
        self.assertEqual(report["openalex_partial_search"], 2)
        self.assertEqual(report["total_searchable_rows_all_layers"], 4)
        self.assertEqual(report["historical_original_bibliography_entries"], 2)
        self.assertEqual(report["openalex_title_gate"]["automatic-title-inclusion"], 1)
        self.assertEqual(
            report["cross_layer_or_within_layer_possible_doi_duplicates"]["duplicate_doi_keys"], 1)
        self.assertEqual(report["manual_article_eligibility_checks_completed"], 0)

    def test_validation_does_not_promote_references(self):
        base = [dict(id="W1", scope="automatic-title-inclusion")]
        with self.assertRaises(ValueError):
            summarize(base, [], [
                dict(id="theory:1", countries=["NO"], scope="historical-reference")],
                {"unlinked_candidate_records": 0},
                {"unique_provisional_candidate_records": 1})
        with self.assertRaises(ValueError):
            summarize(base + base, [], [],
                {"unlinked_candidate_records": 0},
                {"unique_provisional_candidate_records": 0})
        self.assertEqual(doi_key("https://doi.org/10.5555/X"), "10.5555/x")
        self.assertEqual(doi_key("https://bad.example/x"), "")


if __name__ == "__main__":
    unittest.main()
