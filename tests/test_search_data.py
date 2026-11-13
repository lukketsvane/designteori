"""Tests of the site search data (docs/data/search/) and of the builder and reference search.

Uses only the published files plus the existing docs/data and pdf/manifest.json (CI safe). Tests that need the raw sqlite
or the private cache are skipped when those files are missing.
"""
from __future__ import annotations

import base64
import collections
import gzip
import json
import math
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from designteori import DOCS_DATA_DIR, DOCS_DIR, PDF_DIR, RAW_SQLITE, ROOT, normalize_title, read_json, write_json
from designteori import search_build as sb
from designteori import search_eval as se
from designteori.pdf import HOST_DENY, allowed_url, has_explicit_open_license, safe_public_link

SEARCH = sb.SEARCH_DIR
FIXTURES = ROOT / "tests" / "fixtures" / "search"
HAVE_META = (SEARCH / "meta.json").is_file()


def _meta():
    return read_json(SEARCH / "meta.json")


def _works():
    return (read_json(DOCS_DATA_DIR / "publications.json") or []) + (read_json(DOCS_DATA_DIR / "nordic_additions.json") or [])


class TestTextUtilities(unittest.TestCase):
    def test_fold_and_tokenize_fixture(self):
        cases = read_json(FIXTURES / "tokenizer_cases.json")["cases"]
        self.assertGreaterEqual(len(cases), 40)
        for c in cases:
            self.assertEqual(sb.tokenize(c["in"]), c["tokens"], c["in"])

    def test_required_foldings(self):
        self.assertEqual(sb.tokenize("Malmö"), ["malmo"])
        self.assertEqual(sb.tokenize("håndverk"), ["handverk"])
        self.assertEqual(sb.tokenize("Æble"), ["aeble"])
        self.assertEqual(sb.tokenize("İstanbul"), ["istanbul"])
        self.assertEqual(sb.tokenize("co-design"), ["co", "design"])
        self.assertEqual(sb.tokenize("web3 a 1983"), ["web3", "1983"])

    def test_query_key(self):
        self.assertEqual(sb.query_key("  Service   DESIGN \n"), "service design")
        self.assertEqual(sb.query_key("service design."), "service design.")  # no punctuation stripping, by design

    def test_clean_abstract_keeps_angle_brackets_in_text(self):
        raw = "<jats:p>If design was <like this>, then <i>interaction</i> would be <b>that</b>.</jats:p>\n  Second   line"
        self.assertEqual(sb.clean_abstract(raw), "If design was <like this>, then interaction would be that . Second line".replace("that .", "that."))

    def test_detect_lang_and_codes(self):
        self.assertEqual(sb.detect_lang("This is a study of the design of services for the public sector in the Nordic countries"), "en")
        self.assertEqual(sb.detect_lang("Dette er ei studie av korleis ein kan involvere innbyggjarar og kva det betyr for tenestene"), "nn")
        self.assertEqual(sb.detect_lang("Dette er en studie av hvordan vi kan involvere innbyggerne og hva det betyr for tjenestene"), "nb")
        self.assertEqual(sb.abstract_lang("xyz"), "und")
        self.assertEqual(sb.derive_lang({"language": "no", "title": "Design"}, None), "b")
        self.assertEqual(sb.derive_lang({"language": "de", "title": "x"}, None), "o")
        self.assertEqual(sb.derive_lang({"title": "Servicedesign i offentleg sektor og korleis ein kan bruke det i praksis"}, None), "n")
        self.assertEqual(sb.derive_lang({"title": "Design", "language": None}, {"t": "x", "l": "da", "s": "oa"}), "d")
        self.assertEqual(sb.derive_lang({"title": "x"}, None), "u")


class TestExtractionRules(unittest.TestCase):
    GOOD = ("Abstract\nThis paper studies how designers and public servants work together to change a municipal service. "
            "We followed three projects over two years and describe the practices that made collaboration possible. "
            "The findings show that shared artefacts, regular meetings and a common vocabulary were more important than formal roles. "
            "We discuss what this means for the design of public services and for research on participatory design in practice. "
            "Implications for education and for policy are drawn from the cases and compared with earlier studies of similar work.\n"
            "Keywords: service design\n1 Introduction\nText")

    def test_accepts_clean_abstract(self):
        text, reason = sb.extract_abstract([self.GOOD])
        self.assertEqual(reason, "")
        self.assertTrue(text.startswith("This paper studies"))
        self.assertNotIn("Keywords", text)
        self.assertTrue(300 <= len(text) <= 2500)

    def test_rejects_short_and_noisy(self):
        self.assertEqual(sb.extract_abstract(["Abstract\nToo short.\nKeywords: a"])[1], "too-short")
        self.assertEqual(sb.extract_abstract(["Just some page without heading"])[1], "no-heading")
        long_text = "Abstract\n" + ("This is a sentence about design research. " * 80) + "\n"
        self.assertEqual(sb.extract_abstract([long_text])[1], "too-long")
        bad = self.GOOD.replace("service", "serv�ce")
        self.assertEqual(sb.extract_abstract([bad])[1], "fffd")
        noend = self.GOOD.replace("similar work.", "similar work and")
        self.assertEqual(sb.extract_abstract([noend])[1], "bad-ending")

    def test_rejects_header_and_footer_residue(self):
        cases = {
            "residue-email": "Contact the author at name@example.com for details.",
            "residue-isbn": "Published as ISBN 978-91-506-3193-7 by the department.",
            "residue-header-status": "Received 17 January 2025 and accepted later.",
            "residue-copyright": "All text is covered by © 2015 the publisher.",
            "residue-url": "More material is at www.example.org/staff/name.",
        }
        for reason, extra in cases.items():
            text = self.GOOD.replace("Implications for education", extra + " Implications for education")
            self.assertEqual(sb.extract_abstract([text])[1], reason, reason)
        # ordinary words that look like the header words must pass
        ok = self.GOOD.replace("similar work.", "similar work, which received praise and was accepted by the partners.")
        self.assertEqual(sb.extract_abstract([ok])[1], "")

    def test_repairs_line_break_hyphens(self):
        vocab = {"latest", "wellbeing"}
        fixed = sb.fix_hyphen_breaks("the lat- est network- based well- being kunst- og Human- Centred pre- and", vocab)
        self.assertEqual(fixed, "the latest network-based wellbeing kunst- og Human-Centred pre- and")
        self.assertEqual(sb.fix_hyphen_breaks("x lat- est", None), "x lat-est")
        text, reason = sb.extract_abstract([self.GOOD.replace("shared artefacts", "shared arte-\nfacts")], {"artefacts"})
        self.assertEqual(reason, "")
        self.assertIn("shared artefacts", text)

    def test_rejects_block_that_starts_mid_sentence(self):
        text = self.GOOD.replace("Abstract\nThis paper studies", "Abstract\nthis paper studies")
        self.assertEqual(sb.extract_abstract([text])[1], "starts-lowercase")

    def test_rejects_two_column_mess(self):
        lines = ["Abstract"]
        for i in range(14):
            lines += ["This design study looks at", "how", "people work together on shared services in cities and towns across the region."]
        text, reason = sb.extract_abstract(["\n".join(lines)])
        self.assertEqual(text, "")
        self.assertIn(reason, ("columns", "too-long"))


class TestAccessAndDuplicates(unittest.TestCase):
    def test_classification_rules(self):
        works = [
            {"id": "W1", "doi": "https://doi.org/10.1/x", "oa_url": "https://doi.org/10.1/x", "_layer": "openalex"},
            {"id": "W2", "doi": "", "oa_url": "https://example.org/paper.pdf", "_layer": "openalex"},
            {"id": "W3", "doi": "", "oa_url": "", "_layer": "openalex"},
            {"id": "W4", "doi": "https://doi.org/10.1/y", "oa_url": "https://example.org/landing", "_layer": "openalex"},
            {"id": "nordic:a:1", "doi": "", "oa_url": "https://doi.org/10.2/z", "source_url": "", "_layer": "nordic"},
            {"id": "W5", "doi": "", "oa_url": "https://sci-hub.se/x", "_layer": "openalex"},
            {"id": "W6", "doi": "", "oa_url": "", "_layer": "openalex"},
            {"id": "W7", "doi": "", "oa_url": "", "_layer": "openalex"},
        ]
        manifest = {"W6": {"license": "CC BY 4.0", "sha256": "a" * 64}}
        found = {"W7": {"url": "https://example.org/w7.pdf", "status": "verified-oa-link", "sha256": "b" * 64},
                 "W6": {"url": "https://example.org/w6.pdf", "status": "in-repo-pdf", "sha256": "a" * 64}}
        acc = sb.classify_access(works, manifest, found)
        self.assertEqual([a["acc"] for a in acc], ["d", "u", "0", "u", "d", "0", "h", "v"])
        self.assertEqual(acc[3]["url"], "https://example.org/landing")
        self.assertEqual(acc[6]["url"], f"{sb.REPO_RAW_BASE}/pdf/W6.pdf")
        self.assertEqual(acc[4]["url"], "https://doi.org/10.2/z")  # DOI-only archive work keeps its only public address

    def test_duplicate_groups(self):
        def w(i, title, year, authors, layer="nordic", **kw):
            d = {"id": i, "title": title, "year": year, "authors": authors, "_layer": layer}
            d.update(kw)
            return d

        works = [
            w("W1", "Service design in practice", 2018, ["Anna Seravalli"], "openalex", citations=5),
            w("nordic:nva:1", "Service Design in Practice.", 2019, ["Seravalli, Anna"]),
            w("nordic:nva:2", "Service design in practice", 2018, ["Other, Person"]),      # no shared surname
            w("nordic:nva:3", "Service design in practice", 2030, ["Seravalli, Anna"]),    # year too far
            w("nordic:nva:4", "Another title", 2018, ["X, Y"], duplicate_status="possible-duplicate"),
            w("nordic:nva:5", "Twin", 2010, ["Kim, Min Jae"]),
            w("nordic:nva:6", "Twin", 2010, ["Min Jae Kim"]),
        ]
        acc = [{"acc": "u"}] * 7
        flags, info = sb.possible_duplicates(works, acc)
        self.assertEqual(flags, [False, True, False, False, True, False, True])
        self.assertEqual(info["archive_status"], 1)
        self.assertEqual(info["title_extra_rows"], 2)
        self.assertEqual(info["title_groups"], 2)


def _tiny_index(tmp: Path, cfg_extra: dict | None = None) -> se.Index:
    works = [
        {"id": "W1", "title": "Sustainability in design practice", "authors": ["A One"], "source": "Journal One"},
        {"id": "W2", "title": "Design for sustainability and service design", "authors": ["B Two"], "source": "Design Studies"},
        {"id": "W3", "title": "Tacit knowledge in craft", "authors": ["C Three"], "source": "Craft Journal"},
        {"id": "W4", "title": "Participatory design in the public sector", "authors": ["D Four"], "source": "CoDesign"},
        {"id": "W5", "title": "Participants and participation", "authors": ["E Five"], "source": "Design Issues"},
        {"id": "W6", "title": "Handverk og kunnskap", "authors": ["F Six"], "source": "Form"},
    ]
    for w in works:
        w["_layer"] = "openalex"
    cfg = sb.build_config()
    if cfg_extra:
        cfg.update(cfg_extra)
    lex, _ = sb.build_lex(works, {"W3": "An abstract about tacit knowledge and craft skill"}, {}, set(cfg["stopwords"]))
    d = Path(tmp)
    write_json(d / "search_config.json", cfg, compact=True)
    write_json(d / "lex.json", lex, compact=True)
    n = len(works)
    write_json(d / "meta.json", {"schema": 1, "n": n, "ids": [w["id"] for w in works], "acc": "0" * n, "flag": "0" * n,
                                 "lang": "e" * n, "abs": "0" * n, "similar": None, "vectors": None}, compact=True)
    return se.Index(d)


class TestReferenceSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.idx = _tiny_index(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_postings_roundtrip_and_bm25(self):
        idx = self.idx
        j = idx.term_ix["tacit"]
        docs, tf = idx.postings(j)
        self.assertEqual(docs.tolist(), [2])
        self.assertEqual(tf.tolist(), [4 + 1])  # title weight 4 + abstract weight 1
        df, n = 1, idx.n
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        dl = idx.doclen[2]
        expect = idf * 5 * 2.2 / (5 + 1.2 * (1 - 0.75 + 0.75 * dl / idx.avgdl))
        d, v = idx.term_values(j)
        self.assertAlmostEqual(float(v[0]), expect, places=12)

    def test_morphology_group(self):
        idx = self.idx
        terms = {idx.terms[j]: w for j, w in idx.expand("sustainable")}
        self.assertIn("sustainability", terms)
        self.assertEqual(terms["sustainability"], 0.8)
        part = {idx.terms[j]: w for j, w in idx.expand("participation")}
        self.assertEqual(part["participation"], 1.0)
        self.assertEqual(part.get("participatory"), 0.8)
        self.assertEqual({idx.terms[j]: w for j, w in idx.expand("designs")}["design"], 1.0)

    def test_search_finds_morphological_variant(self):
        top = self.idx.lexical("sustainable design", glossary=False)
        self.assertIn(1, top[:2])  # "Design for sustainability" has both groups covered

    def test_glossary_covers_core_tokens_and_adds_english(self):
        idx = self.idx
        core = idx.core_tokens("taus kunnskap i handverk")
        self.assertEqual(core, ["taus", "kunnskap", "handverk"])
        toks = {g["token"]: g["sources"] for g in idx.glossary_groups(core)}
        self.assertIn("tacit", toks)
        self.assertIn("craft", toks)
        self.assertIn("knowledge", toks)
        self.assertEqual(toks["tacit"], {0, 1})
        score, dek = idx.lexical_scores("taus kunnskap i handverk")
        self.assertEqual(int(np.argmax(score)), 2)           # the English tacit-knowledge-craft title wins
        self.assertAlmostEqual(float(dek[2]), 1.0)

    def test_glossary_phrase_bonus_only_when_entry_covers_whole_query(self):
        idx = self.idx
        titles = ["Sustainability in design practice", "Design for sustainability and service design", "Tacit knowledge in craft",
                  "Participatory design in the public sector", "Participants and participation", "Handverk og kunnskap"]
        idx._titles = [" " + " ".join(sb.tokenize(t)) + " " for t in titles]
        try:
            plain, _ = idx.lexical_scores("tenestedesign", phrase=False)
            boosted, _ = idx.lexical_scores("tenestedesign", phrase=True)
            diff = boosted - plain
            self.assertAlmostEqual(float(diff[1]), se.PHRASE_BONUS)   # "service design" stands in the title
            self.assertEqual(float(np.abs(np.delete(diff, 1)).sum()), 0.0)
            plain2, _ = idx.lexical_scores("tenestedesign blomar", phrase=False)
            boosted2, _ = idx.lexical_scores("tenestedesign blomar", phrase=True)
            self.assertEqual(float(np.abs(boosted2 - plain2).sum()), 0.0)  # the entry covers only one of two core tokens
        finally:
            idx._titles = None

    def test_glossary_collision_with_mote(self):
        core = self.idx.core_tokens("møte med brukarar")
        self.assertNotIn("fashion", [g["token"] for g in self.idx.glossary_groups(core)])

    def test_all_stopword_query_is_kept_and_rrf(self):
        self.assertEqual(self.idx.core_tokens("the of and"), ["the", "of", "and"])
        fused = se.Index.rrf([([5, 6, 7], 1.0), ([6, 5, 9], 1.0)])
        self.assertEqual(fused[:2], [5, 6])  # equal score, lowest position first
        r = {d: 1.0 / (60 + k) for k, d in enumerate([5, 6, 7], start=1)}
        self.assertTrue(r[5] > r[7])

    def test_metrics(self):
        self.assertEqual(se.recall_at([1, 2, 3], {1, 3}), 1.0)
        self.assertEqual(se.recall_at([1, 2, 3], set(range(20)), 10), 0.3)
        self.assertEqual(se.first_rank([4, 5, 6], {6}), 3)

    def test_candidate_pool_for_sorting(self):
        pool = self.idx.candidate_pool("sustainable design")
        self.assertIn(1, pool)


@unittest.skipUnless(HAVE_META, "docs/data/search/meta.json is missing")
class TestPublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = _meta()
        cls.works = _works()
        cls.n = len(cls.works)

    def test_meta_shape(self):
        m = self.meta
        self.assertEqual(m["schema"], 1)
        self.assertEqual(m["n"], 6432)
        self.assertEqual(m["ids"], [w["id"] for w in self.works])
        for k in ("lang", "abs", "acc", "flag"):
            self.assertEqual(len(m[k]), self.n, k)
        self.assertLessEqual(len(json.dumps(m)), 200_000)
        self.assertLessEqual(len(gzip.compress((SEARCH / "meta.json").read_bytes())), 70_000)

    def test_file_hashes_and_build_id(self):
        files = self.meta["files"]
        self.assertTrue(files)
        for name, info in files.items():
            p = SEARCH / name
            self.assertEqual(p.stat().st_size, info["bytes"], name)
            self.assertEqual(sb.sha256_file(p), info["sha256"], name)
        self.assertEqual(sb.build_id_of(files), self.meta["build_id"])

    def test_file_size_limits(self):
        for p in SEARCH.rglob("*"):
            if p.is_file():
                limit = sb.LEX_MAX_BYTES if p.name == "lex.json" else 2_000_000
                self.assertLessEqual(p.stat().st_size, limit, p.name)
        self.assertLessEqual(len(gzip.compress((SEARCH / "lex.json").read_bytes(), 6)), sb.LEX_MAX_GZIP)

    def test_counts_recomputed_from_sources(self):
        manifest = (read_json(PDF_DIR / "manifest.json") or {}).get("items") or {}
        found = read_json(DOCS_DATA_DIR / "pdf_found.json")
        works = [dict(w, _layer="openalex" if not w["id"].startswith("nordic:") else "nordic") for w in self.works]
        acc = sb.classify_access(works, manifest, found)
        counts = collections.Counter(a["acc"] for a in acc)
        stored = self.meta["counts"]["acc"]
        for k in "hvud0":
            self.assertEqual(stored[k], counts.get(k, 0), k)
        self.assertEqual("".join(a["acc"] for a in acc), self.meta["acc"])
        self.assertEqual(sum(stored.values()), 6432)
        self.assertEqual(stored["h"], 23)
        self.assertEqual(stored["v"], 3239)
        self.assertEqual(stored["0"], 344)
        self.assertEqual(stored["h"] + stored["v"], 3262)
        self.assertEqual(self.meta["counts"]["pdf_verified_total"], 3262)
        flags, info = sb.possible_duplicates(works, acc)
        self.assertEqual(sum(flags), self.meta["counts"]["flag"]["d"])
        for k in ("layers", "abs", "lang", "flag", "year_range", "sources"):
            self.assertIn(k, self.meta["counts"])
        self.assertEqual(sum(self.meta["counts"]["lang"].values()), 6432)
        self.assertEqual(self.meta["counts"]["layers"], {"openalex": 4694, "nordic": 1738})

    def test_about_equals_meta_counts(self):
        a = read_json(SEARCH / "about.json")
        c = self.meta["counts"]
        self.assertEqual(a["total"], 6432)
        self.assertEqual(a["layers"], c["layers"])
        self.assertEqual(a["sources"], c["sources"])
        self.assertEqual(a["year_range"], c["year_range"])
        self.assertEqual(a["languages"], c["lang"])
        self.assertEqual({"h": a["access"]["h"], "v": a["access"]["v"], "u": a["access"]["u"], "d": a["access"]["d"], "0": a["access"]["none"]}, c["acc"])
        self.assertEqual((a["abstracts"]["oa"], a["abstracts"]["x"], a["abstracts"]["none"]), (c["abs"]["o"], c["abs"]["x"], c["abs"]["0"]))
        self.assertEqual(a["review"]["possible_duplicates"], c["flag"]["d"])
        self.assertEqual(a["pdf_verified_total"], c["pdf_verified_total"])
        self.assertEqual(a["review"]["human_checked"], 0)
        self.assertEqual(a["review"]["affiliation_unknown"], 408)
        self.assertEqual(a["review"]["archive_possible_duplicates"], 125)
        self.assertEqual(a["year_range"][0], 1983)

    def test_lex_structure_and_bm25_samples(self):
        lex = read_json(SEARCH / "lex.json")
        n = lex["n"]
        terms = lex["terms"]
        self.assertEqual(terms, sorted(terms))
        self.assertEqual(len(set(terms)), len(terms))
        self.assertTrue(all(re.fullmatch(r"[a-z0-9]{2,}", t) for t in terms))
        self.assertEqual(len(lex["doclen"]), n)
        self.assertAlmostEqual(lex["avgdl"], sum(lex["doclen"]) / n, places=9)
        sums = [0] * n
        for t, flat in zip(terms, lex["post"]):
            d = 0
            for k in range(0, len(flat), 2):
                d += flat[k]
                tf = flat[k + 1]
                self.assertTrue(0 <= d < n)
                self.assertTrue(1 <= tf <= 255)
                sums[d] += tf
        self.assertEqual(sums, lex["doclen"])
        cfg = read_json(SEARCH / "search_config.json")
        self.assertFalse(set(cfg["stopwords"]) & set(terms))
        idx = se.Index(with_vectors=False)
        for term in ("infrastructuring", "tacit", "malmo"):
            j = idx.term_ix[term]
            docs, tf = idx.postings(j)
            df = len(docs)
            d = int(docs[len(docs) // 2])
            f = float(tf[len(docs) // 2])
            expect = math.log(1 + (n - df + 0.5) / (df + 0.5)) * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * lex["doclen"][d] / lex["avgdl"]))
            got = dict(zip(*idx.term_values(j)))[d]
            self.assertAlmostEqual(got, expect, places=12)

    def test_config(self):
        cfg = read_json(SEARCH / "search_config.json")
        self.assertEqual([e["q"] for e in cfg["examples"]], [e["q"] for e in sb.search_terms.EXAMPLES])
        self.assertEqual(len(cfg["examples"]), 10)
        self.assertGreaterEqual(len(cfg["glossary"]), 120)
        self.assertTrue(200 <= len(cfg["stopwords"]) <= 300)
        self.assertEqual(cfg["stopwords"], sorted(set(cfg["stopwords"])))
        for protected in ("design", "research", "practice", "user", "service", "public", "participation", "craft", "method"):
            self.assertNotIn(protected, cfg["stopwords"])
        for e in cfg["glossary"]:
            self.assertEqual(e["w"], 1.0)
        # one-token Norwegian words that fold to another word must not trigger an expansion (collision check)
        for e in cfg["glossary"]:
            for phrase in e["from"]:
                self.assertNotEqual(phrase, ["mote"])
        idx = se.Index(with_vectors=False)
        expect = {
            "taus kunnskap": "tacit", "tyst kunnskap": "tacit", "handverk": "craft", "håndverk": "craft", "hantverk": "craft",
            "håndværk": "craft", "tenestedesign": "service", "tjenestedesign": "service", "tjänstedesign": "service",
            "offentleg sektor": "sector", "offentlige sektor": "sector", "deltaking": "participation", "deltakelse": "participation",
            "deltagelse": "participation", "deltagande": "participation", "medverknad": "involvement", "medvirkning": "involvement",
            "berekraftig": "sustainability", "bærekraftig": "sustainability", "bæredygtig": "sustainability", "hållbar": "sustainability",
            "innbyggjar": "citizen", "innbygger": "citizen", "borger": "citizen", "medborgar": "citizen", "brukar": "user",
            "bruker": "user", "användare": "user", "forsking": "research", "forskning": "research", "designforsking": "design",
            "formgjeving": "design", "formgivning": "design", "formgivare": "design", "utdanning": "education",
            "utbildning": "education", "uddannelse": "education", "eldre": "elderly", "aldring": "ageing", "äldre": "elderly",
            "born": "children", "barn": "children", "børn": "children", "omsorg": "care", "omsorgsarbeid": "care",
            "velferdsteknologi": "welfare", "arkitektur": "architecture", "samskaping": "creation", "samskapning": "creation",
            "samdesign": "co", "medskaping": "co", "infrastruktur": "infrastructuring", "kroppsleg": "embodied",
            "kroppslig": "embodied", "kropp": "body", "praksis": "practice", "praksisbasert": "practice", "verktøy": "tool",
            "kunst": "art", "moda": "fashion", "tekstil": "textile", "leik": "play", "lek": "play", "kunnskap": "knowledge",
        }
        for q, token in expect.items():
            groups = {g["token"] for g in idx.glossary_groups(idx.core_tokens(q))}
            self.assertIn(token, groups, q)

    def test_glossary_json(self):
        g = read_json(SEARCH / "glossary.json")["terms"]
        self.assertGreaterEqual(len(g), 25)
        for t in g:
            for k in ("id", "term", "nn", "en", "no", "q"):
                self.assertTrue(t[k], k)
            self.assertLessEqual(len(re.findall(r"[.!?](?:\s|$)", t["nn"])), 3)
        required = ["research through design", "infrastructuring", "taus kunnskap", "deltakande design", "samdesign", "tenestedesign",
                    "spekulativt design", "kritisk design", "designtenking", "handverk", "materialitet", "designantropologi",
                    "levande laboratorium", "berekraftig design", "overgangsdesign", "design for omsorg", "brukarmedverknad",
                    "designforsking", "praksisbasert forsking", "forskingsdesign", "designpedagogikk", "kanon"]
        have = {t["term"] for t in g}
        for r in required:
            self.assertIn(r, have, r)

    def test_tokenizer_fixture_matches_published_cases(self):
        cases = read_json(FIXTURES / "tokenizer_cases.json")["cases"]
        self.assertGreaterEqual(len(cases), 40)

    def test_abstract_shards_and_rights(self):
        shards = sorted((SEARCH / "abstracts").glob("a*.json"))
        self.assertEqual(len(shards), math.ceil(self.n / sb.SHARD_SIZE))
        manifest = (read_json(PDF_DIR / "manifest.json") or {}).get("items") or {}
        found = read_json(DOCS_DATA_DIR / "pdf_found.json")
        pos = {w: i for i, w in enumerate(self.meta["ids"])}
        n_abs = 0
        sources = collections.Counter()
        for k, p in enumerate(shards):
            data = read_json(p)
            for wid, rec in data.items():
                self.assertEqual(pos[wid] // sb.SHARD_SIZE, k)
                n_abs += 1
                self.assertIn(rec["s"], ("oa", "x"))
                self.assertIn(rec["l"], ("en", "nb", "nn", "da", "sv", "fi", "de", "und"))
                self.assertTrue(rec["t"].strip())
                self.assertLessEqual(len(rec["t"]), 5000)
                self.assertNotIn("<jats", rec["t"])
                sources[rec["s"]] += 1
                i = pos[wid]
                self.assertEqual(self.meta["abs"][i], "o" if rec["s"] == "oa" else "x")
                if rec["s"] == "oa":                       # R5
                    self.assertTrue(wid.startswith("W"))
                    self.assertGreaterEqual(len(rec["t"]), 50)
                    self.assertNotIn("u", rec)
                else:                                      # R6: extraction only with a verified open PDF or licence
                    self.assertIn(self.meta["acc"][i], "hv")
                    self.assertTrue(wid in manifest or (wid in found and found[wid]["status"] == "verified-oa-link"))
                    self.assertTrue(300 <= len(rec["t"]) <= 2500)
                    self.assertLessEqual(len(rec["t"]), 2500)
                    self.assertNotIn("�", rec["t"])
                    expected_url = self.access_url(wid)
                    self.assertEqual(rec["u"], expected_url)
        self.assertEqual(n_abs, sum(1 for c in self.meta["abs"] if c != "0"))
        self.assertEqual(sources["oa"], self.meta["counts"]["abs"]["o"])
        self.assertEqual(sources["x"], self.meta["counts"]["abs"]["x"])
        report = read_json(SEARCH / "abstracts_report.json")
        self.assertEqual(report["abstracts"]["x"], sources["x"])
        self.assertEqual(report["extraction"]["sha_mismatch"], 0)

    def access_url(self, wid: str) -> str:
        items = read_json(SEARCH / "access.json")["items"]
        return items[wid][1]

    def test_access_file_rules(self):
        items = read_json(SEARCH / "access.json")["items"]
        manifest = (read_json(PDF_DIR / "manifest.json") or {}).get("items") or {}
        found = read_json(DOCS_DATA_DIR / "pdf_found.json")
        by_id = {w["id"]: w for w in self.works}
        pos = {w: i for i, w in enumerate(self.meta["ids"])}
        counts = collections.Counter()
        for wid, row in items.items():
            code, url = row[0], row[1]
            counts[code] += 1
            self.assertEqual(self.meta["acc"][pos[wid]], code)
            self.assertFalse(any(b in url.lower() for b in HOST_DENY))
            if code == "h":                                                    # R2
                self.assertIn(wid, manifest)
                self.assertTrue(has_explicit_open_license(row[2]))
                self.assertEqual(url, f"https://raw.githubusercontent.com/lukketsvane/designteori/main/pdf/{wid}.pdf")
            elif code == "v":                                                  # R3
                self.assertEqual(url, found[wid]["url"])
                self.assertEqual(found[wid]["status"], "verified-oa-link")
                self.assertTrue(safe_public_link(url))
            elif code == "u":                                                  # R4
                w = by_id[wid]
                self.assertIn(url, (w.get("oa_url"), w.get("source_url")))
                self.assertTrue(allowed_url(url))
                self.assertFalse(url.lower().startswith("https://doi.org/"))
                self.assertNotEqual(url, w.get("doi"))
            elif code == "d":
                self.assertTrue(url.startswith("https://doi.org/"))
            else:
                self.fail(code)
        for k in "hvu":
            self.assertEqual(counts[k], self.meta["counts"]["acc"][k], k)
        for wid, c in zip(self.meta["ids"], self.meta["acc"]):
            if c in "hvu":
                self.assertIn(wid, items)
            if c == "d":
                w = by_id[wid]
                self.assertTrue(w.get("doi") or wid in items, wid)

    def test_no_private_text_or_pdfs_in_docs(self):                            # R1, R8
        for p in DOCS_DIR.rglob("*.pdf"):
            self.fail(f"PDF under docs: {p}")
        for p in SEARCH.rglob("*"):
            if p.is_file():
                self.assertNotIn(b"designteori-pdf-cache", p.read_bytes()[:5_000_000], p.name)
        try:
            out = subprocess.run(["git", "ls-files", "pdf"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return
        if out.returncode != 0 or not out.stdout.strip():
            return
        manifest = (read_json(PDF_DIR / "manifest.json") or {}).get("items") or {}
        allowed = {"pdf/manifest.json"} | {v.get("file") for v in manifest.values()}
        for line in out.stdout.split():
            self.assertIn(line, allowed)

    def test_duplicate_flags_and_hidden_count(self):
        flags = self.meta["flag"]
        self.assertEqual(flags.count("d"), self.meta["counts"]["flag"]["d"])
        n_status = sum(1 for w in self.works if w.get("duplicate_status") == "possible-duplicate")
        self.assertEqual(n_status, 125)
        for i, w in enumerate(self.works):
            if w.get("duplicate_status") == "possible-duplicate":
                self.assertEqual(flags[i], "d")
        for i, w in enumerate(self.works):
            if flags[i] == "u":
                self.assertFalse(w.get("countries") or w.get("source_country"))
                self.assertTrue(w["id"].startswith("nordic:"))

    @unittest.skipUnless(RAW_SQLITE.is_file(), "raw sqlite is missing")
    def test_oa_abstracts_equal_source_after_tag_removal(self):
        oa = sb.load_openalex_abstracts()
        pos = {w: i for i, w in enumerate(self.meta["ids"])}
        n = 0
        for p in sorted((SEARCH / "abstracts").glob("a*.json")):
            for wid, rec in read_json(p).items():
                if rec["s"] == "oa":
                    self.assertEqual(rec["t"], oa[wid], wid)
                    n += 1
        self.assertEqual(n, len([1 for t in oa.values() if len(t) <= sb.MAX_ABSTRACT_CHARS]))


@unittest.skipUnless(HAVE_META and (SEARCH / "vectors.i8").is_file(), "vectors.i8 is missing")
class TestVectorsAndNeighbours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = _meta()
        cls.n = cls.meta["n"]
        cls.V = np.frombuffer((SEARCH / "vectors.i8").read_bytes(), dtype=np.int8).reshape(cls.n, 256)

    def test_vectors(self):
        self.assertEqual((SEARCH / "vectors.i8").stat().st_size, 1_646_592)
        norm = np.linalg.norm(self.V.astype(np.float64) / 127.0, axis=1)
        self.assertLess(float(np.abs(norm - 1).max()), 0.02)
        self.assertFalse(np.any(np.all(self.V == 0, axis=1)))
        self.assertEqual(self.meta["vectors"]["dim"], 256)

    def test_text_hash_is_from_published_text(self):                           # R10
        works = _works()
        shard = {}
        for p in sorted((SEARCH / "abstracts").glob("a*.json")):
            shard.update(read_json(p))
        self.assertEqual(sb.text_sha256(works, shard), self.meta["vectors"]["text_sha256"])

    @unittest.skipUnless((SEARCH / "similar.bin").is_file(), "similar.bin is missing")
    def test_similar_bin(self):
        raw = (SEARCH / "similar.bin").read_bytes()
        n, k = self.n, 20
        self.assertEqual(len(raw), 385_920)
        idx = np.frombuffer(raw[: n * k * 2], dtype="<u2").reshape(n, k).astype(np.int64)
        sim = np.frombuffer(raw[n * k * 2:], dtype=np.uint8).reshape(n, k).astype(np.int64)
        self.assertTrue(np.all(idx < n))
        self.assertFalse(np.any(idx == np.arange(n)[:, None]))
        self.assertTrue(np.all(np.diff(sim, axis=1) <= 0))
        works = _works()
        titles = [normalize_title(w.get("title")) for w in works]
        rng = np.random.default_rng(3)
        for i in rng.choice(n, 40, replace=False):
            self.assertFalse(any(titles[j] == titles[i] for j in idx[i] if titles[i]))
            self.assertEqual(len(set(idx[i].tolist())), k)
        # sample rows against a direct float computation from the int8 vectors
        F = self.V.astype(np.float64) / 127.0
        for i in rng.choice(n, 5, replace=False):
            s = F @ F[i]
            s[i] = -9
            for j in range(n):
                if titles[j] == titles[i] and titles[i]:
                    s[j] = -9
            best = int(np.argmax(s))
            self.assertIn(best, idx[i][:3].tolist())

    def test_query_vectors(self):
        qv = read_json(SEARCH / "query_vectors.json")
        self.assertEqual(qv["dim"], 256)
        keys = set(qv["queries"])
        for e in sb.search_terms.EXAMPLES:
            self.assertIn(sb.query_key(e["q"]), keys)
        for k, b in qv["queries"].items():
            self.assertEqual(sb.query_key(k), k)
            self.assertEqual(len(base64.b64decode(b)), 256)
        bq = read_json(SEARCH / "benchmark_queries.json")
        for q in bq["queries"]:
            self.assertIn(sb.query_key(q["text"]), keys)


@unittest.skipUnless(HAVE_META and (SEARCH / "benchmark_queries.json").is_file() and (SEARCH / "query_vectors.json").is_file(), "benchmark is missing")
class TestBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bq = read_json(SEARCH / "benchmark_queries.json")
        cls.meta = _meta()

    def test_query_set(self):
        qs = self.bq["queries"]
        self.assertGreaterEqual(len(qs), 24)
        by = collections.Counter(q["group"] for q in qs)
        self.assertGreaterEqual(by["known-item"], 6)
        self.assertGreaterEqual(by["topical-en"], 8)
        self.assertGreaterEqual(by["cross-lingual"], 8)
        texts = {q["text"] for q in qs}
        for t in ("participation in service design in the public sector", "infrastructuring Malmö", "taus kunnskap i handverk", "berekraftig design"):
            self.assertIn(t, texts)
        ids = set(self.meta["ids"])
        for i, q in enumerate(qs):
            self.assertEqual(q["split"], "dev" if i % 3 == 0 else "test", q["id"])
            self.assertGreaterEqual(len(q["relevant"]), 1)
            self.assertTrue(set(q["relevant"]) <= ids)
        nb = [q for q in qs if q["group"] == "known-item" and q["lang"] in ("nn", "nb")]
        self.assertGreaterEqual(len(nb), 2)
        self.assertEqual(self.bq["pool_depth"], 30)
        self.assertIn("språkmodell", self.bq["judge"])

    def test_known_item_queries_share_at_most_half_of_title_tokens(self):
        works = {w["id"]: w for w in _works()}
        for q in self.bq["queries"]:
            if q["group"] != "known-item" or len(q["relevant"]) != 1:
                continue
            tt = set(sb.tokenize(works[q["relevant"][0]]["title"]))
            qt = set(sb.tokenize(q["text"]))
            self.assertLessEqual(len(qt & tt) / max(1, len(qt)), 0.5 + 1e-9, q["text"])

    def test_quality_recomputed_from_published_files(self):
        stored = read_json(SEARCH / "search_quality.json")
        again = se.run_benchmark(write=False)["quality"]
        for metric in ("recall_at_10", "success_at_10"):
            for system in se.SYSTEMS:
                for g, v in stored["metrics"][metric][system].items():
                    tol = 1e-9 if system == "lexical" else 1e-6
                    if v is None:
                        self.assertIsNone(again["metrics"][metric][system][g])
                    else:
                        self.assertAlmostEqual(v, again["metrics"][metric][system][g], delta=tol, msg=f"{metric}/{system}/{g}")
        self.assertEqual(stored["n_queries"], len(self.bq["queries"]))
        self.assertEqual(stored["params"]["gloss_w"], 1.0)
        for k in ("recall_at_10", "success_at_10"):
            self.assertEqual(set(stored["metrics"][k]), {"lexical", "semantic", "fused", "fallback"})
        self.assertGreaterEqual(len(stored["caveats"]), 5)

    def test_parity_file(self):
        par = read_json(SEARCH / "parity.json")
        self.assertEqual(len(par["queries"]), len(self.bq["queries"]))
        for q in par["queries"]:
            for k in ("lexical", "fallback", "fused"):
                self.assertLessEqual(len(q[k]), 20)

    def test_glossary_queries_give_five_hits(self):
        idx = se.Index()
        for t in read_json(SEARCH / "glossary.json")["terms"]:
            res = idx.search(t["q"])
            self.assertGreaterEqual(len(res["fused"]), 5, t["q"])


if __name__ == "__main__":
    unittest.main()
