"""Offline tests for DOI CSV ingestion and safe public-OA queueing."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hent_doi_csv as importer


class DOIImportTests(unittest.TestCase):
    def test_normalize_doi(self):
        n = importer.normalize_doi
        self.assertEqual(n("DOI:10.1016/J.DESTUD.2018.04.001"),
                         "10.1016/j.destud.2018.04.001")
        self.assertEqual(n("https://doi.org/10.7577/formakademisk.123?foo=bar"),
                         "10.7577/formakademisk.123")
        self.assertEqual(n("https://dx.doi.org/10.1234%2FXYZ"),
                         "10.1234/xyz")
        self.assertEqual(n("10.1234/test)."), "10.1234/test")
        for value in ("", "not a DOI", "https://example.com/not-a-doi",
                      "https://sci-hub.se/10.1234/test", "10.2/bad"):
            self.assertEqual(n(value), "")

    def test_deduplicate_csv_with_bad_records(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "doi_liste.csv"
            path.write_text("DOI,title,oa_url\n"
                "10.1234/ABC,First,https://archive.example.org/1.pdf\n"
                "https://doi.org/10.1234/abc,Repeat,\n"
                "invalid,Wrong,\n"
                "10.5678/xyz,Second,https://sci-hub.se/x\n",
                encoding="utf-8")
            entries, summary = importer.read_dois(path)
        self.assertEqual(len(entries), 2)
        self.assertEqual(summary["duplicate_rows"], 1)
        self.assertEqual(summary["invalid_rows"], 1)
        self.assertEqual(entries[1]["oa_url"], "")

    def test_unique_ambiguous_and_outside_catalogue(self):
        entries = [{"doi": x, "title": "", "line": i+2, "oa_url": ""}
                   for i,x in enumerate(("10.1234/a", "10.1234/b", "10.1234/c"))]
        known = {
            "10.1234/a": [{"id": "W1", "title": "Test", "kind": "article",
                            "oa_url": "https://repo.example.org/test.pdf"}],
            "10.1234/b": [{"id": "W2"}, {"id": "W3"}]
        }
        rows = importer.make_rows(entries, known, {"W1"})
        self.assertEqual(rows[0]["id"], "W1")
        self.assertEqual(rows[0]["archived"], "yes")
        self.assertEqual(rows[1]["catalog_match"], "ambiguous-catalog-doi")
        self.assertTrue(rows[1]["id"].startswith("doi:"))
        self.assertEqual(rows[2]["catalog_match"], "doi-not-in-catalog")
        self.assertEqual(rows[0]["oa_url"], "https://repo.example.org/test.pdf")

    def test_provenance_is_retained_without_claiming_identity(self):
        with tempfile.TemporaryDirectory() as td, patch.object(importer.oa, "PRIVATE", Path(td)):
            input_file = Path(td) / "corpus.csv"
            input_file.write_text(
                "doi,source_ids,source_layer,scope,review_status,oa_url\n"
                "10.1234/xyz,W7;W8,openalex,automatic-title-inclusion,"
                "possible-duplicate-doi-needs-review,https://repo.example.org/paper.pdf\n",
                encoding="utf-8",
            )
            rows, _ = importer.read_dois(input_file)
            catalog = {"10.1234/xyz": [{"id": "W7"}, {"id": "W8"}]}
            staged = importer.make_rows(rows, catalog)
            self.assertEqual(staged[0]["catalog_match"], "ambiguous-catalog-doi")
            self.assertEqual(staged[0]["source_ids"], ["W7", "W8"])
            self.assertEqual(staged[0]["catalogue_ids"], ["W7", "W8"])
            importer.private_index(staged)
            meta = importer.oa.read_json(Path(td) / "doi_csv_metadata.json")
            self.assertEqual(meta[staged[0]["id"]]["source_ids_from_input"], ["W7", "W8"])
            self.assertEqual(meta[staged[0]["id"]]["source_review_status_from_input"],
                             "possible-duplicate-doi-needs-review")
            importer.write_report(staged, {}, {"unique_dois": 1})
            with (Path(td) / "doi_csv_report.csv").open(newline="", encoding="utf-8") as f:
                report_row = next(csv.DictReader(f))
            self.assertEqual(report_row["source_ids_from_input"], "W7;W8")
            self.assertEqual(report_row["catalogue_ids"], "W7;W8")

    def test_private_metadata_and_report_do_not_publish(self):
        with tempfile.TemporaryDirectory() as td, patch.object(importer.oa, "PRIVATE", Path(td)):
            rows = importer.make_rows([{"doi": "10.1234/a", "line": 2,
                                          "title": "Title", "oa_url": ""}], {})
            importer.private_index(rows)
            metadata = importer.oa.read_json(Path(td) / "doi_csv_metadata.json")
            self.assertEqual(metadata[rows[0]["id"]]["doi"], "https://doi.org/10.1234/a")
            report = importer.write_report(rows, {}, {"unique_dois": 1})
            self.assertEqual(report["statuses"]["not-attempted"], 1)
            with (Path(td) / "doi_csv_report.csv").open(newline="", encoding="utf-8") as f:
                parsed = list(csv.DictReader(f))
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0]["cache_verified"], "no")


if __name__ == "__main__":
    unittest.main()
