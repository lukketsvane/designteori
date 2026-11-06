"""Tests for Open Access PDF discovery, security gates, and repo `pdf/` sync."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from designteori.pdf import (
    allowed_url,
    cached_pdf_ok,
    candidate_https_url,
    extract_openalex_work_urls,
    pdf_candidates_from_html,
    pdf_data,
    repo_pdf_filename,
    safe_public_link,
    synthesized_oa_urls,
)


class TestPdfPipeline(unittest.TestCase):
    def test_https_upgrade_and_url_security(self):
        self.assertEqual(
            candidate_https_url("http://urn.kb.se/resolve?urn=urn:nbn:se:umu:diva-12345"),
            "https://urn.kb.se/resolve?urn=urn:nbn:se:umu:diva-12345",
        )
        self.assertTrue(allowed_url("https://journals.oslomet.no/index.php/formakademisk/article/download/123/456"))
        self.assertFalse(allowed_url("http://example.org/test.pdf"))
        self.assertFalse(allowed_url("https://localhost/secret.pdf"))
        self.assertFalse(allowed_url("https://127.0.0.1/secret.pdf"))
        self.assertFalse(allowed_url("https://sci-hub.se/10.1016/j.destud.2020.01.001"))
        self.assertFalse(allowed_url("https://annas-archive.org/md5/12345"))
        self.assertFalse(safe_public_link("https://example.org/file.pdf?access_token=secret123"))
        self.assertTrue(safe_public_link("https://dl.designresearchsociety.org/nordes/vol1/iss1/5.pdf"))

    def test_html_pdf_discovery(self):
        html = b"""
        <html><head>
          <meta name="bepress_citation_pdf_url" content="https://dl.designresearchsociety.org/cgi/viewcontent.cgi?article=1012&context=nordes">
          <meta name="citation_pdf_url" content="/index.php/formakademisk/article/view/402/511">
        </head><body>
          <a href="/bitstreams/abc-123/download">Download PDF</a>
        </body></html>
        """
        urls = pdf_candidates_from_html(html, "https://journals.oslomet.no/index.php/formakademisk/article/view/402")
        self.assertIn("https://dl.designresearchsociety.org/cgi/viewcontent.cgi?article=1012&context=nordes", urls)
        self.assertIn("https://journals.oslomet.no/index.php/formakademisk/article/download/402/511", urls)
        self.assertIn("https://journals.oslomet.no/bitstreams/abc-123/download", urls)

    def test_openalex_url_ranking_and_http_upgrade(self):
        work = {
            "best_oa_location": {
                "is_oa": True,
                "landing_page_url": "http://urn.kb.se/resolve?urn=urn:nbn:se:kth:diva-99",
                "pdf_url": "http://kth.diva-portal.org/smash/get/diva2:99/FULLTEXT01.pdf",
                "source": {"type": "repository"},
            }
        }
        urls = extract_openalex_work_urls(work)
        self.assertEqual(urls[0], "https://kth.diva-portal.org/smash/get/diva2:99/FULLTEXT01.pdf")
        self.assertIn("https://urn.kb.se/resolve?urn=urn:nbn:se:kth:diva-99", urls)

    def test_synthesized_oa_urls(self):
        urls = synthesized_oa_urls("10.48550/arXiv.2401.12345")
        self.assertIn("https://arxiv.org/pdf/2401.12345.pdf", urls)
        drs = synthesized_oa_urls("10.21606/nordes.2023.42")
        self.assertEqual(drs, ["https://doi.org/10.21606/nordes.2023.42"])

    def test_repo_pdf_filename_and_cache_integrity(self):
        self.assertEqual(repo_pdf_filename("W2108785486"), "W2108785486.pdf")
        slug = repo_pdf_filename("nordic:diva:oai:DiVA.org:kth-12345")
        self.assertTrue(slug.endswith(".pdf"))
        self.assertNotIn(":", slug)

        sample_pdf = b"%PDF-1.4\n" + (b"0123456789" * 80) + b"\n%%EOF\n"
        self.assertTrue(pdf_data(sample_pdf))
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            (tdir / "pdf").mkdir()
            wid = "W999999"
            fname = hashlib.sha256(wid.encode()).hexdigest()[:24] + ".pdf"
            (tdir / "pdf" / fname).write_bytes(sample_pdf)
            rec = {
                "status": "pdf-confirmed",
                "bytes": len(sample_pdf),
                "sha256": hashlib.sha256(sample_pdf).hexdigest(),
            }
            self.assertTrue(cached_pdf_ok(wid, rec, tdir))
            rec_bad = {**rec, "sha256": "0" * 64}
            self.assertFalse(cached_pdf_ok(wid, rec_bad, tdir))


if __name__ == "__main__":
    unittest.main()

