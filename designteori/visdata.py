"""Utforsk: builder for the data files in docs/data/vis/.

Run as ``python -u -m designteori.visdata`` from the repository root. The
specification is steg9-utforsk/spesifikasjon.md with the binding amendments
from the review; where this file and the text differ, this file is what the
tests check.

Only the standard library and numpy are imported at module level, so that
``compileall`` and the test suite work in CI. scipy and networkx are imported
inside the layout functions. The builder never runs in CI.

Everything is deterministic: fixed seeds, fixed tie-breaks, files written as
bytes with LF line endings, so that ``bytes`` and ``sha256`` in manifest.json
agree with what git checks out on any machine.
"""
from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import argparse
import collections
import gzip
import hashlib
import json
import math
import re
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import DOCS_DATA_DIR, RAW_SQLITE, normalize_doi, now_iso, read_json
from .pdf import allowed_url, safe_public_link

VIS_DIR = DOCS_DATA_DIR / "vis"
# Notes folder (spring buffer, t-SNE checkpoint, reports): outside the repository, given with
# --notatmappe or the environment variable UTFORSK_NOTATMAPPE; without it the build keeps no notes.
NOTATMAPPE = Path(os.environ["UTFORSK_NOTATMAPPE"]) if os.environ.get("UTFORSK_NOTATMAPPE") else None
N_FORVENTA = 6432
KART_STORLEIK = 10000
MIN_VERK_NETT = 2
GENERERT = None  # set in main()
# Without --generert the files are built with this placeholder; skriv_alle then keeps the old
# timestamp when no byte changed (a rebuild of the same input gives the same files and ?v=).
PLASSHALDAR = "@@GENERERT@@"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LAND_NORDISK = [("DK", "Danmark"), ("FI", "Finland"), ("IS", "Island"), ("NO", "Noreg"), ("SE", "Sverige")]

LANDNAMN = {
    "AE": "Dei sameinte arabiske emirata", "AR": "Argentina", "AT": "Austerrike", "AU": "Australia",
    "BE": "Belgia", "BG": "Bulgaria", "BI": "Burundi", "BO": "Bolivia", "BR": "Brasil", "BW": "Botswana",
    "CA": "Canada", "CH": "Sveits", "CL": "Chile", "CN": "Kina", "CO": "Colombia", "CU": "Cuba",
    "CY": "Kypros", "CZ": "Tsjekkia", "DE": "Tyskland", "DK": "Danmark", "DZ": "Algerie", "EC": "Ecuador",
    "EE": "Estland", "EG": "Egypt", "ES": "Spania", "ET": "Etiopia", "FI": "Finland", "FR": "Frankrike",
    "GB": "Storbritannia", "GH": "Ghana", "GL": "Grønland", "GR": "Hellas", "HK": "Hongkong",
    "HR": "Kroatia", "HU": "Ungarn", "ID": "Indonesia", "IE": "Irland", "IL": "Israel", "IN": "India",
    "IR": "Iran", "IS": "Island", "IT": "Italia", "JP": "Japan", "KE": "Kenya", "KR": "Sør-Korea",
    "LB": "Libanon", "LI": "Liechtenstein", "LK": "Sri Lanka", "LT": "Litauen", "LU": "Luxembourg",
    "LV": "Latvia", "ML": "Mali", "MT": "Malta", "MX": "Mexico", "MY": "Malaysia", "MZ": "Mosambik",
    "NA": "Namibia", "NG": "Nigeria", "NL": "Nederland", "NO": "Noreg", "NZ": "New Zealand", "OM": "Oman",
    "PE": "Peru", "PG": "Papua Ny-Guinea", "PK": "Pakistan", "PL": "Polen", "PR": "Puerto Rico",
    "PT": "Portugal", "QA": "Qatar", "RO": "Romania", "RU": "Russland", "SA": "Saudi-Arabia",
    "SE": "Sverige", "SG": "Singapore", "SI": "Slovenia", "SK": "Slovakia", "SM": "San Marino",
    "TH": "Thailand", "TN": "Tunisia", "TR": "Tyrkia", "TW": "Taiwan", "TZ": "Tanzania", "UA": "Ukraina",
    "US": "USA", "UY": "Uruguay", "VE": "Venezuela", "VN": "Vietnam", "ZA": "Sør-Afrika", "ZM": "Zambia",
    "ZW": "Zimbabwe", "FO": "Færøyane", "AX": "Åland", "EU": "Europa", "XK": "Kosovo", "RS": "Serbia",
    "BY": "Kviterussland",
}

TYPAR = [
    ("artikkel", "Artikkel"), ("konferanse", "Konferansebidrag"), ("bok", "Bok eller kapittel"),
    ("avhandling", "Avhandling"), ("anna", "Anna"), ("ukjend", "Ukjend"),
]
TYPE_TIL_GRUPPE = {
    "article": "artikkel", "review": "artikkel", "editorial": "artikkel", "letter": "artikkel",
    "book-review": "artikkel",
    "conference-paper": "konferanse", "conference-abstract": "konferanse", "proceedings-article": "konferanse",
    "book": "bok", "book-chapter": "bok", "reference-entry": "bok",
    "dissertation": "avhandling", "thesis": "avhandling",
    "paratext": "anna", "other": "anna",
    "unknown": "ukjend", "": "ukjend",
}

KANALGRUPPER = [
    ("tidsskrift", "Tidsskrift"), ("konferanse", "Konferanse"), ("hci", "HCI"), ("bok", "Bok"),
    ("repositorium", "Repositorium"), ("anna", "Anna"), ("ukjend", "Ukjend"),
]
UKJEND_GRUPPE = 6
# first rule that matches wins (spec 5.1); the order is repositorium, bok, hci, konferanse, tidsskrift
KANAL_REGLAR = [
    (4, re.compile(r"portal|orbit|diva|zenodo|aaltodoc|\bhal\b|nora -|doaj|publications \(|research at the|research \(|architecture, design and conservation|university of|repository|chalmers research|vbn")),
    (3, re.compile(r"ebooks|series|lecture notes|handbook|advances in|smart innovation|communications in|press|springer|human-computer interaction series")),
    (2, re.compile(r"\bchi\b|designing interactive|dis companion|nordichi|nordic conference on human|tangible|computer-human|human-computer|human factors|cscw|computer supported|interaction design and children|mindtrek|ozchi|interacting with computers|child-computer|\binteractions\b|creativity and cognition|participatory design conference|human-centered informatics")),
    (1, re.compile(r"conference|congress|proceedings|\bdrs\b|servdes|iasdr|cumulus|eksig|learnxdesign|symposium|nordes")),
    (0, re.compile(r"journal|design studies|design issues|artifact|she ji|formakademisk|codesign|design and culture|design science|design philosophy|craft research|design research|swedish design|digital creativity|creativity and innovation|design and technology|sustainability|computers &")),
]
UKJENT_KANALNAMN = {"ukjent", "ukjend", "unknown"}

PRESET_NAMN = {
    "participatory-design": "Deltakande design", "codesign": "Co-design",
    "research-through-design": "Research through Design", "design-theory-epistemology": "Designteori",
    "service-systemic-design": "Teneste- og systemdesign", "sustainable-circular": "Berekraftig design",
    "critical-speculative": "Kritisk design", "interaction-hci-ai": "Interaksjonsdesign",
    "design-history-nordic": "Designhistorie", "craft-materiality-textile": "Handverk og tekstil",
    "aesthetics-form": "Estetikk og form", "design-education-pedagogy": "Designdidaktikk",
    "design-ethics-justice": "Etikk og universell", "design-anthropology": "Designantropologi",
    "industrial-product": "Industridesign", "urban-architecture": "By og arkitektur",
}
# A reviewed name may replace the automatic one here (key = preset key). Set after reading tema-sjekk.md.
# Reviewed 2026-11-13 against the 8 titles nearest each centroid and the c-TF-IDF terms (tema-sjekk.md). The keys
# stay the nearest preset (they are only identifiers in the URL); the names say what the cluster holds.
TEMA_NAMN_OVERSTYRING: dict[str, str] = {
    "research-through-design": "Co-design og casestudiar",
    "critical-speculative": "Systemdesign og undervising",
    "participatory-design": "Nordisk designforsking",
    "interaction-hci-ai": "Deltakande design",
    "aesthetics-form": "Interaksjonsdesign og brukarar",
    "design-history-nordic": "Relasjonelt design og framtider",
    "craft-materiality-textile": "Handverk og fagdidaktikk",
    "industrial-product": "Tenestedesign på norsk",
}

# Short names for the largest institutions, keyed by OpenAlex institution id (amendment 69).
KORT_NAMN = {
    "I9927081": "Aalto", "I204337017": "Aarhus", "I891191580": "Aalborg", "I177969490": "Syddansk",
    "I893397424": "Kolding", "I96673099": "DTU", "I204778367": "NTNU", "I86987016": "KTH",
    "I66862912": "Chalmers", "I83467386": "ITU", "I135606841": "AHO", "I102134673": "Linköping",
    "I184531372": "OsloMet", "I90267481": "Umeå", "I183111857": "Malmö", "I4210128030": "Kunstakademiet",
    "I133731052": "Helsingfors", "I184942183": "Oslo", "I881427289": "Göteborg", "I124055696": "København",
    "I98358874": "Delft", "I98381234": "Oulu", "I180519160": "CBS", "I161593684": "Stockholm",
    "I83019370": "Eindhoven", "I107707843": "Roskilde", "I95220073": "Lappland", "I30867006": "Arkitektskolen Aarhus",
    "I187531555": "Lund", "I93860229": "Milano", "I123387679": "Uppsala", "I223464139": "Linné",
    "I2801380234": "Sørøst-Noreg", "I166825849": "Tampere", "I190632392": "Luleå", "I155660961": "Turku",
    "I94722563": "Jyväskylä", "I992397": "Borås", "I302099661": "Kunstuniv. Helsingfors", "I82509713": "Mälardalen",
    "I69601649": "VIA", "I99412970": "Kunstakademiets skolar", "I162608824": "Sussex", "I4387153886": "Tampere (gml.)",
    "I218177685": "Konstfack",
}
STORE_INSTITUSJONAR = 30
KORT_MAKS = 28

# Nynorsk names of a few city names that OpenAlex gives in English.
BYNAMN = {
    "Copenhagen": "København", "Gothenburg": "Göteborg", "Reykjavik": "Reykjavík", "Malmo": "Malmö", "Vaxjo": "Växjö",
    "Milan": "Milano", "Stord / Soerstokken": "Stord", "Struer Municipality": "Struer", "Holar": "Hólar",
}
# Nordic places must lie inside this box (Greenland and the Faroes included); OpenAlex has a few wrong coordinates.
NORDISK_RAMME = (53.0, 84.0, -75.0, 35.0)  # lat min, lat max, lon min, lon max

TERM_MIN_DF = 5
TERM_MAKS_DEL = 0.4
TERM_MAKS_ANTAL = 6000
TERM_STANDARD = ["codesign", "service design", "research through design", "sustainability", "design thinking", "speculative design"]

STOPPORD = frozenset("""
a an the and or nor but of in on at to for with without by from as is are was were be been being am it its this that these those
not no into onto about above across after against along among around before behind below beneath beside besides between beyond
during except inside near off out outside over past since through throughout till toward towards under until up upon via vs versus
within than then there their them they we us our you your he she his her him i me my mine how what why when where who whom whose
which whether can could may might must shall should will would do does did done have has had having also both each either few
more most other some such only own same so too very just et al etc per
og i på av for med til en et ei ein eit er som det den de dei å om fra frå ved ikke ikkje har kan seg sin sitt sine si så eller
mot under over etter mellom hos hjå gjennom gjenom han hun vi me du jeg eg meg deg oss dette denne disse desse hva kva hvordan
korleis hvorfor kvifor når kor hvor var vart blir blei bli blitt blitt vore være vere ble vil vill skal skulle kunne kunna må måtte
bare berre også òg mer meir mest mykje mye ho henne hans hennar deira deres sitt
och att är ett vid inte sig mellan genom från vad hur varför när varit blev blir bli kan ska skulle kunde måste endast också mer mest
han hon vi ni jag du detta denna dessa den det de dem sin sitt sina
af at mod gennem fra efter mellem hos sig ikke har kan skal skulle kunne måtte kun også mere mest hvad hvordan hvorfor hvor
han hun vi du jeg dette denne disse
""".split())

SEG_SPLIT_RE = re.compile(r'[.,;:!?()\[\]{}"\u201c\u201d\u00ab\u00bb/|]')
TOKEN_RE = re.compile(r"\w[\w'\u2019-]*\w|\w")
_STRIPP_TEGN = str.maketrans("", "", "-'\u2019")

_FOLD_KART = str.maketrans({
    "ø": "o", "æ": "ae", "ß": "ss", "ð": "d", "þ": "th", "ł": "l", "đ": "d", "œ": "oe",
})

_t0 = time.time()
_steg_tider: list[tuple[str, float]] = []


def logg(msg: str) -> None:
    print(f"[{time.time() - _t0:7.1f}s] {msg}", flush=True)


class Steg:
    """Context manager that prints a progress line and records the run time of a step."""

    def __init__(self, namn: str):
        self.namn = namn

    def __enter__(self):
        self.start = time.time()
        logg(f"-> {self.namn}")
        return self

    def __exit__(self, *exc):
        _steg_tider.append((self.namn, time.time() - self.start))
        if exc[0] is None:
            logg(f"<- {self.namn} ({time.time() - self.start:.1f}s)")
        return False


# ---------------------------------------------------------------------------
# Text helpers. fold() and termnokkel() must agree with the JavaScript in docs/utforsk.
# Test vectors: fold("Malmö") == "malmo", fold("Þórður Ærø") == "thordur aero",
# fold("Straße") == "strasse", fold("håndverk") == "handverk".
# ---------------------------------------------------------------------------


def fold(s: object) -> str:
    t = unicodedata.normalize("NFD", str(s or ""))
    t = "".join(c for c in t if not 0x300 <= ord(c) <= 0x36F)
    t = t.lower().translate(_FOLD_KART)
    return " ".join(t.split())


def termnokkel(text: object) -> str:
    """Key of a term: NFC, lowercase, tokens by the regex, - ' and ’ removed from each token, one space between."""
    s = unicodedata.normalize("NFC", str(text or "")).lower()
    toks: list[str] = []
    for seg in SEG_SPLIT_RE.split(s):
        toks.extend(t.translate(_STRIPP_TEGN) for t in TOKEN_RE.findall(seg))
    return " ".join(toks)


def kort_hash(s: str, n: int) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


def kanal_fold(namn: str) -> str:
    """Folded venue name for merging spellings: "The Artifact" and "Artifact", "&" and "and",
    commas and an ellipsis ("Proceedings of the ... International Conference") make no difference."""
    f = fold(namn).replace("&", " and ").replace("…", " ").replace("...", " ").replace(",", " ")
    f = " ".join(f.split())
    return f[4:] if f.startswith("the ") else f


def kanal_nokkel(namn: str) -> str:
    return "k" + kort_hash(kanal_fold(namn), 8)


def kanal_gruppe(namn: str) -> int:
    n = (namn or "").lower().strip()
    if not n:
        return UKJEND_GRUPPE
    for idx, rx in KANAL_REGLAR:
        if rx.search(n):
            return idx
    return 5


def forfattar_namnenokkel(namn: str) -> str:
    return "n:" + kort_hash(fold(namn), 10)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def json_bytes(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def skriv_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def liste(a) -> list:
    return np.asarray(a).tolist()


# ---------------------------------------------------------------------------
# Step 1: the works, dictionaries, links
# ---------------------------------------------------------------------------


class Ns:
    """Plain attribute bag."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def opne_db() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)


def hovudland(teljar: collections.Counter) -> str:
    """Most frequent country, ties alphabetical."""
    if not teljar:
        return ""
    return sorted(teljar.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def les_korpus(db: sqlite3.Connection, indeks_sti: Path) -> Ns:
    pub = read_json(DOCS_DATA_DIR / "publications.json")
    arkiv = read_json(DOCS_DATA_DIR / "nordic_additions.json")
    indeks = read_json(indeks_sti)
    ids = [p["id"] for p in pub] + [p["id"] for p in arkiv]
    if ids != indeks["ids"]:
        raise SystemExit("semantic_index.ids er ikkje lik publications + nordic_additions i rekkjefølgje")
    n = len(ids)
    n_oa = len(pub)
    id_til_i = {w: i for i, w in enumerate(ids)}
    if len(id_til_i) != n:
        raise SystemExit("duplikate verks-id-ar")

    # authorships of in-scope works, in rowid order
    rader = collections.defaultdict(list)
    for wid, aid, anamn, iid, inamn, land in db.execute(
        "select a.work_id, a.author_id, a.author_name, a.institution_id, a.institution_name, a.country "
        "from authorships a join works w on w.id = a.work_id where w.in_scope = 1 order by a.rowid"
    ):
        rader[wid].append((aid or "", anamn or "", iid or "", inamn or "", land or ""))
    ukjende = set(rader) - set(ids[:n_oa])
    if ukjende:
        raise SystemExit(f"authorships for {len(ukjende)} verk som ikkje er i publications.json")

    forf_per_verk: list[list[tuple[str, str]]] = []  # (nokkel, namn)
    inst_per_verk: list[list[str]] = []
    fland_per_verk: list[list[str]] = []
    inst_namn = collections.defaultdict(collections.Counter)
    inst_land = collections.defaultdict(collections.Counter)
    forf_land = collections.defaultdict(collections.Counter)
    forf_verk_oa = collections.defaultdict(set)  # author id -> works
    inst_verk = collections.defaultdict(set)
    land_verk = collections.defaultdict(set)
    forfordning_avvik = 0
    utan_forfattarar = 0
    tomme_id_plassar = 0
    for i in range(n_oa):
        rs = rader.get(ids[i], [])
        forf: list[tuple[str, str]] = []
        sett_namn = set()
        inst: list[str] = []
        fland: list[str] = []
        for aid, anamn, iid, inamn, land in rs:
            if anamn and anamn not in sett_namn:
                sett_namn.add(anamn)
                if aid:
                    forf.append((aid, anamn))
                else:
                    forf.append((forfattar_namnenokkel(anamn), anamn))
                    tomme_id_plassar += 1
            if aid:
                forf_verk_oa[aid].add(i)
                if land:
                    forf_land[aid][land] += 1
            if iid:
                if iid not in inst:
                    inst.append(iid)
                inst_namn[iid][inamn] += 1
                inst_verk[iid].add(i)
                if land:
                    inst_land[iid][land] += 1
            if land and land not in fland:
                fland.append(land)
        for c in fland:
            land_verk[c].add(i)
        # compare with publications.json
        if [nm for _, nm in forf] != list(pub[i].get("authors") or []):
            forfordning_avvik += 1
        if not rs:
            utan_forfattarar += 1
        forf_per_verk.append(forf)
        inst_per_verk.append(inst)
        fland_per_verk.append(fland)
    for j, a in enumerate(arkiv):
        forf = []
        sett = set()
        for nm in a.get("authors") or []:
            nm = str(nm).strip()
            if not nm:
                continue
            k = forfattar_namnenokkel(nm)
            if k in sett:
                continue
            sett.add(k)
            forf.append((k, nm))
        forf_per_verk.append(forf)
        inst_per_verk.append([])
        fland_per_verk.append([])
    if forfordning_avvik:
        logg(f"ADVARSEL: forfattarrekkjefølgje avvik frå publications.json for {forfordning_avvik} verk")

    # venues
    kanal_namn_per_verk: list[str] = []
    for p in pub:
        kanal_namn_per_verk.append(str(p.get("source") or "").strip())
    for a in arkiv:
        kanal_namn_per_verk.append(str(a.get("venue") or "").strip())
    kanal_spel = collections.defaultdict(collections.Counter)
    kanal_n = collections.Counter()
    kanal_per_verk_fold: list[str] = []
    for nm in kanal_namn_per_verk:
        f = kanal_fold(nm)
        if not f or f in UKJENT_KANALNAMN:
            kanal_per_verk_fold.append("")
            continue
        kanal_per_verk_fold.append(f)
        kanal_spel[f][nm] += 1
        kanal_n[f] += 1
    kanalar = []
    for f in kanal_spel:
        namn = sorted(kanal_spel[f].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        kanalar.append({"k": "k" + kort_hash(f, 8), "namn": namn, "g": kanal_gruppe(namn), "n": kanal_n[f], "_f": f})
    kanalar.sort(key=lambda d: (-d["n"], d["namn"], d["_f"]))
    if len({d["k"] for d in kanalar}) != len(kanalar):
        raise SystemExit("kollisjon i kanalnøklar")
    kanal_idx = {d["_f"]: j for j, d in enumerate(kanalar)}
    for d in kanalar:
        del d["_f"]
    kanal_per_verk = [kanal_idx.get(f, -1) for f in kanal_per_verk_fold]

    # type, year, citations, flags
    typ_idx = {k: j for j, (k, _) in enumerate(TYPAR)}
    ukjend_typar = collections.Counter()
    typ_per_verk = []
    for rec in pub + arkiv:
        kind = str(rec.get("kind") or "")
        g = TYPE_TIL_GRUPPE.get(kind)
        if g is None:
            ukjend_typar[kind] += 1
            g = "ukjend"
        typ_per_verk.append(typ_idx[g])
    ar = [int(r["year"]) for r in pub + arkiv]
    lag = [0] * n_oa + [1] * len(arkiv)
    sit = [int(p.get("citations") or 0) for p in pub] + [-1] * len(arkiv)
    merk = [0] * n_oa
    for a in arkiv:
        v = 0
        if a.get("duplicate_status") == "possible-duplicate":
            v |= 1
        if a.get("review_status") == "metadata-unreviewed":
            v |= 2
        merk.append(v)

    # Nordic country of the work
    nordisk = {k: j for j, (k, _) in enumerate(LAND_NORDISK)}
    land_per_verk = []
    ukjent_nordisk = collections.Counter()
    for rec in pub + arkiv:
        cs = rec.get("countries") or []
        idxs = sorted({nordisk[c] for c in cs if c in nordisk})
        for c in cs:
            if c not in nordisk:
                ukjent_nordisk[c] += 1
        land_per_verk.append(idxs)

    return Ns(
        pub=pub, arkiv=arkiv, indeks=indeks, ids=ids, n=n, n_oa=n_oa, n_arkiv=len(arkiv), id_til_i=id_til_i,
        rader=rader, forf_per_verk=forf_per_verk, inst_per_verk=inst_per_verk, fland_per_verk=fland_per_verk,
        inst_namn=inst_namn, inst_land=inst_land, forf_land=forf_land, forf_verk_oa=forf_verk_oa,
        inst_verk=inst_verk, land_verk=land_verk, kanalar=kanalar, kanal_per_verk=kanal_per_verk,
        typ_per_verk=typ_per_verk, ar=ar, lag=lag, sit=sit, merk=merk, land_per_verk=land_per_verk,
        forfordning_avvik=forfordning_avvik, utan_forfattarar=utan_forfattarar,
        tomme_id_plassar=tomme_id_plassar, ukjende_typar=ukjend_typar, ukjent_nordisk=ukjent_nordisk,
        kanal_namn_per_verk=kanal_namn_per_verk,
    )


def bygg_ordbokar(K: Ns, kanon_land: set[str]) -> None:
    """Dictionaries forfattarar, institusjonar, land_alle and the index columns that point into them."""
    n = K.n
    # forfattarar: one pass in work order, index at first appearance
    forf_idx: dict[str, int] = {}
    forf_lst: list[dict] = []
    forf_kol: list[list[int]] = []
    skrivemaatar: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for i in range(n):
        rad = []
        for k, nm in K.forf_per_verk[i]:
            j = forf_idx.get(k)
            if j is None:
                j = len(forf_lst)
                forf_idx[k] = j
                forf_lst.append({"k": k, "namn": nm})
            skrivemaatar[j][nm] += 1
            if j not in rad:
                rad.append(j)
        forf_kol.append(rad)
    # one author id can be written with and without diacritics in different works
    # ("Kristina Lindstrom" and "Kristina Lindström"): show the spelling that keeps its
    # diacritics (as publications.json has it), then the most common, then the first seen
    for j, c in skrivemaatar.items():
        if len(c) > 1:
            forste = forf_lst[j]["namn"]
            forf_lst[j]["namn"] = max(c, key=lambda nm: (sum(1 for ch in nm if ord(ch) > 127), c[nm], nm == forste))
    # institusjonar
    inst_ids = sorted(K.inst_verk, key=lambda x: (-len(K.inst_verk[x]), x))
    stor = inst_ids[:STORE_INSTITUSJONAR]
    manglar = [x for x in stor if x not in KORT_NAMN]
    if manglar:
        raise SystemExit(f"KORT_NAMN manglar for dei største institusjonane: {manglar}")
    inst_lst = []
    for iid in inst_ids:
        namn = sorted(K.inst_namn[iid].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        kort = KORT_NAMN.get(iid)
        if not kort:
            kort = namn if len(namn) <= KORT_MAKS else namn[: KORT_MAKS - 1].rstrip() + "…"
        inst_lst.append({"k": iid, "namn": namn, "kort": kort, "land": hovudland(K.inst_land[iid])})
    inst_idx = {d["k"]: j for j, d in enumerate(inst_lst)}
    inst_kol = [[inst_idx[x] for x in K.inst_per_verk[i]] for i in range(n)]
    # land_alle: union of authorship countries and cited_canon countries, by works then code
    koder = set(K.land_verk) | set(kanon_land)
    land_alle_koder = sorted(koder, key=lambda c: (-len(K.land_verk.get(c, ())), c))
    namn_mangel = [c for c in land_alle_koder if c not in LANDNAMN]
    if namn_mangel:
        logg(f"ADVARSEL: LANDNAMN manglar for {namn_mangel}")
    land_alle = [{"k": c, "namn": LANDNAMN.get(c, c)} for c in land_alle_koder]
    la_idx = {c: j for j, c in enumerate(land_alle_koder)}
    fland_kol = [[la_idx[c] for c in K.fland_per_verk[i]] for i in range(n)]
    K.forfattarar = forf_lst
    K.forf_idx = forf_idx
    K.forf_kol = forf_kol
    K.institusjonar = inst_lst
    K.inst_idx = inst_idx
    K.inst_kol = inst_kol
    K.land_alle = land_alle
    K.la_idx = la_idx
    K.fland_kol = fland_kol


def bygg_lenker(K: Ns) -> dict:
    """PDF status and links (spec 5.1 with amendment 61)."""
    katalog = read_json(DOCS_DATA_DIR / "pdf_katalog.json")
    funne = read_json(DOCS_DATA_DIR / "pdf_found.json")
    verifisert = {}
    for rec in katalog["items"]:
        if rec.get("verified_oa_pdf"):
            verifisert[rec["id"]] = rec
    pdf_url = [""] * K.n
    doi = [""] * K.n
    kjelde = [""] * K.n
    status = [3] * K.n
    teljar = collections.Counter()
    nedgradert = 0
    recs = K.pub + K.arkiv
    for i, rec in enumerate(recs):
        wid = K.ids[i]
        d = normalize_doi(rec.get("doi"))
        if i >= K.n_oa:
            kjelde[i] = str(rec.get("source") or "")
        adresse = str(rec.get("oa_url") or "").strip() or str(rec.get("source_url") or "").strip()
        if wid in verifisert:
            url = str(verifisert[wid].get("public_pdf_url") or "").strip() or str((funne.get(wid) or {}).get("url") or "").strip()
            if url and allowed_url(url) and safe_public_link(url):
                status[i] = 0
                pdf_url[i] = url
            else:
                nedgradert += 1
        if status[i] != 0 and adresse and allowed_url(adresse):
            host = ""
            m = re.match(r"https?://([^/]+)", adresse, re.I)
            if m:
                host = m.group(1).lower()
            er_doi_lenke = host in ("doi.org", "dx.doi.org")
            if er_doi_lenke:
                if not d:
                    d = normalize_doi(adresse)
            else:
                status[i] = 1
                pdf_url[i] = adresse
        if status[i] == 3 and d:
            status[i] = 2
        doi[i] = d
        teljar[status[i]] += 1
    if nedgradert:
        logg(f"ADVARSEL: {nedgradert} stadfesta PDF-ar fall gjennom allowed_url/safe_public_link")
    return {"status": status, "pdf": pdf_url, "doi": doi, "kjelde": kjelde, "teljar": teljar}


def merk_dublettar(K: Ns) -> int:
    """Bit 4 in `merk`: the same paper is already in the corpus under another id. Found by a
    shared verified PDF address, a shared DOI, or the same title with years at most 2 apart and
    a shared author surname. The first work of a group (OpenAlex before archive) is not marked."""
    def etternamn(nm: str) -> str:
        nm = nm.strip()
        return fold(nm.split(",")[0] if "," in nm else (nm.split() or [""])[-1])
    tittel = [re.sub(r"[^0-9a-z]+", "", fold(str(r.get("title") or ""))) for r in K.pub + K.arkiv]
    namn = [{etternamn(nm) for _, nm in K.forf_per_verk[i]} - {""} for i in range(K.n)]
    foreldre = list(range(K.n))

    def rot(a):
        while foreldre[a] != a:
            foreldre[a] = foreldre[foreldre[a]]
            a = foreldre[a]
        return a

    def slaa(a, b):
        a, b = rot(a), rot(b)
        if a != b:
            foreldre[max(a, b)] = min(a, b)

    for nokkel_av in (lambda i: K.lenker["pdf"][i] if K.lenker["status"][i] == 0 else "", lambda i: K.lenker["doi"][i].lower()):
        sett: dict[str, int] = {}
        for i in range(K.n):
            k = nokkel_av(i)
            if k:
                if k in sett:
                    slaa(sett[k], i)
                else:
                    sett[k] = i
    per_tittel = collections.defaultdict(list)
    for i, t in enumerate(tittel):
        if len(t) >= 20:
            per_tittel[t].append(i)
    for gruppe in per_tittel.values():
        for x in range(len(gruppe)):
            for y in range(x + 1, len(gruppe)):
                a, b = gruppe[x], gruppe[y]
                if abs(K.ar[a] - K.ar[b]) <= 2 and namn[a] & namn[b]:
                    slaa(a, b)
    n = 0
    for i in range(K.n):
        if rot(i) != i:
            K.merk[i] |= 4
            n += 1
    return n


# ---------------------------------------------------------------------------
# Step 2: terms from titles (amendment 48; also used for theme and sub-theme names)
# ---------------------------------------------------------------------------


def bygg_termar(titler: list[str]) -> Ns:
    n = len(titler)
    post: dict[str, list[int]] = collections.defaultdict(list)
    surf: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for i, t in enumerate(titler):
        s = unicodedata.normalize("NFC", str(t or "")).lower()
        sett: set[str] = set()
        for seg in SEG_SPLIT_RE.split(s):
            raw = TOKEN_RE.findall(seg)
            nykl = [r.translate(_STRIPP_TEGN) for r in raw]
            L = len(raw)
            for a in range(L):
                for b in range(a, min(a + 3, L)):
                    toks = nykl[a : b + 1]
                    if toks[0] in STOPPORD or toks[-1] in STOPPORD:
                        continue
                    if b == a and len(toks[0]) < 3:
                        continue
                    if any(x.isdigit() for x in toks):
                        continue
                    k = " ".join(toks)
                    surf[k][" ".join(raw[a : b + 1])] += 1
                    if k not in sett:
                        sett.add(k)
                        post[k].append(i)
    maks_df = TERM_MAKS_DEL * n
    kand = [(k, len(v)) for k, v in post.items() if TERM_MIN_DF <= len(v) <= maks_df]
    kand.sort(key=lambda kv: (-kv[1], kv[0]))
    kand = kand[:TERM_MAKS_ANTAL]
    nokklar = [k for k, _ in kand]
    df = [d for _, d in kand]
    vis = [sorted(surf[k].items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for k in nokklar]
    off = [0]
    flat: list[int] = []
    for k in nokklar:
        flat.extend(post[k])  # appended in work order, so ascending and distinct
        off.append(len(flat))
    standard = [t for t in TERM_STANDARD if t in set(nokklar)][:4]
    return Ns(k=nokklar, vis=vis, df=df, off=off, post=np.asarray(flat, dtype=np.uint16), standard=standard,
              alle_kandidatar=len(post))


def ctfidf(teljar: np.ndarray) -> np.ndarray:
    """c-TF-IDF. teljar[t, c] = works of class c with term t."""
    teljar = teljar.astype(np.float64)
    tot_c = np.maximum(teljar.sum(0), 1.0)
    snitt = tot_c.mean()
    tf_alle = np.maximum(teljar.sum(1), 1.0)
    skar = teljar / tot_c[None, :] * np.log(1.0 + snitt / tf_alle[:, None])
    # Deviation from the plain formula: weight by lift (the class's share of the term over the class's share of
    # all terms) so that words that are common everywhere ("research", "study") do not label every theme.
    lift = (teljar / tf_alle[:, None]) / (tot_c[None, :] / tot_c.sum())
    return skar * lift


def vel_ord(skår: np.ndarray, teljar: np.ndarray, T: Ns, antal: int) -> list[str]:
    """Highest scores first; skip terms that only repeat a chosen term (contiguous word containment)."""
    valde: list[str] = []
    valde_k: list[str] = []
    for t in np.argsort(-skår, kind="stable"):
        if teljar[t] <= 0:
            break
        k = T.k[t]
        kk = f" {k} "
        if any(kk in f" {v} " or f" {v} " in kk for v in valde_k):
            continue
        valde.append(T.vis[t])
        valde_k.append(k)
        if len(valde) >= antal:
            break
    return valde


def termmatrise(T: Ns, klasse: np.ndarray, antal: int) -> np.ndarray:
    """teljar[t, c] for the vocabulary; klasse[i] in 0..antal-1 or -1 (ignored)."""
    M = np.zeros((len(T.k), antal), dtype=np.int64)
    for t in range(len(T.k)):
        w = T.post[T.off[t] : T.off[t + 1]].astype(np.int64)
        kl = klasse[w]
        kl = kl[kl >= 0]
        if kl.size:
            M[t] = np.bincount(kl, minlength=antal)
    return M


# ---------------------------------------------------------------------------
# Step 3: vectors, themes, neighbours
# ---------------------------------------------------------------------------


def les_vektorar(sti: Path, dim: int, n: int) -> np.ndarray:
    if sti.suffix == ".npy":
        V = np.load(sti).astype(np.float32)
    else:
        raa = np.fromfile(sti, dtype=np.int8)
        if raa.size != n * dim:
            raise SystemExit(f"{sti}: {raa.size} byte, venta {n}x{dim}")
        V = raa.reshape(n, dim).astype(np.float32) / 127.0
    if V.shape != (n, dim):
        raise SystemExit(f"vektorformat {V.shape}, venta {(n, dim)}")
    nrm = np.linalg.norm(V, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    return (V / nrm).astype(np.float32)


def knn_cosinus(V: np.ndarray, k: int, blokk: int = 512) -> tuple[np.ndarray, np.ndarray]:
    n = V.shape[0]
    idx = np.empty((n, k), dtype=np.int32)
    sim = np.empty((n, k), dtype=np.float32)
    for b in range(0, n, blokk):
        S = V[b : b + blokk] @ V.T
        r = np.arange(S.shape[0])
        S[r, b + r] = -2.0
        part = np.argpartition(-S, k - 1, axis=1)[:, :k]
        ps = np.take_along_axis(S, part, 1)
        ordn = np.lexsort((part, -ps), axis=1)
        idx[b : b + blokk] = np.take_along_axis(part, ordn, 1)
        sim[b : b + blokk] = np.take_along_axis(ps, ordn, 1)
    return idx, sim


def kmeans_sfarisk(V: np.ndarray, k: int, seed: int = 42, maks: int = 100):
    n = V.shape[0]
    rng = np.random.default_rng(seed)
    senter = np.empty((k, V.shape[1]), dtype=np.float32)
    senter[0] = V[int(rng.integers(n))]
    d = np.maximum(1.0 - V @ senter[0], 0.0).astype(np.float64)
    for j in range(1, k):
        p = d * d
        s = p.sum()
        pick = int(rng.integers(n)) if s <= 0 else int(rng.choice(n, p=p / s))
        senter[j] = V[pick]
        d = np.minimum(d, np.maximum(1.0 - V @ senter[j], 0.0))
    forrige = None
    konvergert = False
    for _ in range(maks):
        ny = (V @ senter.T).argmax(1)
        if forrige is not None and np.array_equal(ny, forrige):
            konvergert = True
            break
        forrige = ny
        for j in range(k):
            m = ny == j
            if m.any():
                c = V[m].mean(0)
                senter[j] = c / np.linalg.norm(c)
    return ny, senter, konvergert


def bygg_tema(V: np.ndarray, indeks: dict, T: Ns, seed: int = 42) -> Ns:
    n = V.shape[0]
    lab, senter, konv = kmeans_sfarisk(V, 10, seed, 300)
    if not konv:
        logg("ADVARSEL: k-means konvergerte ikkje")
    storleik = np.bincount(lab, minlength=10)
    rekkje = sorted(range(10), key=lambda j: (-storleik[j], j))
    omkode = np.empty(10, dtype=np.int64)
    for ny_j, gml_j in enumerate(rekkje):
        omkode[gml_j] = ny_j
    tema = omkode[lab]
    senter = senter[rekkje]
    # name: greedy unique matching to the presets
    nokklar = list(indeks["presets"].keys())
    Pm = np.asarray([indeks["presets"][k] for k in nokklar], dtype=np.float32)
    Pm /= np.linalg.norm(Pm, axis=1, keepdims=True)
    cos = senter @ Pm.T
    tatt_t, tatt_p = set(), set()
    par = {}
    kandidatar = sorted(((-float(cos[a, b]), a, b) for a in range(10) for b in range(len(nokklar))))
    for negc, a, b in kandidatar:
        if a in tatt_t or b in tatt_p:
            continue
        par[a] = (b, -negc)
        tatt_t.add(a)
        tatt_p.add(b)
    # c-TF-IDF terms
    M = termmatrise(T, tema, 10)
    skår = ctfidf(M)
    tema_lst = []
    for j in range(10):
        b, c = par[j]
        key = nokklar[b]
        namn = TEMA_NAMN_OVERSTYRING.get(key, PRESET_NAMN.get(key, key))
        ord_ = vel_ord(skår[:, j], M[:, j], T, 5)
        # neutral keys in links (tema=t3): the preset a cluster is matched to is often another
        # subject than its name says, and the main page uses the preset keys for its own themes
        tema_lst.append({"k": f"t{j}", "preset": key, "namn": namn, "ord": ord_, "n": int((tema == j).sum()),
                         "sentroide": [round(float(x), 4) for x in senter[j]], "_cos": c,
                         "_auto": PRESET_NAMN.get(key, key)})
    # sub-themes
    under = np.full(n, -1, dtype=np.int64)
    under_lst = []
    for j in range(10):
        med = np.flatnonzero(tema == j)
        ks = int(min(6, max(2, round(len(med) / 150))))
        sl, _, kv = kmeans_sfarisk(V[med], ks, seed, 300)
        ss = np.bincount(sl, minlength=ks)
        rk = sorted(range(ks), key=lambda q: (-ss[q], q))
        om = np.empty(ks, dtype=np.int64)
        for ny_q, gml_q in enumerate(rk):
            om[gml_q] = ny_q
        sl = om[sl]
        klasse = np.full(n, -1, dtype=np.int64)
        klasse[med] = sl
        Ms = termmatrise(T, klasse, ks)
        sk = ctfidf(Ms)
        base = len(under_lst)
        for q in range(ks):
            ord2 = vel_ord(sk[:, q], Ms[:, q], T, 2)
            under_lst.append({"tema": j, "namn": " · ".join(ord2) if ord2 else f"{tema_lst[j]['namn']} {q + 1}",
                              "n": int((sl == q).sum())})
        under[med] = base + sl
    return Ns(tema=tema, under=under, tema_lst=tema_lst, under_lst=under_lst, senter=senter, konvergert=konv)


def ankre(tema: Ns, x: np.ndarray, y: np.ndarray) -> None:
    """Anchors: density peak per theme (most members within 4 % of the map width), medoid per sub-theme."""
    pos = np.stack([x, y], 1).astype(np.float64)
    r = 0.04 * KART_STORLEIK
    for j, t in enumerate(tema.tema_lst):
        med = np.flatnonzero(tema.tema == j)
        p = pos[med]
        d2 = ((p[:, None, :] - p[None, :, :]) ** 2).sum(2)
        ant = (d2 <= r * r).sum(1)
        b = int(np.argmax(ant))
        t["lx"], t["ly"] = int(p[b, 0]), int(p[b, 1])
    for q, u in enumerate(tema.under_lst):
        med = np.flatnonzero(tema.under == q)
        p = pos[med]
        d = np.sqrt(((p[:, None, :] - p[None, :, :]) ** 2).sum(2)).sum(1)
        b = int(np.argmin(d))
        u["lx"], u["ly"] = int(p[b, 0]), int(p[b, 1])


# ---------------------------------------------------------------------------
# Step 4: t-SNE in numpy (amendment 53)
# ---------------------------------------------------------------------------


def betinga_p(D: np.ndarray, perplexity: float) -> np.ndarray:
    n, k = D.shape
    mal = math.log(perplexity)
    Dm = D - D.min(axis=1, keepdims=True)
    beta = np.ones(n)
    lo = np.zeros(n)
    hi = np.full(n, np.inf)
    for _ in range(120):
        P = np.exp(-Dm * beta[:, None])
        sP = P.sum(1)
        H = np.log(sP) + beta * (Dm * P).sum(1) / sP
        for_hog = H > mal
        lo = np.where(for_hog, beta, lo)
        hi = np.where(for_hog, hi, beta)
        beta = np.where(for_hog, np.where(np.isinf(hi), beta * 2.0, (beta + hi) / 2.0), (beta + lo) / 2.0)
    P = np.exp(-Dm * beta[:, None])
    return P / P.sum(1, keepdims=True)


def tsne(V: np.ndarray, idx: np.ndarray, sim: np.ndarray, iterasjonar: int, seed: int,
         kontrollpunkt: Path | None, perplexity: float = 30.0, lr: float | None = None) -> np.ndarray:
    n, k = idx.shape
    D = np.maximum(2.0 - 2.0 * sim.astype(np.float64), 0.0)
    Pc = betinga_p(D, perplexity)
    rader = np.repeat(np.arange(n, dtype=np.int64), k)
    kolonner = idx.astype(np.int64).ravel()
    nokkel = np.concatenate([rader * n + kolonner, kolonner * n + rader])
    verdi = np.concatenate([Pc.ravel(), Pc.ravel()])
    uniq, inv = np.unique(nokkel, return_inverse=True)
    sum_v = np.bincount(inv, weights=verdi)
    pr = (uniq // n).astype(np.int64)
    pc = (uniq % n).astype(np.int64)
    pv = (sum_v / (2.0 * n)).astype(np.float32)
    logg(f"t-SNE: {len(pv)} kantar i P, sum {float(pv.sum()):.4f}")
    lr = lr or max(n / 12.0, 200.0)
    avtrykk = hashlib.sha1(V.tobytes() + f"{iterasjonar}|{seed}|{perplexity}|{lr}|{k}".encode()).hexdigest()
    # PCA start
    Vc = V - V.mean(0)
    _, _, vt = np.linalg.svd(Vc.astype(np.float64), full_matrices=False)
    Y = (Vc @ vt[:2].T.astype(np.float32)).astype(np.float32)
    Y = Y / Y.std(0, keepdims=True) * 1e-4
    uY = np.zeros_like(Y)
    gains = np.ones_like(Y)
    start = 0
    if kontrollpunkt is not None and kontrollpunkt.exists():
        try:
            z = np.load(kontrollpunkt, allow_pickle=False)
            if str(z["avtrykk"]) == avtrykk and int(z["it"]) <= iterasjonar:
                Y, uY, gains, start = z["Y"], z["uY"], z["gains"], int(z["it"])
                logg(f"t-SNE: held fram frå kontrollpunkt ved iterasjon {start}")
        except Exception as exc:  # noqa: BLE001
            logg(f"t-SNE: kontrollpunkt ikkje brukt ({exc})")
    fase1 = min(250, iterasjonar // 3)
    blokk = 128
    buf = np.empty((blokk, n), dtype=np.float32)
    t_start = time.time()
    for it in range(start, iterasjonar):
        eksag = 12.0 if it < fase1 else 1.0
        mom = 0.5 if it < fase1 else 0.8
        diff = Y[pr] - Y[pc]
        qe = 1.0 / (1.0 + (diff * diff).sum(1))
        w = pv * qe
        attr = np.stack([np.bincount(pr, weights=w * diff[:, 0], minlength=n),
                         np.bincount(pr, weights=w * diff[:, 1], minlength=n)], 1).astype(np.float32)
        sq = (Y * Y).sum(1)
        rep = np.empty_like(Y)
        YT = np.ascontiguousarray(Y.T)
        Z = 0.0
        for b in range(0, n, blokk):
            Yb = Y[b : b + blokk]
            m = Yb.shape[0]
            Dm = buf[:m]
            np.matmul(Yb, YT, out=Dm)  # BLAS sgemm
            Dm *= -2.0
            Dm += sq[b : b + m, None]
            Dm += sq[None, :]
            np.maximum(Dm, 0.0, out=Dm)
            Dm += 1.0
            np.reciprocal(Dm, out=Dm)  # q = 1 / (1 + D)
            rr = np.arange(m)
            Dm[rr, b + rr] = 0.0
            Z += float(Dm.sum(dtype=np.float64))
            np.multiply(Dm, Dm, out=Dm)  # q2
            rep[b : b + m] = Yb * Dm.sum(1)[:, None] - Dm @ Y
        grad = 4.0 * (eksag * attr - rep / np.float32(Z))
        same = (grad > 0) == (uY > 0)
        gains = np.where(same, gains * 0.8, gains + 0.2)
        np.maximum(gains, 0.01, out=gains)
        uY = mom * uY - lr * gains * grad
        Y = (Y + uY).astype(np.float32)
        Y -= Y.mean(0)
        if (it + 1) % 50 == 0 or it == start:
            kl = float((pv * (np.log(pv) - np.log(qe) + math.log(Z))).sum())
            logg(f"t-SNE {it + 1}/{iterasjonar}  KL≈{kl:.3f}  Z={Z:.0f}  maks|Y|={float(np.abs(Y).max()):.1f}  "
                 f"{(time.time() - t_start) / (it - start + 1):.2f}s/iter")
        if kontrollpunkt is not None and (it + 1) % 100 == 0:
            np.savez(kontrollpunkt, Y=Y, uY=uY, gains=gains, it=np.int64(it + 1), avtrykk=np.asarray(avtrykk))
    if kontrollpunkt is not None:
        np.savez(kontrollpunkt, Y=Y, uY=uY, gains=gains, it=np.int64(iterasjonar), avtrykk=np.asarray(avtrykk))
    return Y


def normaliser_kart(Y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    Yc = Y.astype(np.float64) - np.median(Y.astype(np.float64), axis=0)
    r = np.percentile(np.abs(Yc).max(1), 99.5)
    if r <= 0:
        r = 1.0
    s = 4500.0 / r
    x = np.clip(np.rint(5000.0 + Yc[:, 0] * s), 0, KART_STORLEIK).astype(np.int64)
    y = np.clip(np.rint(5000.0 - Yc[:, 1] * s), 0, KART_STORLEIK).astype(np.int64)
    return x, y


# ---------------------------------------------------------------------------
# Step 5: networks and layouts (5.5, amendment 74)
# ---------------------------------------------------------------------------

OVERLAPP_REST: dict[str, int] = {}
SPRING_BUFFER: dict = {}
SPRING_BUFFER_STI: Path | None = None


def lagre_spring_buffer() -> None:
    """Keep finished spring layouts on disk so that a crash later in the build does not cost minutes again."""
    if SPRING_BUFFER_STI is None:
        return
    # plain arrays in an .npz (no pickle): a buffer file can never run code when it is read
    tmp = SPRING_BUFFER_STI.with_name(SPRING_BUFFER_STI.stem + ".tmp.npz")
    np.savez(tmp, **{k: np.asarray(v, dtype=np.float64) for k, v in SPRING_BUFFER.items()})
    os.replace(tmp, SPRING_BUFFER_STI)


def les_spring_buffer(sti: Path) -> None:
    global SPRING_BUFFER_STI
    SPRING_BUFFER_STI = sti
    if sti.exists():
        try:
            with np.load(sti, allow_pickle=False) as z:
                SPRING_BUFFER.update({k: z[k] for k in z.files})
        except Exception as exc:  # noqa: BLE001
            logg(f"spring-buffer ikkje lesen ({exc})")


PX_ENHET = KART_STORLEIK / 900.0  # map units per pixel for a view about 900 px wide at k = 1


def bygg_graf(medlemmar: list[list[int]], min_verk: int, nokkel_av: list[str], berre=None):
    """Nodes = members that occur in >= min_verk works; edges = pairs that share a work.

    medlemmar[i] = member indices of work i (into nokkel_av). Returns node order (by n desc, key asc),
    n per node, edge list [a, b, w] with a < b positions in the node order, sorted by w desc, then (a, b).
    """
    n_per: collections.Counter = collections.Counter()
    for rad in medlemmar:
        for m in rad:
            if berre is None or berre(nokkel_av[m]):
                n_per[m] += 1
    alle = len(n_per)
    behald = [m for m, c in n_per.items() if c >= min_verk]
    behald.sort(key=lambda m: (-n_per[m], nokkel_av[m]))
    pos = {m: p for p, m in enumerate(behald)}
    par: collections.Counter = collections.Counter()
    for rad in medlemmar:
        ps = sorted({pos[m] for m in rad if m in pos})
        for x in range(len(ps)):
            for y in range(x + 1, len(ps)):
                par[(ps[x], ps[y])] += 1
    kantar = [[a, b, w] for (a, b), w in par.items()]
    kantar.sort(key=lambda e: (-e[2], e[0], e[1]))
    return Ns(noder=behald, n=[n_per[m] for m in behald], kantar=kantar, alle=alle)


def komponentar(n: int, kantar) -> list[list[int]]:
    foreldre = list(range(n))

    def finn(a):
        while foreldre[a] != a:
            foreldre[a] = foreldre[foreldre[a]]
            a = foreldre[a]
        return a

    for a, b, *_ in kantar:
        ra, rb = finn(a), finn(b)
        if ra != rb:
            foreldre[max(ra, rb)] = min(ra, rb)
    grupper: dict[int, list[int]] = collections.defaultdict(list)
    for a in range(n):
        grupper[finn(a)].append(a)
    liste_ = list(grupper.values())
    liste_.sort(key=lambda g: (-len(g), g[0]))
    return liste_


def pakk_sirklar(storleik: list[int], gap: float) -> np.ndarray:
    """Place circles of radius sqrt(size) on a spiral around the first (largest) one. Returns centres."""
    r = np.sqrt(np.asarray(storleik, dtype=np.float64))
    senter = np.zeros((len(r), 2))
    for c in range(1, len(r)):
        rho = r[0] + r[c] + gap
        vinkel0 = c * 2.399963229728653
        while True:
            m = max(24, int(2 * math.pi * rho / 1.0))
            ang = vinkel0 + 2 * math.pi * np.arange(m) / m
            kand = np.stack([rho * np.cos(ang), rho * np.sin(ang)], 1)
            d = np.sqrt(((kand[:, None, :] - senter[None, :c, :]) ** 2).sum(2))
            ok = (d >= r[c] + r[None, :c] + gap).all(1)
            if ok.any():
                senter[c] = kand[int(np.argmax(ok))]
                break
            rho += 0.5
    return senter


def _fjern_overlapp_tett(P: np.ndarray, r: np.ndarray, passes: int) -> tuple[np.ndarray, int]:
    """Dense fallback when scipy is missing (small graphs only)."""
    n = len(P)
    idx = np.arange(n)
    sgn = np.where(idx[:, None] < idx[None, :], 1.0, -1.0)
    ang = (idx[:, None] + idx[None, :]) * 2.399963229728653
    rsum = r[:, None] + r[None, :]
    brukt = 0
    for brukt in range(1, passes + 1):
        dx = P[:, 0, None] - P[None, :, 0]
        dy = P[:, 1, None] - P[None, :, 1]
        dist = np.hypot(dx, dy)
        np.fill_diagonal(dist, np.inf)
        ov = rsum - dist
        mask = ov > 0
        if not mask.any():
            return P, brukt - 1
        nul = dist < 1e-9
        d_safe = np.where(nul, 1.0, dist)
        ux = np.where(nul, sgn * np.cos(ang), dx / d_safe)
        uy = np.where(nul, sgn * np.sin(ang), dy / d_safe)
        skyv = np.where(mask, ov * 0.55, 0.0)
        P[:, 0] += (skyv * ux).sum(1)
        P[:, 1] += (skyv * uy).sum(1)
    return P, brukt


def fjern_overlapp(P: np.ndarray, r: np.ndarray, passes: int = 400) -> tuple[np.ndarray, int]:
    """Push apart until no two circles overlap (vectorised, candidate pairs from a k-d tree).

    Returns the positions and the number of passes used.
    """
    n = len(P)
    if n < 2:
        return P, 0
    P = P.copy()
    try:
        from scipy.spatial import cKDTree
    except ImportError:  # pragma: no cover
        return _fjern_overlapp_tett(P, r, passes)
    rmaks = float(r.max())
    brukt = 0
    for brukt in range(1, passes + 1):
        par = cKDTree(P).query_pairs(2.0 * rmaks, output_type="ndarray")
        if len(par) == 0:
            return P, brukt - 1
        i, j = par[:, 0], par[:, 1]
        dx = P[i, 0] - P[j, 0]
        dy = P[i, 1] - P[j, 1]
        dist = np.hypot(dx, dy)
        ov = r[i] + r[j] - dist
        m = ov > 0
        if not m.any():
            return P, brukt - 1
        i, j, dx, dy, dist, ov = i[m], j[m], dx[m], dy[m], dist[m], ov[m]
        nul = dist < 1e-9
        ang = (i + j) * 2.399963229728653
        d_safe = np.where(nul, 1.0, dist)
        ux = np.where(nul, np.cos(ang), dx / d_safe)
        uy = np.where(nul, np.sin(ang), dy / d_safe)
        s = ov * 0.55
        P[:, 0] += np.bincount(i, weights=s * ux, minlength=n) - np.bincount(j, weights=s * ux, minlength=n)
        P[:, 1] += np.bincount(i, weights=s * uy, minlength=n) - np.bincount(j, weights=s * uy, minlength=n)
    return P, brukt


def tel_overlapp(P: np.ndarray, r: np.ndarray) -> int:
    n = len(P)
    if n < 2:
        return 0
    try:
        from scipy.spatial import cKDTree
    except ImportError:  # pragma: no cover
        d = np.hypot(P[:, 0, None] - P[None, :, 0], P[:, 1, None] - P[None, :, 1])
        np.fill_diagonal(d, np.inf)
        return int(((r[:, None] + r[None, :] - d) > 1e-6).sum() // 2)
    par = cKDTree(P).query_pairs(2.0 * float(r.max()), output_type="ndarray")
    if len(par) == 0:
        return 0
    d = np.hypot(P[par[:, 0], 0] - P[par[:, 1], 0], P[par[:, 0], 1] - P[par[:, 1], 1])
    return int(((r[par[:, 0]] + r[par[:, 1]] - d) > 1e-6).sum())


def tilpass_ramme(P: np.ndarray, margin: float = 0.04) -> np.ndarray:
    """Equal scale on both axes, centred, inside the margin."""
    lo = P.min(0)
    hi = P.max(0)
    ut = max(hi[0] - lo[0], hi[1] - lo[1], 1e-9)
    s = KART_STORLEIK * (1 - 2 * margin) / ut
    c = (lo + hi) / 2.0
    return (P - c) * s + KART_STORLEIK / 2.0


def utforming(n: int, kantar, radius_px: np.ndarray, vekt_kol: int = 2, seed: int = 11, namn: str = "") -> tuple[np.ndarray, list[int]]:
    """Force-directed layout per connected component, packed on a spiral, overlaps removed.

    kantar = [[a, b, w, ...]] with the weight in column ``vekt_kol``. Returns positions (n, 2) in map
    units and the component id per node (0 = largest).
    """
    import networkx as nx  # imported here so CI never needs it

    komp = komponentar(n, kantar)
    lokal: list[np.ndarray] = []
    kant_per: dict[int, list] = collections.defaultdict(list)
    ref = {}
    for c, g in enumerate(komp):
        for a in g:
            ref[a] = c
    for e in kantar:
        kant_per[ref[e[0]]].append(e)
    for c, g in enumerate(komp):
        if len(g) == 1:
            p = np.zeros((1, 2))
        elif len(g) == 2:
            p = np.array([[-0.5, 0.0], [0.5, 0.0]])
        else:
            nokkel = hashlib.sha1(repr((g, [(e[0], e[1], e[vekt_kol]) for e in kant_per[c]], seed, nx.__version__)).encode()).hexdigest()
            if nokkel in SPRING_BUFFER:
                p = SPRING_BUFFER[nokkel]
            else:
                G = nx.Graph()
                G.add_nodes_from(g)
                for e in kant_per[c]:
                    G.add_edge(e[0], e[1], sw=math.sqrt(e[vekt_kol]))
                t0 = time.time()
                pos = nx.spring_layout(G, k=1.2 / math.sqrt(len(g)), weight="sw", iterations=500, seed=seed)
                p = np.asarray([pos[a] for a in g], dtype=np.float64)
                SPRING_BUFFER[nokkel] = p
                lagre_spring_buffer()
                logg(f"{namn}: komponent {c} med {len(g)} nodar lagt ut på {time.time() - t0:.1f}s")
        p = p - p.mean(0)
        avst = np.sqrt((p * p).sum(1))
        # large components have a few far-flung leaf nodes: size the circle by the 98th percentile so that the
        # dense core is not made tiny by them (the overlap pass cleans up any collision with a neighbour)
        m = np.quantile(avst, 0.98) if len(g) >= 50 else avst.max()
        lokal.append(p / m if m > 0 else p)
    storleik = [len(g) for g in komp]
    gap = 0.05 * math.sqrt(storleik[0])
    for _ in range(4):
        senter = pakk_sirklar(storleik, gap)
        P = np.zeros((n, 2))
        for c, g in enumerate(komp):
            P[g] = senter[c] + lokal[c] * math.sqrt(storleik[c])
        ut = max(np.ptp(P[:, 0]), np.ptp(P[:, 1]), 1e-9)
        s = KART_STORLEIK * 0.92 / ut
        ny_gap = 0.03 * KART_STORLEIK / s
        if abs(ny_gap - gap) < 0.02 * gap:
            break
        gap = ny_gap
    P = tilpass_ramme(P)
    r_units = (radius_px + 2.0) * PX_ENHET
    gjenstar = 0
    for runde in range(4):
        P, brukt = fjern_overlapp(P, r_units)
        P = tilpass_ramme(P)
        gjenstar = tel_overlapp(P, r_units)
        if gjenstar == 0:
            break
    OVERLAPP_REST[namn] = gjenstar
    logg(f"{namn}: {len(komp)} komponentar, overlapp att etter fjerning: {gjenstar}")
    P = np.clip(np.rint(P), 0, KART_STORLEIK)
    ids = [0] * n
    for c, g in enumerate(komp):
        for a in g:
            ids[a] = c
    return P, ids


def bygg_nett(K: Ns, modus: str, namn: str, gjenbruk: dict | None = None) -> dict:
    if modus == "inst":
        medlemmar = K.inst_kol
        nokkel_av = [d["k"] for d in K.institusjonar]
        graf = bygg_graf(medlemmar, MIN_VERK_NETT, nokkel_av)
        land_av = [K.institusjonar[m]["land"] for m in graf.noder]
    else:
        medlemmar = K.forf_kol
        nokkel_av = [d["k"] for d in K.forfattarar]
        graf = bygg_graf(medlemmar, MIN_VERK_NETT, nokkel_av, berre=lambda k: k.startswith("A"))
        land_av = [hovudland(K.forf_land[nokkel_av[m]]) for m in graf.noder]
    nmaks = max(graf.n) if graf.n else 1
    radius = 3.0 + 17.0 * np.sqrt(np.asarray(graf.n, dtype=np.float64) / nmaks)
    refs = list(graf.noder)
    if gjenbruk and gjenbruk.get("noder", {}).get("ref") == refs and gjenbruk.get("kantar") == graf.kantar:
        x = gjenbruk["noder"]["x"]
        y = gjenbruk["noder"]["y"]
        komp = gjenbruk["noder"]["komp"]
        logg(f"{namn}: bruker eksisterande utforming")
    else:
        P, komp = utforming(len(refs), graf.kantar, radius, namn=namn)
        x = P[:, 0].astype(np.int64).tolist()
        y = P[:, 1].astype(np.int64).tolist()
    la_idx = K.la_idx
    return {
        "format": "utforsk-nett-1", "generert": GENERERT, "modus": modus,
        "noder": {"ref": refs, "n": graf.n, "land": [la_idx.get(c, -1) for c in land_av], "x": x, "y": y, "komp": komp},
        "kantar": graf.kantar,
        "tal": {"alle": graf.alle, "vist": len(refs), "min_verk": MIN_VERK_NETT, "kantar": len(graf.kantar)},
    }


# ---------------------------------------------------------------------------
# Step 6: citations (5.6 with amendments 54 to 58, 70, 76)
# ---------------------------------------------------------------------------

PARTIKLAR = {"van", "von", "de", "der", "del"}
INSTITUSJON_RE = re.compile(r"univers|institut|associat|college|school")


# Classics whose OpenAlex records carry a reviewer, an editor or no author, so that one
# book became several nodes labelled with the wrong name ("Stewart 1984" for Schön's
# The Reflective Practitioner). Checked by hand against the cited_canon rows on
# 2026-11-13. Every title key listed (canonical key and aliases) becomes one node,
# whatever the first author, labelled "{namn} {år}".
KJELDE_RETTING: dict[str, tuple[str, int, tuple[str, ...]]] = {
    "reflectivepractitionerhowprofessionalsthinkinaction": ("Schön", 1983, ("reflectivepractitioner",)),
    "educatingthereflectivepractitioner": ("Schön", 1987, (
        "educatingthereflectivepractitionertowardanewdesignforteachingandlearningintheprofessions",)),
    "designerlywaysofknowing": ("Cross", 1982, ()),
    "designatwork": ("Greenbaum", 1991, ()),
    "workorienteddesignofcomputerartifacts": ("Ehn", 1988, ()),
    "designsforthepluriverse": ("Escobar", 2018, (
        "designsforthepluriverseradicalinterdependenceautonomyandthemakingofworlds",)),
    "designfortherealworld": ("Papanek", 1971, ("designfortherealworldhumanecologyandsocialchange",)),
    "situatedlearning": ("Lave", 1991, ("situatedlearninglegitimateperipheralparticipation",)),
    "thoughtfulinteractiondesign": ("Löwgren", 2004, (
        "thoughtfulinteractiondesignadesignperspectiveoninformationtechnology",)),
    "speculativeeverythingdesignfictionandsocialdreaming": ("Dunne", 2013, ()),
    "designwayintentionalchangeinanunpredictableworld": ("Nelson", 2003, (
        "designwayintentionalchangeinanunpredictableworldfoundationsandfundamentalsofdesigncompetence",)),
    "engineeringdesignasystematicapproach": ("Pahl", 1984, ()),
    "sciencesoftheartificial": ("Simon", 1969, ()),
    "designofeverydaythings": ("Norman", 1988, ("designofeverydaythingsrevisedandexpandededition",)),
    "tacitdimension": ("Polanyi", 1966, ()),
}
KJELDE_ALIAS: dict[str, str] = {}
for _k, (_n, _a, _alias) in KJELDE_RETTING.items():
    KJELDE_ALIAS[_k] = _k
    for _x in _alias:
        KJELDE_ALIAS[_x] = _k


def tittelnokkel(t: object) -> str:
    s = fold(t)
    if s.startswith("the "):
        s = s[4:]
    return re.sub(r"[^a-z0-9]+", "", s)


def forste_etternamn_fold(forfattarar: str) -> str:
    seg = str(forfattarar or "").split(";")[0].strip()
    ord_ = fold(seg).split()
    return ord_[-1] if ord_ else ""


def etternamn_visning(seg: str, komma_er_etternamn: bool) -> str:
    seg = seg.strip()
    if komma_er_etternamn and "," in seg:
        return seg.split(",")[0].strip()
    ord_ = seg.split()
    if not ord_:
        return ""
    i = len(ord_) - 1
    while i > 0 and ord_[i - 1].lower() in PARTIKLAR:
        i -= 1
    return " ".join(ord_[i:])


def merkelapp(forfattarar: str, ar: int | None, tittel: str, komma_er_etternamn: bool = False) -> str:
    seg = str(forfattarar or "").split(";")[0].strip()
    if not seg or INSTITUSJON_RE.search(seg.lower()):
        namn = " ".join(str(tittel or "").split()[:2])
    else:
        namn = etternamn_visning(seg, komma_er_etternamn)
    namn = namn or "Utan namn"
    return f"{namn} {ar}" if ar else namn


def bygg_siteringar(db: sqlite3.Connection, K: Ns) -> Ns:
    n, n_oa = K.n, K.n_oa
    id_til_i = K.id_til_i
    canon = {}
    for cid, doi, tittel, ar, kind, forf, kjelde, countries, nci in db.execute(
        "select id, doi, title, year, kind, authors, source, countries, nordic_citing_count from cited_canon"
    ):
        try:
            land = json.loads(countries or "[]")
        except ValueError:
            land = []
        canon[cid] = {"id": cid, "doi": normalize_doi(doi), "tittel": tittel or "", "ar": ar or None,
                      "forf": forf or "", "kjelde": (kjelde or "").strip(), "land": [c for c in land if c]}
    ikkje_korpus = {c: r for c, r in canon.items() if c not in id_til_i}

    ref_alle = [-1] * n
    for i in range(n_oa):
        ref_alle[i] = 0
    ref_utan = [-1] * n
    for i in range(n_oa):
        ref_utan[i] = 0
    mal: list[set] = [set() for _ in range(n)]
    siterarar_verk: dict[int, set[int]] = collections.defaultdict(set)
    siterarar_canon: dict[str, set[int]] = collections.defaultdict(set)
    rader = til_korpus = til_kanon = sjolv = 0
    siterande = set()
    for citing, cited in db.execute(
        "select r.citing_id, r.cited_id from references_all r join works w on w.id = r.citing_id "
        "where w.in_scope = 1 order by r.rowid"
    ):
        ci = id_til_i[citing]
        rader += 1
        siterande.add(ci)
        ref_alle[ci] += 1
        if cited in id_til_i:
            til_korpus += 1
            if cited == citing:
                sjolv += 1
                continue
            mal[ci].add(id_til_i[cited])
            siterarar_verk[id_til_i[cited]].add(ci)
        elif cited in canon:
            til_kanon += 1
            mal[ci].add(cited)
            siterarar_canon[cited].add(ci)
        else:
            ref_utan[ci] += 1
    logg(f"referansar {rader}, til korpus {til_korpus} (sjølv {sjolv}), til kanon {til_kanon}, siterande verk {len(siterande)}")

    # merge canon items: normalised title + first author surname
    grupper: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for cid in sorted(ikkje_korpus):
        r = ikkje_korpus[cid]
        tk = tittelnokkel(r["tittel"])
        if tk in KJELDE_ALIAS:
            grupper[(KJELDE_ALIAS[tk], "*")].append(cid)
        elif not tk:
            grupper[("~" + cid, "")].append(cid)
        else:
            grupper[(tk, forste_etternamn_fold(r["forf"]))].append(cid)
    namngitt: dict[str, list[str]] = collections.defaultdict(list)
    for (tk, sur) in grupper:
        if sur and not tk.startswith("~"):
            namngitt[tk].append(sur)

    def gruppe_siterarar(nykl) -> int:
        s = set()
        for cid in grupper[nykl]:
            s |= siterarar_canon.get(cid, set())
        return len(s)

    for (tk, sur) in sorted(k for k in grupper if k[1] == "" and not k[0].startswith("~")):
        kand = namngitt.get(tk)
        if kand:
            best = sorted(kand, key=lambda s2: (-gruppe_siterarar((tk, s2)), s2))[0]
            grupper[(tk, best)].extend(grupper.pop((tk, sur)))
    noder = []
    for nykl, medl in grupper.items():
        sit = set()
        for cid in medl:
            sit |= siterarar_canon.get(cid, set())
        if not sit:
            continue
        medl_s = sorted(medl, key=lambda c: (-len(siterarar_canon.get(c, ())), c))
        noder.append((nykl, medl_s, sit))

    def merge_nokkel(nd):
        nykl = nd[0]
        return f"{nykl[0]}|{nykl[1]}" if not nykl[0].startswith("~") else nykl[0]

    noder.sort(key=lambda nd: (-len(nd[2]), merge_nokkel(nd), nd[1][0]))
    m = len(noder)
    canon_til_node = {}
    kj = {"k": [], "tittel": [], "merkelapp": [], "ar": [], "kanalnamn": [], "kgr": [], "fland": [], "doi": []}
    n_sitert = [0] * (n + m)
    for v, siterarar in siterarar_verk.items():
        n_sitert[v] = len(siterarar)
    for j, (nykl, medl, sit) in enumerate(noder):
        rep = canon[medl[0]]
        for cid in medl:
            canon_til_node[cid] = n + j
        aar = [canon[c]["ar"] for c in medl if canon[c]["ar"]]
        ar_ = min(aar) if aar else None
        rett = KJELDE_RETTING.get(nykl[0]) if nykl[1] == "*" else None
        if rett:
            ar_ = rett[1]
        kanalnamn = next((canon[c]["kjelde"] for c in medl if canon[c]["kjelde"]), "")
        doi_ = next((canon[c]["doi"] for c in medl if canon[c]["doi"]), "")
        land = sorted({K.la_idx[c] for cid in medl for c in canon[cid]["land"] if c in K.la_idx})
        kj["k"].append(rep["id"])
        kj["tittel"].append(rep["tittel"])
        kj["merkelapp"].append(f"{rett[0]} {rett[1]}" if rett else merkelapp(rep["forf"], ar_, rep["tittel"]))
        kj["ar"].append(ar_)
        kj["kanalnamn"].append(kanalnamn)
        kj["kgr"].append(kanal_gruppe(kanalnamn))
        kj["fland"].append(land)
        kj["doi"].append(doi_)
        n_sitert[n + j] = len(sit)

    ref_off = [0]
    ref_til: list[int] = []
    for i in range(n):
        if i < n_oa:
            noder_i = sorted({(t if isinstance(t, int) else canon_til_node[t]) for t in mal[i]})
            ref_til.extend(noder_i)
        ref_off.append(len(ref_til))
    til_kjelde = sum(1 for t in ref_til if t >= n)
    logg(f"kjelder (utanfor korpus, sitert): {m}; bruksklare referansar etter samanslåing: {len(ref_til)}")
    return Ns(kj=kj, m=m, ref_off=ref_off, ref_til=ref_til, ref_alle=ref_alle, ref_utan=ref_utan, n_sitert=n_sitert,
              rader=rader, til_korpus=til_korpus, til_kanon=til_kanon, sjolv=sjolv, siterande=len(siterande),
              mal=mal, canon=canon, antal_canon_ikkje_korpus=len(ikkje_korpus),
              grupper_med_fleire=sum(1 for nd in noder if len(nd[1]) > 1), til_kjelde=til_kjelde)


def forfattarmerkelapp(K: Ns, i: int) -> str:
    """Label of a corpus work: first author's surname and year."""
    if K.forf_per_verk[i]:
        k, nm = K.forf_per_verk[i][0]
        namn = nm
        komma = k.startswith("n:")
    else:
        namn, komma = "", False
    return merkelapp(namn, K.ar[i], K.pub[i]["title"] if i < K.n_oa else K.arkiv[i - K.n_oa]["title"], komma)


def bygg_kart_sit(K: Ns, S: Ns, gjenbruk: dict | None) -> dict:
    n = K.n
    ant = 150
    rang = sorted(range(n + S.m), key=lambda v: (-S.n_sitert[v], v))[:ant]
    pos = {v: p for p, v in enumerate(rang)}
    par: collections.Counter = collections.Counter()
    for i in range(K.n_oa):
        ps = sorted(pos[t] for t in S.ref_til[S.ref_off[i] : S.ref_off[i + 1]] if t in pos)
        for x in range(len(ps)):
            for y in range(x + 1, len(ps)):
                par[(ps[x], ps[y])] += 1
    nv = [S.n_sitert[v] for v in rang]
    alle = []
    for (a, b), c in par.items():
        if c >= 2:
            alle.append((c / math.sqrt(nv[a] * nv[b]), a, b, c))
    alle.sort(key=lambda e: (-e[0], e[1], e[2]))
    behald = {(a, b) for _, a, b, _ in alle[:600]}
    per_node: dict[int, list] = collections.defaultdict(list)
    for e in alle:
        per_node[e[1]].append(e)
        per_node[e[2]].append(e)
    for p, lst in per_node.items():
        for _, a, b, _ in lst[:2]:
            behald.add((a, b))
    kant = [[a, b, c, round(w, 4)] for w, a, b, c in alle if (a, b) in behald]
    kant.sort(key=lambda e: (-e[3], e[0], e[1]))

    import networkx as nx

    G = nx.Graph()
    G.add_nodes_from(range(ant))
    for a, b, c, w in kant:
        G.add_edge(a, b, w=w)
    samf = [set(c) for c in nx.community.louvain_communities(G, weight="w", resolution=1.2, seed=3)]
    # merge communities under 5 nodes into the neighbour they share most weight with
    while len(samf) > 3 and min(len(c) for c in samf) < 5:
        minste = min(range(len(samf)), key=lambda q: (len(samf[q]), min(samf[q])))
        vekt = collections.Counter()
        for a, b, c, w in kant:
            if a in samf[minste] and b not in samf[minste]:
                for q, cs in enumerate(samf):
                    if b in cs:
                        vekt[q] += w
            elif b in samf[minste] and a not in samf[minste]:
                for q, cs in enumerate(samf):
                    if a in cs:
                        vekt[q] += w
        if vekt:
            mål = sorted(vekt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        else:
            mål = max((q for q in range(len(samf)) if q != minste), key=lambda q: (len(samf[q]), -q))
        samf[mål] |= samf[minste]
        del samf[minste]
    samf.sort(key=lambda c: (-len(c), min(c)))
    gr = [0] * ant
    for q, c in enumerate(samf):
        for a in c:
            gr[a] = q
    # labels, unique within the map
    base = []
    for v in rang:
        if v < n:
            base.append(forfattarmerkelapp(K, v))
        else:
            base.append(S.kj["merkelapp"][v - n])
    sett = collections.Counter()
    unike = []
    for lab in base:
        sett[lab] += 1
        unike.append(lab if sett[lab] == 1 else f"{lab} {chr(ord('a') + sett[lab] - 1)}")
    grupper = []
    for q, c in enumerate(samf):
        topp = min(c)  # position order is n_sitert order, so the smallest position is the most cited
        grupper.append({"namn": f"{unike[topp]} m.fl.", "n": len(c)})
    radius = 4.0 + 1.15 * np.sqrt(np.asarray(nv, dtype=np.float64))
    if gjenbruk and gjenbruk.get("noder") == rang and gjenbruk.get("kantar") == kant:
        x, y = gjenbruk["x"], gjenbruk["y"]
        logg("siteringskart: bruker eksisterande utforming")
    else:
        P, _ = utforming(ant, kant, radius, vekt_kol=3, namn="siteringskart")
        x = P[:, 0].astype(np.int64).tolist()
        y = P[:, 1].astype(np.int64).tolist()
    return {"noder": rang, "merkelapp": unike, "x": x, "y": y, "gr": gr, "kantar": kant, "grupper": grupper}


def land_topp(K: Ns, S: Ns) -> tuple[list[int], dict]:
    """The eight countries with the largest flow (left plus right) over the whole corpus, ties by code."""
    n = K.n
    ukjend = -1
    venstre = collections.Counter()
    hogre = collections.Counter()
    til_kjelde = ukjent_kanal = ukjent_land = 0
    for i in range(K.n_oa):
        A = K.fland_kol[i] or [ukjend]
        for v in S.ref_til[S.ref_off[i] : S.ref_off[i + 1]]:
            B = K.fland_kol[v] if v < n else S.kj["fland"][v - n]
            B = B or [ukjend]
            w = 1.0 / (len(A) * len(B))
            for a in A:
                venstre[a] += w * len(B)
            for b in B:
                hogre[b] += w * len(A)
            if v >= n:
                til_kjelde += 1
                if S.kj["kgr"][v - n] == UKJEND_GRUPPE:
                    ukjent_kanal += 1
                if not S.kj["fland"][v - n]:
                    ukjent_land += 1
    kodar = [d["k"] for d in K.land_alle]
    tot = {c: venstre.get(c, 0.0) + hogre.get(c, 0.0) for c in range(len(kodar))}
    rang = sorted(tot, key=lambda c: (-tot[c], kodar[c]))
    topp = [c for c in rang if tot[c] > 0][:8]
    info = {"mal_utan_kanal_del": round(ukjent_kanal / til_kjelde, 4) if til_kjelde else 0.0,
            "mal_utan_land_del": round(ukjent_land / til_kjelde, 4) if til_kjelde else 0.0,
            "ref_til_kjelder": til_kjelde}
    return topp, info


# ---------------------------------------------------------------------------
# Step 7: places (5.7, amendment 69)
# ---------------------------------------------------------------------------

OPENALEX_INST = "https://api.openalex.org/institutions"
HENT_UA = "visdata-builder/1.0"
HENT_MAKS_BATCH = 40
HENT_MAKS_ENKELT = 60

LANDSENTER = {
    "NO": (60.5, 8.5), "SE": (62.0, 15.0), "DK": (56.0, 10.0), "FI": (64.0, 26.0), "IS": (65.0, -18.0),
    "GB": (54.0, -2.0), "US": (39.0, -98.0), "DE": (51.0, 10.0), "NL": (52.2, 5.3), "FR": (46.6, 2.5),
    "IT": (42.8, 12.5), "ES": (40.0, -3.7), "CA": (56.0, -106.0), "AU": (-25.0, 134.0), "CH": (46.8, 8.2),
    "AT": (47.5, 14.5), "BE": (50.6, 4.7), "IE": (53.2, -8.0), "PL": (52.0, 19.0), "PT": (39.5, -8.0),
    "CN": (35.0, 103.0), "JP": (36.0, 138.0), "KR": (36.5, 127.8), "IN": (22.0, 79.0), "BR": (-10.0, -52.0),
    "MX": (23.6, -102.5), "ZA": (-29.0, 25.0), "NZ": (-41.0, 174.0), "SG": (1.35, 103.8), "HK": (22.3, 114.2),
    "TR": (39.0, 35.0), "RU": (61.0, 100.0), "EE": (58.7, 25.5), "LV": (56.9, 24.6), "LT": (55.2, 23.9),
    "CZ": (49.8, 15.5), "HU": (47.2, 19.5), "GR": (39.0, 22.0), "IL": (31.5, 35.0), "IR": (32.5, 54.0),
    "AE": (24.0, 54.0), "SA": (24.0, 45.0), "EG": (26.5, 30.0), "NG": (9.0, 8.0), "KE": (0.0, 38.0),
    "GH": (7.9, -1.0), "AR": (-34.0, -64.0), "CL": (-35.7, -71.5), "CO": (4.6, -74.0), "TW": (23.7, 121.0),
    "MY": (4.0, 102.0), "TH": (15.0, 101.0), "ID": (-2.0, 118.0), "VN": (16.0, 106.0),
}


def _hent_json(url: str):
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": HENT_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as svar:
        return json.loads(svar.read().decode("utf-8"))


def _kort_inst(r: dict) -> dict:
    geo = r.get("geo") or {}
    return {"id": str(r.get("id") or "").rsplit("/", 1)[-1], "display_name": r.get("display_name"),
            "country_code": r.get("country_code"),
            "geo": {k: geo.get(k) for k in ("city", "region", "country_code", "latitude", "longitude")}}


def hent_stader(ids: list[str], raa_sti: Path) -> dict:
    """Fetch geo data for institutions missing in the raw cache. Stops at the first 403 or 429."""
    import urllib.error
    import urllib.parse

    raa = read_json(raa_sti, {"henta": None, "resultat": {}, "utan_svar": []})
    resultat = raa["resultat"]
    utan = set(raa.get("utan_svar", []))
    mangla = [i for i in ids if i not in resultat and i not in utan]
    logg(f"stader: {len(ids)} institusjonar, {len(resultat)} i buffer, {len(mangla)} å hente")
    kall = 0
    stoppa = False
    batchar = [mangla[k : k + 50] for k in range(0, len(mangla), 50)]
    for b in batchar:
        if kall >= HENT_MAKS_BATCH:
            break
        filt = "ids.openalex:" + "|".join(b)
        url = (OPENALEX_INST + "?" + urllib.parse.urlencode(
            {"filter": filt, "per-page": 50, "select": "id,display_name,country_code,geo"}, safe=":,", quote_via=urllib.parse.quote))
        try:
            svar = _hent_json(url)
        except urllib.error.HTTPError as e:
            logg(f"stader: HTTP {e.code} for batch {kall + 1}; stoppar")
            stoppa = True
            break
        except Exception as e:  # noqa: BLE001
            logg(f"stader: nettverksfeil ({e}); stoppar")
            stoppa = True
            break
        kall += 1
        for r in svar.get("results", []):
            k = _kort_inst(r)
            resultat[k["id"]] = k
        logg(f"stader: batch {kall}/{len(batchar)} ok, {len(resultat)} totalt")
        time.sleep(1.2)
    if not stoppa:
        att = [i for i in mangla if i not in resultat]
        for i in att[:HENT_MAKS_ENKELT]:
            try:
                r = _hent_json(f"{OPENALEX_INST}/{i}?select=id,display_name,country_code,geo")
            except urllib.error.HTTPError as e:
                if e.code in (403, 429):
                    logg(f"stader: HTTP {e.code} på enkeltoppslag; stoppar")
                    break
                if e.code == 404:
                    utan.add(i)
                    continue
                break
            except Exception as e:  # noqa: BLE001
                logg(f"stader: nettverksfeil på enkeltoppslag ({e})")
                break
            k = _kort_inst(r)
            resultat[k["id"] or i] = k
            time.sleep(1.2)
        att = [i for i in mangla if i not in resultat and i not in utan]
        if att:
            logg(f"stader: {len(att)} institusjonar utan svar etter enkeltoppslag")
    if mangla:
        raa["henta"] = now_iso()
        raa["resultat"] = {k: resultat[k] for k in sorted(resultat)}
        raa["utan_svar"] = sorted(utan)
        skriv_bytes(raa_sti, json_bytes(raa))
    rest = [i for i in ids if i not in resultat and i not in utan]
    if rest:
        logg(f"stader: att å hente ({len(rest)}): {' '.join(rest[:30])}{' …' if len(rest) > 30 else ''}")
    return raa


def skriv_kjelde_stader(raa: dict, K: Ns, ut: Path) -> dict:
    inst = {}
    manglar = []
    for iid, r in raa["resultat"].items():
        g = r.get("geo") or {}
        lat, lon = g.get("latitude"), g.get("longitude")
        by = g.get("city") or g.get("region")
        land = g.get("country_code") or r.get("country_code")
        if lat is None or lon is None or not by or not land:
            manglar.append(iid)
            continue
        inst[iid] = {"namn": r.get("display_name") or "", "by": by, "land": str(land).upper(), "lat": round(float(lat), 4),
                     "lon": round(float(lon), 4)}
    manglar.extend(raa.get("utan_svar", []))
    ut_obj = {"format": "utforsk-kjelde-stader-1", "henta": raa.get("henta"),
              "kjelde": "OpenAlex institutions API (CC0)",
              "institusjonar": {k: inst[k] for k in sorted(inst)}, "manglar": sorted(set(manglar))}
    skriv_bytes(ut, json_bytes(ut_obj))
    return ut_obj


def _avstand_km(lat1, lon1, lat2, lon2) -> float:
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371.0 * math.hypot(x, y)


def bygg_stader(K: Ns, kj: dict | None) -> dict:
    kjinst = (kj or {}).get("institusjonar", {})
    plassar: dict[str, list[dict]] = collections.defaultdict(list)  # base key -> real places
    inst_til: list[tuple[str, int] | None] = []
    omtrentleg = 0
    utanfor: list[str] = []
    for d in K.institusjonar:
        e = kjinst.get(d["k"])
        approx = False
        if not e:
            sentrum = LANDSENTER.get(d["land"])
            if not sentrum:
                inst_til.append(None)
                continue
            e = {"by": LANDNAMN.get(d["land"], d["land"]), "land": d["land"], "lat": sentrum[0], "lon": sentrum[1]}
            approx = True
            omtrentleg += 1
        if e["land"] in {k for k, _ in LAND_NORDISK} and not (
            NORDISK_RAMME[0] <= e["lat"] <= NORDISK_RAMME[1] and NORDISK_RAMME[2] <= e["lon"] <= NORDISK_RAMME[3]
        ):
            utanfor.append(d["k"])
            inst_til.append(None)
            continue
        by = BYNAMN.get(e["by"], e["by"])
        cc = e["land"].lower()
        base = cc + "-" + (re.sub(r"[^a-z0-9]+", "-", fold(by)).strip("-") or "ukjend")
        funne = None
        for p in plassar[base]:
            if _avstand_km(p["lat"] / p["m"], p["lon"] / p["m"], e["lat"], e["lon"]) <= 60.0:
                funne = p
                break
        if funne is None:
            nr = len(plassar[base]) + 1
            funne = {"k": base if nr == 1 else f"{base}-{nr}", "by": by, "land": e["land"], "lat": 0.0, "lon": 0.0,
                     "m": 0, "inst": [], "omtrentleg": approx}
            plassar[base].append(funne)
        funne["lat"] += e["lat"]
        funne["lon"] += e["lon"]
        funne["m"] += 1
        funne["omtrentleg"] = funne["omtrentleg"] and approx
        inst_til.append((funne["k"], 0))
        funne["inst"].append(d["k"])
    alle = [p for lst in plassar.values() for p in lst]
    nøkkel_til_p = {p["k"]: p for p in alle}
    verk_per_stad: dict[str, set[int]] = collections.defaultdict(set)
    inst_nr = {d["k"]: j for j, d in enumerate(K.institusjonar)}
    stad_av_inst = {}
    for j, t in enumerate(inst_til):
        if t is not None:
            stad_av_inst[j] = t[0]
    for i in range(K.n):
        for j in K.inst_kol[i]:
            s = stad_av_inst.get(j)
            if s:
                verk_per_stad[s].add(i)
    alle.sort(key=lambda p: (-len(verk_per_stad.get(p["k"], ())), p["k"]))
    pos = {p["k"]: q for q, p in enumerate(alle)}
    stader = [{"k": p["k"], "by": p["by"], "land": p["land"], "lat": round(p["lat"] / p["m"], 3),
               "lon": round(p["lon"] / p["m"], 3), "n": len(verk_per_stad.get(p["k"], ()))} for p in alle]
    inst_stad = [pos[stad_av_inst[j]] if j in stad_av_inst else -1 for j in range(len(K.institusjonar))]
    med = sum(1 for x in inst_stad if x >= 0)
    ut = {"format": "utforsk-stader-1", "generert": GENERERT,
          "kjelde": "OpenAlex institutions API (CC0)" if kj and kjinst else "landsentrum (omtrentleg, API utilgjengeleg)",
          "stader": stader, "inst_stad": inst_stad,
          "tal": {"institusjonar": len(K.institusjonar), "med_stad": med, "stader": len(stader),
                  "omtrentlege_institusjonar": omtrentleg, "utanfor_land": len(utanfor)}}
    return ut


# ---------------------------------------------------------------------------
# Step 8: assembling, writing, reports
# ---------------------------------------------------------------------------

UPPER_GRENSER = {
    "manifest.json": 10_000, "verk.json": 1_900_000, "lenker.json": 700_000, "nett_inst.json": 300_000,
    "nett_forf.json": 600_000, "stader.json": 200_000, "siteringar.json": 1_000_000, "tid.json": 400_000,
    "termar.bin": 900_000,
}

FORVENTA = {
    "verk": 6432, "openalex": 4694, "arkiv": 1738, "land_kjent": 6024, "forfattarland_kjent": 4603,
    "institusjonar": 1090, "nett_inst_noder": 531, "nett_inst_kantar": 3567, "forfattarar_openalex": 6033,
    "nett_forf_noder": 1824, "nett_forf_kantar": 4970, "forfattarar_totalt": 8921, "referansar": 109116,
    "siterande_verk": 3554, "referansar_kjent_mal_rader": 31123, "referansar_til_korpus": 6611,
    "referansar_til_kanon": 24512, "sjolvsiteringar": 27, "pdf_verifisert": 3262, "pdf_ikkje_stadfest": 1387,
    "pdf_doi": 1439, "pdf_ingen": 344, "kanalar": 841, "samandrag": 4204,
}


def bygg_verk(K: Ns, T: Ns, tema: Ns, x, y) -> dict:
    tema_ut = []
    for j, t in enumerate(tema.tema_lst):
        tema_ut.append({"k": t["k"], "preset": t["preset"], "namn": t["namn"], "ord": t["ord"], "n": t["n"], "lx": t["lx"], "ly": t["ly"],
                        "sentroide": t["sentroide"]})
    under_ut = [{"tema": u["tema"], "namn": u["namn"], "n": u["n"], "lx": u["lx"], "ly": u["ly"]} for u in tema.under_lst]
    tittel = [str(r["title"]) for r in K.pub] + [str(r["title"]) for r in K.arkiv]
    return {
        "format": "utforsk-verk-1", "generert": GENERERT, "n": K.n, "n_openalex": K.n_oa, "n_arkiv": K.n_arkiv,
        "land": [{"k": k, "namn": nm} for k, nm in LAND_NORDISK],
        "land_alle": K.land_alle,
        "typar": [{"k": k, "namn": nm} for k, nm in TYPAR],
        "kanalgrupper": [{"k": k, "namn": nm} for k, nm in KANALGRUPPER],
        "kanalar": K.kanalar,
        "tema": tema_ut, "undertema": under_ut,
        "forfattarar": K.forfattarar, "institusjonar": K.institusjonar,
        "kol": {
            "id": K.ids, "tittel": tittel, "ar": K.ar, "lag": K.lag, "type": K.typ_per_verk, "kanal": K.kanal_per_verk,
            "land": K.land_per_verk, "fland": K.fland_kol, "forf": K.forf_kol, "inst": K.inst_kol, "sit": K.sit,
            "pdf": K.lenker["status"], "tema": liste(tema.tema), "undertema": liste(tema.under),
            "x": liste(x), "y": liste(y), "merk": K.merk,
        },
    }


def bygg_lenker_fil(K: Ns) -> dict:
    return {"format": "utforsk-lenker-1", "generert": GENERERT, "pdf": K.lenker["pdf"], "doi": K.lenker["doi"],
            "kjelde": K.lenker["kjelde"]}


def bygg_naboar(idx: np.ndarray, sim: np.ndarray) -> bytes:
    a = np.ascontiguousarray(idx[:, :10].astype("<u2")).tobytes()
    b = np.clip(np.rint(sim[:, :10].astype(np.float64) * 255.0), 0, 255).astype(np.uint8).tobytes()
    return a + b


def bygg_siteringar_fil(K: Ns, S: Ns, kart: dict, topp: list[int], info: dict) -> dict:
    sum_utan = sum(v for v in S.ref_utan if v > 0)
    return {
        "format": "utforsk-siteringar-1", "generert": GENERERT,
        "kjelder": S.kj,
        "ref_off": S.ref_off, "ref_til": S.ref_til, "ref_alle": S.ref_alle, "ref_utan": S.ref_utan,
        "n_sitert": S.n_sitert,
        "kart": kart,
        "land_topp": topp,
        "tal": {"referansar": S.rader, "siterande_verk": S.siterande, "kjent_mal": len(S.ref_til),
                "kjent_mal_rader": S.til_korpus + S.til_kanon, "til_korpus_rader": S.til_korpus,
                "til_korpus_utan_sjolv": S.til_korpus - S.sjolv, "til_kanon_rader": S.til_kanon,
                "sjolvsiteringar": S.sjolv, "utan_metadata_rader": sum_utan, "kjelder": S.m,
                "kjelder_i_kanon_utan_sitering": S.antal_canon_ikkje_korpus - S.m, **info},
    }


def bygg_tid_fil(T: Ns) -> dict:
    return {
        "format": "utforsk-tid-1", "generert": GENERERT,
        "termar": {"k": T.k, "vis": T.vis, "df": T.df},
        "off": T.off,
        "standard": T.standard,
        "tal": {"termar": len(T.k), "postingar": int(T.post.size), "min_df": min(T.df) if T.df else 0,
                "maks_df": max(T.df) if T.df else 0, "kjelde": "titlar"},
    }


def teikn_fffd(K: Ns) -> dict:
    t = sum(1 for r in K.pub + K.arkiv if "�" in str(r.get("title") or ""))
    a = sum(1 for lst in K.forf_per_verk if any("�" in nm for _, nm in lst))
    i = sum(1 for d in K.institusjonar if "�" in d["namn"])
    return {"titlar": t, "verk_med_forfattarnamn": a, "institusjonsnamn": i}


def vel_generert(ut: Path, filer: dict[str, bytes], tal: dict) -> str:
    """The old timestamp when every file would come out byte for byte the same, else now."""
    gml = read_json(ut / "manifest.json")
    if not gml or not gml.get("generert") or gml.get("tal") != tal:
        return now_iso()
    g = gml["generert"].encode("utf-8")
    for namn, data in filer.items():
        sti = ut / namn
        if not sti.exists() or sti.read_bytes() != data.replace(PLASSHALDAR.encode("utf-8"), g):
            return now_iso()
    return gml["generert"]


def skriv_alle(ut: Path, filer: dict[str, bytes], tal: dict) -> dict:
    global GENERERT
    if GENERERT == PLASSHALDAR:
        GENERERT = vel_generert(ut, filer, tal)
    g = GENERERT.encode("utf-8")
    filer = {k: v.replace(PLASSHALDAR.encode("utf-8"), g) for k, v in filer.items()}
    manifest_filer = {}
    for namn, data in filer.items():
        skriv_bytes(ut / namn, data)
        manifest_filer[namn] = {"bytes": len(data), "sha256": sha256_bytes(data), "gzip": len(gzip.compress(data, 6, mtime=0))}
    manifest = {"format": "utforsk-manifest-1", "generert": GENERERT, "filer": manifest_filer, "tal": tal}
    mdata = json_bytes(manifest)
    skriv_bytes(ut / "manifest.json", mdata)
    manifest_filer["manifest.json"] = {"bytes": len(mdata), "sha256": sha256_bytes(mdata), "gzip": len(gzip.compress(mdata, 6, mtime=0))}
    return manifest_filer


def skriv_tema_sjekk(sti: Path, K: Ns, tema: Ns, V: np.ndarray) -> None:
    tit = [str(r["title"]) for r in K.pub + K.arkiv]
    ut = ["# Tema-sjekk (generert av visdata.py)", "", f"Generert {GENERERT}. Namna er automatiske; sett `TEMA_NAMN_OVERSTYRING` i visdata.py der eit namn er openbert feil.", ""]
    for j, t in enumerate(tema.tema_lst):
        med = np.flatnonzero(tema.tema == j)
        nærast = med[np.argsort(-(V[med] @ tema.senter[j]), kind="stable")[:8]]
        ut.append(f"## {j}: {t['namn']} (`{t['k']}`, preset `{t['preset']}`), {t['n']} verk, cosinus til preset {t['_cos']:.3f}")
        if t["namn"] != t["_auto"]:
            ut.append(f"Automatisk namn frå preset: {t['_auto']}; overstyrt etter gjennomgang.")
        ut.append(f"Ord: {', '.join(t['ord'])}")
        ut.append("")
        for i in nærast:
            ut.append(f"- {tit[i]} ({K.ar[i]})")
        ut.append("")
        ut.append("Undertema:")
        for q, u in enumerate(tema.under_lst):
            if u["tema"] == j:
                ut.append(f"- {u['namn']} ({u['n']})")
        ut.append("")
    skriv_bytes(sti, ("\n".join(ut) + "\n").encode("utf-8"))


def skriv_data_rapport(sti: Path, tal: dict, filer: dict, avvik: list[str], notat: list[str]) -> None:
    ut = ["# Data-rapport for Utforsk (generert av visdata.py)", "", f"Generert {GENERERT}.", "", "## Køyretid per steg", ""]
    for namn, s in _steg_tider:
        ut.append(f"- {namn}: {s:.1f} s")
    ut += ["", "## Tal i manifest", ""]
    for k, v in tal.items():
        ut.append(f"- {k}: {v}")
    ut += ["", "## Filstorleik", "", "| fil | byte | gzip |", "|---|---|---|"]
    for k, v in filer.items():
        ut.append(f"| {k} | {v['bytes']} | {v['gzip']} |")
    ut += ["", "## Avvik frå det spesifikasjonen venta", ""]
    ut += [f"- {a}" for a in avvik] or ["- ingen"]
    ut += ["", "## Merknader", ""]
    ut += [f"- {a}" for a in notat]
    skriv_bytes(sti, ("\n".join(ut) + "\n").encode("utf-8"))


def lag_tal(K: Ns, S: Ns, T: Ns, nett_i: dict, nett_f: dict, stader: dict, db: sqlite3.Connection) -> dict:
    # Talet er det katalogen publiserer (metadata-samandrag pluss uttrekk frå opne PDF-ar), ikkje berre metadata i sqlite.
    meta = read_json(DOCS_DATA_DIR / "search" / "meta.json", None)
    if meta and meta.get("counts", {}).get("abs"):
        samandrag = int(meta["counts"]["abs"].get("o", 0)) + int(meta["counts"]["abs"].get("x", 0))
    else:
        samandrag = db.execute("select count(*) from works where in_scope = 1 and abstract is not null and length(abstract) >= 50").fetchone()[0]
    pt = K.lenker["teljar"]
    return {
        "verk": K.n, "openalex": K.n_oa, "arkiv": K.n_arkiv,
        "land_kjent": sum(1 for r in K.land_per_verk if r), "forfattarland_kjent": sum(1 for r in K.fland_kol if r),
        "institusjonar": len(K.institusjonar), "nett_inst_noder": nett_i["tal"]["vist"], "nett_inst_kantar": nett_i["tal"]["kantar"],
        "forfattarar_openalex": nett_f["tal"]["alle"], "nett_forf_noder": nett_f["tal"]["vist"],
        "nett_forf_kantar": nett_f["tal"]["kantar"], "forfattarar_totalt": len(K.forfattarar),
        "kanalar": len(K.kanalar), "land_alle": len(K.land_alle),
        "stader": stader["tal"]["stader"], "institusjonar_med_stad": stader["tal"]["med_stad"],
        "referansar": S.rader, "siterande_verk": S.siterande, "referansar_kjent_mal_rader": S.til_korpus + S.til_kanon,
        "referansar_til_korpus": S.til_korpus, "referansar_til_kanon": S.til_kanon, "sjolvsiteringar": S.sjolv,
        "referansar_bruksklare": len(S.ref_til), "kjelder": S.m,
        "pdf_verifisert": pt[0], "pdf_ikkje_stadfest": pt[1], "pdf_doi": pt[2], "pdf_ingen": pt[3],
        "samandrag": samandrag, "termar": len(T.k), "postingar": int(T.post.size),
    }


def sett_lavare_prioritet() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    global GENERERT
    ap = argparse.ArgumentParser(prog="python -m designteori.visdata", description="Bygg docs/data/vis/ for Utforsk")
    ap.add_argument("--hent-stader", action="store_true", help="hent institusjonskoordinatar frå OpenAlex (maks 40 kall)")
    ap.add_argument("--gjenbruk-layout", action="store_true", help="bruk x, y frå eksisterande filer når inndata er like")
    ap.add_argument("--rapport", nargs="?", const="", default=None, metavar="MAPPE",
                    help="skriv tema-sjekk.md og data-rapport.md til MAPPE (standard: notatmappa)")
    ap.add_argument("--vektorar", default=str(DOCS_DATA_DIR / "semantic_vectors.bin"), help="int8-fil (verk x dim) eller .npy")
    ap.add_argument("--indeks", default=str(DOCS_DATA_DIR / "semantic_index.json"), help="semantic_index.json (ids, presets, dimensions)")
    ap.add_argument("--iterasjonar", type=int, default=750, help="t-SNE-iterasjonar (250 utvida + resten)")
    ap.add_argument("--ut", default=str(VIS_DIR), help="utmappe")
    ap.add_argument("--generert", default=None, help="fast tidsstempel (ISO) for eit reproduserbart bygg")
    ap.add_argument("--notatmappe", default=str(NOTATMAPPE) if NOTATMAPPE else None, help="mappe for buffer og rapportar (eller UTFORSK_NOTATMAPPE)")
    ap.add_argument("--perplexity", type=float, default=30.0)
    ap.add_argument("--lr", type=float, default=None)
    args = ap.parse_args(argv)
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    sett_lavare_prioritet()
    GENERERT = args.generert or PLASSHALDAR
    ut = Path(args.ut)
    notat = Path(args.notatmappe) if args.notatmappe else None
    avvik: list[str] = []
    merknader: list[str] = []
    if notat and notat.exists():
        les_spring_buffer(notat / "spring_buffer.npz")
    if not RAW_SQLITE.exists():
        raise SystemExit(f"{RAW_SQLITE} finst ikkje; byggjaren treng databasen")
    db = opne_db()
    gml_verk = read_json(ut / "verk.json")

    with Steg("les verk og forfattarar"):
        K = les_korpus(db, Path(args.indeks))
        kanon_land: set[str] = set()
        for (c,) in db.execute("select countries from cited_canon"):
            try:
                kanon_land |= {x for x in json.loads(c or "[]") if x}
            except ValueError:
                pass
        bygg_ordbokar(K, kanon_land)
        K.lenker = bygg_lenker(K)
        K.dublettar = merk_dublettar(K)
        logg(f"same verk under to id-ar (merk & 4): {K.dublettar}")
        logg(f"verk {K.n}, forfattarar {len(K.forfattarar)}, institusjonar {len(K.institusjonar)}, kanalar {len(K.kanalar)}, land_alle {len(K.land_alle)}")
        logg(f"PDF-status: {dict(sorted(K.lenker['teljar'].items()))}")
        if K.forfordning_avvik:
            avvik.append(f"forfattarrekkjefølgje avvik frå publications.json for {K.forfordning_avvik} verk")
        if K.ukjende_typar:
            avvik.append(f"ukjende kind-verdiar (til «ukjend»): {dict(K.ukjende_typar)}")
        if K.ukjent_nordisk:
            avvik.append(f"verk med land utanfor dei fem nordiske (ignorert): {dict(K.ukjent_nordisk)}")

    with Steg("termar frå titlar"):
        titler = [str(r["title"]) for r in K.pub + K.arkiv]
        T = bygg_termar(titler)
        logg(f"termar: {len(T.k)} i ordlista, {int(T.post.size)} postingar, kandidatar {T.alle_kandidatar}; standard {T.standard}")

    with Steg("vektorar, naboar og tema"):
        dim = int(K.indeks.get("dimensions") or 128)
        V = les_vektorar(Path(args.vektorar), dim, K.n)
        knn_idx, knn_sim = knn_cosinus(V, 90)
        naboar = bygg_naboar(knn_idx, knn_sim)
        tema = bygg_tema(V, K.indeks, T)
        logg("tema: " + ", ".join(f"{t['namn']} {t['n']}" for t in tema.tema_lst))

    with Steg("kartutforming (t-SNE)"):
        gjenbrukt = False
        if args.gjenbruk_layout and gml_verk and gml_verk["kol"]["id"] == K.ids:
            x, y = gml_verk["kol"]["x"], gml_verk["kol"]["y"]
            gjenbrukt = True
            logg("bruker x, y frå eksisterande verk.json")
        else:
            kp = (notat / "tsne_kontrollpunkt.npz") if notat and notat.exists() else None
            Y = tsne(V, knn_idx, knn_sim, args.iterasjonar, 42, kp, args.perplexity, args.lr)
            xa, ya = normaliser_kart(Y)
            x, y = xa.tolist(), ya.tolist()
        ankre(tema, np.asarray(x), np.asarray(y))
        if not gjenbrukt:
            merknader.append(f"t-SNE med {args.iterasjonar} iterasjonar (perplexity {args.perplexity}, kNN 90, seed 42)")

    with Steg("samforfattarnett"):
        gm_i = read_json(ut / "nett_inst.json") if args.gjenbruk_layout else None
        gm_f = read_json(ut / "nett_forf.json") if args.gjenbruk_layout else None
        nett_i = bygg_nett(K, "inst", "institusjonar", gm_i)
        nett_f = bygg_nett(K, "forf", "forfattarar", gm_f)
        logg(f"nett inst {nett_i['tal']}, forf {nett_f['tal']}")

    with Steg("siteringar"):
        S = bygg_siteringar(db, K)
        gm_s = (read_json(ut / "siteringar.json") or {}).get("kart") if args.gjenbruk_layout else None
        kart = bygg_kart_sit(K, S, gm_s)
        topp, info = land_topp(K, S)
        logg(f"land_topp: {[K.land_alle[c]['k'] for c in topp]}; {info}")
        logg(f"kart: {len(kart['kantar'])} kantar, {len(kart['grupper'])} grupper")
        merknader.append(
            f"KJELDE_RETTING: {len(KJELDE_RETTING)} klassikarar der OpenAlex har meldar, redaktør eller ingen forfattar "
            "(til dømes Schön 1983, som var delt på «Stewart 1984», «Checkoway 1985», «Bogumil 1985» og «Reflective Practitioner 2014») "
            "er slått saman til éin node kvar og namngjevne for hand. Lista er i visdata.py; «Artificial Intelligence 2021» og "
            "«Harvard business 1988» er feilkopla referansar i kjelda og står att urørte. Gamle kanon=-lenker til ein variant "
            "som ikkje lenger er representant, finn ikkje noden.")

    with Steg("stader"):
        kj_sti = ut / "kjelde_stader.json"
        raa_sti = (notat / "openalex_institusjonar_raa.json") if notat else None
        if args.hent_stader:
            if not notat or not notat.exists():
                raise SystemExit("notatmappa finst ikkje; gi --notatmappe (treng ho til bufferfila)")
            raa = hent_stader([d["k"] for d in K.institusjonar], raa_sti)
            skriv_kjelde_stader(raa, K, kj_sti)
        kj = read_json(kj_sti)
        if kj is None:
            avvik.append("kjelde_stader.json manglar; stader er omtrentlege landsentrum")
        stader = bygg_stader(K, kj)
        logg(f"stader {stader['tal']}")
        if stader["tal"]["med_stad"] < 0.95 * len(K.institusjonar):
            avvik.append(f"berre {stader['tal']['med_stad']} av {len(K.institusjonar)} institusjonar har stad (under 95 %)")

    with Steg("skriv filer"):
        verk = bygg_verk(K, T, tema, x, y)
        filer = {
            "verk.json": json_bytes(verk),
            "lenker.json": json_bytes(bygg_lenker_fil(K)),
            "naboar.bin": naboar,
            "nett_inst.json": json_bytes(nett_i),
            "nett_forf.json": json_bytes(nett_f),
            "stader.json": json_bytes(stader),
            "siteringar.json": json_bytes(bygg_siteringar_fil(K, S, kart, topp, info)),
            "tid.json": json_bytes(bygg_tid_fil(T)),
            "termar.bin": np.ascontiguousarray(T.post.astype("<u2")).tobytes(),
        }
        tal = lag_tal(K, S, T, nett_i, nett_f, stader, db)
        manifest_filer = skriv_alle(ut, filer, tal)
        for namn, grense in UPPER_GRENSER.items():
            if manifest_filer[namn]["bytes"] > grense:
                avvik.append(f"{namn} er {manifest_filer[namn]['bytes']} byte, over grensa {grense}")
        if manifest_filer["verk.json"]["gzip"] > 650_000:
            avvik.append(f"verk.json gzip {manifest_filer['verk.json']['gzip']} over 650 KB")
        for k, v in FORVENTA.items():
            if tal.get(k) != v:
                avvik.append(f"{k}: fekk {tal.get(k)}, venta {v}")
        for k, v in tal.items():
            logg(f"tal {k} = {v}")
        for k, v in manifest_filer.items():
            logg(f"fil {k}: {v['bytes']} byte, gzip {v['gzip']}")

    if args.rapport is not None:
        mappe = Path(args.rapport) if args.rapport else notat
        if mappe is None:
            raise SystemExit("--rapport utan mappe treng --notatmappe")
        mappe.mkdir(parents=True, exist_ok=True)
        merknader += [
            "Forfattarnamn: arkivverk skriv «Etternamn, Fornamn», OpenAlex «Fornamn Etternamn», så same person kan vere to nøklar.",
            "Nøklane i kanon og ego (`kjelder.k`) er den representative sitert-id-en; ein ombygging kan endre han, så gamle `kanon=`-lenker kan slutte å virke.",
            f"U+FFFD (øydelagt teikn som alt finst i kjeldebasen): {teikn_fffd(K)}; strengane er behaldne.",
            f"OpenAlex-verk utan forfattarland: {sum(1 for i in range(K.n_oa) if not K.fland_kol[i])} (utan authorships-rader: {K.utan_forfattarar}); forfattarplassar utan id (fekk n:-nøkkel): {K.tomme_id_plassar}.",
            f"Nettverk: overlapp att etter fjerning av overlapp (ved 900 px brei visning, k = 1): {OVERLAPP_REST}. Forfattarnettet er for tett til å bli fritt for overlapp ved den storleiken; sida kan skalere nodane ned.",
            "Tillegg til kontrakten: `siteringar.ref_utan[i]` (referansar utan metadata, -1 for arkiv), `siteringar.kart.merkelapp` (unike merkelappar parallelt med `kart.noder`, også for korpusverk), `siteringar.land_topp`, `siteringar.tal.mal_utan_kanal_del`/`mal_utan_land_del`, `manifest.filer.*.gzip`, `tid.tal.min_df`/`maks_df`, `stader.kjelde`.",
            "`kanalar` har 846 oppføringar: dei 847 i spesifikasjonen tel «Ukjent» som namn, men dei fem verka med det namnet har kanal -1.",
            "Temaord (`tema.ord`, undertemanamn): c-TF-IDF er vekta med lift (andelen klassen har av ordet delt på andelen av alle ord), elles fekk alle tema generiske ord som «research» og «study». Namna på åtte av ti tema er overstyrte etter gjennomgang (TEMA_NAMN_OVERSTYRING); nøklane er framleis næraste preset.",
            "Maskina var delt: BLAS-tråder (OPENBLAS_NUM_THREADS=4) vart 10 til 20 gonger tregare enn éin tråd under last frå andre prosessar. Køyr med OPENBLAS_NUM_THREADS=1 om maskina er travel (t-SNE tek då om lag 5 minutt).",
            f"Mogleg dublett (merk & 1): {sum(1 for v in K.merk if v & 1)}; ikkje gjennomgått (merk & 2): {sum(1 for v in K.merk if v & 2)}; same verk som eit anna i korpuset (merk & 4, delt PDF-adresse, delt DOI eller same tittel med år innan 2 og felles etternamn): {sum(1 for v in K.merk if v & 4)}; ein av dei to: {sum(1 for v in K.merk if v & 5)}.",
            f"Kanon-element som ikkje er verk i korpuset: {S.antal_canon_ikkje_korpus}, av dei sitert og slått saman til {S.m} noder ({S.grupper_med_fleire} grupper med fleire variantar).",
            f"t-SNE-vektorar frå {args.vektorar}.",
            "Forfattarnettet har 1 823 noder og 4 959 kantar mot venta 1 824 og 4 970: verket W2994871791 har to ulike forfattar-id-ar med same namn, og regelen om éin oppføring per namn og verk (endring 51) gir den eine ho mistar verket. n i nettet er rekna frå verk.json, slik at sidas tal stemmer med lista.",
            f"Stader utanfor landets ramme (feil koordinatar frå OpenAlex, ikkje plasserte): {stader['tal'].get('utanfor_land', 0)}.",
        ]
        skriv_tema_sjekk(mappe / "tema-sjekk.md", K, tema, V)
        skriv_data_rapport(mappe / "data-rapport.md", tal, manifest_filer, avvik, merknader)
        logg(f"rapportar skrivne til {mappe}")
    for a in avvik:
        logg(f"AVVIK: {a}")
    logg("ferdig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
