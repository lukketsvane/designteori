"""Unit tests for teorielement input preparation and Windows filename sanitization."""
import json
import sqlite3
from pathlib import Path

import pytest

from teorielement.prep import (
    CONCL_RE,
    REFS_RE,
    build_end,
    clip,
    render,
    safe_filename,
)


def test_safe_filename_alphanumeric():
    assert safe_filename("W1012987640") == "W1012987640"
    assert safe_filename("simple_id_123") == "simple_id_123"


def test_safe_filename_colons():
    ident = "nordic:diva:00094b8101b6c8b7abf0"
    expected = "nordic_diva_00094b8101b6c8b7abf0"
    assert safe_filename(ident) == expected


def test_safe_filename_all_win32_reserved_chars():
    # Win32 reserved characters: < > : " / \ | ? *
    ident = 'bad<name>:with"slash/backslash\\pipe|question?star*'
    sanitized = safe_filename(ident)
    assert "<" not in sanitized
    assert ">" not in sanitized
    assert ":" not in sanitized
    assert '"' not in sanitized
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert "|" not in sanitized
    assert "?" not in sanitized
    assert "*" not in sanitized
    assert sanitized == "bad_name__with_slash_backslash_pipe_question_star_"


def test_safe_filename_collision_freedom_catalog():
    catalog_path = Path(__file__).resolve().parent.parent / "docs/data/pdf_katalog.json"
    if not catalog_path.exists():
        pytest.skip("pdf_katalog.json not found")
    data = json.loads(catalog_path.read_text(encoding="utf8"))
    items = data.get("items", [])
    assert len(items) > 0

    all_ids = [item["id"] for item in items if "id" in item]
    sanitized_ids = [safe_filename(i) for i in all_ids]

    assert len(all_ids) == len(set(all_ids)), "Catalog has duplicate raw IDs"
    assert len(sanitized_ids) == len(set(sanitized_ids)), "Sanitization introduced collisions!"
    assert all(":" not in s for s in sanitized_ids), "Colon found in sanitized filenames"


def test_clip():
    pages = [(1, "A" * 5000), (2, "B" * 5000), (3, "C" * 5000)]
    clipped = clip(pages, 12000)
    assert len(clipped) == 3
    assert clipped[0] == (1, "A" * 5000)
    assert clipped[1] == (2, "B" * 5000)
    assert clipped[2] == (3, "C" * 2000)
    assert sum(len(text) for _, text in clipped) == 12000


def test_clip_empty():
    assert clip([], 1000) == []


def test_render():
    parts = [(1, "First page text"), (2, "Second page text")]
    rendered = render(parts)
    assert "===== SIDE 1 =====" in rendered
    assert "First page text" in rendered
    assert "===== SIDE 2 =====" in rendered
    assert "Second page text" in rendered


def test_concl_and_refs_regex():
    assert CONCL_RE.search("Conclusions")
    assert CONCL_RE.search("10. Discussion and conclusions")
    assert CONCL_RE.search("Konklusjon")
    assert CONCL_RE.search("Sammanfattning")

    assert REFS_RE.search("References")
    assert REFS_RE.search("Referanser")
    assert REFS_RE.search("Litteraturliste")


def test_build_end_with_conclusions():
    pages = [
        (1, "Intro"),
        (2, "Methods"),
        (3, "Results"),
        (4, "Conclusion\nIn summary, the design theory holds."),
        (5, "References\n[1] Smith et al."),
    ]
    end_parts = build_end(pages, front_last=1)
    assert len(end_parts) >= 1
    page_num, text = end_parts[0]
    assert page_num == 4
    assert "Conclusion" in text
    assert "References" not in text


def test_build_end_fallback_refs():
    pages = [
        (1, "Intro"),
        (2, "Body text 1"),
        (3, "Body text 2"),
        (4, "Body text 3"),
        (5, "References\n[1] Smith et al."),
    ]
    end_parts = build_end(pages, front_last=1)
    assert len(end_parts) >= 1
    # Check that references were excluded from the end text
    for _, text in end_parts:
        assert "[1] Smith et al." not in text


def test_prep_synthetic_workflow(tmp_path, monkeypatch):
    """Test full execution of prep logic against a mock sqlite database and catalog."""
    import teorielement.prep as prep_module

    db_path = tmp_path / "mock_corpus.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE documents (sha256 TEXT PRIMARY KEY, file_path TEXT, bytes INT, pages INT, extracted_pages INT, char_count INT, extractor TEXT, chunk_version TEXT, quality TEXT, processed_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE pages (sha256 TEXT, page INT, text TEXT, PRIMARY KEY(sha256, page))"
    )

    # Insert one extracted doc and one needs_ocr doc
    sha_ok = "aabbcc112233"
    sha_ocr = "ddeeff445566"
    conn.execute(
        "INSERT INTO documents VALUES (?, 'path1', 1000, 2, 2, 100, 'pdf', 'v1', 'extracted', '2026-11-12')",
        (sha_ok,),
    )
    conn.execute(
        "INSERT INTO documents VALUES (?, 'path2', 1000, 2, 0, 0, 'pdf', 'v1', 'needs_ocr', '2026-11-12')",
        (sha_ocr,),
    )
    conn.execute("INSERT INTO pages VALUES (?, 1, 'Intro text on page 1')", (sha_ok,))
    conn.execute("INSERT INTO pages VALUES (?, 2, 'Conclusion text on page 2')", (sha_ok,))
    conn.commit()
    conn.close()

    mock_catalog = {
        "items": [
            {
                "id": "nordic:diva:test1234",
                "document_sha256": sha_ok,
                "title": "A Test Paper",
                "year": 2024,
                "doi": "10.1234/test",
                "license": "cc-by",
            },
            {
                "id": "nordic:nva:test5678",
                "document_sha256": sha_ocr,
                "title": "An OCR Paper",
                "year": 2023,
                "doi": "",
                "license": "",
            },
        ]
    }
    mock_cat_file = tmp_path / "pdf_katalog.json"
    mock_cat_file.write_text(json.dumps(mock_catalog), encoding="utf8")

    work_dir = tmp_path / "teorielement"
    monkeypatch.setattr(prep_module, "ROOT", tmp_path)
    monkeypatch.setattr(prep_module, "PRIVATE_CORPUS_DB", db_path)
    monkeypatch.setattr(prep_module, "WORK", work_dir)

    # Create dummy catalog at ROOT / "docs/data/pdf_katalog.json"
    docs_data = tmp_path / "docs" / "data"
    docs_data.mkdir(parents=True, exist_ok=True)
    (docs_data / "pdf_katalog.json").write_text(json.dumps(mock_catalog), encoding="utf8")

    # Run main()
    monkeypatch.setattr("sys.argv", ["prep.py"])
    prep_module.main()

    # Check generated files
    expected_fname = "nordic_diva_test1234.txt"
    input_file = work_dir / "input" / expected_fname
    assert input_file.exists(), f"Expected {expected_fname} to be created"
    content = input_file.read_text(encoding="utf8")
    assert "ID: nordic:diva:test1234" in content
    assert "Intro text on page 1" in content

    # Check index.json
    index_file = work_dir / "index.json"
    assert index_file.exists()
    index_data = json.loads(index_file.read_text(encoding="utf8"))
    assert len(index_data) == 1
    safe_key = "nordic_diva_test1234"
    entry = index_data[safe_key] if isinstance(index_data, dict) else index_data[0]
    assert entry["id"] == "nordic:diva:test1234"
    assert entry["file"] == expected_fname
    assert entry["sha256"] == sha_ok

    # Check skipped.json
    skipped_file = work_dir / "skipped.json"
    assert skipped_file.exists()
    skipped_data = json.loads(skipped_file.read_text(encoding="utf8"))
    assert len(skipped_data) == 1
    assert skipped_data[0]["id"] == "nordic:nva:test5678"
    assert skipped_data[0]["reason"] == "needs_ocr"
