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
        self.assertTrue(pdf.pdf_data(b"%PDF-1.7\n" + b"a" * 600 + b"%%EOF"))
        self.assertFalse(pdf.pdf_data(b"%PDF-1.7\n" + b"a" * 600))

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



    def test_archive_landing_pages_are_queued(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for folder in ("docs/data", "fulltekst"):
                (root / folder).mkdir(parents=True)
            (root / "docs/data/publications.json").write_text("[]", encoding="utf-8")
            (root / "docs/data/nordic_additions.json").write_text(json.dumps([{
                "id": "nordic:nva:1", "title": "Nordic research", "origin": "external",
                "scope": "repository-candidate",
                "source_url": "https://nva.example.org/record/1"
            }, {
                "id": "nordic:editorial:2", "title": "Reference", "origin": "editorial",
                "source_url": "https://github.com/lukketsvane/designteori"
            }]), encoding="utf-8")
            (root / "fulltekst/manifest.json").write_text('{"items":[]}', encoding="utf-8")
            with patch.object(pdf, "ROOT", root):
                rows, _ = pdf.queue_rows()
            self.assertEqual(len(rows), 2)
            self.assertEqual(next(r for r in rows if r["id"] == "nordic:nva:1")["oa_url"],
                             "https://nva.example.org/record/1")
            self.assertEqual(next(r for r in rows if r["id"] == "nordic:editorial:2")["oa_url"], "")

    def test_successful_direct_pdf_skips_discovery_apis(self):
        payload = b"%PDF-1.7\n" + b" " * 800 + b"%%EOF"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "private"
            progress = {}
            rows = [{"id": "Wxyz", "title": "Example", "doi": "https://doi.org/10.1/test",
                     "oa_url": "https://repository.example.org/example.pdf", "archived": "no"}]
            with patch.multiple(pdf, PRIVATE=root, LOG=root / "progress.json"), \
                 patch.object(pdf, "safe_request", return_value=(payload,
                     "https://repository.example.org/example.pdf", "application/pdf")), \
                 patch.object(pdf, "unpaywall_urls") as unpaywall, \
                 patch.object(pdf, "openalex_urls") as openalex, \
                 patch.object(pdf.time, "sleep"):
                n = pdf.download(rows, progress, limit=1, email="contact@example.org",
                                 pause=1, max_bytes=100000, retry_failed=False,
                                 lookup_openalex=True)
            self.assertEqual(n, 1)
            self.assertEqual(progress["Wxyz"]["status"], "pdf-confirmed")
            unpaywall.assert_not_called()
            openalex.assert_not_called()
            self.assertEqual(len(list((root / "pdf").glob("*.pdf"))), 1)

    def test_verified_cache_requires_real_bytes(self):
        import hashlib
        raw = b"%PDF-1.7\n" + b" " * 600 + b"%%EOF"
        with tempfile.TemporaryDirectory() as td:
            with patch.object(pdf, "PRIVATE", Path(td)):
                target = pdf.cache_path("W500")
                target.parent.mkdir(parents=True)
                target.write_bytes(raw)
                entry = {"status": "pdf-confirmed", "bytes": len(raw),
                         "sha256": hashlib.sha256(raw).hexdigest()}
                self.assertTrue(pdf.cached_pdf_ok("W500", entry))
                target.write_bytes(b"%PDF-1.7 broken")
                self.assertFalse(pdf.cached_pdf_ok("W500", entry))
                target.unlink()
                self.assertFalse(pdf.cached_pdf_ok("W500", entry))

    def test_atomic_progress_writes(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "progress.json"
            pdf.write_json(target, {"W1": {"status": "pdf-confirmed"}})
            self.assertEqual(json.loads(target.read_text())["W1"]["status"], "pdf-confirmed")
            pdf.write_json(target, {"W2": {"status": "failed"}})
            self.assertEqual(list(json.loads(target.read_text())), ["W2"])
            self.assertFalse(list(Path(td).glob("*.tmp")))

    def test_storage_limit_prevents_download(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            with patch.multiple(pdf, PRIVATE=Path(td), LOG=Path(td) / "progress.json"), \
                 patch.object(pdf, "safe_request") as request:
                result = pdf.download([
                    {"id": "W123", "archived": "no", "oa_url": "https://example.org/file.pdf",
                     "doi": "", "kind": "article"}
                ], {}, limit=1, email="", pause=1.0, max_bytes=1_000_000,
                   retry_failed=False, lookup_openalex=False,
                   max_cache_bytes=100, min_free_bytes=0)
            self.assertEqual(result, 0)
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
