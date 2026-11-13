"""Klynger: cluster analysis and map data for the "kart" tab (docs/data/klynger/).

Run as ``python -u -m designteori.klynger`` from the repository root. One run rebuilds everything with fixed
seeds: the comparison of vector sources, the cluster candidates, the chosen two-level clustering, the names, the
2D layout and the two published files kart.json and om.json. The evaluation numbers and the material the names
rest on are written to the notes folder (NOTAT) for a verifier; the reasoning behind the choices is in
NOTAT/evaluering.md.

Only the standard library and numpy are imported at module level, so that ``compileall`` and the test suite work
in CI. scipy and networkx are imported inside the functions that need them. The builder never runs in CI: it reads
data/nordic_design_research.sqlite (references, read-only) and, if present, the private full-text cache (only
chunk vectors are read from it, never text). Nothing that leaves this module carries abstract or full text.
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

from . import DOCS_DATA_DIR, PRIVATE_CORPUS_DB, RAW_SQLITE, now_iso, read_json

UT = DOCS_DATA_DIR / "klynger"
SOK = DOCS_DATA_DIR / "search"
NOTAT = Path("C:/Users/Iver/Documents/github/FORML-RE/.claude/arbeidsflyt-20261112/steg10-kart")
STEG6_DOKVEKTORAR = Path("C:/Users/Iver/Documents/github/FORML-RE/.claude/arbeidsflyt-20261112/steg6-metaanalyse/tema/cache_docs.npz")
VERSJON = 1
N_FORVENTA = 6432
SKALA = 10000  # coordinates are integers 0..SKALA
K_NN = 15
SEEDS = list(range(10))

# ---------------------------------------------------------------------------
# Choices. Each is argued in NOTAT/evaluering.md from the numbers this module writes to NOTAT/evaluering-tal.json.
# ---------------------------------------------------------------------------
KJELDE = "a_justert"           # title + abstract vectors (vectors.i8), title-only group aligned (juster_tittel_berre)
TITTEL_KRYMP = 0.01             # shrinkage of the covariances in the alignment
TOPP_METODE = ("kmeans", 8)    # spherical k-means, k (the most stable k in 8..16 in both builds, see evaluering.md)
UNDER_OPPLOYSING = 0.5          # Louvain resolution inside each top cluster (fuzzy kNN graph restricted to it)
UNDER_K = [2, 3, 4, 5, 6]       # spherical k-means inside each top cluster (evaluated alternative)
UNDER_MIN_STAB = 0.6
MIN_TOPP = 25                   # smaller graph communities are merged into the neighbour they share most weight with
MIN_UNDER = 12
GRENSE_DEL = 0.5                # a work is on a border when fewer than this share of its 15 neighbours share its cluster
TITTEL_BEHANDLING = "med"       # "med": title-only works are clustered with the rest and flagged
UTFORMING = "tsne"              # "tsne", "umap" or "svd"
TSNE_ITER = 1000
TSNE_PERPLEXITY = 30.0
UMAP_EPOKAR = 500

KANDIDAT_OPPLOYSING = [0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
KANDIDAT_K = [6, 8, 10, 12, 14, 16, 20]
UNDER_KANDIDATAR = [0.4, 0.5, 0.6, 0.8, 1.0]

PERIODAR = [("før 2000", -10_000, 1999), ("2000–04", 2000, 2004), ("2005–09", 2005, 2009), ("2010–14", 2010, 2014),
            ("2015–19", 2015, 2019), ("2020–24", 2020, 2024), ("2025–26", 2025, 10_000)]

# Reviewed names. Key: the most central work of the cluster in the build the name was checked against. If the key is
# not among the cluster's five most central works in a new build, the automatic name is used and flagged.
# Checked 2026-11-13 against the terms and the eight most central titles in NOTAT/namnegrunnlag.md, then revised the
# same day after a verifier read ten random titles per cluster (NOTAT/kontroll/k3_namn_utval.txt): names that fitted
# only the centre of a cluster were widened or replaced (see NOTAT/evaluering.md, section 7). The names are set by
# the analysis, not reviewed by a subject expert.
NAMN_TOPP: dict[str, str] = {
    "W2094495192": "Designmetodikk, produktutvikling og designteam",
    "W2980032970": "Interaksjonsdesign og HCI",
    "nordic:nva:df2fc6603fa902e39783": "Designutdanning og undervising",
    "W7112102007": "Deltakande design og co-design",
    "nordic:nordes:cc99826647bd8ca7c983": "Handverk, kunst, materiale og kritisk praksis",
    "nordic:nva:c23b90c9058cd61a87c5": "Berekraft, klima og framtider",
    "nordic:nva:81591de1f19a19f49d3a": "Norske fagmiljø: handverk, didaktikk, tenestedesign",
    "nordic:nva:ee4378a8e4b4b13233a6": "Tenestedesign og innovasjon",
}
NAMN_UNDER: dict[str, str] = {
    "W4313503718": "Ingeniørdesign og designleiing",
    "W2238158355": "Kreativitet og idéutvikling",
    "W1974929188": "Designtenking i organisasjonar",
    "nordic:nva:c5f4e46d9596209fcce2": "Designteori og forskingsmetode",
    "W1964838658": "Designkognisjon og resonnering",
    "W4297968558": "Teori og praksis i interaksjonsdesign",
    "W4400142411": "Robotar, KI og kropp",
    "W4400610587": "Empati og brukarforståing",
    "W4205696976": "Lyd og køyretøy",
    "W4412045118": "Meir-enn-menneskeleg HCI",
    "nordic:nva:f7995b89f9efc9dacb88": "Brukarsentrert design og brukarmedverknad",
    "W2502266073": "Interaksjonsdesign for arbeidsliv",
    "nordic:nva:df2fc6603fa902e39783": "Designutdanning og designkompetanse",
    "W2736471571": "Co-design i skulen",
    "nordic:nva:07c32384ed0c5222af10": "Berekraft i designutdanninga",
    "nordic:nva:2d2da03f1ad446cb87e7": "Born, matematikk og inkluderande undervising",
    "W4364862113": "Designtenking i undervising",
    "W7152443517": "Generativ KI i undervising",
    "nordic:nva:179ba6aba03a2ee685e4": "Spekulativ design og framtider i undervisinga",
    "W7112102007": "Metodar for deltakande design",
    "nordic:nva:e1e1e681b01bc5fc24dc": "Co-design, samarbeid og lab",
    "W3036567598": "Deltakande design, rettferd og marginaliserte grupper",
    "nordic:nva:706a1db5fc0f4b4539d3": "Deltakande design i helse",
    "W1988944132": "Born, unge og spel i co-design",
    "W4383616658": "Fasilitering av deltaking",
    "nordic:nva:944e7ae1d97910962e0b": "Konferansebind frå PDC",
    "nordic:nva:6e8ec734e3b10fb41e8e": "Deltakande design med eldre",
    "W3047220765": "Estetikk og designfilosofi",
    "nordic:nordes:cc99826647bd8ca7c983": "Tekstil og mote",
    "W4412035372": "Spekulativ og kunstnarleg designpraksis",
    "W7225150284": "Handverk og praksisbasert forsking",
    "W2793604173": "Kjønn, kropp og feminisme",
    "nordic:nordes:a327efe57da110b2aa1c": "Designantropologi og teknologi",
    "nordic:nva:8f14b3629b17154557ce": "Konferansebind (Nordes, DRS, IASDR)",
    "nordic:nva:5a9b0b6c69621c2068a4": "Systemendring og framtider",
    "W7160449131": "Byar og planlegging",
    "nordic:nva:91d728fe435b9a022586": "Berekraftig design, innovasjon og næring",
    "nordic:nva:7682a711cc1200383840": "Sirkulær mote og tekstil",
    "nordic:nva:c764dfbbab418dddba62": "Systemisk design, transport og kvardagspraksis",
    "nordic:nordes:109a5de8fba50509e59c": "Designaktivisme og politikk",
    "nordic:nva:898048d5b131af21835a": "Kunst og handverk i skulen",
    "nordic:nva:e55ef98f18d463e279f9": "Nordiskspråkleg designteori og tenestedesign",
    "W2966096216": "Leiarartiklar, arkitektur og blanda tidsskriftstoff",
    "nordic:nva:af941e1d1301e3e994f7": "Norske prosjekt: interaksjonsdesign, tenester og helse",
    "W1800324983": "Innleiingar til konferansar",
    "W1872603985": "Profesjon, politikk, institusjonar (svensk, finsk)",
    "nordic:nva:ee4378a8e4b4b13233a6": "Tenestedesign som praksis",
    "nordic:nva:0ec6610bbad18df61af9": "Tenestedesign i helse",
    "nordic:nva:63696e4fd6b474e93c95": "Offentlege tenester",
    "W252519751": "Prototypar av tenester",
    "nordic:nva:2e418bcebf88e47e9a99": "Kultur og makt i tenester",
    "nordic:nva:b7851ea25f2d229103a0": "Undervising i tenestedesign",
}

# Colour slot (0..7 in the page's categorical palette, docs/kart.js PAL) per top cluster, keyed like NAMN_TOPP. The
# slots were chosen so the clusters that border each other most in the map get the colours that differ most. A
# cluster whose key is missing gets the first free slot; more than len(PALETT_PLASSAR) clusters stops the build,
# because the page has no more distinct colours.
PALETT_PLASSAR = 8
FARGE_TOPP: dict[str, int] = {
    "W2094495192": 5,
    "W2980032970": 7,
    "nordic:nva:df2fc6603fa902e39783": 4,
    "W7112102007": 0,
    "nordic:nordes:cc99826647bd8ca7c983": 6,
    "nordic:nva:c23b90c9058cd61a87c5": 3,
    "nordic:nva:81591de1f19a19f49d3a": 1,
    "nordic:nva:ee4378a8e4b4b13233a6": 2,
}
NORDISKE_SPRAK = "bndsf"  # meta.json lang codes: bokmål, nynorsk, dansk, svensk, finsk

# Stop words: English, Norwegian (both forms), Swedish, Danish, and academic boilerplate.
STOPPORD = frozenset("""
a an the and or nor but of in on at to for with without by from as is are was were be been being am it its this that
these those not no into onto about above across after against along among around before behind below beneath beside
besides between beyond during except inside near off out outside over past since through throughout till toward towards
under until up upon via vs versus within than then there their them they we us our you your he she his her him i me my
mine how what why when where who whom whose which whether can could may might must shall should will would do does did
done have has had having also both each either few more most other some such only own same so too very just et al etc
per one two three first second new well many much often thus therefore however yet while here way ways
paper papers article articles study studies research researchers researcher results result findings finding based using
used use uses approach approaches present presents presented discuss discusses discussed discussion argue argues aim aims
aimed author authors chapter chapters work works focus focuses focused show shows shown provide provides provided
explore explores explored investigate investigates examine examines describe describes described conclude concludes
conclusion conclusions contribute contributes contribution contributions propose proposes proposed suggest suggests
including include includes particular particularly various different important key main several within through toward
abstract th st nd rd issn isbn doi org www http https download pdf copyright vol pp
og i på av for med til en et ei ein eit er som det den de dei å om fra frå ved ikke ikkje har kan seg sin sitt sine si
så eller mot under over etter mellom hos hjå gjennom han hun vi me du jeg eg meg deg oss dette denne disse desse hva kva
hvordan korleis hvorfor kvifor når kor hvor var vart blir blei bli blitt vore være vere ble vil vill skal skulle kunne
kunna må måtte bare berre også òg mer meir mest mykje mye ho henne hans hennar deira deres artikkelen artikkel studien
studie denne dette knyttet knytt basert gjennomført der både andre ulike viser enn slik blant samt nye hver noen nokre
mange flere fleire innen innan samme kunne bidrar bidreg gir gjer gjør tar får finnes finst dermed derfor difor altså
dei deira hvilke hvilken kva hvis viktig viktige
och att är ett vid inte sig mellan genom från vad hur varför när varit blev blir bli kan ska skulle kunde måste endast
också mer mest han hon vi ni jag du detta denna dessa den det de dem sin sitt sina
af at mod gennem fra efter mellem hos sig ikke har kan skal skulle kunne måtte kun også mere mest hvad hvordan hvorfor
hvor han hun vi du jeg dette denne disse
""".split())

# Personal name fragments are never published as cluster terms (they come from greetings and tributes to named
# colleagues). The build logs every published term that matches a frequent author given name (fornamn_sjekk), so
# new cases can be added here; on 2026-11-13 only these two were found (sub-cluster of greetings in FormAkademisk).
PERSONNAMN = frozenset({"liv", "merete"})

ORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")

_t0 = time.time()


def logg(msg: str) -> None:
    print(f"[{time.time() - _t0:7.1f}s] {msg}", flush=True)


class Ns(dict):
    __getattr__ = dict.__getitem__

    def __setattr__(self, k, v):
        self[k] = v


def sett_lavare_prioritet() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
    except Exception:  # noqa: BLE001
        pass


def fold(s: object) -> str:
    t = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------


def les_korpus() -> Ns:
    meta = read_json(SOK / "meta.json")
    pub = read_json(DOCS_DATA_DIR / "publications.json")
    arkiv = read_json(DOCS_DATA_DIR / "nordic_additions.json")
    ids = list(meta["ids"])
    if ids != [p["id"] for p in pub] + [a["id"] for a in arkiv]:
        raise SystemExit("meta.json ids er ikkje publications + nordic_additions i rekkjefølgje")
    n = len(ids)
    if n != N_FORVENTA:
        logg(f"ADVARSEL: {n} verk, venta {N_FORVENTA}")
    rec = pub + arkiv
    kanal_vis = [str(p.get("source") or "").strip() for p in pub] + [str(a.get("venue") or "").strip() for a in arkiv]
    kanal = [fold(v) for v in kanal_vis]
    kanal = ["" if v in {"ukjent", "ukjend", "unknown"} else v for v in kanal]
    emne = [str(p.get("topic") or "") for p in pub] + [""] * len(arkiv)
    abstr = {}
    for f in sorted((SOK / "abstracts").glob("a*.json")):
        abstr.update(read_json(f))
    return Ns(
        ids=ids, n=n, n_oa=len(pub), id_til_i={w: i for i, w in enumerate(ids)},
        tittel=[str(r.get("title") or "") for r in rec],
        ar=np.asarray([int(r.get("year") or 0) for r in rec]),
        kanal=kanal, kanal_vis=kanal_vis, emne=emne,
        land=[list(r.get("countries") or []) for r in rec],
        sprak=str(meta["lang"]), abs=str(meta["abs"]),
        tittel_berre=np.asarray([c == "0" for c in meta["abs"]]),
        abstrakt=[str((abstr.get(w) or {}).get("t") or "") for w in ids],
        meta=meta,
    )


def normaliser(V: np.ndarray) -> np.ndarray:
    V = V.astype(np.float32)
    nrm = np.linalg.norm(V, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    return V / nrm


def sentrer(V: np.ndarray, maske: np.ndarray | None = None) -> np.ndarray:
    """Subtract the mean of the rows in maske (default all), then L2-normalise. Removes the direction every text shares."""
    m = V[maske].mean(0) if maske is not None else V.mean(0)
    return normaliser(V - m)


def _matrise_rot(C: np.ndarray, invers: bool) -> np.ndarray:
    w, U = np.linalg.eigh(C)
    w = np.maximum(w, 1e-9 * w.max())
    return (U * w ** (-0.5 if invers else 0.5)) @ U.T


def juster_tittel_berre(V: np.ndarray, tb: np.ndarray, krymp: float = TITTEL_KRYMP) -> np.ndarray:
    """Align the title-only vectors with the others.

    A title-only work is embedded from the prompt "title: none | text: <title>", which puts these vectors in their own
    region: in the raw space 99.6 % of a title-only work's 15 neighbours are title-only (base rate 34.6 %). Each group
    is centred on its own mean, and the title-only group is whitened and recoloured with the covariance of the works
    with an abstract (CORAL; covariances shrunk by krymp times the identity). Then every row is L2-normalised."""
    X = V.astype(np.float64)
    A = X[~tb] - X[~tb].mean(0)
    B = X[tb] - X[tb].mean(0)
    eye = np.eye(X.shape[1])
    Ca = np.cov(A.T) + krymp * eye
    Cb = np.cov(B.T) + krymp * eye
    ut = np.empty_like(X)
    ut[~tb] = A
    ut[tb] = B @ _matrise_rot(Cb, True) @ _matrise_rot(Ca, False)
    return normaliser(ut.astype(np.float32))


def vektorar_a(K: Ns) -> np.ndarray:
    v = K.meta["vectors"]
    raa = np.fromfile(SOK / v["file"], dtype=np.int8)
    if raa.size != K.n * int(v["dim"]):
        raise SystemExit(f"vectors.i8: {raa.size} byte, venta {K.n}x{v['dim']}")
    return normaliser(raa.reshape(K.n, int(v["dim"])).astype(np.float32) / float(v["scale"]))


def vektorar_b(K: Ns) -> np.ndarray:
    idx = read_json(DOCS_DATA_DIR / "semantic_index.json")
    if idx["ids"] != K.ids:
        raise SystemExit("semantic_index.json ids følgjer ikkje meta.json")
    d = int(idx.get("dimensions") or 128)
    raa = np.fromfile(DOCS_DATA_DIR / "semantic_vectors.bin", dtype=np.int8)
    return normaliser(raa.reshape(K.n, d).astype(np.float32) / 127.0)


def vektorar_c(K: Ns) -> tuple[np.ndarray, np.ndarray] | None:
    """Document vectors averaged from the private full-text chunk vectors (mean of chunk vectors per work).

    Only vectors are read. Cached in NOTAT (private notes, not published). Returns (mask, X) or None."""
    cache = NOTAT / "fulltekst_dokvektorar.npz"
    if not cache.exists():
        if STEG6_DOKVEKTORAR.exists():
            z = np.load(STEG6_DOKVEKTORAR)
            np.savez(cache, ids=z["ids"], X=z["X"], nchunks=z["nchunks"])
            logg(f"fulltekstvektorar: kopierte frå steg 6 ({len(z['ids'])} verk)")
        elif PRIVATE_CORPUS_DB.exists():
            logg("fulltekstvektorar: les chunk-vektorar frå den private databasen (berre vektorar)")
            db = sqlite3.connect(f"file:{PRIVATE_CORPUS_DB.as_posix()}?mode=ro", uri=True)
            w_av_sha = collections.defaultdict(list)
            for w, s in db.execute("select work_id, sha256 from work_documents"):
                if w in K.id_til_i:
                    w_av_sha[s].append(w)
            summar: dict[str, np.ndarray] = {}
            tal = collections.Counter()
            for sha, blob in db.execute("select c.sha256, e.vector from embeddings e join chunks c using(chunk_id) "
                                        "where e.dimensions=256 and e.model='embeddinggemma-300m'"):
                ws = w_av_sha.get(sha)
                if not ws:
                    continue
                v = np.frombuffer(blob, dtype="<f4").astype(np.float64)
                for w in ws:
                    if w in summar:
                        summar[w] += v
                    else:
                        summar[w] = v.copy()
                    tal[w] += 1
            ids = sorted(summar)
            X = np.stack([summar[w] / tal[w] for w in ids]).astype(np.float32)
            np.savez(cache, ids=np.asarray(ids), X=X, nchunks=np.asarray([tal[w] for w in ids]))
        else:
            return None
    z = np.load(cache)
    maske = np.zeros(K.n, dtype=bool)
    X = np.zeros((K.n, z["X"].shape[1]), dtype=np.float32)
    for w, v in zip(z["ids"], z["X"]):
        i = K.id_til_i.get(str(w))
        if i is not None:
            maske[i] = True
            X[i] = v
    X[maske] = normaliser(X[maske])
    return maske, X


# ---------------------------------------------------------------------------
# Bibliographic coupling (external check: two works are coupled when they share at least one reference)
# ---------------------------------------------------------------------------


def les_kopling(K: Ns) -> Ns:
    from scipy import sparse

    db = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
    rader, kol = [], []
    ref_i: dict[str, int] = {}
    for a, b in db.execute("select citing_id, cited_id from references_all"):
        i = K.id_til_i.get(a)
        if i is None:
            continue
        j = ref_i.setdefault(b, len(ref_i))
        rader.append(i)
        kol.append(j)
    A = sparse.csr_matrix((np.ones(len(rader), dtype=np.int32), (rader, kol)), shape=(K.n, len(ref_i)))
    A.data[:] = 1
    A.sum_duplicates()
    A.data[:] = 1
    har_ref = np.asarray(A.sum(1)).ravel() > 0
    C = (A @ A.T).tocoo()
    av = C.row != C.col
    nokklar = np.sort(C.row[av].astype(np.int64) * K.n + C.col[av].astype(np.int64))
    logg(f"kopling: {int(har_ref.sum())} verk med referanseliste, {len(ref_i)} ulike referansar, "
         f"{len(nokklar) // 2} kopla par")
    return Ns(har_ref=har_ref, nokklar=nokklar, n=K.n)


def er_kopla(KP: Ns, i: np.ndarray, j: np.ndarray) -> np.ndarray:
    q = i.astype(np.int64) * KP.n + j.astype(np.int64)
    p = np.searchsorted(KP.nokklar, q)
    p = np.minimum(p, len(KP.nokklar) - 1)
    return KP.nokklar[p] == q


def kopla_par_i(KP: Ns, maske: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Coupled pairs i < j with both ends in maske."""
    i = KP.nokklar // KP.n
    j = KP.nokklar % KP.n
    v = (i < j) & maske[i] & maske[j]
    return i[v], j[v]


# ---------------------------------------------------------------------------
# Neighbours and neighbour-based measures (independent of any clustering)
# ---------------------------------------------------------------------------


def knn(V: np.ndarray, k: int, pop: np.ndarray | None = None, blokk: int = 512) -> tuple[np.ndarray, np.ndarray]:
    """Cosine k nearest neighbours of every row in pop, searched only within pop. Indices are into V."""
    P = np.arange(V.shape[0]) if pop is None else np.flatnonzero(pop)
    W = V[P]
    m = len(P)
    idx = np.empty((m, k), dtype=np.int64)
    sim = np.empty((m, k), dtype=np.float32)
    for b in range(0, m, blokk):
        S = W[b: b + blokk] @ W.T
        r = np.arange(S.shape[0])
        S[r, b + r] = -2.0
        part = np.argpartition(-S, k - 1, axis=1)[:, :k]
        ps = np.take_along_axis(S, part, 1)
        ordn = np.lexsort((part, -ps), axis=1)
        idx[b: b + blokk] = np.take_along_axis(part, ordn, 1)
        sim[b: b + blokk] = np.take_along_axis(ps, ordn, 1)
    return P[idx], sim


def same_del(lab: list[str], idx: np.ndarray, rader: np.ndarray, pop: np.ndarray) -> dict:
    """Share of neighbours with the same non-empty label, and the random baseline within pop."""
    a = np.asarray(lab, dtype=object)
    har = np.asarray([bool(x) for x in lab])
    r = np.flatnonzero(har[rader])
    if not len(r):
        return {"del": None, "basis": None, "n": 0}
    rr = rader[r]
    del_ = float((a[idx[r]] == a[rr][:, None]).mean())
    tel = collections.Counter(a[pop & har])
    m = int(pop.sum())
    basis = float(np.mean([(tel[a[i]] - 1) / (m - 1) for i in rr]))
    return {"del": round(del_, 4), "basis": round(basis, 4), "n": int(len(r))}


def kopling_del(V: np.ndarray, pop: np.ndarray, KP: Ns, k: int = K_NN, rader_maske: np.ndarray | None = None) -> dict:
    p = pop & KP.har_ref
    idx, _ = knn(V, k, p)
    rader = np.flatnonzero(p)
    v = np.ones(len(rader), dtype=bool) if rader_maske is None else rader_maske[rader]
    kop = er_kopla(KP, np.repeat(rader[v], k), idx[v].ravel()).reshape(-1, k)
    m = int(p.sum())
    pi, _ = kopla_par_i(KP, p)
    basis = 2 * len(pi) / (m * (m - 1))
    return {"del": round(float(kop.mean()), 4), "basis": round(basis, 4), "loft": round(float(kop.mean()) / basis, 2),
            "n": int(v.sum())}


def evaluer_kjelde(namn: str, V: np.ndarray, pop: np.ndarray, K: Ns, KP: Ns) -> dict:
    idx, sim = knn(V, K_NN, pop)
    rader = np.flatnonzero(pop)
    tb = K.tittel_berre
    ut = {"kjelde": namn, "n": int(pop.sum()), "k": K_NN,
          "kopling": kopling_del(V, pop, KP),
          "kopling_tittel_berre": kopling_del(V, pop, KP, rader_maske=tb),
          "kopling_med_samandrag": kopling_del(V, pop, KP, rader_maske=~tb),
          "kanal": same_del(K.kanal, idx, rader, pop),
          "emne": same_del(K.emne, idx, rader, pop),
          "sprak": same_del([c if c not in "0u" else "" for c in K.sprak], idx, rader, pop)}
    for gruppe, mask in (("tittel_berre", tb), ("med_samandrag", ~tb)):
        r = mask[rader]
        ut[f"kanal_{gruppe}"] = same_del(K.kanal, idx[r], rader[r], pop)
        ut[f"emne_{gruppe}"] = same_del(K.emne, idx[r], rader[r], pop)
    r = tb[rader]
    ut["tittel_berre_homofili"] = {"del": round(float(tb[idx[r]].mean()), 4) if r.any() else None,
                                   "basis": round(float(tb[pop].mean()), 4)}
    ut["snitt_cos_k"] = round(float(sim.mean()), 4)
    return ut


# ---------------------------------------------------------------------------
# Graph, clustering and cluster measures
# ---------------------------------------------------------------------------


def fuzzy_graf(idx: np.ndarray, sim: np.ndarray, n: int):
    """UMAP-style fuzzy kNN graph: w_ij = exp(-(d_ij - rho_i) / sigma_i), symmetrised by fuzzy union."""
    from scipy import sparse

    k = idx.shape[1]
    d = np.maximum(1.0 - sim.astype(np.float64), 0.0)
    rho = d[:, 0]
    dd = np.maximum(d - rho[:, None], 0.0)
    mal = math.log2(k)
    lo = np.zeros(n)
    hi = np.full(n, np.inf)
    sig = np.ones(n)
    for _ in range(64):
        s = np.exp(-dd / sig[:, None]).sum(1)
        for_stor = s > mal
        hi = np.where(for_stor, sig, hi)
        lo = np.where(for_stor, lo, sig)
        sig = np.where(np.isinf(hi), sig * 2.0, (lo + hi) / 2.0)
    w = np.exp(-dd / sig[:, None])
    A = sparse.csr_matrix((w.ravel(), (np.repeat(np.arange(n), k), idx.ravel())), shape=(n, n))
    W = A + A.T - A.multiply(A.T)
    W = W.tocsr()
    W.eliminate_zeros()
    return W


def nx_graf(W):
    import networkx as nx

    C = W.tocoo()
    v = C.row < C.col
    G = nx.Graph()
    G.add_nodes_from(range(W.shape[0]))
    G.add_weighted_edges_from(zip(C.row[v].tolist(), C.col[v].tolist(), C.data[v].tolist()))
    return G


def ordne(lab: np.ndarray) -> np.ndarray:
    """Relabel 0..k-1 by size (largest first), ties by smallest member index."""
    u = np.unique(lab)
    nokkel = sorted(u, key=lambda c: (-int((lab == c).sum()), int(np.flatnonzero(lab == c)[0])))
    om = {c: j for j, c in enumerate(nokkel)}
    return np.asarray([om[c] for c in lab], dtype=np.int64)


def louvain(G, n: int, opploysing: float, seed: int) -> np.ndarray:
    import networkx as nx

    lab = np.empty(n, dtype=np.int64)
    for j, c in enumerate(nx.community.louvain_communities(G, weight="weight", resolution=opploysing, seed=seed)):
        lab[list(c)] = j
    return ordne(lab)


def sla_saman_sma(lab: np.ndarray, W, V: np.ndarray, min_n: int) -> np.ndarray:
    """Merge clusters smaller than min_n into the cluster they share most edge weight with (else nearest centroid)."""
    lab = lab.copy()
    while True:
        st = np.bincount(lab)
        sma = [c for c in np.argsort(st, kind="stable") if 0 < st[c] < min_n]
        if not sma or (st > 0).sum() <= 1:
            break
        c = sma[0]
        med = np.flatnonzero(lab == c)
        rad = W[med].tocoo()
        vekt = collections.Counter()
        for j, w in zip(rad.col, rad.data):
            if lab[j] != c:
                vekt[int(lab[j])] += float(w)
        if vekt:
            mal = sorted(vekt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        else:
            s = normaliser(V[med].mean(0, keepdims=True))[0]
            cand = [d for d in range(len(st)) if d != c and st[d] > 0]
            sent = np.stack([normaliser(V[lab == d].mean(0, keepdims=True))[0] for d in cand])
            mal = cand[int(np.argmax(sent @ s))]
        lab[med] = mal
    return ordne(lab)


def kmeans_sfarisk(V: np.ndarray, k: int, seed: int, maks: int = 100) -> np.ndarray:
    n = V.shape[0]
    rng = np.random.default_rng(seed)
    senter = np.empty((k, V.shape[1]), dtype=np.float32)
    senter[0] = V[int(rng.integers(n))]
    d = np.maximum(1.0 - V @ senter[0], 0.0).astype(np.float64)
    for j in range(1, k):
        p = d * d
        s = p.sum()
        senter[j] = V[int(rng.integers(n)) if s <= 0 else int(rng.choice(n, p=p / s))]
        d = np.minimum(d, np.maximum(1.0 - V @ senter[j], 0.0))
    forrige = None
    for _ in range(maks):
        ny = (V @ senter.T).argmax(1)
        if forrige is not None and np.array_equal(ny, forrige):
            break
        forrige = ny
        for j in range(k):
            m = ny == j
            if m.any():
                c = V[m].mean(0)
                senter[j] = c / np.linalg.norm(c)
    return ordne(ny)


def kontingens(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    _, ia = np.unique(a, return_inverse=True)
    _, ib = np.unique(b, return_inverse=True)
    M = np.zeros((ia.max() + 1, ib.max() + 1), dtype=np.int64)
    np.add.at(M, (ia, ib), 1)
    return M


def ari(a: np.ndarray, b: np.ndarray) -> float:
    M = kontingens(a, b).astype(np.float64)
    n = M.sum()
    c2 = lambda x: x * (x - 1) / 2.0  # noqa: E731
    s = c2(M).sum()
    sa = c2(M.sum(1)).sum()
    sb = c2(M.sum(0)).sum()
    forv = sa * sb / c2(n)
    mx = (sa + sb) / 2
    return float((s - forv) / (mx - forv)) if mx != forv else 1.0


def nmi(a, b) -> float:
    M = kontingens(np.asarray(a), np.asarray(b)).astype(np.float64)
    n = M.sum()
    pa, pb = M.sum(1) / n, M.sum(0) / n
    P = M / n
    nz = P > 0
    mi = (P[nz] * np.log(P[nz] / np.outer(pa, pb)[nz])).sum()
    ha = -(pa[pa > 0] * np.log(pa[pa > 0])).sum()
    hb = -(pb[pb > 0] * np.log(pb[pb > 0])).sum()
    return float(mi / math.sqrt(ha * hb)) if ha > 0 and hb > 0 else 0.0


def silhuett(V: np.ndarray, lab: np.ndarray, blokk: int = 1024) -> tuple[float, np.ndarray]:
    """Mean cosine silhouette, and per-work values."""
    n = V.shape[0]
    k = int(lab.max()) + 1
    O = np.zeros((n, k), dtype=np.float32)
    O[np.arange(n), lab] = 1.0
    st = O.sum(0)
    s = np.empty(n)
    for b in range(0, n, blokk):
        D = 1.0 - V[b: b + blokk] @ V.T
        r = np.arange(D.shape[0])
        D[r, b + r] = 0.0
        sumd = D @ O
        eigen = lab[b: b + blokk]
        a = sumd[r, eigen] / np.maximum(st[eigen] - 1, 1)
        snitt = sumd / st[None, :]
        snitt[r, eigen] = np.inf
        bb = snitt.min(1)
        s[b: b + blokk] = np.where(st[eigen] > 1, (bb - a) / np.maximum(np.maximum(a, bb), 1e-12), 0.0)
    return float(s.mean()), s


def modularitet(W, lab: np.ndarray) -> float:
    C = W.tocoo()
    m2 = float(C.data.sum())
    inne = float(C.data[lab[C.row] == lab[C.col]].sum())
    grad = np.asarray(W.sum(1)).ravel()
    dc = np.bincount(lab, weights=grad)
    return inne / m2 - float(((dc / m2) ** 2).sum())


def kopling_inne(lab: np.ndarray, KP: Ns, maske: np.ndarray | None = None) -> dict:
    p = KP.har_ref if maske is None else (KP.har_ref & maske)
    i, j = kopla_par_i(KP, p)
    same = lab[i] == lab[j]
    m = int(p.sum())
    st = np.bincount(lab[p], minlength=int(lab.max()) + 1).astype(np.float64)
    par_same = float((st * (st - 1) / 2).sum())
    par_alle = m * (m - 1) / 2
    inne = float(same.mean()) if len(same) else 0.0
    forv = par_same / par_alle
    tett_inne = same.sum() / par_same if par_same else 0.0
    tett_mellom = (~same).sum() / (par_alle - par_same) if par_alle > par_same else 0.0
    return {"del_inne": round(inne, 4), "venta": round(forv, 4), "loft": round(inne / forv, 2) if forv else None,
            "tettleik_inne": round(float(tett_inne), 5), "tettleik_mellom": round(float(tett_mellom), 5),
            "forhold": round(float(tett_inne / tett_mellom), 2) if tett_mellom else None, "par": int(len(same))}


def nmi_mot(lab: np.ndarray, eigenskap: list[str]) -> float:
    r = [i for i, x in enumerate(eigenskap) if x]
    return round(nmi(lab[r], [eigenskap[i] for i in r]), 4)


def stabilitet(partisjonar: list[np.ndarray]) -> dict:
    v = [ari(partisjonar[a], partisjonar[b]) for a in range(len(partisjonar)) for b in range(a + 1, len(partisjonar))]
    return {"snitt": round(float(np.mean(v)), 4), "min": round(float(np.min(v)), 4)}


def klynge_stabilitet(ref: np.ndarray, andre: list[np.ndarray]) -> list[float]:
    """Per cluster of ref: mean over the other runs of the best Jaccard overlap with any of their clusters."""
    ut = []
    for c in range(int(ref.max()) + 1):
        A = ref == c
        js = []
        for p in andre:
            best = 0.0
            for d in np.unique(p[A]):
                B = p == d
                best = max(best, float((A & B).sum() / (A | B).sum()))
            js.append(best)
        ut.append(round(float(np.mean(js)), 3))
    return ut


def grense(lab: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Share of each work's neighbours that share its cluster."""
    return (lab[idx] == lab[:, None]).mean(1)


def mal_partisjon(lab: np.ndarray, V: np.ndarray, W, KP: Ns, K: Ns, idx: np.ndarray, sil: bool = True) -> dict:
    st = np.bincount(lab)
    ut = {"k": int(len(st)), "storleikar": [int(x) for x in st],
          "modularitet": round(modularitet(W, lab), 4),
          "kopling": kopling_inne(lab, KP),
          "nmi_kanal": nmi_mot(lab, K.kanal), "nmi_emne": nmi_mot(lab, K.emne),
          "nmi_sprak": nmi_mot(lab, [c if c not in "0u" else "" for c in K.sprak]),
          "nmi_tittel_berre": round(nmi(lab, K.tittel_berre.astype(int)), 4)}
    g = grense(lab, idx)
    ut["grense_del"] = round(float((g < GRENSE_DEL).mean()), 4)
    ut["nabo_inne"] = round(float(g.mean()), 4)
    if sil:
        ut["silhuett"] = round(silhuett(V, lab)[0], 4)
    return ut


def null_silhuett(V: np.ndarray, k: int, seed: int = 7) -> float:
    """Silhouette of k-means on a Gaussian cloud with the same mean and covariance (no cluster structure)."""
    rng = np.random.default_rng(seed)
    mu = V.mean(0)
    C = np.cov(V.T.astype(np.float64))
    Z = rng.multivariate_normal(mu, C, size=V.shape[0]).astype(np.float32)
    Z = normaliser(Z)
    return round(silhuett(Z, kmeans_sfarisk(Z, k, 0))[0], 4)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def svd2(V: np.ndarray) -> np.ndarray:
    Vc = V - V.mean(0)
    _, _, vt = np.linalg.svd(Vc.astype(np.float64), full_matrices=False)
    Y = Vc @ vt[:2].T
    for c in range(2):
        if Y[np.argmax(np.abs(Y[:, c])), c] < 0:
            Y[:, c] *= -1
    return Y


def umap_lik(W, V: np.ndarray, epokar: int, seed: int, a: float = 1.577, b: float = 0.895, neg: int = 5) -> np.ndarray:
    """A UMAP-like layout: spectral start, then attraction along fuzzy kNN edges and repulsion from random points,
    in small batches so that each point moves about once per batch."""
    from scipy.sparse import csgraph
    from scipy.sparse.linalg import eigsh

    n = W.shape[0]
    rng = np.random.default_rng(seed)
    ncomp, _ = csgraph.connected_components(W, directed=False)
    if ncomp == 1:
        grad = np.asarray(W.sum(1)).ravel()
        Dm = 1.0 / np.sqrt(grad)
        from scipy import sparse

        Nm = sparse.diags(Dm) @ W @ sparse.diags(Dm)
        v0 = np.sqrt(grad) / np.linalg.norm(np.sqrt(grad))
        val, vec = eigsh(Nm, k=3, which="LA", v0=v0, tol=1e-6, maxiter=n * 20)
        o = np.argsort(-val)
        Y = vec[:, o[1:3]]
    else:
        Y = svd2(V)
    for c in range(2):
        if Y[np.argmax(np.abs(Y[:, c])), c] < 0:
            Y[:, c] *= -1
    Y = (Y * (10.0 / np.abs(Y).max())).astype(np.float64) + rng.normal(0, 1e-4, size=(n, 2))
    C = W.tocoo()
    wmax = C.data.max()
    hold = C.data >= wmax / epokar
    ri, ci, w = C.row[hold], C.col[hold], C.data[hold]
    eps = wmax / w
    neste = eps.copy()
    batch = max(n // 2, 256)
    for e in range(epokar):
        alfa = 1.0 - e / epokar
        aktiv = np.flatnonzero(neste <= e + 1)
        neste[aktiv] += eps[aktiv]
        aktiv = aktiv[rng.permutation(len(aktiv))]
        for s in range(0, len(aktiv), batch):
            ed = aktiv[s: s + batch]
            i, j = ri[ed], ci[ed]
            dv = Y[i] - Y[j]
            d2 = (dv * dv).sum(1)
            koef = np.where(d2 > 0, -2.0 * a * b * np.power(np.maximum(d2, 1e-12), b - 1.0) / (1.0 + a * np.power(d2, b)), 0.0)
            g = np.clip(koef[:, None] * dv, -4, 4) * alfa
            dY = np.zeros_like(Y)
            np.add.at(dY, i, g)
            np.add.at(dY, j, -g)
            ii = np.repeat(i, neg)
            kk = rng.integers(0, n, size=len(ii))
            dv = Y[ii] - Y[kk]
            d2 = (dv * dv).sum(1)
            koef = 2.0 * b / ((0.001 + d2) * (1.0 + a * np.power(d2, b)))
            g = np.where((kk != ii)[:, None], np.clip(koef[:, None] * dv, -4, 4), 0.0) * alfa
            np.add.at(dY, ii, g)
            Y += dY
        if (e + 1) % 100 == 0:
            logg(f"umap-lik: epoke {e + 1}/{epokar}, maks|Y| {float(np.abs(Y).max()):.1f}")
    return Y


def tillit_kontinuitet(V: np.ndarray, Y: np.ndarray, k: int = K_NN, blokk: int = 256) -> dict:
    """Trustworthiness, continuity and the share of the k nearest neighbours kept, high-D cosine against 2D Euclid."""
    n = V.shape[0]
    Y = Y.astype(np.float64)
    sq = (Y * Y).sum(1)
    sum_t = 0.0
    sum_c = 0.0
    behalde = 0
    ar = np.arange(n, dtype=np.int32) + 1
    for b in range(0, n, blokk):
        r = np.arange(min(blokk, n - b))
        S = V[b: b + blokk] @ V.T
        S[r, b + r] = np.inf
        oh = np.argsort(-S, axis=1, kind="stable")  # self first
        rank_h = np.empty_like(oh, dtype=np.int32)
        np.put_along_axis(rank_h, oh, np.broadcast_to(ar - 1, oh.shape), 1)  # self has rank 0
        D = sq[b: b + blokk, None] + sq[None, :] - 2.0 * Y[b: b + blokk] @ Y.T
        D[r, b + r] = -np.inf
        ol = np.argsort(D, axis=1, kind="stable")
        rank_l = np.empty_like(ol, dtype=np.int32)
        np.put_along_axis(rank_l, ol, np.broadcast_to(ar - 1, ol.shape), 1)
        nn_h = oh[:, 1: k + 1]
        nn_l = ol[:, 1: k + 1]
        rh_av_l = np.take_along_axis(rank_h, nn_l, 1)
        rl_av_h = np.take_along_axis(rank_l, nn_h, 1)
        sum_t += float(np.maximum(rh_av_l - k, 0).sum())
        sum_c += float(np.maximum(rl_av_h - k, 0).sum())
        behalde += int((rh_av_l <= k).sum())
    f = 2.0 / (n * k * (2 * n - 3 * k - 1))
    return {"tillit": round(1 - f * sum_t, 4), "kontinuitet": round(1 - f * sum_c, 4),
            "naboar_behaldne": round(behalde / (n * k), 4)}


def til_ruta(Y: np.ndarray) -> np.ndarray:
    """Centre on the median, scale so 99.5 % of points fit, clip, and map to integers 0..SKALA (y grows downwards)."""
    Yc = Y.astype(np.float64) - np.median(Y, axis=0)
    rad = np.abs(Yc).max(1)
    r = np.percentile(rad, 99.5)
    r = r if r > 0 else 1.0
    # the outermost 0.5 % are pulled in softly (to at most 1.06 r) instead of being clipped onto the edge
    ute = rad > r
    ny = r + 0.06 * r * (1.0 - np.exp(-(rad[ute] - r) / r))
    Yc[ute] *= (ny / rad[ute])[:, None]
    s = (0.47 * SKALA) / (1.06 * r)
    x = np.clip(np.rint(SKALA / 2 + Yc[:, 0] * s), 0, SKALA).astype(np.int64)
    y = np.clip(np.rint(SKALA / 2 - Yc[:, 1] * s), 0, SKALA).astype(np.int64)
    return np.stack([x, y], 1)


def etikettpunkt(P: np.ndarray, med: np.ndarray, sentral: np.ndarray, radius: float) -> list[int]:
    """Label anchor: the member where the group is both dense and in the majority. Score = own works within radius
    times their share of all works within radius, so a small tight clump inside another cluster loses to the main
    mode. Ties go to the more central work. (A plain density peak with a small radius put the label of a bimodal
    cluster on a secondary clump where the cluster was a minority.)"""
    p = P[med].astype(np.float64)
    alle = P.astype(np.float64)
    if len(med) > 1500:
        rng = np.random.default_rng(0)
        prove = np.sort(rng.choice(len(med), 1500, replace=False))
    else:
        prove = np.arange(len(med))
    eigen = np.zeros(len(prove))
    tot = np.zeros(len(prove))
    r2 = radius * radius
    for b in range(0, len(prove), 256):
        q = p[prove[b: b + 256]]
        eigen[b: b + 256] = (((q[:, None, :] - p[None, :, :]) ** 2).sum(2) <= r2).sum(1)
        tot[b: b + 256] = (((q[:, None, :] - alle[None, :, :]) ** 2).sum(2) <= r2).sum(1)
    skar = eigen * eigen / np.maximum(tot, 1.0)
    best = max(range(len(prove)), key=lambda t: (round(float(skar[t]), 6), float(sentral[med[prove[t]]]), -prove[t]))
    return [int(p[prove[best], 0]), int(p[prove[best], 1])]


def fargeplassar(nokklar: list[list[str]]) -> list[int]:
    """Palette slot per top cluster from FARGE_TOPP (key = one of the cluster's naming keys); free slots for the rest."""
    if len(nokklar) > PALETT_PLASSAR:
        raise SystemExit(f"{len(nokklar)} klynger, men paletten på sida har berre {PALETT_PLASSAR} fargar")
    ut: list[int | None] = []
    for nk in nokklar:
        ut.append(next((FARGE_TOPP[w] for w in nk if w in FARGE_TOPP), None))
    brukt: set[int] = set()
    for c, s in enumerate(ut):
        if s is not None and s in brukt:
            logg(f"fargeplass {s} er alt teken, klynge {c} får ein ledig")
            ut[c] = None
        elif s is not None:
            brukt.add(s)
    ledige = [s for s in range(PALETT_PLASSAR) if s not in brukt]
    for c, s in enumerate(ut):
        if s is None:
            ut[c] = ledige.pop(0)
            logg(f"klynge {c} har ingen fargenøkkel, får plass {ut[c]}")
    return [int(s) for s in ut]  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Terms (class-based TF-IDF over titles and abstracts)
# ---------------------------------------------------------------------------


def termar_per_verk(K: Ns) -> tuple[list[str], "object"]:
    """Binary work x term matrix of unigrams and bigrams in title + abstract (stop words removed)."""
    from scipy import sparse

    vok: dict[str, int] = {}
    rader, kol = [], []
    for i in range(K.n):
        tekst = unicodedata.normalize("NFC", f"{K.tittel[i]} . {K.abstrakt[i]}").lower()
        sett = set()
        for seg in re.split(r"[.,;:!?()\[\]{}\"“”«»/|]", tekst):
            ord_ = [o.replace("’", "'") for o in ORD_RE.findall(seg)]
            for a, o in enumerate(ord_):
                if o not in STOPPORD and len(o) >= 3:
                    sett.add(o)
                if a + 1 < len(ord_):
                    o2 = ord_[a + 1]
                    if o not in STOPPORD and o2 not in STOPPORD and len(o) >= 2 and len(o2) >= 2:
                        sett.add(f"{o} {o2}")
        for t in sett:
            j = vok.setdefault(t, len(vok))
            rader.append(i)
            kol.append(j)
    X = sparse.csr_matrix((np.ones(len(rader), dtype=np.int32), (rader, kol)), shape=(K.n, len(vok)))
    df = np.asarray(X.sum(0)).ravel()
    hald = np.flatnonzero((df >= 5) & (df <= 0.4 * K.n))
    namn = list(vok)
    return [namn[j] for j in hald], X[:, hald].tocsc()


def fornamn_sjekk(termlister: list[list[str]], min_n: int = 20) -> list[str]:
    """Published terms with a token that is the given name of an author with at least min_n authorships. For the
    log only: common words that are also names (young, urban) show up here too and are left for a reader to judge."""
    db = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
    tel: collections.Counter = collections.Counter()
    for (n,) in db.execute("select author_name from authorships"):
        for t in str(n or "").replace(",", " ").split()[:-1]:
            tel[t.lower()] += 1
    db.close()
    return sorted({t for lst in termlister for t in lst if any(tel[o] >= min_n for o in t.split())})


def ctfidf(teljar: np.ndarray) -> np.ndarray:
    """c-TF-IDF with lift (as in visdata.ctfidf). teljar[t, c] = works in class c with term t."""
    teljar = teljar.astype(np.float64)
    tot_c = np.maximum(teljar.sum(0), 1.0)
    snitt = tot_c.mean()
    tf_alle = np.maximum(teljar.sum(1), 1.0)
    skar = teljar / tot_c[None, :] * np.log(1.0 + snitt / tf_alle[:, None])
    lift = (teljar / tf_alle[:, None]) / (tot_c[None, :] / tot_c.sum())
    return skar * lift


def klassetermar(termar: list[str], X, klasse: np.ndarray, antal: int, ut_n: int = 8, min_df: int = 3) -> list[list[str]]:
    from scipy import sparse

    v = np.flatnonzero(klasse >= 0)
    O = sparse.csr_matrix((np.ones(len(v)), (klasse[v], v)), shape=(antal, X.shape[0]))
    M = np.asarray((O @ X).todense()).T  # terms x classes
    sk = ctfidf(M)
    ut = []
    for c in range(antal):
        valde: list[str] = []
        for t in np.argsort(-sk[:, c], kind="stable"):
            if M[t, c] < min_df:
                continue
            ord_ = termar[t]
            if any(o in PERSONNAMN for o in ord_.split()):
                continue
            kk = f" {ord_} "
            if any(kk in f" {x} " or f" {x} " in kk for x in valde):
                continue
            valde.append(ord_)
            if len(valde) >= ut_n:
                break
        ut.append(valde)
    return ut


# ---------------------------------------------------------------------------
# Cluster descriptions
# ---------------------------------------------------------------------------


def periodeprofil(ar: np.ndarray) -> list[int]:
    return [int(((ar >= lo) & (ar <= hi)).sum()) for _, lo, hi in PERIODAR]


def toppliste(verdiar: list[str], n: int = 5) -> list[list]:
    tel = collections.Counter(v for v in verdiar if v)
    return [[k, c] for k, c in sorted(tel.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def unike_titlar(K: Ns, rekkje: np.ndarray, n: int) -> list[int]:
    """The first n works of a ranking, one work per title (duplicate records and chapters share titles)."""
    sett: set[str] = set()
    ut: list[int] = []
    for i in rekkje:
        f = fold(K.tittel[i])
        if f in sett:
            continue
        sett.add(f)
        ut.append(int(i))
        if len(ut) >= n:
            break
    return ut


def skildre(K: Ns, V: np.ndarray, med: np.ndarray) -> Ns:
    """Profile of a group. Three rankings by cosine to the group's mean vector in the text space:
    nokkel (all works; the naming keys, as when the names were checked), sentrale (the five shown on the page) and
    sentrale60 (the catalogue link). The shown rankings take works with an abstract first and title-only works only
    when there are too few: a title-only vector is built from a few words, sits closer to the generic middle and
    filled 30 of the 40 places when all works were ranked together."""
    c = normaliser(V[med].mean(0, keepdims=True))[0]
    cos = V[med] @ c
    rekkje_alle = med[np.lexsort((med, -cos))]
    tb = K.tittel_berre[rekkje_alle]
    rekkje_vist = np.concatenate([rekkje_alle[~tb], rekkje_alle[tb]])
    nokkel = unike_titlar(K, rekkje_alle, 8)
    vist = unike_titlar(K, rekkje_vist, 60)
    rekkje = np.asarray(nokkel, dtype=np.int64)
    vis_kanal: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for i in med:
        if K.kanal[i]:
            vis_kanal[K.kanal[i]][K.kanal_vis[i]] += 1
    kanalar = toppliste([K.kanal[i] for i in med])
    kanalar = [[kort(sorted(vis_kanal[k].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]), n] for k, n in kanalar]
    land = toppliste([c for i in med for c in K.land[i]])
    nordisk = np.asarray([K.sprak[i] in NORDISKE_SPRAK for i in med])
    return Ns(nokkel=[K.ids[i] for i in rekkje[:5]], sentrale_i=rekkje[:8], sentrale=[K.ids[i] for i in vist[:5]],
              sentrale60=vist, periode=periodeprofil(K.ar[med]), kanalar=kanalar, land=land, sentrum=c, cos=cos,
              nordisk=round(float(nordisk.mean()), 3) if len(med) else 0.0)


def kort(s: str, maks: int = 100) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= maks else s[: maks - 1].rstrip() + "…"


def vel_namn(sentrale: list[str], tabell: dict[str, str], termar: list[str]) -> tuple[str, bool]:
    for w in sentrale:
        if w in tabell:
            return tabell[w], True
    auto = ", ".join(termar[:2]) if termar else "utan namn"
    return auto[:1].upper() + auto[1:], False


# ---------------------------------------------------------------------------
# Number formatting for the Nynorsk text
# ---------------------------------------------------------------------------


def tal(x: float | int, des: int = 0) -> str:
    if des == 0:
        s = f"{int(round(x)):,}".replace(",", "\u00a0")
    else:
        s = f"{x:,.{des}f}".replace(",", "X").replace(".", ",").replace("X", "\u00a0")
    return s


def pst(x: float, des: int = 0) -> str:
    return f"{tal(100 * x, des)}\u00a0%"


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def steg_kjelder(K: Ns, KP: Ns) -> tuple[dict, dict]:
    Va = vektorar_a(K)
    tb = K.tittel_berre
    gs = Va.copy()
    gs[tb] = Va[tb] - Va[tb].mean(0)
    gs[~tb] = Va[~tb] - Va[~tb].mean(0)
    vek = {"a": Va, "a_sentrert": sentrer(Va), "a_gruppesentrert": normaliser(gs),
           "a_justert": juster_tittel_berre(Va, tb), "a_justert_krymp0.001": juster_tittel_berre(Va, tb, 0.001),
           "b": vektorar_b(K)}
    vek["b_sentrert"] = sentrer(vek["b"])
    alle = np.ones(K.n, dtype=bool)
    res = {"alle": [], "fulltekst": []}
    for nm in ("a", "a_sentrert", "a_gruppesentrert", "a_justert", "a_justert_krymp0.001", "b", "b_sentrert"):
        res["alle"].append(evaluer_kjelde(nm, vek[nm], alle, K, KP))
        logg(f"kjelde {nm} (alle): kopling {res['alle'][-1]['kopling']}, kanal {res['alle'][-1]['kanal']}")
    c = vektorar_c(K)
    if c is not None:
        mask, Xc = c
        vek["c"] = Xc
        Xcs = Xc.copy()
        Xcs[mask] = sentrer(Xc[mask])
        vek["c_sentrert"] = Xcs
        blanda = vek["a_sentrert"].copy()
        blanda[mask] = normaliser(vek["a_sentrert"][mask] + sentrer(Xc[mask]))
        vek["a+c"] = blanda
        Vas_ft = vek["a"].copy()
        Vas_ft[mask] = sentrer(vek["a"][mask])
        for nm, V in (("a", vek["a"]), ("a_sentrert", Vas_ft), ("a_justert", vek["a_justert"]), ("b", vek["b"]),
                      ("c", Xc), ("c_sentrert", Xcs), ("a+c", blanda)):
            res["fulltekst"].append(evaluer_kjelde(nm, V, mask, K, KP))
            logg(f"kjelde {nm} (fulltekst, {int(mask.sum())}): kopling {res['fulltekst'][-1]['kopling']}")
    return res, vek


def steg_kandidatar(K: Ns, KP: Ns, V: np.ndarray, W, idx: np.ndarray) -> dict:
    G = nx_graf(W)
    ut = {"louvain": [], "kmeans": []}
    for r in KANDIDAT_OPPLOYSING:
        parts = []
        for s in SEEDS:
            parts.append(sla_saman_sma(louvain(G, K.n, r, s), W, V, MIN_TOPP))
        m = mal_partisjon(parts[0], V, W, KP, K, idx)
        m.update({"oppløysing": r, "stabilitet": stabilitet(parts),
                  "k_over_seeds": sorted({int(p.max()) + 1 for p in parts})})
        ut["louvain"].append(m)
        logg(f"louvain r={r}: k={m['k']} sil={m['silhuett']} stab={m['stabilitet']} mod={m['modularitet']} "
             f"kopling-løft={m['kopling']['loft']} grense={m['grense_del']}")
    for k in KANDIDAT_K:
        parts = [kmeans_sfarisk(V, k, s) for s in SEEDS]
        m = mal_partisjon(parts[0], V, W, KP, K, idx)
        m.update({"stabilitet": stabilitet(parts), "null_silhuett": null_silhuett(V, k)})
        ut["kmeans"].append(m)
        logg(f"kmeans k={k}: sil={m['silhuett']} (null {m['null_silhuett']}) stab={m['stabilitet']} "
             f"mod={m['modularitet']} kopling-løft={m['kopling']['loft']} grense={m['grense_del']}")
    return ut


def topp_partisjon(K: Ns, V: np.ndarray, W) -> tuple[np.ndarray, list[np.ndarray]]:
    metode, par = TOPP_METODE
    if metode == "louvain":
        G = nx_graf(W)
        parts = [sla_saman_sma(louvain(G, K.n, par, s), W, V, MIN_TOPP) for s in SEEDS]
    else:
        parts = [kmeans_sfarisk(V, int(par), s) for s in SEEDS]
    return parts[0], parts


def under_partisjon(V: np.ndarray, W, topp: np.ndarray, opploysing: float, seeds=SEEDS) -> tuple[np.ndarray, list[dict]]:
    """Louvain inside each top cluster. Returns global sub-cluster ids (ordered by top cluster, then size) and
    per-top statistics."""
    import networkx as nx  # noqa: F401

    under = np.full(len(topp), -1, dtype=np.int64)
    stat = []
    base = 0
    for c in range(int(topp.max()) + 1):
        med = np.flatnonzero(topp == c)
        Ws = W[med][:, med].tocsr()
        G = nx_graf(Ws)
        parts = [sla_saman_sma(louvain(G, len(med), opploysing, s), Ws, V[med], MIN_UNDER) for s in seeds]
        lab = parts[0]
        sil = silhuett(V[med], lab)[0] if lab.max() > 0 else 0.0
        stat.append({"topp": c, "n": int(len(med)), "k": int(lab.max()) + 1,
                     "stabilitet": stabilitet(parts) if len(parts) > 1 else None, "silhuett": round(sil, 4),
                     "storleikar": [int(x) for x in np.bincount(lab)],
                     "klynge_stabilitet": klynge_stabilitet(lab, parts[1:]) if len(parts) > 1 else None})
        under[med] = base + lab
        base += int(lab.max()) + 1
    return under, stat


def under_kmeans_tabell(V: np.ndarray, topp: np.ndarray, KP: Ns) -> list[dict]:
    """For each top cluster and k in UNDER_K: stability over the seeds, silhouette, coupling ratio, smallest size."""
    ut = []
    for c in range(int(topp.max()) + 1):
        med = np.flatnonzero(topp == c)
        Vc = V[med]
        rad = {"topp": c, "n": int(len(med)), "k": {}}
        for k in UNDER_K:
            parts = [kmeans_sfarisk(Vc, k, s) for s in SEEDS]
            lab = np.full(len(topp), -1, dtype=np.int64)
            lab[med] = parts[0]
            maske = topp == c
            kop = kopling_inne(np.where(maske, lab, 0), KP, maske)
            rad["k"][k] = {"stabilitet": stabilitet(parts)["snitt"], "silhuett": round(silhuett(Vc, parts[0])[0], 4),
                           "kopling_forhold": kop["forhold"], "minste": int(np.bincount(parts[0]).min())}
        rad["vald_k"] = vel_under_k(rad["k"])
        ut.append(rad)
        logg(f"under-kmeans topp {c} (n={len(med)}): " + "  ".join(
            f"k{k}: stab {v['stabilitet']} sil {v['silhuett']} kop {v['kopling_forhold']}" for k, v in rad["k"].items())
            + f"  -> {rad['vald_k']}")
    return ut


def vel_under_k(tab: dict) -> int:
    """The largest k whose mean ARI over the ten seeds is at least UNDER_MIN_STAB and whose smallest sub-cluster
    has at least MIN_UNDER works; if none, the most stable k."""
    ok = [k for k, v in tab.items() if v["stabilitet"] >= UNDER_MIN_STAB and v["minste"] >= MIN_UNDER]
    if ok:
        return max(ok)
    return max(tab, key=lambda k: (tab[k]["stabilitet"], -k))


def kopling_per_topp(under: np.ndarray, topp: np.ndarray, KP: Ns) -> float:
    """Mean over top clusters of the coupling density ratio (inside sub-cluster against between sub-clusters)."""
    v = []
    for c in range(int(topp.max()) + 1):
        m = topp == c
        f = kopling_inne(np.where(m, under, 0), KP, m)["forhold"]
        if f is not None:
            v.append(f)
    return round(float(np.mean(v)), 3)


def kopling_inne_forelder(under: np.ndarray, topp: np.ndarray, KP: Ns) -> dict:
    """Coupling density ratio for sub-clusters counted only over pairs inside the same top cluster (pooled):
    P(coupled | same sub-cluster) / P(coupled | same top cluster, other sub-cluster). Unlike the ratio over all
    pairs, this does not contain the top-level effect."""
    p = KP.har_ref
    i, j = kopla_par_i(KP, p)
    st = topp[i] == topp[j]
    su = under[i] == under[j]
    nt = np.bincount(topp[p]).astype(np.float64)
    nu = np.bincount(under[p]).astype(np.float64)
    par_u = float((nu * (nu - 1) / 2).sum())
    par_t = float((nt * (nt - 1) / 2).sum()) - par_u
    tett_u = float((st & su).sum()) / par_u
    tett_t = float((st & ~su).sum()) / par_t
    return {"forhold": round(tett_u / tett_t, 2), "tettleik_same_under": round(tett_u, 5),
            "tettleik_same_topp_anna_under": round(tett_t, 5)}


def steg_under_kandidatar(V: np.ndarray, W, topp: np.ndarray, KP: Ns, kmeans_tab: list[dict]) -> list[dict]:
    ut = []
    for r in UNDER_KANDIDATAR:
        under, stat = under_partisjon(V, W, topp, r)
        ks = [s["k"] for s in stat]
        st = [s["stabilitet"]["snitt"] for s in stat]
        ut.append({"metode": "louvain", "oppløysing": r, "k_per_topp": ks, "sum_k": int(sum(ks)),
                   "stabilitet_snitt": round(float(np.mean(st)), 4), "stabilitet_min": round(float(np.min(st)), 4),
                   "silhuett_snitt": round(float(np.mean([s["silhuett"] for s in stat])), 4),
                   "kopling_forhold_snitt": kopling_per_topp(under, topp, KP),
                   "minste": int(min(min(s["storleikar"]) for s in stat))})
        logg(f"under louvain r={r}: {ut[-1]}")
    for k in UNDER_K:  # the same k in every top cluster, for comparison
        st = [t["k"][k]["stabilitet"] for t in kmeans_tab]
        kp = [t["k"][k]["kopling_forhold"] for t in kmeans_tab if t["k"][k]["kopling_forhold"] is not None]
        ut.append({"metode": "kmeans", "k": k, "sum_k": k * len(kmeans_tab),
                   "stabilitet_snitt": round(float(np.mean(st)), 4), "stabilitet_min": round(float(np.min(st)), 4),
                   "silhuett_snitt": round(float(np.mean([t["k"][k]["silhuett"] for t in kmeans_tab])), 4),
                   "kopling_forhold_snitt": round(float(np.mean(kp)), 3),
                   "minste": int(min(t["k"][k]["minste"] for t in kmeans_tab))})
        logg(f"under kmeans k={k}: {ut[-1]}")
    return ut


def tittel_tildeling(V: np.ndarray, topp: np.ndarray, K: Ns, KP: Ns, W) -> dict:
    """Compare treatments of title-only works: (med) clustered with the rest, versus (tildel) clusters built from
    works with an abstract only and title-only works given the majority cluster of their 15 nearest abstract works.
    External check: for title-only works with a reference list, the share of their coupled partners in the same
    cluster."""
    tb = K.tittel_berre
    ab = ~tb
    metode, par = TOPP_METODE
    Vab = V[ab]
    idx_ab, sim_ab = knn(V, K_NN, ab)
    W_ab = fuzzy_graf(np.searchsorted(np.flatnonzero(ab), idx_ab), sim_ab, int(ab.sum()))
    if metode == "louvain":
        lab_ab = sla_saman_sma(louvain(nx_graf(W_ab), int(ab.sum()), par, 0), W_ab, Vab, MIN_TOPP)
    else:
        lab_ab = kmeans_sfarisk(Vab, int(par), 0)
    tildelt = np.full(K.n, -1, dtype=np.int64)
    tildelt[ab] = lab_ab
    # nearest abstract works of each title-only work
    P = np.flatnonzero(ab)
    for b in range(0, K.n, 512):
        rad = np.arange(b, min(b + 512, K.n))
        rad = rad[tb[rad]]
        if not len(rad):
            continue
        S = V[rad] @ Vab.T
        part = np.argpartition(-S, K_NN - 1, axis=1)[:, :K_NN]
        for r, p in zip(rad, part):
            st = np.bincount(lab_ab[p], weights=np.take(V[P[p]] @ V[r], np.arange(K_NN)))
            tildelt[r] = int(np.argmax(st))

    def partnar_del(lab):
        i, j = kopla_par_i(KP, KP.har_ref)
        v = tb[i] | tb[j]
        return round(float((lab[i[v]] == lab[j[v]]).mean()), 4), int(v.sum())

    d_med, n_par = partnar_del(topp)
    d_tildel, _ = partnar_del(tildelt)
    return {"par_med_tittel_berre": n_par, "same_klynge_med": d_med, "same_klynge_tildel": d_tildel,
            "k_tildel": int(lab_ab.max()) + 1, "ari_med_mot_tildel": round(ari(topp, tildelt), 4),
            "kopling_med": kopling_inne(topp, KP), "kopling_tildel": kopling_inne(tildelt, KP)}


def lagre_bilete(sti: Path, P: np.ndarray, lab: np.ndarray, tittel: str, merk: np.ndarray | None = None) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return
    fig, ax = plt.subplots(figsize=(9, 9), dpi=90)
    cm = plt.get_cmap("tab20")
    ax.scatter(P[:, 0], -P[:, 1], s=2, c=[cm(int(c) % 20) for c in lab], linewidths=0)
    if merk is not None:
        ax.scatter(P[merk, 0], -P[merk, 1], s=0.5, c="k", linewidths=0, alpha=0.4)
    for c in range(int(lab.max()) + 1):
        m = lab == c
        ax.text(float(np.median(P[m, 0])), -float(np.median(P[m, 1])), str(c), fontsize=12, weight="bold")
    ax.set_title(tittel)
    ax.set_aspect("equal")
    fig.savefig(sti, bbox_inches="tight")
    plt.close(fig)


def skriv_json(sti: Path, obj, kompakt: bool = True) -> int:
    data = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if kompakt
            else json.dumps(obj, ensure_ascii=False, indent=1)) + "\n"
    b = data.encode("utf-8")
    sti.parent.mkdir(parents=True, exist_ok=True)
    tmp = sti.with_suffix(sti.suffix + ".tmp")
    tmp.write_bytes(b)
    os.replace(tmp, sti)
    return len(b)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m designteori.klynger", description="Bygg docs/data/klynger/ (kartet)")
    ap.add_argument("--berre", choices=["kjelder", "kandidatar", "under", "utforming"], default=None,
                    help="stopp etter dette steget (for utvikling)")
    ap.add_argument("--generert", default=None, help="fast tidsstempel (ISO) for eit reproduserbart bygg")
    ap.add_argument("--utan-sveip", action="store_true", help="hopp over kandidatsveipet (brukar lagra tal)")
    ap.add_argument("--notat", default=str(NOTAT))
    ap.add_argument("--ut", default=str(UT))
    args = ap.parse_args(argv)
    for strom in (sys.stdout, sys.stderr):
        try:
            strom.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    sett_lavare_prioritet()
    notat = Path(args.notat)
    notat.mkdir(parents=True, exist_ok=True)
    talfil = notat / "evaluering-tal.json"
    E = read_json(talfil) if talfil.exists() else {}
    if not isinstance(E, dict):
        E = {}

    K = les_korpus()
    logg(f"verk {K.n}, med samandrag {int((~K.tittel_berre).sum())}, berre tittel {int(K.tittel_berre.sum())}")
    vektor_sha = hashlib.sha256((SOK / K.meta["vectors"]["file"]).read_bytes()).hexdigest()
    meta_sha = ((K.meta.get("files") or {}).get(K.meta["vectors"]["file"]) or {}).get("sha256")
    if meta_sha != vektor_sha:
        raise SystemExit(f"vectors.i8 sha256 {vektor_sha[:12]} stemmer ikkje med meta.json ({str(meta_sha)[:12]})")
    logg(f"vectors.i8 sha256 {vektor_sha[:12]}")
    KP = les_kopling(K)

    # 1. vector sources
    res, vek = steg_kjelder(K, KP)
    E["kjelder"] = res
    skriv_json(talfil, E, kompakt=False)
    if args.berre == "kjelder":
        return 0
    V = vek[KJELDE]
    del vek

    # 2. graph and candidates
    idx90, sim90 = knn(V, 90)
    idx, sim = idx90[:, :K_NN], sim90[:, :K_NN]
    W = fuzzy_graf(idx, sim, K.n)
    logg(f"graf: {W.nnz // 2} kantar")
    if not args.utan_sveip or "kandidatar" not in E or "louvain" not in E.get("kandidatar", {}):
        E["kandidatar"] = steg_kandidatar(K, KP, V, W, idx)
        skriv_json(talfil, E, kompakt=False)
    if args.berre == "kandidatar":
        return 0

    topp, topp_parts = topp_partisjon(K, V, W)
    if not args.utan_sveip or "under_kandidatar" not in E:
        E["under_kmeans"] = under_kmeans_tabell(V, topp, KP)
        E["under_kandidatar"] = steg_under_kandidatar(V, W, topp, KP, E["under_kmeans"])
        E["tittel_berre"] = tittel_tildeling(V, topp, K, KP, W)
        logg(f"tittel berre: {E['tittel_berre']}")
        E.pop("under_kandidatar_louvain", None)
        skriv_json(talfil, E, kompakt=False)
    if args.berre == "under":
        return 0
    under, under_stat = under_partisjon(V, W, topp, UNDER_OPPLOYSING)
    mal = mal_partisjon(topp, V, W, KP, K, idx)
    mal["stabilitet"] = stabilitet(topp_parts)
    mal["null_silhuett"] = null_silhuett(V, int(topp.max()) + 1)
    _, sil_verk = silhuett(V, topp)
    klstab = klynge_stabilitet(topp, topp_parts[1:])
    mal_u = {"k": int(under.max()) + 1, "kopling": kopling_inne(under, KP), "silhuett": round(silhuett(V, under)[0], 4),
             "kopling_inne_forelder": kopling_inne_forelder(under, topp, KP),
             "kopling_snitt_per_topp": kopling_per_topp(under, topp, KP)}
    rng = np.random.default_rng(3)
    mal["nmi_kanal_null"] = round(float(np.mean([nmi_mot(rng.permutation(topp), K.kanal) for _ in range(5)])), 4)
    mal["nmi_emne_null"] = round(float(np.mean([nmi_mot(rng.permutation(topp), K.emne) for _ in range(5)])), 4)
    g_topp = grense(topp, idx)
    E["vald"] = {"topp": mal, "klynge_stabilitet": klstab, "under": mal_u, "under_per_topp": under_stat}
    skriv_json(talfil, E, kompakt=False)
    logg(f"vald topp: k={mal['k']} {mal['storleikar']} sil={mal['silhuett']} stab={mal['stabilitet']}")

    # 3. layouts
    from . import visdata

    utf = {}
    kp = notat / "tsne_kontrollpunkt.npz"
    Y_t = visdata.tsne(V, idx90.astype(np.int32), sim90, TSNE_ITER, 42, kp, TSNE_PERPLEXITY)
    utf["tsne"] = Y_t
    utf["umap"] = umap_lik(W, V, UMAP_EPOKAR, 42)
    utf["svd"] = svd2(V)
    kv = {}
    for nm, Y in utf.items():
        kv[nm] = tillit_kontinuitet(V, Y)
        lagre_bilete(notat / f"kart-{nm}.png", til_ruta(Y), topp, f"{nm} {kv[nm]}")
        logg(f"utforming {nm}: {kv[nm]}")
    gml = read_json(DOCS_DATA_DIR / "semantic_map.json")
    if gml and gml.get("points"):
        gi = np.asarray([K.id_til_i[p["id"]] for p in gml["points"]])
        Yg = np.asarray([[p["x"], p["y"]] for p in gml["points"]])
        kv["noverande_kart"] = tillit_kontinuitet(vektorar_b(K)[gi], Yg)
        kv["noverande_kart"]["n"] = int(len(gi))
        kv["noverande_kart_mot_vald_kjelde"] = tillit_kontinuitet(V[gi], Yg)
        logg(f"noverande kart: {kv['noverande_kart']}")
    E["utforming"] = kv
    skriv_json(talfil, E, kompakt=False)
    if args.berre == "utforming":
        return 0
    P = til_ruta(utf[UTFORMING])

    # 4. terms, descriptions, names
    termar, X = termar_per_verk(K)
    logg(f"termar: {len(termar)}")
    nk = int(topp.max()) + 1
    tt = klassetermar(termar, X, topp, nk)
    klynger = []
    grunnlag = []
    nokklar = []
    for c in range(nk):
        med = np.flatnonzero(topp == c)
        d = skildre(K, V, med)
        nokklar.append(d.nokkel)
        namn, sjekka = vel_namn(d.nokkel, NAMN_TOPP, tt[c])
        sentral = np.zeros(K.n)
        sentral[med] = d.cos
        lx, ly = etikettpunkt(P, med, sentral, 0.08 * SKALA)
        g = g_topp[med]
        klynger.append({"id": c, "namn": namn, "namn_sjekka": sjekka, "ord": tt[c][:6], "n": int(len(med)),
                        "lx": lx, "ly": ly, "sentrale": d.sentrale, "sentrale60": d.sentrale60,
                        "periode": d.periode, "kanalar": d.kanalar,
                        "land": d.land, "stabilitet": klstab[c],
                        "kjerne": round(float((g >= GRENSE_DEL).mean()), 3),
                        "tittel_berre": int(K.tittel_berre[med].sum()), "nordisk": d.nordisk,
                        "silhuett": round(float(sil_verk[med].mean()), 3), "under": []})
        grunnlag.append((c, None, namn, tt[c], [K.tittel[i] for i in d.sentrale_i], d))
    for c, s in enumerate(fargeplassar(nokklar)):
        klynger[c]["farge"] = s
    under_lst = []
    for c in range(nk):
        med = np.flatnonzero(topp == c)
        u_ids = sorted(set(int(u) for u in under[med]))
        lok = np.full(K.n, -1, dtype=np.int64)
        for q, u in enumerate(u_ids):
            lok[under == u] = q
        ut_ = klassetermar(termar, X, lok, len(u_ids), min_df=2)
        st = under_stat[c]["klynge_stabilitet"]
        for q, u in enumerate(u_ids):
            m2 = np.flatnonzero(under == u)
            d = skildre(K, V, m2)
            namn, sjekka = vel_namn(d.nokkel, NAMN_UNDER, ut_[q])
            sentral = np.zeros(K.n)
            sentral[m2] = d.cos
            lx, ly = etikettpunkt(P, m2, sentral, 0.03 * SKALA)
            under_lst.append({"id": u, "k": c, "namn": namn, "namn_sjekka": sjekka, "ord": ut_[q][:5], "n": int(len(m2)),
                              "lx": lx, "ly": ly, "sentrale": d.sentrale, "sentrale60": d.sentrale60,
                              "periode": d.periode, "kanalar": d.kanalar[:3], "land": d.land[:3],
                              "nordisk": d.nordisk, "stabilitet": st[q] if st else None})
            klynger[c]["under"].append(u)
            grunnlag.append((c, u, namn, ut_[q], [K.tittel[i] for i in d.sentrale_i], d))

    # 5. flags and output
    kjelde_rad = next(r for r in res["alle"] if r["kjelde"] == KJELDE)
    flagg = np.zeros(K.n, dtype=np.int64)
    flagg[g_topp < GRENSE_DEL] |= 1
    flagg[K.tittel_berre] |= 2
    flagg[np.asarray([s in NORDISKE_SPRAK for s in K.sprak])] |= 4
    flagg[np.asarray([s == "e" for s in K.sprak])] |= 8
    tal_ = {
        "verk": K.n, "med_samandrag": int((~K.tittel_berre).sum()), "berre_tittel": int(K.tittel_berre.sum()),
        "abs_o": K.abs.count("o"), "abs_x": K.abs.count("x"),
        "klynger": nk, "underklynger": int(under.max()) + 1,
        "silhuett": mal["silhuett"], "silhuett_null": mal["null_silhuett"],
        "stabilitet_ari": mal["stabilitet"]["snitt"], "stabilitet_ari_min": mal["stabilitet"]["min"],
        "modularitet": mal["modularitet"], "kopling_loft": mal["kopling"]["loft"],
        "kopling_del_inne": mal["kopling"]["del_inne"], "kopling_venta": mal["kopling"]["venta"],
        "kopling_forhold": mal["kopling"]["forhold"],
        "grense_del": mal["grense_del"], "nabo_inne": mal["nabo_inne"],
        "nmi_kanal": mal["nmi_kanal"], "nmi_emne": mal["nmi_emne"], "nmi_sprak": mal["nmi_sprak"],
        "nmi_kanal_null": mal["nmi_kanal_null"], "nmi_emne_null": mal["nmi_emne_null"],
        "under_silhuett": mal_u["silhuett"],
        # over all pairs: contains the top-level effect, so it is not evidence for the sub-clusters on their own
        "under_kopling_loft_alle_par": mal_u["kopling"]["loft"],
        "under_kopling_forhold_alle_par": mal_u["kopling"]["forhold"],
        # only pairs inside the same top cluster: same sub-cluster against other sub-cluster
        "under_kopling_forhold_inne_topp": mal_u["kopling_inne_forelder"]["forhold"],
        "under_kopling_forhold_snitt_per_topp": mal_u["kopling_snitt_per_topp"],
        "utforming": kv[UTFORMING], "utforming_svd": kv["svd"],
        "kjelde_kopling": kjelde_rad["kopling"],
        "kjelde_kopling_tittel_berre": kjelde_rad["kopling_tittel_berre"]["del"],
        "kjelde_kopling_med_samandrag": kjelde_rad["kopling_med_samandrag"]["del"],
        "tittel_berre_homofili": kjelde_rad["tittel_berre_homofili"]["del"],
        "tittel_berre_homofili_basis": kjelde_rad["tittel_berre_homofili"]["basis"],
        "grense_del_tittel_berre": round(float((g_topp[K.tittel_berre] < GRENSE_DEL).mean()), 4),
        "grense_del_med_samandrag": round(float((g_topp[~K.tittel_berre] < GRENSE_DEL).mean()), 4),
        "gammal_kjelde_kopling": next(r["kopling"] for r in res["alle"] if r["kjelde"] == "b"),
    }
    nordisk = np.asarray([c in NORDISKE_SPRAK for c in K.sprak])
    delar = [float(nordisk[topp == c].mean()) for c in range(nk)]
    tal_["nordisk_sprak_klynge"] = int(np.argmax(delar))
    tal_["nordisk_sprak_del"] = round(max(delar), 4)
    tal_["nordisk_sprak_del_alle"] = round(float(nordisk.mean()), 4)
    tal_["nordisk_sprak_del_av_nordiske"] = round(float((topp[nordisk] == tal_["nordisk_sprak_klynge"]).mean()), 4)
    namnetreff = fornamn_sjekk([c["ord"] for c in klynger] + [u["ord"] for u in under_lst])
    logg(f"termar som òg er vanlege førenamn (sjå over): {namnetreff}")
    kart = {
        "versjon": VERSJON,
        "generert": args.generert or now_iso(),
        "kjelde": {"fil": "search/vectors.i8", "modell": K.meta["vectors"]["model"], "dim": K.meta["vectors"]["dim"],
                   "tekst": "tittel og samandrag (berre tittel når samandrag manglar)",
                   "førebuing": "verk med og utan samandrag sentrerte kvar for seg, berre-tittel-vektorane justerte "
                                "til same spreiing (CORAL), normaliserte",
                   "meta_bygd": K.meta.get("built"), "tekst_sha256": K.meta["vectors"].get("text_sha256"),
                   # sha256 of the vectors.i8 bytes the map was built from; tests compare it with meta.json and the file
                   "vektor_sha256": vektor_sha},
        "metode": {
            "naboar": K_NN,
            "graf": "kNN-graf (cosinus) med UMAP-vekter",
            "klynger": f"Louvain, oppløysing {TOPP_METODE[1]}, minste klynge {MIN_TOPP}" if TOPP_METODE[0] == "louvain"
            else f"sfærisk k-means, k={TOPP_METODE[1]}",
            "underklynger": f"Louvain i nabonettet inne i kvar klynge, oppløysing {UNDER_OPPLOYSING:g}, "
                            f"minste underklynge {MIN_UNDER}",
            "utforming": {"tsne": f"t-SNE, perplexity {TSNE_PERPLEXITY:g}, {TSNE_ITER} iterasjonar",
                          "umap": f"UMAP-liknande, {UMAP_EPOKAR} epokar", "svd": "lineær projeksjon (SVD)"}[UTFORMING],
            "grense": f"under {int(GRENSE_DEL * 100)} % av dei {K_NN} næraste naboane i same klynge",
            "frø": SEEDS,
        },
        "tal": tal_,
        "periodar": [p[0] for p in PERIODAR],
        "skala": SKALA,
        "flagg": {"1": "grense", "2": "berre tittel", "4": "nordisk språk", "8": "engelsk"},
        # sentrale60 in klynger and under: row numbers into ids (not ids, to keep the file small)
        "ids": K.ids,
        "x": [int(v) for v in P[:, 0]], "y": [int(v) for v in P[:, 1]],
        "k": [int(v) for v in topp], "u": [int(v) for v in under], "f": [int(v) for v in flagg],
        "klynger": klynger,
        "under": under_lst,
    }
    ut = Path(args.ut)
    b = skriv_json(ut / "kart.json", kart)
    logg(f"kart.json: {b} byte")
    b2 = skriv_json(ut / "om.json", om_tekst(tal_, klynger, kv), kompakt=False)
    logg(f"om.json: {b2} byte")
    skriv_grunnlag(notat / "namnegrunnlag.md", K, grunnlag, klynger, under_lst)
    lagre_bilete(notat / "kart-vald.png", P, topp, "vald", None)
    return 0


def skriv_grunnlag(sti: Path, K: Ns, grunnlag, klynger, under_lst) -> None:
    linjer = ["# Namnegrunnlag (generert av designteori/klynger.py)", "",
              "For kvar klynge: namnet, dei skiljande orda (c-TF-IDF over tittel og samandrag), dei mest sentrale "
              "titlane, kanalar, land og periodeprofil. Underklyngeorda er rekna mot syskena i same klynge.", ""]
    for c, u, namn, ord_, titlar, d in grunnlag:
        if u is None:
            kl = klynger[c]
            linjer.append(f"## {c}. {namn}  (n={kl['n']}, stabilitet {kl['stabilitet']}, kjerne {kl['kjerne']}, "
                          f"berre tittel {kl['tittel_berre']}, sjekka={kl['namn_sjekka']})")
        else:
            ul = under_lst[u]
            linjer.append(f"### {c}.{u} {namn}  (n={ul['n']}, stabilitet {ul['stabilitet']}, sjekka={ul['namn_sjekka']})")
        linjer.append(f"- ord: {', '.join(ord_)}")
        linjer.append(f"- kanalar: {'; '.join(f'{k} ({n})' for k, n in d.kanalar)}")
        linjer.append(f"- land: {', '.join(f'{k} {n}' for k, n in d.land)}  periode: {d.periode}")
        linjer.append(f"- nøkkel (mest sentrale verk): {d.nokkel[0]}")
        for t in titlar:
            linjer.append(f"  - {t}")
        linjer.append("")
    sti.write_text("\n".join(linjer) + "\n", encoding="utf-8")


def om_tekst(t: dict, klynger: list[dict], kv: dict) -> dict:
    u = t["utforming"]
    s = t["utforming_svd"]
    return {
        "versjon": VERSJON,
        "tittel": "Om kartet",
        # the line above the map; says that language, not only theme, shapes the clearest island
        "linje": (f"{tal(t['verk'])} verk, eitt per prikk. Verk med lik ordbruk og like tema ligg nær kvarandre. "
                  f"Språk speler òg inn: {pst(t['nordisk_sprak_del_av_nordiske'])} av verka på nordiske språk ligg i "
                  f"éi klynge. Grensene er mjuke: {pst(t['grense_del'])} av verka ligg mellom klynger."),
        "ingress":(f"Kartet viser alle {tal(t['verk'])} verka i korpuset. Kvar prikk er eitt verk. Verk som handlar om "
                    "det same, ligg nær kvarandre. Fargane er {k} klynger som ein algoritme har funne, og kvar klynge "
                    "er delt i mindre underklynger.").replace("{k}", tal(t["klynger"])),
        "bolkar": [
            {"tittel": "Korleis kartet er laga",
             "tekst": (f"Tittel og samandrag for kvart verk er gjort om til ein talvektor med språkmodellen "
                       f"EmbeddingGemma (256 tal per verk). {tal(t['berre_tittel'])} verk har ikkje samandrag, og for "
                       "dei byggjer vektoren berre på tittelen. Slike vektorar la seg først i ein eigen klump, fordi "
                       "dei er laga på ein annan måte (tittelen står der samandraget elles står) og av ein svært kort "
                       "tekst. Difor er verk med og utan samandrag sentrerte kvar for seg, og vektorane "
                       "for berre-tittel-verka er justerte til same spreiing som dei andre. "
                       f"For kvart verk er dei {K_NN} mest like verka funne, og desse "
                       "naboskapa er lagde ut på flata med t-SNE, ein metode som held på kven som er nabo med kven.")},
            {"tittel": "Kva avstand tyder",
             "tekst": ("Nærleik i kartet tyder at tekstane liknar kvarandre i ordbruk og tema. Store avstandar og "
                       "retningar tyder lite: t-SNE held på dei næraste naboane, ikkje på avstanden mellom fjerne "
                       f"område. I snitt er {pst(u['naboar_behaldne'])} av dei {K_NN} næraste naboane i tekstrommet "
                       f"òg blant dei {K_NN} næraste i kartet (tillit {tal(u['tillit'], 2)}). Ein lineær projeksjon av "
                       f"dei same vektorane, slik det gamle kartet var laga, held på {pst(s['naboar_behaldne'])}.")},
            {"tittel": "Korleis klyngene er funne",
             "tekst": (f"Klyngene er funne i tekstrommet, ikkje i biletet. Dei {tal(t['klynger'])} klyngene kjem frå "
                       f"k-means: kvart verk høyrer til det klyngesenteret det liknar mest. Talet {tal(t['klynger'])} "
                       "er eit val, ikkje noko dataa viser. Av 8 til 16 klynger gav dette talet det mest stabile "
                       "resultatet frå køyring til køyring, og det skilde verka minst like godt som dei andre. Inne i kvar klynge er det funne "
                       "grupper av verk som har mange "
                       "felles naboar "
                       f"(Louvain-metoden), til saman {tal(t['underklynger'])} underklynger. Namna er sette for hand i "
                       "analysen ut frå orda som skil klynga frå resten, dei mest sentrale titlane og eit tilfeldig "
                       "utval titlar. Ingen fagperson har kontrollert dei. Dei er merkelappar, ikkje fagfolk si "
                       "inndeling.")},
            {"tittel": "Kor sikre klyngene er",
             "tekst": (f"Feltet er meir eit samanhengande landskap enn øyar. Silhuetten, eit mål frå -1 til 1 på kor "
                       f"klart verka ligg i eiga klynge, er {tal(t['silhuett'], 2)} (ei tilfeldig sky utan klynger gir "
                       f"{tal(t['silhuett_null'], 2)}). {pst(t['grense_del'])} av verka ligg på ei grense: færre enn "
                       f"halvparten av naboane deira er i same klynge. Køyrer ein metoden ti gonger med ulike startverdiar, "
                       f"er samsvaret i snitt {tal(t['stabilitet_ari'], 2)} (justert Rand-indeks, 1 er likt kvar gong), "
                       f"og {tal(t['stabilitet_ari_min'], 2)} for dei to køyringane som liknar minst. "
                       f"Klynga «{klynger[t['nordisk_sprak_klynge']]['namn']}» er delvis ei språkgruppe: "
                       f"{pst(t['nordisk_sprak_del'])} av verka der er på eit nordisk språk, mot "
                       f"{pst(t['nordisk_sprak_del_alle'])} i heile korpuset, og "
                       f"{pst(t['nordisk_sprak_del_av_nordiske'])} av alle verk på nordiske språk ligg i denne klynga.")},
            {"tittel": "Ein kontroll utanfor teksten",
             "tekst": (f"Klyngene er laga berre av tekst. Likevel deler verk i same klynge oftare referansar: av alle par "
                       f"av verk som siterer minst éitt felles verk, ligg {pst(t['kopling_del_inne'])} i same klynge, mot "
                       f"{pst(t['kopling_venta'])} om klyngene var tilfeldige. Kanal og OpenAlex-emne heng moderat saman "
                       "med klyngene. Målet NMI går frå 0 (ingen samanheng) til 1 (same inndeling). Det er "
                       f"{tal(t['nmi_kanal'], 2)} for kanal og {tal(t['nmi_emne'], 2)} for emne, mot "
                       f"{tal(t['nmi_kanal_null'], 2)} og {tal(t['nmi_emne_null'], 2)} om verka vart fordelte tilfeldig "
                       "på klynger av same storleik.")},
            {"tittel": "Verk med berre tittel",
             "tekst": (f"Dei {tal(t['berre_tittel'])} verka utan samandrag er plasserte og grupperte som dei andre, og "
                       "dei er merkte i kartet. Plasseringa deira er litt mindre sikker: naboane deira deler sjeldnare "
                       f"referansar med dei ({pst(t['kjelde_kopling_tittel_berre'])} mot "
                       f"{pst(t['kjelde_kopling_med_samandrag'])} for verk med samandrag). Dei ligg ikkje oftare på ei "
                       f"grense ({pst(t['grense_del_tittel_berre'])} mot {pst(t['grense_del_med_samandrag'])}). "
                       f"Dei har framleis oftare andre berre-tittel-verk som naboar ({pst(t['tittel_berre_homofili'])} "
                       f"mot {pst(t['tittel_berre_homofili_basis'])} venta), delvis fordi mange av dei kjem frå dei "
                       "nordiske arkiva. Grenseverk er òg merkte.")},
            {"tittel": "Sentrale verk",
             "tekst": ("Dei sentrale verka i ei klynge er dei som liknar mest på snittet av klynga i tekstrommet, "
                       "ikkje dei som ligg midt i biletet. Verk med samandrag kjem først. Ein vektor bygd berre på ein "
                       "kort tittel seier lite og hamnar difor lett nær midten av klynga, så verk med berre tittel kjem "
                       "med berre når det er for få andre. Lenkja til katalogen opnar dei 60 første i same rekkjefølgje.")},
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
