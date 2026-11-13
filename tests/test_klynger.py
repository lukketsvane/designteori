"""Tests for the map data in docs/data/klynger/ (built by designteori/klynger.py).

The tests read the published files only (no database), so they run in CI. Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from designteori import DOCS_DATA_DIR

KLYNGER = DOCS_DATA_DIR / "klynger"
META = DOCS_DATA_DIR / "search" / "meta.json"
MAKS_BYTE = 950_000
MAKS_STRENG = 140  # no abstract or full text: every string in kart.json is an id, a name, a term or a label

_cache: dict[str, object] = {}


def les(sti: Path):
    k = str(sti)
    if k not in _cache:
        _cache[k] = json.loads(sti.read_text(encoding="utf-8"))
    return _cache[k]


def strengar(obj, sti=""):
    if isinstance(obj, str):
        yield sti, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from strengar(v, f"{sti}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from strengar(v, f"{sti}[{i}]")


class KartFil(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kart = les(KLYNGER / "kart.json")
        cls.meta = les(META)
        cls.n = len(cls.kart["ids"])

    def test_storleik(self):
        self.assertLess((KLYNGER / "kart.json").stat().st_size, MAKS_BYTE)

    def test_toppfelt(self):
        for f in ("versjon", "generert", "kjelde", "metode", "tal", "periodar", "skala", "ids", "x", "y", "k", "u",
                  "f", "klynger", "under"):
            self.assertIn(f, self.kart, f)
        self.assertEqual(self.kart["versjon"], 1)

    def test_ids_som_meta(self):
        ids = self.kart["ids"]
        self.assertEqual(ids, self.meta["ids"])
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(self.n, self.meta["n"])

    def test_bygd_frå_same_vektorar(self):
        # The map must be rebuilt (python -m designteori.klynger) whenever the search vectors are rebuilt. The key is
        # the hash of the vector bytes, not of the input text: a rebuild with the same text can still change them.
        vfil = self.meta["vectors"]["file"]
        sha = self.kart["kjelde"]["vektor_sha256"]
        self.assertEqual(sha, self.meta["files"][vfil]["sha256"])
        self.assertEqual(sha, hashlib.sha256((META.parent / vfil).read_bytes()).hexdigest())

    def test_ingen_personnamn_i_ord(self):
        from designteori.klynger import PERSONNAMN

        for gruppe in ("klynger", "under"):
            for c in self.kart[gruppe]:
                for t in c["ord"]:
                    self.assertFalse(set(t.split()) & PERSONNAMN, (gruppe, c["id"], t))

    def test_kolonner(self):
        for f in ("x", "y", "k", "u", "f"):
            self.assertEqual(len(self.kart[f]), self.n, f)
            self.assertTrue(all(isinstance(v, int) for v in self.kart[f]), f)

    def test_koordinatar(self):
        s = self.kart["skala"]
        for f in ("x", "y"):
            self.assertTrue(all(0 <= v <= s for v in self.kart[f]), f)
        # not collapsed: the points spread over most of the square
        for f in ("x", "y"):
            v = sorted(self.kart[f])
            self.assertGreater(v[int(0.95 * self.n)] - v[int(0.05 * self.n)], 0.4 * s)

    def test_klyngereferansar(self):
        kl = self.kart["klynger"]
        un = self.kart["under"]
        self.assertEqual([c["id"] for c in kl], list(range(len(kl))))
        self.assertEqual([u["id"] for u in un], list(range(len(un))))
        self.assertTrue(6 <= len(kl) <= 20)
        for i in range(self.n):
            k, u = self.kart["k"][i], self.kart["u"][i]
            self.assertTrue(0 <= k < len(kl))
            self.assertTrue(0 <= u < len(un))
            self.assertEqual(un[u]["k"], k, i)
        for c in kl:
            self.assertEqual(sorted(c["under"]), [u["id"] for u in un if u["k"] == c["id"]])

    def test_storleikar_summerer(self):
        kl = self.kart["klynger"]
        un = self.kart["under"]
        self.assertEqual(sum(c["n"] for c in kl), self.n)
        self.assertEqual(sum(u["n"] for u in un), self.n)
        tk = [0] * len(kl)
        tu = [0] * len(un)
        for k, u in zip(self.kart["k"], self.kart["u"]):
            tk[k] += 1
            tu[u] += 1
        self.assertEqual(tk, [c["n"] for c in kl])
        self.assertEqual(tu, [u["n"] for u in un])
        for c in kl:
            self.assertEqual(sum(un[u]["n"] for u in c["under"]), c["n"])

    def test_skildring(self):
        ids = self.kart["ids"]
        pos = {w: i for i, w in enumerate(ids)}
        s = self.kart["skala"]
        np_ = len(self.kart["periodar"])
        for gruppe, felt in ((self.kart["klynger"], "k"), (self.kart["under"], "u")):
            for c in gruppe:
                self.assertTrue(c["namn"].strip())
                self.assertTrue(1 <= len(c["namn"].split()) <= 6, c["namn"])
                self.assertTrue(c["ord"])
                self.assertTrue(0 <= c["lx"] <= s and 0 <= c["ly"] <= s)
                self.assertTrue(1 <= len(c["sentrale"]) <= 5)
                for w in c["sentrale"]:
                    self.assertIn(w, pos)
                    self.assertEqual(self.kart[felt][pos[w]], c["id"])
                self.assertEqual(len(c["periode"]), np_)
                self.assertEqual(sum(c["periode"]), c["n"])
                for namn, n in c["kanalar"] + c["land"]:
                    self.assertIsInstance(namn, str)
                    self.assertTrue(0 < n <= c["n"])

    def test_flagg(self):
        from designteori.klynger import NORDISKE_SPRAK

        abs_ = self.meta["abs"]
        lang = self.meta["lang"]
        for i, f in enumerate(self.kart["f"]):
            self.assertTrue(0 <= f < 16, i)
            self.assertEqual(bool(f & 2), abs_[i] == "0", i)
            self.assertEqual(bool(f & 4), lang[i] in NORDISKE_SPRAK, i)
            self.assertEqual(bool(f & 8), lang[i] == "e", i)

    def test_sentrale60(self):
        # ranked in the text space by klynger.skildre: row numbers into ids, unique, members of the group, works with
        # an abstract before title-only works
        tb = [a == "0" for a in self.meta["abs"]]
        for gruppe, felt in ((self.kart["klynger"], "k"), (self.kart["under"], "u")):
            for c in gruppe:
                s = c["sentrale60"]
                self.assertTrue(1 <= len(s) <= 60)
                self.assertEqual(len(set(s)), len(s))
                for i in s:
                    self.assertEqual(self.kart[felt][i], c["id"])
                flagg = [tb[i] for i in s]
                self.assertEqual(flagg, sorted(flagg), (felt, c["id"]))
                vist = [self.kart["ids"][i] for i in s[: len(c["sentrale"])]]
                self.assertEqual(vist, c["sentrale"])

    def test_farge_og_sprak(self):
        from designteori.klynger import PALETT_PLASSAR

        plassar = [c["farge"] for c in self.kart["klynger"]]
        self.assertEqual(len(set(plassar)), len(plassar))
        self.assertTrue(all(0 <= p < PALETT_PLASSAR for p in plassar))
        for c in self.kart["klynger"] + self.kart["under"]:
            self.assertTrue(0 <= c["nordisk"] <= 1)
        t = self.kart["tal"]
        self.assertEqual(max(c["nordisk"] for c in self.kart["klynger"]),
                         self.kart["klynger"][t["nordisk_sprak_klynge"]]["nordisk"])

    def test_ingen_lang_tekst(self):
        for sti, s in strengar({k: v for k, v in self.kart.items() if k != "ids"}):
            self.assertLessEqual(len(s), MAKS_STRENG, sti)
            self.assertNotIn("—", s, sti)

    def test_tal(self):
        t = self.kart["tal"]
        self.assertEqual(t["verk"], self.n)
        self.assertEqual(t["klynger"], len(self.kart["klynger"]))
        self.assertEqual(t["underklynger"], len(self.kart["under"]))
        self.assertEqual(t["berre_tittel"], self.meta["abs"].count("0"))
        for f in ("silhuett", "stabilitet_ari", "modularitet", "grense_del", "nmi_kanal", "nmi_emne"):
            self.assertTrue(-1 <= t[f] <= 1, f)
        for f in ("tillit", "kontinuitet", "naboar_behaldne"):
            self.assertTrue(0 <= t["utforming"][f] <= 1, f)
        # the sub-cluster coupling is reported both over all pairs and inside the parent cluster, under clear keys
        self.assertNotIn("under_kopling_loft", t)
        for f in ("under_kopling_loft_alle_par", "under_kopling_forhold_alle_par", "under_kopling_forhold_inne_topp"):
            self.assertGreater(t[f], 0, f)
        for f in ("nmi_kanal_null", "nmi_emne_null"):
            self.assertTrue(0 <= t[f] < t[f.replace("_null", "")], f)


class OmFil(unittest.TestCase):
    def test_om(self):
        om = les(KLYNGER / "om.json")
        self.assertEqual(om["versjon"], 1)
        self.assertTrue(om["tittel"] and om["ingress"])
        self.assertTrue(20 < len(om["linje"]) < 260)
        self.assertIn("nordiske språk", om["linje"])
        self.assertGreaterEqual(len(om["bolkar"]), 4)
        for sti, s in strengar(om):
            self.assertNotIn("—", s, sti)
            self.assertLessEqual(len(s), 900, sti)
        for b in om["bolkar"]:
            self.assertTrue(b["tittel"] and b["tekst"])
            self.assertNotIn("{", b["tekst"])

    def test_storleik(self):
        self.assertLess((KLYNGER / "om.json").stat().st_size, 20_000)


if __name__ == "__main__":
    unittest.main()
