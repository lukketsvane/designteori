"""Tests for the figure data in docs/data/meta/ (built by designteori/metavis.py).

The tests read the published files and the copies of the verified findings: tests/fixtures/funn-samla.json (round 1:
76 findings, 75 of them checked again; the corrected claim for adjusted ones; 15 new questions with the expectation fixed
before the measurement) and tests/fixtures/runde2.json (round 2: 90 findings, one refuted; nine new questions). The page
shows 18 figures; a figure is one or more parts (d01 to d36) that answer the same question, and the data of a figure is
{part id: part data}. Checks that need the private database are skipped when it is absent (CI has no database).
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
FIXTURE2 = Path(__file__).resolve().parent / "fixtures" / "runde2.json"
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


def fasit2():
    if "fasit2" not in _cache:
        _cache["fasit2"] = json.loads(FIXTURE2.read_text(encoding="utf-8"))
    return _cache["fasit2"]


def kravtekst(finn_id: str) -> str:
    """The text a headline is checked against: the (corrected) claim, or the question with expectation and result."""
    for f in (fasit(), fasit2()):
        for x in f["funn"]:
            if x["id"] == finn_id:
                return x["claim"]
        for q in f["nye_sporsmal"]:
            if q["id"] == finn_id:
                return " ".join([q["question"], q["expected_before"], q["result"]])
    raise KeyError(finn_id)


def utvida_tekst(finn_id: str) -> str:
    """The claim, and for a confirmed round-2 finding also the number field the verifier checked it against. An adjusted
    finding is only read through its corrected claim."""
    for x in fasit2()["funn"]:
        if x["id"] == finn_id:
            return x["claim"] + (" " + x.get("numbers", "") if x["status"] == "confirmed" else "")
    return kravtekst(finn_id)


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
    """The data of a figure: {part id: part data}."""
    m = les("manifest.json")
    for f in m["figurar"]:
        if f["id"] == fig_id:
            return les(f["fil"])["figurar"][fig_id]
    raise KeyError(fig_id)


def part(part_id: str) -> dict:
    """The data of one part (d01 to d36), found through the figure that holds it."""
    m = les("manifest.json")
    for f in m["figurar"]:
        if part_id in [d["id"] for d in f["delar"]]:
            return les(f["fil"])["figurar"][f["id"]][part_id]
    raise KeyError(part_id)


PARTS = ["d%02d" % i for i in range(1, 37)]
SPORSMAL_ID = re.compile(r"(eininga|skilja|tida|grenser)-\d")


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
        # about 18 figures, in the order of the page
        self.assertGreaterEqual(len(ids), 16)
        self.assertLessEqual(len(ids), 20)
        self.assertEqual(ids, ["f%02d" % i for i in range(1, len(ids) + 1)])
        # every part is in exactly one figure, and the data of a figure holds exactly its parts
        brukt = [d["id"] for f in m["figurar"] for d in f["delar"]]
        self.assertEqual(sorted(brukt), PARTS)
        for f in m["figurar"]:
            self.assertIn(f["seksjon"], SEKSJONAR)
            self.assertEqual(f["fil"], f["seksjon"] + ".json")
            self.assertEqual(sorted(les(f["fil"])["figurar"][f["id"]]), sorted(d["id"] for d in f["delar"]), f["id"])
            for k in ("tittel", "sporsmal", "form", "nemnar"):
                self.assertTrue(f[k].strip(), (f["id"], k))
            self.assertEqual(f["nemnar"], f["delar"][0]["nemnar"])
            # every part carries its denominator and layer in one short line
            for d in f["delar"]:
                self.assertLessEqual(len(d["nemnar"]), 260, d["id"])
                self.assertTrue(re.search(r"\d", d["nemnar"]), d["id"])
            if f["id"] == "f11":
                # the map's own series: none of the verified findings states it, so none is cited
                self.assertEqual(f["finn"], [])
                self.assertTrue(all(t.get("kjelde") == "kart" for t in f["tal"]))
            else:
                self.assertTrue(f["finn"], f["id"])
            self.assertTrue(f["tal"], f["id"])
            for t in f["tal"]:
                self.assertIn(t["del"], [d["id"] for d in f["delar"]])
        # no figure is in a section file without being in the manifest
        for s in SEKSJONAR:
            d = les(s + ".json")
            self.assertEqual(d["format"], metavis.FORMAT)
            self.assertEqual(d["seksjon"], s)
            for fid in d["figurar"]:
                self.assertIn(fid, ids)

    def test_page_lists_the_same_figures(self):
        """The html has one figure per manifest entry, in the same order, and the scripts the page needs."""
        html = (DOCS_DATA_DIR.parent / "funn" / "index.html").read_text(encoding="utf-8")
        ids = re.findall(r'data-fig="(f\d\d)"', html)
        self.assertEqual(ids, [f["id"] for f in les("manifest.json")["figurar"]])
        for js in ("funn.js", "funn-h.js", "funn-a.js", "funn-nett.js", "funn-b.js", "funn-c.js", "funn-d.js", "funn-e.js", "funn-samla.js"):
            self.assertIn('src="%s"' % js, html)
            self.assertTrue((DOCS_DATA_DIR.parent / "funn" / js).exists(), js)
        samla = (DOCS_DATA_DIR.parent / "funn" / "funn-samla.js").read_text(encoding="utf-8")
        for f in les("manifest.json")["figurar"]:
            self.assertIn("F.fig.%s = F.sam(" % f["id"], samla)
            for d in f["delar"]:
                self.assertIn('"%s"' % d["id"], samla[samla.index("F.fig.%s = " % f["id"]):].split("\n")[0])

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
        for n in part("d13")["noder"]:
            self.assertLessEqual(len(n["tittel"]), 110)
        self.assertNotIn("namn", part("d09")["forfattar"])


class TestHeadlines(unittest.TestCase):
    """Every headline number agrees with the verified finding it cites, within rounding."""

    def test_findings_used_are_verified(self):
        status = {x["id"]: x["status"] for x in fasit()["funn"]}
        status.update({q["id"]: q["status"] for q in fasit()["nye_sporsmal"]})
        status.update({x["id"]: x["status"] for x in fasit2()["funn"]})
        status.update({q["id"]: q["status"] for q in fasit2()["nye_sporsmal"]})
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
        # the unverifiable round-1 finding and the refuted round-2 finding are never used
        self.assertNotIn("omgrep-6", brukt)
        self.assertNotIn("dekning-6", brukt)
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
                if not er_med(t["verdi"], utvida_tekst(t["finn"])):
                    feil.append((f["id"], t["finn"], t["etikett"], t["verdi"]))
        self.assertGreater(n, 600)
        self.assertEqual(feil, [], "tal som ikkje finst i det verifiserte funnet")

    def test_adjusted_findings_are_read_through_the_corrected_claim_only(self):
        """A headline from an adjusted finding must be in the corrected claim itself, not in the number field."""
        adj = {x["id"] for x in fasit2()["funn"] if x["status"] == "adjusted"} | {x["id"] for x in fasit()["funn"] if x["status"] == "adjusted"}
        feil = []
        for f in les("manifest.json")["figurar"]:
            for t in f["tal"]:
                if t.get("finn") in adj and not er_med(t["verdi"], kravtekst(t["finn"])):
                    feil.append((f["id"], t["finn"], t["etikett"], t["verdi"]))
        self.assertEqual(feil, [])

    def test_site_numbers_agree_with_kart_json(self):
        kart = json.loads((DOCS_DATA_DIR / "klynger" / "kart.json").read_text(encoding="utf-8"))
        t = kart["tal"]
        d18 = part("d18")
        self.assertEqual(len(d18["x"]), t["verk"])
        self.assertEqual(d18["silhuett"], t["silhuett"])
        self.assertEqual(d18["silhuett_null"], t["silhuett_null"])
        self.assertEqual(d18["grense_del"], t["grense_del"])
        self.assertEqual(len(d18["klynger"]), t["klynger"])
        sett = {"Verk i kartet": t["verk"], "Klynger i kartet": t["klynger"], "Silhuett": t["silhuett"],
                "Silhuett, tilfeldig datasky": t["silhuett_null"], "Del nær klyngegrensa": t["grense_del"]}
        for x in [f for f in les("manifest.json")["figurar"] if f["id"] == "f11"][0]["tal"]:
            self.assertEqual(x.get("kjelde"), "kart")
            self.assertEqual(x["verdi"], sett[x["etikett"]])

    def test_every_finding_group_has_a_figure(self):
        """The eight round-1 dimensions, the ten round-2 groups and all 24 new questions are shown."""
        m = les("manifest.json")
        brukt = {fid for f in m["figurar"] for fid in f["finn"]}
        for dim in ("populasjon", "vekst", "kanalar", "siteringar", "tema", "omgrep", "kunnskapsformer", "teorielement"):
            self.assertTrue(any(b.startswith(dim + "-") for b in brukt), dim)
        for dim in ("arkiv", "dekning", "grense", "ikkjeforsking", "panel", "praksis", "samanlikning", "sprak", "tilgang", "vekting"):
            self.assertTrue(any(b.startswith(dim + "-") for b in brukt), dim)
        for q in fasit()["nye_sporsmal"] + fasit2()["nye_sporsmal"]:
            self.assertIn(q["id"], brukt)

    def test_arithmetic_of_the_series(self):
        # the series add up to the headline totals they sit under
        d01 = part("d01")
        n = {x["id"]: x["n"] for x in d01["nodar"]}
        self.assertEqual(n["hent_oa"], n["ut"] + n["liste"] + n["andre"])
        self.assertEqual(n["hent_ark"], n["fjerna"] + n["ark_att"])
        self.assertEqual(n["reg"], 6432)
        self.assertEqual(n["liste"] + n["andre"] + n["ark_att"], n["reg"])
        self.assertEqual(n["ft"] + n["utan"], n["reg"])
        d02 = part("d02")
        self.assertEqual(sum(d02["oa"]), 4694)
        self.assertEqual(sum(d02["ark"]), 1738)
        self.assertEqual(sum(d02["per_oa"]), 4694)
        self.assertEqual(sum(d02["typ_sum_oa"]), 4694)
        self.assertEqual(sum(d02["typ_sum_ark"]), 1738)
        self.assertEqual(d02["per_oa"][:6], [69, 102, 305, 923, 1201, 1549])
        # the archive type "thesis" (177) is 46 doctoral and 131 master theses
        self.assertEqual(d02["typ_sum_ark"][3], d02["avhandling_ark"]["thesis"])
        self.assertEqual(d02["avhandling_ark"]["doktor"] + d02["avhandling_ark"]["master"], 177)
        d05 = part("d05")
        self.assertEqual(round(sum(sum(v) for v in d05["oa"].values())), sum(d02["oa"][d02["ar"].index(2000):]))
        for i in range(7):
            s = sum(d05["del_oa"][k][i] for k in d05["del_oa"])
            self.assertAlmostEqual(s, 100.0, delta=0.35)
            s2 = sum(d05["del_samla"][k][i] for k in d05["del_samla"])
            self.assertAlmostEqual(s2, 100.0, delta=0.45)
        d06 = part("d06")
        for p in d06["per"]:
            self.assertAlmostEqual(p["ein"] + p["to"] + p["tre"] + p["fire"], 100.0, delta=0.25)
        d14 = part("d14")
        self.assertEqual(d14["sum"], 79794)
        self.assertEqual(d14["n"], 4694)
        self.assertEqual(d14["x"][0], 0.0)
        self.assertEqual(d14["x"][-1], 1.0)
        self.assertEqual(d14["y"][-1], 1.0)
        for k in ("alle", "liste", "andre"):
            c = part("d10")[k]
            self.assertEqual(c["y"][-1], 1.0)
            self.assertTrue(all(b >= a for a, b in zip(c["y"], c["y"][1:])))
            self.assertTrue(all(y <= x + 1e-9 for x, y in zip(c["x"], c["y"])), k)
        d16 = part("d16")
        self.assertEqual(d16["til_laget"] + d16["til_utanfor"] + d16["utanfor_tabellen"], d16["sum"])
        self.assertEqual(d16["sum"], 109116)

    def test_array_shapes_for_the_pictures(self):
        d09 = part("d09")
        for k in ("forfattar", "institusjon"):
            d = d09[k]
            n = len(d["x"])
            self.assertEqual(n, d["noder"])
            self.assertEqual(len(d["y"]), n)
            self.assertEqual(len(d["n"]), n)
            self.assertEqual(len(d["kant"]), 2 * d["kantar"])
            self.assertTrue(all(0 <= v < n for v in d["kant"]))
            self.assertTrue(all(0 <= v <= d09["skala"] for v in d["x"] + d["y"]))
        self.assertEqual(d09["forfattar"]["noder"], 6033)
        land = d09["land"]
        self.assertEqual(len(land["k"]), len(land["x"]))
        self.assertTrue(all(a < len(land["k"]) and b < len(land["k"]) for a, b, _ in land["kant"]))
        d18 = part("d18")
        n = len(d18["x"])
        self.assertEqual(n, 6432)
        for k in ("y", "k", "f"):
            self.assertEqual(len(d18[k]), n)
        self.assertEqual(sorted(set(d18["k"])), [c["id"] for c in d18["klynger"]])
        d13 = part("d13")
        nn = len(d13["noder"])
        self.assertTrue(all(0 <= a < nn and 0 <= b < nn for a, b, _, _ in d13["kantar"]))
        self.assertEqual(d13["topp100_inne"], 15)
        for n in d13["noder"]:
            self.assertEqual("id" in n, bool(n["inne"]), n["namn"])


class TestNewQuestions(unittest.TestCase):
    """The expected-range strips: the expectation is the one written before the measurement. 15 questions from round 1
    and 9 from round 2, drawn as two rows of the same figure."""

    @classmethod
    def setUpClass(cls):
        cls.f = part("d26")
        cls.fasit = {q["id"]: q for q in fasit()["nye_sporsmal"]}
        cls.fasit.update({q["id"]: q for q in fasit2()["nye_sporsmal"]})

    def test_24_questions_with_the_verified_outcome(self):
        self.assertEqual(len(self.f["sporsmal"]), 24)
        self.assertEqual([q["runde"] for q in self.f["sporsmal"]], [1] * 15 + [2] * 9)
        for q in self.f["sporsmal"]:
            self.assertEqual(q["utfall"], self.fasit[q["id"]]["held"], q["id"])
            if q["runde"] == 2:
                self.assertIn(q["id"].split("-")[0], ("grenser", "skilja", "tida"))
        tel = {"held": 0, "failed": 0, "undecided": 0}
        tel2 = dict(tel)
        for q in self.f["sporsmal"]:
            tel[q["utfall"]] += 1
            if q["runde"] == 2:
                tel2[q["utfall"]] += 1
        self.assertEqual(tel, {"held": 5, "failed": 11, "undecided": 8})
        self.assertEqual(tel2, {"held": 1, "failed": 3, "undecided": 5})
        self.assertEqual(self.f["utfall"], tel)
        self.assertEqual(self.f["runde2"], tel2)
        # the source's own label is kept where it says more than the verdict (delvis, som skilnad i grad)
        etikett = {q["id"]: q.get("etikett") for q in self.f["sporsmal"] if q.get("etikett")}
        self.assertEqual(etikett, {"skilja-7": "delvis", "skilja-8": "som skilnad i grad"})

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
            self.assertLessEqual(len(q["rader"]), 7)
            self.assertTrue(q["nemnar"].strip(), q["id"])
            if q["runde"] == 2:
                self.assertTrue(re.search(r"\d", q["nemnar"]), q["id"])
        self.assertEqual(sum(len(q["rader"]) for q in self.f["sporsmal"] if q["runde"] == 1), 47)
        self.assertEqual(sum(len(q["rader"]) for q in self.f["sporsmal"] if q["runde"] == 2), 47)
        self.assertEqual(sum(self.f["rader"].values()), 94)


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
        n = {x["id"]: x["n"] for x in part("d01")["nodar"]}
        self.assertEqual(n["liste"], liste)
        self.assertEqual(n["hent_oa"], 24812)
        self.assertEqual(n["ut"], 20118)

    def test_year_series(self):
        d02 = part("d02")
        for y, k in zip(d02["ar"], d02["oa"]):
            got = self.con.execute("select count(*) from works where in_scope=1 and year=?", (y,)).fetchone()[0]
            self.assertEqual(got, k, y)

    def test_citations(self):
        cit = [r[0] or 0 for r in self.con.execute("select citations from works where in_scope=1")]
        d14 = part("d14")
        self.assertEqual(sum(cit), d14["sum"])
        self.assertEqual(sum(1 for c in cit if c == 0), d14["usiterte"])
        self.assertEqual(max(cit), d14["maks"])

    def test_authors(self):
        n = self.con.execute("select count(distinct a.author_id) from authorships a join works w on w.id=a.work_id "
                             "where w.in_scope=1 and a.author_id is not null and a.author_id!=''").fetchone()[0]
        self.assertEqual(n, part("d08")["forf_n"])
        self.assertEqual(n, part("d09")["forfattar"]["noder"])


class TestRound1Fixes(unittest.TestCase):
    """Numbers that the pictures must state with their denominator and layer."""

    def test_skilja5_shows_both_denominators(self):
        q = [x for x in part("d26")["sporsmal"] if x["id"] == "skilja-5"][0]
        rad = q["rader"][0]
        self.assertEqual([m["v"] for m in rad["obs"]], [95.9, 65.9])
        self.assertIn("4 080", rad["merknad"])
        self.assertEqual(rad["dom"], "open")  # one mark inside the expected range, one outside
        self.assertEqual(q["utfall"], "held")
        for x in part("d26")["sporsmal"]:
            self.assertTrue(x["nemnar"].strip(), x["id"])

    def test_language_flag_is_split_by_layer(self):
        d18 = part("d18")
        s = d18["sprak"]
        self.assertEqual((s["oa"], s["ark"]), (203, 193))
        self.assertEqual(s["n_oa"] + s["n_ark"], 6432)
        flagged = sum(1 for v in d18["f"] if v & 4)
        self.assertEqual(flagged, s["oa"] + s["ark"])
        self.assertEqual(sum(d18["lag"]), s["n_ark"])
        for k in ("land", "per", "lag"):
            self.assertEqual(len(d18[k]), 6432)

    def test_rank_series_matches_stated_shares(self):
        r = part("d05")["rang"]
        for k, v in r["del"].items():
            self.assertEqual(len(v), 3)
        for j in range(3):
            self.assertAlmostEqual(sum(r["del"][k][j] for k in r["del"]), 100.0, delta=0.4)
        # the verified shares for 2020-24: fractional credit and author countries only
        self.assertEqual([r["del"]["NO"][1], r["del"]["FI"][1]], [22.4, 19.5])
        self.assertEqual([r["del"]["NO"][2], r["del"]["FI"][2]], [18.9, 20.4])


class TestRunde2(unittest.TestCase):
    """What the page says about itself and about which population a number belongs to."""

    def test_hero_counts_of_the_findings(self):
        funn = les("manifest.json")["funn"]
        s1 = [x["status"] for x in fasit()["funn"]]
        s2 = [x["status"] for x in fasit2()["funn"]]
        self.assertEqual(funn["totalt"], len(s1) + len(s2))
        self.assertEqual(funn["stadfesta"], s1.count("confirmed") + s2.count("confirmed"))
        self.assertEqual(funn["retta"], s1.count("adjusted") + s2.count("adjusted"))
        self.assertEqual(funn["ukontrollerbar"], s1.count("unverifiable") + s2.count("unverifiable"))
        self.assertEqual(funn["refuta"], s1.count("refuted") + s2.count("refuted"))
        self.assertEqual(funn["kontrollerte"], funn["stadfesta"] + funn["retta"])
        self.assertEqual((funn["totalt"], funn["kontrollerte"], funn["stadfesta"], funn["retta"]), (166, 164, 80, 84))
        self.assertEqual(funn["sporsmal"], len(fasit()["nye_sporsmal"]) + len(fasit2()["nye_sporsmal"]))
        self.assertEqual(funn["sporsmal"], 24)
        alle = [x["id"] for x in fasit()["funn"] + fasit2()["funn"]]
        status = {x["id"]: x["status"] for x in fasit()["funn"] + fasit2()["funn"]}
        brukt = {fid for f in les("manifest.json")["figurar"] for fid in f["finn"] if not SPORSMAL_ID.match(fid)}
        self.assertTrue(brukt <= set(alle))
        self.assertEqual(funn["teikna"], len(brukt))
        # what is not drawn: the unverifiable and the refuted finding, and the ones no figure needs
        ikkje = sorted(set(alle) - brukt)
        self.assertIn("omgrep-6", ikkje)
        self.assertIn("dekning-6", ikkje)
        self.assertEqual(status["omgrep-6"], "unverifiable")
        self.assertEqual(status["dekning-6"], "refuted")
        self.assertEqual(ikkje, UTEN_FIGUR)

    def test_figures_state_their_layer_and_population(self):
        nem = {d["id"]: d["nemnar"] for f in les("manifest.json")["figurar"] for d in f["delar"]}
        self.assertIn("øvre grense", nem["d01"])
        self.assertIn("6 236", nem["d01"])
        self.assertIn("22 lesbare av 23 CC-verk", nem["d25"])
        self.assertNotIn("23 CC-verk (52", nem["d25"])
        self.assertIn("i heile tabellen", nem["d08"])
        js = (DOCS_DATA_DIR.parent / "funn" / "funn-a.js").read_text(encoding="utf-8")
        self.assertIn("har minst fem verk i heile tabellen (", js)   # the panel states its own base: 1 390 of 6 033, 24 812 rows
        self.assertIn("delmengd av dei 3 272", nem["d19"])
        self.assertIn("3 272", nem["d25"])
        stripe = [r["namn"] for q in part("d26")["sporsmal"] if q["id"] == "eininga-4" for r in q["rader"]]
        self.assertTrue(any("OpenAlex-laget" in n and "arkivlaget 95" in n for n in stripe))
        # round 2 figures name their layer and population
        self.assertIn("4 694", nem["d28"])
        self.assertIn("3 978", nem["d30"])
        self.assertIn("1 738", nem["d29"])

    def test_forfattar_populations_in_d08(self):
        d08 = part("d08")
        self.assertEqual(d08["tabell_rader"], 24812)
        self.assertEqual(d08["forf_n"], 6033)
        self.assertEqual(d08["forf_ge5"], 441)           # at least five works in scope (4 694 works)
        self.assertEqual(d08["grense"]["n_ge5"], 1390)   # at least five works anywhere in the table
        self.assertEqual(d08["grense"]["rein_pct"], 2.4)
        self.assertEqual(d08["grense"]["under_halv_pct"], 67.4)

    def test_d25_counts_texts_not_registered_works(self):
        u = part("d25")["utval"]
        self.assertEqual((u["lesbare"], u["v03"]), (22, 23))
        self.assertIn("22 CC-tekstar", kravtekst("teorielement-3"))
        self.assertEqual(part("d25")["kausal"]["v03"][3], 52)

    def test_cluster_letter_and_number_are_the_same_cluster(self):
        # tema-6 calls it "klynge 8" (279 works); the page calls it I (the ninth letter, id 8). Never both on screen.
        kl = {k["id"]: k for k in part("d20")["klynger"]}
        self.assertEqual(len(kl), 10)
        self.assertEqual("ABCDEFGHIJ"[8], "I")
        self.assertEqual(kl[8]["n"], part("d19")["klynge8"]["n"])
        self.assertEqual(kl[8]["n"], 279)
        self.assertIn("Klynge 8", kravtekst("tema-6"))
        self.assertIn("279", kravtekst("tema-6"))

    def test_d05_archive_layer_makes_norway_largest(self):
        d = part("d05")
        i = d["periodar"].index("2020–24")
        sm = {k: v[i] for k, v in d["del_samla"].items()}
        self.assertEqual(max(sm, key=sm.get), "NO")
        self.assertEqual((sm["NO"], sm["DK"], sm["SE"], sm["FI"]), (34.5, 25.7, 21.4, 15.4))
        self.assertIn("34,5 %", kravtekst("vekst-4"))
        oa = d["rang"]["del"]
        for j in range(3):
            self.assertEqual(sorted(oa, key=lambda k: -oa[k][j])[:2], ["DK", "SE"])
        # round 2: without the whitelist Norway falls behind Finland, and Finland's archive zero is an extraction choice
        self.assertEqual(d["utan_kvitlista"], {"NO": 14.2, "FI": 20.9})
        self.assertIn("14,2", kravtekst("grense-4"))
        self.assertEqual(part("d29")["land"]["FI"], 0)
        self.assertEqual(part("d29")["land"]["uttak_finland"], 22)

    def test_round1_corrections_by_round2(self):
        """The corrections the report lists for round-1 numbers are in the figures."""
        d = part("d19")
        self.assertEqual(d["utval_sprak"][0], ["norsk", 97.2])        # Norwegian-language works only
        self.assertEqual(d["nordisk_samla"], [83.3, 169, 203])        # all Nordic-language works
        self.assertIn("83,3 %", kravtekst("vekting-7"))
        d02 = part("d02")["avhandling_ark"]
        self.assertEqual((d02["thesis"], d02["doktor"], d02["master"]), (177, 46, 131))
        self.assertIn("46 er doktoravhandlingar", utvida_tekst("tilgang-8"))
        self.assertIn("131 masteroppg", utvida_tekst("tilgang-8"))
        ark = {a["namn"]: a for a in part("d29")["arkiv"]}
        self.assertEqual(ark["Nordes"]["n"], 408)     # 380 Nordes contributions and 28 DRS-prefix works
        self.assertIn("380", kravtekst("arkiv-1"))
        d27 = part("d27")
        self.assertEqual((d27["poster"], d27["ulike"]["m"], d27["ulike"]["lo"], d27["ulike"]["hi"]), (6432, 6236, 6215, 6428))
        self.assertEqual(d27["dublettar"]["oa"] + d27["dublettar"]["ark"] + d27["dublettar"]["begge"], d27["dublettar"]["sum"])
        self.assertEqual(d27["poster"] - d27["ulike"]["m"], d27["dublettar"]["sum"])
        # the refuted Nordes validation (623 entries) is replaced by about 665
        self.assertEqual(d27["lister"][0]["n"], 665)
        self.assertEqual(d27["lister"][0]["pct"], 92)

    def test_page_text(self):
        html = (DOCS_DATA_DIR.parent / "funn" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("76</b>", html)
        self.assertNotIn("funn bak biletet", html)
        self.assertIn("om lag 6&#8239;236 ulike verk", html)
        self.assertIn("registrerte postar", html)
        self.assertIn("Tekstklynger, bokstav A–J", html)
        self.assertIn("Kartklynger, tal 1–8", html)
        f11 = html[html.index('id="f11"'):html.index('id="f12"')]
        self.assertEqual(f11.count("åtte klynger"), 1)
        self.assertIn("Fem forventingar heldt, elleve heldt ikkje og åtte er uavgjorde", html)
        self.assertIn("Svart flate</b> er berre scene for nettverk og kart", html)
        self.assertNotIn("—", html)
        # black is the stage for networks and maps only: the figures on black are f06, f08 and f11
        self.assertEqual(re.findall(r'class="fig svart" id="(f\d\d)"', html), ["f06", "f08", "f11"])

    def test_one_colour_one_meaning(self):
        """The cluster colours keep clear of the hues of the countries and the layers."""
        import colorsys
        js = (DOCS_DATA_DIR.parent / "funn" / "funn.js").read_text(encoding="utf-8")
        pal = re.search(r"const PAL = \[(.*?)\];", js).group(1)
        farger = re.findall(r"#([0-9a-f]{6})", pal)
        self.assertEqual(len(farger), 8)
        css = (DOCS_DATA_DIR.parent / "funn" / "funn.css").read_text(encoding="utf-8")
        # the light and the dark values of the hues that mean a country or a layer
        reserved = {k + str(i): v for k in ("DK", "FI", "IS", "NO", "SE", "oa", "ark") for i, v in enumerate(re.findall(r"--%s: (#[0-9a-f]{6})" % k, css))}
        self.assertGreaterEqual(len(reserved), 14)

        def hue(h):
            r, g, b = (int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
            hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
            return hh * 360, ss, ll

        for c in farger:
            hc, sc, lc = hue(c)
            if sc < 0.35:        # white, sand and steel grey carry no hue
                continue
            for k, v in reserved.items():
                hv, sv, lv = hue(v)
                d = abs(hc - hv)
                d = min(d, 360 - d)
                self.assertGreaterEqual(d, 18, (c, k, v))


# findings no figure draws: the unverifiable one, the refuted one and the ones that other findings already carry
UTEN_FIGUR = [
    "arkiv-7", "arkiv-9", "dekning-3", "dekning-5", "dekning-6", "grense-8", "ikkjeforsking-2", "ikkjeforsking-3",
    "ikkjeforsking-5", "ikkjeforsking-7", "ikkjeforsking-8", "kanalar-3", "kunnskapsformer-9", "omgrep-1", "omgrep-6",
    "omgrep-7", "omgrep-8", "omgrep-9", "panel-10", "panel-5", "panel-6", "panel-8", "panel-9", "populasjon-3",
    "populasjon-7", "praksis-6", "praksis-8", "samanlikning-8", "siteringar-5", "sprak-3", "sprak-5", "sprak-9",
    "tema-3", "tema-5", "tema-9", "teorielement-10", "teorielement-5", "teorielement-9", "tilgang-5", "vekst-2",
    "vekting-8",
]


class TestRunde2Parts(unittest.TestCase):
    """The new parts of round 2 (d27 to d36): arithmetic, and every number is in the finding it cites."""

    def test_numbers_are_in_the_cited_findings(self):
        """Every number in the data of a round-2 part is in the claim of one of the findings the part cites (for a
        confirmed finding also in its checked number field). Axis limits and counts of things drawn are the exceptions."""
        def flat(o, sti=""):
            if isinstance(o, bool):
                return
            if isinstance(o, (int, float)):
                yield sti, o
            elif isinstance(o, dict):
                for k, v in o.items():
                    yield from flat(v, sti + "/" + k)
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    yield from flat(v, sti + "[%d]" % i)

        feil = []
        for f in les("manifest.json")["figurar"]:
            for dl in f["delar"]:
                if dl["id"] not in ("d27", "d28", "d29", "d30", "d31", "d32", "d33", "d34", "d35", "d36"):
                    continue
                tekst = " ".join(utvida_tekst(x) for x in dl["finn"])
                for sti, v in flat(les(f["fil"])["figurar"][f["id"]][dl["id"]]):
                    if "/akse" in sti or v in (0, 1, 2, 3) or (isinstance(v, float) and abs(v) < 1e-9):
                        continue
                    if not er_med(v, tekst):
                        feil.append((dl["id"], sti, v))
        self.assertEqual(feil, [])

    def test_d28_grid_follows_the_stated_rule(self):
        d = part("d28")
        self.assertEqual(len(d["tal"]), 17)
        self.assertEqual([g["id"] for g in d["grenser"]], ["A", "H", "D", "ALL"])
        self.assertEqual([g["n"] for g in d["grenser"]], [2308, 4381, 4405, 1994])
        self.assertEqual(d["grenser"][3]["n"], 1994)
        teljing = {k: [0, 0, 0] for k in ("A", "H", "D", "ALL")}
        for r in d["tal"]:
            for k, p in zip(("A", "H", "D", "ALL"), r["per"]):
                teljing[k]["hfi".index(p["dom"])] += 1
                if p["v"] is None:
                    continue
                # held: under 10 % or 2 points (percent measures) from round 1; moved: under 25 % or 5 points
                diff = abs(p["v"] - r["r1"])
                rel = diff / abs(r["r1"])
                pts = r["eining"] == "prosent"
                kl = "h" if (rel < 0.10 or (pts and diff < 2)) else ("f" if (rel < 0.25 or (pts and diff < 5)) else "i")
                self.assertEqual(p["dom"], kl, (r["namn"], k))
        self.assertEqual(teljing, d["teljing"])
        # the verified findings state these counts: 17 held without HCI channels, 14 with the design-word demand,
        # 9 without the whitelist (5 do not hold), and the same five do not hold under all three together
        self.assertEqual((teljing["H"][0], teljing["D"][0], teljing["A"][0], teljing["A"][2], teljing["ALL"][2]), (17, 14, 9, 5, 5))
        self.assertIn("17 under grensa utan HCI-kanalar, 14 under kravet om designord", kravtekst("grense-1"))
        self.assertIn("berre 9 utan kvitlista", kravtekst("grense-1"))
        self.assertIn("Utan kvitlista held 5 tal ikkje", kravtekst("grense-1"))
        # cells whose value the findings do not state are shown as a class only
        self.assertEqual(sum(1 for r in d["tal"] for p in r["per"] if p["v"] is None), 11)

    def test_d29_archive_rows_add_up(self):
        d = part("d29")
        self.assertEqual(sum(a["n"] for a in d["arkiv"]), d["att"], 1738)
        self.assertEqual(sum(a["port"] for a in d["arkiv"]), d["port_sum"])
        self.assertEqual(sum(a["doi_treff"] for a in d["arkiv"]), d["fjerna_doi"])
        self.assertEqual(sum(a["dobbel"] for a in d["arkiv"]), d["fjerna_dobbel"])
        self.assertEqual(d["port_sum"] - d["fjerna_doi"] - d["fjerna_dobbel"], d["att"])
        self.assertEqual(sum(a["doi"] or 0 for a in d["arkiv"]), d["doi"][0])
        self.assertEqual(sum(a["pdf"] or 0 for a in d["arkiv"]), d["pdf"][0])
        # the archive layer in the sankey is the same 1 738
        n = {x["id"]: x["n"] for x in part("d01")["nodar"]}
        self.assertEqual(n["ark_att"], d["att"])

    def test_d30_panel_numbers(self):
        d = part("d30")
        for k in ("alle", "panel", "utanfor"):
            a, b = {"alle": d["alle"], "panel": d["panel"], "utanfor": d["utanfor"]}[k]
            self.assertAlmostEqual(b / a, d["faktor"][k], delta=0.01)
        self.assertEqual(d["panel"][0] + d["utanfor"][0], d["alle"][0])
        self.assertEqual(d["panel"][1] + d["utanfor"][1], d["alle"][1])
        # the OpenAlex 2020-24 count is the same as in the year series
        self.assertEqual(d["alle"][1], part("d02")["per_oa"][5])

    def test_d31_three_groups_with_start_and_end(self):
        d = part("d31")
        self.assertEqual([g["n"] for g in d["grupper"]], [4149, 5933, 11677])
        for r in d["rader"]:
            for k in ("A", "B", "C"):
                self.assertEqual(len(r[k]), 2)
                self.assertTrue(r["akse"][0] <= min(r[k]) and max(r[k]) <= r["akse"][1], (r["namn"], k))
        # scope: authors per verk and the share of single-author works agree with round 1 (d06)
        d06 = part("d06")["per"]
        rad = {r["namn"]: r for r in d["rader"]}
        self.assertEqual(rad["Forfattarar per verk"]["A"], [2.2, 3.1])
        self.assertAlmostEqual(d06[3]["snitt"], 2.2, delta=0.01)
        self.assertAlmostEqual(d06[5]["snitt"], 3.1, delta=0.01)
        self.assertEqual(rad["Einforfattarverk"]["A"], [d06[3]["ein"], d06[5]["ein"]])

    def test_d32_d33_open_pdf(self):
        d = part("d32")
        for nm, n, v in d["lag"]:
            self.assertAlmostEqual(sum(v), 100, delta=0.4, msg=nm)
        self.assertEqual(sum(k[1] for k in d["k"]), 4694)
        self.assertEqual(d["k"][5], [1036, 1549])
        e = part("d33")
        self.assertEqual(sum(k for _, k in e["land"]), e["poster"], 78)
        self.assertEqual(sum(k for _, k in e["periode"]), e["poster"])
        self.assertEqual(e["oa"][0] + e["ark"][0], e["poster"])
        self.assertEqual(e["slag"]["dr"] + e["slag"]["ma"], e["slag"]["thesis"])

    def test_d34_d35_d36(self):
        d = part("d34")
        self.assertEqual(d["nordisk"]["oa"][0] + d["nordisk"]["ark"][0], d["nordisk"]["n"], 394)
        self.assertEqual(d["port"]["ark"][0] + d["port"]["oa"][0], d["port"]["treff"][0])
        p = part("d35")
        self.assertEqual(p["tradisjon_sum"][0] + p["tradisjon_sum"][2], 4694)
        # 132 works belong to two traditions and 6 to three, so the six counts add up to 1 804 + 132 + 2 * 6
        self.assertEqual(sum(t[1] for t in p["tradisjon"]), p["tradisjon_sum"][0] + 132 + 2 * 6)
        v = part("d36")
        self.assertTrue(all(r["etter"][0] <= r["etter"][1] for r in v["rader"]))
        self.assertLessEqual(v["maks_klynge_pp"], 3.0)
        for r in v["rader"]:
            if r["gruppe"] == "klynge":
                self.assertLessEqual(abs(r["etter"][0] - r["for"]), 3.0 + 1e-9, r["namn"])


class TestHelpers(unittest.TestCase):
    def test_number_extraction(self):
        self.assertEqual(sorted(tal_i_tekst("6 432 av 24 812 (87,8 %) og 0,0737")), [0.0737, 87.8, 6432.0, 24812.0])
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
