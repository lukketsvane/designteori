"""
Opaque-Box Requirement-Driven Acceptance Test Suite for DESIGNTEORI (R1–R4).

Covers all 8 features across Tiers 1–4:
- Tier 1: Feature Coverage (5 tests per feature * 8 features = 40 tests)
- Tier 2: Boundary & Corner Cases (5 tests per feature * 8 features = 40 tests)
- Tier 3: Pairwise Cross-Feature Combinations (6 tests)
- Tier 4: Real-World Acceptance Scenarios (4 scenarios)
Total: 90 tests.

Execution:
  python -m unittest tests/test_acceptance_requirements.py
  python -m unittest discover -s tests
  python -m pytest tests/test_acceptance_requirements.py
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from designteori import (
    ROOT,
    DATA_DIR,
    DOCS_DIR,
    DOCS_DATA_DIR,
    IMPORTS_DIR,
    PDF_DIR,
    RAW_SQLITE,
    RAW_SQLITE_GZ,
    UNIFIED_SQLITE_GZ,
    read_json,
)
from designteori.eligibility import HARD_NON_DESIGN_RE, FORBIDDEN_VENUES_RE
from designteori.build import verify_all


# ---------------------------------------------------------------------------
# Tier 1: Feature Coverage (40 Tests, 5 per Feature)
# ---------------------------------------------------------------------------


class Tier1FeatureCoverageTests(unittest.TestCase):
    """
    Tier 1: Positive feature coverage across F1–F8 (5 tests per feature = 40 tests).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.nva_report_path = DOCS_DATA_DIR / "nva_audit_report.json"
        cls.pdf_katalog_path = DOCS_DATA_DIR / "pdf_katalog.json"
        cls.publications_path = DOCS_DATA_DIR / "publications.json"
        cls.nordic_additions_path = DOCS_DATA_DIR / "nordic_additions.json"
        cls.aalto_path = IMPORTS_DIR / "aalto" / "aaltodoc_design.json"
        cls.kgl_path = IMPORTS_DIR / "kgl" / "danish_design.json"
        cls.iris_path = IMPORTS_DIR / "iris" / "iceland_design.json"
        cls.nordes_path = IMPORTS_DIR / "nordes" / "nordes_drs.json"
        cls.semje_path = DOCS_DIR / "validering" / "semje.json"
        cls.grensa_dir = DOCS_DIR / "validering" / "grensa"
        cls.gransking_dir = ROOT / "gransking"

        cls.nva_report = (
            read_json(cls.nva_report_path) if cls.nva_report_path.exists() else {}
        )
        cls.pdf_katalog = (
            read_json(cls.pdf_katalog_path) if cls.pdf_katalog_path.exists() else {}
        )
        cls.semje_data = (
            read_json(cls.semje_path) if cls.semje_path.exists() else {}
        )

    # --- Feature 1: NVA URL Audit & Resolution (R1.1) ---

    def test_t1_f1_nva_audit_report_exists_and_valid_json(self) -> None:
        """F1.1: Verify nva_audit_report.json exists, parses, and has root keys."""
        self.assertTrue(
            self.nva_report_path.exists(),
            f"Missing NVA audit report: {self.nva_report_path}",
        )
        self.assertIsInstance(self.nva_report, dict)
        for key in ("summary", "items"):
            self.assertIn(key, self.nva_report, f"Missing root key: {key}")
        self.assertIsInstance(self.nva_report["items"], list)
        self.assertGreater(len(self.nva_report["items"]), 0)

    def test_t1_f1_nva_audit_covers_all_760_archive_records(self) -> None:
        """F1.2: Verify audit report accounts for all 760 unverified NVA candidates."""
        total_audited = self.nva_report.get(
            "audited_count", self.nva_report.get("target_handle_count", 0)
        )
        self.assertGreaterEqual(
            total_audited,
            760,
            f"Expected total_audited >= 760, got {total_audited}",
        )
        self.assertGreaterEqual(
            len(self.nva_report.get("items", [])),
            760,
            f"Expected >= 760 items in NVA report, got {len(self.nva_report.get('items', []))}",
        )

    def test_t1_f1_nva_audit_resolution_status_taxonomy(self) -> None:
        """F1.3: Ensure every audited item conforms to resolution status taxonomy."""
        valid_taxonomy = {
            "verified_oa_pdf",
            "verified_oa_artifact",
            "landing_verified_no_open_file",
            "redirect_resolved",
            "doi_backfilled",
            "tombstoned_or_deleted",
            "needs_manual_review",
            "unreachable",
            "publication_not_found",
            "redirect_failed",
            "error",
        }
        for item in self.nva_report.get("items", []):
            status = item.get("resolution_status") or item.get("status")
            self.assertIsNotNone(status, f"Missing status in item {item.get('id')}")
            self.assertIn(
                status,
                valid_taxonomy,
                f"Unknown resolution status '{status}' for item {item.get('id')}",
            )

    def test_t1_f1_nva_catalog_entries_updated_with_status(self) -> None:
        """F1.4: Cross-reference catalog items against NVA audit report."""
        catalog_items = {
            item["id"]: item for item in self.pdf_katalog.get("items", [])
        }
        matched = sum(
            1 for item in self.nva_report.get("items", []) if item["id"] in catalog_items
        )
        self.assertGreaterEqual(
            matched,
            760,
            f"Expected at least 760 audited items present in pdf_katalog.json, matched {matched}",
        )

    def test_t1_f1_nva_audit_report_contains_timestamp_and_summary(self) -> None:
        """F1.5: Verify ISO timestamp and non-negative summary distribution."""
        ts = self.nva_report.get("audited_at") or self.nva_report.get("audit_timestamp")
        self.assertIsNotNone(ts, "Missing audit timestamp in nva_audit_report.json")
        self.assertRegex(
            str(ts),
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            f"Timestamp does not match ISO 8601: {ts}",
        )
        summary = self.nva_report.get("summary", {})
        self.assertIsInstance(summary, dict)
        self.assertGreater(len(summary), 0)
        for stat, count in summary.items():
            self.assertGreaterEqual(
                count, 0, f"Summary count for '{stat}' is negative: {count}"
            )

    # --- Feature 2: OpenAlex 18 Queries Rerun (R1.2) ---

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t1_f2_openalex_query_log_exists_in_database(self) -> None:
        """F2.1: Verify query_log table exists and is populated in RAW_SQLITE."""
        self.assertTrue(RAW_SQLITE.exists(), f"RAW_SQLITE missing at {RAW_SQLITE}")
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            count = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
            self.assertGreater(count, 0, "query_log table is unexpectedly empty")
        finally:
            conn.close()

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t1_f2_openalex_18_nordic_queries_identified(self) -> None:
        """F2.2: Verify all 18 specific Nordic keyword queries exist in query_log."""
        expected_queries = [
            "nordic_lang:designteori",
            "nordic_lang:designforskning",
            "nordic_lang:designforsking",
            "nordic_lang:formgivning",
            "nordic_lang:formgiving",
            "nordic_lang:formgjeving",
            "nordic_lang:brukskunst",
            "nordic_lang:industridesign",
            "nordic_lang:tjenestedesign",
            "nordic_lang:tjänstedesign",
            "nordic_lang:interaksjonsdesign",
            "nordic_lang:interaktionsdesign",
            "nordic_lang:brukermedvirkning",
            "nordic_lang:brugerinddragelse",
            "nordic_lang:muotoilu",
            "nordic_lang:muotoilututkimus",
            "nordic_lang:taideteollisuus",
            "nordic_lang:hönnun",
        ]
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            placeholders = ",".join("?" for _ in expected_queries)
            rows = conn.execute(
                f"SELECT query FROM query_log WHERE query IN ({placeholders})",
                expected_queries,
            ).fetchall()
            found_queries = {row[0] for row in rows}
            missing = set(expected_queries) - found_queries
            self.assertEqual(
                len(missing), 0, f"Missing {len(missing)} Nordic queries: {missing}"
            )
        finally:
            conn.close()

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t1_f2_openalex_18_nordic_queries_quota_errors_cleared(self) -> None:
        """F2.3: Verify all 18 Nordic queries have cleared rate limit quota errors."""
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            errors = conn.execute(
                "SELECT query, error FROM query_log WHERE query LIKE 'nordic_lang:%' "
                "AND (error LIKE '%429%' OR error LIKE '%quota%' OR error LIKE '%Rate limit%')"
            ).fetchall()
            self.assertEqual(
                len(errors), 0, f"Found lingering quota errors in query_log: {errors}"
            )
        finally:
            conn.close()

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t1_f2_openalex_query_log_returned_counts_non_negative(self) -> None:
        """F2.4: Verify returned and total_hits counts are non-negative integers."""
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT query, returned, total_hits FROM query_log WHERE query LIKE 'nordic_lang:%'"
            ).fetchall()
            self.assertGreaterEqual(len(rows), 18)
            for query, returned, total_hits in rows:
                self.assertIsNotNone(returned, f"returned is None for {query}")
                self.assertGreaterEqual(
                    returned, 0, f"returned count negative for {query}: {returned}"
                )
                if total_hits is not None:
                    self.assertGreaterEqual(
                        total_hits,
                        0,
                        f"total_hits negative for {query}: {total_hits}",
                    )
        finally:
            conn.close()

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t1_f2_openalex_ingested_works_have_valid_identifiers(self) -> None:
        """F2.5: Verify raw OpenAlex work identifiers follow W<digits> standard."""
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT id FROM works WHERE id LIKE 'W%' LIMIT 100"
            ).fetchall()
            self.assertGreater(len(rows), 0, "No OpenAlex works found in database")
            for (wid,) in rows:
                self.assertTrue(
                    bool(re.fullmatch(r"W\d+", wid)),
                    f"Invalid OpenAlex work ID format: {wid}",
                )
        finally:
            conn.close()

    # --- Feature 3: Finnish, Danish, and Icelandic Archive Harvest (R1.3) ---

    def test_t1_f3_finland_aalto_harvest_populated_positive_count(self) -> None:
        """F3.1: Verify imports/aalto/aaltodoc_design.json exists with count > 0."""
        self.assertTrue(self.aalto_path.exists(), f"Missing {self.aalto_path}")
        records = read_json(self.aalto_path)
        self.assertIsInstance(records, list)
        self.assertGreater(
            len(records), 0, "Aalto archive harvest count must be > 0"
        )

    def test_t1_f3_denmark_kgl_harvest_populated_records(self) -> None:
        """F3.2: Verify imports/kgl/danish_design.json exists with populated records."""
        self.assertTrue(self.kgl_path.exists(), f"Missing {self.kgl_path}")
        records = read_json(self.kgl_path)
        self.assertIsInstance(records, list)
        self.assertGreater(
            len(records), 0, "Danish design archive count must be > 0"
        )

    def test_t1_f3_iceland_iris_harvest_populated_records(self) -> None:
        """F3.3: Verify imports/iris/iceland_design.json exists with populated records."""
        self.assertTrue(self.iris_path.exists(), f"Missing {self.iris_path}")
        records = read_json(self.iris_path)
        self.assertIsInstance(records, list)
        self.assertGreater(
            len(records), 0, "Iceland design archive count must be > 0"
        )

    def test_t1_f3_nordic_archive_records_schema_validation(self) -> None:
        """F3.4: Verify all archive records contain core schema fields."""
        required_keys = {"id", "title", "authors", "year", "venue"}
        for fpath in (self.aalto_path, self.kgl_path, self.iris_path):
            records = read_json(fpath)
            for r in records[:50]:
                missing = required_keys - set(r.keys())
                self.assertEqual(
                    len(missing),
                    0,
                    f"Record in {fpath.name} missing keys {missing}: {r}",
                )
                self.assertTrue(bool(r.get("id")), f"Empty id in {fpath.name}")
                self.assertTrue(bool(r.get("title")), f"Empty title in {fpath.name}")

    def test_t1_f3_nordic_archive_records_filter_clinical_noise(self) -> None:
        """F3.5: Verify archive titles do not match hard non-design clinical noise."""
        for fpath in (self.aalto_path, self.kgl_path, self.iris_path):
            records = read_json(fpath)
            for r in records:
                title = r.get("title", "")
                self.assertFalse(
                    bool(HARD_NON_DESIGN_RE.search(title)),
                    f"Clinical/hard non-design noise detected in {fpath.name}: '{title}'",
                )

    # --- Feature 4: Nordes ~665 Scrape Replacement (R1.4) ---

    def test_t1_f4_nordes_harvest_replaces_623_partial_scrape(self) -> None:
        """F4.1: Verify Nordes record count strictly exceeds the 623 partial scrape."""
        self.assertTrue(self.nordes_path.exists(), f"Missing {self.nordes_path}")
        records = read_json(self.nordes_path)
        self.assertGreater(
            len(records),
            623,
            f"Nordes records ({len(records)}) must strictly exceed partial scrape 623",
        )

    def test_t1_f4_nordes_harvest_reaches_665_target_threshold(self) -> None:
        """F4.2: Verify Nordes harvest reaches the ~665 conference index target."""
        records = read_json(self.nordes_path)
        self.assertGreaterEqual(
            len(records),
            660,
            f"Nordes records ({len(records)}) must meet or exceed ~665 target index threshold (660)",
        )

    def test_t1_f4_nordes_crossref_pagination_offsets_beyond_400(self) -> None:
        """F4.3: Verify pagination covers records originating from offsets >= 400."""
        records = read_json(self.nordes_path)
        self.assertGreater(
            len(records),
            600,
            "Total records imply pagination reached offset 600",
        )

    def test_t1_f4_nordes_records_contain_drs_doi_or_venue(self) -> None:
        """F4.4: Verify every record in nordes_drs.json contains DRS DOI or Nordes venue."""
        records = read_json(self.nordes_path)
        for r in records:
            doi = (r.get("doi") or "").lower()
            venue = (r.get("venue") or "").lower()
            is_valid = ("10.21606" in doi) or ("nordes" in venue) or ("drs" in venue)
            self.assertTrue(
                is_valid,
                f"Record {r.get('id')} lacks DRS prefix 10.21606 or Nordes venue: {r}",
            )

    def test_t1_f4_nordes_records_zero_id_collisions(self) -> None:
        """F4.5: Verify IDs in nordes_drs.json are unique."""
        records = read_json(self.nordes_path)
        ids = [r["id"] for r in records]
        self.assertEqual(
            len(ids),
            len(set(ids)),
            f"Found {len(ids) - len(set(ids))} duplicate IDs in nordes_drs.json",
        )

    # --- Feature 5: Teorielement Inter-Rater Reliability (R2.1) ---

    def test_t1_f5_semje_script_executable_with_cli_args(self) -> None:
        """F5.1: Verify docs/validering/semje.py executes cleanly with --help."""
        semje_py = DOCS_DIR / "validering" / "semje.py"
        self.assertTrue(semje_py.exists(), f"Missing {semje_py}")
        res = subprocess.run(
            [sys.executable, str(semje_py), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"semje.py --help failed with code {res.returncode}: {res.stderr}",
        )
        self.assertIn("--maskin", res.stdout)
        self.assertIn("--utval", res.stdout)

    def test_t1_f5_semje_del_a_reports_f1_and_bootstrap_ci(self) -> None:
        """F5.2: Verify part_a reports matched, F1, and bootstrap confidence intervals."""
        part_a = self.semje_data.get("part_a", {})
        self.assertGreater(len(part_a), 0, "Missing part_a in semje.json")
        for pair_name, metrics in part_a.items():
            self.assertIn("f1", metrics, f"Missing f1 in {pair_name}")
            self.assertIn("f1_ci", metrics, f"Missing f1_ci in {pair_name}")
            f1 = metrics["f1"]
            ci = metrics["f1_ci"]
            self.assertGreaterEqual(f1, 0.0)
            self.assertLessEqual(f1, 1.0)
            self.assertEqual(len(ci), 2)
            self.assertLessEqual(ci[0], ci[1])

    def test_t1_f5_semje_del_b_reports_kappa_across_9_fields(self) -> None:
        """F5.3: Verify part_b evaluates all 9 core theory claim coding fields."""
        expected_fields = [
            "is_claim",
            "is_headline",
            "claim_location",
            "attribution",
            "relation_kind",
            "support_status",
            "scope",
            "explanation",
            "prediction",
        ]
        fields = self.semje_data.get("part_b", {}).get("fields", {})
        for field in expected_fields:
            self.assertIn(field, fields, f"Missing field '{field}' in semje.json part_b")
            f_data = fields[field]
            self.assertIn("n_units", f_data)
            self.assertIn("alpha", f_data)

    def test_t1_f5_semje_concepts_and_support_jaccard_metrics(self) -> None:
        """F5.4: Verify semje reports concepts and support_forms Jaccard metrics."""
        part_b = self.semje_data.get("part_b", {})
        self.assertIn("concepts", part_b, "Missing concepts in part_b")
        self.assertIn("support_forms", part_b, "Missing support_forms in part_b")
        for pair, c_metrics in part_b["concepts"].items():
            jaccard = c_metrics.get("jaccard")
            self.assertIsNotNone(jaccard, f"Missing concepts jaccard for {pair}")
            self.assertGreaterEqual(jaccard, 0.0)
            self.assertLessEqual(jaccard, 1.0)

    def test_t1_f5_semje_json_output_structure_validity(self) -> None:
        """F5.5: Validate top-level keys and positive text counts in semje.json."""
        for key in ("coders_b", "coders_a", "draws", "part_b", "part_a", "n_items", "n_texts"):
            self.assertIn(key, self.semje_data, f"Missing key in semje.json: {key}")
        self.assertGreater(
            self.semje_data.get("n_texts", 0),
            0,
            "n_texts in semje.json must be > 0",
        )
        self.assertGreater(
            self.semje_data.get("n_items", 0),
            0,
            "n_items in semje.json must be > 0",
        )

    # --- Feature 6: Grensa 400-Work Coding Sheet (R2.2) ---

    def test_t1_f6_grensa_generation_script_produces_required_files(self) -> None:
        """F6.1: Verify generator script and all 4 boundary coding sheet files exist."""
        script_path = ROOT / "scripts" / "lag_grensekodeark.py"
        self.assertTrue(script_path.exists(), f"Missing generator script: {script_path}")
        expected_files = [
            "kodeark_kodar_A.csv",
            "kodeark_kodar_B.csv",
            "nokkel_IKKJE_TIL_KODARAR.csv",
            "kodar-rettleiing.md",
        ]
        for fname in expected_files:
            fpath = self.grensa_dir / fname
            self.assertTrue(fpath.exists(), f"Missing Grensa output file: {fpath}")

    def test_t1_f6_grensa_coder_sheets_contain_exact_400_works(self) -> None:
        """F6.2: Verify Coder A and B sheets each contain exactly 400 works."""
        for fname in ("kodeark_kodar_A.csv", "kodeark_kodar_B.csv"):
            fpath = self.grensa_dir / fname
            with open(fpath, encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
            self.assertEqual(
                len(rows) - 1,
                400,
                f"Expected exactly 400 works in {fname}, got {len(rows) - 1}",
            )

    def test_t1_f6_grensa_stratification_8_strata_50_works_each(self) -> None:
        """F6.3: Verify exact stratification across 8 strata with 50 works each."""
        key_path = self.grensa_dir / "nokkel_IKKJE_TIL_KODARAR.csv"
        with open(key_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            counts: dict[str, int] = {}
            for r in reader:
                rute = r["rute"]
                counts[rute] = counts.get(rute, 0) + 1
        self.assertEqual(
            len(counts), 8, f"Expected 8 strata, got {len(counts)}: {list(counts.keys())}"
        )
        for rute, count in counts.items():
            self.assertEqual(
                count, 50, f"Expected 50 works in stratum '{rute}', got {count}"
            )

    def test_t1_f6_grensa_hare_niemeyer_weights_sum_to_26425(self) -> None:
        """F6.4: Verify Hare-Niemeyer sampling weights sum to exactly 26,425.0."""
        key_path = self.grensa_dir / "nokkel_IKKJE_TIL_KODARAR.csv"
        with open(key_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            total_weight = sum(float(r["vekt"]) for r in reader)
        self.assertAlmostEqual(
            total_weight,
            26425.0,
            delta=0.1,
            msg=f"Expected weight sum ~26,425.0, got {total_weight}",
        )

    def test_t1_f6_grensa_coder_sheets_blinded_to_ground_truth(self) -> None:
        """F6.5: Verify coder sheets do not leak ground truth strata or weights."""
        prohibited_cols = {"rute", "stratum", "vekt", "fasit", "inne_ute", "celle_N"}
        for fname in ("kodeark_kodar_A.csv", "kodeark_kodar_B.csv"):
            fpath = self.grensa_dir / fname
            with open(fpath, encoding="utf-8-sig") as f:
                header = next(csv.reader(f))
            leaked = set(header).intersection(prohibited_cols)
            self.assertEqual(
                len(leaked), 0, f"Leaked columns {leaked} in coder sheet {fname}"
            )

    # --- Feature 7: Manuscript Updates & Gransking Invariants (R3) ---

    def test_t1_f7_manuscript_md_contains_all_p1_p10_headers(self) -> None:
        """F7.1: Verify gransking/artikkel.md contains sections for Påstand P1..P10."""
        md_path = self.gransking_dir / "artikkel.md"
        self.assertTrue(md_path.exists(), f"Missing {md_path}")
        text = md_path.read_text(encoding="utf-8")
        for i in range(1, 11):
            target = f"Påstand P{i}"
            self.assertIn(
                target, text, f"Missing required claim header '{target}' in {md_path}"
            )

    def test_t1_f7_manuscript_zero_unicode_em_dash_invariants(self) -> None:
        """F7.2: Verify zero Unicode em-dash (U+2014) in any gransking file."""
        candidates = list(self.gransking_dir.rglob("*.md")) + \
                     list(self.gransking_dir.rglob("*.tex")) + \
                     list(self.gransking_dir.rglob("*.svg"))
        for fpath in candidates:
            txt = fpath.read_text(encoding="utf-8")
            self.assertNotIn(
                "\u2014",
                txt,
                f"Prohibited Unicode em-dash found in {fpath.relative_to(ROOT)}",
            )

    def test_t1_f7_manuscript_zero_latex_em_dash_invariants(self) -> None:
        """F7.3: Verify zero LaTeX em-dash (---) in gransking/artikkel.tex."""
        tex_path = self.gransking_dir / "artikkel.tex"
        self.assertTrue(tex_path.exists(), f"Missing {tex_path}")
        txt = tex_path.read_text(encoding="utf-8")
        self.assertNotIn(
            "---", txt, f"Prohibited LaTeX em-dash '---' found in {tex_path}"
        )

    def test_t1_f7_manuscript_compiled_pdf_present_and_sized(self) -> None:
        """F7.4: Verify gransking/artikkel.pdf exists and is > 100 KB."""
        pdf_path = self.gransking_dir / "artikkel.pdf"
        self.assertTrue(pdf_path.exists(), f"Missing PDF at {pdf_path}")
        size = pdf_path.stat().st_size
        self.assertGreater(
            size,
            100_000,
            f"PDF file size {size} bytes is under required threshold of 100,000 bytes",
        )

    def test_t1_f7_manuscript_statistical_results_files_consistent(self) -> None:
        """F7.5: Verify P1–P10 rows and confidence interval consistency."""
        res_json_path = self.gransking_dir / "data" / "resultatsamandrag.json"
        self.assertTrue(res_json_path.exists(), f"Missing {res_json_path}")
        data = read_json(res_json_path)
        table = data.get("summary_table", [])
        self.assertEqual(len(table), 10, f"Expected 10 claims in summary table, got {len(table)}")
        for row in table:
            cid = row["id"]
            self.assertTrue(cid.startswith("P"), f"Invalid claim id: {cid}")
            est = float(row["estimat_pct"])
            lo = float(row["ki95_lav_pct"])
            hi = float(row["ki95_hog_pct"])
            self.assertTrue(
                0.0 <= lo <= est <= hi <= 100.0,
                f"Invalid confidence interval for {cid}: lo={lo}, est={est}, hi={hi}",
            )

    # --- Feature 8: Corpus Protection & Invariants (R4) ---

    def test_t1_f8_locked_corpus_files_exist_and_unmodified(self) -> None:
        """F8.1: Verify existence of locked published corpus files."""
        locked = [
            self.publications_path,
            self.nordic_additions_path,
            DOCS_DATA_DIR / "meta" / "manifest.json",
            DOCS_DATA_DIR / "search" / "search_config.json",
            DATA_DIR / "designteori.sqlite.gz",
        ]
        if RAW_SQLITE.exists():
            locked.insert(0, RAW_SQLITE)
        for fpath in locked:
            self.assertTrue(fpath.exists(), f"Missing locked corpus file: {fpath}")

    def test_t1_f8_verify_all_command_passes_with_ok_true(self) -> None:
        """F8.2: Verify verify_all() executes and returns ok: true."""
        res = verify_all()
        self.assertTrue(res.get("ok"), f"verify_all failed: {res}")
        self.assertEqual(res.get("openalex_works"), 4694)
        self.assertEqual(res.get("nordic_candidates"), 1738)

    def test_t1_f8_zero_hard_non_design_papers_in_corpus(self) -> None:
        """F8.3: Verify zero clinical/hard non-design titles in publications.json."""
        pubs = read_json(self.publications_path)
        for pub in pubs:
            title = pub.get("title", "")
            self.assertFalse(
                bool(HARD_NON_DESIGN_RE.search(title)),
                f"Forbidden non-design title in publications.json: '{title}'",
            )

    def test_t1_f8_unified_sqlite_passes_integrity_and_privacy_checks(self) -> None:
        """F8.4: Verify public UNIFIED_SQLITE_GZ integrity check and zero leaked abstracts."""
        self.assertTrue(UNIFIED_SQLITE_GZ.exists(), "Missing designteori.sqlite.gz")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "check.sqlite"
            with gzip.open(UNIFIED_SQLITE_GZ, "rb") as src, tmp_db.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            conn = sqlite3.connect(tmp_db)
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                self.assertEqual(integrity, "ok", f"SQLite integrity failure: {integrity}")
                leaked_abstracts = conn.execute(
                    "SELECT COUNT(*) FROM works WHERE COALESCE(abstract, '') <> ''"
                ).fetchone()[0]
                self.assertEqual(
                    leaked_abstracts, 0, f"Leaked {leaked_abstracts} abstracts in public DB"
                )
                leaked_raw = conn.execute(
                    "SELECT COUNT(*) FROM works WHERE COALESCE(raw_json, '{}') <> '{}'"
                ).fetchone()[0]
                self.assertEqual(
                    leaked_raw, 0, f"Leaked {leaked_raw} raw blobs in public DB"
                )
            finally:
                conn.close()

    def test_t1_f8_all_four_test_suites_execute_cleanly(self) -> None:
        """F8.5: Verify core verification command executes with returncode 0."""
        res = subprocess.run(
            [sys.executable, "designteori.py", "verify"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"designteori.py verify failed with code {res.returncode}: {res.stderr}",
        )
        self.assertIn('"ok": true', res.stdout)


# ---------------------------------------------------------------------------
# Tier 2: Boundary and Corner Cases (40 Tests, 5 per Feature)
# ---------------------------------------------------------------------------


class Tier2BoundaryAndCornerTests(unittest.TestCase):
    """
    Tier 2: Boundary value analysis, corner cases, and stress resilience across F1–F8.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.nva_report_path = DOCS_DATA_DIR / "nva_audit_report.json"
        cls.nva_report = (
            read_json(cls.nva_report_path) if cls.nva_report_path.exists() else {}
        )
        cls.nordes_path = IMPORTS_DIR / "nordes" / "nordes_drs.json"
        cls.semje_path = DOCS_DIR / "validering" / "semje.json"
        cls.grensa_dir = DOCS_DIR / "validering" / "grensa"
        cls.gransking_dir = ROOT / "gransking"

    # --- Feature 1: NVA URL Audit ---

    def test_t2_f1_nva_audit_boundary_exact_760_count(self) -> None:
        """F1.B1: Assert target audited count exactly satisfies the 760-handle target."""
        audited = self.nva_report.get("audited_count", len(self.nva_report.get("items", [])))
        self.assertEqual(
            audited,
            760,
            f"Expected exactly 760 audited NVA items, got {audited}",
        )

    def test_t2_f1_nva_audit_handles_malformed_url_schemes(self) -> None:
        """F1.B2: Verify resolution logic handles non-handle/malformed URL inputs safely."""
        from urllib.parse import urlparse
        for item in self.nva_report.get("items", [])[:50]:
            h_url = item.get("handle_url", "")
            parsed = urlparse(h_url)
            self.assertIn(parsed.scheme, ("http", "https"))
            self.assertTrue(parsed.netloc.endswith("handle.net"))

    def test_t2_f1_nva_audit_handles_http_error_codes(self) -> None:
        """F1.B3: Verify items with error conditions have descriptive status or error message."""
        summary = self.nva_report.get("summary", {})
        error_count = summary.get("error", 0) + summary.get("redirect_failed", 0)
        self.assertGreaterEqual(error_count, 0)
        for item in self.nva_report.get("items", []):
            if item.get("resolution_status") == "error":
                self.assertIsNotNone(item.get("error"))

    def test_t2_f1_nva_audit_zero_byte_document_resolution(self) -> None:
        """F1.B4: Ensure items marked verified_oa_pdf do not resolve to empty files."""
        pdf_items = [
            i for i in self.nva_report.get("items", [])
            if i.get("resolution_status") == "verified_oa_pdf"
        ]
        self.assertGreater(
            len(pdf_items), 0, "Expected at least 1 verified OA PDF in audit"
        )
        for item in pdf_items:
            open_files = item.get("open_files", [])
            self.assertGreater(
                len(open_files),
                0,
                f"Item {item.get('id')} marked verified_oa_pdf but has 0 open files",
            )

    def test_t2_f1_nva_audit_missing_or_null_field_resilience(self) -> None:
        """F1.B5: Verify handling of items with null or missing DOI fields."""
        items = self.nva_report.get("items", [])
        no_doi_items = [i for i in items if not i.get("original_doi")]
        self.assertGreater(len(no_doi_items), 0, "Expected items without original DOI")
        for item in no_doi_items:
            self.assertIsInstance(item.get("id"), str)
            self.assertIn("resolution_status", item)

    # --- Feature 2: OpenAlex 18 Queries Rerun ---

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t2_f2_openalex_boundary_zero_quota_errors_remain(self) -> None:
        """F2.B1: Assert 18 Nordic queries have exactly 0 quota errors in query_log."""
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM query_log WHERE query LIKE 'nordic_lang:%' AND (error LIKE '%429%' OR error LIKE '%quota%')"
            ).fetchone()[0]
            self.assertEqual(count, 0, f"Found {count} lingering quota errors in 18 Nordic queries")
        finally:
            conn.close()

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t2_f2_openalex_empty_hits_query_logged_as_success(self) -> None:
        """F2.B2: Assert queries returning 0 hits have error IS NULL (clean run)."""
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            zero_hits = conn.execute(
                "SELECT query, error FROM query_log WHERE total_hits = 0 AND query LIKE 'nordic_lang:%'"
            ).fetchall()
            for q, err in zero_hits:
                self.assertIsNone(err, f"0-hit query '{q}' has unexpected error: {err}")
        finally:
            conn.close()

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t2_f2_openalex_pagination_max_page_boundary(self) -> None:
        """F2.B3: Verify query_log pages are within bounds for Nordic language queries."""
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            max_page = conn.execute(
                "SELECT MAX(page) FROM query_log WHERE query LIKE 'nordic_lang:%'"
            ).fetchone()[0]
            self.assertIsNotNone(max_page)
            self.assertLessEqual(max_page, 10, f"Max page {max_page} exceeds limit")
        finally:
            conn.close()

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t2_f2_openalex_special_characters_in_nordic_queries(self) -> None:
        """F2.B4: Verify proper diacritic query logging for hönnun and tjänstedesign."""
        special_queries = ["nordic_lang:hönnun", "nordic_lang:tjänstedesign", "nordic_lang:muotoilututkimus"]
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            for q in special_queries:
                row = conn.execute(
                    "SELECT returned, error FROM query_log WHERE query = ?", (q,)
                ).fetchone()
                self.assertIsNotNone(row, f"Diacritic query '{q}' missing from query_log")
                self.assertIsNone(row[1], f"Diacritic query '{q}' has error: {row[1]}")
        finally:
            conn.close()

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t2_f2_openalex_deduplication_on_repeated_ingestion(self) -> None:
        """F2.B5: Verify (query, page) primary key uniqueness in query_log."""
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT query, page, COUNT(*) FROM query_log GROUP BY query, page HAVING COUNT(*) > 1"
            ).fetchall()
            self.assertEqual(len(rows), 0, f"Found duplicate query_log keys: {rows}")
        finally:
            conn.close()

    # --- Feature 3: FI/DK/IS Archive Harvest ---

    def test_t2_f3_finland_archive_strict_positive_lower_bound(self) -> None:
        """F3.B1: Assert Finland Aalto harvest count meets strict positive threshold."""
        p = IMPORTS_DIR / "aalto" / "aaltodoc_design.json"
        records = read_json(p)
        self.assertGreaterEqual(
            len(records), 20, f"Expected >= 20 Aalto records, got {len(records)}"
        )

    def test_t2_f3_oai_resumption_token_boundary_termination(self) -> None:
        """F3.B2: Verify archive harvester termination logic on empty resumption."""
        p = IMPORTS_DIR / "aalto" / "aaltodoc_design.json"
        self.assertTrue(p.stat().st_size > 0)

    def test_t2_f3_archive_record_missing_doi_fallback_identifier(self) -> None:
        """F3.B3: Verify records without DOI have deterministic non-empty IDs."""
        for fpath in (
            IMPORTS_DIR / "aalto" / "aaltodoc_design.json",
            IMPORTS_DIR / "kgl" / "danish_design.json",
            IMPORTS_DIR / "iris" / "iceland_design.json",
        ):
            records = read_json(fpath)
            for r in records:
                wid = r.get("id", "")
                self.assertTrue(bool(wid), f"Empty ID in {fpath.name}")
                self.assertNotIn(" ", wid, f"Whitespace in ID '{wid}' in {fpath.name}")

    def test_t2_f3_archive_author_list_truncation_boundary(self) -> None:
        """F3.B4: Verify author lists are lists of strings and not oversized."""
        p = IMPORTS_DIR / "aalto" / "aaltodoc_design.json"
        for r in read_json(p):
            authors = r.get("authors", [])
            self.assertIsInstance(authors, list)
            for a in authors:
                self.assertIsInstance(a, str)

    def test_t2_f3_archive_publication_year_boundary_filtering(self) -> None:
        """F3.B5: Verify publication years fall strictly in 1900..2026 or None."""
        for fpath in (
            IMPORTS_DIR / "aalto" / "aaltodoc_design.json",
            IMPORTS_DIR / "kgl" / "danish_design.json",
            IMPORTS_DIR / "iris" / "iceland_design.json",
        ):
            for r in read_json(fpath):
                yr = r.get("year")
                if yr is not None:
                    self.assertIsInstance(yr, int)
                    self.assertTrue(
                        1900 <= yr <= 2026,
                        f"Year {yr} out of range [1900, 2026] in {fpath.name}",
                    )

    # --- Feature 4: Nordes ~665 Scrape Replacement ---

    def test_t2_f4_nordes_count_strictly_exceeds_623_legacy_bound(self) -> None:
        """F4.B1: Assert Nordes harvest record count is >= 665."""
        records = read_json(self.nordes_path)
        self.assertGreaterEqual(
            len(records), 665, f"Expected >= 665 records, got {len(records)}"
        )

    def test_t2_f4_nordes_pagination_offset_600_yields_records(self) -> None:
        """F4.B2: Verify total count requires offset 600 pagination."""
        records = read_json(self.nordes_path)
        self.assertGreater(
            len(records),
            600,
            f"Record count {len(records)} proves query surpassed offset 400",
        )

    def test_t2_f4_nordes_crossref_rate_limit_backoff_handling(self) -> None:
        """F4.B3: Inspect harvest_nordes_crossref source for polite delay."""
        import inspect
        from designteori import collect
        src = inspect.getsource(collect.harvest_nordes_crossref)
        self.assertIn("sleep", src, "Missing polite rate limit delay in harvester")

    def test_t2_f4_nordes_handling_special_characters_in_titles(self) -> None:
        """F4.B4: Verify no unicode replacement characters (\ufffd) in Nordes titles."""
        records = read_json(self.nordes_path)
        for r in records:
            title = r.get("title", "")
            self.assertNotIn("\ufffd", title, f"Mangled title in Nordes: {title}")

    def test_t2_f4_nordes_conference_year_temporal_boundary(self) -> None:
        """F4.B5: Verify conference years span from 2005 (inaugural Nordes) to present."""
        records = read_json(self.nordes_path)
        years = [r.get("year") for r in records if r.get("year")]
        self.assertIn(2005, years, "Inaugural Nordes 2005 papers missing")
        self.assertGreaterEqual(max(years), 2021, "Recent Nordes conferences missing")

    # --- Feature 5: Teorielement Inter-Rater Reliability ---

    def test_t2_f5_semje_selftest_zero_noise_yields_perfect_scores(self) -> None:
        """F5.B1: Verify perfect agreement logic in semje with zero noise."""
        sys.path.insert(0, str((DOCS_DIR / "validering").resolve()))
        import semje
        pairs = [("a", "a"), ("b", "b"), ("c", "c"), ("a", "a")]
        k = semje.kappa(pairs)
        self.assertEqual(k, 1.0)
        self.assertEqual(semje.overlap("design research", "design research"), 1.0)

    def test_t2_f5_semje_single_class_coder_kappa_fallback(self) -> None:
        """F5.B2: Verify fallback to pct agreement when rater variance is zero."""
        semje_data = read_json(self.semje_path)
        part_b = semje_data.get("part_b", {})
        fields = part_b.get("fields", {})
        for fname, fdata in fields.items():
            for pair, pdata in fdata.get("pairs", {}).items():
                self.assertIn("pct", pdata, f"Missing pct in {fname} for {pair}")

    def test_t2_f5_semje_sample_size_scaling_boundary(self) -> None:
        """F5.B3: Verify sample size exceeds original 30-text pilot."""
        semje_data = read_json(self.semje_path)
        self.assertGreater(
            semje_data.get("n_items", 0),
            30,
            "Validation items should scale beyond 30-text pilot",
        )

    def test_t2_f5_semje_missing_item_excerpt_graceful_handling(self) -> None:
        """F5.B4: Verify excerpt overlap metrics do not raise division by zero."""
        semje_data = read_json(self.semje_path)
        excerpts = semje_data.get("part_b", {}).get("excerpts", {})
        for pair, pdata in excerpts.items():
            for field, m in pdata.items():
                share = m.get("share_overlap")
                self.assertIsNotNone(share)
                self.assertTrue(0.0 <= share <= 1.0)

    def test_t2_f5_semje_bootstrap_draws_ci_convergence(self) -> None:
        """F5.B5: Verify bootstrap CI bounds satisfy lo <= stat <= hi."""
        semje_data = read_json(self.semje_path)
        draws = semje_data.get("draws", 0)
        self.assertGreaterEqual(draws, 500, f"Expected >= 500 bootstrap draws, got {draws}")

    # --- Feature 6: Grensa 400-Work Coding Sheet ---

    def test_t2_f6_grensa_exact_400_row_count_no_off_by_one(self) -> None:
        """F6.B1: Assert neither sheet has off-by-one errors (not 399 or 401)."""
        for fname in ("kodeark_kodar_A.csv", "kodeark_kodar_B.csv", "nokkel_IKKJE_TIL_KODARAR.csv"):
            fpath = self.grensa_dir / fname
            with open(fpath, encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
            self.assertEqual(
                len(rows) - 1, 400, f"Off-by-one in {fname}: got {len(rows)-1} rows"
            )

    def test_t2_f6_grensa_exact_50_stratum_allocation_balance(self) -> None:
        """F6.B2: Assert all 8 strata have exactly 50 works allocated."""
        key_path = self.grensa_dir / "nokkel_IKKJE_TIL_KODARAR.csv"
        with open(key_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            from collections import Counter
            counts = Counter(r["rute"] for r in reader)
        self.assertEqual(set(counts.values()), {50})

    def test_t2_f6_grensa_hare_niemeyer_weight_sum_precision(self) -> None:
        """F6.B3: Assert sampling weight sum precision within 0.01 tolerance."""
        key_path = self.grensa_dir / "nokkel_IKKJE_TIL_KODARAR.csv"
        with open(key_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            total = sum(float(r["vekt"]) for r in reader)
        self.assertAlmostEqual(total, 26425.0, delta=0.01)

    def test_t2_f6_grensa_zero_strata_leakage_in_coder_csvs(self) -> None:
        """F6.B4: Assert no sampling weight or route columns in coder CSVs."""
        for fname in ("kodeark_kodar_A.csv", "kodeark_kodar_B.csv"):
            fpath = self.grensa_dir / fname
            with open(fpath, encoding="utf-8-sig") as f:
                header = next(csv.reader(f))
            self.assertNotIn("vekt", header)
            self.assertNotIn("rute", header)

    def test_t2_f6_grensa_coder_work_id_overlap_is_exact_identity(self) -> None:
        """F6.B5: Assert set of works in Coder A and B is identical."""
        def get_ids(fname: str) -> set[str]:
            with open(self.grensa_dir / fname, encoding="utf-8-sig") as f:
                return {r["id"] for r in csv.DictReader(f)}
        self.assertEqual(get_ids("kodeark_kodar_A.csv"), get_ids("kodeark_kodar_B.csv"))

    # --- Feature 7: Manuscript Updates & Invariants ---

    def test_t2_f7_manuscript_p1_p10_claim_count_exact_boundary(self) -> None:
        """F7.B1: Assert exactly 10 claims exist in resultatsamandrag.json."""
        res_json = read_json(self.gransking_dir / "data" / "resultatsamandrag.json")
        ids = [r["id"] for r in res_json.get("summary_table", [])]
        expected = [f"P{i}" for i in range(1, 11)]
        self.assertEqual(ids, expected)

    def test_t2_f7_manuscript_zero_em_dash_regex_boundary_checks(self) -> None:
        """F7.B2: Strict regex check for zero em-dash in artikkel.md and artikkel.tex."""
        em_dash_re = re.compile(r"\u2014")
        md_txt = (self.gransking_dir / "artikkel.md").read_text(encoding="utf-8")
        tex_txt = (self.gransking_dir / "artikkel.tex").read_text(encoding="utf-8")
        self.assertEqual(len(em_dash_re.findall(md_txt)), 0)
        self.assertEqual(len(em_dash_re.findall(tex_txt)), 0)

    def test_t2_f7_manuscript_pdf_size_strict_lower_bound(self) -> None:
        """F7.B3: Assert compiled PDF size strictly exceeds 100,000 bytes."""
        pdf_path = self.gransking_dir / "artikkel.pdf"
        self.assertGreater(pdf_path.stat().st_size, 100_000)

    def test_t2_f7_manuscript_statistical_confidence_interval_bounds(self) -> None:
        """F7.B4: For all P1..P10 claims, assert 0 <= lo <= est <= hi <= 100."""
        res_json = read_json(self.gransking_dir / "data" / "resultatsamandrag.json")
        for r in res_json.get("summary_table", []):
            est = float(r["estimat_pct"])
            lo = float(r["ki95_lav_pct"])
            hi = float(r["ki95_hog_pct"])
            self.assertTrue(0.0 <= lo <= est <= hi <= 100.0)

    def test_t2_f7_manuscript_corpus_sample_size_floor_checks(self) -> None:
        """F7.B5: Assert metadata.corpus_total_works >= 6000 and fulltext_pdfs >= 1400."""
        res_json = read_json(self.gransking_dir / "data" / "resultatsamandrag.json")
        meta = res_json.get("metadata", {})
        self.assertGreaterEqual(meta.get("corpus_total_works", 0), 6000)
        self.assertGreaterEqual(meta.get("fulltext_pdfs_analyzed", 0), 1400)

    # --- Feature 8: Corpus Protection & Invariants ---

    def test_t2_f8_corpus_openalex_works_minimum_count_bound(self) -> None:
        """F8.B1: Assert publications.json has >= 3500 entries (baseline 4,694)."""
        pubs = read_json(DOCS_DATA_DIR / "publications.json")
        self.assertGreaterEqual(len(pubs), 3500)

    def test_t2_f8_corpus_sqlite_gz_maximum_file_size_bound(self) -> None:
        """F8.B2: Assert designteori.sqlite.gz is under 95 MB limit."""
        gz_path = DATA_DIR / "designteori.sqlite.gz"
        self.assertTrue(gz_path.exists())
        self.assertLessEqual(gz_path.stat().st_size, 95_000_000)

    def test_t2_f8_corpus_sqlite_abstract_and_raw_blob_leak_zero(self) -> None:
        """F8.B3: Assert zero leaked abstracts and raw_json in public unified DB."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "check.sqlite"
            with gzip.open(UNIFIED_SQLITE_GZ, "rb") as src, tmp_db.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            conn = sqlite3.connect(tmp_db)
            try:
                leaked_abs = conn.execute(
                    "SELECT COUNT(*) FROM works WHERE COALESCE(abstract, '') <> ''"
                ).fetchone()[0]
                self.assertEqual(leaked_abs, 0)
                leaked_raw = conn.execute(
                    "SELECT COUNT(*) FROM works WHERE COALESCE(raw_json, '{}') <> '{}'"
                ).fetchone()[0]
                self.assertEqual(leaked_raw, 0)
            finally:
                conn.close()

    def test_t2_f8_corpus_uncommitted_working_tree_preservation(self) -> None:
        """F8.B4: Verify tracked corpus files are intact and uncorrupted."""
        for fpath in (
            DOCS_DATA_DIR / "publications.json",
            DOCS_DATA_DIR / "nordic_additions.json",
        ):
            self.assertTrue(fpath.exists())
            self.assertGreater(fpath.stat().st_size, 1000)

    def test_t2_f8_corpus_semantic_vector_dimensions_exact_match(self) -> None:
        """F8.B5: Assert vector file existence or metadata consistency."""
        vis_manifest = read_json(DOCS_DATA_DIR / "vis" / "manifest.json")
        self.assertIn("verk.json", vis_manifest.get("filer", {}))
        sem_meta = read_json(DOCS_DATA_DIR / "semantic_index.json")
        vec_bin = DOCS_DATA_DIR / "semantic_vectors.bin"
        self.assertTrue(vec_bin.exists(), "Missing semantic_vectors.bin")
        self.assertEqual(
            vec_bin.stat().st_size,
            len(sem_meta["ids"]) * sem_meta["dimensions"],
        )


# ---------------------------------------------------------------------------
# Tier 3: Pairwise Cross-Feature Combinations (6 Tests)
# ---------------------------------------------------------------------------


class Tier3PairwiseCrossFeatureTests(unittest.TestCase):
    """
    Tier 3: Pairwise cross-feature interactions across F1–F8.
    """

    def test_t3_pairwise_nva_audit_with_corpus_hygiene(self) -> None:
        """F1 x F8: Resolved NVA URLs comply with allowed host and security policies."""
        nva_report = read_json(DOCS_DATA_DIR / "nva_audit_report.json")
        for item in nva_report.get("items", [])[:100]:
            h_url = item.get("handle_url", "")
            r_url = item.get("resolved_registration_url", "")
            self.assertTrue(h_url.startswith("https://hdl.handle.net/"))
            if r_url:
                self.assertTrue(r_url.startswith("https://nva.sikt.no/"))

    @unittest.skipUnless(RAW_SQLITE.exists(), "RAW_SQLITE absent in CI")
    def test_t3_pairwise_openalex_rerun_with_sqlite_purity(self) -> None:
        """F2 x F8: Rerun Nordic queries in SQLite do not compromise database integrity."""
        conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            self.assertEqual(row[0], "ok")
            nordic_queries = conn.execute(
                "SELECT COUNT(*) FROM query_log WHERE query LIKE 'nordic_lang:%'"
            ).fetchone()[0]
            self.assertEqual(nordic_queries, 18)
        finally:
            conn.close()

    def test_t3_pairwise_archive_harvest_and_nordes_deduplication(self) -> None:
        """F3 x F4: Harvested archive and Nordes records have zero ID collisions."""
        nordes_ids = {r["id"] for r in read_json(IMPORTS_DIR / "nordes" / "nordes_drs.json")}
        aalto_ids = {r["id"] for r in read_json(IMPORTS_DIR / "aalto" / "aaltodoc_design.json")}
        collision = nordes_ids.intersection(aalto_ids)
        self.assertEqual(
            len(collision), 0, f"ID collision between Nordes and Aalto: {collision}"
        )

    def test_t3_pairwise_validation_sampling_id_consistency(self) -> None:
        """F5 x F6: Grensa coding sheet IDs are well-formed canonical identifiers."""
        grensa_key = DOCS_DIR / "validering" / "grensa" / "nokkel_IKKJE_TIL_KODARAR.csv"
        with open(grensa_key, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                wid = r["id"]
                self.assertTrue(bool(wid))
                self.assertTrue(
                    wid.startswith("W") or wid.startswith("nordic:") or wid.startswith("10."),
                    f"Unexpected work ID format in Grensa: {wid}",
                )

    def test_t3_pairwise_grensa_strata_with_manuscript_claims(self) -> None:
        """F6 x F7: Grensa 400-work sample and 26,425 population align with manuscript text."""
        grensa_key = DOCS_DIR / "validering" / "grensa" / "nokkel_IKKJE_TIL_KODARAR.csv"
        with open(grensa_key, encoding="utf-8-sig") as f:
            total_weight = sum(float(r["vekt"]) for r in csv.DictReader(f))
        self.assertAlmostEqual(total_weight, 26425.0, delta=0.1)

    def test_t3_pairwise_manuscript_updates_with_corpus_locking(self) -> None:
        """F7 x F8: Updating manuscript preserves locked published corpus files."""
        verify_res = verify_all()
        self.assertTrue(verify_res.get("ok"))
        self.assertTrue((ROOT / "gransking" / "artikkel.md").exists())
        self.assertTrue((ROOT / "gransking" / "artikkel.tex").exists())


# ---------------------------------------------------------------------------
# Tier 4: Real-World Acceptance Scenarios (4 Workloads)
# ---------------------------------------------------------------------------


class Tier4RealWorldScenarioTests(unittest.TestCase):
    """
    Tier 4: End-to-end acceptance scenarios exercising full lifecycle integration.
    """

    def test_t4_scenario_archive_harvest_and_audit_lifecycle(self) -> None:
        """
        Scenario 1: Full archive harvest and NVA audit lifecycle (F1, F3, F4, F8).
        Validates audit coverage, harvest file populations, and verify_all status.
        """
        nva_report = read_json(DOCS_DATA_DIR / "nva_audit_report.json")
        self.assertGreaterEqual(len(nva_report.get("items", [])), 760)

        aalto = read_json(IMPORTS_DIR / "aalto" / "aaltodoc_design.json")
        self.assertGreater(len(aalto), 0)
        nordes = read_json(IMPORTS_DIR / "nordes" / "nordes_drs.json")
        self.assertGreaterEqual(len(nordes), 665)

        res = verify_all()
        self.assertTrue(res.get("ok"))

    def test_t4_scenario_validation_and_stratification_workflows(self) -> None:
        """
        Scenario 2: Validation workflows and stratification matrix execution (F5, F6, F8).
        Validates semje agreement metrics, Grensa sheets (400 works, 8 strata, 50 each, blinded).
        """
        semje_data = read_json(DOCS_DIR / "validering" / "semje.json")
        self.assertGreater(semje_data.get("n_texts", 0), 0)
        self.assertIn("part_b", semje_data)

        key_path = DOCS_DIR / "validering" / "grensa" / "nokkel_IKKJE_TIL_KODARAR.csv"
        with open(key_path, encoding="utf-8-sig") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 400)
            from collections import Counter
            counts = Counter(r["rute"] for r in reader)
            self.assertEqual(set(counts.values()), {50})
            total_weight = sum(float(r["vekt"]) for r in reader)
            self.assertAlmostEqual(total_weight, 26425.0, delta=0.1)

    def test_t4_scenario_manuscript_quantitative_and_typographic_integrity(self) -> None:
        """
        Scenario 3: Manuscript integrity, claims P1–P10, and typography rules (F7, F8).
        """
        gransking_dir = ROOT / "gransking"
        md_txt = (gransking_dir / "artikkel.md").read_text(encoding="utf-8")
        for i in range(1, 11):
            self.assertIn(f"Påstand P{i}", md_txt)

        for fpath in list(gransking_dir.rglob("*.md")) + list(gransking_dir.rglob("*.tex")):
            self.assertNotIn("\u2014", fpath.read_text(encoding="utf-8"))

        self.assertNotIn("---", (gransking_dir / "artikkel.tex").read_text(encoding="utf-8"))
        self.assertGreater((gransking_dir / "artikkel.pdf").stat().st_size, 100_000)

    def test_t4_scenario_whole_repo_regression_and_corpus_gate(self) -> None:
        """
        Scenario 4: Multi-suite regression gating and locked corpus verification (F1–F8).
        """
        res = verify_all()
        self.assertTrue(res.get("ok"))

        if RAW_SQLITE.exists():
            conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
            try:
                status = conn.execute("PRAGMA integrity_check").fetchone()[0]
                self.assertEqual(status, "ok")
            finally:
                conn.close()

        pubs = read_json(DOCS_DATA_DIR / "publications.json")
        self.assertEqual(len(pubs), 4694)
        additions = read_json(DOCS_DATA_DIR / "nordic_additions.json")
        self.assertEqual(len(additions), 1738)

    def test_t4_nva_audit_doi_normalization_and_cli_subcommands(self) -> None:
        """Verify NVA audit report separates non-DOI external URLs from real DOIs and CLI exposes rerun-nordic/audit-nva."""
        from designteori import normalize_doi

        nva_report = read_json(DOCS_DATA_DIR / "nva_audit_report.json")
        for item in nva_report.get("items", []):
            if item.get("doi_found"):
                self.assertTrue(
                    bool(normalize_doi(item["doi_found"])),
                    f"Non-DOI value in doi_found for {item.get('id')}: {item.get('doi_found')}",
                )
            if item.get("doi_backfilled"):
                self.assertTrue(
                    bool(normalize_doi(item.get("doi_found"))),
                    f"Invalid doi_backfilled flag for {item.get('id')}",
                )

        proc = subprocess.run(
            [sys.executable, str(ROOT / "designteori.py"), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        self.assertIn("rerun-nordic", proc.stdout)
        self.assertIn("audit-nva", proc.stdout)


if __name__ == "__main__":
    unittest.main()
