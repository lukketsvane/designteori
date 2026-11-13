"""Tests for the figure data in docs/data/meta/ (built by designteori/metavis.py).

The tests read the published files and the copy of the verified findings in tests/fixtures/funn-samla.json
(76 findings; the corrected claim for adjusted ones; 15 new questions with the expectation fixed before the
measurement). Checks that need the private database are skipped when it is absent (CI has no database).
Standard library only, apart from importing designteori.metavis for the verdict rule (that module needs numpy
at import, which CI installs).
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from designteori import DOCS_DATA_DIR, RAW_SQLITE
from designteori import metavis

META = DOCS_DATA_DIR / "meta"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "funn-samla.json"
SEKSJONAR = ["materialet", "vekst", "kanalar", "siteringar", "tema", "omgrep", "kunnskap", "teori", "sporsmaal"]
TOTAL_GRENSE = 1_500_000

_cache: dict[str, object] = {}


def les(namn: str):
    if namn not in _cache:
        _cache[namn] = json.loads((META / namn).read_text(encoding="utf-8"))
    return _cache[namn]


def fasit():
    if "fasit" not in _cache:
        _cache["fasit"] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return _cache["fasit"]


def norm_lf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def tal_i_tekst(tekst: str) -> list[float]:
    """All numbers in a Norwegian text: thousands groups with a (narrow) space, decimal comma or point."""
    t = re.sub(r"[   ]", " ", tekst)
    t = re.sub(r"(?<![\d,.])(\d{1,3})((?: \d{3})+)(?!\d)", lambda m: m.group(1) + m.group(2).replace(" ", ""), t)
    return [float(m.group(0).replace(",", ".")) for m in re.finditer(r"\d+(?:[.,]\d+)?", t)]


def er_med(verdi, tekst: str) -> bool:
    """True when ``verdi`` equals a number in the text within rounding to the decimals ``verdi`` carries."""
    if isinstance(verdi, bool) or verdi is None:
        return False
    v = abs(float(verdi))
    s = repr(float(verdi)) if not float(verdi).is_integer() else str(int(verdi))
    d = len(s.split(".")[1]) if "." in s else 0
    tol = 0.5 * 10 ** (-d) + 1e-9
    return any(abs(x - v) <= tol for x in tal_i_tekst(tekst))


ORDTAL = {1: "ein", 2: "to", 3: "tre", 4: "fire", 5: "fem", 6: "seks", 7: "sju", 8: "åtte", 9: "ni", 10: "ti"}


def er_med_ord(verdi, tekst: str) -> bool:
    """Like er_med, but a whole number may also be spelled out in the text (tre, fire, ...)."""
    if er_med(verdi, tekst):
        return True
    if float(verdi) == 50 and "halvpart" in tekst.lower():
        return True
    ord_ = ORDTAL.get(int(verdi)) if float(verdi).is_integer() else None
    return bool(ord_ and re.search(r"\b%s\b" % ord_, tekst.lower()))


def kravtekst(finn_id: str) -> str:
    """The text a headline is checked against: the (corrected) claim, or the question with expectation and result."""
    f = fasit()
    for x in f["funn"]:
        if x["id"] == finn_id:
            return x["claim"]
    for q in f["nye_sporsmal"]:
        if q["id"] == finn_id:
            return " ".join([q["question"], q["expected_before"], q["result"]])
    raise KeyError(finn_id)


def alle_strenger(obj, sti=""):
    if isinstance(obj, str):
        yield sti, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from alle_strenger(v, sti + "/" + str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from alle_strenger(v, sti + "[%d]" % i)


def fig(fig_id: str) -> dict:
    m = les("manifest.json")
    for f in m["figurar"]:
        if f["id"] == fig_id:
            return les(f["fil"])["figurar"][fig_id]
    raise KeyError(fig_id)


class TestManifest(unittest.TestCase):
    def test_files_match_manifest(self):
        m = les("manifest.json")
        self.assertEqual(m["format"], metavis.FORMAT)
        self.assertEqual(sorted(m["filer"]), sorted(s + ".json" for s in SEKSJONAR))
        tot = 0
        for namn, info in m["filer"].items():
            raa = (META / namn).read_bytes()
            self.assertIn(info["bytes"], (len(raa), len(norm_lf(raa))), namn)
            self.assertIn(info["sha256"], {hashlib.sha256(raa).hexdigest(), hashlib.sha256(norm_lf(raa)).hexdigest()}, namn)
            tot += info["bytes"]
        self.assertLessEqual(tot + (META / "manifest.json").stat().st_size, TOTAL_GRENSE)

    def test_figure_list(self):
        m = les("manifest.json")
        ids = [f["id"] for f in m["figurar"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 18)
        self.assertLessEqual(len(ids), 26)
        self.assertEqual(ids, ["f%02d" % i for i in range(1, len(ids) + 1)])
        for f in m["figurar"]:
            self.assertIn(f["seksjon"], SEKSJONAR)
            self.assertEqual(f["fil"], f["seksjon"] + ".json")
            self.assertIn(f["id"], les(f["fil"])["figurar"])
            for k in ("tittel", "sporsmal", "form", "nemnar"):
                self.assertTrue(f[k].strip(), (f["id"], k))
            # every figure carries its denominator and layer in one short line
            self.assertLessEqual(len(f["nemnar"]), 260, f["id"])
            self.assertTrue(re.search(r"\d", f["nemnar"]), f["id"])
            self.assertTrue(f["finn"], f["id"])
            self.assertTrue(f["tal"], f["id"])
        # no figure is in a section file without being in the manifest
        for s in SEKSJONAR:
            d = les(s + ".json")
            self.assertEqual(d["format"], metavis.FORMAT)
            self.assertEqual(d["seksjon"], s)
            for fid in d["figurar"]:
                self.assertIn(fid, ids)

    def test_no_text_over_300_characters(self):
        for namn in [s + ".json" for s in SEKSJONAR] + ["manifest.json"]:
            for sti, s in alle_strenger(les(namn)):
                self.assertLessEqual(len(s), 300, f"{namn}{sti}")
                self.assertNotIn("—", s, f"{namn}{sti}")  # no em dashes

    def test_no_private_text_or_names(self):
        # counts and derived values only: no author names, no abstracts, no full-text fields
        for namn in [s + ".json" for s in SEKSJONAR]:
            raa = (META / namn).read_text(encoding="utf-8")
            for forbudt in ('"abstract"', '"forfattarar":[{', '"author_name"', '"fulltekst_tekst"', '"tekst":'):
                self.assertNotIn(forbudt, raa, (namn, forbudt))
        f13 = fig("f13")
        for n in f13["noder"]:
            self.assertLessEqual(len(n["tittel"]), 110)
        self.assertNotIn("namn", fig("f09")["forfattar"])


class TestHeadlines(unittest.TestCase):
    """Every headline number agrees with the verified finding it cites, within rounding."""

    def test_findings_used_are_verified(self):
        status = {x["id"]: x["status"] for x in fasit()["funn"]}
        status.update({q["id"]: q["status"] for q in fasit()["nye_sporsmal"]})
        m = les("manifest.json")
        brukt = set()
        for f in m["figurar"]:
            for fid in f["finn"]:
                self.assertIn(fid, status, (f["id"], fid))
                self.assertIn(status[fid], ("confirmed", "adjusted"), (f["id"], fid))
                brukt.add(fid)
            for t in f["tal"]:
                if t.get("finn"):
                    self.assertIn(t["finn"], f["finn"], (f["id"], t))
        # the one unverifiable finding is never used, and nothing outside the 91 ids
        self.assertNotIn("omgrep-6", brukt)
        self.assertTrue(brukt <= set(status))

    def test_headline_numbers_agree_with_claims(self):
        m = les("manifest.json")
        feil = []
        n = 0
        for f in m["figurar"]:
            for t in f["tal"]:
                if not t.get("finn"):
                    continue
                n += 1
                if not er_med(t["verdi"], kravtekst(t["finn"])):
                    feil.append((f["id"], t["finn"], t["etikett"], t["verdi"]))
        self.assertGreater(n, 250)
        self.assertEqual(feil, [], "tal som ikkje finst i det verifiserte funnet")

    def test_site_numbers_agree_with_kart_json(self):
        kart = json.loads((DOCS_DATA_DIR / "klynger" / "kart.json").read_text(encoding="utf-8"))
        t = kart["tal"]
        f18 = fig("f18")
        self.assertEqual(len(f18["x"]), t["verk"])
        self.assertEqual(f18["silhuett"], t["silhuett"])
        self.assertEqual(f18["silhuett_null"], t["silhuett_null"])
        self.assertEqual(f18["grense_del"], t["grense_del"])
        self.assertEqual(len(f18["klynger"]), t["klynger"])
        sett = {"Verk i kartet": t["verk"], "Klynger i kartet": t["klynger"], "Silhuett": t["silhuett"],
                "Silhuett, tilfeldig datasky": t["silhuett_null"], "Del nær klyngegrensa": t["grense_del"]}
        for x in [f for f in les("manifest.json")["figurar"] if f["id"] == "f18"][0]["tal"]:
            self.assertEqual(x.get("kjelde"), "kart")
            self.assertEqual(x["verdi"], sett[x["etikett"]])

    def test_every_finding_group_has_a_figure(self):
        """The eight dimensions and the five new-question lenses are all shown."""
        m = les("manifest.json")
        brukt = {fid for f in m["figurar"] for fid in f["finn"]}
        for dim in ("populasjon", "vekst", "kanalar", "siteringar", "tema", "omgrep", "kunnskapsformer", "teorielement"):
            self.assertTrue(any(b.startswith(dim + "-") for b in brukt), dim)
        for q in fasit()["nye_sporsmal"]:
            self.assertIn(q["id"], brukt)

    def test_arithmetic_of_the_series(self):
        # the series add up to the headline totals they sit under
        f01 = fig("f01")
        n = {x["id"]: x["n"] for x in f01["nodar"]}
        self.assertEqual(n["hent_oa"], n["ut"] + n["liste"] + n["andre"])
        self.assertEqual(n["hent_ark"], n["fjerna"] + n["ark_att"])
        self.assertEqual(n["reg"], 6432)
        self.assertEqual(n["liste"] + n["andre"] + n["ark_att"], n["reg"])
        self.assertEqual(n["ft"] + n["utan"], n["reg"])
        f02 = fig("f02")
        self.assertEqual(sum(f02["oa"]), 4694)
        self.assertEqual(sum(f02["ark"]), 1738)
        self.assertEqual(sum(f02["per_oa"]), 4694)
        self.assertEqual(sum(f02["typ_sum_oa"]), 4694)
        self.assertEqual(sum(f02["typ_sum_ark"]), 1738)
        self.assertEqual(f02["per_oa"][:6], [69, 102, 305, 923, 1201, 1549])
        f05 = fig("f05")
        self.assertEqual(round(sum(sum(v) for v in f05["oa"].values())), sum(f02["oa"][f02["ar"].index(2000):]))
        for i in range(7):
            s = sum(f05["del_oa"][k][i] for k in f05["del_oa"])
            self.assertAlmostEqual(s, 100.0, delta=0.35)
            s2 = sum(f05["del_samla"][k][i] for k in f05["del_samla"])
            self.assertAlmostEqual(s2, 100.0, delta=0.45)
        f06 = fig("f06")
        for p in f06["per"]:
            self.assertAlmostEqual(p["ein"] + p["to"] + p["tre"] + p["fire"], 100.0, delta=0.25)
        f14 = fig("f14")
        self.assertEqual(f14["sum"], 79794)
        self.assertEqual(f14["n"], 4694)
        self.assertEqual(f14["x"][0], 0.0)
        self.assertEqual(f14["x"][-1], 1.0)
        self.assertEqual(f14["y"][-1], 1.0)
        for k in ("alle", "liste", "andre"):
            c = fig("f10")[k]
            self.assertEqual(c["y"][-1], 1.0)
            self.assertTrue(all(b >= a for a, b in zip(c["y"], c["y"][1:])))
            self.assertTrue(all(y <= x + 1e-9 for x, y in zip(c["x"], c["y"])), k)
        f16 = fig("f16")
        self.assertEqual(f16["til_laget"] + f16["til_utanfor"] + f16["utanfor_tabellen"], f16["sum"])
        self.assertEqual(f16["sum"], 109116)

    def test_array_shapes_for_the_pictures(self):
        f09 = fig("f09")
        for k in ("forfattar", "institusjon"):
            d = f09[k]
            n = len(d["x"])
            self.assertEqual(n, d["noder"])
            self.assertEqual(len(d["y"]), n)
            self.assertEqual(len(d["n"]), n)
            self.assertEqual(len(d["kant"]), 2 * d["kantar"])
            self.assertTrue(all(0 <= v < n for v in d["kant"]))
            self.assertTrue(all(0 <= v <= f09["skala"] for v in d["x"] + d["y"]))
        self.assertEqual(f09["forfattar"]["noder"], 6033)
        land = f09["land"]
        self.assertEqual(len(land["k"]), len(land["x"]))
        self.assertTrue(all(a < len(land["k"]) and b < len(land["k"]) for a, b, _ in land["kant"]))
        f18 = fig("f18")
        n = len(f18["x"])
        self.assertEqual(n, 6432)
        for k in ("y", "k", "f"):
            self.assertEqual(len(f18[k]), n)
        self.assertEqual(sorted(set(f18["k"])), [c["id"] for c in f18["klynger"]])
        f13 = fig("f13")
        nn = len(f13["noder"])
        self.assertTrue(all(0 <= a < nn and 0 <= b < nn for a, b, _, _ in f13["kantar"]))
        self.assertEqual(f13["topp100_inne"], 15)
        for n in f13["noder"]:
            self.assertEqual("id" in n, bool(n["inne"]), n["namn"])


class TestNewQuestions(unittest.TestCase):
    """The expected-range strips: the expectation is the one written before the measurement."""

    @classmethod
    def setUpClass(cls):
        cls.f = fig("f26")
        cls.fasit = {q["id"]: q for q in fasit()["nye_sporsmal"]}

    def test_fifteen_questions_with_the_verified_outcome(self):
        self.assertEqual(len(self.f["sporsmal"]), 15)
        for q in self.f["sporsmal"]:
            self.assertEqual(q["utfall"], self.fasit[q["id"]]["held"], q["id"])
        tel = {"held": 0, "failed": 0, "undecided": 0}
        for q in self.f["sporsmal"]:
            tel[q["utfall"]] += 1
        self.assertEqual(tel, {"held": 4, "failed": 8, "undecided": 3})
        self.assertEqual(self.f["utfall"], tel)

    def test_expected_bounds_and_marks_are_in_the_texts(self):
        for q in self.f["sporsmal"]:
            fq = self.fasit[q["id"]]
            for r in q["rader"]:
                v = r["venta"]
                for grense in (v["lo"], v["hi"]):
                    if grense is not None and not r.get("venta_ord"):
                        self.assertTrue(er_med_ord(grense, fq["expected_before"]), (q["id"], r["namn"], grense))
                if r.get("avleidd"):
                    continue
                for m in r["obs"]:
                    stilt = (m.get("lo"), m.get("hi")) if m.get("mid") else (m["v"], m.get("lo"), m.get("hi"))
                    for x in stilt:
                        if x is not None:
                            self.assertTrue(er_med_ord(x, fq["result"]), (q["id"], r["namn"], x))

    def test_verdict_rule_is_recomputed(self):
        for q in self.f["sporsmal"]:
            for r in q["rader"]:
                lo, hi = r["venta"]["lo"], r["venta"]["hi"]
                a, b = r["akse"]
                band = (lo - 5, lo + 5) if r["venta"]["tilnaerma"] else (a if lo is None else lo, b if hi is None else hi)
                d = []
                for m in r["obs"]:
                    v0, v1 = m.get("lo", m["v"]), m.get("hi", m["v"])
                    d.append(1 if (v0 >= band[0] and v1 <= band[1]) else (-1 if (v1 < band[0] or v0 > band[1]) else 0))
                if all(x == 1 for x in d):
                    dom = "treff"
                elif all(x == -1 for x in d) or (r.get("modus") == "alle" and any(x == -1 for x in d)):
                    dom = "bom"
                else:
                    dom = "open"
                self.assertEqual(r["dom"], dom, (q["id"], r["namn"]))
                self.assertTrue(band[0] <= band[1])
                for m in r["obs"]:
                    self.assertTrue(a <= m.get("lo", m["v"]) and m.get("hi", m["v"]) <= b, (q["id"], r["namn"], m))

    def test_strips_per_question(self):
        for q in self.f["sporsmal"]:
            self.assertGreaterEqual(len(q["rader"]), 2)
            self.assertLessEqual(len(q["rader"]), 6)
        self.assertEqual(sum(len(q["rader"]) for q in self.f["sporsmal"]), 47)
        self.assertEqual(sum(self.f["rader"].values()), 47)


@unittest.skipUnless(RAW_SQLITE.exists(), "databasen finst ikkje (CI)")
class TestAgainstDatabase(unittest.TestCase):
    """Series recomputed straight from the database, independent of metavis."""

    @classmethod
    def setUpClass(cls):
        import sqlite3
        cls.con = sqlite3.connect("file:%s?mode=ro" % RAW_SQLITE.as_posix(), uri=True)

    def test_counts(self):
        c = self.con
        self.assertEqual(c.execute("select count(*) from works").fetchone()[0], 24812)
        self.assertEqual(c.execute("select count(*) from works where in_scope=1").fetchone()[0], 4694)
        liste = c.execute("select count(*) from works where in_scope=1 and decision='Dedicated design theory and research venue'").fetchone()[0]
        n = {x["id"]: x["n"] for x in fig("f01")["nodar"]}
        self.assertEqual(n["liste"], liste)
        self.assertEqual(n["hent_oa"], 24812)
        self.assertEqual(n["ut"], 20118)

    def test_year_series(self):
        f02 = fig("f02")
        for y, k in zip(f02["ar"], f02["oa"]):
            got = self.con.execute("select count(*) from works where in_scope=1 and year=?", (y,)).fetchone()[0]
            self.assertEqual(got, k, y)

    def test_citations(self):
        cit = [r[0] or 0 for r in self.con.execute("select citations from works where in_scope=1")]
        f14 = fig("f14")
        self.assertEqual(sum(cit), f14["sum"])
        self.assertEqual(sum(1 for c in cit if c == 0), f14["usiterte"])
        self.assertEqual(max(cit), f14["maks"])

    def test_authors(self):
        n = self.con.execute("select count(distinct a.author_id) from authorships a join works w on w.id=a.work_id "
                             "where w.in_scope=1 and a.author_id is not null and a.author_id!=''").fetchone()[0]
        self.assertEqual(n, fig("f08")["forf_n"])
        self.assertEqual(n, fig("f09")["forfattar"]["noder"])


class TestRound1Fixes(unittest.TestCase):
    """Numbers that the pictures must state with their denominator and layer."""

    def test_skilja5_shows_both_denominators(self):
        q = [x for x in fig("f26")["sporsmal"] if x["id"] == "skilja-5"][0]
        rad = q["rader"][0]
        self.assertEqual([m["v"] for m in rad["obs"]], [95.9, 65.9])
        self.assertIn("4 080", rad["merknad"])
        self.assertEqual(rad["dom"], "open")  # one mark inside the expected range, one outside
        self.assertEqual(q["utfall"], "held")
        for x in fig("f26")["sporsmal"]:
            self.assertTrue(x["nemnar"].strip(), x["id"])

    def test_language_flag_is_split_by_layer(self):
        f18 = fig("f18")
        s = f18["sprak"]
        self.assertEqual((s["oa"], s["ark"]), (203, 193))
        self.assertEqual(s["n_oa"] + s["n_ark"], 6432)
        flagged = sum(1 for v in f18["f"] if v & 4)
        self.assertEqual(flagged, s["oa"] + s["ark"])
        self.assertEqual(sum(f18["lag"]), s["n_ark"])
        for k in ("land", "per", "lag"):
            self.assertEqual(len(f18[k]), 6432)

    def test_rank_series_matches_stated_shares(self):
        r = fig("f05")["rang"]
        for k, v in r["del"].items():
            self.assertEqual(len(v), 3)
        for j in range(3):
            self.assertAlmostEqual(sum(r["del"][k][j] for k in r["del"]), 100.0, delta=0.4)
        # the verified shares for 2020-24: fractional credit and author countries only
        self.assertEqual([r["del"]["NO"][1], r["del"]["FI"][1]], [22.4, 19.5])
        self.assertEqual([r["del"]["NO"][2], r["del"]["FI"][2]], [18.9, 20.4])


class TestHelpers(unittest.TestCase):
    def test_number_extraction(self):
        self.assertEqual(sorted(tal_i_tekst("6 432 av 24 812 (87,8 %) og 0,0737")), [0.0737, 87.8, 6432.0, 24812.0])
        self.assertTrue(er_med(87.8, "87,8 %"))
        self.assertTrue(er_med(5, "om lag 5 poeng"))
        self.assertFalse(er_med(5.1, "om lag 5 poeng"))
        self.assertTrue(er_med(-10.9, "skilnad -10.9 poeng"))
        self.assertTrue(er_med(2010, "frå 2010 til 2014"))
        self.assertFalse(er_med(2014, "frå 2010 til 2 015"))

    def test_lorenz_and_gini(self):
        x, y = metavis.lorenz([1, 1, 1, 1], 10)
        self.assertEqual(x[-1], 1.0)
        self.assertEqual(y[-1], 1.0)
        self.assertAlmostEqual(metavis.gini([5, 5, 5, 5]), 0.0)
        self.assertGreater(metavis.gini([1, 1, 1, 97]), 0.7)

    def test_period_rule(self):
        self.assertEqual(metavis.periode(1999), 0)
        self.assertEqual(metavis.periode(2000), 1)
        self.assertEqual(metavis.periode(2024), 5)
        self.assertEqual(metavis.periode(2026), 6)


if __name__ == "__main__":
    unittest.main()
