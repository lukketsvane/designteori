"""Tests for the Utforsk data files in docs/data/vis/ (built by designteori/visdata.py).

The tests read the published files only. Checks that need the private database are skipped when it is
absent (CI has no database). Standard library only, apart from importing designteori.visdata for the shared
text helpers (that module needs numpy at import, which CI installs).
"""
from __future__ import annotations

import base64
import gzip
import shutil
import subprocess
import tempfile
import hashlib
import json
import random
import re
import struct
import unittest
from array import array
from pathlib import Path

from designteori import DOCS_DATA_DIR, RAW_SQLITE
from designteori.pdf import allowed_url, safe_public_link

VIS = DOCS_DATA_DIR / "vis"
UTFORSK = DOCS_DATA_DIR.parent / "utforsk"
N = 6432
KEY_RE = re.compile(r"^[A-Za-z0-9:_.-]+$")

JSON_FILER = ["verk.json", "lenker.json", "nett_inst.json", "nett_forf.json", "stader.json", "siteringar.json", "tid.json"]
BIN_FILER = ["naboar.bin", "termar.bin"]
ALLE_FILER = JSON_FILER[:2] + ["naboar.bin"] + JSON_FILER[2:] + ["termar.bin"]
GRENSER = {
    "manifest.json": 10_000, "verk.json": 1_900_000, "lenker.json": 700_000, "nett_inst.json": 300_000,
    "nett_forf.json": 600_000, "stader.json": 200_000, "siteringar.json": 1_000_000, "tid.json": 400_000,
    "termar.bin": 900_000,
}

_cache: dict[str, object] = {}


def les(namn: str):
    if namn not in _cache:
        _cache[namn] = json.loads((VIS / namn).read_text(encoding="utf-8"))
    return _cache[namn]


def les_docs(namn: str):
    key = "docs/" + namn
    if key not in _cache:
        _cache[key] = json.loads((DOCS_DATA_DIR / namn).read_text(encoding="utf-8"))
    return _cache[key]


def norm_lf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


class TestManifest(unittest.TestCase):
    def test_files_exist_and_match_manifest(self):
        m = les("manifest.json")
        self.assertEqual(m["format"], "utforsk-manifest-1")
        self.assertEqual(sorted(m["filer"]), sorted(ALLE_FILER))
        for namn in ALLE_FILER:
            sti = VIS / namn
            self.assertTrue(sti.is_file(), namn)
            raa = sti.read_bytes()
            info = m["filer"][namn]
            ok_bytes = info["bytes"] in (len(raa), len(norm_lf(raa)))
            self.assertTrue(ok_bytes, f"{namn}: bytes {info['bytes']} vs {len(raa)}")
            kandidatar = {hashlib.sha256(raa).hexdigest()}
            if namn.endswith(".json"):
                kandidatar.add(hashlib.sha256(norm_lf(raa)).hexdigest())
            self.assertIn(info["sha256"], kandidatar, namn)
            self.assertGreater(info["gzip"], 0)
            self.assertLessEqual(info["gzip"], info["bytes"] + 64)
        self.assertTrue((VIS / "kjelde_stader.json").is_file())

    def test_sizes(self):
        for namn, grense in GRENSER.items():
            raa = norm_lf((VIS / namn).read_bytes()) if namn.endswith(".json") else (VIS / namn).read_bytes()
            self.assertLessEqual(len(raa), grense, namn)
        verk = norm_lf((VIS / "verk.json").read_bytes())
        self.assertLessEqual(len(gzip.compress(verk, 6)), 650_000)
        self.assertEqual((VIS / "naboar.bin").stat().st_size, 192_960)

    def test_same_generert(self):
        g = {les(n)["generert"] for n in JSON_FILER + ["manifest.json"]}
        self.assertEqual(len(g), 1, g)

    def test_first_keys(self):
        for namn in JSON_FILER + ["manifest.json"]:
            d = les(namn)
            self.assertEqual(list(d)[:2], ["format", "generert"], namn)

    def test_manifest_numbers(self):
        t = les("manifest.json")["tal"]
        self.assertEqual(t["verk"], N)
        self.assertEqual(t["openalex"] + t["arkiv"], N)
        self.assertEqual(t["pdf_verifisert"] + t["pdf_ikkje_stadfest"] + t["pdf_doi"] + t["pdf_ingen"], N)
        self.assertEqual(t["referansar_kjent_mal_rader"], t["referansar_til_korpus"] + t["referansar_til_kanon"])
        self.assertEqual(t["forfattarar_totalt"], len(les("verk.json")["forfattarar"]))
        self.assertEqual(t["termar"], len(les("tid.json")["termar"]["k"]))


class TestVerk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = les("verk.json")
        cls.kol = cls.v["kol"]

    def test_index_and_lengths(self):
        idx = les_docs("semantic_index.json")
        pub = les_docs("publications.json")
        arkiv = les_docs("nordic_additions.json")
        v = self.v
        self.assertEqual(v["n"], N)
        self.assertEqual(v["n"], len(idx["ids"]))
        self.assertEqual(v["n"], len(pub) + len(arkiv))
        self.assertEqual(v["n_openalex"], len(pub))
        self.assertEqual(v["n_arkiv"], len(arkiv))
        self.assertEqual(self.kol["id"], idx["ids"])
        self.assertEqual(len(set(self.kol["id"])), N)
        for k, col in self.kol.items():
            self.assertEqual(len(col), N, k)
        self.assertEqual(self.kol["tittel"][:50], [p["title"] for p in pub[:50]])
        for k in self.kol["id"]:
            self.assertTrue(KEY_RE.match(k), k)

    def test_ranges(self):
        k, v = self.kol, self.v
        # the page counts years from 1983 (tilstand.js AR_MIN, kart.js year colours)
        self.assertTrue(all(1983 <= a <= 2026 for a in k["ar"]))
        self.assertTrue(all(0 <= x <= 10000 for x in k["x"]) and all(0 <= y <= 10000 for y in k["y"]))
        self.assertTrue(all(a in (0, 1) for a in k["lag"]))
        self.assertTrue(all(0 <= t < len(v["typar"]) for t in k["type"]))
        self.assertTrue(all(-1 <= c < len(v["kanalar"]) for c in k["kanal"]))
        self.assertTrue(all(0 <= t < len(v["tema"]) for t in k["tema"]))
        self.assertTrue(all(0 <= t < len(v["undertema"]) for t in k["undertema"]))
        self.assertTrue(all(p in (0, 1, 2, 3) for p in k["pdf"]))
        self.assertTrue(all(0 <= m <= 7 for m in k["merk"]))
        for i in range(N):
            self.assertEqual(k["lag"][i] == 1, k["sit"][i] == -1, i)
            self.assertEqual(v["undertema"][k["undertema"][i]]["tema"], k["tema"][i], i)
        for nm, ordb in (("land", "land"), ("fland", "land_alle"), ("forf", "forfattarar"), ("inst", "institusjonar")):
            lim = len(v[ordb])
            for rad in k[nm]:
                self.assertEqual(len(rad), len(set(rad)), nm)
                for j in rad:
                    self.assertTrue(0 <= j < lim, nm)
        for rad in k["land"]:
            self.assertEqual(rad, sorted(rad))
        self.assertTrue(all(isinstance(a, int) for a in k["ar"]))

    def test_dictionaries(self):
        v = self.v
        for namn in ("land", "land_alle", "typar", "kanalgrupper", "kanalar", "tema", "forfattarar", "institusjonar"):
            nokklar = [d["k"] for d in v[namn]]
            self.assertEqual(len(nokklar), len(set(nokklar)), namn)
            for k in nokklar:
                self.assertTrue(KEY_RE.match(k), (namn, k))
        self.assertEqual([d["k"] for d in v["land"]], ["DK", "FI", "IS", "NO", "SE"])
        self.assertEqual(len(v["kanalar"]), les("manifest.json")["tal"]["kanalar"])
        self.assertEqual([d["n"] for d in v["kanalar"]], sorted((d["n"] for d in v["kanalar"]), reverse=True))
        gr = [d["k"] for d in v["kanalgrupper"]]
        self.assertEqual(gr, ["tidsskrift", "konferanse", "hci", "bok", "repositorium", "anna", "ukjend"])
        self.assertEqual(v["kanalgrupper"][2]["namn"], "HCI")
        self.assertTrue(all(0 <= d["g"] < 6 for d in v["kanalar"]))
        # works per venue add up
        teljar = {}
        for c in self.kol["kanal"]:
            teljar[c] = teljar.get(c, 0) + 1
        for j, d in enumerate(v["kanalar"]):
            self.assertEqual(teljar.get(j, 0), d["n"], d["namn"])
        # land_alle sorted by works then code
        verk_per = [0] * len(v["land_alle"])
        for rad in self.kol["fland"]:
            for j in rad:
                verk_per[j] += 1
        nøkkel = [(-verk_per[j], v["land_alle"][j]["k"]) for j in range(len(verk_per))]
        self.assertEqual(nøkkel, sorted(nøkkel))
        for d in v["land_alle"][:20]:
            self.assertNotEqual(d["namn"], d["k"], d)
        inst_n = [0] * len(v["institusjonar"])
        for rad in self.kol["inst"]:
            for j in rad:
                inst_n[j] += 1
        self.assertEqual(inst_n, sorted(inst_n, reverse=True))
        for d in v["institusjonar"][:30]:
            self.assertTrue(d["kort"] and len(d["kort"]) <= 28, d)
        for d in v["institusjonar"]:
            self.assertLessEqual(len(d["kort"]), 28)

    def test_authors_dictionary(self):
        v = self.v
        først = {}
        for i, rad in enumerate(self.kol["forf"]):
            for j in rad:
                først.setdefault(j, i)
        self.assertEqual(len(først), len(v["forfattarar"]))
        # index assigned at first appearance: first-appearance order is increasing in the index
        rekkje = [først[j] for j in range(len(v["forfattarar"]))]
        self.assertEqual(rekkje, sorted(rekkje))
        self.assertTrue(all(d["k"].startswith("A") or d["k"].startswith("n:") for d in v["forfattarar"]))

    def test_themes(self):
        """Utforsk uses the cluster division of the Kart tab: the same 8 clusters, 52 sub-clusters and map positions."""
        v, k = self.v, self.kol
        kart = les_docs("klynger/kart.json")
        self.assertEqual(len(v["tema"]), 8)
        self.assertEqual(len(v["undertema"]), 52)
        self.assertEqual(sum(t["n"] for t in v["tema"]), N)
        self.assertEqual(sum(u["n"] for u in v["undertema"]), N)
        self.assertEqual(k["id"], kart["ids"])
        self.assertEqual(k["tema"], kart["k"])
        self.assertEqual(k["undertema"], kart["u"])
        self.assertEqual(k["x"], kart["x"])
        self.assertEqual(k["y"], kart["y"])
        telt = [0] * 8
        for t in k["tema"]:
            telt[t] += 1
        self.assertEqual(telt, [t["n"] for t in v["tema"]])
        self.assertEqual(telt, sorted(telt, reverse=True))
        for j, (t, c) in enumerate(zip(v["tema"], kart["klynger"])):
            self.assertEqual(t["k"], f"t{j}")
            self.assertEqual((t["namn"], t["n"], t["farge"]), (c["namn"], c["n"], c["farge"]))
            self.assertEqual((t["lx"], t["ly"]), (c["lx"], c["ly"]))
            self.assertTrue(0 <= t["lx"] <= 10000 and 0 <= t["ly"] <= 10000)
            self.assertTrue(1 <= len(t["ord"]) <= 6)
            self.assertNotIn("preset", t)
        self.assertEqual(len({t["k"] for t in v["tema"]}), 8)
        self.assertEqual(sorted(t["farge"] for t in v["tema"]), list(range(8)))
        for u, c in zip(v["undertema"], kart["under"]):
            self.assertEqual((u["namn"], u["n"], u["tema"]), (c["namn"], c["n"], c["k"]))
            self.assertTrue(0 <= u["lx"] <= 10000 and 0 <= u["ly"] <= 10000)

    def test_fold_and_term_key(self):
        from designteori.visdata import fold, termnokkel

        self.assertEqual(fold("Malmö"), "malmo")
        self.assertEqual(fold("Þórður Ærø"), "thordur aero")
        self.assertEqual(fold("Straße"), "strasse")
        self.assertEqual(fold("håndverk"), "handverk")
        self.assertEqual(fold("  Co  Design "), "co design")
        self.assertEqual(termnokkel("Co-design"), "codesign")
        self.assertEqual(termnokkel("Service  design, again"), "service design again")

    def test_venue_groups(self):
        from designteori.visdata import kanal_gruppe

        self.assertEqual(kanal_gruppe("Interactions"), 2)
        self.assertEqual(kanal_gruppe("International Journal of Child-Computer Interaction"), 2)
        self.assertEqual(kanal_gruppe("Design Studies"), 0)
        self.assertEqual(kanal_gruppe(""), 6)
        self.assertEqual(kanal_gruppe("Lecture Notes in Computer Science"), 3)

    def test_unknown_venue_is_minus_one(self):
        for j, d in enumerate(self.v["kanalar"]):
            self.assertNotIn(d["namn"].strip().lower(), ("ukjent", "ukjend", "unknown"))

    def test_land_values(self):
        k = self.kol
        t = les("manifest.json")["tal"]
        self.assertEqual(sum(1 for r in k["land"] if r), t["land_kjent"])
        self.assertEqual(sum(1 for r in k["fland"] if r), t["forfattarland_kjent"])
        for i in range(N):
            if k["lag"][i] == 1:
                self.assertEqual(k["fland"][i], [])
                self.assertEqual(k["sit"][i], -1)


class TestLenker(unittest.TestCase):
    def test_links(self):
        v = les("verk.json")
        ln = les("lenker.json")
        pdf = v["kol"]["pdf"]
        for nm in ("pdf", "doi", "kjelde"):
            self.assertEqual(len(ln[nm]), N, nm)
        found = les_docs("pdf_found.json")
        ids = set(v["kol"]["id"])
        self.assertEqual(sum(1 for p in pdf if p == 0), sum(1 for k in found if k in ids))
        for i in range(N):
            u = ln["pdf"][i]
            self.assertEqual(pdf[i] in (0, 1), u != "", i)
            if u:
                self.assertTrue(allowed_url(u), u)
                if pdf[i] == 0:
                    self.assertTrue(safe_public_link(u), u)
            d = ln["doi"][i]
            self.assertFalse(d.lower().startswith("http"), d)
            if pdf[i] == 2:
                self.assertTrue(d, i)
            if v["kol"]["lag"][i] == 0:
                self.assertEqual(ln["kjelde"][i], "")
            else:
                self.assertNotEqual(ln["kjelde"][i], "", i)
        verifisert = [v["kol"]["id"][i] for i in range(N) if pdf[i] == 0]
        self.assertTrue(all(k in found for k in verifisert))


class TestRights(unittest.TestCase):
    def test_no_abstract_keys_or_long_strings(self):
        forbudt = {"abstract", "samandrag", "text", "fulltext"}

        def gå(o, namn):
            if isinstance(o, dict):
                for k, x in o.items():
                    self.assertNotIn(str(k).lower(), forbudt, f"{namn}: nøkkel {k}")
                    gå(x, namn)
            elif isinstance(o, list):
                for x in o:
                    gå(x, namn)

        for namn in JSON_FILER + ["manifest.json"]:
            d = les(namn)
            if namn != "manifest.json":
                gå(d, namn)
        v = les("verk.json")
        self.assertTrue(all(len(t) <= 600 for t in v["kol"]["tittel"]))
        s = les("siteringar.json")
        self.assertTrue(all(len(t) <= 600 for t in s["kjelder"]["tittel"]))
        t = les("tid.json")
        for lst in (t["termar"]["k"], t["termar"]["vis"], t["standard"]):
            self.assertTrue(all(len(x) <= 80 for x in lst))
        self.assertLessEqual(max(len(x) for x in t["termar"]["k"]), 80)
        for k in t["termar"]["k"]:
            self.assertLessEqual(len(k.split(" ")), 3, k)


class TestNaboar(unittest.TestCase):
    def test_neighbours(self):
        raa = (VIS / "naboar.bin").read_bytes()
        self.assertEqual(len(raa), 192_960)
        idx = array("H")
        idx.frombytes(raa[:128_640])
        if idx.itemsize != 2:
            self.skipTest("unusual array item size")
        import sys

        if sys.byteorder == "big":
            idx.byteswap()
        cos = raa[128_640:]
        self.assertEqual(len(idx), N * 10)
        self.assertEqual(len(cos), N * 10)
        for i in range(N):
            rad = idx[i * 10 : i * 10 + 10]
            c = cos[i * 10 : i * 10 + 10]
            self.assertNotIn(i, rad)
            self.assertTrue(all(0 <= j < N for j in rad))
            self.assertEqual(len(set(rad)), 10)
            self.assertTrue(all(c[q] >= c[q + 1] for q in range(9)), i)

    def _naboar(self):
        raa = (VIS / "naboar.bin").read_bytes()
        idx = struct.unpack("<%dH" % (N * 10), raa[: N * 20])
        return idx, raa[N * 20 :]

    def test_cosines_match_vectors(self):
        # stored cosine (x/255) against the int8 vectors the neighbours come from
        vek = (DOCS_DATA_DIR / "semantic_vectors.bin").read_bytes()
        dim = len(vek) // N
        self.assertEqual(dim * N, len(vek))
        idx, cos = self._naboar()

        def v(i):
            r = struct.unpack("%db" % dim, vek[i * dim : (i + 1) * dim])
            n = sum(x * x for x in r) ** 0.5 or 1.0
            return [x / n for x in r]

        rng = random.Random(7)
        for i in rng.sample(range(N), 60):
            a = v(i)
            for q in range(10):
                j = idx[i * 10 + q]
                ekte = sum(x * y for x, y in zip(a, v(j)))
                self.assertAlmostEqual(cos[i * 10 + q] / 255, max(0.0, ekte), delta=0.02, msg=(i, j))

    def test_map_places_neighbours_close(self):
        # the Kart layout must keep similar works near each other and not collapse
        k = les("verk.json")["kol"]
        x, y = k["x"], k["y"]
        idx, _ = self._naboar()
        rng = random.Random(11)
        utval = rng.sample(range(N), 800)
        nabo = sum(((x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2) ** 0.5 for i in utval for j in idx[i * 10 : i * 10 + 10]) / 8000
        tilf = sum(((x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2) ** 0.5 for i in utval for j in rng.sample(range(N), 10)) / 8000
        # the positions are those of the Kart tab (built from the search vectors), the neighbour lists come from the
        # Utforsk vectors, so the two agree less than a layout built from the same vectors would
        self.assertLess(nabo, 0.7 * tilf, (nabo, tilf))
        for col in (x, y):
            m = sum(col) / N
            sd = (sum((c - m) ** 2 for c in col) / N) ** 0.5
            self.assertGreater(sd, 1000)
        self.assertGreater(len({(round(a), round(b)) for a, b in zip(x, y)}), N * 0.9)


class TestNett(unittest.TestCase):
    def kontroll(self, namn, kol, prefiks):
        d = les(namn)
        v = les("verk.json")
        noder = d["noder"]
        n = len(noder["ref"])
        for k in ("n", "land", "x", "y", "komp"):
            self.assertEqual(len(noder[k]), n, k)
        self.assertEqual(d["tal"]["vist"], n)
        self.assertEqual(d["tal"]["kantar"], len(d["kantar"]))
        self.assertGreaterEqual(min(noder["n"]), d["tal"]["min_verk"])
        self.assertEqual(noder["n"], sorted(noder["n"], reverse=True))
        self.assertEqual(len(set(noder["ref"])), n)
        telt = {}
        for rad in v["kol"][kol]:
            for j in rad:
                telt[j] = telt.get(j, 0) + 1
        for p in range(n):
            r = noder["ref"][p]
            self.assertEqual(telt.get(r, 0), noder["n"][p], (namn, p))
            self.assertTrue(v[{"inst": "institusjonar", "forf": "forfattarar"}[kol]][r]["k"].startswith(prefiks))
            self.assertTrue(-1 <= noder["land"][p] < len(v["land_alle"]))
        self.assertTrue(all(0 <= x <= 10000 for x in noder["x"]) and all(0 <= y <= 10000 for y in noder["y"]))
        self.assertEqual(min(noder["komp"]), 0)
        grense = [0] * (max(noder["komp"]) + 1)
        for c in noder["komp"]:
            grense[c] += 1
        self.assertEqual(grense, sorted(grense, reverse=True))
        sist = None
        for a, b, w in d["kantar"]:
            self.assertTrue(0 <= a < b < n)
            self.assertGreaterEqual(w, 1)
            if sist is not None:
                self.assertLessEqual(w, sist)
            sist = w
            self.assertEqual(noder["komp"][a], noder["komp"][b])
        self.assertEqual(len({(a, b) for a, b, _ in d["kantar"]}), len(d["kantar"]))
        return d

    def test_institutions(self):
        d = self.kontroll("nett_inst.json", "inst", "I")
        self.assertEqual(d["modus"], "inst")
        self.assertEqual(d["tal"]["alle"], len(les("verk.json")["institusjonar"]))

    def test_authors(self):
        d = self.kontroll("nett_forf.json", "forf", "A")
        self.assertEqual(d["modus"], "forf")


class TestStader(unittest.TestCase):
    def test_places(self):
        s = les("stader.json")
        v = les("verk.json")
        self.assertEqual(len(s["inst_stad"]), len(v["institusjonar"]))
        for p in s["stader"]:
            self.assertTrue(-90 <= p["lat"] <= 90 and -180 <= p["lon"] <= 180, p)
            self.assertTrue(KEY_RE.match(p["k"]), p)
            self.assertTrue(p["by"])
        self.assertEqual(len({p["k"] for p in s["stader"]}), len(s["stader"]))
        # Nordic places lie inside their country's box (a lat/lon swap or a wrong sign fails)
        boks = {"NO": (57.5, 81.0, 4.0, 34.0), "SE": (55.0, 69.5, 10.5, 24.5), "DK": (54.4, 58.0, 7.8, 15.5),
                "FI": (59.5, 70.5, 19.0, 32.0), "IS": (63.0, 67.0, -25.0, -13.0)}
        for p in s["stader"]:
            if p["land"] in boks:
                la0, la1, lo0, lo1 = boks[p["land"]]
                self.assertTrue(la0 <= p["lat"] <= la1 and lo0 <= p["lon"] <= lo1, p)
        self.assertTrue(all(-1 <= x < len(s["stader"]) for x in s["inst_stad"]))
        med = sum(1 for x in s["inst_stad"] if x >= 0)
        self.assertGreaterEqual(med, 0.95 * len(s["inst_stad"]))
        self.assertEqual(s["tal"]["med_stad"], med)
        self.assertEqual(s["tal"]["stader"], len(s["stader"]))
        ns = [p["n"] for p in s["stader"]]
        self.assertEqual(ns, sorted(ns, reverse=True))
        # n = works with an author at an institution in the place
        verk_per = [set() for _ in s["stader"]]
        for i, rad in enumerate(v["kol"]["inst"]):
            for j in rad:
                if s["inst_stad"][j] >= 0:
                    verk_per[s["inst_stad"][j]].add(i)
        self.assertEqual([len(x) for x in verk_per], ns)
        kj = les("kjelde_stader.json")
        self.assertEqual(kj["format"], "utforsk-kjelde-stader-1")
        for e in kj["institusjonar"].values():
            self.assertEqual(set(e), {"namn", "by", "land", "lat", "lon"})


class TestSiteringar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = les("siteringar.json")
        cls.v = les("verk.json")

    def test_csr(self):
        s = self.s
        m = len(s["kjelder"]["k"])
        off, til = s["ref_off"], s["ref_til"]
        self.assertEqual(len(off), N + 1)
        self.assertEqual(off[0], 0)
        self.assertEqual(off[N], len(til))
        self.assertEqual(len(s["n_sitert"]), N + m)
        self.assertEqual(len(s["ref_alle"]), N)
        self.assertEqual(len(s["ref_utan"]), N)
        lag = self.v["kol"]["lag"]
        for i in range(N):
            rad = til[off[i] : off[i + 1]]
            self.assertTrue(off[i] <= off[i + 1])
            self.assertTrue(all(rad[q] < rad[q + 1] for q in range(len(rad) - 1)), i)
            self.assertTrue(all(0 <= t < N + m for t in rad))
            self.assertNotIn(i, rad, "self-citation")
            if lag[i] == 0:
                self.assertGreaterEqual(s["ref_alle"][i], len(rad), i)
                self.assertLessEqual(s["ref_utan"][i], s["ref_alle"][i], i)
                self.assertGreaterEqual(s["ref_utan"][i], 0)
            else:
                self.assertEqual(s["ref_alle"][i], -1)
                self.assertEqual(s["ref_utan"][i], -1)
                self.assertEqual(len(rad), 0)
        t = s["tal"]
        self.assertEqual(t["kjent_mal"], len(til))
        self.assertEqual(t["kjelder"], m)
        self.assertEqual(t["referansar"], sum(x for x in s["ref_alle"] if x > 0))
        self.assertEqual(t["siterande_verk"], sum(1 for x in s["ref_alle"] if x > 0))

    def test_n_sitert(self):
        s = self.s
        m = len(s["kjelder"]["k"])
        teljar = [0] * (N + m)
        for t in s["ref_til"]:
            teljar[t] += 1
        self.assertEqual(teljar, s["n_sitert"])
        self.assertTrue(all(x >= 1 for x in s["n_sitert"][N:]))
        ns = s["n_sitert"][N:]
        self.assertEqual(ns, sorted(ns, reverse=True))

    def test_sources(self):
        k = self.s["kjelder"]
        m = len(k["k"])
        for namn, kol in k.items():
            self.assertEqual(len(kol), m, namn)
        ids = set(self.v["kol"]["id"])
        self.assertEqual(len(set(k["k"])), m)
        self.assertFalse(ids & set(k["k"]))
        lim = len(self.v["land_alle"])
        for j in range(m):
            self.assertTrue(0 <= k["kgr"][j] < 7)
            self.assertTrue(all(0 <= c < lim for c in k["fland"][j]))
            self.assertFalse(str(k["doi"][j]).lower().startswith("http"))
            self.assertTrue(k["merkelapp"][j])

    def test_map(self):
        s = self.s
        kart = s["kart"]
        n = len(s["n_sitert"])
        self.assertEqual(len(kart["noder"]), 150)
        for nm in ("merkelapp", "x", "y", "gr"):
            self.assertEqual(len(kart[nm]), 150, nm)
        self.assertEqual(len(set(kart["merkelapp"])), 150)
        self.assertTrue(all(0 <= v < n for v in kart["noder"]))
        self.assertEqual(len(set(kart["noder"])), 150)
        ns = [s["n_sitert"][v] for v in kart["noder"]]
        self.assertEqual(ns, sorted(ns, reverse=True))
        self.assertTrue(all(0 <= x <= 10000 for x in kart["x"]) and all(0 <= y <= 10000 for y in kart["y"]))
        self.assertEqual(max(kart["gr"]) + 1, len(kart["grupper"]))
        self.assertEqual(sum(g["n"] for g in kart["grupper"]), 150)
        self.assertGreaterEqual(min(g["n"] for g in kart["grupper"]), min(5, 150 // len(kart["grupper"])) if len(kart["grupper"]) > 3 else 0)
        for a, b, c, w in kart["kantar"]:
            self.assertTrue(0 <= a < b < 150)
            self.assertGreaterEqual(c, 2)
            self.assertTrue(0 < w <= 1.0001)
        self.assertEqual(len(s["land_topp"]), 8)
        self.assertEqual(len({*s["land_topp"]}), 8)
        self.assertTrue(all(0 <= c < len(self.v["land_alle"]) for c in s["land_topp"]))


class TestTid(unittest.TestCase):
    def test_terms(self):
        t = les("tid.json")
        v = len(t["termar"]["k"])
        df = t["termar"]["df"]
        off = t["off"]
        self.assertEqual(len(t["termar"]["vis"]), v)
        self.assertEqual(len(df), v)
        self.assertEqual(len(off), v + 1)
        self.assertEqual(off[0], 0)
        self.assertTrue(all(off[q] <= off[q + 1] for q in range(v)))
        self.assertTrue(all(df[q] == off[q + 1] - off[q] for q in range(v)))
        pairs = list(zip([-d for d in df], t["termar"]["k"]))
        self.assertEqual(pairs, sorted(pairs))
        self.assertEqual(len(set(t["termar"]["k"])), v)
        self.assertEqual(t["tal"]["min_df"], min(df))
        self.assertGreaterEqual(min(df), 5)
        self.assertLessEqual(max(df), int(0.4 * N))
        self.assertEqual(t["tal"]["termar"], v)
        self.assertEqual(t["tal"]["postingar"], off[-1])
        ks = set(t["termar"]["k"])
        self.assertTrue(1 <= len(t["standard"]) <= 4)
        for s in t["standard"]:
            self.assertIn(s, ks)
        raa = (VIS / "termar.bin").read_bytes()
        self.assertEqual(len(raa), 2 * off[-1])
        post = array("H")
        post.frombytes(raa)
        import sys

        if sys.byteorder == "big":
            post.byteswap()
        for q in range(v):
            rad = post[off[q] : off[q + 1]]
            self.assertTrue(all(rad[r] < rad[r + 1] for r in range(len(rad) - 1)), t["termar"]["k"][q])
            self.assertTrue(all(0 <= x < N for x in rad))
        for k in t["termar"]["k"]:
            self.assertEqual(k, " ".join(k.split()))
            self.assertNotIn("-", k)

    def test_default_terms_present(self):
        t = les("tid.json")
        for k in ("codesign", "service design", "research through design", "sustainability"):
            self.assertIn(k, t["termar"]["k"])


@unittest.skipUnless(RAW_SQLITE.exists(), "the private database is not present")
class TestMotDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sqlite3

        cls.db = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
        cls.v = les("verk.json")
        cls.ids = cls.v["kol"]["id"]

    def test_fland_for_random_works(self):
        rnd = random.Random(1)
        k = self.v["kol"]
        for i in rnd.sample(range(les("verk.json")["n_openalex"]), 200):
            rader = self.db.execute(
                "select country from authorships where work_id = ? and country is not null and country != '' order by rowid",
                (self.ids[i],),
            ).fetchall()
            forventa = []
            for (c,) in rader:
                if c not in forventa:
                    forventa.append(c)
            gjeve = [self.v["land_alle"][j]["k"] for j in k["fland"][i]]
            self.assertEqual(gjeve, forventa, self.ids[i])

    def test_authors_in_order(self):
        pub = les_docs("publications.json")
        rnd = random.Random(2)
        for i in rnd.sample(range(len(pub)), 200):
            namn = [self.v["forfattarar"][j]["namn"] for j in self.v["kol"]["forf"][i]]
            self.assertEqual(namn, list(pub[i].get("authors") or []), self.ids[i])

    def test_institution_counts(self):
        for j, d in enumerate(self.v["institusjonar"][:20]):
            n = self.db.execute(
                "select count(distinct a.work_id) from authorships a join works w on w.id = a.work_id "
                "where w.in_scope = 1 and a.institution_id = ?", (d["k"],)).fetchone()[0]
            teljar = sum(1 for rad in self.v["kol"]["inst"] if j in rad)
            self.assertEqual(teljar, n, d["k"])

    def test_reference_counts(self):
        t = les("manifest.json")["tal"]
        db = self.db
        rader = db.execute("select count(*) from references_all r join works w on w.id = r.citing_id where w.in_scope = 1").fetchone()[0]
        self.assertEqual(rader, t["referansar"])
        kort = db.execute(
            "select count(*) from references_all r join works w on w.id = r.citing_id join works c on c.id = r.cited_id "
            "where w.in_scope = 1 and c.in_scope = 1").fetchone()[0]
        self.assertEqual(kort, t["referansar_til_korpus"])
        kanon = db.execute(
            "select count(*) from references_all r join works w on w.id = r.citing_id join cited_canon c on c.id = r.cited_id "
            "where w.in_scope = 1 and r.cited_id not in (select id from works where in_scope = 1)").fetchone()[0]
        self.assertEqual(kanon, t["referansar_til_kanon"])
        self.assertEqual(t["referansar_kjent_mal_rader"], kort + kanon)

    def test_n_sitert_for_corpus_nodes(self):
        s = les("siteringar.json")
        n = N
        i_av = {w: i for i, w in enumerate(self.ids)}
        for v in s["kart"]["noder"]:
            if v >= n:
                continue
            tal = self.db.execute(
                "select count(distinct r.citing_id) from references_all r join works w on w.id = r.citing_id "
                "where w.in_scope = 1 and r.cited_id = ? and r.citing_id != r.cited_id", (self.ids[v],)).fetchone()[0]
            self.assertEqual(s["n_sitert"][v], tal, self.ids[v])
        for j, k in enumerate(s["kjelder"]["k"][:60]):
            eigen = self.db.execute(
                "select count(distinct r.citing_id) from references_all r join works w on w.id = r.citing_id "
                "where w.in_scope = 1 and r.cited_id = ?", (k,)).fetchone()[0]
            self.assertGreaterEqual(s["n_sitert"][N + j], eigen, k)
        self.assertEqual(len(i_av), N)

    def test_term_df(self):
        from designteori.visdata import SEG_SPLIT_RE, TOKEN_RE, termnokkel
        import unicodedata

        t = les("tid.json")
        v = self.v
        rnd = random.Random(3)
        titlar = v["kol"]["tittel"]
        segs = []
        for tt in titlar:
            s = unicodedata.normalize("NFC", tt).lower()
            segs.append([[x.replace("-", "").replace("'", "").replace("’", "") for x in TOKEN_RE.findall(seg)]
                         for seg in SEG_SPLIT_RE.split(s)])
        for q in rnd.sample(range(len(t["termar"]["k"])), 50):
            ord_ = t["termar"]["k"][q].split(" ")
            m = len(ord_)
            df = 0
            for sg in segs:
                if any(toks[a : a + m] == ord_ for toks in sg for a in range(len(toks) - m + 1)):
                    df += 1
            self.assertEqual(df, t["termar"]["df"][q], t["termar"]["k"][q])
        self.assertEqual(termnokkel("co-design"), "codesign")

    def test_no_abstract_text_in_files(self):
        rader = self.db.execute(
            "select abstract from works where in_scope = 1 and length(abstract) >= 200").fetchall()
        rnd = random.Random(4)
        utval = [r[0] for r in rnd.sample(rader, 200)]
        tekst = "".join((VIS / n).read_text(encoding="utf-8") for n in JSON_FILER + ["manifest.json", "kjelde_stader.json"])
        for a in utval:
            self.assertNotIn(a, tekst)
            self.assertNotIn(a[:120], tekst)


# ---------------------------------------------------------------------------
# Page checks: skipped while docs/utforsk/index.html is absent
# ---------------------------------------------------------------------------

ALLOWED_CDN = ("d3@7.9.0", "d3-sankey@0.12.3", "topojson-client@3.1.0", "world-atlas@2.0.2")
HTTPS_RE = re.compile(r"https://[^\s\"'`)<>\\]+")
# any absolute or protocol-relative URL in markup or code
URL_RE = re.compile(r"""(?:https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s"'`)<>\\]*""")
NODE = shutil.which("node")


@unittest.skipUnless((UTFORSK / "index.html").exists(), "docs/utforsk/index.html is not present yet")
class TestSide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.filer = [p for p in UTFORSK.rglob("*") if p.is_file() and p.suffix in (".html", ".js", ".css")]

    def test_https_urls(self):
        for p in self.filer:
            tekst = p.read_text(encoding="utf-8")
            for url in HTTPS_RE.findall(tekst):
                if url.startswith("https://doi.org/") or url.startswith(("https://fonts.googleapis.com", "https://fonts.gstatic.com")):
                    continue
                if url.startswith("https://cdn.jsdelivr.net/npm/"):
                    self.assertTrue(any(url.startswith(f"https://cdn.jsdelivr.net/npm/{lib}") for lib in ALLOWED_CDN), (p.name, url))
                    self.assertRegex(url, r"@\d+\.\d+\.\d+")
                    continue
                if p.suffix == ".js" and url.startswith("https://") and "w3.org" in url:
                    continue
                self.fail(f"{p.name}: ikkje tillaten URL {url}")

    def test_no_http_or_protocol_relative_urls(self):
        for p in self.filer:
            tekst = p.read_text(encoding="utf-8")
            for url in URL_RE.findall(tekst):
                if url.startswith("https://"):
                    continue  # judged by test_https_urls
                if "w3.org" in url:
                    continue  # SVG namespace
                self.fail(f"{p.name}: URL utan https {url}")

    def test_ids_used_by_scripts_exist(self):
        js = UTFORSK / "js"
        if not js.exists():
            self.skipTest("js/ is missing")
        html = (UTFORSK / "index.html").read_text(encoding="utf-8")
        kode = "\n".join(p.read_text(encoding="utf-8") for p in js.rglob("*.js"))
        finst = set(re.findall(r'\bid="([^"$]+)"', html)) | set(re.findall(r'\bid="([A-Za-z][\w-]*)"', kode))
        brukte = set(re.findall(r"""getElementById\(\s*["']([^"']+)["']\s*\)""", kode))
        brukte |= set(re.findall(r"""querySelector\(\s*["']#([A-Za-z][\w-]*)["']\s*\)""", kode))
        self.assertTrue(brukte)
        manglar = sorted(brukte - finst)
        self.assertEqual(manglar, [], f"id-ar som skripta bruker, men som ikkje finst: {manglar}")
        # the ids main.js needs at start are in the page itself
        for i in ("startmelding", "visflate", "chiprad", "listepanel", "filterlinje", "kort", "tooltip", "live", "live-merke", "kopier", "hopp"):
            self.assertIn(f'id="{i}"', html, i)

    @unittest.skipUnless(NODE, "node finst ikkje")
    def test_js_syntax(self):
        for p in sorted((UTFORSK / "js").rglob("*.js")):
            r = subprocess.run([NODE, "--check", str(p)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{p.name}: {r.stderr}")

    @unittest.skipUnless(NODE, "node finst ikkje")
    def test_js_fold_matches_builder(self):
        from designteori.visdata import fold, termnokkel

        v = les("verk.json")
        tekstar = list(v["kol"]["tittel"]) + [d["namn"] for d in v["forfattarar"]] + [d["namn"] for d in v["kanalar"]]
        tekstar += ["Malmö", "Þórður Ærø", "Straße", "håndverk", "co-design", "Research-through-Design", "Łódź đ œuvre"]
        kjelde = (UTFORSK / "js" / "hjelp.js").read_text(encoding="utf-8")
        modul = "data:text/javascript;base64," + base64.b64encode(kjelde.encode("utf-8")).decode("ascii")
        skript = (
            "import { readFileSync, writeFileSync } from 'node:fs';\n"
            f"const h = await import({json.dumps(modul)});\n"
            "const inn = JSON.parse(readFileSync(process.argv[2], 'utf8'));\n"
            "writeFileSync(process.argv[3], JSON.stringify(inn.map((t) => [h.fold(t), h.termNokkel(t)])));\n"
        )
        with tempfile.TemporaryDirectory() as d:
            ds = Path(d)
            (ds / "k.mjs").write_text(skript, encoding="utf-8")
            (ds / "inn.json").write_text(json.dumps(tekstar, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([NODE, str(ds / "k.mjs"), str(ds / "inn.json"), str(ds / "ut.json")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            ut = json.loads((ds / "ut.json").read_text(encoding="utf-8"))
        avvik = [(t, a, fold(t)) for t, (a, _) in zip(tekstar, ut) if a != fold(t)]
        self.assertEqual(avvik[:5], [], f"{len(avvik)} fold-avvik")
        avvik = [(t, b, termnokkel(t)) for t, (_, b) in zip(tekstar, ut) if b != termnokkel(t)]
        self.assertEqual(avvik[:5], [], f"{len(avvik)} termnøkkel-avvik")
        self.assertEqual(fold("Þórður Ærø"), "thordur aero")
        self.assertEqual(fold("håndverk"), "handverk")
        self.assertEqual(fold("Straße"), "strasse")

    def test_sri_on_cdn_scripts(self):
        html = (UTFORSK / "index.html").read_text(encoding="utf-8")
        for tag in re.findall(r"<script\b[^>]*>", html):
            if "cdn.jsdelivr.net" in tag:
                self.assertIn("integrity=", tag, tag)
                self.assertIn('crossorigin="anonymous"', tag, tag)
        data_js = UTFORSK / "js" / "data.js"
        if data_js.exists():
            tekst = data_js.read_text(encoding="utf-8")
            n_url = len(re.findall(r"https://cdn\.jsdelivr\.net/npm/[^\"'`\s]+\.js", tekst))
            n_sri = len(re.findall(r"sha(?:256|384|512)-", tekst))
            self.assertGreaterEqual(n_sri, n_url, "SRI manglar for skript lasta frå data.js")

    def test_sri_values(self):
        # the exact hashes published by jsDelivr for these files (amendment 66)
        venta = {
            "d3@7.9.0/dist/d3.min.js": "sha256-8glLv2FBs1lyLE/kVOtsSw8OQswQzHr5IfwVj864ZTk=",
            "d3-sankey@0.12.3/dist/d3-sankey.min.js": "sha256-gobbXWqgScxuilRnCJQ7ed+02q77DM9Cr2dOwO5Mhr4=",
            "topojson-client@3.1.0/dist/topojson-client.min.js": "sha256-Jc0CrkhsxQY+AhWk5M+xXeg3AMh6xIusTVfcaq8+u4k=",
            "world-atlas@2.0.2/countries-50m.json": "sha256-BDQs3B4wFrzX2xYw3pVoTWe3n+PIxGAyHoeu9GlQI5Q=",
        }
        tekst = (UTFORSK / "index.html").read_text(encoding="utf-8") + (UTFORSK / "js" / "data.js").read_text(encoding="utf-8")
        for fil, sri in venta.items():
            m = re.search(re.escape(fil) + r"""[^\n]*?(sha256-[A-Za-z0-9+/=]+)""", tekst)
            self.assertIsNotNone(m, fil)
            self.assertEqual(m.group(1), sri, fil)

    def test_no_fixture(self):
        self.assertFalse((UTFORSK / "_fixture").exists())

    def test_samandrag_only_in_one_file(self):
        js = UTFORSK / "js"
        if not js.exists():
            self.skipTest("js/ is missing")
        definisjonar = [p for p in js.rglob("*.js") if re.search(r"function\s+hentSamandrag\b|hentSamandrag\s*=", p.read_text(encoding="utf-8"))]
        self.assertEqual([p.name for p in definisjonar], ["samandrag.js"])
        for p in self.filer:
            if p.name == "samandrag.js":
                continue
            self.assertNotIn("abstract", p.read_text(encoding="utf-8").lower(), p.name)

    def test_imports_resolve_and_versions_equal(self):
        js = UTFORSK / "js"
        if not js.exists():
            self.skipTest("js/ is missing")
        versjonar = set()
        for p in self.filer:
            tekst = p.read_text(encoding="utf-8")
            for m in re.finditer(r"""(?:import\s*\(|from\s+|import\s+)["'](\.{1,2}/[^"']+)["']""", tekst):
                spes = m.group(1)
                sti, _, q = spes.partition("?")
                if p.suffix == ".js":
                    self.assertTrue((p.parent / sti).resolve().is_file(), f"{p.name}: {spes}")
                    mm = re.fullmatch(r"v=(\w+)", q)
                    self.assertIsNotNone(mm, f"{p.name}: importen {spes} manglar ?v=N")
                    versjonar.add(mm.group(1))
            for m in re.finditer(r"""(?:src|href)=["']([^"']+\?v=(\w+))["']""", tekst):
                versjonar.add(m.group(2))
        self.assertLessEqual(len(versjonar), 1, f"ulike ?v= i docs/utforsk: {versjonar}")


if __name__ == "__main__":
    unittest.main()
