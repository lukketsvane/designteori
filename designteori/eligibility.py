"""Strict Design Theory & Design Research eligibility gate for DESIGNTEORI.

Ensures 100% topical purity across OpenAlex, Nordic national/institutional archives,
cited canon, semantic indices, SQLite exports, and mirrored PDFs: zero clinical,
biomedical, general STEM/engineering, enterprise IT, or general management noise.
"""
from __future__ import annotations

import html
import json
import re
import sqlite3
from pathlib import Path

import numpy as np

from . import PRIVATE_CACHE, RAW_SQLITE

PURE_DESIGN_VENUES = {
    "S2764463729",  # FormAkademisk
    "S152445846",   # Design Studies
    "S107659597",   # Design Issues
    "S4210216195",  # International Journal of Design
    "S4210189112",  # CoDesign
    "S153469747",   # The Design Journal
    "S2898472644",  # She Ji
    "S191448683",   # Journal of Design History
    "S1509497",     # Design and Culture
    "S4210222023",  # Journal of Design Research
    "S4210182550",  # Artifact
    "S4210174351",  # Design Philosophy Papers
    "S207009260",   # Strategic Design Research Journal
    "S4210211686",  # Journal of Textile Design Research and Practice
    "S4220651532",  # Proceedings of DRS (Design Research Society)
    "S4393917623",  # Nordic Design Research Conference (Nordes)
    "S4306420687",  # Participatory Design Conference (PDC)
    "S4363608268",  # Designing Interactive Systems Conference (ACM DIS)
    "S7407097501",  # ServDes Service Design and Innovation Conference
}

DEDICATED_VENUE_NAMES_RE = re.compile(
    r"\b(?:formakademisk|design studies|design issues|the design journal|"
    r"international journal of design|codesign|co-design|she ji|"
    r"journal of design history|design and culture|design philosophy papers|"
    r"journal of design research|strategic design research|"
    r"textile design research|proceedings of drs|design research society|"
    r"nordic design research|nordes|participatory design conference|"
    r"designing interactive systems|servdes|iasdr|craft research)\b",
    re.I,
)

ALLOWED_NON_VENUE_SUBFIELDS = {
    "Human-Computer Interaction",
    "Visual Arts and Performing Arts",
    "Architecture",
    "Art and Architecture",
    "Arts and Humanities (miscellaneous)",
    "Philosophy",
    "History and Philosophy of Science",
    "Cultural Studies",
    "Museology",
    "Anthropology",
    "Communication",
    "Education",
    "Urban Studies",
    "Human Factors and Ergonomics",
    "Literature and Literary Theory",
    "History",
    "Sociology and Political Science",
    "",
}

CORE_DESIGN_TOPICS = {
    "Design Education and Practice",
    "Crafts, Textile, and Design",
    "Sustainable Design and Development",
    "Fashion and Cultural Textiles",
    "Architecture, Modernity, and Design",
}

FORBIDDEN_VENUES_RE = re.compile(
    r"\b(?:theseus|ieee access|ieee transactions|ieee communications|ieee engineering management|"
    r"frontiers in (?:psychiatry|neuroscience|medicine|oncology|immunology|pharmacology|plant|microbiology|genetics|cardiovascular|public health)|"
    r"procedia cirp|cirp annals|ifac|spie|annals of internal medicine|astroparticle|computer physics|"
    r"journal of cleaner production|ehealth|medical internet research|bmj|lancet|plos medicine|nature genetics|"
    r"hawaii international conference on system sciences|hicss|mis quarterly|service science|"
    r"lecture notes in geoinformation|international journal of business|journal of marketing|"
    r"engineering applications of artificial intelligence|physical review|pubmed|"
    r"studies in health technology|journal of biomedical informatics|"
    r"sykepleien|tidsskrift for den norske legeforening|nordisk sygeplejeforskning|"
    r"jmir|perioperative|daimi report series|student papers)\b",
    re.I,
)

HARD_NON_DESIGN_RE = re.compile(
    r"(?:^(?:online guest lecture|guest lecture|paper presentation|keynote:|panel:|poster:)\b|"
    r"^(?:review|editorial|preface|foreword|erratum|corrigendum)$|"
    r"\b(?:trial design|study design|research design|experimental design|survey design|"
    r"questionnaire design|sampling design|curriculum design|instructional design|"
    r"design science research|mechanical engineering design|"
    r"cohort|clinical trial|randomi[sz]ed|"
    r"prisma|scoping review|systematic review protocol|finngen|feyncalc|astroparticle|"
    r"fear conditioning|neuromorphic|vaccine|drug design|protein design|primer design|"
    r"molecular design|catalyst|alloy|polymer|concrete|seismic|wind turbine|"
    r"photovoltaic|solar cell|battery|fuel cell|inverter|power electronic|microgrid|"
    r"antenna|microstrip|cmos|vlsi|fpga|asic|circuit|filter design|amplifier|"
    r"controller|control design|control system|topology optimization|origami|"
    r"additive manufacturing|laser powder|machining|5g|6g|mimo|wireless|"
    r"routing|compiler|neural network|convolutional|anti-spoofing|"
    r"computer architecture|software architecture|enterprise architecture|network architecture|"
    r"system architecture|cloud computing|edge computing|mobile edge|blockchain|cryptograph|"
    r"mechanism design|market design|auction design|firm performance|top management|"
    r"supply chain|digital marketing|tax design|pension design|prenatal|patient choice|"
    r"iec 61499|fare structure|plant design|optical scattering|recommender system|bandit|"
    r"information systems? design theor\w*|action design research|"
    r"miljøterapi|fosterovervåking|hjemmeføds\w*|sykeplei\w*|pasient\w*|medication adherence|"
    r"dialysis|clinical|hospital|shared decision-making|"
    r"infection risk|waiting time|dynamic capabilities|entrepreneurship|"
    r"bioengineering|autonomous ship|uudelleen\s*muotoilu|rooftop tent|"
    r"engaging by design|"
    r"design and analysis of (?:experiments|algorithms|clinical|randomized|computer))\b)",
    re.I,
)

STRICT_DESIGN_THEORY_RE = re.compile(
    r"\b(?:"
    r"design theor\w*|theor(?:y|ies) of design|design philosoph\w*|philosophy of design|"
    r"design epistemolog\w*|epistemology of design|ontological design|design ontolog\w*|"
    r"designerly|design knowledge|design inquiry|design discourse|"
    r"design thinking|design cognition|design judg(?:e)?ment|design criti(?:que|cism)|"
    r"design aesthetic\w*|aesthetics of design|interaction aesthetic\w*|somaesthetic\w*|soma design|"
    r"pluriversal design|posthuman\w* design|more-than-human design|"
    r"critical design|speculative design|discursive design|adversarial design|feminist design|"
    r"design ethic\w*|ethics of design|design justice|"
    r"designteori\w*|arkitekturteori\w*|formlær\w*|formlär\w*|"
    r"design research\w*|research through design|research by design|constructive design|"
    r"practice-based design|practice-led design|"
    r"design method\w*|design methodology|design process\w*|design practice\w*|design studio\w*|"
    r"design pedagog\w*|design education|design didact\w*|designdidakt\w*|designpedagog\w*|"
    r"designforsk\w*|muotoilututkimu\w*|"
    r"participatory design|cooperative design|co-design\w*|codesign\w*|"
    r"scandinavian design|nordic design|danish design|swedish design|finnish design|norwegian design|icelandic design|"
    r"user-cent(?:e)?red design|human-cent(?:e)?red design|"
    r"interaction design\w*|service design\w*|systemic design|systems-oriented design|"
    r"transition design|sustainable design|circular design|ecological design|eco-design|"
    r"universal design|inclusive design|design anthropolog\w*|design histor\w*|history of design|"
    r"industrial design\w*|graphic design\w*|visual communication design|"
    r"information design|textile design\w*|fashion design\w*|furniture design|craft research|"
    r"material-driven design|experiential design|sonic interaction design|"
    r"tjenestedesign\w*|tjänstedesign\w*|"
    r"interaksjonsdesign\w*|interaktionsdesign\w*|industridesign\w*|"
    r"brukskunst\w*|kunsthåndverk\w*|kunsthandverk\w*|kunsthåndværk\w*|konsthantverk\w*|"
    r"formgivning\w*|formgiving\w*|formgjeving\w*|"
    r"muotoilu\w*|palvelumuotoilu\w*|teollinen muotoilu|taideteollisu\w*|yhteissuunnittelu\w*|"
    r"hönnun\w*|vöruhönnun\w*|þjónustuhönnun\w*"
    r")\b",
    re.I,
)

CANON_NOISE_RE = re.compile(
    r"\b(?:thematic analysis in psychology|harvard business review|prisma|"
    r"dominant logic for marketing|service-dominant logic|patient education|"
    r"nervous and mental|choice reviews|universitas komputer|policy analysis and management|"
    r"american dietetic|firm performance)\b",
    re.I,
)


def clean_display_title(raw: object) -> str:
    txt = html.unescape(str(raw or ""))
    txt = re.sub(r"<[^>]+>", "", txt)
    return re.sub(r"\s+", " ", txt).strip()


def load_semantic_gate_scores(
    raw_sqlite: Path = RAW_SQLITE,
    vec_cache: Path | None = None,
) -> dict[str, float]:
    """Compute cosine similarity of cached Google EmbeddingGemma-300M vectors to the flagship Design Theory centroid."""
    cache_file = vec_cache or (PRIVATE_CACHE / "work_vector_cache.sqlite")
    if not cache_file.is_file() or not Path(raw_sqlite).is_file():
        return {}
    try:
        vconn = sqlite3.connect(cache_file)
        vecs: dict[str, np.ndarray] = {}
        for wid, blob in vconn.execute("SELECT work_id, vector FROM work_vectors"):
            arr = np.frombuffer(blob, dtype="<f4")
            norm = float(np.linalg.norm(arr))
            if norm > 1e-9:
                vecs[wid] = arr / norm
        vconn.close()
        if not vecs:
            return {}

        rconn = sqlite3.connect(raw_sqlite)
        seeds = [
            vecs[wid]
            for wid, sid in rconn.execute("SELECT id, source_id FROM works")
            if (sid or "").rsplit("/", 1)[-1] in PURE_DESIGN_VENUES and wid in vecs
        ]
        rconn.close()
        if len(seeds) < 20:
            return {}
        centroid = np.mean(seeds, axis=0)
        cnorm = float(np.linalg.norm(centroid))
        if cnorm <= 1e-9:
            return {}
        centroid = centroid / cnorm
        return {wid: float(vec @ centroid) for wid, vec in vecs.items()}
    except Exception:
        return {}


def evaluate_strict_design_scope(
    title: str,
    countries: list[str],
    source_id: str = "",
    source_name: str = "",
    raw_json_str: str = "",
    semantic_cos: float | None = None,
) -> tuple[int, str]:
    """Return (1, rationale) iff the work is strictly Nordic design theory / design research."""
    if not countries:
        return 0, "Missing Nordic country affiliation"
    t = clean_display_title(title)
    s = str(source_name or "").strip()
    if not t or HARD_NON_DESIGN_RE.search(t) or FORBIDDEN_VENUES_RE.search(s):
        return 0, "Excluded non-design domain or methodology term"

    short_sid = (source_id or "").rsplit("/", 1)[-1]
    in_pure_venue = (short_sid in PURE_DESIGN_VENUES) or bool(DEDICATED_VENUE_NAMES_RE.search(s))
    if in_pure_venue:
        return 1, "Dedicated design theory and research venue"

    subfield = ""
    topic = ""
    if raw_json_str and raw_json_str != "{}":
        try:
            d = json.loads(raw_json_str)
            pt = d.get("primary_topic") or {}
            subfield = (pt.get("subfield") or {}).get("display_name") or ""
            topic = pt.get("display_name") or ""
        except Exception:
            pass

    if subfield not in ALLOWED_NON_VENUE_SUBFIELDS and topic not in CORE_DESIGN_TOPICS:
        return 0, "Excluded non-design academic subfield"

    if semantic_cos is not None and semantic_cos < 0.60:
        return 0, "Below Google EmbeddingGemma design-theory semantic threshold"

    if STRICT_DESIGN_THEORY_RE.search(t):
        return 1, "Explicit design theory or design research title"
    if topic == "Design Education and Practice" and re.search(r"\bdesign\w*\b", t, re.I):
        return 1, "Core OpenAlex design research topic and title"

    return 0, "Outside strict design theory and design research scope"


def is_strict_nordic_archive_work(
    title: str,
    source_name: str = "",
    venue: str = "",
    semantic_cos: float | None = None,
) -> bool:
    t = clean_display_title(title)
    s = f"{source_name or ''} {venue or ''}".strip()
    if not t or HARD_NON_DESIGN_RE.search(t) or FORBIDDEN_VENUES_RE.search(s):
        return False
    in_pure_venue = bool(DEDICATED_VENUE_NAMES_RE.search(s)) or ("nordes" in s.lower())
    if in_pure_venue:
        return True
    if semantic_cos is not None and semantic_cos < 0.62:
        return False
    return bool(STRICT_DESIGN_THEORY_RE.search(t))
