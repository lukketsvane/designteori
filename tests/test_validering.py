"""Validation and coding workflows test suite (Milestone 2 / Track #3 / R2).

Tests:
1. Grensa 400-work boundary coding sheet integrity:
   - 400 unique works across 8 strata x 50 items.
   - In-scope (200) and out-of-scope (200) balance.
   - Sampling weights summing to 26,425.0 (per stratum and overall).
   - Independent randomization order between Coder A and Coder B.
   - Coder instruction guide presence and schema compliance.
2. Teorielement Inter-Rater Reliability workflow:
   - Coder A and Coder B workbooks presence and non-emptiness.
   - semje.json integrity: Del A F1 and CI.
   - Del B agreement across all 9 nominal fields (percent agreement, Cohen's kappa, Krippendorff's alpha).
   - Jaccard metrics for concepts, support forms, and theories.
"""
from __future__ import annotations

import csv
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
GRENSE_DIR = ROOT / "docs" / "validering" / "grensa"
VALIDERING_DIR = ROOT / "docs" / "validering"


class TestGrensaCodingSheet(unittest.TestCase):
    """Test suite for Grensa 400-work boundary coding sheet."""

    def test_grensa_files_exist(self):
        """Assert all 4 primary files exist in docs/validering/grensa/."""
        required_files = [
            GRENSE_DIR / "kodeark_kodar_A.csv",
            GRENSE_DIR / "kodeark_kodar_B.csv",
            GRENSE_DIR / "nokkel_IKKJE_TIL_KODARAR.csv",
            GRENSE_DIR / "kodar-rettleiing.md",
        ]
        for f in required_files:
            self.assertTrue(f.exists(), f"Missing required file: {f}")
            self.assertGreater(f.stat().st_size, 0, f"File is empty: {f}")

    def test_grensa_coder_sheets_row_counts_and_columns(self):
        """Assert coder sheets have 400 data rows and expected columns without leaking strata."""
        expected_cols = ["id", "title", "venue", "year", "abstract_link", "design_research", "merknad"]

        for name in ["kodeark_kodar_A.csv", "kodeark_kodar_B.csv"]:
            path = GRENSE_DIR / name
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, expected_cols, f"Unexpected header in {name}")
                rows = list(reader)
                self.assertEqual(len(rows), 400, f"{name} must have exactly 400 data rows")

                ids = [r["id"] for r in rows]
                self.assertEqual(len(set(ids)), 400, f"{name} contains duplicate IDs")
                # Ensure no blind-breaking columns exist
                for row in rows:
                    self.assertNotIn("rute", row)
                    self.assertNotIn("inne_ute", row)
                    self.assertNotIn("side", row)
                    self.assertNotIn("vekt", row)

    def test_grensa_coder_ordering_permutation(self):
        """Assert Coder A and Coder B receive the same 400 works in distinct random order."""
        with open(GRENSE_DIR / "kodeark_kodar_A.csv", encoding="utf-8-sig") as f:
            ids_a = [r["id"] for r in csv.DictReader(f)]
        with open(GRENSE_DIR / "kodeark_kodar_B.csv", encoding="utf-8-sig") as f:
            ids_b = [r["id"] for r in csv.DictReader(f)]

        self.assertEqual(set(ids_a), set(ids_b), "Coder A and B must code the exact same work set")
        self.assertNotEqual(ids_a, ids_b, "Coder A and B must have independent random orderings")

    def test_grensa_strata_and_weight_sum(self):
        """Assert master key has 8 strata x 50 works and weights sum to 26,425.0."""
        key_path = GRENSE_DIR / "nokkel_IKKJE_TIL_KODARAR.csv"
        with open(key_path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        self.assertEqual(len(rows), 400, "Master key must have 400 rows")

        expected_strata_totals = {
            "OA tidsskriftliste": 2386.0,
            "OA tittelord": 1722.0,
            "OA emne og tittel": 586.0,
            "arkivlaget (utan moglege dublettar)": 1613.0,
            "ute: anna fagfelt": 11117.0,
            "ute: utanfor tittelord": 5708.0,
            "ute: domene- eller metodeord": 2639.0,
            "ute: under semantisk terskel": 654.0,
        }

        # Check counts per stratum
        counts = {}
        side_counts = {"inne": 0, "ute": 0}
        strata_weights = {}

        for r in rows:
            route = r["rute"]
            side = r["inne_ute"]
            weight = float(r["vekt"])

            counts[route] = counts.get(route, 0) + 1
            side_counts[side] = side_counts.get(side, 0) + 1
            strata_weights[route] = strata_weights.get(route, 0.0) + weight

        self.assertEqual(len(counts), 8, "Must have exactly 8 strata")
        for route, count in counts.items():
            self.assertEqual(count, 50, f"Stratum '{route}' must have exactly 50 works")

        self.assertEqual(side_counts["inne"], 200, "Must have 200 in-scope works")
        self.assertEqual(side_counts["ute"], 200, "Must have 200 out-of-scope works")

        # Check sum of weights per stratum
        for route, expected_pop in expected_strata_totals.items():
            actual_weight = round(strata_weights[route], 1)
            self.assertEqual(
                actual_weight,
                expected_pop,
                f"Stratum '{route}' weights sum to {actual_weight}, expected {expected_pop}",
            )

        # Check overall sum
        total_weight = sum(float(r["vekt"]) for r in rows)
        self.assertEqual(round(total_weight, 1), 26425.0, f"Total weight sum was {total_weight}")

    def test_grensa_guide_content(self):
        """Assert coder instructions guide contains the operational questions and categories."""
        guide_path = GRENSE_DIR / "kodar-rettleiing.md"
        content = guide_path.read_text(encoding="utf-8")
        self.assertIn("Rettleiing til kodarane", content)
        self.assertIn("design_research", content)
        self.assertIn("yes", content)
        self.assertIn("no", content)
        self.assertIn("unclear", content)
        self.assertIn("20261113", content)


class TestTeorielementInterRaterReliability(unittest.TestCase):
    """Test suite for Teorielement inter-rater reliability workflow."""

    def test_workbooks_exist(self):
        """Assert Coder A and Coder B workbooks exist in docs/validering/."""
        workbooks = [
            VALIDERING_DIR / "kodeark-del-a-A.xlsx",
            VALIDERING_DIR / "kodeark-del-b-A.xlsx",
            VALIDERING_DIR / "kodeark-del-a-B.xlsx",
            VALIDERING_DIR / "kodeark-del-b-B.xlsx",
        ]
        for wb in workbooks:
            self.assertTrue(wb.exists(), f"Missing workbook: {wb}")
            self.assertGreater(wb.stat().st_size, 1000, f"Workbook too small or empty: {wb}")

    def test_semje_json_exists_and_structure(self):
        """Assert semje.json exists and adheres to validation schema."""
        semje_path = VALIDERING_DIR / "semje.json"
        self.assertTrue(semje_path.exists(), "semje.json does not exist")
        data = json.loads(semje_path.read_text(encoding="utf-8"))

        required_keys = ["coders_a", "coders_b", "draws", "part_a", "part_b", "n_items", "n_texts"]
        for k in required_keys:
            self.assertIn(k, data, f"Missing key in semje.json: {k}")

        self.assertEqual(data["n_items"], 52, "Expected 52 items evaluated in Part B")
        self.assertEqual(data["n_texts"], 21, "Expected 21 texts evaluated in Part B")

    def test_del_a_agreement_metrics(self):
        """Assert Del A contains pairwise F1 metrics and valid confidence intervals."""
        data = json.loads((VALIDERING_DIR / "semje.json").read_text(encoding="utf-8"))
        part_a = data.get("part_a", {})

        self.assertIn("A–B", part_a, "Missing A–B comparison in part_a")
        ab = part_a["A–B"]
        self.assertGreaterEqual(ab["f1"], 0.70, f"A-B F1 too low: {ab['f1']}")
        self.assertLessEqual(ab["f1"], 1.00)
        self.assertGreater(ab["matched"], 0)
        self.assertIsNotNone(ab.get("f1_ci"))
        ci = ab["f1_ci"]
        self.assertLessEqual(ci[0], ab["f1"])
        self.assertGreaterEqual(ci[1], ab["f1"])

    def test_del_b_nominal_fields_agreement(self):
        """Assert all 9 nominal fields are present with valid percent agreement and Cohen's kappa."""
        data = json.loads((VALIDERING_DIR / "semje.json").read_text(encoding="utf-8"))
        fields = data.get("part_b", {}).get("fields", {})

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
        for ef in expected_fields:
            self.assertIn(ef, fields, f"Missing nominal field in part_b: {ef}")
            f_entry = fields[ef]
            self.assertIn("pairs", f_entry)
            self.assertIn("A–B", f_entry["pairs"])
            ab_pair = f_entry["pairs"]["A–B"]
            self.assertGreater(ab_pair["n"], 0)
            self.assertGreaterEqual(ab_pair["pct"], 0.0)
            self.assertLessEqual(ab_pair["pct"], 1.0)
            if ab_pair["kappa"] is not None:
                self.assertGreaterEqual(ab_pair["kappa"], -1.0)
                self.assertLessEqual(ab_pair["kappa"], 1.0)

        # Specifically check relation_kind agreement meets pilot benchmark
        rk_ab = fields["relation_kind"]["pairs"]["A–B"]
        self.assertGreaterEqual(rk_ab["pct"], 0.75, f"relation_kind agreement was {rk_ab['pct']}")
        self.assertGreaterEqual(rk_ab["kappa"], 0.65, f"relation_kind kappa was {rk_ab['kappa']}")

    def test_del_b_jaccard_metrics(self):
        """Assert Jaccard similarities for concepts, support forms, and theories are in valid ranges."""
        data = json.loads((VALIDERING_DIR / "semje.json").read_text(encoding="utf-8"))
        part_b = data.get("part_b", {})

        # Concepts
        concepts = part_b.get("concepts", {}).get("A–B", {})
        self.assertGreaterEqual(concepts.get("jaccard", 0), 0.80)
        self.assertIn("role", concepts)
        self.assertIn("definition_status", concepts)

        # Support forms
        support = part_b.get("support_forms", {}).get("A–B", {})
        self.assertGreaterEqual(support.get("jaccard", 0), 0.70)
        self.assertIn("kappa_per_form", support)

        # Theories
        theories = part_b.get("theories", {}).get("A–B", {})
        self.assertGreaterEqual(theories.get("jaccard", 0), 0.80)


if __name__ == "__main__":
    unittest.main()
