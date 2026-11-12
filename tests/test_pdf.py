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
    cache_path,
    cached_pdf_ok,
    candidate_https_url,
    extract_diva_query,
    extract_dspace_handle,
    extract_nva_uuid,
    extract_openalex_work_urls,
    expand_registered_oa_urls,
    has_explicit_open_license,
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
    sync_repo_pdf_folder,
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
        self.assertTrue(is_bot_challenge_html(b"<html><head><title>Preparing to download ...</title></head></html>"))
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

    def test_sync_repo_pdf_license_and_size_gates(self):
        self.assertTrue(has_explicit_open_license("CC BY 4.0"))
        self.assertTrue(has_explicit_open_license("cc-by"))
        self.assertTrue(has_explicit_open_license("CC BY-NC-ND 4.0"))
        self.assertTrue(has_explicit_open_license("cc0"))
        self.assertTrue(has_explicit_open_license("public-domain"))
        self.assertFalse(has_explicit_open_license(""))
        self.assertFalse(has_explicit_open_license("other-oa"))
        self.assertFalse(has_explicit_open_license("implied-oa"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            docs = root / "docs"
            pdf_dir = root / "pdf"
            (cache / "pdf").mkdir(parents=True)
            docs.mkdir(parents=True)
            pdf_dir.mkdir(parents=True)

            good_bytes = b"%PDF-1.7\n" + (b"A" * 1000) + b"\n%%EOF\n"
            unlic_bytes = b"%PDF-1.7\n" + (b"B" * 1000) + b"\n%%EOF\n"
            big_bytes = b"%PDF-1.7\n" + (b"C" * 3000) + b"\n%%EOF\n"

            def _put(wid: str, blob: bytes, lic: str = "") -> dict:
                sha = hashlib.sha256(blob).hexdigest()
                cache_path(wid, cache).write_bytes(blob)
                return {
                    "status": "pdf-confirmed",
                    "sha256": sha,
                    "bytes": len(blob),
                    "url": f"https://example.org/{wid}.pdf",
                    "license": lic,
                }

            progress = {
                "W1": _put("W1", good_bytes, "CC BY 4.0"),
                "W2": _put("W2", unlic_bytes, ""),
                "W3": _put("W3", big_bytes, "CC BY 4.0"),
                "W4": _put("W4", unlic_bytes, "other-oa"),
            }
            import json
            (cache / "progress.json").write_text(json.dumps(progress), encoding="utf-8")
            (docs / "source_links.json").write_text("{}", encoding="utf-8")
            # Pre-seed an unlicensed file in `pdf/` + `manifest.json` to ensure it gets pruned
            (pdf_dir / "W2.pdf").write_bytes(unlic_bytes)
            (pdf_dir / "manifest.json").write_text(json.dumps({
                "items": {
                    "W2": {
                        "file": "pdf/W2.pdf",
                        "sha256": progress["W2"]["sha256"],
                        "bytes": len(unlic_bytes),
                        "source_url": "https://example.org/W2.pdf",
                        "license": "",
                    }
                }
            }), encoding="utf-8")

            rows = [
                {"id": wid, "priority": "high", "license": lic}
                for wid, lic in [("W1", "CC BY 4.0"), ("W2", ""), ("W3", "CC BY 4.0"), ("W4", "other-oa")]
            ]
            with patch("designteori.pdf.queue_rows", return_value=rows), \
                 patch("designteori.pdf.DOCS_DATA_DIR", docs):
                res = sync_repo_pdf_folder(cache, pdf_dir, max_file_mb=0.002)

            self.assertEqual(res["repo_pdf_count"], 1)
            self.assertTrue((pdf_dir / "W1.pdf").is_file())
            self.assertFalse((pdf_dir / "W2.pdf").exists())
            self.assertFalse((pdf_dir / "W3.pdf").exists())
            self.assertFalse((pdf_dir / "W4.pdf").exists())
            man = json.loads((pdf_dir / "manifest.json").read_text(encoding="utf-8"))["items"]
            self.assertEqual(list(man.keys()), ["W1"])
            self.assertEqual(man["W1"]["license"], "CC BY 4.0")

    def test_non_oa_repo_fallback_paywall_toc_and_hal_dtu_expansion(self):
        self.assertEqual(
            expand_registered_oa_urls("https://hal.science/hal-03981270"),
            ["https://hal.science/hal-03981270/document", "https://hal.science/hal-03981270"],
        )
        self.assertEqual(
            expand_registered_oa_urls("https://shs.hal.science/halshs-0123456"),
            ["https://shs.hal.science/halshs-0123456/document", "https://shs.hal.science/halshs-0123456"],
        )
        self.assertEqual(
            expand_registered_oa_urls("https://hal.science/hal-03981270/file/paper.pdf"),
            ["https://hal.science/hal-03981270/file/paper.pdf"],
        )
        self.assertEqual(
            expand_registered_oa_urls("https://orbit.dtu.dk/files/160367810/Paper.pdf"),
            [
                "https://backend.orbit.dtu.dk/ws/files/160367810/Paper.pdf",
                "https://orbit.dtu.dk/files/160367810/Paper.pdf",
            ],
        )
        self.assertEqual(
            expand_registered_oa_urls("https://www.ep.liu.se/ecp/059/010/ecp09059010.pdf"),
            [
                "https://ep.liu.se/ecp/059/010/ecp09059010.pdf",
                "https://www.ep.liu.se/ecp/059/010/ecp09059010.pdf",
            ],
        )

        urls = extract_openalex_work_urls({
            "open_access": {"is_oa": True, "oa_url": "https://oa.example.org/fallback"},
            "best_oa_location": {
                "is_oa": True,
                "pdf_url": "https://repo.example.org/oa.pdf",
                "source": {"type": "repository"},
            },
            "locations": [
                {"is_oa": False, "pdf_url": "https://journals.sagepub.com/doi/pdf/10.1177/123", "landing_page_url": "https://www.sciencedirect.com/science/article/pii/123"},
                {"is_oa": False, "pdf_url": "https://www.gbv.de/dms/tib-ub-hannover/999_toc.pdf"},
                {"is_oa": False, "landing_page_url": "https://adk.elsevierpure.com/ws/files/59247138/Design.pdf"},
                {"is_oa": False, "landing_page_url": "https://orbit.dtu.dk/files/160367810/Thesis.pdf"},
                {"is_oa": False, "landing_page_url": "https://www.ep.liu.se/ecp/059/010/ecp09059010.pdf"},
                {"is_oa": False, "landing_page_url": "https://vbn.aau.dk/da/publications/a6cddb66-e5f7-4891-a7a8-ba23c8f5d202"},
                {"is_oa": False, "landing_page_url": "https://research.ulapland.fi/en/publications/some-design-study"},
                {"is_oa": False, "landing_page_url": "https://hdl.handle.net/10044/1/99999"},
                {"is_oa": False, "landing_page_url": "https://hdl.handle.net/2117/123456"},
                {"is_oa": False, "landing_page_url": "https://pure.au.dk/portal/en/publications/metadata-only-uuid"},
                {"is_oa": False, "landing_page_url": "https://radar.gsa.ac.uk/id/eprint/6543"},
                {"is_oa": False, "landing_page_url": "https://publisher.example.org/abstract-only-page"},
            ],
        })
        self.assertEqual(urls[0], "https://repo.example.org/oa.pdf")
        self.assertEqual(urls[1], "https://oa.example.org/fallback")
        self.assertIn("https://adk.elsevierpure.com/ws/files/59247138/Design.pdf", urls)
        self.assertIn("https://backend.orbit.dtu.dk/ws/files/160367810/Thesis.pdf", urls)
        self.assertIn("https://ep.liu.se/ecp/059/010/ecp09059010.pdf", urls)
        self.assertIn("https://vbn.aau.dk/da/publications/a6cddb66-e5f7-4891-a7a8-ba23c8f5d202", urls)
        self.assertIn("https://research.ulapland.fi/en/publications/some-design-study", urls)
        self.assertIn("https://hdl.handle.net/10044/1/99999", urls)
        self.assertIn("https://hdl.handle.net/2117/123456", urls)
        self.assertIn("https://radar.gsa.ac.uk/id/eprint/6543", urls)
        self.assertLess(
            urls.index("https://adk.elsevierpure.com/ws/files/59247138/Design.pdf"),
            urls.index("https://radar.gsa.ac.uk/id/eprint/6543"),
        )
        self.assertLess(
            urls.index("https://backend.orbit.dtu.dk/ws/files/160367810/Thesis.pdf"),
            urls.index("https://orbit.dtu.dk/files/160367810/Thesis.pdf"),
        )
        self.assertLess(
            urls.index("https://ep.liu.se/ecp/059/010/ecp09059010.pdf"),
            urls.index("https://www.ep.liu.se/ecp/059/010/ecp09059010.pdf"),
        )
        for blocked in (
            "https://journals.sagepub.com/doi/pdf/10.1177/123",
            "https://www.sciencedirect.com/science/article/pii/123",
            "https://www.gbv.de/dms/tib-ub-hannover/999_toc.pdf",
            "https://pure.au.dk/portal/en/publications/metadata-only-uuid",
            "https://publisher.example.org/abstract-only-page",
        ):
            self.assertNotIn(blocked, urls)

        urls2 = extract_openalex_work_urls({
            "locations": [
                {"is_oa": False, "landing_page_url": "https://aaltodoc.aalto.fi/handle/123456789/119186"},
                {"is_oa": False, "landing_page_url": "https://trepo.tuni.fi/handle/10024/219467"},
                {"is_oa": False, "landing_page_url": "https://osuva.uwasa.fi/handle/10024/17899"},
                {"is_oa": False, "landing_page_url": "https://cris.maastrichtuniversity.nl/en/publications/study"},
                {"is_oa": False, "pdf_url": "https://www.maastrichtuniversity.nl/sites/default/files/general_privacy_statement_um.pdf"},
                {"is_oa": False, "pdf_url": "https://www.strath.ac.uk/media/ps/strategyandpolicy/DP_Policy.pdf"},
            ],
        })
        self.assertEqual(urls2, [
            "https://aaltodoc.aalto.fi/handle/123456789/119186",
            "https://trepo.tuni.fi/handle/10024/219467",
            "https://osuva.uwasa.fi/handle/10024/17899",
            "https://cris.maastrichtuniversity.nl/en/publications/study",
        ])


if __name__ == "__main__":
    unittest.main()

