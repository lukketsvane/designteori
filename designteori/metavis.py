"""Metavis: figure data for docs/funn/ (the picture version of the meta-study).

Run as ``python -u -m designteori.metavis`` from the repository root. The builder reads the two
databases read-only (data/nordic_design_research.sqlite and, for counts only, the private
corpus.sqlite), the site's own data (docs/data/nordic_additions.json, nordic_status.json, vis/*.json,
klynger/kart.json) and writes compact JSON files to docs/data/meta/: one file per section plus
manifest.json, which records for every figure the verified finding ids and the headline numbers.

Rules the code keeps (and tests/test_metavis.py checks):
  - every headline number agrees with the verified finding it cites (the corrected claim for adjusted
    findings); nothing is taken from refuted or unverifiable findings;
  - series that are computed here use the same definitions as the round-1 scripts;
  - series that the round-1 scripts computed from material that is not in the repository (the full-text
    reading, the k=10 cluster analysis, the null models, the pilots, the new questions) are kept here as
    literals in RUNDE1, each with the finding id that states it. They are values, not new analysis;
  - no text longer than 300 characters in any output file, no private text (counts and derived values only).

Only the standard library and numpy are imported at module level, so that compileall and the tests work in
CI. scipy and networkx are imported inside the layout functions. The builder never runs in CI.

Everything is deterministic: fixed seeds, fixed tie-breaks, files written as bytes with LF endings.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import argparse
import collections
import hashlib
import json
import math
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np

from . import DOCS_DATA_DIR, PRIVATE_CORPUS_DB, RAW_SQLITE

META_DIR = DOCS_DATA_DIR / "meta"
FORMAT = "meta-1"
NORD = ("DK", "FI", "IS", "NO", "SE")
NORD_NAMN = {"DK": "Danmark", "FI": "Finland", "IS": "Island", "NO": "Noreg", "SE": "Sverige"}
PERIODAR = [("før 2000", 0, 1999), ("2000–04", 2000, 2004), ("2005–09", 2005, 2009), ("2010–14", 2010, 2014),
            ("2015–19", 2015, 2019), ("2020–24", 2020, 2024), ("2025–26", 2025, 2026)]
PER_NAMN = [p[0] for p in PERIODAR]
MAKS_TEKST = 300
SEED = 20261113
TITTEL_LAG = {"oa": "OpenAlex-laget (4 694 verk)", "ark": "arkivlaget (1 738 verk)"}


def periode(y: int) -> int:
    for i, (_, a, b) in enumerate(PERIODAR):
        if a <= y <= b:
            return i
    return len(PERIODAR) - 1


def pct(a: float, b: float, d: int = 1) -> float:
    return round(100.0 * a / b, d) if b else 0.0


def r(x: float, d: int = 3) -> float:
    return round(float(x), d)


def fold(s: str) -> str:
    s = (s or "").replace("�", "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def ro(path) -> sqlite3.Connection:
    return sqlite3.connect("file:%s?mode=ro" % Path(path).as_posix(), uri=True)


def gini(counts) -> float:
    xs = sorted(counts)
    n = len(xs)
    if n == 0 or sum(xs) == 0:
        return 0.0
    cum = sum(i * x for i, x in enumerate(xs, 1))
    return 2 * cum / (n * sum(xs)) - (n + 1) / n


def lorenz(counts, punkt: int = 60):
    """Lorenz curve over a count list: cumulative share of items (small first) against cumulative share of the
    total. Returns (x, y) lists thinned to about ``punkt`` points, always keeping the end points."""
    xs = sorted(counts)
    n, tot = len(xs), float(sum(xs))
    cum = np.cumsum(xs) / tot
    idx = sorted(set(np.unique(np.round(np.linspace(0, n - 1, punkt)).astype(int)).tolist() + [n - 1]))
    x = [0.0] + [r((i + 1) / n, 4) for i in idx]
    y = [0.0] + [r(cum[i], 4) for i in idx]
    return x, y


# ----------------------------------------------------------------------------------------------------------
# Round-1 literals. Each key names the verified finding that states the values (see tests/test_metavis.py).
# ----------------------------------------------------------------------------------------------------------

RUNDE1 = {
    # vekst-8: null model for Nordic co-authorship (institution countries drawn at random)
    "nullmodell_land": {
        "verk_med_fleire_nordiske": [276, 1050], "landpar": [349, 1580], "verk_grunnlag": 1941,
        "par": [["DK", "GB", 160, 148.7], ["SE", "US", 124, 96.9], ["DK", "NL", 109, 82.0]],
    },
    # eininga-5: co-author network by unit (verified result of the new question)
    "nett_eining": {"forf_storste": [3580, 6033], "forf_null_pct": 82.0, "komponentar": 1011, "aleine": 488,
                    "par_fleire_gonger_pct": 12.2, "par_null_pct": 0.5, "par_per_periode": [25.3, 29.9, 48.5],
                    "inst_storste_pct": 94.4, "land": [85, 86], "land_ujamt": [["DK-SE", 121], ["IS-FI", 1]]},
    # tema-10 / tema-4: what explains variation in the text vectors, structure of the k=10 map
    "tema_forklaring": {
        "justert_r2": [["ti klynger", 14.01], ["kanal (12)", 8.9], ["land", 1.44], ["periode", 1.16], ["lag", 0.33]],
        "same_1435": [["kanal", 8.9], ["språk", 4.6], ["land", 2.6], ["periode", 1.5]],
        "silhuett": [0.0737, 0.0317], "midt_mellom": 14.6, "klynge8_sprak": [78.1, 7.6], "klynge8_n": 279,
    },
    # tema-8: cluster shares (percent of the period) in the full-text sample, k=10, 2005-09 .. 2020-24
    "klyngeandelar": {
        "periodar": ["2005–09", "2010–14", "2015–19", "2020–24"], "nemnar": [222, 515, 873, 1232],
        "namn": ["utdanning og undervising", "interaksjon, kropp og teknologi", "designtenking, produkt og kognisjon",
                 "byar, berekraft og samskaping", "spekulative og meir-enn-menneskelege framtider",
                 "deltaking og helse", "arkitektur, kunst og estetikk", "tenestedesign", "norskspråkleg tekst",
                 "handverk, tekstil og materialitet"],
        "storleik": [402, 375, 365, 331, 331, 317, 295, 289, 279, 279],
    },
    # omgrep-4 / omgrep-5: breadth (share of English full texts 2020-25 that use the concept) and anchor share
    "omgrep": {
        "breidde": [["design process", 72.3], ["design research", 51.0], ["design thinking", 30.4],
                    ["interaction design", 26.8], ["participatory design", 31.4], ["wicked problem", 12.7],
                    ["more-than-human", 13.7]],
        "breidde_spenn": [["speculative design", 3, 10], ["systemic design", 3, 10], ["universal design", 3, 10],
                          ["design fiction", 3, 10]],
        "anker": [["wicked problem", 48.7], ["embodied interaction", 51.3], ["soma design", 54.3],
                  ["speculative design", 44.9], ["reflective practice", 36.0], ["design process", 9.7],
                  ["design research", 11.6]],
    },
    # kunnskapsformer-2/3/4/5/6/7/8: reading of 80 texts (weighted), agreement per form on the 40 test texts,
    # co-occurrence phi, data-collection markers over 2 176 English full texts. Codebook order, not ranked.
    "former": {
        "kode": ["argument", "literature", "example", "case", "data_collection", "experiment", "design_work",
                 "practice_reflection", "modelling", "use_in_practice"],
        "namn": ["argument", "litteraturgrunnlag", "eksempel", "case", "datainnsamling", "kontrollert eksperiment",
                 "designarbeid", "praksisrefleksjon", "modellering", "bruk i praksis"],
        "lesing_pct": [40.4, 68.4, 7.7, 28.5, 56.1, 0.0, 39.4, 19.9, 3.7, 31.7],
        "lesing_ci": [[28.6, 52.1], [56.7, 80.1], [1.4, 14.1], [17.3, 39.7], [43.8, 68.4], [0.0, 3.7], [27.2, 51.5],
                      [10.1, 29.7], [0.0, 8.1], [20.5, 42.9]],
        "kappa": [0.48, 0.17, -0.05, 0.29, 0.75, 0.0, 0.16, 0.28, 0.45, 0.17],
        "kappa_ci_data": [0.52, 0.95], "presisjon_data": 0.83, "gjenfinning_data": 0.95,
        "marker": {"data_collection": [1264, 2176, 56.0, 60.1], "argument": [882, 2176, 38.5, 42.6]},
        "justert_datainnsamling": 50.8,
        "phi": [["design_work", "practice_reflection", 14, 0.45], ["data_collection", "use_in_practice", 22, 0.41],
                ["design_work", "use_in_practice", 17, 0.36], ["argument", "example", 7, 0.35],
                ["case", "data_collection", 19, 0.35], ["case", "use_in_practice", 13, 0.33],
                ["example", "practice_reflection", 4, 0.27], ["data_collection", "design_work", 20, 0.12],
                ["argument", "literature", 27, 0.11], ["example", "design_work", 4, 0.11],
                ["argument", "practice_reflection", 9, 0.10], ["literature", "example", 6, 0.10],
                ["literature", "case", 17, 0.04], ["practice_reflection", "use_in_practice", 6, 0.03],
                ["case", "practice_reflection", 5, 0.01], ["literature", "data_collection", 31, -0.02],
                ["argument", "case", 9, -0.06], ["literature", "practice_reflection", 11, -0.08],
                ["literature", "use_in_practice", 17, -0.09], ["literature", "design_work", 21, -0.10],
                ["example", "use_in_practice", 1, -0.12], ["case", "design_work", 7, -0.12],
                ["data_collection", "practice_reflection", 7, -0.14], ["example", "case", 0, -0.20],
                ["argument", "design_work", 10, -0.21], ["argument", "use_in_practice", 5, -0.34],
                ["example", "data_collection", 0, -0.34], ["argument", "data_collection", 6, -0.67]],
        "per_tekst": {"snitt": 3.06, "tre_pluss": 49, "ei": 6, "ingen": 2, "n": 80},
        "periode": [["til 2004", 10, 4, 16.8, 68.7], ["2005–09", 91, 44, 38.4, 58.5], ["2010–14", 314, 142, 39.8, 50.8],
                    ["2015–19", 580, 359, 57.9, 65.8], ["2020–24", 918, 553, 57.0, 63.4], ["2025–26", 263, 162, 55.6, 67.3]],
        "for_etter_2015": [["før 2015", 415, 190], ["frå 2015", 1761, 1074]],
        "kjelde": [["FormAkademisk", 288, 142, 43.6, 55.1], ["Nordic design research conference", 221, 91, 34.9, 47.8],
                   ["Proceedings of DRS", 153, 86, 48.3, 63.8], ["Designing Interactive Systems", 108, 63, 48.9, 67.2],
                   ["ServDes", 80, 42, 41.7, 63.1], ["The Design Journal", 76, 53, 58.7, 78.9],
                   ["Proceedings of the Design Society", 56, 39, 56.7, 80.1], ["Design Studies", 54, 49, 80.1, 96.0],
                   ["CoDesign", 50, 41, 69.2, 90.2], ["Artifact", 44, 12, 16.3, 41.8],
                   ["Participatory Design Conference", 40, 20, 35.2, 64.8]],
        "innan_kjelde": [["FormAkademisk", 41.4, 51.8], ["ServDes", 48.1, 54.7], ["Nordic design research conference", 40.9, 41.4]],
        "land_eitt": [["Danmark", 594, 333, 52.0, 60.0], ["Finland", 430, 298, 64.8, 73.5], ["Noreg", 439, 239, 49.8, 59.0],
                      ["Sverige", 541, 291, 49.6, 57.9]],
    },
    # tema-/teorielement-: the three pilots (one model reader, one codebook, no human validation)
    "teori": {
        "utval": {"kjerne": [3150, 6432], "v01": 30, "v03": 23, "cc_av": [23, 4694], "dis_v03": [9, 23], "dis_kjerne": [108, 3150],
                  "frå_2020": [17, 23]},
        "kjerne_lag": {"avh_bok_samla": 38, "avh_bok_oa": 22, "avh_bok_arkiv": 67},
        "kausal": {"v01": [31, 24, 37, 315], "v03": [56, 41, 70, 52], "les2": 45, "diff": [-10.9, -25, 1]},
        "stad": {"konklusjon": [46, 33, 60], "samandrag": 31, "innleiing": 23},
        "eigne": {"v03": [94, 87, 100], "v01": 81}, "stotte": {"oppgjeve": [27, 13, 42], "ikkje": [71, 55, 86]},
        "omgrep": {"unike": 104, "definerte": 8, "gyldigheit": 4, "forklaring": 8, "foresegn": 1, "krav": 52},
        "to_omgrep": [["v0.1", 304, 315], ["v0.2", 286, 306], ["v0.3", 44, 52]],
        "teoriar": {"namn": 29, "tekstar": 20, "av": 22},
        "att": {"funne": [35, 52], "type_lik": [30, 35], "kappa": 0.79, "stotte_lik": [24, 35], "stad": [34, 35], "attribusjon": [35, 35]},
        "gjenfinning": [["samandrag", 14, 16], ["konklusjon", 16, 24], ["innleiing", 5, 12]],
    },
}


# ----------------------------------------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------------------------------------

class Ctx:
    """Everything the figures read, loaded once. All databases are opened read-only."""

    def __init__(self, med_korpus: bool = True):
        self.con = ro(RAW_SQLITE)
        self.docs = DOCS_DATA_DIR
        self.W: dict[str, dict] = {}
        self._load_works()
        self._load_authorships()
        self.add = json.loads((self.docs / "nordic_additions.json").read_text(encoding="utf-8"))
        self.status = json.loads((self.docs / "nordic_status.json").read_text(encoding="utf-8"))
        self.vk = json.loads((self.docs / "vis" / "verk.json").read_text(encoding="utf-8"))
        self.kart = json.loads((self.docs / "klynger" / "kart.json").read_text(encoding="utf-8"))
        self.sit = json.loads((self.docs / "vis" / "siteringar.json").read_text(encoding="utf-8"))
        self.fulltekst_oa: set[str] = set()
        self.fulltekst_ark = 0
        if med_korpus and Path(PRIVATE_CORPUS_DB).exists():
            self._load_fulltekst()

    def _load_works(self):
        for row in self.con.execute(
                "select id,doi,year,kind,source,source_id,language,countries,citations,decision,topic,oa_url "
                "from works where in_scope=1"):
            wid, doi, year, kind, source, sid, lang, countries, cit, dec, topic, oa_url = row
            self.W[wid] = dict(id=wid, doi=doi or "", year=year, per=periode(year), kind=kind, source=source or "",
                               sid=sid or "", lang=lang or "", wc=sorted(json.loads(countries or "[]")),
                               cit=cit or 0, dec=dec or "", topic=topic or "", oa=bool(oa_url), auth={})
        self.n_all = self.con.execute("select count(*) from works").fetchone()[0]

    def _load_authorships(self):
        for wid, aid, name, iid, iname, c in self.con.execute(
                "select work_id,author_id,author_name,institution_id,institution_name,country from authorships"):
            w = self.W.get(wid)
            if w is None:
                continue
            if not aid:
                aid = "anon|" + (name or "")
            a = w["auth"].setdefault(aid, dict(c=set(), i={}))
            if c:
                a["c"].add(c)
            if iid:
                a["i"][iid] = (iname or "", c or "")
        for w in self.W.values():
            A = w["auth"]
            w["n_auth"] = len(A)
            w["ac"] = sorted({c for a in A.values() for c in a["c"]})
            w["an"] = sorted(set(w["ac"]) & set(NORD))
            w["insts"] = {i: v for a in A.values() for i, v in a["i"].items()}

    def _load_fulltekst(self):
        cc = ro(PRIVATE_CORPUS_DB)
        ids = {row[0] for row in cc.execute("select distinct work_id from work_documents")}
        cc.close()
        self.fulltekst_oa = ids & set(self.W)
        self.fulltekst_ark = len(ids & {a["id"] for a in self.add})

    def oa_list(self):
        return list(self.W.values())


# ----------------------------------------------------------------------------------------------------------
# Figure registry
# ----------------------------------------------------------------------------------------------------------

FIGURAR: list[dict] = []


def figur(id: str, seksjon: str, tittel: str, sporsmal: str, form: str, nemnar: str, finn: list[str]):
    """Register a figure builder. The builder returns (data, tal) with tal = headline numbers
    [{finn, etikett, verdi}]."""
    def dekor(fn):
        FIGURAR.append(dict(id=id, seksjon=seksjon, tittel=tittel, sporsmal=sporsmal, form=form, nemnar=nemnar,
                            finn=finn, fn=fn))
        return fn
    return dekor


def T(finn, etikett: str, verdi, kjelde: str | None = None) -> dict:
    """A headline number. ``finn`` is the verified finding that states it; numbers that come from the site's own
    data (kjelde="kart") carry no finding id and are checked against that data instead."""
    t = {"finn": finn, "etikett": etikett, "verdi": verdi}
    if kjelde:
        t["kjelde"] = kjelde
    return t


# ==== FIGURAR ====
# ---- Seksjon 1: materialet ----------------------------------------------------------------------------

TYPE_OA = {"article": 0, "conference-paper": 1, "book-chapter": 2, "book": 2, "dissertation": 3}
TYPE_ARK = {"article": 0, "proceedings-article": 1, "book-chapter": 2, "book": 2, "thesis": 3, "unknown": 5}
TYPE_NAMN = ["artikkel", "konferansebidrag", "bok eller kapittel", "avhandling", "anna", "ukjend"]


@figur("d01", "materialet", "Frå 24 812 rader til 6 432 postar",
       "Kor mange av dei hente radene vart registrerte verk, og kor mange har fulltekst?", "sankey",
       "Utanfor scope = utanfor inngangsporten. 6 432 er ei øvre grense for ulike verk: om lag 6 236 med tittel, år og førsteforfattar (196 dublettpostar). Fulltekst talt i den private cachen (berre tal).",
       ["populasjon-1", "populasjon-2", "populasjon-8", "populasjon-9", "dekning-1"])
def d01(ctx: Ctx):
    n_all = ctx.n_all
    oa = ctx.oa_list()
    liste = sum(1 for w in oa if w["dec"] == "Dedicated design theory and research venue")
    andre = len(oa) - liste
    ark_tot = ctx.status["source_records_total"]
    mc = ctx.status["match_status_counts"]
    fjerna = mc["matched-doi"] + mc["duplicate-staging-doi"]
    ark_att = len(ctx.add)
    assert ark_tot - fjerna == ark_att, (ark_tot, fjerna, ark_att)
    reg = len(oa) + ark_att
    ft = len(ctx.fulltekst_oa) + ctx.fulltekst_ark
    nodar = [
        ("hent_oa", "Hente OpenAlex-rader", 0, n_all), ("hent_ark", "Arkivposter", 0, ark_tot),
        ("ut", "Utanfor scope", 1, n_all - len(oa)), ("liste", "Inn via tidsskriftlista", 1, liste),
        ("andre", "Inn via tittel eller emne", 1, andre), ("ark_att", "Arkivverk att", 1, ark_att),
        ("fjerna", "Fjerna på DOI-treff", 1, fjerna), ("reg", "Registrerte postar", 2, reg),
        ("ft", "Med fulltekst", 3, ft), ("utan", "Utan fulltekst", 3, reg - ft)]
    lenkjer = [("hent_oa", "ut", n_all - len(oa)), ("hent_oa", "liste", liste), ("hent_oa", "andre", andre),
               ("hent_ark", "fjerna", fjerna), ("hent_ark", "ark_att", ark_att),
               ("liste", "reg", liste), ("andre", "reg", andre), ("ark_att", "reg", ark_att),
               ("reg", "ft", ft), ("reg", "utan", reg - ft)]
    data = {"nodar": [{"id": i, "namn": n, "kol": k, "n": v} for i, n, k, v in nodar],
            "lenkjer": [{"fra": a, "til": b, "n": v} for a, b, v in lenkjer],
            "fulltekst": {"oa": len(ctx.fulltekst_oa), "ark": ctx.fulltekst_ark,
                          "oa_pct": pct(len(ctx.fulltekst_oa), len(oa)), "ark_pct": pct(ctx.fulltekst_ark, ark_att),
                          "samla_pct": pct(ft, reg)}}
    tal = [T("populasjon-1", "Hente rader", n_all), T("populasjon-1", "OpenAlex-laget", len(oa)),
           T("populasjon-1", "Utanfor scope", n_all - len(oa)), T("populasjon-1", "Arkivlaget", ark_att),
           T("populasjon-1", "Registrerte verk", reg), T("populasjon-2", "Inn via tidsskriftlista", liste),
           T("populasjon-8", "OpenAlex-verk med fulltekst", len(ctx.fulltekst_oa))]
    return data, tal


@figur("d02", "materialet", "Når verka kom, og kva slag dei er",
       "Kor tungt ligg materialet på nyare år, og kva slag verk er det?", "stabla stolpar",
       "Kvart verk talt ein gong per lag. 2026 er ufullstendig (til 4. november). Slag etter registreringa i laget.",
       ["populasjon-4", "populasjon-5", "populasjon-10", "vekst-1", "kanalar-4", "tilgang-8"])
def d02(ctx: Ctx):
    oa = ctx.oa_list()
    ar_min = min(min(w["year"] for w in oa), min(a["year"] for a in ctx.add))
    ar = list(range(ar_min, 2027))
    cy_oa = collections.Counter(w["year"] for w in oa)
    cy_ark = collections.Counter(a["year"] for a in ctx.add)
    per_oa = [0] * len(PERIODAR)
    per_ark = [0] * len(PERIODAR)
    for w in oa:
        per_oa[w["per"]] += 1
    for a in ctx.add:
        per_ark[periode(a["year"])] += 1
    typ_oa = [[0] * len(TYPE_NAMN) for _ in PERIODAR]
    typ_ark = [[0] * len(TYPE_NAMN) for _ in PERIODAR]
    for w in oa:
        typ_oa[w["per"]][TYPE_OA.get(w["kind"], 4)] += 1
    for a in ctx.add:
        typ_ark[periode(a["year"])][TYPE_ARK.get(a["kind"], 4)] += 1
    sum_oa = [sum(x) for x in zip(*typ_oa)]
    sum_ark = [sum(x) for x in zip(*typ_ark)]
    assert sum_ark[3] == 177, sum_ark
    n = len(oa) + len(ctx.add)
    fra2010 = sum(per_oa[3:]) + sum(per_ark[3:])
    for_2000 = per_oa[0] + per_ark[0]
    data = {"ar": ar, "oa": [cy_oa[y] for y in ar], "ark": [cy_ark[y] for y in ar],
            "periodar": PER_NAMN, "per_oa": per_oa, "per_ark": per_ark,
            "typar": TYPE_NAMN, "typ_oa": typ_oa, "typ_ark": typ_ark, "typ_sum_oa": sum_oa, "typ_sum_ark": sum_ark,
            "artikkel_del_oa": [pct(typ_oa[i][0], per_oa[i]) for i in range(len(PERIODAR))],
            "avhandling_ark": {"thesis": 177, "doktor": 46, "master": 131},
            "ufullstendig": 2026}
    bok = sum_oa[2] + sum_ark[2]
    avh = sum_oa[3] + sum_ark[3]
    tal = [T("populasjon-4", "Verk frå 2010 og seinare", fra2010),
           T("populasjon-4", "Del frå 2010 og seinare, prosent", pct(fra2010, n)),
           T("populasjon-4", "Verk før 2000", for_2000), T("populasjon-4", "Del før 2000, prosent", pct(for_2000, n)),
           T("vekst-1", "OpenAlex 2010–14", per_oa[3]), T("vekst-1", "OpenAlex 2020–24", per_oa[5]),
           T("vekst-1", "OpenAlex før 2000", per_oa[0]),
           T("kanalar-4", "Artikkelandel OpenAlex, prosent", pct(sum_oa[0], len(oa))),
           T("kanalar-4", "Konferanseandel OpenAlex, prosent", pct(sum_oa[1], len(oa))),
           T("kanalar-4", "Artikkelandel før 2000, prosent", data["artikkel_del_oa"][0]),
           T("populasjon-10", "Bøker og kapittel", bok), T("populasjon-10", "Avhandlingar", avh),
           T("populasjon-5", "Arkivverk utan slag", sum_ark[5]),
           T("tilgang-8", "Slaget thesis i arkivlaget", 177), T("tilgang-8", "Doktoravhandlingar under thesis", 46),
           T("tilgang-8", "Masteroppgåver under thesis", 131)]
    return data, tal


@figur("d03", "materialet", "Språk er ei merking som følgjer kanalen",
       "Kor mange verk er på nordiske språk, og kvar står dei?", "punkt og stolpar",
       "OpenAlex-laget (4 694 verk); språkmerket er maskingjeve. Arkivlaget har ikkje språkfelt.",
       ["populasjon-6", "kanalar-7"])
def d03(ctx: Ctx):
    oa = ctx.oa_list()
    eigne = {"NO": {"no", "nb", "nn"}, "DK": {"da"}, "SE": {"sv"}, "FI": {"fi"}, "IS": {"is"}}
    land = []
    for k in ("NO", "DK", "SE", "FI", "IS"):
        ws = [w for w in oa if w["wc"] == [k]]
        h = sum(1 for w in ws if w["lang"] in eigne[k])
        land.append({"k": k, "namn": NORD_NAMN[k], "n": len(ws), "eige": h, "del": pct(h, len(ws))})
    en = sum(1 for w in oa if w["lang"] == "en")
    ikkje = len(oa) - en
    fa = [w for w in oa if "FormAkademisk" in w["source"]]
    fa_ikkje = sum(1 for w in fa if w["lang"] != "en")
    per = [[0, 0] for _ in PERIODAR]
    per_fa = [[0, 0] for _ in PERIODAR]
    for w in oa:
        per[w["per"]][0] += 1
        per[w["per"]][1] += (w["lang"] != "en")
        if "FormAkademisk" in w["source"]:
            per_fa[w["per"]][0] += 1
            per_fa[w["per"]][1] += (w["lang"] != "en")
    no_verk = [w for w in oa if "NO" in w["wc"]]
    data = {"land": land, "engelsk": en, "ikkje_engelsk": ikkje,
            "formakademisk": {"n": len(fa), "ikkje_engelsk": fa_ikkje},
            "utan_formakademisk": {"ikkje_engelsk": ikkje - fa_ikkje, "n": len(oa) - len(fa)},
            "periodar": PER_NAMN, "per_n": [x[0] for x in per], "per_ikkje_engelsk": [pct(x[1], x[0]) for x in per],
            "fa_per_n": [x[0] for x in per_fa], "fa_per_ikkje_engelsk": [pct(x[1], x[0]) for x in per_fa],
            "norske_ikkje_engelsk_pct": pct(sum(1 for w in no_verk if w["lang"] != "en"), len(no_verk))}
    tal = [T("populasjon-6", "Engelskmerkte, prosent", pct(en, len(oa))),
           T("populasjon-6", "Norskeigne i Noreg-verk", land[0]["eige"]),
           T("populasjon-6", "Noreg-verk med eitt land", land[0]["n"]),
           T("populasjon-6", "Danske verk med eige språk", land[1]["eige"]),
           T("kanalar-7", "Ikkje-engelske verk", ikkje), T("kanalar-7", "Av desse i FormAkademisk", fa_ikkje),
           T("kanalar-7", "Ikkje-engelske i FormAkademisk, prosent", pct(fa_ikkje, len(fa))),
           T("kanalar-7", "FormAkademisk 2005–09 ikkje-engelske, prosent", data["fa_per_ikkje_engelsk"][2]),
           T("kanalar-7", "FormAkademisk 2025–26 ikkje-engelske, prosent", data["fa_per_ikkje_engelsk"][6])]
    return data, tal


@figur("d04", "materialet", "Kven har fulltekst",
       "Kor stor del av verka er lesne som fulltekst, og kven er over- og underrepresenterte?", "knotte-stolpar",
       "OpenAlex-laget (4 694 verk), unnateke arkivraden (1 738 verk). Fulltekst tyder at ei fil er henta og lesen; berre tal frå den private cachen.",
       ["populasjon-8"])
def d04(ctx: Ctx):
    oa = ctx.oa_list()
    has = ctx.fulltekst_oa

    def grp(namn, filt):
        ws = [w for w in oa if filt(w)]
        h = sum(1 for w in ws if w["id"] in has)
        return {"namn": namn, "n": len(ws), "fulltekst": h, "del": pct(h, len(ws))}

    grupper = [grp("Verk med open lenkje", lambda w: w["oa"]), grp("Verk utan open lenkje", lambda w: not w["oa"]),
               grp("FormAkademisk", lambda w: "FormAkademisk" in w["source"]),
               grp("Norske verk", lambda w: "NO" in w["wc"]), grp("Svenske verk", lambda w: "SE" in w["wc"]),
               grp("Finske verk", lambda w: "FI" in w["wc"]), grp("Danske verk", lambda w: "DK" in w["wc"]),
               grp("Før 2000", lambda w: w["year"] < 2000), grp("Bokkapittel", lambda w: w["kind"] == "book-chapter"),
               grp("Artiklar", lambda w: w["kind"] == "article"),
               grp("Minst 100 siteringar", lambda w: w["cit"] >= 100)]
    per = []
    for y0, y1 in ((2000, 2004), (2005, 2009), (2010, 2014), (2015, 2018), (2019, 2023), (2024, 2026)):
        per.append(grp("%d–%d" % (y0, y1), lambda w, a=y0, b=y1: a <= w["year"] <= b))
    tot = len(has)
    data = {"alle": {"n": len(oa), "fulltekst": tot, "del": pct(tot, len(oa))}, "grupper": grupper, "periodar": per,
            "arkiv": {"n": len(ctx.add), "fulltekst": ctx.fulltekst_ark, "del": pct(ctx.fulltekst_ark, len(ctx.add))}}
    g = {x["namn"]: x for x in grupper}
    tal = [T("populasjon-8", "OpenAlex-verk med fulltekst", tot),
           T("populasjon-8", "Del med fulltekst, prosent", pct(tot, len(oa))),
           T("populasjon-8", "Med open lenkje, prosent", g["Verk med open lenkje"]["del"]),
           T("populasjon-8", "Utan open lenkje, prosent", g["Verk utan open lenkje"]["del"]),
           T("populasjon-8", "FormAkademisk med fulltekst", g["FormAkademisk"]["fulltekst"]),
           T("populasjon-8", "Norske verk, prosent", g["Norske verk"]["del"]),
           T("populasjon-8", "Danske verk, prosent", g["Danske verk"]["del"]),
           T("populasjon-8", "Før 2000 med fulltekst", g["Før 2000"]["fulltekst"]),
           T("populasjon-8", "Bokkapittel, prosent", g["Bokkapittel"]["del"]),
           T("populasjon-8", "Minst 100 siteringar, prosent", g["Minst 100 siteringar"]["del"])]
    return data, tal


# ---- Seksjon 2: vekst, land og samarbeid --------------------------------------------------------------

def land_andelar(ws, schema="brok"):
    """Credit per Nordic country for a list of OpenAlex works. brok: fractional over the work's countries;
    heil: whole count; forf: fractional over the Nordic countries of the author rows only."""
    c = collections.Counter()
    for w in ws:
        if schema == "forf":
            for k in w["an"]:
                c[k] += 1.0 / len(w["an"])
        elif schema == "heil":
            for k in w["wc"]:
                c[k] += 1.0
        else:
            n = len(w["wc"])
            for k in w["wc"]:
                c[k] += 1.0 / n
    return c


@figur("d05", "vekst", "Land over tid",
       "Korleis er veksten fordelt på land, og kva avheng rangeringa av?", "stabla område",
       "4 694 OpenAlex-verk (samla utgåve: 1 738 arkivverk til). Rang 2020–24: heiltal, brøkdel og berre forfattarland. Veksten kan ikkje skiljast frå at OpenAlex fekk fleire kjelder.",
       ["vekst-3", "vekst-4", "vekst-10", "populasjon-6", "grense-4"])
def d05(ctx: Ctx):
    oa = ctx.oa_list()
    ar = list(range(2000, 2027))
    frak = {k: [0.0] * len(ar) for k in NORD}
    ark = {k: [0] * len(ar) for k in NORD + ("utan",)}
    for w in oa:
        if w["year"] >= 2000:
            for k in w["wc"]:
                frak[k][w["year"] - 2000] += 1.0 / len(w["wc"])
    for a in ctx.add:
        if a["year"] >= 2000 and a["duplicate_status"] != "possible-duplicate":
            k = a["source_country"] if a["source_country"] in NORD else "utan"
            ark[k][a["year"] - 2000] += 1
    del_oa = {k: [] for k in NORD}
    del_samla = {k: [] for k in NORD + ("utan",)}
    for i in range(len(PERIODAR)):
        c = land_andelar([w for w in oa if w["per"] == i])
        tot = sum(c.values())
        for k in NORD:
            del_oa[k].append(pct(c[k], tot))
        cs = collections.Counter(c)
        for a in ctx.add:
            if periode(a["year"]) == i and a["duplicate_status"] != "possible-duplicate":
                cs[a["source_country"] if a["source_country"] in NORD else "utan"] += 1
        ts = sum(cs.values())
        for k in NORD + ("utan",):
            del_samla[k].append(pct(cs[k], ts))
    forf = land_andelar([w for w in oa if w["per"] == 5], "forf")
    tf = sum(forf.values())
    heil = land_andelar(oa, "heil")
    arkland = collections.Counter(a["source_country"] or "utan" for a in ctx.add)
    ws24 = [w for w in oa if w["per"] == 5]
    h24 = land_andelar(ws24, "heil")
    b24 = land_andelar(ws24, "brok")
    th, tb = sum(h24.values()), sum(b24.values())
    rang = {"periode": "2020–24", "verk": len(ws24), "metodar": ["heil", "brok", "forf"],
            "del": {k: [pct(h24[k], th), pct(b24[k], tb), pct(forf[k], tf)] for k in NORD}}
    data = {"rang": rang, "ar": ar, "oa": {k: [r(x, 2) for x in v] for k, v in frak.items()}, "ark": ark,
            "periodar": PER_NAMN, "del_oa": del_oa, "del_samla": del_samla,
            "forf_2020_24": {k: pct(forf[k], tf) for k in NORD},
            "heil": {k: int(heil[k]) for k in NORD}, "heil_sum": int(sum(heil.values())),
            "ark_land": dict(arkland), "ark_dublett": sum(1 for a in ctx.add if a["duplicate_status"] == "possible-duplicate"),
            "utan_kvitlista": {"NO": 14.2, "FI": 20.9},
            "namn": NORD_NAMN, "ufullstendig": 2026}
    tal = [T("grense-4", "Noreg utan kvitlista, prosent", 14.2), T("grense-4", "Finland utan kvitlista, prosent", 20.9),
           T("vekst-3", "Danmark 2010–14, prosent", del_oa["DK"][3]), T("vekst-3", "Danmark 2015–19, prosent", del_oa["DK"][4]),
           T("vekst-3", "Danmark 2020–24, prosent", del_oa["DK"][5]), T("vekst-3", "Sverige 2020–24, prosent", del_oa["SE"][5]),
           T("vekst-3", "Noreg 2020–24, prosent", del_oa["NO"][5]), T("vekst-3", "Finland 2020–24, prosent", del_oa["FI"][5]),
           T("vekst-3", "Noreg med forfattarland, prosent", data["forf_2020_24"]["NO"]),
           T("vekst-3", "Finland med forfattarland, prosent", data["forf_2020_24"]["FI"]),
           T("vekst-3", "Island, verk i alt", int(heil["IS"])),
           T("vekst-4", "Noreg samla 2020–24, prosent", del_samla["NO"][5]),
           T("vekst-4", "Danmark samla 2020–24, prosent", del_samla["DK"][5]),
           T("vekst-4", "Noreg samla 2010–14, prosent", del_samla["NO"][3]),
           T("vekst-4", "Danmark samla 2010–14, prosent", del_samla["DK"][3]),
           T("vekst-4", "Arkivverk frå Noreg", arkland["NO"]), T("vekst-4", "Arkivverk utan land", arkland["utan"]),
           T("vekst-4", "Dublettmerkte arkivverk", data["ark_dublett"]),
           T("vekst-10", "Noreg, verk", int(heil["NO"])), T("vekst-10", "Sverige, verk", int(heil["SE"])),
           T("vekst-10", "Danmark, verk", int(heil["DK"])), T("vekst-10", "Finland, verk", int(heil["FI"])),
           T("vekst-10", "Landmedlemskap i sum", int(sum(heil.values())))]
    return data, tal


@figur("d06", "vekst", "Større team og fleire grenser",
       "Korleis har lagstorleik og samarbeid over grenser endra seg?", "linjer og stolpar",
       "OpenAlex-laget (4 694 verk). Før 2000 er det berre 69 verk. OpenAlex kan ha betre forfattarlister for nyare verk.",
       ["vekst-6", "vekst-7"])
def d06(ctx: Ctx):
    oa = ctx.oa_list()
    per = []
    for i in range(len(PERIODAR)):
        ws = [w for w in oa if w["per"] == i]
        n = len(ws)
        multi = [w for w in ws if w["n_auth"] >= 2]
        mi = [w for w in multi if w["insts"]]
        per.append({"n": n, "snitt": r(sum(w["n_auth"] for w in ws) / n, 2),
                    "ein": pct(sum(1 for w in ws if w["n_auth"] == 1), n), "to": pct(sum(1 for w in ws if w["n_auth"] == 2), n),
                    "tre": pct(sum(1 for w in ws if w["n_auth"] == 3), n), "fire": pct(sum(1 for w in ws if w["n_auth"] >= 4), n),
                    "plassar": sum(w["n_auth"] for w in ws),
                    "n_fleirforf": len(multi), "n_fleirforf_inst": len(mi),
                    "fleire_inst": pct(sum(1 for w in mi if len(w["insts"]) >= 2), len(mi)),
                    "nord_og_utanfor": pct(sum(1 for w in multi if w["an"] and set(w["ac"]) - set(NORD)), len(multi)),
                    "fleire_nordiske": pct(sum(1 for w in multi if len(w["an"]) >= 2), len(multi))})
    ar = list(range(1995, 2027))
    snitt_ar = []
    for y in ar:
        ws = [w for w in oa if w["year"] == y]
        snitt_ar.append(r(sum(w["n_auth"] for w in ws) / len(ws), 2) if len(ws) >= 10 else None)
    typ = {}
    for k, namn in (("article", "artikkel"), ("conference-paper", "konferansebidrag")):
        typ[namn] = [r(sum(w["n_auth"] for w in oa if w["kind"] == k and w["per"] == i) /
                       max(1, sum(1 for w in oa if w["kind"] == k and w["per"] == i)), 2) if i >= 3 else None
                     for i in range(len(PERIODAR))]
    multi_all = [w for w in oa if w["n_auth"] >= 2]
    fleire_nord = sum(1 for w in oa if len(w["an"]) >= 2)
    data = {"periodar": PER_NAMN, "per": per, "ar": ar, "snitt_ar": snitt_ar, "snitt_type": typ,
            "fleirforfattarverk": len(multi_all), "fleire_nordiske_verk": fleire_nord, "ufullstendig": 2026}
    tal = [T("vekst-6", "Snitt forfattarar før 2000", per[0]["snitt"]), T("vekst-6", "Snitt 2010–14", per[3]["snitt"]),
           T("vekst-6", "Snitt 2020–24", per[5]["snitt"]),
           T("vekst-6", "Einforfattarverk før 2000, prosent", per[0]["ein"]), T("vekst-6", "Einforfattarverk 2010–14, prosent", per[3]["ein"]),
           T("vekst-6", "Einforfattarverk 2020–24, prosent", per[5]["ein"]),
           T("vekst-6", "Fire eller fleire før 2000, prosent", per[0]["fire"]), T("vekst-6", "Fire eller fleire 2010–14, prosent", per[3]["fire"]),
           T("vekst-6", "Fire eller fleire 2020–24, prosent", per[5]["fire"]),
           T("vekst-6", "Forfattarplassar 2010–14", per[3]["plassar"]), T("vekst-6", "Forfattarplassar 2020–24", per[5]["plassar"]),
           T("vekst-7", "Fleire institusjonar 2010–14, prosent", per[3]["fleire_inst"]),
           T("vekst-7", "Fleire institusjonar 2020–24, prosent", per[5]["fleire_inst"]),
           T("vekst-7", "Nordisk og ikkje-nordisk 2010–14, prosent", per[3]["nord_og_utanfor"]),
           T("vekst-7", "Nordisk og ikkje-nordisk 2020–24, prosent", per[5]["nord_og_utanfor"]),
           T("vekst-7", "To eller fleire nordiske land 2010–14, prosent", per[3]["fleire_nordiske"]),
           T("vekst-7", "To eller fleire nordiske land 2020–24, prosent", per[5]["fleire_nordiske"]),
           T("vekst-7", "Verk med fleire nordiske land", fleire_nord)]
    return data, tal


@figur("d07", "vekst", "Nordisk samarbeid mot ein nullmodell",
       "Kor ofte skriv nordiske land saman, mot det eit tilfeldig val av institusjonar ville gitt?", "observert mot venta",
       "OpenAlex-laget: 1 941 verk med minst to institusjonar med kjent land og eit nordisk land. Nullmodellen er ein målestokk, ikkje ei forklaring.",
       ["vekst-8"])
def d07(ctx: Ctx):
    n = RUNDE1["nullmodell_land"]
    par = [{"par": "%s og %s" % (NORD_NAMN.get(a, a), NORD_NAMN.get(b, b)), "a": a, "b": b, "obs": o, "venta": v}
           for a, b, o, v in n["par"]]
    data = {"verk": {"obs": n["verk_med_fleire_nordiske"][0], "venta": n["verk_med_fleire_nordiske"][1]},
            "landpar": {"obs": n["landpar"][0], "venta": n["landpar"][1]}, "grunnlag": n["verk_grunnlag"],
            "forhald": r(n["verk_med_fleire_nordiske"][0] / n["verk_med_fleire_nordiske"][1], 2),
            "forhald_par": r(n["landpar"][0] / n["landpar"][1], 2),
            "utanlandske_par": par,
            "namn": {"GB": "Storbritannia", "US": "USA", "NL": "Nederland", **NORD_NAMN}}
    tal = [T("vekst-8", "Verk med fleire nordiske land", n["verk_med_fleire_nordiske"][0]),
           T("vekst-8", "Venta ved tilfeldig val", n["verk_med_fleire_nordiske"][1]),
           T("vekst-8", "Forhold verk", data["forhald"]),
           T("vekst-8", "Landpar", n["landpar"][0]), T("vekst-8", "Landpar venta", n["landpar"][1]),
           T("vekst-8", "Verk med to institusjonar med kjent land", n["verk_grunnlag"]),
           T("vekst-8", "DK og GB observert", 160), T("vekst-8", "DK og GB venta", 148.7)]
    return data, tal


def _institusjonar(ctx: Ctx):
    oa = ctx.oa_list()
    nord = set(NORD)
    namn, land = {}, {}
    for w in oa:
        for i, (nm, c) in w["insts"].items():
            namn[i], land[i] = nm, c
    per_aktive, per_topp10, per_k50 = [], [], []
    hel = collections.Counter()
    for p in range(len(PERIODAR)):
        kred = collections.Counter()
        for w in oa:
            if w["per"] != p:
                continue
            ni = [i for i, (nm, c) in w["insts"].items() if c in nord]
            for i in ni:
                kred[i] += 1.0 / len(ni)
                hel[i] += 1
        vals = sorted(kred.values(), reverse=True)
        tot = sum(vals)
        per_aktive.append(len(kred))
        per_topp10.append(pct(sum(vals[:10]), tot))
        run, k50 = 0.0, 0
        for k50, v in enumerate(vals, 1):
            run += v
            if run >= tot / 2:
                break
        per_k50.append(k50)
    return namn, land, hel, per_aktive, per_topp10, per_k50


@figur("d08", "vekst", "Institusjonar og forfattarar",
       "Kor konsentrert er feltet på institusjonar og på forfattarar, og kor høyrer forfattarane til feltet?", "små multiplar",
       "OpenAlex-laget. Institusjonar: 4 502 verk med nordisk institusjon, brøkdelskreditt. Forfattarar: 6 033 med OpenAlex-id; «minst fem verk» tel i scope i dei to første felta og i heile tabellen i det siste.",
       ["vekst-5", "vekst-9", "eininga-2"])
def d08(ctx: Ctx):
    oa = ctx.oa_list()
    namn, land, hel, aktive, topp10, k50 = _institusjonar(ctx)
    topp = [{"namn": namn[i], "land": land[i], "n": n} for i, n in sorted(hel.items(), key=lambda kv: (-kv[1], kv[0]))[:10]]
    n_inst = len(hel)
    ein = sum(1 for v in hel.values() if v == 1)
    # authors: works in the corpus per author id
    forf = collections.Counter()
    for w in oa:
        for a in w["auth"]:
            if not a.startswith("anon|"):
                forf[a] += 1
    slottar = sum(forf.values())
    boksar = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 9), (10, 999)]
    namn_b = ["1", "2", "3", "4", "5–9", "10 eller fleire"]
    hist = [{"namn": nb, "forfattarar": sum(1 for v in forf.values() if a <= v <= b),
             "plassar": sum(v for v in forf.values() if a <= v <= b)} for nb, (a, b) in zip(namn_b, boksar)]
    ge5 = [v for v in forf.values() if v >= 5]
    # whole database: how many works does each author have, and how many of them are in scope
    tot_verk = collections.defaultdict(set)
    for wid, aid in ctx.con.execute("select work_id,author_id from authorships where author_id is not null and author_id!=''"):
        if aid in forf:
            tot_verk[aid].add(wid)
    inne = set(ctx.W)
    rader = [(len(tot_verk[a]), len(tot_verk[a] & inne)) for a in forf]
    andel5 = [k / n for n, k in rader if n >= 5]
    andel_h = [0] * 10
    for x in andel5:
        andel_h[min(9, int(x * 10))] += 1
    sl_alle = sum(k for n, k in rader)
    under_halv = sum(k for n, k in rader if k / n < 0.5)
    sl3 = sum(k for n, k in rader if n >= 3)
    under3 = sum(k for n, k in rader if n >= 3 and k / n < 0.5)
    data = {"periodar": PER_NAMN, "aktive": aktive, "topp10": topp10, "k50": k50, "topp": topp,
            "institusjonar": n_inst, "ein_verk": ein, "ref_tilfeldig_69": {"topp10": 55, "aktive": 42},
            "type_del": {"universitet og høgskular": 85.4, "kunst- og designskular": 10.7, "forskingsinstitutt og organisasjonar": 2.5,
                         "føretak og studio": 1.2, "anna": 0.3},
            "forf_hist": hist, "forf_n": len(forf), "forf_plassar": slottar,
            "forf_ge5": len(ge5), "forf_ge5_plassar": sum(ge5), "tabell_rader": ctx.n_all,
            "grense": {"n_ge5": len(andel5), "hist": andel_h, "rein_pct": pct(sum(1 for x in andel5 if x == 1), len(andel5)),
                       "median": r(float(np.median(andel5)), 2), "under_halv_pct": pct(sum(1 for x in andel5 if x < 0.5), len(andel5)),
                       "plassdel_under_halv": pct(under_halv, sl_alle), "plassdel_under_halv_ge3": pct(under3, sl3),
                       "heilt_inne_pct": pct(sum(1 for n, k in rader if n == k), len(rader))}}
    g = data["grense"]
    tal = [T("vekst-5", "Nordiske institusjonar med minst eitt verk", n_inst), T("vekst-5", "Av desse med eitt verk", ein),
           T("vekst-5", "Aktive før 2000", aktive[0]), T("vekst-5", "Aktive 2020–24", aktive[5]),
           T("vekst-5", "Topp ti før 2000, prosent", topp10[0]), T("vekst-5", "Topp ti 2020–24, prosent", topp10[5]),
           T("vekst-5", "Institusjonar for halvparten 2020–24", k50[5]),
           T("vekst-9", "Forfattarar med OpenAlex-id", len(forf)), T("vekst-9", "Forfattarplassar", slottar),
           T("vekst-9", "Forfattarar med fem eller fleire verk", len(ge5)),
           T("vekst-9", "Del med eitt verk, prosent", pct(hist[0]["forfattarar"], len(forf))),
           T("vekst-9", "Plassdel for fem eller fleire, prosent", pct(sum(ge5), slottar)),

           T("eininga-2", "Reine, prosent", g["rein_pct"]), T("eininga-2", "Median del i scope", g["median"]), T("eininga-2", "Under halvparten i scope, prosent", g["under_halv_pct"]),
           T("eininga-2", "Plassdel under halvparten, prosent", g["plassdel_under_halv"]),
           T("eininga-2", "Plassdel blant minst tre verk, prosent", g["plassdel_under_halv_ge3"]),
           T("eininga-2", "Heilt inne, prosent", g["heilt_inne_pct"])]
    return data, tal


def pakk_layout(G, skala: int = 10000):
    """Deterministic picture of a graph: the largest component with a spring layout (its far outliers pulled in),
    the other components in tight rings around it. Returns {node: (x, y)} in 0..skala."""
    import networkx as nx

    def senter(pos):
        xs = np.array([p[0] for p in pos.values()])
        ys = np.array([p[1] for p in pos.values()])
        return {n: (p[0] - np.median(xs), p[1] - np.median(ys)) for n, p in pos.items()}

    def norm(pos, radius, hale=False):
        pos = senter(pos)
        rr = np.array([math.hypot(*p) for p in pos.values()])
        if hale and len(rr) > 20:
            r90 = float(np.percentile(rr, 90))

            def kompr(rad):
                return rad if rad <= r90 else r90 + (rad - r90) * 0.2
        else:
            def kompr(rad):
                return rad
        out = {}
        for n, p in pos.items():
            rad = math.hypot(*p)
            f = kompr(rad) / rad if rad > 1e-12 else 1.0
            out[n] = (p[0] * f, p[1] * f)
        mx = max(1e-9, max(math.hypot(*p) for p in out.values()))
        return {n: (p[0] / mx * radius, p[1] / mx * radius) for n, p in out.items()}

    comps = sorted(nx.connected_components(G), key=lambda c: (-len(c), min(str(x) for x in c)))
    out = {}
    gi = comps[0]
    sub = G.subgraph(gi)
    n = len(gi)
    pg = nx.spring_layout(sub, k=1.6 / math.sqrt(max(n, 2)), iterations=90, seed=SEED)
    out.update(norm(pg, 1.0, hale=True))
    ring_r, theta, h = 1.08, 0.0, 0.0
    for comp in comps[1:]:
        s_ = len(comp)
        rho = 0.006 + 0.014 * math.sqrt(s_) if s_ > 1 else 0.004
        if s_ >= 3:
            p = norm(nx.spring_layout(G.subgraph(comp), iterations=60, seed=SEED), rho)
        elif s_ == 2:
            a_, b_ = sorted(comp, key=str)
            p = {a_: (-rho / 2, 0.0), b_: (rho / 2, 0.0)}
        else:
            p = {next(iter(comp)): (0.0, 0.0)}
        d = 2 * math.asin(min(1.0, (rho + 0.003) / ring_r))
        if theta + d > 2 * math.pi:
            ring_r += 2 * h + 0.014
            theta, h = 0.0, 0.0
            d = 2 * math.asin(min(1.0, (rho + 0.003) / ring_r))
        ang = theta + d / 2
        cx, cy = ring_r * math.cos(ang), ring_r * math.sin(ang)
        for nd, (x, y) in p.items():
            out[nd] = (cx + x, cy + y)
        theta += d
        h = max(h, rho)
    xs = [p[0] for p in out.values()]
    ys = [p[1] for p in out.values()]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    sc = (skala - 400) / max(hi_x - lo_x, hi_y - lo_y)
    return {nd: (int(round(200 + (x - lo_x) * sc)), int(round(200 + (y - lo_y) * sc))) for nd, (x, y) in out.items()}


@figur("d09", "vekst", "Same felt, tre bilete",
       "Er medforfattarnettet samanhengande, og kva avheng det av eininga ein tel?", "nettverk",
       "Medforfattarar (6 033 forfattarar), institusjonar (1 090) og land (86) i OpenAlex-laget. Kvar prikk er ein forfattar, institusjon eller land.",
       ["eininga-5", "vekst-9"])
def d09(ctx: Ctx):
    import itertools
    import networkx as nx
    oa = ctx.oa_list()
    forf = collections.Counter()
    nordisk = {}
    G = nx.Graph()
    par = collections.Counter()
    for w in oa:
        ids = sorted(a for a in w["auth"] if not a.startswith("anon|"))
        for a in ids:
            forf[a] += 1
            if w["auth"][a]["c"] & set(NORD):
                nordisk[a] = 1
        G.add_nodes_from(ids)
        for p in itertools.combinations(ids, 2):
            G.add_edge(*p)
            par[p] += 1
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    pos = pakk_layout(G)
    ids = sorted(G.nodes)
    idx = {a: i for i, a in enumerate(ids)}
    kant = sorted((idx[a], idx[b]) for a, b in G.edges)
    forfattar = {"x": [pos[a][0] for a in ids], "y": [pos[a][1] for a in ids], "n": [min(forf[a], 9) for a in ids],
                 "nord": [nordisk.get(a, 0) for a in ids], "kant": [v for e in kant for v in e],
                 "stor": len(comps[0]), "komponentar": len(comps), "aleine": sum(1 for c in comps if len(c) == 1),
                 "noder": len(ids), "kantar": len(kant),
                 "par_fleire_pct": pct(sum(1 for v in par.values() if v >= 2), len(par))}
    # institutions
    H = nx.Graph()
    iland = {}
    ivrk = collections.Counter()
    for w in oa:
        ii = sorted(w["insts"])
        H.add_nodes_from(ii)
        for i in ii:
            iland[i] = w["insts"][i][1]
            ivrk[i] += 1
        for p in itertools.combinations(ii, 2):
            H.add_edge(*p)
    hc = sorted(nx.connected_components(H), key=len, reverse=True)
    hpos = pakk_layout(H)
    hids = sorted(H.nodes)
    hidx = {a: i for i, a in enumerate(hids)}
    hk = sorted((hidx[a], hidx[b]) for a, b in H.edges)
    kode = {k: i for i, k in enumerate(NORD)}
    inst = {"x": [hpos[a][0] for a in hids], "y": [hpos[a][1] for a in hids], "n": [min(ivrk[a], 99) for a in hids],
            "land": [kode.get(iland[a], 5) for a in hids], "kant": [v for e in hk for v in e],
            "stor": len(hc[0]), "komponentar": len(hc), "noder": len(hids), "kantar": len(hk)}
    # countries
    K = nx.Graph()
    kn = collections.Counter()
    kp = collections.Counter()
    for w in oa:
        cs = sorted({v[1] for v in w["insts"].values() if v[1]})
        K.add_nodes_from(cs)
        for c in cs:
            kn[c] += 1
        for p in itertools.combinations(cs, 2):
            K.add_edge(*p)
            kp[p] += 1
    kc = sorted(nx.connected_components(K), key=len, reverse=True)
    kjerne = K.subgraph(kc[0])
    kpos = nx.spring_layout(kjerne, k=1.0 / math.sqrt(kjerne.number_of_nodes()), iterations=300, seed=SEED)
    kx0 = np.array([p[0] for p in kpos.values()])
    ky0 = np.array([p[1] for p in kpos.values()])
    for j, nd in enumerate(sorted(set(K.nodes) - set(kc[0]))):
        kpos[nd] = (kx0.max() + 0.12 * (j + 1), ky0.max() + 0.12 * (j + 1))
    kids = sorted(K.nodes)
    kx = np.array([kpos[a][0] for a in kids])
    ky = np.array([kpos[a][1] for a in kids])
    sc = 9000 / max(np.ptp(kx), np.ptp(ky))
    land = {"k": kids, "x": [int(round(500 + (v - kx.min()) * sc)) for v in kx],
            "y": [int(round(500 + (v - ky.min()) * sc)) for v in ky], "n": [kn[a] for a in kids],
            "kant": [[kids.index(a), kids.index(b), v] for (a, b), v in sorted(kp.items())],
            "stor": len(kc[0]), "noder": len(kids), "komponentar": len(kc),
            "dk_se": kp[("DK", "SE")], "is_fi": kp[("FI", "IS")]}
    e = RUNDE1["nett_eining"]
    data = {"forfattar": forfattar, "institusjon": inst, "land": land, "skala": 10000,
            "null_forfattar_pct": e["forf_null_pct"], "par_null_pct": e["par_null_pct"],
            "stor_pct": {"forfattar": pct(len(comps[0]), len(ids)), "institusjon": pct(len(hc[0]), len(hids)),
                         "land": pct(len(kc[0]), len(kids))}}
    tal = [T("eininga-5", "Del i største komponent, prosent", data["stor_pct"]["forfattar"]),
           T("eininga-5", "Nullmodell, prosent", e["forf_null_pct"]),
           T("eininga-5", "Komponentar", len(comps)), T("eininga-5", "Aleinestaande", forfattar["aleine"]),
           T("eininga-5", "Medforfattarpar med fleire verk, prosent", forfattar["par_fleire_pct"]),
           T("eininga-5", "Nullmodell par, prosent", e["par_null_pct"]),
           T("eininga-5", "Institusjonar i største komponent, prosent", data["stor_pct"]["institusjon"]),
           T("eininga-5", "Land i same komponent", len(kc[0])), T("eininga-5", "Land", len(kids)),
           T("eininga-5", "DK og SE, verk", kp[("DK", "SE")]), T("eininga-5", "IS og FI, verk", kp[("FI", "IS")])]
    return data, tal


# ---- Seksjon 3: kanalar -------------------------------------------------------------------------------

FAMILY_RULES = [
    (r"formakademisk", "FormAkademisk"),
    (r"nordic design research|^nordes\b", "Nordes"),
    (r"proceedings of drs|design research society learn|^drs ", "DRS (konferanse)"),
    (r"designing interactive systems|dis companion", "DIS (ACM)"),
    (r"participatory design conference", "PDC"),
    (r"servdes", "ServDes"),
    (r"^chi conference", "CHI (ACM)"),
    (r"nordic conference on human computer", "NordiCHI"),
    (r"^j of design research|^journal of design research", "Journal of Design Research"),
    (r"interaction design architecture", "Interaction Design & Architecture(s)"),
    (r"ozchi|australian conference on (computer )?human computer", "OzCHI"),
    (r"computer supported cooperative work", "CSCW"),
    (r"proceedings of the design society|international conference on engineering design", "Design Society / ICED"),
    (r"linkoping electronic conference proceedings", "Linkoping Electronic Conference Proceedings"),
    (r"^linkoping studies in science", "Linkoping studies (avhandlingsserie)"),
    (r"^proceedings$", "Proceedings (uspesifisert)"),
]
FAMILY_RX = [(re.compile(p), n) for p, n in FAMILY_RULES]
REPO_RX = re.compile(r"portal|repository|research portal|research archive|orbit|aaltodoc|doaj|^hal$|zenodo|^nora\b|"
                     r"lacris|publications|publication library|publication database|rucforsk|diva|"
                     r"open research|research at the|institutional|research.*\(.*university.*\)|"
                     r"^vbn|^research at|pure |ruc ")
SERIES_RX = re.compile(r"ebooks|lecture notes|series|handbooks|^advances in|procedia|electronic workshops|"
                       r"^ifip|communications in computer|proceedings\b.*conference series|iop conference|"
                       r"^springer|^routledge|^crc|design research foundations")
NORDIC_RX = re.compile(r"nordic|nordisk|scandinavian|^nordes$|norddesign|formakademisk|swedish design research|"
                       r"tidsskrift|tidskrift|techne serien|tyovaentutkimus|tyovaen|dansk|linkoping electronic|"
                       r"architecture design and conservation|^nordlit|nordisk arkitektur|^buks|"
                       r"socialmedicinsk|geografisk")
NORDIC_FAMILIES = {"FormAkademisk", "Nordes", "NordiCHI", "Linkoping Electronic Conference Proceedings"}
DEDIKERT = "Dedicated design theory and research venue"
KANAL_KLASSAR = ["nordisk kanal", "internasjonal kanal", "forlagsserie", "repositorium", "ukjend"]


def kanalfamilie(namn: str):
    if not namn:
        return None
    f = fold(namn)
    for rx, n in FAMILY_RX:
        if rx.search(f):
            return n
    return namn.replace("�", "")


def kanalklasse(namn: str, fam) -> str:
    if not namn:
        return "ukjend"
    f = fold(namn)
    if fam in NORDIC_FAMILIES or NORDIC_RX.search(f):
        if REPO_RX.search(f) and "tidsskrift" not in f and "nordic" not in f:
            return "repositorium"
        return "nordisk kanal"
    if REPO_RX.search(f):
        return "repositorium"
    if SERIES_RX.search(f):
        return "forlagsserie"
    return "internasjonal kanal"


def _kanalar(ctx: Ctx):
    oa = ctx.oa_list()
    for w in oa:
        if "fam" not in w:
            w["fam"] = kanalfamilie(w["source"])
            w["kcl"] = kanalklasse(w["source"], w["fam"])
    return oa


def _topp_del(tal, k=10):
    v = sorted(tal, reverse=True)
    return pct(sum(v[:k]), sum(v))


@figur("d10", "kanalar", "Kanalane er konsentrerte, og porten set delar av biletet",
       "Kor samla ligg verka i få kanalar, og kva er dette eit resultat av?", "Lorenz-kurver",
       "4 451 OpenAlex-verk med kanalnamn, om lag 650 kanalfamiliar. Gruppene er definerte ved inngangsporten (2 386 mot 2 308 verk).",
       ["kanalar-1", "kanalar-2"])
def d10(ctx: Ctx):
    oa = _kanalar(ctx)
    namngjevne = [w for w in oa if w["fam"]]
    fam = collections.Counter(w["fam"] for w in namngjevne)
    liste = collections.Counter(w["fam"] for w in namngjevne if w["dec"] == DEDIKERT)
    andre = collections.Counter(w["fam"] for w in namngjevne if w["dec"] != DEDIKERT)
    n_liste = sum(1 for w in oa if w["dec"] == DEDIKERT)

    def kurve(c):
        x, y = lorenz(list(c.values()), 70)
        return {"x": x, "y": y, "familiar": len(c), "verk": sum(c.values()), "gini": r(gini(list(c.values())), 2),
                "topp10": _topp_del(list(c.values()))}

    per = []
    for i in range(len(PERIODAR)):
        c = collections.Counter(w["fam"] for w in namngjevne if w["per"] == i)
        per.append({"n": sum(c.values()), "familiar": len(c), "topp10": _topp_del(list(c.values())),
                    "gini": r(gini(list(c.values())), 2)})
    topp = [{"namn": k, "n": v} for k, v in fam.most_common(10)]
    data = {"alle": kurve(fam), "liste": kurve(liste), "andre": kurve(andre), "topp": topp, "periodar": PER_NAMN, "per": per,
            "med_kanalnamn": len(namngjevne), "utan_kanalnamn": len(oa) - len(namngjevne),
            "inngang": {"liste": n_liste, "andre": len(oa) - n_liste}}
    tal = [T("kanalar-1", "Verk med kanalnamn", len(namngjevne)),
           T("kanalar-1", "Kanalfamiliar", len(fam)),
           T("kanalar-1", "FormAkademisk, verk", fam["FormAkademisk"]),
           T("kanalar-1", "FormAkademisk, prosent", pct(fam["FormAkademisk"], len(namngjevne))),
           T("kanalar-1", "Dei ti største, prosent", _topp_del(list(fam.values()))),
           T("kanalar-1", "Dei ti største før 2000, om lag prosent", round(per[0]["topp10"])),
           T("kanalar-1", "Dei ti største 2020–24, om lag prosent", round(per[5]["topp10"])),
           T("kanalar-1", "Verk før 2000 med kanalnamn", per[0]["n"]),
           T("kanalar-2", "Inn via tidsskriftlista", n_liste), T("kanalar-2", "Andre verk", len(oa) - n_liste),
           T("kanalar-2", "Topp ti i lista-gruppa, prosent", data["liste"]["topp10"]),
           T("kanalar-2", "Topp ti i andre, prosent", data["andre"]["topp10"]),
           T("kanalar-2", "Andre verk med kanalnamn", sum(andre.values()))]
    return data, tal


@figur("d11", "kanalar", "Nordiske og internasjonale kanalar",
       "Kor stor del av verka ligg i nordiske kanalar, og er norsk særstilling ein effekt av porten?", "stabla stolpar og stolpepar",
       "OpenAlex-laget (4 694 verk). «Nordisk kanal» er ein smal definisjon: PDC, DIS og ServDes har nordisk opphav og står som internasjonale.",
       ["kanalar-5", "kanalar-6"])
def d11(ctx: Ctx):
    oa = _kanalar(ctx)
    nord_n = sum(1 for w in oa if w["kcl"] == "nordisk kanal")
    fa_nordes = sum(1 for w in oa if w["fam"] in ("FormAkademisk", "Nordes"))
    per = []
    for i in range(len(PERIODAR)):
        ws = [w for w in oa if w["per"] == i]
        per.append({"n": len(ws), **{k: pct(sum(1 for w in ws if w["kcl"] == k), len(ws)) for k in KANAL_KLASSAR},
                    "nord_utan_fa_nordes": pct(sum(1 for w in ws if w["kcl"] == "nordisk kanal" and w["fam"] not in ("FormAkademisk", "Nordes")), len(ws))})
    # kanalar-6 states these shares (the verifier's recount); they are kept as the stated values
    stilt = {"NO": (45.4, 3.6), "DK": (11.0, 10.1), "SE": (15.2, 4.1), "FI": (11.3, 2.4)}
    land = []
    for k in ("NO", "DK", "SE", "FI"):
        land.append({"k": k, "namn": NORD_NAMN[k], "n": sum(1 for w in oa if k in w["wc"]),
                     "nordisk": stilt[k][0], "nordisk_andre": stilt[k][1]})
    fa = [w for w in oa if w["fam"] == "FormAkademisk"]
    no_med_kanal = [w for w in oa if "NO" in w["wc"] and w["fam"]]
    data = {"periodar": PER_NAMN, "per": per, "klassar": KANAL_KLASSAR, "land": land,
            "nordisk": nord_n, "nordisk_pct": pct(nord_n, len(oa)), "fa_nordes": fa_nordes,
            "fa_norsk": sum(1 for w in fa if "NO" in w["wc"]), "fa_n": len(fa),
            "fa_del_av_norske": pct(sum(1 for w in fa if "NO" in w["wc"]), len(no_med_kanal)),
            "nordiChi": sum(1 for w in oa if w["fam"] == "NordiCHI"),
            "ufullstendig": "2025–26"}
    tal = [T("kanalar-5", "Verk i nordiske kanalar", nord_n), T("kanalar-5", "Del i nordiske kanalar, prosent", pct(nord_n, len(oa))),
           T("kanalar-5", "FormAkademisk og Nordes", fa_nordes), T("kanalar-5", "NordiCHI", data["nordiChi"]),
           T("kanalar-6", "Noreg i nordisk kanal, om lag prosent", round(land[0]["nordisk"])),
           T("kanalar-6", "Noreg utan porten, prosent", land[0]["nordisk_andre"]),
           T("kanalar-6", "Danmark utan porten, prosent", land[1]["nordisk_andre"]),
           T("kanalar-6", "Sverige utan porten, prosent", land[2]["nordisk_andre"]),
           T("kanalar-6", "Finland utan porten, prosent", land[3]["nordisk_andre"]),
           T("kanalar-6", "FormAkademisk-verk med Noreg", data["fa_norsk"]), T("kanalar-6", "FormAkademisk-verk", len(fa)),
           T("kanalar-6", "FormAkademisk, del av norske verk med kanal, prosent", data["fa_del_av_norske"])]
    return data, tal


@figur("d12", "kanalar", "Siteringar etter kanal, kjerne og hale",
       "Kor ulikt blir verk frå ulike kanalar registrert sitert, og kva held seg av kanalane over tid?", "punkt og matrise",
       "Registrerte siteringar i OpenAlex for verk 2005–2022, ikkje verdi eller bruk. Kanalfamiliar med minst 8 verk i matrisen.",
       ["kanalar-8", "kanalar-9"])
def d12(ctx: Ctx):
    oa = _kanalar(ctx)
    ws = [w for w in oa if 2005 <= w["year"] <= 2022 and w["fam"]]
    by = collections.defaultdict(list)
    for w in ws:
        by[w["fam"]].append(w["cit"])
    vis = {"Design Studies": "Design Studies", "CoDesign": "CoDesign", "DIS (ACM)": "Designing Interactive Systems",
           "FormAkademisk": "FormAkademisk", "DRS (konferanse)": "Proceedings of DRS", "Nordes": "Nordes"}
    sit = []
    for k, namn in vis.items():
        v = by[k]
        sit.append({"namn": namn, "fam": k, "n": len(v), "median": float(np.median(v)), "usiterte": pct(sum(1 for x in v if x == 0), len(v)),
                    "p25": float(np.percentile(v, 25)), "p75": float(np.percentile(v, 75))})
    stor = sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:19]
    alle = [{"namn": k, "n": len(v), "median": float(np.median(v))} for k, v in stor]
    # persistence of venue families
    named = [w for w in oa if w["fam"]]
    n = collections.Counter(w["fam"] for w in named)
    forst, sist = {}, {}
    for w in named:
        forst[w["fam"]] = min(forst.get(w["fam"], 9999), w["year"])
        sist[w["fam"]] = max(sist.get(w["fam"], 0), w["year"])
    stor8 = sorted([f for f in n if n[f] >= 8], key=lambda f: (forst[f], -n[f], f))
    rader = []
    for f in stor8:
        pc = [sum(1 for w in named if w["fam"] == f and w["per"] == i) for i in (2, 3, 4, 5)]
        rader.append({"namn": f, "n": n[f], "per": pc, "forste": forst[f], "siste": sist[f]})
    alle4 = [x for x in rader if all(c > 0 for c in x["per"])]
    slutt_for = [x for x in rader if x["siste"] <= 2020]
    fam_per = [len({w["fam"] for w in named if w["per"] == i}) for i in range(len(PERIODAR))]
    verk_per = [sum(1 for w in named if w["per"] == i) for i in range(len(PERIODAR))]
    p5 = [w for w in named if w["per"] == 5]
    nye = [w for w in p5 if forst[w["fam"]] >= 2015]
    data = {"sit": sit, "sit_alle": alle, "periodar": PER_NAMN, "matrise_per": ["2005–09", "2010–14", "2015–19", "2020–24"],
            "matrise": rader, "fam_per": fam_per, "verk_per": verk_per, "alle_fire": len(alle4), "slutt_2020": len(slutt_for),
            "nye_2020_24": {"verk": len(nye), "av": len(p5)}}
    sd = {x["namn"]: x for x in sit}
    tal = [T("kanalar-8", "Design Studies, median", sd["Design Studies"]["median"]), T("kanalar-8", "Design Studies, n", sd["Design Studies"]["n"]),
           T("kanalar-8", "CoDesign, median", sd["CoDesign"]["median"]),
           T("kanalar-8", "FormAkademisk, median", sd["FormAkademisk"]["median"]),
           T("kanalar-8", "DRS, median", sd["Proceedings of DRS"]["median"]), T("kanalar-8", "Nordes, median", sd["Nordes"]["median"]),
           T("kanalar-9", "Familiar med verk i alle fire periodar", len(alle4)),
           T("kanalar-9", "Verk 2020–24 i kanalar frå 2015 eller seinare", len(nye)),
           T("kanalar-9", "Verk 2020–24 med kanalnamn", len(p5)),
           T("kanalar-9", "Verk før 2000 med kanalnamn", verk_per[0])]
    return data, tal


# ---- Seksjon 4: siteringar ----------------------------------------------------------------------------

SIT_PERIODAR = [("1983–2009", 1983, 2009), ("2010–14", 2010, 2014), ("2015–19", 2015, 2019), ("2020–25", 2020, 2025)]


def sit_periode(y: int):
    for i, (_, a, b) in enumerate(SIT_PERIODAR):
        if a <= y <= b:
            return i
    return 4 if y == 2026 else None


def _referansar(ctx: Ctx):
    """References made by the in-scope works, and metadata for the cited items (works table, then cited_canon)."""
    if getattr(ctx, "_refs", None) is not None:
        return ctx._refs
    refs = collections.defaultdict(list)
    for a, b in ctx.con.execute("select r.citing_id, r.cited_id from references_all r join works w on w.id=r.citing_id "
                                "where w.in_scope=1 order by 1,2"):
        refs[a].append(b)
    meta = {}
    for i, y, ins, src, cs in ctx.con.execute("select id,year,in_scope,source,countries from works"):
        meta[i] = (y, ins, src or "", json.loads(cs or "[]"))
    kanon = {}
    for i, y in ctx.con.execute("select id,year from cited_canon"):
        kanon[i] = y
    ctx._refs = (dict(refs), meta, kanon)
    return ctx._refs


@figur("d13", "siteringar", "Dei mest siterte elementa som nettverk",
       "Kva blir sitert saman, og kor skeivt fordeler referansane seg?", "nettverk og stolpar",
       "Referansane frå 3 554 OpenAlex-verk med referanseliste (109 116 referansar). Nettverket viser dei 150 mest siterte elementa i éi Louvain-køyring; kant = sitert saman av minst to verk.",
       ["siteringar-3", "siteringar-4"])
def d13(ctx: Ctx):
    refs, meta, kanon = _referansar(ctx)
    cnt = collections.Counter(b for lst in refs.values() for b in lst)
    tot = sum(cnt.values())
    srt = sorted(cnt.values(), reverse=True)
    k1 = int(round(len(srt) * 0.01))
    ein = sum(1 for v in srt if v == 1)
    s = ctx.sit
    kart = s["kart"]
    kj = s["kjelder"]
    vk = ctx.vk["kol"]
    noder = []
    for i, nid in enumerate(kart["noder"]):
        inne = nid < len(vk["id"])
        if inne:
            tittel, ar = vk["tittel"][nid], vk["ar"][nid]
        else:
            tittel, ar = kj["tittel"][nid - len(vk["id"])], kj["ar"][nid - len(vk["id"])]
        post = {"namn": kart["merkelapp"][i], "x": kart["x"][i], "y": kart["y"][i], "gr": kart["gr"][i],
                "n": s["n_sitert"][nid], "ar": ar, "inne": 1 if inne else 0,
                "tittel": (tittel or "").replace("—", "-")[:110]}
        if inne:
            post["id"] = vk["id"][nid]  # the work's OpenAlex id, for the link to the work page (#verk/<id>)
        noder.append(post)
    # siteringar-4 (checked count; the same work sits under several OpenAlex ids, so a plain recount gives 16)
    topp100_inne = 15
    data = {"noder": noder, "kantar": kart["kantar"], "grupper": kart["grupper"], "skala": ctx.kart["skala"],
            "del_referansar": {"topp100": pct(sum(srt[:100]), tot), "topp1": pct(sum(srt[:k1]), tot),
                               "ein_gong": pct(ein, tot)},
            "elementa": len(srt), "referansar": tot, "ein_gong_n": ein, "topp1_n": k1,
            "topp100_inne": topp100_inne}
    tal = [T("siteringar-3", "Ulike siterte element", len(srt)),
           T("siteringar-3", "Dei 100 mest siterte, prosent av referansane", data["del_referansar"]["topp100"]),
           T("siteringar-3", "Det øvste prosentet, prosent", data["del_referansar"]["topp1"]),
           T("siteringar-3", "Det øvste prosentet, element", k1),
           T("siteringar-3", "Sitert berre ein gong, element", ein),
           T("siteringar-3", "Sitert berre ein gong, prosent av referansane", data["del_referansar"]["ein_gong"]),
           T("siteringar-4", "Av dei 100 mest siterte i laget", topp100_inne)]
    return data, tal


@figur("d14", "siteringar", "Mottekne siteringar er svært skeive",
       "Kor ujamt er registrerte siteringar fordelte, og kor mange verk har ingen?", "Lorenz-kurve og stolpar",
       "Registrerte siteringar i OpenAlex for 4 694 verk (79 794 siteringar). Sitering er ikkje kvalitet. 2026 er ufullstendig.",
       ["siteringar-9"])
def d14(ctx: Ctx):
    oa = ctx.oa_list()
    cit = sorted((w["cit"] for w in oa), reverse=True)
    tot = sum(cit)
    n = len(cit)
    x, y = lorenz(cit, 90)
    k1, k10 = int(round(n * 0.01)), int(round(n * 0.10))
    uten = sum(1 for c in cit if c == 0)

    def usitert(filt):
        ws = [w for w in oa if filt(w)]
        return pct(sum(1 for w in ws if w["cit"] == 0), len(ws)), len(ws)

    grp = []
    for namn, a, b in (("1983–2009", 1983, 2009), ("2010–14", 2010, 2014), ("2015–19", 2015, 2019), ("2020–22", 2020, 2022),
                       ("2023–25", 2023, 2025), ("2026", 2026, 2026)):
        p, k = usitert(lambda w, a=a, b=b: a <= w["year"] <= b)
        grp.append({"namn": namn, "usitert": p, "n": k})
    ar = list(range(2000, 2027))
    per_ar = [usitert(lambda w, y=y: w["year"] == y)[0] for y in ar]
    kap, kn = usitert(lambda w: w["kind"] == "book-chapter" and 2015 <= w["year"] <= 2019)
    art, an = usitert(lambda w: w["kind"] == "article" and 2015 <= w["year"] <= 2019)
    i_laget = sum(1 for lst in [[b for b in l if b in ctx.W] for l in _referansar(ctx)[0].values()] for _ in set(lst))
    sitert_i_laget = len({b for l in _referansar(ctx)[0].values() for b in l if b in ctx.W})
    data = {"x": x, "y": y, "median": float(np.median(cit)), "snitt": r(tot / n, 1), "maks": cit[0], "sum": tot, "n": n,
            "usiterte": uten, "usiterte_pct": pct(uten, n), "topp1_pct": pct(sum(cit[:k1]), tot), "topp10_pct": pct(sum(cit[:k10]), tot),
            "grupper": grp, "ar": ar, "usitert_ar": per_ar, "kapittel_2015_19": {"usitert": kap, "n": kn},
            "artikkel_2015_19": {"usitert": art, "n": an}, "sitert_av_laget": sitert_i_laget,
            "sitert_av_laget_pct": pct(sitert_i_laget, n), "ufullstendig": 2026}
    tal = [T("siteringar-9", "Median siteringar", data["median"]), T("siteringar-9", "Snitt siteringar", data["snitt"]),
           T("siteringar-9", "Verk utan sitering", uten), T("siteringar-9", "Verk utan sitering, prosent", data["usiterte_pct"]),
           T("siteringar-9", "Topp 1 prosent, del av siteringane", data["topp1_pct"]),
           T("siteringar-9", "Topp 10 prosent, del av siteringane", data["topp10_pct"]),
           T("siteringar-9", "Siteringar i alt", tot),
           T("siteringar-9", "Usiterte 1983–2009, prosent", grp[0]["usitert"]),
           T("siteringar-9", "Usiterte 2023–25, prosent", grp[4]["usitert"]),
           T("siteringar-9", "Usiterte 2026, prosent", grp[5]["usitert"]),
           T("siteringar-9", "Bokkapittel 2015–19 usiterte, prosent", kap), T("siteringar-9", "Artiklar 2015–19 usiterte, prosent", art)]
    return data, tal


@figur("d15", "siteringar", "Referansetal og referansealder",
       "Kor mange referansar har verka, og kor gamle er dei?", "små multiplar",
       "3 554 OpenAlex-verk med referanseliste. Alder berre for referansar med kjent år (31 756 av 109 116); skeivt mot sterkt siterte element.",
       ["siteringar-1", "siteringar-6"])
def d15(ctx: Ctx):
    refs, meta, kanon = _referansar(ctx)
    W = ctx.W
    per = [[] for _ in range(5)]
    ages = [[] for _ in range(5)]
    for cid, lst in refs.items():
        w = W[cid]
        i = sit_periode(w["year"])
        per[i].append(len(lst))
        for b in lst:
            m = meta.get(b)
            y = m[0] if m else kanon.get(b)
            if y and y <= w["year"] + 1:
                ages[i].append(max(0, w["year"] - y))
    namn = [p[0] for p in SIT_PERIODAR] + ["2026"]
    rader = []
    for i in range(5):
        a = np.array(ages[i])
        hist = [int((a == k).sum()) for k in range(0, 40)] + [int((a >= 40).sum())]
        rader.append({"namn": namn[i], "verk_med_liste": len(per[i]), "median_ref": float(np.median(per[i])),
                      "med_ar": len(a), "median_alder": float(np.median(a)), "del_5": pct(int((a <= 5).sum()), len(a)),
                      "alder_hist": hist})
    ntot = sum(len(x) for x in per)
    nrefs = sum(len(v) for v in refs.values())
    nages = sum(len(x) for x in ages[:4])  # 2026 is shown but not counted in the verified total
    dekn = {}
    for nm, filt in (("bøker", lambda w: w["kind"] == "book"), ("DRS", lambda w: "Proceedings of DRS" in w["source"])):
        ws = [w for w in W.values() if filt(w)]
        dekn[nm] = [sum(1 for w in ws if w["id"] in refs), len(ws)]
    data = {"periodar": rader, "verk": ntot, "alle_verk": len(W), "referansar": nrefs, "med_alder": nages,
            "dekning": dekn}
    tal = [T("siteringar-1", "Verk med referanseliste", ntot), T("siteringar-1", "Verk i laget", len(W)),
           T("siteringar-1", "Del med liste, prosent", pct(ntot, len(W))),
           T("siteringar-1", "Median referansar 1983–2009", rader[0]["median_ref"]), T("siteringar-1", "Median referansar 2010–14", rader[1]["median_ref"]),
           T("siteringar-1", "Median referansar 2015–19", rader[2]["median_ref"]), T("siteringar-1", "Median referansar 2020–25", rader[3]["median_ref"]),
           T("siteringar-1", "Bøker med liste", dekn["bøker"][0]), T("siteringar-1", "Bøker", dekn["bøker"][1]),
           T("siteringar-1", "DRS-verk med liste", dekn["DRS"][0]), T("siteringar-1", "DRS-verk", dekn["DRS"][1]),
           T("siteringar-6", "Referansar med kjent år", nages),
           T("siteringar-6", "Median alder 1983–2009", rader[0]["median_alder"]), T("siteringar-6", "Median alder 2010–14", rader[1]["median_alder"]),
           T("siteringar-6", "Median alder 2015–19", rader[2]["median_alder"]), T("siteringar-6", "Median alder 2020–25", rader[3]["median_alder"]),
           T("siteringar-6", "Fem år eller yngre 1983–2009, prosent", rader[0]["del_5"]),
           T("siteringar-6", "Fem år eller yngre 2010–14, prosent", rader[1]["del_5"]),
           T("siteringar-6", "Fem år eller yngre 2015–19, prosent", rader[2]["del_5"]),
           T("siteringar-6", "Fem år eller yngre 2020–25, prosent", rader[3]["del_5"])]
    return data, tal


@figur("d16", "siteringar", "Kvar referansane går",
       "Kor stor del av referansane frå laget peikar til laget sjølv, til utanforverk og til verk utanfor tabellen?", "stabla stolpar",
       "109 116 referansar frå 3 554 OpenAlex-verk. Delen til laget er eit golv (bøker og arkivlaget manglar referanselister) og kan delvis kome av at laget er tett på nyare år; ikkje testa mot det.",
       ["siteringar-2", "eininga-3"])
def d16(ctx: Ctx):
    refs, meta, kanon = _referansar(ctx)
    W = ctx.W
    til_laget = til_utanfor = til_ukjend = 0
    per = [[0, 0] for _ in range(5)]
    same_kjelde = delt_land = 0
    mottak_scope = collections.Counter()
    mottak_utanfor = collections.Counter()
    for cid, lst in refs.items():
        w = W[cid]
        i = sit_periode(w["year"])
        for b in lst:
            per[i][1] += 1
            if b in W:
                til_laget += 1
                per[i][0] += 1
                v = W[b]
                if v["source"] and v["source"] == w["source"]:
                    same_kjelde += 1
                if set(v["wc"]) & set(w["wc"]):
                    delt_land += 1
                mottak_scope[b] += 1
            elif b in meta and meta[b][1] == 0:
                til_utanfor += 1
                mottak_utanfor[b] += 1
            else:
                til_ukjend += 1
    tot = til_laget + til_utanfor + til_ukjend
    n_utan = sum(1 for m in meta.values() if m[1] == 0)
    namn = [p[0] for p in SIT_PERIODAR] + ["2026"]
    data = {"til_laget": til_laget, "til_utanfor": til_utanfor, "utanfor_tabellen": til_ukjend, "sum": tot,
            "periodar": namn, "per_del": [pct(a, b) for a, b in per], "per_n": [b for a, b in per],
            "same_kjelde_pct": pct(same_kjelde, til_laget), "delt_land_pct": pct(delt_land, til_laget),
            "per_mottakar": {"laget": r(til_laget / len(W), 2), "utanfor": r(til_utanfor / n_utan, 2),
                             "forhold": r((til_laget / len(W)) / (til_utanfor / n_utan), 1)},
            "utanfor_refererte": {"n": len(mottak_utanfor), "av": n_utan, "pct": pct(len(mottak_utanfor), n_utan)}}
    tal = [T("siteringar-2", "Referansar i alt", tot), T("siteringar-2", "Referansar til laget", til_laget),
           T("siteringar-2", "Del til laget, prosent", pct(til_laget, tot)),
           T("siteringar-2", "Del til laget 1983–2009, prosent", data["per_del"][0]),
           T("siteringar-2", "Del til laget 2020–25, prosent", data["per_del"][3]),
           T("siteringar-2", "Til same kjelde, prosent", data["same_kjelde_pct"]),
           T("siteringar-2", "Til verk med delt land, prosent", data["delt_land_pct"]),
           T("eininga-3", "Til utanfor scope", til_utanfor), T("eininga-3", "Utanfor tabellen", til_ukjend),
           T("eininga-3", "Per mottakarverk, laget", data["per_mottakar"]["laget"]),
           T("eininga-3", "Per mottakarverk, utanfor", data["per_mottakar"]["utanfor"]),
           T("eininga-3", "Utanforverk refererte", len(mottak_utanfor)), T("eininga-3", "Utanforverk", n_utan),
           T("eininga-3", "Utanforverk refererte, prosent", data["utanfor_refererte"]["pct"])]
    return data, tal


@figur("d17", "siteringar", "Kva siteringssamfunna følgjer",
       "Kva samsvarer samfunna i det bibliografiske koplingsnettverket med?", "stolpar med spenn",
       "Bibliografisk kopling mellom 3 554 verk (minst to delte referansar). Louvain-samfunn flyttar seg mellom køyringar (ARI 0,5 til 0,7); spenn over ti køyringar.",
       ["siteringar-7", "siteringar-8"])
def d17(ctx: Ctx):
    from scipy import sparse
    from scipy.sparse.csgraph import connected_components
    refs, meta, kanon = _referansar(ctx)
    ids = sorted(refs)
    kol = {}
    rows, cols = [], []
    for i, cid in enumerate(ids):
        for b in set(refs[cid]):
            rows.append(i)
            cols.append(kol.setdefault(b, len(kol)))
    M = sparse.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, cols)), shape=(len(ids), len(kol)))
    C = (M @ M.T).tocoo()
    m = (C.row < C.col) & (C.data >= 2)
    n_kant = int(m.sum())
    A = sparse.coo_matrix((np.ones(n_kant), (C.row[m], C.col[m])), shape=(len(ids), len(ids)))
    nk, lab = connected_components(A, directed=False)
    storst = int(np.bincount(lab).max())
    isolerte = int((np.bincount(lab) == 1).sum())
    nmi = [("kjelde", 0.12, 0.15), ("språk", 0.04, 0.05), ("type", 0.05, 0.05), ("land", 0.03, 0.05), ("periode", 0.03, 0.08)]
    data = {"verk": len(ids), "kantar": n_kant, "storst": storst, "storst_pct": pct(storst, len(ids)), "isolerte": isolerte,
            "samfunn": [18, 20], "samfunn_20": [11, 12], "modularitet": 0.45,
            "nmi": [{"namn": a, "lo": b, "hi": c} for a, b, c in nmi],
            "same_land": {"observert": 34.1, "venta": 26.2}}
    tal = [T("siteringar-7", "Verk i koplingsnettverket", len(ids)), T("siteringar-7", "Kantar", n_kant),
           T("siteringar-7", "Verk i det store nettverket", storst), T("siteringar-7", "Isolerte verk", isolerte),
           T("siteringar-7", "Del i det store nettverket, prosent", data["storst_pct"]),
           T("siteringar-8", "NMI mot kjelde, lågast", 0.12), T("siteringar-8", "NMI mot kjelde, høgast", 0.15),
           T("siteringar-8", "Kantar mellom verk med same første land, prosent", 34.1),
           T("siteringar-8", "Venta ved tilfeldige par, prosent", 26.2)]
    return data, tal


# ---- Seksjon 5: tema og kart ---------------------------------------------------------------------------

# tema-8: share of the period (percent) per cluster of the k=10 full-text analysis, 2005-09 .. 2020-24
KLYNGE_TREND = {0: [5.4, 7.2, 12.1, 15.0], 1: [18.0, 7.0, 9.6, 11.9], 2: [7.2, 10.9, 14.4, 10.7], 3: [4.5, 5.2, 10.7, 11.7],
                4: [3.2, 6.4, 8.6, 11.9], 5: [13.5, 9.3, 11.8, 8.0], 6: [25.2, 20.8, 8.4, 3.8], 7: [4.5, 13.6, 10.2, 7.3],
                8: [10.8, 13.8, 8.2, 7.5], 9: [7.7, 5.8, 6.0, 12.3]}
KLYNGE_RETNING = {0: "veks", 3: "veks", 4: "veks", 9: "veks", 5: "fell", 6: "fell", 8: "fell", 1: "ingen", 2: "ingen", 7: "ingen"}
TEMA_PER = [("2000–04", 2000, 2004), ("2005–09", 2005, 2009), ("2010–14", 2010, 2014), ("2015–19", 2015, 2019), ("2020–24", 2020, 2024)]


@figur("d18", "tema", "Kartet over alle verka",
       "Korleis ligg verka i eit semantisk kart, og kor mange tema er det?", "prikkart",
       "Alle 6 432 verk, eitt per prikk; tittel og samandrag som vektorar. Kartfana sin eigen serie (åtte klynger), ikkje kontrollert av dei verifiserte funna og ikkje dei ti klyngene i metastudien.",
       [])
def d18(ctx: Ctx):
    k = ctx.kart
    n = len(k["ids"])
    kl = []
    for c in k["klynger"]:
        idx = [i for i in range(n) if k["k"][i] == c["id"]]
        nord = sum(1 for i in idx if k["f"][i] & 4)
        kl.append({"id": c["id"], "namn": c["namn"], "n": c["n"], "lx": c["lx"], "ly": c["ly"], "farge": c["farge"],
                   "ord": c["ord"][:5], "nordisk_sprak": pct(nord, len(idx))})
    ids = k["ids"]
    add_by = {a["id"]: a for a in ctx.add}
    land_k, per_k, lag_k = [], [], []
    for i in range(n):
        w = ctx.W.get(ids[i])
        if w is not None:
            nn = w["an"]
            land_k.append(NORD.index(nn[0]) if len(nn) == 1 else (5 if len(nn) > 1 else 6))
            per_k.append(w["per"])
            lag_k.append(0)
        else:
            a = add_by[ids[i]]
            land_k.append(NORD.index(a["source_country"]) if a["source_country"] in NORD else 6)
            per_k.append(periode(a["year"]))
            lag_k.append(1)
    sp_oa = sum(1 for i in range(n) if lag_k[i] == 0 and k["f"][i] & 4)
    sp_ark = sum(1 for i in range(n) if lag_k[i] == 1 and k["f"][i] & 4)
    n_oa = lag_k.count(0)
    data = {"land": land_k, "per": per_k, "lag": lag_k, "periodar": PER_NAMN,
            "sprak": {"oa": sp_oa, "ark": sp_ark, "n_oa": n_oa, "n_ark": n - n_oa,
                      "oa_pct": pct(sp_oa, n_oa), "ark_pct": pct(sp_ark, n - n_oa)},
            "x": k["x"], "y": k["y"], "k": k["k"], "f": k["f"], "skala": k["skala"], "klynger": kl,
            "flagg": k["flagg"], "lenkje": "../index.html#kart?k=",
            "silhuett": k["tal"]["silhuett"], "silhuett_null": k["tal"]["silhuett_null"],
            "grense_del": k["tal"]["grense_del"], "nordisk_sprak_del_alle": k["tal"]["nordisk_sprak_del_alle"]}
    tal = [T(None, "Verk i kartet", n, kjelde="kart"), T(None, "Klynger i kartet", len(kl), kjelde="kart"),
           T(None, "Silhuett", k["tal"]["silhuett"], kjelde="kart"), T(None, "Silhuett, tilfeldig datasky", k["tal"]["silhuett_null"], kjelde="kart"),
           T(None, "Del nær klyngegrensa", k["tal"]["grense_del"], kjelde="kart")]
    return data, tal


@figur("d19", "tema", "Svak struktur, og kva som forklarer variasjonen",
       "Er kartet ti skilde fag, og kva forklarer variasjonen i tekstane?", "stolpar",
       "3 263 verk med fulltekst (delmengd av dei 3 272 i f01) i metastudiens klyngeanalyse (ti klynger A–J, ikkje kartets åtte): 2 447 OpenAlex-verk og 816 arkivverk. Tekstvektorar.",
       ["tema-4", "tema-6", "tema-7", "tema-10", "vekting-7"])
def d19(ctx: Ctx):
    t = RUNDE1["tema_forklaring"]
    data = {"silhuett": {"observert": t["silhuett"][0], "tilfeldig": t["silhuett"][1]}, "midt_mellom": t["midt_mellom"],
            "r2": [{"namn": a, "pct": b} for a, b in t["justert_r2"]],
            "r2_same": [{"namn": a, "pct": b} for a, b in t["same_1435"]],
            "klynge8": {"nordisk": t["klynge8_sprak"][0], "alle": t["klynge8_sprak"][1], "n": t["klynge8_n"]},
            "utval_periode": [["2005–09", 36.7], ["2010–14", 41.1], ["2015–19", 53.0], ["2020–24", 66.9]],
            "utval_sprak": [["norsk", 97.2], ["engelsk", 50.7]], "nordisk_samla": [83.3, 169, 203], "utval_type": [["bokkapittel", 17.3], ["artikkel", 58.3]],
            "verk": 3263}
    tal = [T("tema-4", "Silhuett", t["silhuett"][0]), T("tema-4", "Silhuett, tilfeldig datasky", t["silhuett"][1]),
           T("tema-4", "Verk nær to klyngesenter, prosent", t["midt_mellom"]), T("tema-4", "Verk med fulltekst", 3263),
           T("tema-6", "Klynge 8, nordisk språk, prosent", t["klynge8_sprak"][0]), T("tema-6", "Alle verk, nordisk språk, prosent", t["klynge8_sprak"][1]),
           T("tema-6", "Verk i klynge 8", t["klynge8_n"]),
           T("tema-7", "Utval 2005–09, prosent", 36.7), T("tema-7", "Utval 2020–24, prosent", 66.9),
           T("tema-7", "Norskspråklege med, prosent", 97.2), T("tema-7", "Engelskspråklege med, prosent", 50.7),
           T("tema-7", "Bokkapittel med, prosent", 17.3), T("tema-7", "Artiklar med, prosent", 58.3),
           T("vekting-7", "Nordiskspråklege med, prosent", 83.3), T("vekting-7", "Nordiskspråklege med, verk", 169),
           T("vekting-7", "Nordisk-merkte verk", 203),
           T("tema-10", "Ti klynger, justert R2, prosent", 14.01), T("tema-10", "Kanal, justert R2, prosent", 8.9),
           T("tema-10", "Land, justert R2, prosent", 1.44), T("tema-10", "Periode, justert R2, prosent", 1.16),
           T("tema-10", "Lag, justert R2, prosent", 0.33), T("tema-10", "Språk, same verk, prosent", 4.6)]
    return data, tal


@figur("d20", "tema", "Emne og klynger over tid",
       "Kor skeivt fordeler OpenAlex emna, og kva tema veks eller fell?", "stabla område og skråstrek",
       "OpenAlex-emne for 4 690 verk (2000–2024: 4 076 verk, 13 emne med minst 30 verk). Klyngeandelar i fulltekstutvalet, 2 842 verk 2005–2024. Emnenamn er OpenAlex sine.",
       ["tema-1", "tema-2", "tema-8"])
def d20(ctx: Ctx):
    oa = ctx.oa_list()
    med = [w for w in oa if w["topic"]]
    cnt = collections.Counter(w["topic"] for w in med)
    topp = [{"namn": k, "n": v, "pct": pct(v, len(med))} for k, v in cnt.most_common(8)]
    vin = [w for w in med if 2000 <= w["year"] <= 2024]
    ctot = collections.Counter(w["topic"] for w in vin)
    emne = [k for k, v in ctot.most_common() if v >= 30]
    per_n = []
    del_per = {k: [] for k in emne}
    for _, a, b in TEMA_PER:
        ws = [w for w in vin if a <= w["year"] <= b]
        per_n.append(len(ws))
        c = collections.Counter(w["topic"] for w in ws)
        for k in emne:
            del_per[k].append(pct(c[k], len(ws)))
    endrar = ["Usability and User Interface Design", "Interactive and Immersive Displays", "Crafts, Textile, and Design",
              "Sustainable Design and Development", "Art Education and Development", "Posthumanist Ethics and Activism",
              "Cultural and Historical Studies"]
    kl = RUNDE1["klyngeandelar"]
    kluster = [{"id": i, "namn": kl["namn"][i], "del": KLYNGE_TREND[i], "retning": KLYNGE_RETNING[i], "n": kl["storleik"][i]}
               for i in range(10)]
    data = {"topp": topp, "emne_n": len(med), "ulike_emne": len(cnt), "topp5_pct": pct(sum(v for _, v in cnt.most_common(5)), len(med)),
            "domene": {"fysiske": [3145, 67.1], "sosiale": [1432, 30.5]}, "mekanisk": [1741, 1759],
            "emne": [{"namn": k, "del": del_per[k], "endrar": 1 if k in endrar else 0, "n": ctot[k]} for k in emne],
            "periodar": [p[0] for p in TEMA_PER], "periode_n": per_n, "rikdom_300": [52.4, 60.8, 63.9, 67.2],
            "klyngeperiodar": kl["periodar"], "klyngenemnar": kl["nemnar"], "klynger": kluster}
    dep = del_per["Design Education and Practice"]
    us = del_per["Usability and User Interface Design"]
    tal = [T("tema-1", "Ulike emne", len(cnt)), T("tema-1", "Verk med emne", len(med)),
           T("tema-1", "Design Education and Practice, verk", cnt["Design Education and Practice"]),
           T("tema-1", "Design Education and Practice, prosent", topp[0]["pct"]), T("tema-1", "Dei fem største, prosent", data["topp5_pct"]),
           T("tema-1", "Under Mechanical Engineering", 1741), T("tema-1", "Physical Sciences, verk", 3145),
           T("tema-1", "Physical Sciences, prosent", 67.1),
           T("tema-2", "Emne med minst 30 verk", len(emne)),
           T("tema-2", "Usability 2000–04, prosent", us[0]), T("tema-2", "Usability 2020–24, prosent", us[4]),
           T("tema-2", "Design Education and Practice 2000–04, prosent", dep[0]),
           T("tema-2", "Design Education and Practice 2020–24, prosent", dep[4]),
           T("tema-2", "Ulike emne i utval på 300, 2005–09", 52.4), T("tema-2", "Ulike emne i utval på 300, 2020–24", 67.2),
           T("tema-8", "Utdanning 2005–09, prosent", KLYNGE_TREND[0][0]), T("tema-8", "Utdanning 2020–24, prosent", KLYNGE_TREND[0][3]),
           T("tema-8", "Arkitektur og kunst 2005–09, prosent", KLYNGE_TREND[6][0]), T("tema-8", "Arkitektur og kunst 2020–24, prosent", KLYNGE_TREND[6][3]),
           T("tema-8", "Spekulative framtider 2005–09, prosent", KLYNGE_TREND[4][0]), T("tema-8", "Spekulative framtider 2020–24, prosent", KLYNGE_TREND[4][3]),
           T("tema-8", "Byar og berekraft 2005–09, prosent", KLYNGE_TREND[3][0]), T("tema-8", "Byar og berekraft 2020–24, prosent", KLYNGE_TREND[3][3]),
           T("tema-8", "Handverk 2005–09, prosent", KLYNGE_TREND[9][0]), T("tema-8", "Handverk 2020–24, prosent", KLYNGE_TREND[9][3]),
           T("tema-8", "Norskspråkleg tekst 2005–09, prosent", KLYNGE_TREND[8][0]), T("tema-8", "Norskspråkleg tekst 2020–24, prosent", KLYNGE_TREND[8][3]),
           T("tema-8", "Deltaking og helse 2005–09, prosent", KLYNGE_TREND[5][0]), T("tema-8", "Deltaking og helse 2020–24, prosent", KLYNGE_TREND[5][3])]
    return data, tal


# ---- Seksjon 6: omgrep ---------------------------------------------------------------------------------

@figur("d21", "omgrep", "Breidde og ankerdel for omgrep",
       "Kor mange tekstar bruker eit omgrep, og siterer dei same verket når dei gjer det?", "spreiingsplott",
       "Breidde: 1 043 engelske fulltekstar 2020–25 (design thinking 317 av 1 043 = 30,4). Ankerdel: brukartekstar med referanseliste (78 for wicked problem); eit golv, fordi same verk ligg under fleire id-ar.",
       ["omgrep-4", "omgrep-5"])
def d21(ctx: Ctx):
    o = RUNDE1["omgrep"]
    bre = {k: v for k, v in o["breidde"]}
    spenn = {k: (lo, hi) for k, lo, hi in o["breidde_spenn"]}
    anker = {k: v for k, v in o["anker"]}
    begge, berre_x, berre_y = [], [], []
    for k in sorted(set(bre) | set(spenn) | set(anker)):
        x = bre.get(k)
        sp = spenn.get(k)
        y = anker.get(k)
        post = {"namn": k}
        if x is not None:
            post["x"] = x
        if sp:
            post["x_lo"], post["x_hi"] = sp
        if y is not None:
            post["y"] = y
        har_x = x is not None or sp is not None
        (begge if har_x and y is not None else berre_x if har_x else berre_y).append(post)
    data = {"begge": begge, "berre_breidde": berre_x, "berre_anker": berre_y,
            "x_namn": "Del av engelske fulltekstar 2020–25 som bruker omgrepet, prosent",
            "y_namn": "Del av brukartekstane som siterer same anker, prosent",
            "anker_tittel": {"wicked problem": "Rittel og Webber 1973"}}
    tal = [T("omgrep-4", "design process, breidde", 72), T("omgrep-4", "Breidde speculative design til universal design, nedre", 3),
           T("omgrep-4", "Breidde speculative design til universal design, øvre", 10),
           T("omgrep-4", "design research, breidde 2020–25", 51), T("omgrep-4", "design thinking, breidde 2020–25", 30),
           T("omgrep-4", "interaction design, breidde 2020–25", 27),
           T("omgrep-5", "wicked problem, ankerdel", 48.7), T("omgrep-5", "wicked problem, tekstar", 78),
           T("omgrep-5", "embodied interaction, ankerdel", 51.3), T("omgrep-5", "soma design, ankerdel", 54.3),
           T("omgrep-5", "speculative design, ankerdel", 44.9), T("omgrep-5", "reflective practice, ankerdel", 36.0),
           T("omgrep-5", "design process, ankerdel", 9.7), T("omgrep-5", "design research, ankerdel", 11.6)]
    return data, tal


@figur("d22", "omgrep", "Kva som stig og fell, og kvar omgrep først syner seg",
       "Kva omgrep har endra del mellom periodane, og følgjer første framtreding dekninga?", "stolpar og punktpar",
       "Engelske samandrag i OpenAlex-laget (om lag 3 700 verk). Terskel |z| minst 4 og minst dobbel del; nettside-rusk fjerna. Første framtreding følgjer kor mange verk som finst, og er ikkje første bruk.",
       ["omgrep-2", "omgrep-3"])
def d22(ctx: Ctx):
    data = {"overgangar": [{"namn": "≤2009 til 2010–14", "opp": 2, "ned": 0}, {"namn": "2010–14 til 2015–19", "opp": 0, "ned": 0},
                           {"namn": "2015–19 til 2020–25", "opp": 12, "ned": 4}],
            "lang_bogen": {"opp": [40, 46], "ned": [17, 18], "namn": "≤2014 til 2020–25"},
            "dome": [{"namn": "more-than-human", "fra": 1, "til": 52}, {"namn": "speculative", "fra": 10, "til": 78},
                     {"namn": "interaction design", "fra": 153, "til": 64, "fra_n": 1025, "til_n": 1491,
                      "fra_pct": 14.9, "til_pct": 4.3}],
            "forste": {"termar_pct": [12, 81, 6], "periodar": ["før 2000", "2000–14", "etter 2014"],
                       "verk": [21, 1000, 2430], "verk_namn": ["1995–99", "2000–14", "2015–25"]},
            "forste_dome": [{"namn": "design research", "ar": 1991, "verk": 4}, {"namn": "participatory design", "ar": 1998, "verk": 23}]}
    tal = [T("omgrep-2", "Stigande uttrykk til 2010–14", 2), T("omgrep-2", "Stigande uttrykk til 2020–25", 12),
           T("omgrep-2", "Fallande uttrykk til 2020–25", 4),
           T("omgrep-2", "more-than-human, frå", 1), T("omgrep-2", "more-than-human, til", 52),
           T("omgrep-2", "speculative, frå", 10), T("omgrep-2", "speculative, til", 78),
           T("omgrep-2", "interaction design, frå", 153), T("omgrep-2", "interaction design, til", 64),
           T("omgrep-2", "interaction design, del frå, prosent", 14.9), T("omgrep-2", "interaction design, del til, prosent", 4.3),
           T("omgrep-3", "Første framtreding før 2000, prosent", 12), T("omgrep-3", "Første framtreding 2000–14, prosent", 81),
           T("omgrep-3", "Første framtreding etter 2014, prosent", 6),
           T("omgrep-3", "Verk med engelsk samandrag 1995–99", 21), T("omgrep-3", "Verk med engelsk samandrag 2015–25", 2430),
           T("omgrep-3", "design research første gong", 1991), T("omgrep-3", "participatory design første gong", 1998)]
    return data, tal


# ---- Seksjon 7: kunnskapsformer -----------------------------------------------------------------------

@figur("d23", "kunnskap", "Kunnskapsformer: kor mange, kva som lèt seg måle, og kva som heng saman",
       "Kva støtteformer bruker tekstane, og kva av dei lèt seg måle med markørar?", "intervall, kappa og matrise",
       "2 176 engelske OpenAlex-tekstar med fulltekst. Lesing av 80 tekstar (prosentane er vekta; phi er uvekta tal på tekstar) av éin kodar; markørtest på 40 tekstar. Kodebokrekkjefølgje, ikkje rangert.",
       ["kunnskapsformer-1", "kunnskapsformer-2", "kunnskapsformer-3", "kunnskapsformer-4", "kunnskapsformer-5"])
def d23(ctx: Ctx):
    f = RUNDE1["former"]
    former = [{"kode": f["kode"][i], "namn": f["namn"][i], "lesing": f["lesing_pct"][i], "lo": f["lesing_ci"][i][0],
               "hi": f["lesing_ci"][i][1], "kappa": f["kappa"][i], "malbar": 1 if f["kode"][i] == "data_collection" else 0,
               "grense": 1 if f["kode"][i] == "argument" else 0,
               "ustabil": 1 if f["kode"][i] == "modelling" else 0} for i in range(len(f["kode"]))]
    mk = f["marker"]
    data = {"former": former,
            "marker": {"datainnsamling": {"k": mk["data_collection"][0], "n": mk["data_collection"][1],
                                          "pct": pct(mk["data_collection"][0], mk["data_collection"][1]),
                                          "lo": mk["data_collection"][2], "hi": mk["data_collection"][3]},
                       "argument": {"k": mk["argument"][0], "n": mk["argument"][1], "pct": pct(mk["argument"][0], mk["argument"][1]),
                                    "lo": mk["argument"][2], "hi": mk["argument"][3]}},
            "justert_datainnsamling": f["justert_datainnsamling"], "kappa_data_ci": f["kappa_ci_data"],
            "presisjon": f["presisjon_data"], "gjenfinning": f["gjenfinning_data"],
            "phi": [{"a": a, "b": b, "n": n, "phi": p} for a, b, n, p in f["phi"]], "kodar": f["kode"],
            "per_tekst": f["per_tekst"], "populasjon": 2176, "oa": 4694}
    tal = [T("kunnskapsformer-1", "Tekstar i målinga", 2176), T("kunnskapsformer-1", "OpenAlex-verk", 4694),
           T("kunnskapsformer-2", "Kappa, datainnsamling", 0.75), T("kunnskapsformer-2", "Kappa-intervall, nedre", 0.52),
           T("kunnskapsformer-2", "Kappa-intervall, øvre", 0.95), T("kunnskapsformer-2", "Presisjon", 0.83),
           T("kunnskapsformer-2", "Gjenfinning", 0.95), T("kunnskapsformer-2", "Kappa, argument", 0.48),
           T("kunnskapsformer-3", "Markørar for datainnsamling", 1264), T("kunnskapsformer-3", "Del med markørar, prosent", 58.1),
           T("kunnskapsformer-3", "Lesing av 80, datainnsamling, prosent", 56.1),
           T("kunnskapsformer-3", "Lesing, nedre grense", 43.8), T("kunnskapsformer-3", "Lesing, øvre grense", 68.4),
           T("kunnskapsformer-3", "Justert, om lag, prosent", 50.8), T("kunnskapsformer-3", "Argument-markør", 882),
           T("kunnskapsformer-5", "Tekstar med tre eller fleire", 49),
           T("kunnskapsformer-5", "Tekstar med éi form", 6), T("kunnskapsformer-5", "Tekstar utan form", 2),
           T("kunnskapsformer-5", "Designarbeid og praksisrefleksjon, saman", 14), T("kunnskapsformer-5", "Designarbeid og praksisrefleksjon, phi", 0.45),
           T("kunnskapsformer-5", "Datainnsamling og bruk i praksis, saman", 22), T("kunnskapsformer-5", "Datainnsamling og bruk i praksis, phi", 0.41),
           T("kunnskapsformer-5", "Litteratur og datainnsamling, saman", 31)]
    return data, tal


@figur("d24", "kunnskap", "Datainnsamlingsmarkørar over tid, etter kjelde og etter land",
       "Kor stor del av tekstane har markørar for datainnsamling, og kva skil gruppene?", "punkt med intervall",
       "2 176 engelske fulltekstar; berre denne forma lèt seg måle med markørar. Å ha samla inn data er ikkje det same som at ein påstand er støtta av dei. Kjelder med minst 40 tekstar.",
       ["kunnskapsformer-6", "kunnskapsformer-7", "kunnskapsformer-8"])
def d24(ctx: Ctx):
    f = RUNDE1["former"]

    def punkt(namn, n, k, lo, hi):
        return {"namn": namn, "n": n, "k": k, "pct": pct(k, n), "lo": lo, "hi": hi}

    data = {"periode": [punkt(*x) for x in f["periode"]],
            "for_etter": [{"namn": a, "n": n, "k": k, "pct": pct(k, n)} for a, n, k in f["for_etter_2015"]],
            "kjelde": [punkt(*x) for x in f["kjelde"]],
            "innan_kjelde": [{"namn": a, "for": b, "etter": c} for a, b, c in f["innan_kjelde"]],
            "land": [punkt(*x) for x in f["land_eitt"]]}
    fe = data["for_etter"]
    kj = {x["namn"]: x for x in data["kjelde"]}
    tal = [T("kunnskapsformer-6", "Før 2015, prosent", fe[0]["pct"]), T("kunnskapsformer-6", "Frå 2015, prosent", fe[1]["pct"]),
           T("kunnskapsformer-6", "FormAkademisk før 2015, prosent", 41.4), T("kunnskapsformer-6", "FormAkademisk frå 2015, prosent", 51.8),
           T("kunnskapsformer-6", "ServDes før 2015, prosent", 48.1), T("kunnskapsformer-6", "ServDes frå 2015, prosent", 54.7),
           T("kunnskapsformer-7", "Artifact, prosent", kj["Artifact"]["pct"]),
           T("kunnskapsformer-7", "Design Studies, prosent", kj["Design Studies"]["pct"]),
           T("kunnskapsformer-8", "Finsk tilknyting, prosent", data["land"][1]["pct"]),
           T("kunnskapsformer-8", "Dansk, norsk eller svensk, lågast", 53.8), T("kunnskapsformer-8", "Dansk, norsk eller svensk, høgast", 56.1)]
    return data, tal


# ---- Seksjon 8: teorielement --------------------------------------------------------------------------

@figur("d25", "teori", "Teorielement i pilotane: profil og pålitelegheit",
       "Kva viser dei tre pilotane om hovudpåstandar, støtte og om ei andre lesing finn det same?", "intervall og stolpar",
       "v0.1: 30 av 3 150 fulltekstar (315 påstandar). v0.3: 52 hovudpåstandar frå 22 lesbare av 23 CC-verk. 3 150 er ein delmengd av dei 3 272 fulltekstverka i f01. Éin modell som kodar, ikkje validert.",
       ["teorielement-1", "teorielement-2", "teorielement-3", "teorielement-4", "teorielement-6", "teorielement-7", "teorielement-8"])
def d25(ctx: Ctx):
    t = RUNDE1["teori"]
    data = {"utval": dict(t["utval"], lesbare=22, fulltekst_alle=3272), "kjerne_lag": t["kjerne_lag"], "kausal": t["kausal"], "stad": t["stad"], "eigne": t["eigne"],
            "stotte": t["stotte"], "omgrep": t["omgrep"], "to_omgrep": [{"namn": a, "k": k, "n": n, "pct": pct(k, n)} for a, k, n in t["to_omgrep"]],
            "teoriar": t["teoriar"], "att": t["att"],
            "gjenfinning": [{"namn": a, "k": k, "n": n, "pct": pct(k, n, 1)} for a, k, n in t["gjenfinning"]]}
    tal = [T("teorielement-1", "Registrerte CC-verk", 23), T("teorielement-1", "Fulltekstar i kjernen", 3150),
           T("teorielement-1", "CC-verk 2020–26", 17), T("teorielement-1", "CC-verk frå DIS", 9),
           T("teorielement-2", "Kjernen, del av registrerte, prosent", 49), T("teorielement-2", "Kjernen, registrerte verk", 6432),
           T("teorielement-2", "Avhandlingar og bøker i OpenAlex-laget, prosent", 22),
           T("teorielement-2", "Avhandlingar og bøker i arkivlaget, prosent", 67),
           T("teorielement-3", "causes_or_enables v0.1, prosent", 31), T("teorielement-3", "causes_or_enables v0.1, påstandar", 315),
           T("teorielement-3", "causes_or_enables v0.3, prosent", 56), T("teorielement-3", "causes_or_enables v0.3, påstandar", 52),
           T("teorielement-4", "I konklusjonen, prosent", 46), T("teorielement-4", "I samandraget, prosent", 31),
           T("teorielement-4", "I innleiinga, prosent", 23), T("teorielement-4", "Tekstens eigne, prosent", 94),
           T("teorielement-4", "Støtte oppgjeve, prosent", 27), T("teorielement-4", "Støtte ikkje oppgjeve, prosent", 71),
           T("teorielement-4", "Unike omgrep", 104), T("teorielement-4", "Omgrep funne definerte", 8),
           T("teorielement-4", "Gyldigheitsområde oppgjeve", 4),
           T("teorielement-6", "To omgrep per påstand v0.1", 304), T("teorielement-6", "To omgrep per påstand v0.3", 44),
           T("teorielement-7", "Påstandar funne att", 35), T("teorielement-7", "Samanhengstype lik", 30),
           T("teorielement-7", "Støttestatus lik", 24), T("teorielement-7", "Gjenfinning samandrag", 14),
           T("teorielement-7", "Gjenfinning konklusjon", 16), T("teorielement-7", "Gjenfinning innleiing", 5),
           T("teorielement-8", "causes_or_enables, andre lesing, prosent", 45), T("teorielement-8", "Skilnad, poeng", -10.9)]
    return data, tal


# ---- Seksjon 9: dei femten nye spørsmåla ------------------------------------------------------------

def _rad(namn, eining, akse, venta, obs, *, tilnaerma=False, modus=None, avleidd=False, ordtal=False, venta_ord=False, merknad=None):
    """One expectation-against-outcome strip. ``venta`` is (lo, hi) with None for an open end; ``obs`` is a list of
    marks {v, lo?, hi?, namn?}. The verdict of the strip is computed here, never typed:
    treff when every mark lies inside the expected range, bom when every mark lies outside, open otherwise."""
    lo, hi = venta
    a, b = akse
    if tilnaerma:
        # a single expected value ("om lag 55"): the band is the stated value plus and minus 5 points
        band = (lo - 5, lo + 5)
    else:
        band = (a if lo is None else lo, b if hi is None else hi)

    def inne(m):
        v0, v1 = m.get("lo", m["v"]), m.get("hi", m["v"])
        if v0 >= band[0] and v1 <= band[1]:
            return 1
        if v1 < band[0] or v0 > band[1]:
            return -1
        return 0

    d = [inne(m) for m in obs]
    if all(x == 1 for x in d):
        dom = "treff"
    elif all(x == -1 for x in d):
        dom = "bom"
    elif modus == "alle" and any(x == -1 for x in d):
        dom = "bom"
    else:
        dom = "open"
    rad = {"namn": namn, "eining": eining, "akse": [a, b], "venta": {"lo": lo, "hi": hi, "tilnaerma": 1 if tilnaerma else 0},
           "obs": obs, "dom": dom}
    if modus:
        rad["modus"] = modus
    if avleidd:
        rad["avleidd"] = 1
    if ordtal:
        rad["ordtal"] = 1  # the text spells the number out
    if venta_ord:
        rad["venta_ord"] = 1  # the expectation is a comparison in words; the bound is its numeric form
    if merknad:
        rad["merknad"] = merknad
    return rad


def _m(v, lo=None, hi=None, namn=None, mid=False):
    m = {"v": v}
    if mid:
        m["mid"] = 1  # v is the middle of a stated range; only lo and hi are stated
    if lo is not None:
        m["lo"] = lo
    if hi is not None:
        m["hi"] = hi
    if namn:
        m["namn"] = namn
    return m


NEMNAR_SPORSMAL = {'eininga-1': '2 334 utanforståande av 24 812 rader; mellomdelen: forfattarar med minst to verk', 'eininga-2': '6 033 forfattarar i scope; dei to første stripane: forfattarar med minst fem verk', 'eininga-3': '109 116 referansar frå scope; 20 118 utanforverk', 'eininga-4': 'Kanalar med minst 30 verk: 688 av 3 978 verk (begge lag). Nordes i odde år: 221 av 221 i OpenAlex-laget', 'eininga-5': '6 033 forfattarar; institusjonar og land som eigne nett', 'skilja-1': '2 334 utanforståande; midten: 4 949 forfattarar (verk som eining)', 'skilja-2': '3 295 verk 2005 til 2022; 653 utan siteringar', 'skilja-3': 'Fulltekstar; ordtettleik for datainnsamling, praksis og argument', 'skilja-4': 'Språk målt på teksten sjølv; arkivlaget berre fulltekstar', 'skilja-5': '4 080 verk; 29 kanalar med minst 20 verk; 1 278 verk i mindre kanalar kan ikkje vurderast', 'tida-1': '1 981 verk; 254 stayarar og 58 bærarar; 30 ord', 'tida-2': 'Element sitert av minst 8 ulike verk', 'tida-3': '2 754 forfattarar, 1 201 med dedikert inngang', 'tida-4': '6 033 forfattarar; 2 822 med verk på begge sider', 'tida-5': 'Forfattarar per utgåve i fem arenaer; små nemnarar for grunnleggjarane'}

NYE_SPORSMAL = [
    ("eininga-1", "Eininga", "Er «nordisk» ein gradient på personnivå?", [
        _rad("Utanforståande med nordisk rad elles", "prosent", (0, 50), (20, 40), [_m(6.1)], merknad="Øvre grense 23,3 om alle 401 utan landfelt var nordiske."),
        _rad("Mellomdelen (0,2 til 0,8) blant dei med minst to verk", "prosent", (0, 30), (15, None), [_m(11.0, 6.2, 11.0)])]),
    ("eininga-2", "Eininga", "Går feltgrensa gjennom personane?", [
        _rad("Reine i scope, forfattarar med minst fem verk", "prosent", (0, 50), (None, 30), [_m(2.4)]),
        _rad("Median del av verka i scope", "del", (0, 1), (0.3, 0.6), [_m(0.33)]),
        _rad("Forfattarplassar haldne av personar med under halvparten i scope", "prosent", (0, 60), (30, 50),
             [_m(27.7, namn="alle"), _m(41.7, namn="minst tre verk")])]),
    ("eininga-3", "Eininga", "Kor mange verk utanfor porten blir refererte frå scope?", [
        _rad("Referansar per mottakarverk, scope mot utanfor", "gonger", (0, 8), (3, None), [_m(5.9)]),
        _rad("Utanforverk refererte frå scope", "prosent", (0, 30), (10, 20), [_m(8.5)]),
        _rad("Utanforverk med minst fem siterande utan designord i tittelen", "prosent", (0, 100), (50, None), [_m(58.5, 58, 59, mid=True)]),
        _rad("Referansar til utanforverk mot til scope", "forhold", (0, 3), (1, None), [_m(0.73)], avleidd=True, venta_ord=True)]),
    ("eininga-4", "Eininga", "Kor mykje sagtann gir kanalar som kjem annakvart år?", [
        _rad("Nordes-verk i odde år, OpenAlex-laget (arkivlaget 95)", "prosent", (0, 100), (90, None), [_m(100)], avleidd=True),
        _rad("Delen av verka i skeive kanalar (minst 30 verk)", "prosent", (0, 40), (15, 30), [_m(17.3, 17.3, 21.1)]),
        _rad("Tal skeive kanalar med minst 30 verk", "tal", (0, 10), (5, None), [_m(4)], ordtal=True)]),
    ("eininga-5", "Eininga", "Kor samanhengande er medforfattarnettet etter eining?", [
        _rad("Største forfattarkomponent", "prosent", (0, 100), (25, 45), [_m(59.3, namn="observert"), _m(82.0, namn="nullmodell")], modus="alle"),
        _rad("Største institusjonskomponent", "prosent", (0, 100), (80, None), [_m(94.4)]),
        _rad("Medforfattarpar som skriv saman i fleire verk", "prosent", (0, 30), (None, 25), [_m(12.2)])]),
    ("skilja-1", "Skilja", "Er «nordisk» ein tilstand hos ein person?", [
        _rad("Utanforståande med nordisk linje i samanlikningsverk", "prosent", (0, 50), (20, 35), [_m(6.1)]),
        _rad("Nordisk linje fyrr eller same år som første korpusverk", "prosent", (0, 100), (55, 55), [_m(58)], tilnaerma=True),
        _rad("Midten (minst 15 %), to måtar å telje", "prosent", (0, 40), (15, None), [_m(8.2, namn="verk som eining"), _m(22, namn="eitt land per linje")])]),
    ("skilja-2", "Skilja", "Er «usitert» ein eigen kategori?", [
        _rad("Observerte nullar mot utleidd", "gonger", (0, 3), (1.2, 1.6), [_m(1.32, 0.89, 1.98)]),
        _rad("Risikoforhold for null siteringar utan DOI", "forhold", (0, 3), (2, None), [_m(1.92, 1.51, 1.92)])]),
    ("skilja-3", "Skilja", "Ligg tekstar langs ei akse frå empirisk til konseptuell?", [
        _rad("Datainnsamling mot argument (Spearman)", "rho", (-0.5, 0.5), (-0.20, 0.10), [_m(-0.21, -0.25, -0.17)]),
        _rad("Datainnsamling mot praksis (Spearman)", "rho", (-0.2, 0.5), (0.15, None), [_m(0.09)]),
        _rad("Første hovudkomponent", "prosent", (20, 70), (None, 45), [_m(41.9, 40.2, 43.7)]),
        _rad("Éin topp i datainnsamling (Sarle)", "indeks", (0.3, 0.8), (None, 0.555), [_m(0.50)]),
        _rad("Datainnsamlingstoppen som òg er argumenttopp", "prosent", (0, 60), (25, None), [_m(22.1)]),
        _rad("I botn på alle tre", "prosent", (0, 20), (8, None), [_m(3.5)])]),
    ("skilja-4", "Skilja", "Er språk ei merking på verket?", [
        _rad("Nordisk-merkte med minst 10 % engelske sider", "prosent", (0, 100), (60, None), [_m(25.5, 21, 30, mid=True)]),
        _rad("Engelskmerkte med over 10 % skandinavisk", "prosent", (0, 6), (None, 3), [_m(0.4, 0.3, 0.5, mid=True)]),
        _rad("Skandinavisk del i arkivlaget", "prosent", (0, 100), (30, 55), [_m(30.5)]),
        _rad("Midten (10 til 90 % skandinavisk) av fulltekstane", "prosent", (0, 10), (5, None), [_m(3.4, 1.6, 5.2, mid=True)])]),
    ("skilja-5", "Skilja", "Er artikkel mot konferanse ein eigenskap ved teksten eller kanalen?", [
        _rad("Verk i kanalar med over 90 % same kind", "prosent", (0, 100), (85, None), [_m(95.9, namn="av dei 29 kanalane"), _m(65.9, namn="av alle 4 080")], merknad="95,9 % av verka i dei 29 kanalane med minst 20 verk, men 65,9 % av alle 4 080 verk."),
        _rad("Kanalar med begge slaga over 10 %", "tal", (0, 6), (3, None), [_m(2)], ordtal=True),
        _rad("AUC for kind frå lengd, referansar og forfattarar", "AUC", (0.5, 0.9), (0.60, 0.75), [_m(0.73, namn="alle tre"), _m(0.71, namn="lengd")])]),
    ("tida-1", "Tida", "Endrar folk seg, eller kjem andre folk?", [
        _rad("Median innanfor-del av endringa", "del", (0, 1), (None, 0.35), [_m(0.79, 0.66, 0.79)]),
        _rad("Interaction design: stayarane sin seine del mot den tidlege", "forhold", (0, 1.5), (0.6, None), [_m(0.31)], venta_ord=True),
        _rad("Erstatningsord: bærarar mot andre stayarar", "forhold", (0, 2), (None, 1.5), [_m(0.82, 0.82, 1.41)], avleidd=True)]),
    ("tida-2", "Tida", "Ligg siteringar til same element i bølgjer?", [
        _rad("Holår mot nullmodell", "forhold", (0.5, 1.5), (1.2, None), [_m(0.973, 0.961, 0.985)]),
        _rad("Element med hol på minst tre år", "prosent", (0, 60), (None, 15), [_m(40.5)]),
        _rad("Bøker blant element med tilbakekomst", "forhold", (0.5, 2), (1.2, None), [_m(1.14)])]),
    ("tida-3", "Tida", "Avgjer inngangen om ein blir?", [
        _rad("(a) Auke i delen som kjem att, dedikert inngang", "poeng", (-3, 10), (5, None), [_m(4.6, 1.8, 7.3)]),
        _rad("(b) Same skilnad på heile tabellen", "poeng", (-3, 10), (None, 5), [_m(1.8, -1.7, 5.3)]),
        _rad("(c) Blanding av vegane mot nullmodell", "forhold", (0.4, 1.2), (None, 0.8), [_m(0.65)])]),
    ("tida-4", "Tida", "Kjem utanforverket først?", [
        _rad("Minst fem verk: utanfor først, observert minus null", "poeng", (-5, 10), (3, None), [_m(3.6, -1.2, 6.9)]),
        _rad("Eitt verk: skilnaden frå null", "poeng", (-5, 10), (-3, 3), [_m(-0.4)])]),
    ("tida-5", "Tida", "Kor mange kjem att i same arena?", [
        _rad("Nordes, tilbakevendande frå 2015", "prosent", (0, 40), (25, None), [_m(26.8)]),
        _rad("Nordes minus DIS", "poeng", (-10, 12), (5, None), [_m(0.3, -5, 5)], avleidd=True),
        _rad("Grunnleggjarar att etter åtte år, fem arenaer", "prosent", (0, 40), (None, 20),
             [_m(16.4, namn="Nordes"), _m(15.9, namn="FormAkademisk"), _m(14.3, namn="DRS"), _m(22.6, namn="DIS"), _m(5.5, namn="ServDes")], modus="alle")]),
]


# Round 2: nine new questions (report 3.4). Expectation written before the measurement; the outcome of each
# question is the report's own verdict (uavgjort / nei / delvis / ja), not a sum of the strips.
NEMNAR_SPORSMAL2 = {
    "grenser-1": "FormAkademisk i OpenAlex-laget: 481 verk, 94 forfattarar med minst to verk; nullmodell: språkmerke blanda innan utgivingsår (2 000 trekk)",
    "grenser-2": "1 738 arkivverk, 1 652 utan tittelmatch i OpenAlex-laget (2 250 ulike namn); elleve Nordes-konferansar 2005 til 2025",
    "grenser-3": "Åtte kanalar med minst 25 verk i scope og 25 utanfor: 365 verk i scope og 1 722 utanforverk; AUC frå delte referansar",
    "tida-6": "17 kanalar med minst 10 verk i kvar halvdel av 2005 til 2024; 3 754 verk med kanal og primærtema (OpenAlex-laget)",
    "tida-7": "234 nye kanalar (første verk 2010 til 2017); minne for verk 2012 til 2024 med forfattar-id: 1 215 i nye kanalar, 1 776 i panelet",
    "tida-8": "3 757 verk 2005 til 2024 med kanal-id; 94 kanalar med minst fem verk; panel på 27 kanalar (OpenAlex-laget)",
    "skilja-6": "4 694 verk i OpenAlex-laget: 2 442 med verifisert open PDF mot 2 252 utan; 46 til 50 strata av kanalgruppe og periode",
    "skilja-7": "43 doktorpostar med dokument (41 ulike PDF-ar) mot 179 master og bachelor og 200 artiklar og konferansebidrag",
    "skilja-8": "FormAkademisk: 286 verk med minst ti oppføringar i referanselista (50 norske, 236 engelske)",
}

# (id, lens, title, strips, outcome, label)
NYE_SPORSMAL2 = [
    ("grenser-1", "Grenser", "Er FormAkademisk éi eining eller to forfattargrupper?", [
        _rad("Forfattarar med verk på båe språk (minst to verk)", "prosent", (0, 100), (None, 25), [_m(35.1)]),
        _rad("Forhold til nullgjennomsnittet, språkdeling", "forhold", (0, 1.2), (None, 0.6), [_m(0.57)]),
        _rad("Forhold til nullgjennomsnittet, periodedeling", "forhold", (0, 1.2), (0.57, None), [_m(0.65)], venta_ord=True,
             merknad="Venta nærare null enn språkdelinga (0,57); berre litt nærare.")], "undecided", None),
    ("grenser-2", "Grenser", "Deler laga folk eller berre verk?", [
        _rad("Nordes: arkivforfattarar som står i OpenAlex-laget", "prosent", (0, 100), (35, 60), [_m(33.4)]),
        _rad("NVA: same mål", "prosent", (0, 100), (None, 10), [_m(24.5)]),
        _rad("DiVA: same mål", "prosent", (0, 100), (10, 30), [_m(17.0)]),
        _rad("Alle arkiva samla: same mål", "prosent", (0, 100), (None, 25), [_m(24.2)]),
        _rad("Nordes delt på NVA", "gonger", (0, 4), (3, None), [_m(1.4)]),
        _rad("Konferansar med minst 75 % av verka i eitt lag (av elleve)", "tal", (0, 11), (7, None), [_m(2)], ordtal=True)], "failed", None),
    ("grenser-3", "Grenser", "Skil delte referansar verk i scope frå verk utanfor i same kanal?", [
        _rad("Median AUC over kanalar", "AUC", (0.4, 1.0), (0.58, 0.72), [_m(0.71)]),
        _rad("Kanalar med AUC under 0,80", "prosent", (0, 100), (80, None), [_m(75)]),
        _rad("Utanforverk med høgare likskap til scope enn til utanforverk", "prosent", (0, 100), (25, None),
             [_m(32.8, namn="vekta"), _m(37.2, namn="utan seriane")], modus="alle")], "undecided", None),
    ("tida-6", "Tida", "Har innhaldet i ein kanal flytta seg?", [
        _rad("Kanalar som flyttar seg ut over støynivået", "prosent", (0, 100), (35, 60), [_m(35.3)]),
        _rad("Kanalar nærare eigen tidlegare versjon enn andre sin seine", "prosent", (0, 100), (75, None),
             [_m(58.8, namn="seine mot seine"), _m(79.2, 76, 82.4, namn="tidleg mot andre sine seine", mid=True)]),
        _rad("Kanalar som flyttar seg mot nye kanalar", "prosent", (0, 100), (55, 70), [_m(47.1)]),
        _rad("Mot nye minus mot feltsnittet", "poeng", (-30, 30), (-10, 10), [_m(-5.8)], avleidd=True, venta_ord=True)], "undecided", None),
    ("tida-7", "Tida", "Er nye kanalar heimar eller besøk?", [
        _rad("Nye kanalar med berre eitt verk", "prosent", (0, 100), (55, 75), [_m(59.0)]),
        _rad("Nye kanalar med verk i to ulike år", "prosent", (0, 100), (20, 35), [_m(36.3)]),
        _rad("Nye kanalar med verk minst tre år etter første", "prosent", (0, 100), (10, 25), [_m(32.5)]),
        _rad("Forfattarar med tidlegare verk, nye kanalar", "prosent", (0, 100), (25, 40), [_m(83.5)]),
        _rad("Forfattarar med tidlegare verk, panelkanalar", "prosent", (0, 100), (40, 55), [_m(80.3)]),
        _rad("Einverkskanalar minus kanalar med minst tre verk", "poeng", (-30, 15), (-15, -5), [_m(-5.1, -14, 5)])], "failed", None),
    ("tida-8", "Tida", "Er open tilgang ein eigenskap ved verket, kanalen eller kanal-året?", [
        _rad("Kanalen forklarer variasjonen i open (ICC)", "del", (0, 1), (0.45, 0.65), [_m(0.392, 0.193, 0.54)]),
        _rad("Kanal-år legg til", "del", (0, 0.3), (None, 0.10), [_m(0.069)]),
        _rad("Verk i reine celler", "prosent", (0, 100), (45, None), [_m(49.7)]),
        _rad("Dei tre største kanalane bær av stigninga", "prosent", (0, 100), (50, None), [_m(57.1)]),
        _rad("Panelkanalar med endring på minst 40 poeng (av 27)", "tal", (0, 27), (4, 8), [_m(16)], ordtal=True),
        _rad("Panelkanalar innanfor pluss minus 10 poeng (av 27)", "tal", (0, 27), (8, None), [_m(4)], ordtal=True),
        _rad("Oddsforhold for open, seint mot tidleg, i blanda kanalar", "forhold", (0, 8), (1.5, 3.0), [_m(4.76, 3.48, 6.51)])], "failed", None),
    ("skilja-6", "Skilja", "Er «open» ei eigenskap ved teksten eller ved vegen teksten tok?", [
        _rad("Handverk-ord i samandrag, opne minus ikkje opne, ujustert", "poeng", (-6, 12), (3, 8), [_m(6.4)]),
        _rad("Same, forhold justert mot ujustert", "forhold", (0, 1.5), (None, 0.5), [_m(0.2)]),
        _rad("Ikkje-engelsk språkmerke, ujustert", "poeng", (-6, 12), (3, 8), [_m(5.5)]),
        _rad("Minst tre forfattarar, justert", "poeng", (-12, 12), (-8, -1), [_m(5.2, 2.3, 8.5)]),
        _rad("Minst 30 referansar, justert", "poeng", (-12, 12), (-8, -1), [_m(1.5, -2.2, 5.2)]),
        _rad("Null registrerte siteringar, justert", "poeng", (-20, 6), (-15, -5), [_m(-3.5, -5.9, -1.1)]),
        _rad("Mål der verk med uverifisert adresse ligg nærare dei opne (av sju)", "tal", (0, 7), (5, None), [_m(1)], ordtal=True)], "undecided", None),
    ("skilja-7", "Skilja", "Er ei doktoravhandling éi eining eller fleire tekstar bundne saman?", [
        _rad("Doktoravhandlingar med minst tre referanselister", "prosent", (0, 100), (35, 60),
             [_m(60.5, namn="førehandsordliste"), _m(65.1, namn="utvida ordliste")]),
        _rad("Master og bachelor med minst tre referanselister", "prosent", (0, 30), (None, 8), [_m(7.3, namn="førehandsordliste"), _m(8.9, namn="utvida ordliste")]),
        _rad("Artiklar og konferansebidrag med minst tre", "prosent", (0, 10), (None, 3), [_m(0.75, 0.5, 1.0, mid=True)]),
        _rad("Referanse- og paper-signalet stemmer", "prosent", (0, 100), (75, None), [_m(60.5, namn="førehandsordliste"), _m(65.1, namn="utvida ordliste")]),
        _rad("Median lengd, gonger master og bachelor", "gonger", (0, 4), (1.8, 3), [_m(2.4)]),
        _rad("Doktoravhandlingar kortare enn 75-persentilen for master og bachelor", "prosent", (0, 50), (15, None), [_m(11.6)])], "undecided", "delvis"),
    ("skilja-8", "Skilja", "Held språk ei skiljelinje mellom referanselister i same tidsskrift?", [
        _rad("Norsk mot engelsk delt på engelsk mot engelsk", "forhold", (0, 1.5), (0.3, 0.7), [_m(0.54), _m(0.63)], modus="alle"),
        _rad("Norsk mot norsk delt på engelsk mot engelsk", "forhold", (0, 4), (1.2, None), [_m(2.2), _m(2.4)], modus="alle"),
        _rad("Tidsforhold, tidlege mot seine engelske verk", "forhold", (0, 1.5), (0.7, 1.0), [_m(0.84), _m(0.83)], modus="alle"),
        _rad("Språkforholdet under tidsforholdet, skilnad", "forhold", (0, 0.6), (0.15, None), [_m(0.30), _m(0.20)], modus="alle"),
        _rad("Same mål med berre lister på minst 30, norsk mot engelsk", "forhold", (0, 1.5), (0.3, 0.7), [_m(1.13)])], "held", "som skilnad i grad"),
]


@figur("d26", "sporsmaal", "Forventing mot utfall, 24 nye spørsmål i to rundar",
       "Heldt forventinga som vart fastsett før målinga, og kor tydeleg?", "forventa intervall mot observert",
       "24 spørsmål, kvar forventing skriven ned før måling: 15 frå runde 1 og 9 frå runde 2 (rapport 3.4, kontrollert mot lagra utrekningar). Skygge = forventa område, merke = observert, strek = intervall. Dommen for kvar stripe er rekna frå tala.",
       [q[0] for q in NYE_SPORSMAL] + [q[0] for q in NYE_SPORSMAL2])
def d26(ctx: Ctx):
    fasit = {"eininga-1": "failed", "eininga-2": "held", "eininga-3": "held", "eininga-4": "failed", "eininga-5": "failed",
             "skilja-1": "failed", "skilja-2": "undecided", "skilja-3": "undecided", "skilja-4": "failed", "skilja-5": "held",
             "tida-1": "failed", "tida-2": "failed", "tida-3": "held", "tida-4": "undecided", "tida-5": "failed"}
    sp = []
    tal = []
    alle = [(qid, linse, tittel, rader, fasit[qid], None, 1, NEMNAR_SPORSMAL[qid]) for qid, linse, tittel, rader in NYE_SPORSMAL]
    alle += [(qid, linse, tittel, rader, utfall, etikett, 2, NEMNAR_SPORSMAL2[qid]) for qid, linse, tittel, rader, utfall, etikett in NYE_SPORSMAL2]
    for qid, linse, tittel, rader, utfall, etikett, runde, nemnar in alle:
        q = {"id": qid, "linse": linse, "runde": runde, "tittel": tittel, "utfall": utfall, "nemnar": nemnar, "rader": rader}
        if etikett:
            q["etikett"] = etikett
        sp.append(q)
        for rd in rader:
            if rd.get("avleidd") or rd.get("ordtal"):
                continue
            for j, m in enumerate(rd["obs"]):
                if m.get("mid"):
                    tal.append(T(qid, rd["namn"] + ", nedre", m["lo"]))
                    tal.append(T(qid, rd["namn"] + ", øvre", m["hi"]))
                elif j == 0:
                    tal.append(T(qid, rd["namn"], m["v"]))
    tel = collections.Counter(q["utfall"] for q in sp)
    rader_tel = collections.Counter(rd["dom"] for q in sp for rd in q["rader"])
    runde2 = collections.Counter(q["utfall"] for q in sp if q["runde"] == 2)
    data = {"sporsmal": sp, "utfall": dict(tel), "rader": dict(rader_tel), "runde2": dict(runde2),
            "namn": {"held": "heldt", "failed": "heldt ikkje", "undecided": "uavgjort"}}
    return data, tal


# ---- Runde 2: nye bilete (f27 til f36) -----------------------------------------------------------------
# Verdiane er litteralar frå dei verifiserte funna i runde 2 (finn-id står i kvar figur). Ingen ny rekning:
# runde 2 vart køyrd mot materiale og skript som ikkje ligg i repoet. Prosentar er rekna frå oppgjevne tal
# berre der funnet sjølv gir både tal og prosent.

RUNDE2 = {
    # dekning-1, -2, -4, -7, -8: duplicates and coverage
    "dekning": {
        "poster": 6432, "ulike": {"m": 6236, "lo": 6215, "hi": 6428},
        "dublettar": {"sum": 196, "oa": 52, "ark": 85, "begge": 59, "pct": 3.0},
        "arkiv_i_oa": {"n": 2223, "funne": [25, 24.6, 25.1], "berre_utanfor": [6, 142, 145], "ikkje": [69, 1524, 1531], "fjerna": 485},
        "lister": [{"namn": "Nordes, oppføringar i innhaldslistene 2005 til 2025", "pct": 92, "k": 613, "n": 665, "tilnaerma": 1},
                   {"namn": "FormAkademisk, oppføringar i 55 utgåver", "lo": 86.5, "hi": 89.8, "k": 466, "n": 519}],
        "fangst": {"verk": 19601, "lo": 18175, "hi": 21027, "sett": 6233, "forhold": 3.1},
    },
    # grense-1 .. -7: the 17 core numbers of round 1 under three narrower boundaries (h = held, f = moved, i = did not hold)
    "grense": {
        "grenser": [["A", "utan kvitlista", 2308, 49.2], ["H", "utan HCI-kanalar", 4381, 93.3],
                    ["D", "med designordkrav", 4405, 93.8], ["ALL", "alle tre", 1994, 42.5]],
        "teljing": {"A": [9, 3, 5], "H": [17, 0, 0], "D": [14, 3, 0], "ALL": [10, 2, 5]},
        "regel": "Held: avstand under 10 % eller 2 poeng frå runde 1. Flyttar seg: under 25 % eller 5 poeng. Elles held ikkje.",
        "tal": [
            ["Vekstforhold 2020–24 mot 2010–14", "gonger", 2, 1.68, [1.77, "h"], [1.65, "h"], [1.62, "h"], [1.72, "h"]],
            ["Vekst per år 2010–24, prosent", "prosent", 1, 6.2, [6.4, "h"], [6.0, "h"], [5.8, "h"], [6.2, "h"]],
            ["Danmark, del av verka", "prosent", 1, 38.4, [42.6, "f"], [37.9, "h"], [40.1, "h"], [42.2, "h"]],
            ["Sverige, del av verka", "prosent", 1, 27.4, [27.3, "h"], [27.0, "h"], [27.8, "h"], [26.4, "h"]],
            ["Noreg, del av verka", "prosent", 1, 20.7, [14.2, "i"], [21.3, "h"], [17.9, "f"], [14.7, "i"]],
            ["Finland, del av verka", "prosent", 1, 19.6, [20.9, "h"], [19.5, "h"], [20.3, "h"], [20.7, "h"]],
            ["Forfattarar per verk 2010–14", "tal", 2, 2.2, [2.37, "h"], [2.17, "h"], [2.25, "h"], [2.34, "h"]],
            ["Forfattarar per verk 2020–24", "tal", 2, 3.1, [3.3, "h"], [3.04, "h"], [3.22, "h"], [3.2, "h"]],
            ["Nordisk og ikkje-nordisk land 2010–14", "prosent", 1, 28.1, [26.6, "h"], [27.5, "h"], [28.1, "h"], [25.3, "h"]],
            ["Nordisk og ikkje-nordisk land 2020–24", "prosent", 1, 39.8, [39.2, "h"], [40.5, "h"], [41.1, "h"], [40.4, "h"]],
            ["Utan registrert sitering", "prosent", 1, 26.6, [30.3, "f"], [27.5, "h"], [26.2, "h"], [32.8, "f"]],
            ["Median siteringar", "tal", 0, 3.0, [2.0, "i"], [3.0, "h"], [3.0, "h"], [2.0, "i"]],
            ["Fulltekst, del av verka", "prosent", 1, 52.2, [42.8, "f"], [53.6, "h"], [50.1, "h"], [44.4, "f"]],
            ["Engelskmerkte verk", "prosent", 1, 95.4, [97.5, "h"], [95.1, "h"], [97.3, "h"], [97.1, "h"]],
            ["Ti største kanalfamiliar, del", "prosent", 1, 47.9, [29.3, "i"], [51.5, "h"], [44.9, "h"], [31.1, "i"]],
            ["Største kanal, del", "prosent", 1, 10.8, [4.1, "i"], [11.6, "h"], [8.3, "f"], [4.9, "i"]],
            ["Nordisk kanal, del av alle", "prosent", 1, 19.2, [6.6, "i"], [19.6, "h"], [15.3, "f"], [5.6, "i"]],
        ],
        # cells (row, boundary) whose value is not stated in the verified findings: the class is shown, the value is not
        "utan_tal": [(2, 3), (3, 3), (6, 3), (8, 3), (10, 2), (12, 2), (14, 2), (15, 1), (15, 2), (15, 3), (16, 2)],
        "ikkjeforsking": {"flagga": 207, "kjerne": 169, "median": [3, 3], "usiterte": [26.6, 25.8], "topp10": [47.9, 47.6],
                          "fa": [481, 444]},
    },
    # arkiv-1 .. -6, -8: the archive layer, archive by archive
    "arkiv": {
        "arkiv": [
            # namn, verk, rå, port, DOI-treff, dobbel, att, DOI (verk), open PDF-adresse (verk), ukjend slag (verk)
            ["NVA", 1161, 6212, 1291, 126, 4, 1161, 181, 380, 543],
            ["Nordes", 408, 711, 704, 296, 0, 408, 408, 317, 0],
            ["DiVA", 128, 2806, 186, 53, 5, 128, 29, 87, 128],
            ["KGL", 38, 374, 45, 7, 0, 38, 38, 33, None],
            ["IRIS", 3, 38, 4, 1, 0, 3, 3, 3, None],
            ["Aalto", 0, 22, 2, 2, 0, 0, None, None, None],
        ],
        "port_sum": 2232, "fjerna_doi": 485, "fjerna_dobbel": 9, "att": 1738, "namn_full": {"NVA": "Cristin (NVA)", "KGL": "Det Kongelige Akademi"},
        "doi": [659, 1738, 37.9], "pdf": [820, 1738, 47.2], "ukjend": [671, 1738, 38.6],
        "land": {"FI": 0, "DK": 38, "IS": 3, "uttak_finland": 22, "uttak_danmark": 374, "uttak_island": 38},
        "tema": {"arkiv_n": 816, "oa_n": 2447, "avstand": 23.2,
                 "klynger": [["F", "deltaking og helse", 15.3, 7.8], ["H", "tenestedesign", 14.5, 7.0], ["D", "byar, berekraft og samskaping", 12.5, 9.4],
                             ["C", "designtenking, produkt og kognisjon", 2.9, 13.9], ["A", "utdanning og undervising", 7.2, 14.0],
                             ["J", "handverk, tekstil og materialitet", 6.2, 9.3]]},
    },
    # panel-1 .. -4, -7: fixed panel of 27 channels against all and against the rest
    "panel": {
        "utval": {"kanalar": 569, "panel": 27, "pct": 4.7, "verk": 2140, "av": 3978, "verk_pct": 53.8, "fast_lista": 12, "ikkje": 15},
        "periodar": ["2005–09", "2020–24"], "alle": [305, 1549], "panel": [204, 812], "utanfor": [101, 737],
        "faktor": {"alle": 5.08, "panel": 3.98, "utanfor": 7.30}, "rate": {"panel": 9.4, "alle": 11.0, "utanfor": 13.6},
        "faktor_sist": {"alle": 1.68, "panel": 1.71, "utanfor": 1.65},
        "panelandel_per": ["2005–09", "2010–14", "2015–19", "2020–24"], "panelandel": [66.9, 51.6, 54.0, 52.4],
        "bidrag": [608, 1244, 48.9],
        "utan_fa": {"faktor": 3.24, "rate": 8.1, "fa_verk": 450, "fa_pct": 21.0, "stig": 18, "like": 2, "fell": 7},
        "sist": {"y2024": 317, "y2025": 258, "forhold": 0.814},
    },
    # samanlikning-2 .. -7, -9: scope against Nordic works outside scope (B with a design word in the title, C without)
    "samanlikning": {
        "grupper": [["A", "scope", 4149], ["B", "utanfor, designord i tittel", 5933], ["C", "utanfor, utan designord", 11677]],
        "periodar": ["2010–14", "2020–24"],
        "rader": [
            ["Forfattarar per verk", "tal", 2, [2, 5], [2.20, 3.10], [3.22, 4.38], [3.39, 4.33], "skilnad i endring A minus B -0,26, intervall inkluderer 0"],
            ["Fire eller fleire forfattarar", "prosent", 1, [0, 60], [13.4, 32.5], [30.3, 46.6], [26.4, 41.4], None],
            ["Einforfattarverk", "prosent", 1, [0, 45], [38.2, 23.2], [19.0, 14.0], [29.4, 22.1], "skilnad i endring A minus B -10,1 poeng, intervall -14,6 til -5,3"],
            ["Minst to forfattarland", "prosent", 1, [25, 55], [32.0, 44.5], [39.2, 50.3], [38.1, 50.4], "skilnad i endring +1,4 poeng, intervall -4,6 til +7,6"],
            ["Median referansar", "tal", 0, [15, 40], [19, 29], [25, 34], [25, 36], "skilnad i endring +1, intervall -2 til +5"],
            ["Utan registrert sitering", "prosent", 1, [15, 32], [22.8, 23.0], [21.2, 18.7], [27.0, 29.8], None],
        ],
        "nordiske": {"a": 8.9, "b": 8.0, "auke": [3.1, 1.8, 3.6]},
    },
    # tilgang-1 .. -4, -6, -7: verified public PDF
    "tilgang": {
        "klassar": ["verifisert PDF", "berre uverifisert adresse", "berre DOI", "ingenting"],
        "lag": [["OpenAlex-laget", 4694, [52.0, 12.0, 28.6, 7.3]], ["arkivlaget", 1738, [47.2, 47.3, 5.5, 0.0]], ["begge lag", 6432, [50.7, 21.6, 22.4, 5.3]]],
        "periodar": ["før 2000", "2000–04", "2005–09", "2010–14", "2015–19", "2020–24", "2025–26"],
        "pdf": [1.4, 9.8, 36.7, 41.2, 52.8, 66.9, 49.4],
        "k": [[1, 69], [10, 102], [112, 305], [380, 923], [634, 1201], [1036, 1549], [269, 545]],
        "fast_miks": [None, None, 27.8, 39.4, 55.6, 65.8, 50.3], "utan_fa_nordes": [None, None, 14.3, 28.3, 46.2, 60.8, 45.2],
        "kanal": [["FormAkademisk", 481, 481], ["Nordes", 230, 266], ["DIS, PDC og ServDes", 248, 515], ["DRS-konferanse", 156, 350],
                  ["Andre dedikerte tidsskrift", 323, 725], ["Repositorium", 118, 254], ["Anna internasjonal kanal", 674, 1327],
                  ["Forlagsserie", 96, 381], ["Anna nordisk kanal", 59, 152], ["Ukjend kanal", 57, 243]],
        "land": [["NO", 68.5, 664, 970, 45.6], ["FI", 55.7, 513, 921, 51.8], ["SE", 55.3, 711, 1286, 50.2], ["IS", 46.4, 13, 28, None],
                 ["DK", 40.9, 736, 1801, 37.9]],
        "oa_status": {"opne": [3181, 73.7, 17.5], "stengde": [1430, 5.2, 72.1, 22.7]},
        "fulltekst": {"verifisert": 3262, "med": 3260, "pct": 99.9, "andre": [12, 3170, 0.4]},
    },
    # tilgang-8 .. -10: doctoral theses in the archive layer and the OpenAlex layer
    "avhandlingar": {
        "poster": 78, "oa": [21, 4694, 0.4], "ark": [57, 1738, 3.3], "unike": 71, "heile": 1.2,
        "land": [["NO", 39], ["SE", 21], ["DK", 18], ["FI", 0]],
        "periode": [["før 2010", 11], ["2010–14", 8], ["2015–19", 14], ["2020–24", 31], ["2025–26", 14]],
        "pdf": {"dr": [43, 78, 55.1], "ma": [179, 203, 88.2], "oa": [9, 21, 42.9], "ark": [34, 57, 59.6], "andre_ark": [612, 1480, 41.4]},
        "slag": {"thesis": 177, "dr": 46, "ma": 131}, "master": 203,
    },
    # sprak-1 .. -8: Nordic-language works and texts
    "sprak": {
        "nordisk": {"n": 394, "av": 6432, "pct": 6.1, "oa": [188, 4694], "ark": [206, 1738], "fa": [146, 481]},
        "port": {"treff": [226, 394, 57.4], "ark": [206, 206], "oa": [20, 188], "fa": [7, 146]},
        "ord": {"nordisk_n": 205, "engelsk_n": 2782,
                "ord": [["handverk", 56.1, None], ["berekraft", 39.0, 47.1], ["designprosess", 39.0, 71.7], ["formgiving", 33.2, None], ["designforskning", None, 46.3]],
                "rtd": [0, 205, 318, 2782, 11.4]},
        "fa": {"nordisk_n": 119, "engelsk_n": 291, "formgiving": [33.6, 0.7]},
        "skrivemate": {"bokmal_n": 151, "nynorsk_n": 13, "handverk": {"bokmal": [88, 7], "nynorsk": [4, 12]},
                       "fem": {"bokmal": [274, 16], "nynorsk": [13, 27]}},
        "merke": {"oa_norsk_men_engelsk": [10, 12], "oa_engelsk_men_nordisk": [2, 3], "ark_engelsk_men_nordisk": 13, "ukjend": [38, 36, 2]},
    },
    # praksis-1 .. -9: practice, exhibition and craft vocabulary
    "praksis": {
        "lag": {"n": 4694, "tittel": [179, 3.8], "samandrag": [594, 12.7], "fulltekst": [938, 20.0]},
        "familie": [["praksis", 1.4, 7.1, 8.3], ["utstilling", 0.4, 2.5, 8.0], ["handverk", 2.8, 7.9, 14.8]],
        "tradisjon": [["Interaksjonsdesign", 832, 17.7], ["Industri- og produktdesign", 363, 7.7], ["Arkitektur", 277, 5.9],
                      ["Tenestedesign", 256, 5.5], ["Tekstil og mote", 184, 3.9], ["Grafisk og kommunikasjonsdesign", 36, 0.8]],
        "tradisjon_sum": [1804, 38.4, 2890, 61.6],
        "samandrag": [
            {"namn": "Tekstil og mote", "n": 167, "handverk": [53, 31.7]},
            {"namn": "Interaksjonsdesign", "n": 734, "handverk": [22, 3.0], "praksis": [66, 9.0]},
            {"namn": "Arkitektur", "n": 242, "handverk": [9, 3.7], "praksis": [22, 9.1], "utstilling": [11, 4.5]},
            {"namn": "Industri- og produktdesign", "n": 326, "handverk": [8, 2.5], "praksis": [8, 2.5]},
            {"namn": "Tenestedesign", "n": 240, "praksis": [3, 1.2]}],
        "tekstil_utan_fa": [30, 138, 21.7],
        "tid": {"periodar": ["til 2009", "2010–14", "2015–19", "2020–25"], "handverk_alle": [1.2, None, None, 8.8],
                "handverk": [1.2, 2.6, 3.1, 3.5], "praksis": [2.8, 4.7, 5.3, 8.3], "utstilling": [3.1, 2.6, 2.2, 2.5],
                "fa": [129, 236, 54.7, 11.7]},
        "norsk": {"samandrag": 145, "handverk": [55, 37.9], "utan_fagnamn": [19, 13.1], "faget": [45, 31.0], "fulltekst": 131, "fa": [137, 145]},
        "arkiv": {"samandrag": 198, "titlar": [74, 4.3], "fulltekst": 721, "praksis": 7.5, "utstilling": 9.2, "handverk": 8.6,
                  "tradisjon": [542, 31.2], "tenestedesign": [321, 18.5]},
        "regel": [41, 48, 85.4],
    },
    # vekting-1, -2, -4, -5, -6, -9: the same numbers after weighting the full-text sample against all works
    "vekting": {
        "rader": [
            ["Datainnsamling, markørdel (2 176 engelske tekstar)", "prosent", 58.1, [58.0, 58.0], "markør"],
            ["Argument, markørdel", "prosent", 40.5, [40.6, 40.6], "markør"],
            ["Omgrepsbreidd, snitt tal omgrep (44 omgrep)", "tal", 6.11, [6.14, 6.17], "omgrep"],
            ["Minst fem omgrep, del av tekstane", "prosent", 62.2, [62.0, 62.3], "omgrep"],
            ["Tekstklynge I, del (OpenAlex-kartet)", "prosent", 7.9, [4.9, 4.9], "klynge"],
            ["Tekstklynge J, del", "prosent", 9.3, [6.4, 6.4], "klynge"],
            ["Tekstklynge C, del", "prosent", 13.9, [16.9, 16.9], "klynge"],
            ["Tekstklynge J, del, med arkivlaget", "prosent", 8.6, [5.8, 5.8], "klynge"],
            ["Tekstklynge I, del, med arkivlaget", "prosent", 8.6, [7.2, 7.2], "klynge"],
            ["Tekstklynge C, del, med arkivlaget", "prosent", 11.2, [13.2, 13.4], "klynge"],
            ["Tekstklynge H, del, med arkivlaget", "prosent", 8.9, [10.0, 10.0], "klynge"],
        ],
        "spenn_marker": [57.7, 59.4], "maks_klynge_pp": 3.0,
        "monster": {"periode": [45.7, 62.5], "slag": [61.7, 53.1]},
    },
}


@figur("d27", "materialet", "Postar, ulike verk og kva som er fanga",
       "Kor mange ulike verk er det blant dei 6 432 postane, og kor godt dekkjer laga kjende lister?", "stolpe og dekning",
       "6 432 postar (4 694 OpenAlex og 1 738 arkiv). Ulike verk med tittel, år og førsteforfattar (nivå M); intervallet er 6 215 til 6 428. Arkivdelen: 2 223 arkivposter før fjerning.",
       ["dekning-1", "dekning-2", "dekning-4", "dekning-7", "dekning-8", "dekning-9"])
def d27(ctx: Ctx):
    d = RUNDE2["dekning"]
    data = dict(d)
    tal = [T("dekning-1", "Registrerte postar", d["poster"]), T("dekning-1", "Ulike verk, nivå M", d["ulike"]["m"]),
           T("dekning-1", "Ulike verk, nedre", d["ulike"]["lo"]), T("dekning-1", "Ulike verk, øvre", d["ulike"]["hi"]),
           T("dekning-1", "Dublettpostar", d["dublettar"]["sum"]), T("dekning-1", "Dublettar, prosent", 3.0),
           T("dekning-1", "Innan OpenAlex-laget", 52), T("dekning-1", "Innan arkivlaget", 85), T("dekning-1", "I begge lag", 59),
           T("dekning-2", "Arkivposter", 2223), T("dekning-2", "Fjerna på DOI-treff", 485),
           T("dekning-2", "Funne i OpenAlex-laget, prosent", 25), T("dekning-2", "Berre utanfor scope, prosent", 6),
           T("dekning-2", "Ikkje funne, prosent", 69),
           T("dekning-4", "Fangst-attfangst, verk", 19601), T("dekning-4", "Ki, nedre", 18175), T("dekning-4", "Ki, øvre", 21027),
           T("dekning-4", "Ulike verk sett i begge lag", 6233), T("dekning-4", "Forhold til observert", 3.1),
           T("dekning-7", "Nordes-oppføringar, om lag", 665), T("dekning-7", "Registrerte, om lag", 613), T("dekning-7", "Prosent", 92),
           T("dekning-8", "FormAkademisk-oppføringar", 519), T("dekning-8", "Registrerte, tittelkopling", 466),
           T("dekning-8", "Prosent, nedre", 86.5), T("dekning-8", "Prosent, øvre", 89.8)]
    return data, tal


@figur("d28", "materialet", "Kva som held når porten flyttar seg",
       "Kva av runde 1 sine 17 kjernetal held under snevrare utval av OpenAlex-laget?", "rutenett, tal per grense",
       "OpenAlex-laget, 4 694 verk. Grenser: utan liste = utan kvitlista (2 308), utan HCI = utan HCI-kanalar (4 381), med ord = designordkrav (4 405), alle tre (1 994). Arkivlaget er ikkje omrekna.",
       ["grense-1", "grense-2", "grense-3", "grense-4", "grense-5", "grense-6", "grense-7", "ikkjeforsking-1", "ikkjeforsking-4", "ikkjeforsking-6"])
def d28(ctx: Ctx):
    g = RUNDE2["grense"]
    tel = collections.Counter()
    kol = {"A": 0, "H": 1, "D": 2, "ALL": 3}
    for row in g["tal"]:
        for k, c in kol.items():
            tel[(k, row[4 + c][1])] += 1
    for k in kol:
        assert [tel[(k, "h")], tel[(k, "f")], tel[(k, "i")]] == g["teljing"][k], k
    # the class of a cell follows from the stated rule and the analysis' own value; the value is shown only where the
    # verified findings (claim or checked number field) state it
    vis = {(ri, ci): v for ri, row in enumerate(g["tal"]) for ci, (v, _) in enumerate(row[4:])}
    for ri, ci in g["utan_tal"]:
        vis[(ri, ci)] = None
    data = {"grenser": [{"id": a, "namn": n, "n": k, "pct": p} for a, n, k, p in g["grenser"]],
            "teljing": g["teljing"], "regel": g["regel"],
            "tal": [{"namn": n, "eining": e, "d": dd, "r1": r1, "per": [{"v": vis[(ri, ci)], "dom": dom} for ci, (v, dom) in enumerate(rest)]}
                    for ri, (n, e, dd, r1, *rest) in enumerate(g["tal"])],
            "ikkjeforsking": g["ikkjeforsking"], "kjerne_n": 17}
    tal = [T("grense-1", "Kjernetal", 17), T("grense-1", "Held utan HCI-kanalar", 17), T("grense-1", "Held med designordkrav", 14),
           T("grense-1", "Held utan kvitlista", 9), T("grense-1", "Held ikkje utan kvitlista", 5),
           T("grense-7", "Verk med alle tre grensene", 1994), T("grense-7", "Del av 4 694, prosent", 42.5),
           T("grense-2", "Vekstforhold, nedre", 1.62), T("grense-2", "Vekstforhold, øvre", 1.77), T("grense-2", "Vekstforhold runde 1", 1.68),
           T("grense-2", "Forfattarar per verk 2020–24, nedre", 3.04), T("grense-2", "Forfattarar per verk 2020–24, øvre", 3.30),
           T("grense-2", "Engelskmerkte, nedre", 95.1), T("grense-2", "Engelskmerkte, øvre", 97.5),
           T("grense-3", "Største kanal utan kvitlista, om lag", 4), T("grense-3", "Nordisk kanal utan kvitlista, om lag", 6),
           T("grense-3", "Fulltekst utan kvitlista", 42.8), T("grense-4", "Noreg utan kvitlista", 14.2), T("grense-4", "Finland utan kvitlista", 20.9),
           T("grense-5", "HCI-verk ut", 313), T("grense-6", "Designordkrav fjernar", 289),
           T("ikkjeforsking-1", "Flagga postar, vid regel", 207), T("ikkjeforsking-1", "Kjerneflagga postar", 169),
           T("ikkjeforsking-4", "Usiterte utan kjerne", 25.8), T("ikkjeforsking-6", "Topp ti utan kjerne", 47.6)]
    return data, tal


@figur("d29", "materialet", "Arkivlaget, arkiv for arkiv",
       "Kva kjem frå kvart arkiv, kva fall ut ved porten og kva er opent og engelsk?", "tabell med små stolpar",
       "Arkivlaget, 1 738 verk frå 2 232 poster som kom gjennom porten. Tema: verk med fulltekstklynge, arkiv 816 og OpenAlex 2 447. Finland har 0 arkivverk fordi det finske uttaket gav 22 rader, ikkje fordi finske verk manglar.",
       ["arkiv-1", "arkiv-2", "arkiv-3", "arkiv-4", "arkiv-5", "arkiv-6", "arkiv-8"])
def d29(ctx: Ctx):
    a = RUNDE2["arkiv"]
    rader = a["arkiv"]
    assert sum(x[1] for x in rader) == a["att"]
    assert sum(x[3] for x in rader) == a["port_sum"]
    assert sum(x[4] for x in rader) == a["fjerna_doi"]
    assert sum(x[5] for x in rader) == a["fjerna_dobbel"]
    data = {"arkiv": [{"namn": x[0], "namn_full": a["namn_full"].get(x[0], x[0]), "n": x[1], "raa": x[2], "port": x[3], "doi_treff": x[4],
                       "dobbel": x[5], "att": x[6], "doi": x[7], "pdf": x[8], "ukjend": x[9]} for x in rader],
            "port_sum": a["port_sum"], "fjerna_doi": a["fjerna_doi"], "fjerna_dobbel": a["fjerna_dobbel"], "att": a["att"],
            "doi": a["doi"], "pdf": a["pdf"], "ukjend": a["ukjend"], "land": a["land"],
            "tema": {"arkiv_n": a["tema"]["arkiv_n"], "oa_n": a["tema"]["oa_n"], "avstand": a["tema"]["avstand"],
                     "klynger": [{"bokstav": b, "namn": n, "ark": x, "oa": y} for b, n, x, y in a["tema"]["klynger"]]}}
    tal = [T("arkiv-1", "NVA", 1161), T("arkiv-1", "Nordes", 408), T("arkiv-1", "DiVA", 128), T("arkiv-1", "KGL", 38),
           T("arkiv-1", "IRIS", 3), T("arkiv-1", "Ukjend slag", 671), T("arkiv-1", "NVA med ukjend slag", 543),
           T("arkiv-2", "Arkivverk med DOI", 659), T("arkiv-2", "DOI, prosent", 37.9), T("arkiv-2", "DiVA med DOI", 29), T("arkiv-2", "NVA med DOI", 181),
           T("arkiv-3", "Open PDF-adresse", 820), T("arkiv-3", "Prosent", 47.2), T("arkiv-3", "Nordes", 317), T("arkiv-3", "NVA", 380),
           T("arkiv-5", "Rå rader", 10163), T("arkiv-5", "Gjennom porten", 2232), T("arkiv-5", "Fjerna på DOI-treff", 485),
           T("arkiv-5", "Fjerna på dobbel DOI", 9), T("arkiv-5", "Att", 1738),
           T("arkiv-6", "Danske arkivverk", 38), T("arkiv-6", "Finske arkivverk", 0),
           T("arkiv-8", "Variasjonsavstand", 23.2), T("arkiv-8", "Deltaking og helse, arkiv", 15.3), T("arkiv-8", "Deltaking og helse, OpenAlex", 7.8),
           T("arkiv-8", "Designtenking, arkiv", 2.9), T("arkiv-8", "Designtenking, OpenAlex", 13.9)]
    return data, tal


@figur("d30", "vekst", "Vekst i eit fast panel av 27 kanalar",
       "Veks laget berre fordi nye kanalar kjem til, eller òg i kanalar som var der frå starten?", "stipla linjer og stolpar",
       "OpenAlex-laget, verk 2005 til 2024 med kanal-id (3 978 verk). Panelet er valt på verk i alle periodar, så faktoren for panelet er truleg eit golv og for resten eit tak. 2025 og 2026 er ufullstendige.",
       ["panel-1", "panel-2", "panel-3", "panel-4", "panel-7"])
def d30(ctx: Ctx):
    p = RUNDE2["panel"]
    data = dict(p)
    tal = [T("panel-1", "Kanalar med verk", 569), T("panel-1", "Panelkanalar", 27), T("panel-1", "Panelkanalar, prosent", 4.7),
           T("panel-1", "Panelverk", 2140), T("panel-1", "Verk med kanal-id", 3978), T("panel-1", "Panelverk, prosent", 53.8),
           T("panel-2", "Panel 2005–09", 204), T("panel-2", "Panel 2020–24", 812), T("panel-2", "Panelfaktor", 3.98),
           T("panel-2", "Totalt 2005–09", 305), T("panel-2", "Totalt 2020–24", 1549), T("panel-2", "Totalfaktor", 5.08),
           T("panel-2", "Utanfor 2005–09", 101), T("panel-2", "Utanfor 2020–24", 737), T("panel-2", "Utanforfaktor", 7.30),
           T("panel-2", "Årsrate panel", 9.4), T("panel-2", "Årsrate totalt", 11.0), T("panel-2", "Årsrate utanfor", 13.6),
           T("panel-3", "Ekstra verk frå panelet", 608), T("panel-3", "Ekstra verk", 1244), T("panel-3", "Del, prosent", 48.9),
           T("panel-3", "Faktor 2010–14 til 2020–24, panel", 1.71), T("panel-3", "Faktor totalt", 1.68), T("panel-3", "Faktor utanfor", 1.65),
           T("panel-4", "FormAkademisk i panelet", 450), T("panel-4", "FormAkademisk, prosent", 21.0), T("panel-4", "Panelfaktor utan FormAkademisk", 3.24),
           T("panel-4", "Rate utan FormAkademisk", 8.1), T("panel-4", "Kanalar som stig", 18), T("panel-4", "Kanalar som fell", 7),
           T("panel-7", "Verk 2025", 258), T("panel-7", "Verk 2024", 317)]
    return data, tal


@figur("d31", "vekst", "Auken i team og samarbeid mot nordiske verk utanfor scope",
       "Er auken i teamstorleik og samarbeid særeigen for verka i scope?", "start og slutt for tre grupper",
       "Til og med 2024: A scope 4 149 verk, B nordiske verk utanfor scope med designord i tittelen 5 933, C utan designord 11 677. Eit intervall som inkluderer 0 viser at utvalet ikkje skil gruppene, ikkje at utviklinga er lik.",
       ["samanlikning-1", "samanlikning-2", "samanlikning-3", "samanlikning-4", "samanlikning-5", "samanlikning-6", "samanlikning-7", "samanlikning-9"])
def d31(ctx: Ctx):
    s = RUNDE2["samanlikning"]
    data = {"grupper": [{"id": a, "namn": n, "n": k} for a, n, k in s["grupper"]], "periodar": s["periodar"],
            "rader": [{"namn": n, "eining": e, "d": dd, "akse": ax, "A": a, "B": b, "C": c, "diff": df} for n, e, dd, ax, a, b, c, df in s["rader"]],
            "nordiske": s["nordiske"]}
    tal = [T("samanlikning-2", "Forfattarar A 2010–14", 2.20), T("samanlikning-2", "Forfattarar A 2020–24", 3.10),
           T("samanlikning-2", "Forfattarar B 2010–14", 3.22), T("samanlikning-2", "Forfattarar B 2020–24", 4.38),
           T("samanlikning-2", "Forfattarar C 2010–14", 3.39), T("samanlikning-2", "Forfattarar C 2020–24", 4.33),
           T("samanlikning-2", "Fire eller fleire A 2010–14", 13.4), T("samanlikning-2", "Fire eller fleire A 2020–24", 32.5),
           T("samanlikning-2", "Fire eller fleire B 2010–14", 30.3), T("samanlikning-2", "Fire eller fleire B 2020–24", 46.6),
           T("samanlikning-3", "Einforfattar A 2010–14", 38.2), T("samanlikning-3", "Einforfattar A 2020–24", 23.2),
           T("samanlikning-3", "Einforfattar B 2010–14", 19.0), T("samanlikning-3", "Einforfattar B 2020–24", 14.0),
           T("samanlikning-3", "Einforfattar C 2010–14", 29.4), T("samanlikning-3", "Einforfattar C 2020–24", 22.1),
           T("samanlikning-3", "Skilnad i endring, poeng", -10.1), T("samanlikning-3", "Intervall, nedre", -14.6), T("samanlikning-3", "Intervall, øvre", -5.3),
           T("samanlikning-4", "To forfattarland A 2010–14", 32.0), T("samanlikning-4", "To forfattarland A 2020–24", 44.5),
           T("samanlikning-4", "To forfattarland B 2010–14", 39.2), T("samanlikning-4", "To forfattarland B 2020–24", 50.3),
           T("samanlikning-4", "To forfattarland C 2010–14", 38.1), T("samanlikning-4", "To forfattarland C 2020–24", 50.4),
           T("samanlikning-5", "To nordiske land A 2020–24", 8.9), T("samanlikning-5", "To nordiske land B 2020–24", 8.0),
           T("samanlikning-5", "Auke A", 3.1), T("samanlikning-5", "Auke B", 1.8), T("samanlikning-5", "Auke C", 3.6),
           T("samanlikning-6", "Referansar A 2010–14", 19), T("samanlikning-6", "Referansar A 2020–24", 29),
           T("samanlikning-6", "Referansar B 2010–14", 25), T("samanlikning-6", "Referansar B 2020–24", 34),
           T("samanlikning-6", "Referansar C 2010–14", 25), T("samanlikning-6", "Referansar C 2020–24", 36),
           T("samanlikning-7", "Usiterte A 2010–14", 22.8), T("samanlikning-7", "Usiterte A 2020–24", 23.0),
           T("samanlikning-7", "Usiterte B 2010–14", 21.2), T("samanlikning-7", "Usiterte B 2020–24", 18.7),
           T("samanlikning-7", "Usiterte C 2010–14", 27.0), T("samanlikning-7", "Usiterte C 2020–24", 29.8),
           T("samanlikning-1", "Verk i gruppe B", 6703), T("samanlikning-1", "Utanfor scope utan nordisk land", 1)]
    return data, tal


@figur("d32", "materialet", "Kven som har ein open PDF, og kor dei ligg",
       "Kor stor del av verka har ein verifisert offentleg PDF, og kva avheng det av periode, kanal og land?", "stolpar og linjer",
       "Verifisert offentleg PDF kontrollert i 2026, ikkje lisens. OpenAlex-laget 4 694 verk, arkivlaget 1 738. Fulltekstlaget er i praksis dei verifiserte opne verka (3 260 av 3 262).",
       ["tilgang-1", "tilgang-2", "tilgang-3", "tilgang-4", "tilgang-6", "tilgang-7"])
def d32(ctx: Ctx):
    t = RUNDE2["tilgang"]
    for nm, n, v in t["lag"]:
        assert abs(sum(v) - 100) < 0.4, nm
    data = dict(t)
    tal = [T("tilgang-1", "Verifisert PDF, begge lag, verk", 3262), T("tilgang-1", "Verifisert PDF, prosent", 50.7),
           T("tilgang-1", "Berre uverifisert", 21.6), T("tilgang-1", "Berre DOI", 22.4), T("tilgang-1", "Ingenting", 5.3),
           T("tilgang-1", "OpenAlex-laget, verifisert", 52.0), T("tilgang-1", "Arkivlaget, verifisert", 47.2),
           T("tilgang-2", "Før 2000", 1.4), T("tilgang-2", "2005–09", 36.7), T("tilgang-2", "2010–14", 41.2), T("tilgang-2", "2015–19", 52.8),
           T("tilgang-2", "2020–24", 66.9), T("tilgang-2", "2025–26", 49.4), T("tilgang-2", "Fast kanalmiks 2005–09", 27.8),
           T("tilgang-2", "Fast kanalmiks 2020–24", 65.8), T("tilgang-2", "Utan FormAkademisk og Nordes 2005–09", 14.3),
           T("tilgang-2", "Utan FormAkademisk og Nordes 2020–24", 60.8),
           T("tilgang-3", "FormAkademisk", 100.0), T("tilgang-3", "Nordes", 86.5), T("tilgang-3", "Forlagsserie", 25.2), T("tilgang-3", "Ukjend kanal", 23.5),
           T("tilgang-4", "Noreg", 68.5), T("tilgang-4", "Finland", 55.7), T("tilgang-4", "Sverige", 55.3), T("tilgang-4", "Danmark", 40.9),
           T("tilgang-4", "Noreg utan FormAkademisk og Nordes", 45.6), T("tilgang-4", "Danmark utan FormAkademisk og Nordes", 37.9),
           T("tilgang-6", "Verifiserte PDF-ar med fulltekst", 3260), T("tilgang-6", "Verifiserte PDF-ar", 3262), T("tilgang-6", "Prosent", 99.9),
           T("tilgang-7", "Merkte opne", 3181), T("tilgang-7", "Opne med verifisert PDF", 73.7), T("tilgang-7", "Merkte stengde", 1430),
           T("tilgang-7", "Stengde med verifisert PDF", 5.2)]
    return data, tal


@figur("d33", "materialet", "Doktoravhandlingar i materialet",
       "Kor mange doktoravhandlingar er det, kvar kjem dei frå, og kor ofte er dei opne?", "stolpar",
       "78 doktorpostar (57 i arkivlaget, 21 i OpenAlex-laget), 71 ulike etter samanslåing på tittel. Slaget thesis i arkivlaget er ikkje det same som doktoravhandling: 177 er 46 doktor- og 131 masteroppgåver.",
       ["tilgang-8", "tilgang-9", "tilgang-10"])
def d33(ctx: Ctx):
    a = RUNDE2["avhandlingar"]
    assert sum(k for _, k in a["land"]) == a["poster"] == sum(k for _, k in a["periode"])
    data = dict(a)
    tal = [T("tilgang-8", "Doktorpostar", 78), T("tilgang-8", "Arkivlaget", 57), T("tilgang-8", "OpenAlex-laget", 21), T("tilgang-8", "Ulike", 71),
           T("tilgang-8", "Slaget thesis", 177), T("tilgang-8", "Doktoravhandlingar under thesis", 46), T("tilgang-8", "Masteroppgåver under thesis", 131),
           T("tilgang-8", "Master- eller bachelornivå", 203),
           T("tilgang-9", "Noreg", 39), T("tilgang-9", "Sverige", 21), T("tilgang-9", "Danmark", 18), T("tilgang-9", "Finland", 0),
           T("tilgang-9", "Før 2010", 11), T("tilgang-9", "2010–14", 8), T("tilgang-9", "2015–19", 14), T("tilgang-9", "2020–24", 31),
           T("tilgang-9", "2025–26", 14),
           T("tilgang-10", "Doktor med verifisert PDF", 43), T("tilgang-10", "Doktor, prosent", 55.1), T("tilgang-10", "Master og bachelor", 179),
           T("tilgang-10", "Master og bachelor, prosent", 88.2), T("tilgang-10", "OpenAlex-laget, prosent", 42.9),
           T("tilgang-10", "Arkivlaget, prosent", 59.6), T("tilgang-10", "Andre arkivverk, prosent", 41.4)]
    return data, tal


@figur("d34", "omgrep", "Nordiskspråklege verk og tekstar",
       "Kor mange verk er på nordisk språk, og kva ord bruker dei mot dei engelske tekstane?", "stolpar og punktpar",
       "Språkmerke frå metadata (OpenAlex) og søkeindeks (arkiv): 394 av 6 432 postar. Ordbruk frå fulltekstar på minst 1 500 ord: 205 nordiske og 2 782 engelske. Regexane for medverknad er ikkje jamnbyrdige og er ikkje med.",
       ["sprak-1", "sprak-2", "sprak-4", "sprak-6", "sprak-7", "sprak-8"])
def d34(ctx: Ctx):
    s = RUNDE2["sprak"]
    data = dict(s)
    tal = [T("sprak-1", "Nordiskspråklege verk", 394), T("sprak-1", "Registrerte", 6432), T("sprak-1", "Prosent", 6.1),
           T("sprak-1", "OpenAlex-laget", 188), T("sprak-1", "Arkivlaget", 206), T("sprak-1", "FormAkademisk", 146),
           T("sprak-2", "Handverk, nordiske", 56.1), T("sprak-2", "Berekraft, nordiske", 39.0), T("sprak-2", "Designprosess, nordiske", 39.0),
           T("sprak-2", "Formgiving, nordiske", 33.2), T("sprak-2", "Designprosess, engelske", 71.7), T("sprak-2", "Berekraft, engelske", 47.1),
           T("sprak-2", "Designforskning, engelske", 46.3), T("sprak-2", "Nordiske fulltekstar", 205), T("sprak-2", "Engelske fulltekstar", 2782),
           T("sprak-2", "Forsking gjennom design, engelske", 318), T("sprak-2", "Forsking gjennom design, prosent", 11.4),
           T("sprak-4", "Tittel i porten", 226), T("sprak-4", "Prosent", 57.4), T("sprak-4", "Arkivlaget", 206),
           T("sprak-4", "OpenAlex-laget", 20), T("sprak-4", "FormAkademisk", 7),
           T("sprak-6", "Nordiske fulltekstar i FormAkademisk", 119), T("sprak-6", "Engelske fulltekstar i FormAkademisk", 291),
           T("sprak-6", "Formgiving, nordiske", 33.6), T("sprak-6", "Formgiving, engelske", 0.7),
           T("sprak-7", "Bokmålstekstar", 151), T("sprak-7", "Nynorsktekstar", 13), T("sprak-7", "Håndverk i bokmål", 88),
           T("sprak-7", "Handverk i bokmål", 7), T("sprak-7", "Handverk i nynorsk", 12), T("sprak-7", "Håndverk i nynorsk", 4),
           T("sprak-7", "Bokmålsform, bokmålstekstar", 274), T("sprak-7", "Nynorsk form, bokmålstekstar", 16),
           T("sprak-7", "Nynorsk form, nynorsktekstar", 27), T("sprak-7", "Bokmålsform, nynorsktekstar", 13)]
    return data, tal


@figur("d35", "omgrep", "Praksis, utstilling og handverk som vokabular",
       "Kor ofte bruker tekstane ord for praksis, utstilling og handverk, og kor i materialet står dei?", "stolpar og tabell",
       "OpenAlex-laget, 4 694 verk; ordlista er vår, og absolutte nivå hengjer på henne. Vokabular er ikkje praksis: det er ikkje vist at forfattarane gjorde meir praksisbasert arbeid. Arkivlaget har samandrag for 198 verk.",
       ["praksis-1", "praksis-2", "praksis-3", "praksis-4", "praksis-5", "praksis-7", "praksis-9"])
def d35(ctx: Ctx):
    p = RUNDE2["praksis"]
    data = dict(p)
    tal = [T("praksis-1", "Verk med vokabular i tittel", 179), T("praksis-1", "Tittel, prosent", 3.8), T("praksis-1", "Tittel eller samandrag", 594),
           T("praksis-1", "Samandrag, prosent", 12.7), T("praksis-1", "Heile teksten", 938), T("praksis-1", "Heile teksten, prosent", 20.0),
           T("praksis-1", "Praksis, tittel", 1.4), T("praksis-1", "Praksis, samandrag", 7.1), T("praksis-1", "Praksis, fulltekst", 8.3),
           T("praksis-1", "Utstilling, tittel", 0.4), T("praksis-1", "Utstilling, samandrag", 2.5), T("praksis-1", "Utstilling, fulltekst", 8.0),
           T("praksis-1", "Handverk, tittel", 2.8), T("praksis-1", "Handverk, samandrag", 7.9), T("praksis-1", "Handverk, fulltekst", 14.8),
           T("praksis-2", "Norske samandrag", 145), T("praksis-2", "Med handverk-ord", 55), T("praksis-2", "Prosent", 37.9),
           T("praksis-2", "Utan fagnamnet", 19), T("praksis-2", "Utan fagnamnet, prosent", 13.1), T("praksis-2", "Nemner faget", 45),
           T("praksis-2", "Nemner faget, prosent", 31.0), T("praksis-2", "Norske fulltekstar", 131), T("praksis-2", "FormAkademisk, norske samandrag", 137),
           T("praksis-3", "Minst ein tradisjon", 1804), T("praksis-3", "Prosent", 38.4), T("praksis-3", "Ingen", 2890), T("praksis-3", "Ingen, prosent", 61.6),
           T("praksis-3", "Interaksjonsdesign", 832), T("praksis-3", "Interaksjonsdesign, prosent", 17.7),
           T("praksis-3", "Industri og produkt", 363), T("praksis-3", "Industri og produkt, prosent", 7.7),
           T("praksis-3", "Arkitektur", 277), T("praksis-3", "Arkitektur, prosent", 5.9), T("praksis-3", "Tenestedesign", 256),
           T("praksis-3", "Tenestedesign, prosent", 5.5), T("praksis-3", "Tekstil og mote", 184), T("praksis-3", "Tekstil og mote, prosent", 3.9),
           T("praksis-3", "Grafisk design", 36), T("praksis-3", "Grafisk design, prosent", 0.8),
           T("praksis-4", "Handverk i tekstil, prosent", 31.7), T("praksis-4", "Handverk i tekstil", 53), T("praksis-4", "Tekstilsamandrag", 167),
           T("praksis-4", "Tekstil utan FormAkademisk, prosent", 21.7), T("praksis-4", "Handverk, interaksjon", 22),
           T("praksis-4", "Handverk, interaksjon, prosent", 3.0), T("praksis-4", "Interaksjonssamandrag", 734),
           T("praksis-4", "Handverk, arkitektur", 9), T("praksis-4", "Handverk, arkitektur, prosent", 3.7),
           T("praksis-4", "Arkitektursamandrag", 242), T("praksis-4", "Handverk, industri", 8), T("praksis-4", "Handverk, industri, prosent", 2.5),
           T("praksis-4", "Industrisamandrag", 326), T("praksis-4", "Praksis, arkitektur", 22), T("praksis-4", "Praksis, arkitektur, prosent", 9.1),
           T("praksis-4", "Praksis, interaksjon", 66), T("praksis-4", "Praksis, interaksjon, prosent", 9.0),
           T("praksis-4", "Praksis, tenestedesign", 3), T("praksis-4", "Praksis, tenestedesign, prosent", 1.2), T("praksis-4", "Tenestedesignsamandrag", 240),
           T("praksis-4", "Utstilling, arkitektur", 11), T("praksis-4", "Utstilling, arkitektur, prosent", 4.5),
           T("praksis-5", "Regel stemmer med lesing", 41), T("praksis-5", "Av regeltreff", 48), T("praksis-5", "Prosent", 85.4),
           T("praksis-7", "Handverk til 2009", 1.2), T("praksis-7", "Handverk 2020–25", 8.8), T("praksis-7", "Handverk utan FormAkademisk 2010–14", 2.6),
           T("praksis-7", "Handverk utan FormAkademisk 2015–19", 3.1), T("praksis-7", "Handverk utan FormAkademisk 2020–25", 3.5),
           T("praksis-7", "Praksis utan FormAkademisk til 2009", 2.8), T("praksis-7", "Praksis 2010–14", 4.7), T("praksis-7", "Praksis 2015–19", 5.3),
           T("praksis-7", "Praksis 2020–25", 8.3), T("praksis-7", "Utstilling til 2009", 3.1), T("praksis-7", "Utstilling 2010–14", 2.6),
           T("praksis-7", "Utstilling 2015–19", 2.2), T("praksis-7", "Utstilling 2020–25", 2.5),
           T("praksis-7", "Handverk-samandrag i FormAkademisk", 129), T("praksis-7", "Av", 236), T("praksis-7", "Prosent", 54.7),
           T("praksis-7", "Del av alle samandrag", 11.7),
           T("praksis-9", "Arkivverk med samandrag", 198), T("praksis-9", "Titlar med vokabular", 74), T("praksis-9", "Titlar, prosent", 4.3),
           T("praksis-9", "Engelske fulltekstar", 721), T("praksis-9", "Praksis", 7.5), T("praksis-9", "Utstilling", 9.2), T("praksis-9", "Handverk", 8.6),
           T("praksis-9", "Minst ein tradisjon", 542), T("praksis-9", "Tradisjon, prosent", 31.2), T("praksis-9", "Tenestedesign", 321),
           T("praksis-9", "Tenestedesign, prosent", 18.5)]
    return data, tal


@figur("d36", "tema", "Same tal etter vekting mot alle verk",
       "Flyttar tala frå fulltekstutvalet seg når utvalet blir vekta mot alle verk?", "før og etter",
       "Fulltekstutvalet vekta mot OpenAlex-laget (4 694 verk) og mot begge lag (3 263 av 6 432). Vektinga rettar berre for modellvariablane (kanalgruppe, periode, land, slag, språk), ikkje for uobserverte skilnader.",
       ["vekting-1", "vekting-2", "vekting-3", "vekting-4", "vekting-5", "vekting-6", "vekting-9"])
def d36(ctx: Ctx):
    v = RUNDE2["vekting"]
    data = {"rader": [{"namn": n, "eining": e, "for": f, "etter": [lo, hi], "gruppe": g} for n, e, f, (lo, hi), g in v["rader"]],
            "spenn_marker": v["spenn_marker"], "maks_klynge_pp": v["maks_klynge_pp"],
            "monster": v["monster"]}
    tal = [T("vekting-2", "Markørdel uvekta", 58.1), T("vekting-2", "Markørdel vekta", 58.0), T("vekting-2", "Argument uvekta", 40.5),
           T("vekting-2", "Argument vekta", 40.6), T("vekting-9", "Markørdel, nedre", 57.7), T("vekting-9", "Markørdel, øvre", 59.4),
           T("vekting-9", "Klyngeandel, høgste skifte, poeng", 3.0),
           T("vekting-6", "Snittbreidd uvekta", 6.11), T("vekting-6", "Snittbreidd vekta, nedre", 6.14), T("vekting-6", "Snittbreidd vekta, øvre", 6.17),
           T("vekting-6", "Minst fem omgrep uvekta", 62.2), T("vekting-6", "Minst fem, vekta nedre", 62.0), T("vekting-6", "Minst fem, vekta øvre", 62.3),
           T("vekting-4", "Klynge I uvekta", 7.9), T("vekting-4", "Klynge I vekta", 4.9), T("vekting-4", "Klynge J uvekta", 9.3),
           T("vekting-4", "Klynge J vekta", 6.4), T("vekting-4", "Klynge C uvekta", 13.9), T("vekting-4", "Klynge C vekta", 16.9),
           T("vekting-5", "Klynge J med arkivlaget, før", 8.6), T("vekting-5", "Klynge J med arkivlaget, etter", 5.8),
           T("vekting-5", "Klynge I med arkivlaget, før", 8.6), T("vekting-5", "Klynge I med arkivlaget, etter", 7.2),
           T("vekting-5", "Klynge C med arkivlaget, før", 11.2), T("vekting-5", "Klynge C med arkivlaget, etter, nedre", 13.2),
           T("vekting-5", "Klynge C med arkivlaget, etter, øvre", 13.4), T("vekting-5", "Klynge H med arkivlaget, før", 8.9),
           T("vekting-5", "Klynge H med arkivlaget, etter", 10.0),
           T("vekting-3", "2010–14 vekta", 45.7), T("vekting-3", "2015–19 vekta", 62.5), T("vekting-3", "Artiklar vekta", 61.7),
           T("vekting-3", "Konferanse vekta", 53.1)]
    return data, tal


# ==== SLUTT FIGURAR ====


# ----------------------------------------------------------------------------------------------------------
# Figures as the page shows them. A figure is one or more of the parts above (d01 to d36), merged because they
# answer the same question. The data of a figure is {part id: part data}; the manifest lists the parts.
# ----------------------------------------------------------------------------------------------------------

SAMLA = [
    dict(id="f01", seksjon="materialet", tittel="Frå 24 812 rader til 6 432 postar og om lag 6 236 ulike verk",
         sporsmal="Kor mange ulike verk er det, kor mange er dublettar, og kor godt dekkjer laga kjende lister?",
         form="sankey, dekning og arkiv for arkiv", delar=["d01", "d27", "d29"]),
    dict(id="f02", seksjon="materialet", tittel="Kva som held når grensa eller utvalet flyttar seg",
         sporsmal="Kva av første runde sine tal held under snevrare grenser, og flyttar fulltekstutvalet tala?",
         form="rutenett og før mot etter", delar=["d28", "d36"]),
    dict(id="f03", seksjon="materialet", tittel="Open PDF, fulltekst og avhandlingar",
         sporsmal="Kor stor del av verka har ein verifisert open PDF, og kva avheng det av tid, kanal, land og slag?",
         form="stolpar og linjer", delar=["d32", "d33", "d04"]),
    dict(id="f04", seksjon="vekst", tittel="Materialet er ungt, og veksten held òg i eit fast panel av kanalar",
         sporsmal="Kor raskt veks laget, kven veks, og er det berre nye kanalar?",
         form="stolpar, stabla område og stipla linjer", delar=["d02", "d05", "d30"]),
    dict(id="f05", seksjon="vekst", tittel="Teama er blitt større, og det gjeld òg nordiske verk utanfor scope",
         sporsmal="Korleis har lagstorleik og samarbeid endra seg, og er auken særeigen for verka i scope?",
         form="linjer og start mot slutt", delar=["d06", "d31", "d07", "d08"]),
    dict(id="f06", seksjon="vekst", tittel="Land og institusjonar heng saman, forfattarane gjer det i mindre grad",
         sporsmal="Er medforfattarnettet samanhengande, og kva avheng det av eininga?",
         form="nettverk", delar=["d09"]),
    dict(id="f07", seksjon="kanalar", tittel="Få kanalar tek mykje av verka, og inngangsporten set delar av biletet",
         sporsmal="Kor samla ligg verka i få kanalar, og er norsk særstilling ein effekt av porten?",
         form="Lorenz-kurver og stabla stolpar", delar=["d10", "d11"]),
    dict(id="f08", seksjon="siteringar", tittel="Dei mest siterte elementa som nettverk",
         sporsmal="Kva blir sitert saman, og kor skeivt fordeler referansane seg?", form="nettverk", delar=["d13"]),
    dict(id="f09", seksjon="siteringar", tittel="Siteringane er svært skeive og skil mellom kanalar",
         sporsmal="Kor ujamt fordeler registrerte siteringar seg, og kva skil kanalane?",
         form="Lorenz-kurve, punkt og matrise", delar=["d14", "d12"]),
    dict(id="f10", seksjon="siteringar", tittel="Referanselistene er lengre og eldre, og få peikar til laget sjølv",
         sporsmal="Kor mange referansar, kor gamle, og kvar går dei?", form="små multiplar og stolpar", delar=["d15", "d16"]),
    dict(id="f11", seksjon="tema", tittel="Kartets åtte klynger ligg tett mot kvarandre",
         sporsmal="Korleis ligg verka i kartet, og kvar står dei nordiskspråklege?", form="kart", delar=["d18"]),
    dict(id="f12", seksjon="tema", tittel="Klynger og samfunn følgjer kanalen noko meir enn språk, land eller periode",
         sporsmal="Er dei kopla siteringssamfunna og tekstklyngene skilde fag, og kva følgjer dei?",
         form="stolpar og spenn", delar=["d17", "d19"]),
    dict(id="f13", seksjon="tema", tittel="Eitt emne dominerer, og klyngene har skifta over tid",
         sporsmal="Kor skeivt fordeler OpenAlex-emna, og kva veks eller fell?", form="små søyler og linjer", delar=["d20"]),
    dict(id="f14", seksjon="omgrep", tittel="Omgrep skil seg i breidde, og fleire stig enn fell",
         sporsmal="Kor mange tekstar bruker omgrepet, og kva stig og fell?", form="radplott og punktpar", delar=["d21", "d22"]),
    dict(id="f15", seksjon="omgrep", tittel="Språk og vokabular: nordiske tekstar, praksis og handverk",
         sporsmal="Kor mange verk er på nordiske språk, kva ord bruker dei, og kor ofte står praksis, utstilling og handverk?",
         form="stolpar og punktpar", delar=["d03", "d34", "d35"]),
    dict(id="f16", seksjon="kunnskap", tittel="Berre éi kunnskapsform let seg måle med markørar, og formene opptrer saman",
         sporsmal="Kor mange kunnskapsformer, kva let seg måle, og kva avheng datainnsamlingsmarkørane av?",
         form="punkt med intervall og bogediagram", delar=["d23", "d24"]),
    dict(id="f17", seksjon="teori", tittel="Pilotane gir ein profil, og ei andre lesing finn att to av tre påstandar",
         sporsmal="Kva viser pilotane for teorielement, og finn ei andre lesing det same?", form="intervallpunkt og stolpar", delar=["d25"]),
    dict(id="f18", seksjon="sporsmaal", tittel="Forventing mot utfall, 24 spørsmål i to rundar",
         sporsmal="Heldt forventinga som vart skriven ned før målinga?", form="forventa område mot observert", delar=["d26"]),
]

# the four lenses of the new questions have ids of their own that are not findings
SPORSMAL_ID = re.compile(r"(eininga|skilja|tida|grenser)-\d")

# Findings in the two rounds (counts from the two verification files; tests check them against the fixtures)
FUNN_TOTALT = {"totalt": 166, "stadfesta": 80, "retta": 84, "refuta": 1, "ukontrollerbar": 1,
               "runde1": {"totalt": 76, "stadfesta": 30, "retta": 45, "ukontrollerbar": 1},
               "runde2": {"totalt": 90, "stadfesta": 50, "retta": 39, "refuta": 1},
               "sporsmal": 24, "sporsmal_runde1": 15, "sporsmal_runde2": 9}


# ----------------------------------------------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------------------------------------------

def dump(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def sjekk_tekst(obj, sti="") -> None:
    if isinstance(obj, str):
        if len(obj) > MAKS_TEKST:
            raise ValueError("tekst over %d teikn: %s" % (MAKS_TEKST, sti))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            sjekk_tekst(v, sti + "/" + str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            sjekk_tekst(v, sti + "[%d]" % i)


def funn_tal(manifest_fig: list[dict]) -> dict:
    """The counts the hero shows: the findings of both rounds that were checked (confirmed or adjusted), how many of
    them are drawn in at least one figure, and the new questions (counted separately)."""
    teikna = {fid for f in manifest_fig for fid in f["finn"] if not SPORSMAL_ID.match(fid)}
    ut = {k: v for k, v in FUNN_TOTALT.items() if not isinstance(v, dict)}
    ut["kontrollerte"] = FUNN_TOTALT["stadfesta"] + FUNN_TOTALT["retta"]
    ut["teikna"] = len(teikna)
    return ut


def build(only: list[str] | None = None, ut_mappe: Path | None = None) -> dict:
    ut = ut_mappe or META_DIR
    ut.mkdir(parents=True, exist_ok=True)
    ctx = Ctx()
    deler = {f["id"]: f for f in FIGURAR}
    bygg = [c for c in SAMLA if not only or c["id"] in only or any(d in only for d in c["delar"])]
    ferdig: dict[str, tuple] = {}
    seksjonar: dict[str, dict] = collections.OrderedDict()
    manifest_fig = []
    for c in bygg:
        data, tal, finn, delar = {}, [], [], []
        for did in c["delar"]:
            if did not in ferdig:
                t0 = time.time()
                ferdig[did] = deler[did]["fn"](ctx)
                print("%s %.1f s" % (did, time.time() - t0), flush=True)
            d, t = ferdig[did]
            data[did] = d
            tal += [dict(x, **{"del": did}) for x in t]
            finn += [x for x in deler[did]["finn"] if x not in finn]
            delar.append({"id": did, "tittel": deler[did]["tittel"], "nemnar": deler[did]["nemnar"], "finn": deler[did]["finn"]})
        hoved = deler[c["delar"][0]]
        seksjonar.setdefault(c["seksjon"], collections.OrderedDict())[c["id"]] = data
        manifest_fig.append({"id": c["id"], "seksjon": c["seksjon"], "tittel": c["tittel"], "sporsmal": c["sporsmal"],
                             "form": c["form"], "nemnar": hoved["nemnar"], "finn": finn, "fil": c["seksjon"] + ".json",
                             "delar": delar, "tal": tal})
    filer = {}
    for namn, figs in seksjonar.items():
        obj = {"format": FORMAT, "seksjon": namn, "figurar": figs}
        sjekk_tekst(obj, namn)
        b = dump(obj)
        (ut / (namn + ".json")).write_bytes(b)
        filer[namn + ".json"] = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
    manifest = {"format": FORMAT, "filer": filer, "figurar": manifest_fig, "funn": funn_tal(manifest_fig),
                "kjelder": ["data/nordic_design_research.sqlite", "docs/data/nordic_additions.json",
                            "docs/data/nordic_status.json", "docs/data/vis/*.json", "docs/data/klynger/kart.json",
                            "steg6-metaanalyse/funn-samla.json (verifiserte funn, runde 1)",
                            "steg11-metaanalyse2/funn-samla.json (verifiserte funn, runde 2)"]}
    sjekk_tekst(manifest, "manifest")
    (ut / "manifest.json").write_bytes(dump(manifest))
    tot = sum(v["bytes"] for v in filer.values())
    print("ferdig: %d figurar, %d delar, %d filer, %d bytes" % (len(manifest_fig), len(ferdig), len(filer), tot))
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bygg figurdata til docs/funn/ i docs/data/meta/.")
    ap.add_argument("--berre", nargs="*", help="figur- eller del-id-ar (til dømes f01 f04 d05)")
    ap.add_argument("--ut", help="annan utmappe (til testing)")
    a = ap.parse_args(argv)
    build(a.berre, Path(a.ut) if a.ut else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
