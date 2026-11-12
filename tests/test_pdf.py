"""Tests for Open Access PDF discovery, security gates, and repo `pdf/` sync."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from designteori.pdf import (
    _normalize_candidate,
    allowed_url,
    cached_pdf_ok,
    candidate_https_url,
    extract_diva_query,
    extract_dspace_handle,
    extract_nva_uuid,
    extract_openalex_work_urls,
    expand_registered_oa_urls,
    is_bot_challenge_html,
    parse_core_urls,
    parse_diva_export_csv,
    parse_dspace_bitstream_urls,
    parse_nva_publication_artifacts,
    parse_oai_ojs_records,
    parse_openaire_urls,
    pdf_candidates_from_html,
    pdf_data,
    repo_pdf_filename,
    safe_public_link,
    synthesized_oa_urls,
    unwrap_pdf_payload,
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

    def test_nva_dspace_openaire_core_parsers_and_bot_detection(self):
        self.assertEqual(
            extract_nva_uuid("https://nva.sikt.no/registration/0198cc7bb7cc-1f4942f7-74e5-465f-9470-d142a0880c74"),
            "0198cc7bb7cc-1f4942f7-74e5-465f-9470-d142a0880c74",
        )
        self.assertEqual(extract_nva_uuid("https://api.nva.unit.no/publication/file/abc"), "")
        files, links = parse_nva_publication_artifacts({
            "associatedArtifacts": [
                {"type": "OpenFile", "mimeType": "application/pdf", "allowedOperations": ["read-metadata"], "identifier": "embargoed"},
                {
                    "type": "OpenFile",
                    "mimeType": "application/pdf",
                    "allowedOperations": ["download", "read-metadata"],
                    "identifier": "open-pdf-1",
                    "license": {"value": "https://creativecommons.org/licenses/by/4.0/"},
                },
                {"type": "AssociatedLink", "id": "https://example.org/paper.pdf"},
            ]
        })
        self.assertEqual([f["identifier"] for f in files], ["open-pdf-1"])
        self.assertEqual(files[0]["license"], "https://creativecommons.org/licenses/by/4.0/")
        self.assertEqual(links, ["https://example.org/paper.pdf"])

        presigned = "https://s3.eu-north-1.amazonaws.com/bucket/file.pdf?X-Amz-Signature=deadbeef"
        alias = "https://api.nva.unit.no/publication/file/open-pdf-1"
        cand = _normalize_candidate({"url": presigned, "public_url": alias, "license": "CC-BY"})
        self.assertFalse(safe_public_link(cand["url"]))
        self.assertTrue(safe_public_link(cand["public_url"]))

        self.assertEqual(
            extract_dspace_handle("https://aaltodoc.aalto.fi/handle/123456789/145475"),
            ("aaltodoc.aalto.fi", "123456789/145475", ""),
        )
        bit_urls = parse_dspace_bitstream_urls({
            "_embedded": {
                "bitstreams": [
                    {"name": "license.txt", "sizeBytes": 120, "_links": {"content": {"href": "https://aaltodoc.aalto.fi/server/api/core/bitstreams/1/content"}}},
                    {"name": "thesis.pdf", "sizeBytes": 500000, "_links": {"content": {"href": "https://aaltodoc.aalto.fi/server/api/core/bitstreams/2/content"}}},
                ]
            }
        }, "aaltodoc.aalto.fi")
        self.assertEqual(bit_urls, ["https://aaltodoc.aalto.fi/server/api/core/bitstreams/2/content"])

        oa_urls = parse_openaire_urls({
            "response": {
                "results": {
                    "result": {
                        "metadata": {
                            "oaf:entity": {
                                "oaf:result": {
                                    "children": {
                                        "result": [
                                            {"instance": {"accessright": {"@classid": "CLOSED"}, "url": {"$": "https://closed.example/a.pdf"}}},
                                            {"instance": {"accessright": {"@classid": "OPEN"}, "webresource": {"url": {"$": "https://aaltodoc.aalto.fi/handle/123456789/145475"}}}},
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            }
        })
        self.assertEqual(oa_urls, ["https://aaltodoc.aalto.fi/handle/123456789/145475"])

        core = parse_core_urls({
            "results": [
                {"doi": "10.9999/wrong", "downloadUrl": "https://core.ac.uk/download/1.pdf"},
                {"doi": "https://doi.org/10.21606/NORDES.2021.1", "downloadUrl": "https://core.ac.uk/download/489513693.pdf"},
            ]
        }, "10.21606/nordes.2021.1")
        self.assertEqual(core, ["https://core.ac.uk/download/489513693.pdf"])

        self.assertTrue(is_bot_challenge_html(b"<html><script src='/.within.website/x/cmd/anubis.js'></script></html>"))
        self.assertFalse(is_bot_challenge_html(b"<html><body><h1>Article</h1></body></html>"))

        oai_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
          <ListRecords>
            <record>
              <header><identifier>oai:archive.nordes.org:article/618</identifier></header>
              <metadata>
                <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
                  <dc:title>RETHINKING SCALE - RELATIONALITY, PLACE, AND CRITICAL ZONE</dc:title>
                  <dc:identifier>https://archive.nordes.org/index.php/n13/article/view/618</dc:identifier>
                  <dc:identifier>10.21606/nordes.2025.618</dc:identifier>
                  <dc:relation>https://archive.nordes.org/index.php/n13/article/view/618/585</dc:relation>
                </oai_dc:dc>
              </metadata>
            </record>
          </ListRecords>
        </OAI-PMH>"""
        by_doi, by_title, token = parse_oai_ojs_records(oai_xml)
        self.assertEqual(token, "")
        self.assertEqual(by_doi["10.21606/nordes.2025.618"][0], "https://archive.nordes.org/index.php/n13/article/download/618/585")
        self.assertIn("rethinking scale relationality place and critical zone", by_title)

        self.assertEqual(
            extract_diva_query("https://urn.kb.se/resolve?urn=urn:nbn:se:liu:diva-211651"),
            "urn:nbn:se:liu:diva-211651",
        )
        self.assertEqual(
            extract_diva_query("https://uu.diva-portal.org/smash/get/diva2:2075907/FULLTEXT01.pdf"),
            "diva2:2075907",
        )
        diva_csv = (
            "PID,NBN,FullTextLink,Urls\n"
            "999,urn:nbn:se:other:diva-1,https://example.org/other.pdf,\n"
            "1937243,urn:nbn:se:liu:diva-211651,http://liu.diva-portal.org/smash/get/diva2:1937243/FULLTEXT02.pdf,\n"
        )
        self.assertEqual(
            parse_diva_export_csv(diva_csv, "urn:nbn:se:liu:diva-211651"),
            ["https://liu.diva-portal.org/smash/get/diva2:1937243/FULLTEXT02.pdf"],
        )

        inner_pdf = b"%PDF-1.7\n" + (b"0" * 600) + b"\n%%EOF\n"
        wrapped = b"----abc\r\nContent-Disposition: form-data\r\n\r\n" + inner_pdf + b"\r\n----abc--\r\n"
        self.assertFalse(pdf_data(wrapped))
        unwrapped = unwrap_pdf_payload(wrapped)
        self.assertTrue(pdf_data(unwrapped))
        self.assertTrue(unwrapped.startswith(b"%PDF-1.7"))

        pmc_urls = expand_registered_oa_urls("https://pmc.ncbi.nlm.nih.gov/articles/12290142")
        self.assertIn("https://pmc.ncbi.nlm.nih.gov/articles/PMC12290142/pdf/", pmc_urls)
        self.assertIn("https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC12290142&blobtype=pdf", pmc_urls)


if __name__ == "__main__":
    unittest.main()

