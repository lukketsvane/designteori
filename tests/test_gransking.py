"""Einingstestar for den metavitskaplege granskinga i gransking/ (P1-P10)."""
from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import numpy as np

from gransking.analyse_korpus import (
    chi2_2x2,
    gini_coefficient,
    mann_whitney_u,
    split_body_and_references,
    wilson_ci,
)

ROOT = Path(__file__).resolve().parents[1]
GRANSKING_DIR = ROOT / "gransking"


class TestGransking(unittest.TestCase):
    def test_statistiske_hjelpefunksjonar(self) -> None:
        # Wilson 95 % KI ved k = 0 og k = n/2
        p0, lo0, hi0 = wilson_ci(0, 1461)
        self.assertEqual(p0, 0.0)
        self.assertEqual(lo0, 0.0)
        self.assertAlmostEqual(hi0, 0.00262, places=4)

        p50, lo50, hi50 = wilson_ci(500, 1000)
        self.assertAlmostEqual(p50, 0.50, places=5)
        self.assertTrue(0.46 < lo50 < 0.50 < hi50 < 0.54)

        # Mann-Whitney U og rang-biserial korrelasjon
        x = np.array([10.0, 12.0, 14.0, 16.0, 18.0])
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        mwu = mann_whitney_u(x, y)
        self.assertEqual(mwu["U"], 25.0)
        self.assertAlmostEqual(mwu["rank_biserial"], 1.0, places=4)
        self.assertLess(mwu["p"], 0.02)

        # 2x2 kjikvadrat med Haldane-Anscombe ved nullcelle
        res_chi = chi2_2x2(7, 728, 19, 707)
        self.assertAlmostEqual(res_chi["chi2"], 4.8773, places=3)
        self.assertLess(res_chi["p"], 0.05)
        self.assertLess(res_chi["odds_ratio"], 1.0)

        # Gini-koeffisient (lik fordeling -> 0)
        self.assertAlmostEqual(gini_coefficient([5, 5, 5, 5]), 0.0, places=6)

    def test_referanseseparasjon_fjernar_bibliografi(self) -> None:
        pages = [
            "1. Innleiing\nDette er ein prosessbasert workshop-studie utan hypotesar." * 8,
            "2. Diskusjon\nMe opnar opp moglegheitsrommet for refleksjon." * 8,
            "3. Konklusjon\nDeltakarane var nøgde.\n\nReferences\nPopper, K. (1959). Falsifiable hypothesis and randomized control trial, p < 0.001.",
        ]
        full, body, _ = split_body_and_references(pages)
        self.assertIn("Falsifiable hypothesis", full)
        self.assertNotIn("Falsifiable hypothesis", body)
        self.assertNotIn("randomized control trial", body)

    def test_resultatfiler_og_konfidensintervall(self) -> None:
        json_path = GRANSKING_DIR / "data" / "resultatsamandrag.json"
        csv_path = GRANSKING_DIR / "data" / "tabell_hypotesetestar.csv"
        self.assertTrue(json_path.is_file(), "Manglar resultatsamandrag.json")
        self.assertTrue(csv_path.is_file(), "Manglar tabell_hypotesetestar.csv")

        res = json.loads(json_path.read_text(encoding="utf-8"))
        meta = res["metadata"]
        self.assertGreaterEqual(meta["corpus_total_works"], 6000)
        self.assertGreaterEqual(meta["fulltext_pdfs_analyzed"], 1400)

        rows = res["summary_table"]
        expected_ids = [f"P{i}" for i in range(1, 11)]
        self.assertEqual([r["id"] for r in rows], expected_ids)

        for r in rows:
            self.assertGreater(r["utval_n"], 0, f"Ugyldig n for {r['id']}")
            self.assertLessEqual(r["ki95_lav_pct"], r["estimat_pct"], f"Nedre KI > estimat for {r['id']}")
            self.assertLessEqual(r["estimat_pct"], r["ki95_hog_pct"], f"Estimat > øvre KI for {r['id']}")
            self.assertGreaterEqual(r["ki95_lav_pct"], 0.0)
            self.assertLessEqual(r["ki95_hog_pct"], 100.0)

        with csv_path.open("r", encoding="utf-8") as fh:
            csv_rows = list(csv.DictReader(fh))
        self.assertEqual([r["id"] for r in csv_rows], expected_ids)

    def test_manuskript_figurar_og_typografi(self) -> None:
        required_files = [
            GRANSKING_DIR / "artikkel.md",
            GRANSKING_DIR / "artikkel.tex",
            GRANSKING_DIR / "README.md",
            GRANSKING_DIR / "figurar" / "fig1_hypotesetest_oversikt.svg",
            GRANSKING_DIR / "figurar" / "fig2_kumulativitet_og_amnesi.svg",
            GRANSKING_DIR / "figurar" / "fig3_metode_og_etikkprofil.svg",
            GRANSKING_DIR / "figurar" / "fig4_ekstern_siteringsfordeling.svg",
        ]
        for fpath in required_files:
            self.assertTrue(fpath.is_file(), f"Manglar fil: {fpath}")
            txt = fpath.read_text(encoding="utf-8")
            self.assertGreater(len(txt), 400, f"Fila er uventa kort: {fpath}")
            self.assertNotIn("\u2014", txt, f"Fann em-dash (U+2014) i {fpath.name}")

        md_txt = (GRANSKING_DIR / "artikkel.md").read_text(encoding="utf-8")
        for i in range(1, 11):
            self.assertIn(f"Påstand P{i}", md_txt, f"artikkel.md manglar seksjon for P{i}")

        tex_txt = (GRANSKING_DIR / "artikkel.tex").read_text(encoding="utf-8")
        self.assertNotIn("---", tex_txt, "artikkel.tex skal ikkje innehalde LaTeX em-dash (---)")

        pdf_path = GRANSKING_DIR / "artikkel.pdf"
        self.assertTrue(pdf_path.is_file(), "Manglar ferdigkompilert artikkel.pdf")
        self.assertGreater(pdf_path.stat().st_size, 100_000, "artikkel.pdf er uventa lita")


if __name__ == "__main__":
    unittest.main()
