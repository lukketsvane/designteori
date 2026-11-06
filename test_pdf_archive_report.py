"""Test the private PDF inventory against actual hashed disk contents, offline."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pdf_archive_report as report


class PrivateArchiveReportTests(unittest.TestCase):
    def test_real_files_not_links_or_progress_markers(self):
        raw = b"%PDF-1.7\n" + b" " * 700 + b"%%EOF"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            private = Path(temp) / "private"
            (root / "docs/data").mkdir(parents=True)
            (private / "pdf").mkdir(parents=True)
            (root / "docs/data/publications.json").write_text(json.dumps([
                {"id": "W123", "title": "Verified Design Methods", "year": 2020,
                 "doi": "https://doi.org/10.1234/foo", "authors": ["First Researcher"],
                 "kind": "article"}
            ]), encoding="utf-8")
            (root / "docs/data/nordic_additions.json").write_text("[]", encoding="utf-8")
            progress = {
                "W123": {"status": "pdf-confirmed", "bytes": len(raw),
                         "sha256": hashlib.sha256(raw).hexdigest(),
                         "url": "https://example.org/123.pdf"},
                "W999": {"status": "pdf-confirmed", "bytes": len(raw),
                         "sha256": hashlib.sha256(raw).hexdigest(),
                         "url": "https://example.org/missing.pdf"},
                "W888": {"status": "failed", "reason": "HTTP 404"},
            }
            with patch.multiple(report.harvest, ROOT=root, PRIVATE=private):
                path = report.harvest.cache_path("W123")
                path.write_bytes(raw)
                verified, missing, failed, duplicates = report.audit(progress)
                self.assertEqual(len(verified), 1)
                self.assertEqual(verified[0]["title"], "Verified Design Methods")
                self.assertEqual(verified[0]["authors"], "First Researcher")
                self.assertEqual(missing, ["W999"])
                self.assertEqual(failed[0]["id"], "W888")
                self.assertEqual(duplicates, {})
                summary = report.write_report(verified, missing, failed, duplicates)
                self.assertEqual(summary["verified_pdfs_on_disk"], 1)
                self.assertEqual(summary["cache_entries_missing_or_corrupt"], 1)
                self.assertEqual(summary["actual_disk_bytes"], len(raw))
                self.assertIn("Verified Design Methods",
                              (private / "pdf_local_index.csv").read_text())
                self.assertNotIn("W999", (private / "pdf_local_index.csv").read_text())


if __name__ == "__main__":
    unittest.main()
