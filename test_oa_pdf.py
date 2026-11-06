"""Offline checks for the PDF queue, URL hygiene and licensing boundaries."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hent_oa_pdf as pdf


class PDFHarvestTest(unittest.TestCase):
    def test_url_whitelist_public_https_only(self):
        self.assertTrue(pdf.allowed_url("https://journals.oslomet.no/article/download/1/2"))
        self.assertFalse(pdf.allowed_url("http://example.org/a.pdf"))
        self.assertFalse(pdf.allowed_url("https://127.0.0.1/a.pdf"))
        self.assertFalse(pdf.allowed_url("https://localhost/a.pdf"))
        self.assertFalse(pdf.allowed_url("https://sci-hub.se/10.1111/example"))
        self.assertFalse(pdf.allowed_url("https://username:password@example.org/a.pdf"))
        self.assertFalse(pdf.allowed_url("https://example.org:444/a.pdf"))
        self.assertFalse(pdf.allowed_url("file:///etc/passwd"))
        self.assertFalse(pdf.allowed_url("https://192.168.0.1/a.pdf"))

    def test_pdf_detection(self):
        self.assertFalse(pdf.pdf_data(b"<html>paywall</html>"))
        self.assertTrue(pdf.pdf_data(b"%PDF-1.7\n" + b"a" * 600))

    def test_html_discovery(self):
        html = (b'<html><head><meta name="citation_pdf_url" '
                b'content="/media/item.pdf"></head><body>'
                b'<a href="https://archive.org/bitstream/1/download">PDF</a></body></html>')
        result = pdf.pdf_candidates_from_html(html, "https://journals.example.org/work/1")
        self.assertEqual(result[0], "https://journals.example.org/media/item.pdf")
        self.assertEqual(len(result), 2)

    def test_queue_keeps_all_works_and_separates_archived(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for folder in ("docs/data", "fulltekst"):
                (root / folder).mkdir(parents=True)
            (root / "docs/data/publications.json").write_text(
                json.dumps([
                    {"id": "W1", "title": "A", "kind": "article",
                     "oa_url": "https://repo.example.org/a.pdf"},
                    {"id": "W2", "title": "B", "kind": "review", "doi": "https://doi.org/10.11/test"},
                ]), encoding="utf-8")
            (root / "docs/data/nordic_additions.json").write_text(
                json.dumps([{"id": "nordic:x", "title": "C", "kind": "editorial-candidate"}]),
                encoding="utf-8")
            (root / "fulltekst/manifest.json").write_text(
                json.dumps({"items": [{"id": "W1", "original_fulltext_url":
                          "https://repo.example.org/a.pdf", "sha256": "abc", "license": "CC BY 4.0"}]}),
                encoding="utf-8")
            with patch.object(pdf, "ROOT", root):
                rows, published = pdf.queue_rows()
            self.assertEqual(len(rows), 3)
            self.assertEqual(sum(x["archived"] == "yes" for x in rows), 1)
            self.assertEqual({r["candidate_status"] for r in rows},
                             {"archived", "doi-only", "no-oa-link"})
            self.assertEqual(len(pdf.remote_links({}, published)), 1)

    def test_successful_links_are_not_republication_grants(self):
        links = pdf.remote_links({"W1": {"status": "pdf-confirmed",
                                        "url": "https://repo.example.org/a.pdf",
                                        "sha256": "xyz"}},
                                 {"items": []})
        self.assertEqual(links["W1"]["status"], "private-cache-only")
        self.assertEqual(links["W1"]["license"], "")


if __name__ == "__main__":
    unittest.main()
