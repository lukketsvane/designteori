"""Offline reproducible source-to-DOI queue tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from bygg_doi_eksport import make_export, build

class DOICorpusExportTests(unittest.TestCase):
    def test_prioritisation_and_duplicate_identity_hold(self):
        base = [
            dict(id="W1", doi="https://doi.org/10.1234/test",
                 title="A research paper", kind="article",
                 scope="automatic-title-inclusion", oa_url=""),
            dict(id="W2", doi="10.1234/OTHER", title="Second",
                 kind="article", scope="automatic-title-inclusion",
                 oa_url="https://archive.example.org/other.pdf"),
            dict(id="W3", doi="10.1234/test", title="Duplicate record",
                 kind="book", scope="awaiting-eligibility-review", oa_url="")
        ]
        nordic = [
            dict(id="nordic:1", doi="10.1234/external", origin="external",
                 kind="article", title="Repository work",
                 scope="repository-candidate",
                 source_url="https://research.example.org/record/1")
        ]
        historical = [
            dict(id="theory:1", doi="10.1234/theory",
                 kind="book", title="Historical book",
                 scope="historical-reference")
        ]
        rows, s = make_export(base, nordic, historical)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["doi"], "https://doi.org/10.1234/other")
        self.assertEqual(s["doi_keys_with_multiple_source_records"], 1)
        self.assertEqual(s["doi_with_oa_url"], 2)
        self.assertEqual(s["doi_with_direct_pdf_shaped_url"], 1)
        duplicate = next(x for x in rows if x["doi"].endswith("/test"))
        self.assertEqual(duplicate["candidate_count"], 2)
        self.assertEqual(duplicate["review_status"], "possible-duplicate-doi-needs-review")
        self.assertEqual(duplicate["source_ids"], "W1;W3")
        repo = next(x for x in rows if x["doi"].endswith("/external"))
        self.assertEqual(repo["priority"], "oa-landing-or-url")
        self.assertEqual(repo["scope"], "repository-candidate")

    def test_no_invalid_doi_or_unsafe_oa(self):
        works = [
            dict(id="W1", doi="not DOI", title="Bad"),
            dict(id="W2", doi="https://doi.org/10.4321/ok",
                 oa_url="https://sci-hub.se/10.4321/ok"),
            dict(id="W3", doi="", title="Unknown"),
        ]
        rows, stats = make_export(works, [], [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["oa_url"], "")
        self.assertEqual(stats["registrations_without_valid_doi"]["openalex"], 2)
        with self.assertRaises(ValueError):
            make_export([works[1], works[1]], [], [])

    def test_build_matches_reader_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "docs/data"
            data.mkdir(parents=True)
            (data/"publications.json").write_text(json.dumps([
                dict(id="W1", title="Design theory", doi="10.1234/abc",
                     oa_url="https://archive.example.org/design.pdf",
                     kind="article", scope="automatic-title-inclusion"),
            ]), encoding="utf-8")
            (data/"nordic_additions.json").write_text("[]", encoding="utf-8")
            (data/"theory_additions.json").write_text("[]", encoding="utf-8")
            first = build(root)
            csv_path = root/"results/doi_eksport.csv"
            before = csv_path.read_bytes()
            second = build(root)
            self.assertEqual(first,second)
            self.assertEqual(csv_path.read_bytes(),before)
            with csv_path.open(newline="",encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["doi"],"https://doi.org/10.1234/abc")
            self.assertEqual(rows[0]["oa_url"],"https://archive.example.org/design.pdf")

if __name__ == "__main__":
    unittest.main()
