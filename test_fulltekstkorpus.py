"""Offline tests for private PDF extraction, page chunks, idempotence and FTS."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bygg_fulltekstkorpus as corpus


class FullTextCorpusTests(unittest.TestCase):
    def test_chunk_overlap_and_page_boundaries(self):
        text = " ".join(["design methods in practice."] * 400)
        parts = corpus.chunks_for_page(text, target=900, overlap=150)
        self.assertGreater(len(parts), 3)
        for start, end, chunk in parts:
            self.assertEqual(chunk, corpus.normalized(text)[start:end].strip())
            self.assertLessEqual(len(chunk), 900)
        self.assertEqual(corpus.chunks_for_page("small"), [])

    def test_incremental_index_force_reprocess_and_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.7\n" + b"a" * 600 + b"\n%%EOF")
            digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
            conn = corpus.connection(root / "corpus.sqlite")
            info = {"title": "Paper", "doi": "https://doi.org/10.1234/test",
                    "authors": ["Researcher"], "year": 2020}
            with patch.object(corpus, "extract_pages", return_value=(
                    ["Design researchers collected interviews. " * 20,
                     "Methods and consequences in Nordic design. " * 20],
                    "mock-parser")) as parse:
                self.assertEqual(corpus.index_document(
                    conn, "W1", pdf, digest, "https://example.org/paper.pdf",
                    info, "CC BY 4.0")[1], True)
                self.assertEqual(corpus.index_document(
                    conn, "W1", pdf, digest, "", info, "CC BY 4.0")[1], False)
                self.assertEqual(parse.call_count, 1)
                first = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
                self.assertGreaterEqual(first, 2)
                self.assertGreater(conn.execute(
                    "SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?",
                    ("design",)).fetchone()[0], 0)
                self.assertEqual(corpus.index_document(
                    conn, "W1", pdf, digest, "", info, "CC BY 4.0",
                    force=True)[1], True)
                self.assertEqual(parse.call_count, 2)
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM documents").fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM work_documents").fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM chunks").fetchone()[0], first)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            conn.close()

    def test_empty_page_is_flagged_for_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "scanned.pdf"
            file.write_bytes(b"%PDF-1.7\n" + b"x" * 750 + b"\n%%EOF")
            with patch.object(corpus, "extract_pages",return_value=(
                    ["", "", "Some very short header"], "mock-parser")):
                db=corpus.connection(Path(tmp) / "idx.sqlite")
                corpus.index_document(db,"W2",file,"","",{"title":"Scan"},"")
                self.assertEqual(db.execute(
                    "SELECT quality FROM documents").fetchone()[0],"needs_ocr")
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM chunks").fetchone()[0],0)
                db.close()


if __name__=="__main__":
    unittest.main()
