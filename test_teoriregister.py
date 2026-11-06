"""Test separat teoriregister, DOI-identitet og forsiktig dublettkontroll."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from bygg_teoriregister import build, author_key


class TheoryRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for d in ["docs/data", "bibliografi", "results"]:
            (self.root / d).mkdir(parents=True, exist_ok=True)
        (self.root / "docs/data/publications.json").write_text(json.dumps([
            {"id": "W123", "title": "Existing Paper", "year": 2016,
             "doi": "https://doi.org/10.5555/existing-paper"},
            {"id": "W456", "title": "Design Classics", "year": 1970, "doi": ""},
        ]), encoding="utf-8")
        (self.root / "docs/data/nordic_additions.json").write_text(json.dumps([
            {"id": "nordic:editorial:1", "title": "Nordic Work", "year": 2020,
             "doi": "https://doi.org/10.7777/nordic"},
        ]), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def create_rows(self, rows):
        with (self.root / "bibliografi/historiske_referansar.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=(
                "source", "source_file", "bibtex_key", "kind", "authors",
                "title", "year", "doi", "publisher", "isbn", "url",
                "openalex_id", "match_type", "nordic_affiliation_status",
                "raw_fields_json"
            ))
            writer.writeheader()
            for i, row in enumerate(rows):
                default = {
                    "source": "test", "source_file": "bibliografi/test.bib",
                    "bibtex_key": "key" + str(i), "kind": "book",
                    "authors": "Smith, Ada", "title": "Other Work " + str(i),
                    "year": "2010", "doi": "", "publisher": "Publisher", "isbn": "",
                    "url": "", "openalex_id": "", "match_type": "",
                    "nordic_affiliation_status": "", "raw_fields_json": "{}",
                }
                default.update(row)
                writer.writerow(default)

    def test_doi_and_candidate_separation(self):
        self.create_rows([
            {"title": "Existing Paper", "doi": "10.5555/existing-paper"},
            {"title": "Nordic Work", "doi": "10.7777/nordic"},
            {"title": "Global Work", "year": "1969", "authors": "Jones, Jo"},
            {"title": "Global Work", "year": "1969", "authors": "Jones, Jo",
             "source": "second", "bibtex_key": "duplicate"},
            {"title": "Design Classics", "year": "1970",
             "authors": "Different Author", "openalex_id": "W456"},
            {"title": "Other Paper", "doi": "10.1111/other"},
        ])
        stats = build(self.root)
        rows = json.loads((self.root / "docs/data/theory_additions.json").read_text())
        audit = list(csv.DictReader((self.root / "results/theory_source_audit.csv").open()))
        self.assertEqual(stats["raw_historical_references"], 6)
        self.assertEqual(stats["matched_openalex_exact_doi"], 1)
        self.assertEqual(stats["matched_nordic_editorial_exact_doi"], 1)
        self.assertEqual(stats["unique_provisional_candidate_records"], 3)
        self.assertEqual(stats["source_references_collapsed"], 1)
        self.assertEqual(len(audit), 6)
        self.assertEqual(len({row["id"] for row in rows}), 3)
        self.assertTrue(all(r["scope"] == "historical-reference" for r in rows))
        self.assertEqual(next(r for r in rows if r["title"] == "Global Work")["bibliography_entries"], 2)
        self.assertEqual(next(r for r in audit if r["title"] == "Design Classics")["status"],
                         "possible-openalex-id")
        self.assertTrue(all(not r["countries"] and not r["pdf"] for r in rows))
        self.assertEqual(author_key("Smith, Ada and Jones, Jo"), "smith")

    def test_unknown_authors_do_not_join_by_title(self):
        self.create_rows([
            {"title": "Untitled identity A", "year": "2001", "authors": ""},
            {"title": "Untitled identity A", "year": "2001", "authors": "",
             "bibtex_key": "second"},
        ])
        stats = build(self.root)
        self.assertEqual(stats["unique_provisional_candidate_records"], 2)
        self.assertEqual(stats["source_references_collapsed"], 0)


if __name__ == "__main__":
    unittest.main()
