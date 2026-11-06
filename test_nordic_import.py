"""Offline tests for Nordic repository export adapters and conservative matching."""
import json
import tempfile
import unittest
from pathlib import Path

from import_norden import add, doi, kind, normalize, read_records, record_authors
from samkoyr_norden import normalized_doi, normalized_title


class ImportTests(unittest.TestCase):
    def test_doi_normalization(self):
        self.assertEqual(doi("https://doi.org/10.1016/J.DESTUD.2018.04.001"),
                         "10.1016/j.destud.2018.04.001")
        self.assertEqual(normalized_doi("https://doi.org/10.1016/j.destud.2018.04.001"),
                         "10.1016/j.destud.2018.04.001")
        self.assertEqual(doi("not a DOI"), "")

    def test_normalized_title(self):
        self.assertEqual(normalized_title("Førmåling: Design–Teori!"),
                         normalized_title("Førmåling design teori"))

    def test_csv_import_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "export.csv"
            dest = Path(tmp) / "staging.json"
            path.write_text("title,year,DOI,authors,publicationType\n"
                            '"Design theory in practice",2018,10.1234/test.001,'
                            '"Frida Berg; Signe Holm",AcademicArticle\n', encoding="utf-8")
            self.assertEqual(add("nva", path, dest), (1, 1))
            self.assertEqual(add("nva", path, dest), (1, 1))
            item = json.loads(dest.read_text(encoding="utf-8"))[0]
            self.assertEqual(item["kind"], "article")
            self.assertEqual(item["source"], "nva")
            self.assertEqual(item["source_country"], "NO")
            self.assertEqual(item["affiliation_status"], "not-verified")
            self.assertEqual(item["doi"], "https://doi.org/10.1234/test.001")
            self.assertEqual(len(item["authors"]), 2)

    def test_ris(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diva.ris"
            path.write_text("TY  - JOUR\nTI  - Nordic design methods\n"
                            "AU  - S. Example\nPY  - 2019\n"
                            "DO  - 10.1234/example\nER  -\n", encoding="utf-8")
            entries = list(read_records(path))
            self.assertEqual(len(entries), 1)
            item = normalize(entries[0], "diva")
            self.assertEqual(item["kind"], "article")
            self.assertEqual(item["authors"], ["S. Example"])

    def test_oai_dc(self):
        xml = """<?xml version="1.0"?>
        <OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"
            xmlns:dc="http://purl.org/dc/elements/1.1/">
          <ListRecords><record>
            <header><identifier>oai:test:123</identifier></header>
            <metadata><dc:collection><dc:title>Participatory Design</dc:title>
            <dc:creator>Else Andersen</dc:creator><dc:date>2020</dc:date>
            <dc:identifier>https://doi.org/10.4321/test</dc:identifier>
            <dc:type>journal article</dc:type></dc:collection></metadata>
          </record></ListRecords>
        </OAI-PMH>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.xml"
            path.write_text(xml, encoding="utf-8")
            entries = list(read_records(path))
            self.assertEqual(len(entries), 1)
            item = normalize(entries[0], "chalmers")
            self.assertEqual(item["kind"], "article")
            self.assertEqual(item["source_record_id"], "oai:test:123")
            self.assertEqual(item["doi"], "https://doi.org/10.4321/test")

    def test_nva_json(self):
        item = normalize({
            "identifier": "0181-abc",
            "title": {"en": "Systems Oriented Design"},
            "publicationDate": {"year": "2024"},
            "contributors": [{"identity": {"name": "N. Example"}}],
            "type": "AcademicArticle"
        }, "nva")
        self.assertEqual(item["year"], 2024)
        self.assertEqual(item["authors"], ["N. Example"])
        self.assertEqual(item["kind"], "article")



    def test_reconciliation_keeps_uncertain_titles(self):
        import samkoyr_norden as reconcile_module
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public = root / "docs" / "data"
            public.mkdir(parents=True)
            (root / "data").mkdir()
            (root / "results").mkdir()
            (public / "publications.json").write_text(json.dumps([{
                "id": "W1", "doi": "https://doi.org/10.4321/test",
                "title": "Nordic design methods", "year": 2020
            }]), encoding="utf-8")
            (public / "bibliografiar.json").write_text(json.dumps({"items": [
                {"id": "editorial:1", "origin": "editorial",
                 "title": "Nordic design methods", "year": "2020",
                 "doi": "https://doi.org/10.4321/test", "source_id": "", "authors": "A. Author"},
                {"id": "editorial:2", "origin": "editorial",
                 "title": "Nordic design methods", "year": "2020",
                 "doi": "", "source_id": "", "authors": "A. Author"}
            ]}), encoding="utf-8")
            (root / "data" / "nordic_imports.json").write_text("[]", encoding="utf-8")
            with patch.multiple(reconcile_module, ROOT=root, PUBLIC=public,
                                AUDIT=root / "results" / "nordic_source_audit.csv",
                                OUTPUT=public / "nordic_additions.json",
                                STATUS=public / "nordic_status.json"):
                result = reconcile_module.reconcile()
            self.assertEqual(result["matched_exact"], 1)
            self.assertEqual(result["unlinked_candidate_records"], 1)
            self.assertEqual(result["possible_duplicate_records"], 1)
            unmatched = json.loads((public / "nordic_additions.json").read_text())
            self.assertEqual(unmatched[0]["duplicate_status"], "possible-duplicate")
            self.assertEqual(len(json.loads((public / "source_links.json").read_text())["W1"]), 1)

if __name__ == "__main__":
    unittest.main()
