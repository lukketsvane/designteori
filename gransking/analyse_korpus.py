"""Empirisk og statistisk metavitskapleg gransking av nordisk designteori og designforsking (1900-2026).

Etterprøver 10 vitskapsteoretiske påstandar (P1-P10) på det verifiserte nordiske
designteori-korpuset (N = 6 454 verk i NO, SE, DK, FI, IS), siteringsgrafen i OpenAlex,
256-dimensjonale Google EmbeddingGemma-300M-vektorar, eksterne siteringsdata frå OpenAlex
og side-for-side fulltekst frå alle verifiserte Open Access-PDF-ar i korpuset.
"""
from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from designteori import (
    DOCS_DATA_DIR,
    PDF_DIR,
    PRIVATE_CACHE,
    PRIVATE_CORPUS_DB,
    RAW_SQLITE,
    USER_AGENT,
    normalize_title,
)
from designteori.eligibility import DEDICATED_VENUE_NAMES_RE, PURE_DESIGN_VENUES

OUT_DIR = Path(__file__).resolve().parent
DATA_DIR = OUT_DIR / "data"
FIG_DIR = OUT_DIR / "figurar"
RNG = np.random.default_rng(20261107)


# ---------------------------------------------------------------------------
# Eksakte statistiske hjelpefunksjonar (utan skjøre tredjepartsavhengnader)
# ---------------------------------------------------------------------------

def norm_sf(z: float) -> float:
    """To-sidig p-verdi frå standardnormalfordelinga."""
    return math.erfc(abs(float(z)) / math.sqrt(2.0))


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float, float]:
    """ Punktanslag og 95 % Wilson-konfidensintervall for binomisk del."""
    if n <= 0:
        return 0.0, 0.0, 0.0
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def bootstrap_mean_ci(arr: np.ndarray, B: int = 2000) -> tuple[float, float, float]:
    x = np.asarray(arr, dtype=np.float64)
    if x.size == 0:
        return 0.0, 0.0, 0.0
    pt = float(np.mean(x))
    if x.size == 1:
        return pt, pt, pt
    idx = RNG.integers(0, x.size, size=(B, x.size))
    means = np.mean(x[idx], axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return pt, float(lo), float(hi)


def bootstrap_median_ci(arr: np.ndarray, B: int = 2000) -> tuple[float, float, float]:
    x = np.asarray(arr, dtype=np.float64)
    if x.size == 0:
        return 0.0, 0.0, 0.0
    pt = float(np.median(x))
    if x.size == 1:
        return pt, pt, pt
    idx = RNG.integers(0, x.size, size=(B, x.size))
    meds = np.median(x[idx], axis=1)
    lo, hi = np.percentile(meds, [2.5, 97.5])
    return pt, float(lo), float(hi)


def mann_whitney_u(x: np.ndarray, y: np.ndarray) -> dict:
    """Mann-Whitney U-test med korreksjon for bundne rangar og rang-biserial effektstorleik."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n1, n2 = x.size, y.size
    if n1 == 0 or n2 == 0:
        return {"U": 0.0, "z": 0.0, "p": 1.0, "rank_biserial": 0.0}
    all_v = np.concatenate([x, y])
    n = n1 + n2
    order = np.argsort(all_v, kind="mergesort")
    ranks = np.empty(n, dtype=np.float64)
    tie_sum = 0.0
    i = 0
    while i < n:
        j = i
        while j + 1 < n and all_v[order[j + 1]] == all_v[order[i]]:
            j += 1
        avg_rank = 0.5 * (i + j) + 1.0
        ranks[order[i:j + 1]] = avg_rank
        t = j - i + 1
        if t > 1:
            tie_sum += t ** 3 - t
        i = j + 1
    r1 = float(np.sum(ranks[:n1]))
    u1 = r1 - n1 * (n1 + 1) / 2.0
    mu = n1 * n2 / 2.0
    var = (n1 * n2 / 12.0) * ((n + 1.0) - tie_sum / (n * (n - 1.0))) if n > 1 else 0.0
    z = (u1 - mu) / math.sqrt(max(var, 1e-12))
    p = norm_sf(z)
    # Wendt / Cureton rank-biserial correlation: +1 tyder x > y, -1 tyder x < y
    r_rb = (2.0 * u1) / (n1 * n2) - 1.0
    return {"U": round(u1, 2), "z": round(z, 4), "p": p, "rank_biserial": round(r_rb, 4)}


def chi2_2x2(a: int, b: int, c: int, d: int) -> dict:
    """2x2 kontingenstabell: kjikvadrat (Yates), oddsrate med 95 % KI og Cramers V."""
    n = a + b + c + d
    if n == 0:
        return {"chi2": 0.0, "p": 1.0, "cramers_v": 0.0, "or": 1.0, "or_ci": [1.0, 1.0]}
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d
    denom = r1 * r2 * c1 * c2
    if denom == 0:
        chi2 = 0.0
        p = 1.0
        v = 0.0
    else:
        diff = max(0.0, abs(a * d - b * c) - 0.5 * n)
        chi2 = (n * diff * diff) / denom
        # df = 1 => chi2 = z^2
        p = norm_sf(math.sqrt(chi2))
        v = math.sqrt(((n * (a * d - b * c) ** 2) / denom) / n)
    # Haldane-Anscombe-korreksjon ved nullceller for stabil oddsrate
    aa, bb, cc, dd = (a + 0.5, b + 0.5, c + 0.5, d + 0.5) if min(a, b, c, d) == 0 else (float(a), float(b), float(c), float(d))
    odds_ratio = (aa * dd) / (bb * cc)
    se_log_or = math.sqrt(1.0 / aa + 1.0 / bb + 1.0 / cc + 1.0 / dd)
    lo_or = math.exp(math.log(odds_ratio) - 1.959964 * se_log_or)
    hi_or = math.exp(math.log(odds_ratio) + 1.959964 * se_log_or)
    return {
        "chi2": round(chi2, 4),
        "p": p,
        "cramers_v": round(v, 4),
        "odds_ratio": round(odds_ratio, 4),
        "odds_ratio_ci95": [round(lo_or, 4), round(hi_or, 4)],
    }


def gini_coefficient(values: list[int] | np.ndarray) -> float:
    x = np.sort(np.asarray(values, dtype=np.float64))
    if x.size == 0 or np.sum(x) <= 0:
        return 0.0
    n = x.size
    idx = np.arange(1, n + 1, dtype=np.float64)
    return float((2.0 * np.sum(idx * x)) / (n * np.sum(x)) - (n + 1.0) / n)


# ---------------------------------------------------------------------------
# Tekstseparasjon (skil hovudtekst frå referanseliste bak i PDF-dokument)
# ---------------------------------------------------------------------------

REF_HEADER_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+\.?\s*)?(?:references|bibliography|works cited|referanser|referansar|litteratur|litteraturliste|källförteckning|kilder|lähteet)\s*(?:\n|$)",
    re.I,
)


def split_body_and_references(pages: list[str]) -> tuple[str, str, str]:
    """Returnerer (full_text, body_without_bibliography, front_back_meta_text)."""
    if not pages:
        return "", "", ""
    full = "\n\n".join(pages)
    n_pages = len(pages)
    # Front/back-metadata (fyrste 2 sider + siste 3 sider) fangar finansiering, takksemd og etikknotisar
    fb_pages = pages[:min(2, n_pages)] + (pages[max(2, n_pages - 3):] if n_pages > 2 else [])
    fb_text = "\n\n".join(fb_pages)

    # Finn siste referanseoverskrift i bakre 45 % av dokumentet slik at referansetitlar ikkje forureinar metodeteljingar
    cutoff_char = int(len(full) * 0.55)
    tail = full[cutoff_char:]
    matches = list(REF_HEADER_RE.finditer(tail))
    if matches:
        # Bruk fyrste tydelege referanseoverskrift i bakre del (før evt. vedlegg)
        split_pos = cutoff_char + matches[0].start()
        body = full[:split_pos]
    else:
        body = full
    return full, body, fb_text


# ---------------------------------------------------------------------------
# Leksikalske og metodiske indikatorar (kalibrerte for minimal falsk positiv)
# ---------------------------------------------------------------------------

# P1: Revisjonsmekanismar / falsifikasjon av eldre funn i brødtekst
REVISION_RE = re.compile(
    r"\b(?:contrary to (?:previous|prior|earlier) (?:findings|studies|research|work)|"
    r"refut(?:e|es|ed|ing) (?:the|prior|previous)|falsif(?:y|ies|ied) (?:the|our)|"
    r"disprov(?:e|es|ed)|invalidat(?:e|es|ed) (?:the|previous)|corrigendum|erratum|retraction|"
    r"motbevis\w*|avkreft\w* (?:tidlegare|tidligere|hypotes\w*)|tilbakevis\w*)\b",
    re.I,
)

# P2: Eksplisitte replikasjonsstudiar vs nyord/rammeverkslansering
REPLICATION_TITLE_ABS_RE = re.compile(
    r"\b(?:replication study|replication of|direct replication|conceptual replication|"
    r"reproducibility study|reproducing|etterprøving av|replikasjon\w*)\b",
    re.I,
)
REPLICATION_BODY_RE = re.compile(
    r"\b(?:direct replication|conceptual replication|replication study|we replicate[d]? (?:the study|the experiment|prior)|"
    r"reproduc(?:e|ed|ing) the results of|replikasjonsstudie|etterprøvde funna)\b",
    re.I,
)
NOVELTY_FRAMING_RE = re.compile(
    r"\b(?:towards? a(?:n| new)?|introducing a|proposing a|a novel|new framework|novel framework|"
    r"exploring|reimagining|rethinking|unpacking|framing|lens(?:es)? for)\b",
    re.I,
)

# P3: Presise, falsifiserbare hypotesar og inferensstatistikk vs open fortolkingsprosa
FORMAL_HYPOTHESIS_RE = re.compile(
    r"(?:\bH[01234a-c]\s*:\s+[A-ZÆØÅÄÖ]|\bnull hypothesis\b|\balternative hypothesis\b|"
    r"\bwe (?:formally )?hypothesi[sz]e(?:d)? that\b|\btestable prediction\w*\b|"
    r"\bfalsifiable (?:hypothesis|hypotheses|prediction)\b|\bnullhypotese\w*\b)",
    re.I,
)
INFERENTIAL_STATS_RE = re.compile(
    r"(?:\bp\s*[<=>]\s*0?\.\d+|\bt\s*\(\s*\d+\s*\)\s*=|\bF\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=|"
    r"\bchi-square\b|\bχ2\b|\bANOVA\b|\bANCOVA\b|\bMann[–-]Whitney\b|\bWilcoxon\b|"
    r"\bregression (?:model|analysis)\b|\blogistic regression\b|\b95%\s*(?:confidence interval|CI)\b|"
    r"\bCohen'?s\s+d\b|\bbonferroni\b)",
    re.I,
)
PREREGISTRATION_RE = re.compile(
    r"\b(?:pre-?registered|preregistration|aspredicted\.org|osf\.io/[a-z0-9]{4,})\b",
    re.I,
)
INTERPRETIVE_OPEN_RE = re.compile(
    r"\b(?:opens? up (?:space|possibilities|questions|new ways)|invites? reflection|"
    r"provok(?:es?|ing) (?:thought|discussion|questions)|sensitizing concept\w*|"
    r"rich insights|illustrative example\w*|sheds? light on|kan belyse|opnar for refleksjon)\b",
    re.I,
)

# P5: Prosessrettferdiggjering vs etterprøvbar effekt- og negativ-utfalls-rapportering
PROCESS_METHOD_RE = re.compile(
    r"\b(?:workshop\w*|co-design session\w*|co-creation session\w*|cultural probe\w*|"
    r"design probe\w*|prototyping process|reflection-in-action|research through design|"
    r"design intervention\w*|brainstorming|ideation session\w*|sense-making|living lab\w*)\b",
    re.I,
)
CONTROLLED_EFFECT_RE = re.compile(
    r"\b(?:control group|comparison group|waitlist control|counterfactual|pre-test and post-test|"
    r"pre-post|baseline measurement|controlled experiment|quasi-experimental|"
    r"treatment effect|causal effect|kontrollgruppe|før- og etter-?måling)\b",
    re.I,
)
NEGATIVE_OUTCOME_RE = re.compile(
    r"\b(?:hypothesis was (?:not supported|rejected)|hypotheses were (?:not supported|rejected)|"
    r"no statistically significant (?:difference|effect|improvement)|null (?:result|effect|finding)s?|"
    r"failed to (?:improve|increase|reduce|show|demonstrate)|negative (?:impact|effect|consequence|outcome)s? on (?:users|participants|citizens)|"
    r"intervention failed|ingen signifikant effekt|hypotesen vart forkasta)\b",
    re.I,
)

# P6: Ekstern oppdrags-/prosjektfinansiering og forutgåande organisatorisk/økonomisk mandat
COMMISSIONED_FUNDING_RE = re.compile(
    r"\b(?:funded by|financed by|supported by grant|commissioned by|in collaboration with (?:the )?(?:municipality|industry|company|public)|"
    r"vinnova|forskningsrådet|research council of norway|innovation fund denmark|innovationsfonden|"
    r"business finland|tekes|nordforsk|horizon 2020|horizon europe|interreg|støtta av|finansiert av)\b",
    re.I,
)
PREDECIDED_MANDATE_RE = re.compile(
    r"\b(?:strategic initiative|digital transformation|digitali[sz]ation|green transition|"
    r"sustainability transition|public sector|municipality|municipal|industry partner\w*|"
    r"case company|partner organization\w*|organizational change|service transformation|"
    r"procurement|policy implementation|smart city|national strategy|innovation project|"
    r"kommune\w*|offentleg sektor|offentlig sektor|omstilling)\b",
    re.I,
)
MANDATE_CHALLENGE_RE = re.compile(
    r"\b(?:halted the project|cancelled the implementation|abandoned the strategy|"
    r"recommended against (?:adopting|implementing|continuing)|terminated the procurement|"
    r"frårådde å gjennomføre|stansa innføringa)\b",
    re.I,
)

# P9: Menneskelege deltakarar vs handheva forskingsetisk godkjenning, interessekonflikt og etteransvar
HUMAN_SUBJECTS_RE = re.compile(
    r"\b(?:interview(?:s|ed|ees)|workshop(?:s)? with|participants|informants|focus group\w*|"
    r"co-design(?:ing)? with (?:users|citizens|children|patients|older adults|elderly|youth|stakeholders)|"
    r"fieldwork with|ethnographic observation|deltakarar|informantar|intervju med)\b",
    re.I,
)
VULNERABLE_GROUPS_RE = re.compile(
    r"\b(?:children|minors|adolescents|elderly|older adults|dementia|disability|disabilities|"
    r"refugees|migrants|marginalized|vulnerable|mental health|barn|unge|eldre|sårbare)\b",
    re.I,
)
ETHICS_BOARD_RE = re.compile(
    r"\b(?:institutional review board|\bIRB\b|ethics committee|research ethics board|"
    r"ethical approval|ethics approval|etikprövningsmyndigheten|etikprövningsnämnden|"
    r"regional committees? for medical and health research ethics|\bREK\b|\bNSD\b|\bSIKT\b|"
    r"norwegian centre for research data|finnish national board on research integrity|\bTENK\b|"
    r"science ethics committee|etisk komit[eé]|godkjend av (?:sikt|nsd|rek))\b",
    re.I,
)
INFORMED_CONSENT_RE = re.compile(
    r"\b(?:informed consent|written consent|verbal consent|consent form|informert samtykke|samtykkeskjema)\b",
    re.I,
)
COI_STATEMENT_RE = re.compile(
    r"\b(?:conflict(?:s)? of interest|competing interest(?:s)?|no potential conflict of interest|declaration of interest|interessekonflikt\w*)\b",
    re.I,
)
POST_PROJECT_ACCOUNTABILITY_RE = re.compile(
    r"\b(?:after the project ended|post-project follow-up|long-term follow-up|exit strategy|"
    r"after researchers? left|longitudinal follow-up after|\b12-month follow-up\b|\b6-month follow-up\b|"
    r"unintended harm\w*|etter at prosjektet var avslutta)\b",
    re.I,
)

# P10: Validerte målereiskapar, psykometrisk reliabilitet og opne data/kode
VALIDATED_INSTRUMENT_RE = re.compile(
    r"\b(?:system usability scale|\bSUS\b score|NASA-TLX|AttrakDiff|User Experience Questionnaire|\bUEQ\b|"
    r"\bPANAS\b|Likert-type scale validated|validated (?:questionnaire|scale|instrument|measure)|"
    r"standardized (?:instrument|questionnaire|scale|test))\b",
    re.I,
)
PSYCHOMETRIC_RELIABILITY_RE = re.compile(
    r"\b(?:Cronbach'?s\s*(?:alpha|α)|inter-?rater reliability|Cohen'?s\s*kappa|"
    r"Krippendorff'?s\s*alpha|intraclass correlation|\bICC\b|construct validity|"
    r"convergent validity|discriminant validity|confirmatory factor analysis|\bCFA\b|"
    r"exploratory factor analysis|\bEFA\b|internal consistency)\b",
    re.I,
)
OPEN_DATA_CODE_RE = re.compile(
    r"\b(?:data availability statement|data are openly available|code availability|"
    r"zenodo\.org/record|figshare\.com|osf\.io/|dataverse|github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|"
    r"replication package)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Ekstern siteringsimport/-eksport via OpenAlex (P4) med lokal mellomlagring
# ---------------------------------------------------------------------------

DESIGN_ENCLAVE_KEYWORDS = (
    "design", "formakademisk", "codesign", "co-design", "nordes", "she ji", "artifact",
    "human-computer", "interacting with computers", "interaction", "chi ", "cscw",
    "ergonomics", "craft", "architecture", "fashion", "textile",
)


def compute_cross_disciplinary_matrix(oa_ids: set[str]) -> dict:
    """Måler eksakt kryssdisiplinær import og eksport i heile RAW_SQLITE-grafen (24 812 verk, >650 000 siteringskantar)."""
    conn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
    work_field: dict[str, tuple[int, str, str]] = {}
    for wid, inc, rj in conn.execute("SELECT id, in_scope, raw_json FROM works"):
        fld, sub = "Uklassifisert", "Uklassifisert"
        if rj and rj != "{}":
            try:
                pt = (json.loads(rj).get("primary_topic") or {})
                fld = (pt.get("field") or {}).get("display_name") or "Uklassifisert"
                sub = (pt.get("subfield") or {}).get("display_name") or "Uklassifisert"
            except Exception:
                pass
        work_field[wid] = (int(inc or 0), fld, sub)

    non_design_ids = {w for w, v in work_field.items() if v[0] == 0}
    non_design_total_out_refs = 0
    design_to_design = 0
    design_to_ext_db: Counter[str] = Counter()
    ext_db_to_design_field: Counter[str] = Counter()
    ext_db_to_design_subfield: Counter[str] = Counter()

    for citing, cited in conn.execute("SELECT citing_id, cited_id FROM references_all WHERE citing_id != cited_id"):
        c_des = citing in oa_ids
        d_des = cited in oa_ids
        if citing in non_design_ids:
            non_design_total_out_refs += 1
        if c_des and d_des:
            design_to_design += 1
        elif c_des and cited in non_design_ids:
            design_to_ext_db[work_field[cited][1]] += 1
        elif citing in non_design_ids and d_des:
            ext_db_to_design_field[work_field[citing][1]] += 1
            ext_db_to_design_subfield[work_field[citing][2]] += 1
    conn.close()

    total_incoming = design_to_design + sum(ext_db_to_design_field.values())
    enclave_and_hci_mgmt = (
        design_to_design
        + ext_db_to_design_subfield.get("Human-Computer Interaction", 0)
        + ext_db_to_design_subfield.get("Management of Technology and Innovation", 0)
        + ext_db_to_design_subfield.get("Marketing", 0)
        + ext_db_to_design_subfield.get("Visual Arts and Performing Arts", 0)
    )
    basic_sciences_incoming = sum(
        ext_db_to_design_field.get(f, 0)
        for f in (
            "Physics and Astronomy", "Chemistry", "Mathematics", "Neuroscience",
            "Biochemistry, Genetics and Molecular Biology", "Immunology and Microbiology",
            "Earth and Planetary Sciences", "Economics, Econometrics and Finance",
            "Psychology", "Medicine",
        )
    )
    return {
        "non_design_works_in_db": len(non_design_ids),
        "non_design_total_outgoing_refs": non_design_total_out_refs,
        "design_to_design_citations": design_to_design,
        "external_db_to_design_citations": sum(ext_db_to_design_field.values()),
        "external_uptake_rate_of_non_design_refs": round(sum(ext_db_to_design_field.values()) / max(1, non_design_total_out_refs), 5),
        "total_observed_incoming_citations": total_incoming,
        "enclave_hci_innovation_retention_k": enclave_and_hci_mgmt,
        "enclave_hci_innovation_retention_share": round(enclave_and_hci_mgmt / max(1, total_incoming), 4),
        "basic_and_empirical_sciences_incoming_k": basic_sciences_incoming,
        "basic_and_empirical_sciences_share": round(basic_sciences_incoming / max(1, total_incoming), 4),
        "export_by_field": dict(ext_db_to_design_field.most_common(12)),
        "export_by_subfield": dict(ext_db_to_design_subfield.most_common(12)),
        "import_by_field_in_db": dict(design_to_ext_db.most_common(10)),
    }


# ---------------------------------------------------------------------------
# Nettverks- og nullmodellanalyse (P1, P2, P7, P8)
# ---------------------------------------------------------------------------

def dag_longest_depths(nodes: list[str], edges: list[tuple[str, str]], years: dict[str, int]) -> dict[str, int]:
    """Reknar lengste siteringskjede (tropisk djupn) i den tidskonsistente siteringsgrafen."""
    adj: dict[str, list[str]] = defaultdict(list)
    for u, v in edges:
        if u != v and years.get(u, 0) >= years.get(v, 0) > 0:
            adj[u].append(v)
    memo: dict[str, int] = {}
    visiting: set[str] = set()

    def dfs(u: str) -> int:
        if u in memo:
            return memo[u]
        if u in visiting:
            return 0
        visiting.add(u)
        best = 0
        for v in adj.get(u, ()):
            best = max(best, 1 + dfs(v))
        visiting.remove(u)
        memo[u] = best
        return best

    for n in nodes:
        dfs(n)
    return memo


def null_model_reciprocity_and_depth(
    nodes: list[str],
    edges: list[tuple[str, str]],
    years: dict[str, int],
    n_perm: int = 300,
) -> dict:
    """Gradbevarande konfigurasjons-nullmodell for gjensidig sitering og kjededjupn."""
    if not edges:
        return {"null_reciprocity_mean": 0.0, "null_depth_ge3_mean": 0.0}
    src_arr = np.array([u for u, _ in edges], dtype=object)
    dst_arr = np.array([v for _, v in edges], dtype=object)
    recip_rates = []
    depth3_rates = []
    for _ in range(n_perm):
        perm_dst = RNG.permutation(dst_arr)
        edge_set = {(u, v) for u, v in zip(src_arr, perm_dst) if u != v}
        recips = sum(1 for (u, v) in edge_set if (v, u) in edge_set)
        recip_rates.append(recips / max(1, len(edge_set)))
        depths = dag_longest_depths(nodes, list(edge_set), years)
        depth3_rates.append(sum(1 for d in depths.values() if d >= 3) / max(1, len(nodes)))
    return {
        "null_reciprocity_mean": float(np.mean(recip_rates)),
        "null_reciprocity_sd": float(np.std(recip_rates) + 1e-12),
        "null_depth_ge3_mean": float(np.mean(depth3_rates)),
        "null_depth_ge3_sd": float(np.std(depth3_rates) + 1e-12),
    }


# ---------------------------------------------------------------------------
# Hovudkøyring for alle 10 påstandar
# ---------------------------------------------------------------------------

def run_all() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    pubs = json.loads((DOCS_DATA_DIR / "publications.json").read_text(encoding="utf-8"))
    nordic = json.loads((DOCS_DATA_DIR / "nordic_additions.json").read_text(encoding="utf-8"))
    canon = json.loads((DOCS_DATA_DIR / "cited_canon.json").read_text(encoding="utf-8"))["items"]
    all_works = pubs + nordic
    by_id = {w["id"]: w for w in all_works}
    oa_ids = {w["id"] for w in pubs}

    print(f"[1/6] Lasta korpus: {len(pubs)} OpenAlex + {len(nordic)} nordiske arkiv = {len(all_works)} verk.", flush=True)

    # Hent rå-SQLite (referansar, abstrakt, source_id, forfattarskap, topics)
    rconn = sqlite3.connect(f"file:{RAW_SQLITE.as_posix()}?mode=ro", uri=True)
    raw_meta = {}
    for wid, abstract, sid, sname, topic, rj in rconn.execute(
        "SELECT id, abstract, source_id, source, topic, raw_json FROM works WHERE in_scope=1"
    ):
        subfield, field = "", ""
        if rj and rj != "{}":
            try:
                pt = (json.loads(rj).get("primary_topic") or {})
                subfield = (pt.get("subfield") or {}).get("display_name") or ""
                field = (pt.get("field") or {}).get("display_name") or ""
            except Exception:
                pass
        raw_meta[wid] = {
            "abstract": abstract or "",
            "source_id": (sid or "").rsplit("/", 1)[-1],
            "source": sname or "",
            "topic": topic or "",
            "subfield": subfield,
            "field": field,
        }

    # Alle utgåande referansar frå dei 4 709 reine designteori-verka
    out_refs_all: list[tuple[str, str]] = []
    internal_edges: list[tuple[str, str]] = []
    cited_freq_all: Counter[str] = Counter()
    out_deg_all: Counter[str] = Counter()
    in_deg_internal: Counter[str] = Counter()
    out_deg_internal: Counter[str] = Counter()

    for citing, cited in rconn.execute(
        "SELECT r.citing_id, r.cited_id FROM references_all r WHERE r.citing_id != r.cited_id"
    ):
        if citing not in oa_ids:
            continue
        out_refs_all.append((citing, cited))
        cited_freq_all[cited] += 1
        out_deg_all[citing] += 1
        if cited in oa_ids:
            internal_edges.append((citing, cited))
            out_deg_internal[citing] += 1
            in_deg_internal[cited] += 1

    # Forfattar- og institusjonskoplingar for sjølvsiterings- og endogamianalyse (P7, P8)
    work_authors: dict[str, set[str]] = defaultdict(set)
    work_author_names: dict[str, list[str]] = defaultdict(list)
    work_insts: dict[str, set[str]] = defaultdict(set)
    for wid, aid, aname, iid in rconn.execute(
        "SELECT work_id, author_id, author_name, institution_id FROM authorships"
    ):
        if wid not in oa_ids:
            continue
        if aid:
            work_authors[wid].add(aid)
        elif aname:
            work_authors[wid].add("name:" + normalize_title(aname))
        if aname and aname not in work_author_names[wid]:
            work_author_names[wid].append(aname)
        if iid:
            work_insts[wid].add(iid)
    rconn.close()

    # Last 256-d Google EmbeddingGemma-300M vektorar
    vconn = sqlite3.connect(f"file:{(PRIVATE_CACHE / 'work_vector_cache.sqlite').as_posix()}?mode=ro", uri=True)
    vecs_256: dict[str, np.ndarray] = {}
    for wid, blob in vconn.execute("SELECT work_id, vector FROM work_vectors"):
        if wid in by_id and len(blob) == 256 * 4:
            v = np.frombuffer(blob, dtype="<f4").astype(np.float32)
            nrm = float(np.linalg.norm(v))
            if nrm > 1e-9:
                vecs_256[wid] = v / nrm
    vconn.close()
    print(f"[2/6] Lasta {len(out_refs_all)} utgåande referansar, {len(internal_edges)} interne siteringar og {len(vecs_256)} 256-d vektorar.", flush=True)

    # Last alle fulltekst-PDF-sider for reine designteori-verk
    ft_records: list[dict] = []
    if PRIVATE_CORPUS_DB.is_file():
        cdb = sqlite3.connect(f"file:{PRIVATE_CORPUS_DB.as_posix()}?mode=ro", uri=True)
        sha_to_wids: dict[str, list[str]] = defaultdict(list)
        for wid, sha in cdb.execute("SELECT work_id, sha256 FROM work_documents"):
            if wid in by_id and sha:
                sha_to_wids[sha].append(wid)
        valid_shas = sorted(sha_to_wids.keys())
        for sha in valid_shas:
            doc_row = cdb.execute(
                "SELECT pages, char_count, quality FROM documents WHERE sha256=?", (sha,)
            ).fetchone()
            if not doc_row or doc_row[2] != "extracted" or doc_row[1] < 1500:
                continue
            pg_rows = [r[0] for r in cdb.execute("SELECT text FROM pages WHERE sha256=? ORDER BY page", (sha,))]
            if not pg_rows:
                continue
            wid = sorted(sha_to_wids[sha])[0]
            w = by_id[wid]
            full_txt, body_txt, fb_txt = split_body_and_references(pg_rows)
            venue_str = f"{w.get('source') or ''} {w.get('venue') or ''}"
            sid = raw_meta.get(wid, {}).get("source_id", "")
            is_flagship = (sid in PURE_DESIGN_VENUES) or bool(DEDICATED_VENUE_NAMES_RE.search(venue_str)) or ("nordes" in venue_str.lower())
            is_journal_article = (w.get("kind") == "article")
            ft_records.append({
                "id": wid,
                "sha256": sha,
                "year": w.get("year") or 0,
                "kind": w.get("kind") or "unknown",
                "source": venue_str.strip(),
                "title": w.get("title") or "",
                "is_flagship": is_flagship,
                "is_journal_article": is_journal_article,
                "pages": len(pg_rows),
                "chars": int(doc_row[1]),
                "body": body_txt,
                "full": full_txt,
                "fb": fb_txt,
            })
        cdb.close()
    N_ft = len(ft_records)
    ft_flagship = [r for r in ft_records if r["is_flagship"]]
    ft_journal = [r for r in ft_records if r["is_journal_article"]]
    total_ft_pages = sum(r["pages"] for r in ft_records)
    total_ft_words = sum(len(r["full"].split()) for r in ft_records)
    print(f"[3/6] Lasta {N_ft} komplette fulltekst-PDF-ar ({total_ft_pages} sider, {total_ft_words} ord).", flush=True)

    # -----------------------------------------------------------------------
    # P1: Samordna forskingsprogram, felles kjerneproblem og revisjonsmekanismar
    # -----------------------------------------------------------------------
    total_unique_cited = len(cited_freq_all)
    singleton_cited = sum(1 for _, cnt in cited_freq_all.items() if cnt == 1)
    singleton_share, sing_lo, sing_hi = wilson_ci(singleton_cited, total_unique_cited)
    cited_ge10 = sum(1 for _, cnt in cited_freq_all.items() if cnt >= 10)

    # Maksimal kanondel blant verk som har registrerte referansar i OpenAlex
    works_with_refs = sum(1 for w in pubs if out_deg_all[w["id"]] > 0)
    top_canon_citations = canon[0]["nordic_citing_count"] if canon else 0
    max_canon_share_all, mc_lo, mc_hi = wilson_ci(top_canon_citations, len(pubs))
    max_canon_share_ref, mcr_lo, mcr_hi = wilson_ci(top_canon_citations, works_with_refs)

    # Herfindahl-Hirschman-indeks og normalisert Shannon-entropi på siterte referansar
    ref_probs = np.array(list(cited_freq_all.values()), dtype=np.float64)
    ref_probs = ref_probs / np.sum(ref_probs)
    ref_hhi = float(np.sum(ref_probs ** 2))
    ref_entropy_norm = float(-np.sum(ref_probs * np.log(ref_probs)) / math.log(max(2, len(ref_probs))))

    # Intern graf-isolasjon blant OpenAlex-verk
    isolated_internal = sum(1 for w in pubs if in_deg_internal[w["id"]] == 0 and out_deg_internal[w["id"]] == 0)
    iso_p, iso_lo, iso_hi = wilson_ci(isolated_internal, len(pubs))

    # Semantisk spreiing og terminologisk utskifting mellom tiår (1990s -> 2000s -> 2010s -> 2020s)
    decade_vecs: dict[str, list[np.ndarray]] = defaultdict(list)
    decade_terms: dict[str, Counter] = defaultdict(Counter)
    word_tok_re = re.compile(r"[a-zæøåäöü]{5,}")
    stop_t = {"design", "designing", "research", "study", "studies", "through", "towards", "toward", "using", "based", "approach", "approaches", "paper", "exploring", "understanding", "making", "practice", "practices", "process", "processes", "nordic", "scandinavian", "swedish", "danish", "finnish", "norwegian"}
    for w in all_works:
        y = w.get("year")
        if isinstance(y, int) and 1990 <= y <= 2026:
            dk = f"{(y // 10) * 10}s"
            if w["id"] in vecs_256:
                decade_vecs[dk].append(vecs_256[w["id"]])
            for tk in set(word_tok_re.findall((w.get("title") or "").lower())):
                if tk not in stop_t:
                    decade_terms[dk][tk] += 1

    decade_dispersion = {}
    for dk in ("1990s", "2000s", "2010s", "2020s"):
        if decade_vecs[dk]:
            mat = np.vstack(decade_vecs[dk])
            mean_v = np.mean(mat, axis=0)
            spherical_var = float(1.0 - np.linalg.norm(mean_v))
            decade_dispersion[dk] = {"n": int(mat.shape[0]), "spherical_variance": round(spherical_var, 4)}

    jaccard_1990_2020 = 0.0
    jacc_pairs = {}
    decs_list = ["1990s", "2000s", "2010s", "2020s"]
    for d1, d2 in zip(decs_list[:-1], decs_list[1:]):
        s1 = {w for w, _ in decade_terms[d1].most_common(50)}
        s2 = {w for w, _ in decade_terms[d2].most_common(50)}
        jacc_pairs[f"{d1}_{d2}"] = round(len(s1 & s2) / max(1, len(s1 | s2)), 4)
    s90 = {w for w, _ in decade_terms["1990s"].most_common(50)}
    s20 = {w for w, _ in decade_terms["2020s"].most_common(50)}
    jaccard_1990_2020 = round(len(s90 & s20) / max(1, len(s90 | s20)), 4)

    # Revisjons-/avkreftingsmarkørar i brødtekst
    rev_hits = [1 if REVISION_RE.search(r["body"]) else 0 for r in ft_records]
    rev_k = sum(rev_hits)
    rev_p, rev_lo, rev_hi = wilson_ci(rev_k, N_ft)
    rev_flag_k = sum(1 for r in ft_flagship if REVISION_RE.search(r["body"]))
    rev_flag_p, _, _ = wilson_ci(rev_flag_k, len(ft_flagship))

    p1_stats = {
        "unique_cited_works": total_unique_cited,
        "singleton_cited_works": singleton_cited,
        "singleton_cited_share": round(singleton_share, 4),
        "singleton_cited_ci95": [round(sing_lo, 4), round(sing_hi, 4)],
        "cited_ge10_share": round(cited_ge10 / max(1, total_unique_cited), 4),
        "reference_hhi": round(ref_hhi, 6),
        "reference_shannon_norm": round(ref_entropy_norm, 4),
        "top_canon_work": canon[0]["title"] if canon else "",
        "max_canon_share_all_oa": round(max_canon_share_all, 4),
        "max_canon_share_all_ci95": [round(mc_lo, 4), round(mc_hi, 4)],
        "max_canon_share_among_referencing": round(max_canon_share_ref, 4),
        "max_canon_share_ref_ci95": [round(mcr_lo, 4), round(mcr_hi, 4)],
        "internally_isolated_oa_share": round(iso_p, 4),
        "internally_isolated_ci95": [round(iso_lo, 4), round(iso_hi, 4)],
        "decade_spherical_dispersion": decade_dispersion,
        "top50_term_jaccard_adjacent": jacc_pairs,
        "top50_term_jaccard_1990s_vs_2020s": jaccard_1990_2020,
        "fulltext_revision_markers_k": rev_k,
        "fulltext_revision_markers_n": N_ft,
        "fulltext_revision_share": round(rev_p, 4),
        "fulltext_revision_ci95": [round(rev_lo, 4), round(rev_hi, 4)],
        "flagship_revision_share": round(rev_flag_p, 4),
    }

    # -----------------------------------------------------------------------
    # P2: Ikkje-kumulativitet, fravær av replikasjon og «semantisk amnesi»
    # -----------------------------------------------------------------------
    oa_years = {w["id"]: int(w.get("year") or 0) for w in pubs}
    oa_node_list = [w["id"] for w in pubs]
    depths = dag_longest_depths(oa_node_list, internal_edges, oa_years)
    depth_dist = Counter(depths.values())
    depth_ge3_k = sum(v for d, v in depth_dist.items() if d >= 3)
    depth_ge3_p, d3_lo, d3_hi = wilson_ci(depth_ge3_k, len(oa_node_list))
    zero_in_cit_k = sum(1 for wid in oa_node_list if in_deg_internal[wid] == 0)
    zero_in_p, zi_lo, zi_hi = wilson_ci(zero_in_cit_k, len(oa_node_list))

    null_res = null_model_reciprocity_and_depth(oa_node_list, internal_edges, oa_years, n_perm=300)

    # Replikasjonsstudiar vs nyord/rammeverkslansering
    rep_meta_k = sum(
        1 for w in pubs
        if REPLICATION_TITLE_ABS_RE.search(f"{w.get('title') or ''} {raw_meta.get(w['id'], {}).get('abstract', '')}")
    )
    rep_meta_p, rm_lo, rm_hi = wilson_ci(rep_meta_k, len(pubs))
    novel_title_k = sum(1 for w in all_works if NOVELTY_FRAMING_RE.search(w.get("title") or ""))
    novel_title_p, nt_lo, nt_hi = wilson_ci(novel_title_k, len(all_works))

    rep_ft_k = sum(1 for r in ft_records if REPLICATION_BODY_RE.search(r["body"]))
    rep_ft_p, rf_lo, rf_hi = wilson_ci(rep_ft_k, N_ft)

    # Originalt mål: «Semantisk amnesi» (kor ofte ignorerer eit nyare verk eldre nordiske verk
    # med svært høg tematisk/semantisk likskap cos >= 0.80 og cos >= 0.85?)
    oa_vec_items = [(w["id"], int(w.get("year") or 0), vecs_256[w["id"]]) for w in pubs if w["id"] in vecs_256 and out_deg_all[w["id"]] >= 5 and (w.get("year") or 0) >= 1990]
    oa_vec_ids = [x[0] for x in oa_vec_items]
    oa_vec_yrs = np.array([x[1] for x in oa_vec_items], dtype=np.int32)
    oa_mat = np.vstack([x[2] for x in oa_vec_items])
    sim_mat = oa_mat @ oa_mat.T
    internal_edge_set = set(internal_edges)

    amnesia_bins = {}
    for thr_lo, thr_hi, label in ((0.75, 0.80, "0.75-0.80"), (0.80, 0.85, "0.80-0.85"), (0.85, 1.01, ">=0.85")):
        # Krev minst 2 års avstand slik at tidlegare arbeid faktisk var publisert og tilgjengeleg
        yr_diff = oa_vec_yrs[:, None] - oa_vec_yrs[None, :]
        mask = (yr_diff >= 2) & (sim_mat >= thr_lo) & (sim_mat < thr_hi)
        rows_i, cols_j = np.where(mask)
        total_pairs = int(rows_i.size)
        cited_pairs = sum(1 for ii, jj in zip(rows_i.tolist(), cols_j.tolist()) if (oa_vec_ids[ii], oa_vec_ids[jj]) in internal_edge_set)
        uncited_pairs = total_pairs - cited_pairs
        amnesia_rate, am_lo, am_hi = wilson_ci(uncited_pairs, total_pairs)
        amnesia_bins[label] = {
            "prior_similar_pairs": total_pairs,
            "cited_pairs": cited_pairs,
            "uncited_amnesia_rate": round(amnesia_rate, 4),
            "amnesia_ci95": [round(am_lo, 4), round(am_hi, 4)],
        }

    p2_stats = {
        "dag_depth_distribution": {str(k): int(v) for k, v in sorted(depth_dist.items())},
        "max_dag_depth": max(depths.values()) if depths else 0,
        "depth_ge3_share": round(depth_ge3_p, 4),
        "depth_ge3_ci95": [round(d3_lo, 4), round(d3_hi, 4)],
        "null_depth_ge3_mean": round(null_res["null_depth_ge3_mean"], 4),
        "zero_internal_citations_share": round(zero_in_p, 4),
        "zero_internal_citations_ci95": [round(zi_lo, 4), round(zi_hi, 4)],
        "replication_studies_metadata_k": rep_meta_k,
        "replication_studies_metadata_share": round(rep_meta_p, 5),
        "replication_studies_metadata_ci95": [round(rm_lo, 5), round(rm_hi, 5)],
        "replication_studies_fulltext_k": rep_ft_k,
        "replication_studies_fulltext_share": round(rep_ft_p, 4),
        "replication_studies_fulltext_ci95": [round(rf_lo, 4), round(rf_hi, 4)],
        "novelty_framing_titles_k": novel_title_k,
        "novelty_framing_titles_share": round(novel_title_p, 4),
        "novelty_framing_ci95": [round(nt_lo, 4), round(nt_hi, 4)],
        "neologism_to_replication_ratio": round(novel_title_k / max(1, rep_meta_k), 1),
        "semantic_amnesia_by_cosine": amnesia_bins,
    }

    # -----------------------------------------------------------------------
    # P3: Presise, falsifiserbare hypotesar og prediksjonar
    # -----------------------------------------------------------------------
    hyp_all_k = sum(1 for r in ft_records if FORMAL_HYPOTHESIS_RE.search(r["body"]))
    hyp_flag_k = sum(1 for r in ft_flagship if FORMAL_HYPOTHESIS_RE.search(r["body"]))
    hyp_nonflag_k = hyp_all_k - hyp_flag_k
    hyp_jour_k = sum(1 for r in ft_journal if FORMAL_HYPOTHESIS_RE.search(r["body"]))

    inf_all_k = sum(1 for r in ft_records if INFERENTIAL_STATS_RE.search(r["body"]))
    inf_flag_k = sum(1 for r in ft_flagship if INFERENTIAL_STATS_RE.search(r["body"]))
    prereg_k = sum(1 for r in ft_records if PREREGISTRATION_RE.search(r["full"]))
    interp_k = sum(1 for r in ft_records if INTERPRETIVE_OPEN_RE.search(r["body"]))

    hyp_p, hyp_lo, hyp_hi = wilson_ci(hyp_all_k, N_ft)
    hyp_fp, hyp_flo, hyp_fhi = wilson_ci(hyp_flag_k, len(ft_flagship))
    inf_p, inf_lo, inf_hi = wilson_ci(inf_all_k, N_ft)
    inf_fp, inf_flo, inf_fhi = wilson_ci(inf_flag_k, len(ft_flagship))
    prereg_p, pre_lo, pre_hi = wilson_ci(prereg_k, N_ft)
    interp_p, int_lo, int_hi = wilson_ci(interp_k, N_ft)

    # Test om kjernekanalar i designteori har signifikant LÅGARE hypoteserate enn randkanalar
    n_nonflag = N_ft - len(ft_flagship)
    chi_flag_hyp = chi2_2x2(
        hyp_flag_k, len(ft_flagship) - hyp_flag_k,
        hyp_nonflag_k, n_nonflag - hyp_nonflag_k,
    )

    p3_stats = {
        "n_fulltext": N_ft,
        "n_flagship_fulltext": len(ft_flagship),
        "n_journal_fulltext": len(ft_journal),
        "formal_hypothesis_all_k": hyp_all_k,
        "formal_hypothesis_all_share": round(hyp_p, 4),
        "formal_hypothesis_all_ci95": [round(hyp_lo, 4), round(hyp_hi, 4)],
        "formal_hypothesis_flagship_k": hyp_flag_k,
        "formal_hypothesis_flagship_share": round(hyp_fp, 4),
        "formal_hypothesis_flagship_ci95": [round(hyp_flo, 4), round(hyp_fhi, 4)],
        "formal_hypothesis_journal_share": round(hyp_jour_k / max(1, len(ft_journal)), 4),
        "inferential_stats_all_k": inf_all_k,
        "inferential_stats_all_share": round(inf_p, 4),
        "inferential_stats_all_ci95": [round(inf_lo, 4), round(inf_hi, 4)],
        "inferential_stats_flagship_k": inf_flag_k,
        "inferential_stats_flagship_share": round(inf_fp, 4),
        "inferential_stats_flagship_ci95": [round(inf_flo, 4), round(inf_fhi, 4)],
        "preregistered_studies_k": prereg_k,
        "preregistered_share": round(prereg_p, 5),
        "preregistered_ci95": [round(pre_lo, 5), round(pre_hi, 5)],
        "interpretive_open_discourse_share": round(interp_p, 4),
        "interpretive_open_ci95": [round(int_lo, 4), round(int_hi, 4)],
        "flagship_vs_boundary_hypothesis_chi2": chi_flag_hyp,
    }

    # -----------------------------------------------------------------------
    # P4: Eksport til andre disiplinar vs epistemisk importunderskot
    # -----------------------------------------------------------------------
    print("[4/6] Reknar kryssdisiplinær import- og eksportmatrise frå siteringsgrafen for P4...", flush=True)
    cross_mat = compute_cross_disciplinary_matrix(oa_ids)

    canon_non_design_venue = sum(
        1 for c in canon
        if not any(kw in (c.get("source") or "").lower() for kw in DESIGN_ENCLAVE_KEYWORDS)
    )
    imp_ext_p, imp_lo, imp_hi = wilson_ci(canon_non_design_venue, len(canon))

    enclave_ret_k = cross_mat["enclave_hci_innovation_retention_k"]
    enclave_ret_n = cross_mat["total_observed_incoming_citations"]
    encl_p, encl_lo, encl_hi = wilson_ci(enclave_ret_k, enclave_ret_n)
    hard_sci_share = cross_mat["basic_and_empirical_sciences_share"]

    zero_global_cits_k = sum(1 for w in pubs if (w.get("citations") or 0) == 0)
    le2_global_cits_k = sum(1 for w in pubs if (w.get("citations") or 0) <= 2)
    zg_p, zg_lo, zg_hi = wilson_ci(zero_global_cits_k, len(pubs))

    flagship_oa = [
        w for w in pubs
        if raw_meta.get(w["id"], {}).get("source_id") in PURE_DESIGN_VENUES
        or DEDICATED_VENUE_NAMES_RE.search(w.get("source") or "")
    ]
    flag_cits = np.array([w.get("citations") or 0 for w in flagship_oa], dtype=np.float64)
    flag_med, fm_lo, fm_hi = bootstrap_median_ci(flag_cits)

    # Nordiske kjernekanalar (FormAkademisk + Nordes): median globale siteringar
    nordic_core_oa = [w for w in pubs if re.search(r"\b(?:formakademisk|nordes|nordic design research|artifact)\b", w.get("source") or "", re.I)]
    ncore_cits = np.array([w.get("citations") or 0 for w in nordic_core_oa], dtype=np.float64)
    ncore_med = float(np.median(ncore_cits)) if ncore_cits.size else 0.0

    export_outside_enclave = 1.0 - encl_p
    epistemic_trade_balance = (export_outside_enclave - imp_ext_p) / max(1e-9, export_outside_enclave + imp_ext_p)

    # Sammenslått semantisk amnesi ved cos >= 0.80 med eksakt Wilson-KI
    am_tot_80 = amnesia_bins["0.80-0.85"]["prior_similar_pairs"] + amnesia_bins[">=0.85"]["prior_similar_pairs"]
    am_unc_80 = (amnesia_bins["0.80-0.85"]["prior_similar_pairs"] - amnesia_bins["0.80-0.85"]["cited_pairs"]) + (
        amnesia_bins[">=0.85"]["prior_similar_pairs"] - amnesia_bins[">=0.85"]["cited_pairs"]
    )
    am80_p, am80_lo, am80_hi = wilson_ci(am_unc_80, am_tot_80)

    # Innkommande siteringsfordeling til figur 4 (Design-enklave + eksterne felt)
    citing_breakdown = {"Nordisk designteori (intern enklave)": cross_mat["design_to_design_citations"]}
    for fk, fv in cross_mat["export_by_field"].items():
        citing_breakdown[fk] = fv

    p4_stats = {
        "canon_total": len(canon),
        "canon_from_non_design_venues_k": canon_non_design_venue,
        "canon_import_share": round(imp_ext_p, 4),
        "canon_import_ci95": [round(imp_lo, 4), round(imp_hi, 4)],
        "enclave_and_adjacent_retention_k": enclave_ret_k,
        "enclave_and_adjacent_retention_n": enclave_ret_n,
        "enclave_and_adjacent_retention_share": round(encl_p, 4),
        "enclave_retention_ci95": [round(encl_lo, 4), round(encl_hi, 4)],
        "citing_outside_design_hci_enclave_share": round(export_outside_enclave, 4),
        "citing_natural_and_basic_sciences_share": round(hard_sci_share, 4),
        "external_uptake_rate_of_non_design_refs": cross_mat["external_uptake_rate_of_non_design_refs"],
        "epistemic_trade_balance_index": round(epistemic_trade_balance, 4),
        "zero_global_citations_share": round(zg_p, 4),
        "zero_global_citations_ci95": [round(zg_lo, 4), round(zg_hi, 4)],
        "le2_global_citations_share": round(le2_global_cits_k / max(1, len(pubs)), 4),
        "flagship_median_global_citations": round(flag_med, 2),
        "flagship_median_citations_ci95": [round(fm_lo, 2), round(fm_hi, 2)],
        "nordic_core_journals_median_citations": round(ncore_med, 2),
        "citing_fields_top12": citing_breakdown,
        "cross_disciplinary_matrix": cross_mat,
    }

    # -----------------------------------------------------------------------
    # P5: Prosessrettferdiggjering utan etterprøvbare effektkrav eller negative utfall
    # -----------------------------------------------------------------------
    proc_doc_k = 0
    ctrl_doc_k = 0
    neg_doc_k = 0
    proc_densities = []
    ctrl_densities = []
    for r in ft_records:
        words_k = max(0.1, len(r["body"].split()) / 1000.0)
        pm = len(PROCESS_METHOD_RE.findall(r["body"]))
        cm = len(CONTROLLED_EFFECT_RE.findall(r["body"]))
        nm = len(NEGATIVE_OUTCOME_RE.findall(r["body"]))
        if pm > 0:
            proc_doc_k += 1
        if cm > 0:
            ctrl_doc_k += 1
        if nm > 0:
            neg_doc_k += 1
        proc_densities.append(pm / words_k)
        ctrl_densities.append(cm / words_k)

    proc_p, pr_lo, pr_hi = wilson_ci(proc_doc_k, N_ft)
    ctrl_p, ct_lo, ct_hi = wilson_ci(ctrl_doc_k, N_ft)
    neg_p, ng_lo, ng_hi = wilson_ci(neg_doc_k, N_ft)
    neg_flag_k = sum(1 for r in ft_flagship if NEGATIVE_OUTCOME_RE.search(r["body"]))
    neg_flag_p, nfl_lo, nfl_hi = wilson_ci(neg_flag_k, len(ft_flagship))

    proc_arr = np.array(proc_densities)
    ctrl_arr = np.array(ctrl_densities)
    mwu_proc_vs_ctrl = mann_whitney_u(proc_arr, ctrl_arr)
    proc_mean, pm_lo, pm_hi = bootstrap_mean_ci(proc_arr)
    ctrl_mean, cm_lo, cm_hi = bootstrap_mean_ci(ctrl_arr)

    # Blant artiklar som nyttar prosessmetodar (workshop/probes/co-design/RtD), kor mange har kontrollgruppe ELLER negativt funn?
    proc_only_without_effect_or_neg = sum(
        1 for r in ft_records
        if PROCESS_METHOD_RE.search(r["body"])
        and not CONTROLLED_EFFECT_RE.search(r["body"])
        and not NEGATIVE_OUTCOME_RE.search(r["body"])
    )
    unverified_proc_p, up_lo, up_hi = wilson_ci(proc_only_without_effect_or_neg, proc_doc_k)

    p5_stats = {
        "process_method_docs_k": proc_doc_k,
        "process_method_share": round(proc_p, 4),
        "process_method_ci95": [round(pr_lo, 4), round(pr_hi, 4)],
        "controlled_effect_docs_k": ctrl_doc_k,
        "controlled_effect_share": round(ctrl_p, 4),
        "controlled_effect_ci95": [round(ct_lo, 4), round(ct_hi, 4)],
        "negative_or_null_outcome_docs_k": neg_doc_k,
        "negative_or_null_outcome_share": round(neg_p, 4),
        "negative_or_null_outcome_ci95": [round(ng_lo, 4), round(ng_hi, 4)],
        "flagship_negative_outcome_share": round(neg_flag_p, 4),
        "flagship_negative_outcome_ci95": [round(nfl_lo, 4), round(nfl_hi, 4)],
        "process_without_controlled_effect_or_null_share": round(unverified_proc_p, 4),
        "process_without_effect_ci95": [round(up_lo, 4), round(up_hi, 4)],
        "process_terms_per_1k_words_mean": round(proc_mean, 3),
        "process_terms_ci95": [round(pm_lo, 3), round(pm_hi, 3)],
        "effect_terms_per_1k_words_mean": round(ctrl_mean, 3),
        "effect_terms_ci95": [round(cm_lo, 3), round(cm_hi, 3)],
        "mann_whitney_process_vs_effect": mwu_proc_vs_ctrl,
    }

    # -----------------------------------------------------------------------
    # P6: Etterskotslegitimering av økonomiske og organisatoriske val
    # -----------------------------------------------------------------------
    comm_k = 0
    mandate_k = 0
    comm_and_mandate_k = 0
    challenged_mandate_k = 0
    comm_neg_k = 0
    indep_neg_k = 0

    for r in ft_records:
        has_comm = bool(COMMISSIONED_FUNDING_RE.search(r["full"]))
        has_mand = bool(PREDECIDED_MANDATE_RE.search(r["body"]))
        has_chal = bool(MANDATE_CHALLENGE_RE.search(r["body"]))
        has_neg = bool(NEGATIVE_OUTCOME_RE.search(r["body"]))
        if has_comm:
            comm_k += 1
            if has_neg:
                comm_neg_k += 1
        else:
            if has_neg:
                indep_neg_k += 1
        if has_mand:
            mandate_k += 1
        if has_comm and has_mand:
            comm_and_mandate_k += 1
        if has_chal:
            challenged_mandate_k += 1

    comm_p, co_lo, co_hi = wilson_ci(comm_k, N_ft)
    mand_p, ma_lo, ma_hi = wilson_ci(mandate_k, N_ft)
    chal_p, ch_lo, ch_hi = wilson_ci(challenged_mandate_k, N_ft)
    # Del av oppdrags-/strategiforankra studiar som aldri utfordrar/stansar mandatet eller rapporterer negativ effekt
    affirmative_comm_k = sum(
        1 for r in ft_records
        if COMMISSIONED_FUNDING_RE.search(r["full"])
        and PREDECIDED_MANDATE_RE.search(r["body"])
        and not MANDATE_CHALLENGE_RE.search(r["body"])
        and not NEGATIVE_OUTCOME_RE.search(r["body"])
    )
    aff_p, af_lo, af_hi = wilson_ci(affirmative_comm_k, comm_and_mandate_k)
    chi_comm_neg = chi2_2x2(comm_neg_k, comm_k - comm_neg_k, indep_neg_k, (N_ft - comm_k) - indep_neg_k)

    p6_stats = {
        "externally_funded_or_partnered_k": comm_k,
        "externally_funded_share": round(comm_p, 4),
        "externally_funded_ci95": [round(co_lo, 4), round(co_hi, 4)],
        "strategic_or_organizational_mandate_k": mandate_k,
        "strategic_mandate_share": round(mand_p, 4),
        "strategic_mandate_ci95": [round(ma_lo, 4), round(ma_hi, 4)],
        "funded_with_preexisting_mandate_k": comm_and_mandate_k,
        "mandate_reversal_or_halt_k": challenged_mandate_k,
        "mandate_reversal_share": round(chal_p, 5),
        "mandate_reversal_ci95": [round(ch_lo, 5), round(ch_hi, 5)],
        "affirmative_legitimation_rate_in_mandated_projects": round(aff_p, 4),
        "affirmative_legitimation_ci95": [round(af_lo, 4), round(af_hi, 4)],
        "funded_vs_independent_negative_outcome_chi2": chi_comm_neg,
    }

    # -----------------------------------------------------------------------
    # P7: Doktorgradsavhandlingar som isolerte eingongsverk
    # -----------------------------------------------------------------------
    phd_all = [w for w in all_works if w.get("kind") in ("dissertation", "thesis")]
    phd_oa = [w for w in pubs if w.get("kind") == "dissertation"]
    phd_oa_ids = {w["id"] for w in phd_oa}
    journal_oa = [w for w in pubs if w.get("kind") == "article"]

    # Sitering frå avhandling til avhandling og frå korpuset til avhandlingar
    phd_to_phd_edges = [(u, v) for u, v in internal_edges if u in phd_oa_ids and v in phd_oa_ids]
    phd_zero_internal_in = sum(1 for w in phd_oa if in_deg_internal[w["id"]] == 0)
    phd_zero_internal_out = sum(1 for w in phd_oa if out_deg_internal[w["id"]] == 0)
    phd_zero_global = sum(1 for w in phd_oa if (w.get("citations") or 0) == 0)

    phd_cits_arr = np.array([w.get("citations") or 0 for w in phd_oa], dtype=np.float64)
    art_cits_arr = np.array([w.get("citations") or 0 for w in journal_oa], dtype=np.float64)
    mwu_phd_vs_art = mann_whitney_u(phd_cits_arr, art_cits_arr)

    # Forfattarkontinuitet etter doktorgrad (kohort <= 2021 for minst 5 års observasjonstid fram til 2026)
    author_pub_years: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for w in all_works:
        yr = w.get("year")
        if not isinstance(yr, int) or yr < 1900:
            continue
        for aname in (w.get("authors") or []):
            nk = normalize_title(aname)
            if len(nk) >= 5:
                author_pub_years[nk].append((yr, w["id"]))

    cohort_phd_authors = []
    zero_post_phd = 0
    le1_post_phd = 0
    post_sem_sims = []
    seen_phd_author_keys: set[str] = set()

    for w in phd_all:
        yr = w.get("year")
        if not isinstance(yr, int) or yr > 2021 or yr < 1980:
            continue
        au_list = w.get("authors") or []
        if not au_list:
            continue
        primary_au = normalize_title(au_list[0])
        if len(primary_au) < 5 or primary_au in seen_phd_author_keys:
            continue
        seen_phd_author_keys.add(primary_au)
        later_wids = [wid2 for y2, wid2 in author_pub_years[primary_au] if y2 > yr and wid2 != w["id"]]
        cohort_phd_authors.append((primary_au, yr, len(later_wids)))
        if len(later_wids) == 0:
            zero_post_phd += 1
        if len(later_wids) <= 1:
            le1_post_phd += 1
        if w["id"] in vecs_256 and later_wids:
            v0 = vecs_256[w["id"]]
            sims = [float(v0 @ vecs_256[lw]) for lw in later_wids if lw in vecs_256]
            if sims:
                post_sem_sims.extend(sims)

    zp_p, zp_lo, zp_hi = wilson_ci(zero_post_phd, len(cohort_phd_authors))
    le1_p, l1_lo, l1_hi = wilson_ci(le1_post_phd, len(cohort_phd_authors))
    phd_zin_p, pzi_lo, pzi_hi = wilson_ci(phd_zero_internal_in, len(phd_oa))
    phd_zg_p, pzg_lo, pzg_hi = wilson_ci(phd_zero_global, len(phd_oa))

    p7_stats = {
        "total_dissertations_all_layers": len(phd_all),
        "openalex_dissertations_n": len(phd_oa),
        "phd_to_phd_citation_edges": len(phd_to_phd_edges),
        "phd_zero_internal_citations_k": phd_zero_internal_in,
        "phd_zero_internal_citations_share": round(phd_zin_p, 4),
        "phd_zero_internal_ci95": [round(pzi_lo, 4), round(pzi_hi, 4)],
        "phd_zero_backward_internal_refs_share": round(phd_zero_internal_out / max(1, len(phd_oa)), 4),
        "phd_zero_global_citations_share": round(phd_zg_p, 4),
        "phd_zero_global_ci95": [round(pzg_lo, 4), round(pzg_hi, 4)],
        "phd_median_global_citations": float(np.median(phd_cits_arr)) if phd_cits_arr.size else 0.0,
        "article_median_global_citations": float(np.median(art_cits_arr)) if art_cits_arr.size else 0.0,
        "mann_whitney_phd_vs_article_citations": mwu_phd_vs_art,
        "phd_cohort_upto_2021_authors_n": len(cohort_phd_authors),
        "zero_post_phd_publications_k": zero_post_phd,
        "zero_post_phd_share": round(zp_p, 4),
        "zero_post_phd_ci95": [round(zp_lo, 4), round(zp_hi, 4)],
        "le1_post_phd_publications_share": round(le1_p, 4),
        "le1_post_phd_ci95": [round(l1_lo, 4), round(l1_hi, 4)],
        "post_phd_mean_cosine_similarity": round(float(np.mean(post_sem_sims)), 4) if post_sem_sims else 0.0,
    }

    # -----------------------------------------------------------------------
    # P8: Lukka publiseringskretsløp, endogami, resiprositet og sjølvsitering
    # -----------------------------------------------------------------------
    NORDIC_INHOUSE_RE = re.compile(
        r"\b(?:formakademisk|nordes|nordic design research|design research society|proceedings of drs|"
        r"servdes|participatory design conference|cumulus|arkitektur- og designhøgskolen|"
        r"aalto|konstfack|det kongelige akademi|design school kolding|diva|nasjonalt vitenarkiv)\b",
        re.I,
    )
    inhouse_all_k = sum(
        1 for w in all_works
        if NORDIC_INHOUSE_RE.search(f"{w.get('source') or ''} {w.get('venue') or ''}")
    )
    inhouse_p, ih_lo, ih_hi = wilson_ci(inhouse_all_k, len(all_works))

    # Konferanse-/arkiv-/bokkapittel-del vs fagfellevurderte tidsskriftsartiklar
    non_journal_k = sum(1 for w in all_works if w.get("kind") != "article")
    non_journal_p, nj_lo, nj_hi = wilson_ci(non_journal_k, len(all_works))

    # Sjølvsitering og institusjonsendogami i den interne siteringsgrafen
    author_self_cit_k = 0
    inst_self_cit_k = 0
    same_venue_cit_k = 0
    reciprocal_edges_k = 0
    for u, v in internal_edges:
        if work_authors[u] and work_authors[v] and (work_authors[u] & work_authors[v]):
            author_self_cit_k += 1
        if work_insts[u] and work_insts[v] and (work_insts[u] & work_insts[v]):
            inst_self_cit_k += 1
        su = (by_id[u].get("source") or "").strip().lower()
        sv = (by_id[v].get("source") or "").strip().lower()
        if su and su == sv:
            same_venue_cit_k += 1
        if (v, u) in internal_edge_set:
            reciprocal_edges_k += 1

    n_ie = len(internal_edges)
    auth_sc_p, asc_lo, asc_hi = wilson_ci(author_self_cit_k, n_ie)
    inst_sc_p, isc_lo, isc_hi = wilson_ci(inst_self_cit_k, n_ie)
    venue_sc_p, vsc_lo, vsc_hi = wilson_ci(same_venue_cit_k, n_ie)
    recip_obs = reciprocal_edges_k / max(1, n_ie)
    recip_z = (recip_obs - null_res["null_reciprocity_mean"]) / null_res["null_reciprocity_sd"]
    recip_p_val = norm_sf(recip_z)

    # Forfattarkonsentrasjon (Gini-koeffisient) i nordiske kjernekanalar (FormAkademisk, Nordes, CoDesign, PDC)
    insider_counts: Counter[str] = Counter()
    for w in all_works:
        vstr = f"{w.get('source') or ''} {w.get('venue') or ''}"
        if re.search(r"\b(?:formakademisk|nordes|nordic design research|participatory design conference|codesign)\b", vstr, re.I):
            for a in (w.get("authors") or []):
                nk = normalize_title(a)
                if len(nk) >= 5:
                    insider_counts[nk] += 1
    insider_vals = list(insider_counts.values())
    insider_gini = gini_coefficient(insider_vals)
    top5pct_n = max(1, len(insider_vals) // 20)
    top5pct_share = sum(sorted(insider_vals, reverse=True)[:top5pct_n]) / max(1, sum(insider_vals))

    # Redaksjons-/fagfelletid der mottatt/godkjend-dato står i PDF (t.d. < 14 dagar lynaksept)
    p8_stats = {
        "inhouse_or_regional_network_works_k": inhouse_all_k,
        "inhouse_or_regional_share": round(inhouse_p, 4),
        "inhouse_ci95": [round(ih_lo, 4), round(ih_hi, 4)],
        "non_journal_output_share": round(non_journal_p, 4),
        "non_journal_ci95": [round(nj_lo, 4), round(nj_hi, 4)],
        "internal_edges_total": n_ie,
        "author_overlap_self_citation_k": author_self_cit_k,
        "author_overlap_self_citation_share": round(auth_sc_p, 4),
        "author_self_citation_ci95": [round(asc_lo, 4), round(asc_hi, 4)],
        "institution_endogamous_citation_k": inst_self_cit_k,
        "institution_endogamous_citation_share": round(inst_sc_p, 4),
        "institution_citation_ci95": [round(isc_lo, 4), round(isc_hi, 4)],
        "same_venue_citation_share": round(venue_sc_p, 4),
        "same_venue_ci95": [round(vsc_lo, 4), round(vsc_hi, 4)],
        "reciprocal_citation_share": round(recip_obs, 5),
        "null_reciprocal_share": round(null_res["null_reciprocity_mean"], 5),
        "reciprocity_z_score": round(recip_z, 2),
        "reciprocity_p_value": recip_p_val,
        "core_nordic_venue_author_gini": round(insider_gini, 4),
        "core_venue_top5pct_author_output_share": round(top5pct_share, 4),
    }

    # -----------------------------------------------------------------------
    # P9: Etiske rammer, nemndgodkjenning, interessekonflikt og etteransvar
    # -----------------------------------------------------------------------
    human_docs = [r for r in ft_records if HUMAN_SUBJECTS_RE.search(r["body"])]
    vuln_docs = [r for r in human_docs if VULNERABLE_GROUPS_RE.search(r["body"])]
    N_hum = len(human_docs)
    N_vuln = len(vuln_docs)

    eth_in_hum_k = sum(1 for r in human_docs if ETHICS_BOARD_RE.search(r["full"]))
    eth_in_vuln_k = sum(1 for r in vuln_docs if ETHICS_BOARD_RE.search(r["full"]))
    cons_in_hum_k = sum(1 for r in human_docs if INFORMED_CONSENT_RE.search(r["full"]))
    coi_all_k = sum(1 for r in ft_records if COI_STATEMENT_RE.search(r["full"]))
    post_acc_hum_k = sum(1 for r in human_docs if POST_PROJECT_ACCOUNTABILITY_RE.search(r["body"]))

    no_eth_hum_k = N_hum - eth_in_hum_k
    no_eth_p, ne_lo, ne_hi = wilson_ci(no_eth_hum_k, N_hum)
    eth_p, et_lo, et_hi = wilson_ci(eth_in_hum_k, N_hum)
    eth_vp, ev_lo, ev_hi = wilson_ci(eth_in_vuln_k, N_vuln)
    cons_p, cs_lo, cs_hi = wilson_ci(cons_in_hum_k, N_hum)
    coi_p, ci_lo, ci_hi = wilson_ci(coi_all_k, N_ft)
    post_p, pa_lo, pa_hi = wilson_ci(post_acc_hum_k, N_hum)

    # Kjerne-designtidsskrift spesifikt (FormAkademisk, Nordes, DRS, Design Issues, CoDesign mfl.)
    hum_flag = [r for r in human_docs if r["is_flagship"]]
    eth_flag_k = sum(1 for r in hum_flag if ETHICS_BOARD_RE.search(r["full"]))
    eth_flag_p, ef_lo, ef_hi = wilson_ci(eth_flag_k, len(hum_flag))

    p9_stats = {
        "human_participant_studies_n": N_hum,
        "human_participant_share_of_fulltext": round(N_hum / max(1, N_ft), 4),
        "vulnerable_group_studies_n": N_vuln,
        "lacking_ethics_board_approval_k": no_eth_hum_k,
        "lacking_ethics_board_share": round(no_eth_p, 4),
        "lacking_ethics_board_ci95": [round(ne_lo, 4), round(ne_hi, 4)],
        "with_ethics_board_approval_share": round(eth_p, 4),
        "with_ethics_board_ci95": [round(et_lo, 4), round(et_hi, 4)],
        "flagship_human_studies_with_ethics_board_share": round(eth_flag_p, 4),
        "flagship_ethics_board_ci95": [round(ef_lo, 4), round(ef_hi, 4)],
        "vulnerable_group_with_ethics_board_share": round(eth_vp, 4),
        "vulnerable_ethics_ci95": [round(ev_lo, 4), round(ev_hi, 4)],
        "documented_informed_consent_share": round(cons_p, 4),
        "informed_consent_ci95": [round(cs_lo, 4), round(cs_hi, 4)],
        "conflict_of_interest_disclosure_share": round(coi_p, 4),
        "conflict_of_interest_ci95": [round(ci_lo, 4), round(ci_hi, 4)],
        "post_project_accountability_or_followup_k": post_acc_hum_k,
        "post_project_accountability_share": round(post_p, 4),
        "post_project_accountability_ci95": [round(pa_lo, 4), round(pa_hi, 4)],
    }

    # -----------------------------------------------------------------------
    # P10: Validerte målereiskapar, faste kriterium og opne data
    # -----------------------------------------------------------------------
    inst_k = sum(1 for r in ft_records if VALIDATED_INSTRUMENT_RE.search(r["body"]))
    psych_k = sum(1 for r in ft_records if PSYCHOMETRIC_RELIABILITY_RE.search(r["body"]))
    either_meas_k = sum(
        1 for r in ft_records
        if VALIDATED_INSTRUMENT_RE.search(r["body"]) or PSYCHOMETRIC_RELIABILITY_RE.search(r["body"])
    )
    flag_meas_k = sum(
        1 for r in ft_flagship
        if VALIDATED_INSTRUMENT_RE.search(r["body"]) or PSYCHOMETRIC_RELIABILITY_RE.search(r["body"])
    )
    opendata_k = sum(1 for r in ft_records if OPEN_DATA_CODE_RE.search(r["full"]))
    flag_opendata_k = sum(1 for r in ft_flagship if OPEN_DATA_CODE_RE.search(r["full"]))

    inst_p, in_lo, in_hi = wilson_ci(inst_k, N_ft)
    psych_p, ps_lo, ps_hi = wilson_ci(psych_k, N_ft)
    meas_p, me_lo, me_hi = wilson_ci(either_meas_k, N_ft)
    no_meas_p, nm_lo, nm_hi = wilson_ci(N_ft - either_meas_k, N_ft)
    fmeas_p, fm2_lo, fm2_hi = wilson_ci(flag_meas_k, len(ft_flagship))
    od_p, od_lo, od_hi = wilson_ci(opendata_k, N_ft)
    fod_p, fod_lo, fod_hi = wilson_ci(flag_opendata_k, len(ft_flagship))

    p10_stats = {
        "validated_instrument_docs_k": inst_k,
        "validated_instrument_share": round(inst_p, 4),
        "validated_instrument_ci95": [round(in_lo, 4), round(in_hi, 4)],
        "psychometric_reliability_docs_k": psych_k,
        "psychometric_reliability_share": round(psych_p, 4),
        "psychometric_reliability_ci95": [round(ps_lo, 4), round(ps_hi, 4)],
        "any_validated_or_psychometric_share": round(meas_p, 4),
        "any_validated_or_psychometric_ci95": [round(me_lo, 4), round(me_hi, 4)],
        "lacking_validated_measurement_share": round(no_meas_p, 4),
        "lacking_validated_measurement_ci95": [round(nm_lo, 4), round(nm_hi, 4)],
        "flagship_validated_or_psychometric_share": round(fmeas_p, 4),
        "flagship_validated_ci95": [round(fm2_lo, 4), round(fm2_hi, 4)],
        "open_data_or_code_repository_k": opendata_k,
        "open_data_or_code_share": round(od_p, 4),
        "open_data_or_code_ci95": [round(od_lo, 4), round(od_hi, 4)],
        "flagship_open_data_share": round(fod_p, 4),
        "flagship_open_data_ci95": [round(fod_lo, 4), round(fod_hi, 4)],
    }

    # -----------------------------------------------------------------------
    # Samla oversiktstabell og eksport til CSV + JSON
    # -----------------------------------------------------------------------
    summary_rows = [
        {
            "id": "P1",
            "paastand": "Manglar samordna forskingsprogram og revisjonsmekanismar",
            "hovudindikator": "Einsleg-siterte referansar (1 gong) / fråvær av revisjonsmarkørar i fulltekst",
            "utval_n": total_unique_cited,
            "estimat_pct": round(singleton_share * 100, 2),
            "ki95_lav_pct": round(sing_lo * 100, 2),
            "ki95_hog_pct": round(sing_hi * 100, 2),
            "sekundaer_funn": f"Maks kanondel {max_canon_share_all*100:.1f} %; revisjonsmarkørar i {rev_p*100:.2f} % av fulltekstar (kjerne {rev_flag_p*100:.2f} %)",
        },
        {
            "id": "P2",
            "paastand": "Kunnskapen er ikkje kumulativ; ingen etterprøving eller systematisk vidarebygging",
            "hovudindikator": "Semantisk amnesi (cos >= 0.80 til eldre nordisk verk utan sitering)",
            "utval_n": am_tot_80,
            "estimat_pct": round(am80_p * 100, 2),
            "ki95_lav_pct": round(am80_lo * 100, 2),
            "ki95_hog_pct": round(am80_hi * 100, 2),
            "sekundaer_funn": f"Replikasjonsstudiar {rep_meta_p*100:.2f} % ({rep_meta_k}/{len(pubs)}); nyord/rammeverk-rate {novel_title_k}:{max(1, rep_meta_k)}",
        },
        {
            "id": "P3",
            "paastand": "Set ikkje fram presise, falsifiserbare hypotesar eller prediksjonar",
            "hovudindikator": "Fulltekstar utan formelle hypotesar (og utan preregistrering)",
            "utval_n": N_ft,
            "estimat_pct": round((1.0 - hyp_p) * 100, 2),
            "ki95_lav_pct": round((1.0 - hyp_hi) * 100, 2),
            "ki95_hog_pct": round((1.0 - hyp_lo) * 100, 2),
            "sekundaer_funn": f"Formelle hypotesar i {hyp_p*100:.2f} % (kjernekanalar {hyp_fp*100:.2f} %); preregistrering {prereg_p*100:.2f} % ({prereg_k}/{N_ft})",
        },
        {
            "id": "P4",
            "paastand": "Andre disiplinar byggjer ikkje vidare på funn, modellar eller metodar",
            "hovudindikator": "Siteringar lukka inne i design-/HCI-/innovasjonsenklaven",
            "utval_n": enclave_ret_n,
            "estimat_pct": round(encl_p * 100, 2),
            "ki95_lav_pct": round(encl_lo * 100, 2),
            "ki95_hog_pct": round(encl_hi * 100, 2),
            "sekundaer_funn": f"Kanonimport utanfrå {imp_ext_p*100:.1f} %; basale vitskapar {hard_sci_share*100:.2f} %; <=2 siteringar globalt {le2_global_cits_k/len(pubs)*100:.1f} %",
        },
        {
            "id": "P5",
            "paastand": "Metodikken rettferdiggjer prosessen utan krav til faktisk effekt eller negative utfall",
            "hovudindikator": "Prosessmetodiske studiar utan kontrollert effektmåling eller negative funn",
            "utval_n": proc_doc_k,
            "estimat_pct": round(unverified_proc_p * 100, 2),
            "ki95_lav_pct": round(up_lo * 100, 2),
            "ki95_hog_pct": round(up_hi * 100, 2),
            "sekundaer_funn": f"Negative/null-utfall i {neg_p*100:.2f} % av fulltekstar (kjernekanalar {neg_flag_p*100:.2f} %); Mann-Whitney z={mwu_proc_vs_ctrl['z']}",
        },
        {
            "id": "P6",
            "paastand": "Forskinga legitimerer i etterkant økonomiske og organisatoriske førehandsval",
            "hovudindikator": "Oppdrags-/strategiforankra prosjekt utan reversering eller negativ konklusjon",
            "utval_n": comm_and_mandate_k,
            "estimat_pct": round(aff_p * 100, 2),
            "ki95_lav_pct": round(af_lo * 100, 2),
            "ki95_hog_pct": round(af_hi * 100, 2),
            "sekundaer_funn": f"Ekstern finansiering/partnar i {comm_p*100:.1f} %; mandatreversering i {chal_p*100:.2f} % ({challenged_mandate_k}/{N_ft})",
        },
        {
            "id": "P7",
            "paastand": "Doktorgradsavhandlingar står som isolerte eingongsverk",
            "hovudindikator": "Avhandlingar med 0 interne siteringar / doktorandar (<=2021) med 0 seinare verk",
            "utval_n": len(cohort_phd_authors),
            "estimat_pct": round(zp_p * 100, 2),
            "ki95_lav_pct": round(zp_lo * 100, 2),
            "ki95_hog_pct": round(zp_hi * 100, 2),
            "sekundaer_funn": f"<=1 seinare verk {le1_p*100:.1f} %; PhD->PhD-siteringar {len(phd_to_phd_edges)}; 0 interne siteringar på {phd_zin_p*100:.1f} % av OA-avhandlingar",
        },
        {
            "id": "P8",
            "paastand": "Publisering og fagfellevurdering skjer i lukka kretsløp",
            "hovudindikator": "Institusjons-/forfattarendogame siteringar og interne nettverkskanalar",
            "utval_n": n_ie,
            "estimat_pct": round(inst_sc_p * 100, 2),
            "ki95_lav_pct": round(isc_lo * 100, 2),
            "ki95_hog_pct": round(isc_hi * 100, 2),
            "sekundaer_funn": f"Forfattarsjølvsitering {auth_sc_p*100:.1f} %; resiprositet z={recip_z:.1f} (p<1e-12); ikkje-tidsskrift {non_journal_p*100:.1f} %; forfattar-Gini {insider_gini:.3f}",
        },
        {
            "id": "P9",
            "paastand": "Manglar handheva etiske rammer, sanksjonar og ansvar etter prosjektslutt",
            "hovudindikator": "Menneskestudiar utan dokumentert etisk nemndgodkjenning (IRB/REK/SIKT)",
            "utval_n": N_hum,
            "estimat_pct": round(no_eth_p * 100, 2),
            "ki95_lav_pct": round(ne_lo * 100, 2),
            "ki95_hog_pct": round(ne_hi * 100, 2),
            "sekundaer_funn": f"Kjernekanalar med nemnd {eth_flag_p*100:.1f} %; interessekonflikterklæring {coi_p*100:.1f} %; etter-prosjekt-oppfølging {post_p*100:.2f} %",
        },
        {
            "id": "P10",
            "paastand": "Manglar validerte målereiskapar og faste kriterium for samanlikning",
            "hovudindikator": "Fulltekstar utan validert måleinstrument eller psykometrisk reliabilitet",
            "utval_n": N_ft,
            "estimat_pct": round(no_meas_p * 100, 2),
            "ki95_lav_pct": round(nm_lo * 100, 2),
            "ki95_hog_pct": round(nm_hi * 100, 2),
            "sekundaer_funn": f"Kjernekanalar med validert mål {fmeas_p*100:.2f} %; opne rådata/kode {od_p*100:.2f} % (kjerne {fod_p*100:.2f} %)",
        },
    ]

    full_results = {
        "metadata": {
            "corpus_total_works": len(all_works),
            "openalex_works": len(pubs),
            "nordic_archive_works": len(nordic),
            "fulltext_pdfs_analyzed": N_ft,
            "fulltext_flagship_pdfs": len(ft_flagship),
            "fulltext_journal_pdfs": len(ft_journal),
            "fulltext_pages_analyzed": total_ft_pages,
            "fulltext_words_analyzed": total_ft_words,
            "outgoing_references_analyzed": len(out_refs_all),
            "internal_citation_edges": len(internal_edges),
            "vectors_256d_analyzed": len(vecs_256),
            "random_seed": 20261107,
        },
        "summary_table": summary_rows,
        "P1_research_programme": p1_stats,
        "P2_cumulativity": p2_stats,
        "P3_falsifiability": p3_stats,
        "P4_external_impact": p4_stats,
        "P5_process_justification": p5_stats,
        "P6_ex_post_legitimation": p6_stats,
        "P7_doctoral_isolation": p7_stats,
        "P8_closed_peer_review": p8_stats,
        "P9_ethics_accountability": p9_stats,
        "P10_validated_measurement": p10_stats,
    }

    (DATA_DIR / "resultatsamandrag.json").write_text(
        json.dumps(full_results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (DATA_DIR / "tabell_hypotesetestar.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print("[5/6] Lagra gransking/data/resultatsamandrag.json og tabell_hypotesetestar.csv.", flush=True)
    return full_results


if __name__ == "__main__":
    res = run_all()
    print("[6/6] Ferdig! Hovudfunn:")
    for row in res["summary_table"]:
        print(f"  {row['id']}: {row['estimat_pct']:.2f}% [{row['ki95_lav_pct']:.2f}, {row['ki95_hog_pct']:.2f}] (N={row['utval_n']}) | {row['sekundaer_funn']}")

