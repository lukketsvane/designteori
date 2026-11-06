"""Offline tests: missing references are not silently promoted into the corpus."""
import sqlite3
import unittest

from bygg_referansefrontier import analyze


class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.executescript("""
            CREATE TABLE works(id TEXT PRIMARY KEY, in_scope INTEGER, year INTEGER, source TEXT);
            CREATE TABLE references_all(citing_id TEXT, cited_id TEXT,
                PRIMARY KEY(citing_id,cited_id));
            INSERT INTO works VALUES
                ('W100',1,2021,'Journal A'),
                ('W200',0,2018,'Journal B'),
                ('W300',1,2025,'Journal C'),
                ('W900',1,2010,'Journal D');
            INSERT INTO references_all VALUES
                ('W100','W999'),('W200','W999'),('W300','W999'),
                ('W100','W888'),('W300','W888'),
                ('W100','W900'),('W200','W777'),
                ('W100','NOT_A_WORK');
        """)

    def tearDown(self):
        self.c.close()

    def test_scope_and_deduplication(self):
        rows, summary = analyze(self.c, minimum=2, limit=10, bibliography={})
        self.assertEqual([r["openalex_id"] for r in rows], ["W999", "W888"])
        self.assertEqual(rows[0]["citing_works"], 3)
        self.assertEqual(rows[0]["citing_title_included"], 2)
        self.assertEqual(rows[0]["citing_2020_onwards"], 2)
        self.assertEqual(summary["unresolved_reference_ids"], 3)
        self.assertEqual(summary["unresolved_cited_by_at_least_2"], 2)
        self.assertEqual(summary["unresolved_cited_by_at_least_10"], 0)
        self.assertEqual(summary["known_works"], 4)
        self.assertNotIn("W900", {r["openalex_id"] for r in rows})
        self.assertNotIn("NOT_A_WORK", {r["openalex_id"] for r in rows})

    def test_boundary_and_crosswalk(self):
        bib = {"W888": [{"title": "Published Design Theory",
                          "doi": "10.1234/test",
                          "bibtex_key": "sample2020"}]}
        rows, summary = analyze(self.c, minimum=1, limit=2, bibliography=bib)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["existing_bibliography_doi"], "10.1234/test")
        self.assertEqual(summary["already_crosswalked_in_historical_bibliography"], 1)
        with self.assertRaises(ValueError):
            analyze(self.c, minimum=0, bibliography={})


if __name__ == "__main__":
    unittest.main()
