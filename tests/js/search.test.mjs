import test from "node:test";
import assert from "node:assert/strict";
import { Search as S, buildLex, buildMeta, readJson, exists, root } from "./helpers.mjs";
import path from "node:path";

const casesPath = path.join(root, "tests", "fixtures", "search", "tokenizer_cases.json");

test("folding og tokenisering: fixture frå D", () => {
  assert.ok(exists(casesPath), "tests/fixtures/search/tokenizer_cases.json manglar");
  const cases = readJson(casesPath).cases;
  assert.ok(cases.length >= 40);
  for (const c of cases) assert.deepEqual(S.tokenize(c.in), c.tokens, `tokenize(${JSON.stringify(c.in)})`);
});

test("folding: dømene frå 5.1 og lik skrivemåte for Malmö/Malmo og håndverk/handverk", () => {
  assert.deepEqual(S.tokenize("Malmö"), ["malmo"]);
  assert.deepEqual(S.tokenize("Malmo"), S.tokenize("Malmö"));
  assert.deepEqual(S.tokenize("håndverk"), ["handverk"]);
  assert.deepEqual(S.tokenize("İstanbul"), ["istanbul"]);
  assert.deepEqual(S.tokenize("co-design"), ["co", "design"]);
  assert.deepEqual(S.tokenize("a b cc"), ["cc"]); // token under to teikn vert kasta
  assert.equal(S.normalizeKey("  Service   DESIGN. "), "service design.");
});

const STOP = ["the", "of", "and", "in", "for", "to", "a", "og", "i", "av"];
const DOCS = [
  { title: "Participatory design in the public sector", authors: "Anna Seravalli", venue: "CoDesign" },
  { title: "Sustainable design practice", authors: "Kim Halskov", venue: "Design Studies" },
  { title: "Sustainability transitions and design for sustainability", authors: "Ceschin", venue: "Design Studies" },
  { title: "Craft knowledge and tacit knowing", authors: "Per Galle", venue: "Craft Research" },
  { title: "Participation in services", authors: "Hillgren", venue: "CoDesign", affil: "Malmö University" },
  { title: "Public participatory budgets", authors: "X Y", venue: "Other" },
];
const CFG = {
  fold_map: S.FOLD_MAP, stopwords: STOP,
  glossary: [
    { from: [["taus", "kunnskap"], ["tyst", "kunnskap"]], to: ["tacit knowledge"], w: 1.0 },
    { from: [["handverk"], ["hantverk"]], to: ["craft"], w: 1.0 },
    { from: [["kunnskap"]], to: ["knowledge"], w: 1.0 },
  ],
};
const LEX = buildLex(DOCS, STOP);

test("indeks: avgdl reknast frå doclen, postings dekoda", () => {
  const eng = S.createEngine(CFG, LEX);
  const sum = LEX.doclen.reduce((a, b) => a + b, 0);
  assert.equal(eng.ix.avgdl, sum / LEX.n);
  const j = eng.ix.termMap.get("design");
  assert.deepEqual(Array.from(eng.ix.docs[j]), [0, 1, 2]);
});

test("BM25: poeng stemmer med formelen i 5.2", () => {
  const eng = S.createEngine(CFG, LEX);
  const r = S.lexical(eng, "design", { glossary: false });
  const ix = eng.ix;
  const j = ix.termMap.get("design");
  const df = ix.docs[j].length;
  const idf = Math.log(1 + (ix.N - df + 0.5) / (df + 0.5));
  const expect = new Map();
  ix.docs[j].forEach((d, k) => {
    const f = ix.tfs[j][k];
    expect.set(d, idf * f * (1.2 + 1) / (f + 1.2 * (1 - 0.75 + 0.75 * LEX.doclen[d] / ix.avgdl)));
  });
  // dekning = 1 gir faktor 1.0; eigne ord dekte gir i tillegg (1 + litBonus) for eitt kjerne-token
  const lit = 1 + eng.P.litBonus;
  for (const e of r.list) assert.ok(Math.abs(e.score - expect.get(e.d) * lit) < 1e-9, `doc ${e.d}`);
  assert.equal(r.list.length, expect.size);
  for (let i = 1; i < r.list.length; i++) assert.ok(r.list[i - 1].score >= r.list[i].score);
});

test("stoppord vert fjerna, men er alle stoppord vert dei haldne", () => {
  const eng = S.createEngine(CFG, LEX);
  assert.deepEqual(S.coreTokens(eng, "the design of the public").core, ["design", "public"]);
  assert.deepEqual(S.coreTokens(eng, "the of").core, ["the", "of"]);
});

test("gruppe: eksakt, s-stamme, prefiks (0,5) og morfologi (0,8) per endring 3", () => {
  const eng = S.createEngine(CFG, LEX);
  const terms = (g) => g.map((x) => [eng.ix.terms[x.j], x.w]);
  const g1 = terms(S.buildGroup(eng.ix, "sustainable"));
  assert.deepEqual(g1.find((t) => t[0] === "sustainable"), ["sustainable", 1.0]);
  assert.deepEqual(g1.find((t) => t[0] === "sustainability"), ["sustainability", 0.8]);
  const g2 = terms(S.buildGroup(eng.ix, "participation"));
  assert.deepEqual(g2.find((t) => t[0] === "participation"), ["participation", 1.0]);
  assert.deepEqual(g2.find((t) => t[0] === "participatory"), ["participatory", 0.8]);
  const g3 = terms(S.buildGroup(eng.ix, "participat")); // finst ikkje: prefiksutviding
  assert.deepEqual(g3.find((t) => t[0] === "participation"), ["participation", 0.5]);
  assert.deepEqual(g3.find((t) => t[0] === "participatory"), ["participatory", 0.5]);
  const g4 = terms(S.buildGroup(eng.ix, "sectors")); // s-stamme
  assert.deepEqual(g4.find((t) => t[0] === "sector"), ["sector", 1.0]);
  const g5 = terms(S.buildGroup(eng.ix, "budget")); // 'budgets' er prefiksterm
  assert.deepEqual(g5.find((t) => t[0] === "budgets"), ["budgets", 0.5]);
  const g6 = terms(S.buildGroup(eng.ix, "craf")); // len 4: prefiks, ingen morfologi
  assert.deepEqual(g6, [["craft", 0.5]]);
  assert.deepEqual(S.buildGroup(eng.ix, "zzzz"), []);
});

test("morfologi løftar «design for sustainability» for spørjinga «sustainable design»", () => {
  const eng = S.createEngine(CFG, LEX);
  const r = S.lexical(eng, "sustainable design", { glossary: false, full: true });
  const ranks = r.list.map((e) => e.d);
  assert.ok(ranks.includes(2), "verk 2 (sustainability) skal vere med");
  assert.ok(r.full.some((e) => e.d === 2), "verk 2 har dekning 1 via morfologi");
});

test("ordliste: tilleggsgrupper, tak 6, dedupe og dekning (endring 2)", () => {
  const eng = S.createEngine(CFG, LEX);
  const r = S.lexical(eng, "taus kunnskap i handverk", { glossary: true, full: true });
  assert.deepEqual(r.core, ["taus", "kunnskap", "handverk"]);
  assert.deepEqual(r.extra, ["tacit", "knowledge", "craft"]);
  // verk 3 har craft, knowledge og tacit; dekning 1 trass ingen norske ord i teksten
  assert.ok(r.full.some((e) => e.d === 3));
  const top = r.list[0];
  assert.equal(top.d, 3);
  // utan ordliste finst ingen treff for dei norske orda
  const plain = S.lexical(eng, "taus kunnskap i handverk", { glossary: false });
  assert.equal(plain.list.length, 0);
});

test("ordliste: frasetreff krev alle token; prefiksregelen gjeld frå lengd 5", () => {
  const eng = S.createEngine(CFG, LEX);
  assert.deepEqual(S.lexical(eng, "taus", {}).extra, []); // frasen krev òg kunnskap
  assert.deepEqual(S.lexical(eng, "handverksutdanning", {}).extra, ["craft"]); // handverk (8) er prefiks av spørjetokenet
  const cfg2 = Object.assign({}, CFG, { glossary: [{ from: [["a1"]], to: ["alpha"], w: 1 }] });
  assert.deepEqual(S.lexical(S.createEngine(cfg2, LEX), "a1b", {}).extra, []); // lengd under 5: ingen prefiks
});

test("ordliste: høgst seks tilleggs-token", () => {
  const cfg = Object.assign({}, CFG, { glossary: [{ from: [["xx"]], to: ["alpha beta gamma delta epsilon zeta eta theta"], w: 1 }] });
  const r = S.lexical(S.createEngine(cfg, LEX), "xx", {});
  assert.equal(r.extra.length, 6);
});

test("filtermaske: år, type, språk, tilgang, institusjon, forfattar og dublettar", () => {
  const works = [
    { id: "W1", year: 2010, kind: "article", authors: ["Anna Seravalli"], countries: ["SE"] },
    { id: "W2", year: 2020, kind: "conference-paper", authors: ["Kim, Min Jae"], countries: ["NO"] },
    { id: "W3", year: null, kind: "book", authors: ["Per Galle"], countries: ["DK"] },
    { id: "W4", year: 2015, kind: "thesis", authors: ["Min Jae Kim"], source_country: "FI", countries: [] },
    { id: "W5", year: 2021, kind: "letter", authors: [], countries: [] },
  ];
  const meta = { acc: "hvud0", abs: "oox00", lang: "ebndf", flag: "000d0" };
  const c = S.createCorpus(works, meta);
  const pass = (m) => (m ? Array.from(m).map((v, i) => (v ? i : -1)).filter((i) => i >= 0) : [0, 1, 2, 3, 4]);
  assert.deepEqual(pass(c.mask({ dup: true })), [0, 1, 2, 3, 4].filter(() => true)); // alt med dublettar
  assert.deepEqual(pass(c.mask({ dup: false })), [0, 1, 2, 4]); // standard: dublettar skjulte
  assert.deepEqual(pass(c.mask({ dup: true, yr: [2012, 2020] })), [1, 3]);
  assert.deepEqual(pass(c.mask({ dup: true, yr: [2016, 0] })), [1, 4]);
  assert.deepEqual(pass(c.mask({ dup: true, kind: "conf" })), [1]);
  assert.deepEqual(pass(c.mask({ dup: true, kind: "thesis" })), [3]);
  assert.deepEqual(pass(c.mask({ dup: true, kind: "other" })), [4]);
  assert.deepEqual(pass(c.mask({ dup: true, lang: "e" })), [0]);
  assert.deepEqual(pass(c.mask({ dup: true, lang: "o" })), [4]); // finsk/anna/ukjend ligg saman
  assert.deepEqual(pass(c.mask({ dup: true, cc: "FI" })), [3]); // source_country tel
  assert.deepEqual(pass(c.mask({ dup: true, tilg: "pdf" })), [0, 1, 2]); // h, v, u
  assert.deepEqual(pass(c.mask({ dup: true, tilg: "open" })), [0, 1]); // h, v
  assert.deepEqual(pass(c.mask({ dup: true, tilg: "abs" })), [0, 1, 2]);
  assert.deepEqual(pass(c.mask({ dup: true, inst: new Set(["W2", "W5"]) })), [1, 4]);
  // forfattarfilter: uavhengig av rekkjefølgje, 'Kim, Min Jae' og 'Min Jae Kim' gir same treff
  assert.deepEqual(pass(c.mask({ dup: true, au: "Min Jae Kim" })), [1, 3]);
  assert.deepEqual(pass(c.mask({ dup: true, au: "Kim, Min Jae" })), [1, 3]);
  assert.deepEqual(pass(c.mask({ dup: true, au: "seravalli" })), [0]);
  assert.deepEqual(pass(c.mask({ dup: true, au: "Seravalli Kim" })), []);
  assert.deepEqual(pass(c.mask({ dup: true, au: "Seravallí" })), [0]); // foldet
});

test("sortering: mest siterte, nyaste, eldste og tie-break på posisjon", () => {
  const works = [{ id: "a", year: 2000, citations: 5 }, { id: "b", year: 2020, citations: 5 }, { id: "c", year: null, citations: null }, { id: "d", year: 2010, citations: 9 }];
  const c = S.createCorpus(works, buildMeta(4));
  assert.deepEqual(c.sortList([0, 1, 2, 3], "cited"), [3, 0, 1, 2]);
  assert.deepEqual(c.sortList([0, 1, 2, 3], "new"), [1, 3, 0, 2]);
  assert.deepEqual(c.sortList([0, 1, 2, 3], "old"), [0, 3, 1, 2]);
});

test("RRF: k = 60, rang frå 1, vekter", () => {
  const f = S.fuse([{ list: [{ d: 5 }, { d: 7 }], w: 1.0 }, { list: [{ d: 7 }, { d: 9 }], w: 0.6 }]);
  const rrf = new Map(f.map((e) => [e.d, e.rrf]));
  assert.ok(Math.abs(rrf.get(5) - 1 / 61) < 1e-12);
  assert.ok(Math.abs(rrf.get(7) - (1 / 62 + 0.6 / 61)) < 1e-12);
  assert.ok(Math.abs(rrf.get(9) - 0.6 / 62) < 1e-12);
  assert.deepEqual(f.map((e) => e.d), [7, 5, 9]);
});

test("naboutviding: kjeldeverk og naboar, vekt 1/(1+rang) × likskap/255, tak og maske", () => {
  const k = 2;
  const sim = { k, nbr: Uint16Array.from([1, 2, 0, 2, 0, 1, 0, 1]), sim: Uint8Array.from([255, 128, 255, 0, 128, 0, 0, 0]) };
  const out = S.prfTop([0, 1], sim, null, 10);
  const m = new Map(out.map((e) => [e.d, e.score]));
  assert.ok(Math.abs(m.get(0) - (1 / 2 + (1 / 3) * (255 / 255))) < 1e-12); // eigen vekt som rang 1 + nabo av rang 2
  assert.ok(Math.abs(m.get(1) - (1 / 3 + 1 / 2 * 1)) < 1e-12);
  assert.ok(Math.abs(m.get(2) - (1 / 2 * 128 / 255 + 0)) < 1e-12); // sim 0 gir ikkje poeng
  const masked = S.prfTop([0, 1], sim, Uint8Array.from([1, 0, 1, 1]), 10);
  assert.ok(masked.every((e) => e.d !== 1));
});

test("semantisk del: skalarprodukt/127, ingen terskel, maske", () => {
  const dim = 4, n = 3;
  const v = Int8Array.from([127, 0, 0, 0, 0, 127, 0, 0, 64, 64, 0, 0]);
  const qv = Float32Array.from([1, 0, 0, 0]);
  const r = S.semanticTop(v, n, dim, qv, null, 10);
  assert.deepEqual(r.map((e) => e.d), [0, 2, 1]);
  assert.ok(Math.abs(r[0].score - 1) < 1e-9);
  assert.deepEqual(S.semanticTop(v, n, dim, qv, Uint8Array.from([0, 1, 1]), 10).map((e) => e.d), [2, 1]);
});

test("run: modus og tak (to lister 300, ein liste 200) og pool for andre sorteringar", () => {
  const docs = [];
  for (let i = 0; i < 500; i++) docs.push({ title: "alpha beta item" + i + (i % 2 ? " gamma" : ""), authors: "A" + i });
  const lex = buildLex(docs, []);
  const eng = S.createEngine({ stopwords: [], glossary: [] }, lex);
  const one = S.run(eng, "alpha beta", {});
  assert.equal(one.mode, "ord");
  assert.equal(one.cap, 200);
  assert.equal(one.hits.length, 200);
  assert.ok(one.capped);
  assert.equal(one.lex.full.length, 500, "alle 500 har dekning 1");
  assert.equal(S.sortPool(one).length, 500);
  // med naboar blir det to lister
  const k = 1, n = 500;
  const sim = { k, nbr: new Uint16Array(n).map((_, i) => (i + 1) % n), sim: new Uint8Array(n).fill(200) };
  const two = S.run(eng, "alpha beta", { sim });
  assert.equal(two.mode, "prf");
  assert.equal(two.cap, 300);
  assert.ok(two.hits.length <= 300);
  // med spørjevektor
  const dim = 4, vec = new Int8Array(n * dim).fill(10), qv = Float32Array.from([1, 1, 1, 1]);
  const three = S.run(eng, "alpha beta", { vectors: vec, qv, n, dim });
  assert.equal(three.mode, "sem");
  assert.equal(three.cap, 300);
});

test("legacy: delstrengsøking med same folding", () => {
  const qf = ["malmo university", "aalborg", "infrastructuring malmo"].map((s) => S.fold(s));
  assert.deepEqual(S.legacySearch(qf, "Malmö", S.FOLD_MAP, null), [0, 2]);
  assert.deepEqual(S.legacySearch(qf, "infra malmo", S.FOLD_MAP, null), [2]);
  assert.deepEqual(S.legacySearch(qf, "", S.FOLD_MAP, null), []);
});

test("spørjevektor: base64 int8 -> flyttal /127", () => {
  const b64 = Buffer.from(Int8Array.from([127, -127, 0, 64])).toString("base64");
  const v = S.decodeQV(b64, 127);
  assert.deepEqual(Array.from(v).map((x) => Math.round(x * 127)), [127, -127, 0, 64]);
});

test("Les først: formel i 5.6", () => {
  assert.ok(Math.abs(S.readFirstScore(0.5, 1, 999, "v") - 0.5 * (1 + 0.2 * 1) * 1.05) < 1e-12);
  assert.equal(S.readFirstScore(1, 1, 0, "d"), 1);
  assert.equal(S.readFirstScore(1, 1, null, "u"), 1);
});

test("tittelfrase-påslag: heile frasen i tittelen (stoppord med) går først, berre når titles er gitt", () => {
  const eng = S.createEngine(CFG, LEX);
  const titles = DOCS.map((d) => " " + S.tokenize(d.title).join(" ") + " ");
  const q = "design in the public sector";
  const plain = S.lexical(eng, q, { glossary: false });
  const boosted = S.lexical(eng, q, { glossary: false, titles });
  assert.equal(plain.phraseHits, 0);
  assert.equal(boosted.phraseHits, 1);
  assert.equal(boosted.list[0].d, 0);
  // eitt ord gir aldri påslag, og utan titles er lista lik den målte
  assert.equal(S.lexical(eng, "design", { glossary: false, titles }).phraseHits, 0);
  assert.deepEqual(S.lexical(eng, q, { glossary: false }).list, plain.list);
});

test("eigne ord går føre ordlisteomsetjingar (litBonus)", () => {
  // eitt verk med berre «craft» (ordliste) og eitt med «handverk» (brukaren sitt eige ord) har lik tf og lengd:
  // det med eige ord skal få høgast poeng
  const lex = {
    n: 2, k1: 1.2, b: 0.75, avgdl: 10, doclen: [10, 10],
    terms: ["craft", "handverk"], post: [[1, 4], [0, 4]],
  };
  const cfg = { stopwords: [], glossary: [{ from: [["handverk"]], to: ["craft"], w: 1.0 }] };
  const eng = S.createEngine(cfg, lex);
  const r = S.lexical(eng, "handverk", {});
  assert.deepEqual(r.list.map((e) => e.d), [0, 1]);
  assert.ok(r.list[0].score > r.list[1].score);
});

test("tittelfrase-påslag for ordlistefrasar: «designtenking» løftar «design thinking» i tittelen, men berre når oppføringa dekkjer heile spørjinga", () => {
  const docs = [
    { title: "Systems thinking in a design studio", authors: "A B", venue: "X" },
    { title: "Design thinking meets innovation", authors: "C D", venue: "Y" },
    { title: "Thinking about design education", authors: "E F", venue: "Z" },
  ];
  const cfg = { stopwords: STOP, glossary: [{ from: [["designtenking"]], to: ["design thinking"], w: 1.0 }] };
  const eng = S.createEngine(cfg, buildLex(docs, STOP));
  const titles = docs.map((d) => " " + S.tokenize(d.title).join(" ") + " ");
  const plain = S.lexical(eng, "designtenking", {});
  const boosted = S.lexical(eng, "designtenking", { titles });
  assert.equal(plain.phraseHits, 0);
  assert.equal(boosted.phraseHits, 1);
  assert.equal(boosted.list[0].d, 1);
  // spørjinga har eit ord til som oppføringa ikkje dekkjer: ingen ordlistepåslag
  assert.equal(S.lexical(eng, "designtenking skule", { titles }).phraseHits, 0);
  // utan ordliste ingen påslag
  assert.equal(S.lexical(eng, "designtenking", { titles, glossary: false }).phraseHits, 0);
});
