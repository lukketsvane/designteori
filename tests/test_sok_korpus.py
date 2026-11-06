"""Verifiser at søkjet kan lese kvart kjeldelag utan å slå saman status."""
import sqlite3
import unittest
from sok_korpus import search, match_query


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE works (
                id TEXT PRIMARY KEY,title TEXT,year INTEGER,
                doi TEXT,in_scope INTEGER,abstract TEXT);
            CREATE VIRTUAL TABLE works_fts USING fts5(
                title,abstract,content='works',content_rowid='rowid');
            CREATE TABLE source_candidates (
                id TEXT PRIMARY KEY,title TEXT,authors TEXT,
                year INTEGER,doi TEXT,source_layer TEXT,scope TEXT);
            CREATE VIRTUAL TABLE source_candidates_fts USING fts5(
                title,authors,source_layer,content='source_candidates',
                content_rowid='rowid');
            INSERT INTO works VALUES('W1','Design history',2020,'10.1234/w',1,'');
            INSERT INTO works VALUES('W2','Other research',2005,'',0,'');
            INSERT INTO source_candidates VALUES
                ('theory:1','Design methods','A Author',1950,'',
                 'historical','historical-reference'),
                ('nordic:1','Design studies','B Author',2022,'',
                 'nordic','editorial-candidate');
            INSERT INTO works_fts(works_fts) VALUES('rebuild');
            INSERT INTO source_candidates_fts(source_candidates_fts) VALUES('rebuild');
        """)

    def tearDown(self):
        self.db.close()

    def test_layers_not_promoted(self):
        all_rows = search(self.db, "design", "all")
        self.assertEqual(len(all_rows), 3)
        self.assertEqual({r["layer"] for r in all_rows},
                         {"openalex", "nordic", "historical"})
        historical = search(self.db, "design", "historical")
        self.assertEqual(len(historical), 1)
        self.assertEqual(historical[0]["scope"], "historical-reference")
        self.assertEqual(len(search(self.db, "history", "nordic")), 0)
        self.assertEqual(len(search(self.db, "history", "openalex")), 1)

    def test_safe_query(self):
        self.assertEqual(match_query('design" AND knowledge'), '"design" AND "AND" AND "knowledge"')
        for query in ["...", ""]:
            with self.assertRaises(ValueError):
                match_query(query)
        with self.assertRaises(ValueError):
            search(self.db, "design", layer="wrong")
        with self.assertRaises(ValueError):
            search(self.db, "design", limit=0)


if __name__ == "__main__":
    unittest.main()
