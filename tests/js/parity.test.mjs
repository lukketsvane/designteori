import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import fs from "node:fs";
import { Search as S, searchDir, readJson, exists, isCI } from "./helpers.mjs";

// Parity mot designteori/search_eval.py (parity.json) og kontraktkontrollar mot dei ekte filene i docs/data/search/.
// Utan filene lokalt vert testen hoppa over med melding; i CI (CI=true) er filene påkravde.
const need = ["meta.json", "lex.json", "search_config.json"];
const have = need.every((f) => exists(path.join(searchDir, f)));
const skip = !have && !isCI() ? "docs/data/search/ manglar lokalt" : false;

test("filene finst (påkravd i CI)", { skip: skip || false }, () => {
  for (const f of need) assert.ok(exists(path.join(searchDir, f)), f + " manglar");
});

function load() {
  const meta = readJson(path.join(searchDir, "meta.json"));
  const cfg = readJson(path.join(searchDir, "search_config.json"));
  const lex = readJson(path.join(searchDir, "lex.json"));
  return { meta, cfg, lex, eng: S.createEngine(cfg, lex) };
}

test("kontrakt: meta-strengane har n teikn og teljarane stemmer med strengane", { skip }, () => {
  const { meta } = load();
  assert.equal(meta.schema, 1);
  assert.equal(meta.ids.length, meta.n);
  for (const k of ["lang", "abs", "acc", "flag"]) assert.equal(meta[k].length, meta.n, k);
  const tally = (s) => { const o = {}; for (const c of s) o[c] = (o[c] || 0) + 1; return o; };
  assert.deepEqual(tally(meta.acc), meta.counts.acc);
  assert.deepEqual(tally(meta.abs), meta.counts.abs);
  assert.deepEqual(tally(meta.lang), meta.counts.lang);
  assert.deepEqual(tally(meta.flag), meta.counts.flag);
  const a = meta.counts.acc;
  assert.equal(a.h + a.v + a.u + a.d + a["0"], 6432);
  assert.equal(a.h, 23);
  assert.equal(a.v, 3239);
  assert.equal(a["0"], 344);
  assert.equal(a.h + a.v, 3262);
  assert.equal(meta.counts.pdf_verified_total, 3262);
  assert.ok(meta.counts.layers && meta.counts.year_range && meta.counts.sources, "meta.counts må ha layers, year_range og sources (endring 5)");
});

test("kontrakt: lex.json og search_config.json har forma F les", { skip }, () => {
  const { cfg, lex, meta } = load();
  assert.equal(lex.n, meta.n);
  assert.equal(lex.doclen.length, lex.n);
  assert.equal(lex.terms.length, lex.post.length);
  for (let i = 1; i < lex.terms.length; i++) assert.ok(lex.terms[i - 1] < lex.terms[i], "terms sortert og unike");
  const eng = S.createEngine(cfg, lex);
  assert.ok(Math.abs(eng.ix.avgdl - lex.avgdl) < 1e-9, "avgdl stemmer med doclen");
  assert.ok(cfg.glossary.length >= 120);
  assert.equal(cfg.examples.length, 10);
  assert.ok(cfg.stopwords.every((t) => t === S.fold(t)));
  for (const e of cfg.examples) assert.ok(e.q === S.normalizeKey(e.q));
});

test("kontrakt: access.json og samandragsskjervane", { skip }, () => {
  const { meta } = load();
  const acc = readJson(path.join(searchDir, meta.access.file)).items;
  const ids = new Map(meta.ids.map((id, i) => [id, i]));
  for (const [id, row] of Object.entries(acc)) {
    const code = meta.acc[ids.get(id)];
    assert.ok("hvu".includes(code), id);
    assert.equal(row[0], code);
    assert.ok(/^https?:\/\//.test(row[1]), id);
  }
  const count = meta.abstracts.count;
  let n = 0;
  for (let k = 0; k < count; k++) {
    const sh = readJson(path.join(searchDir, meta.abstracts.dir, meta.abstracts.pattern.replace("{NNN}", String(k).padStart(3, "0"))));
    for (const [id, e] of Object.entries(sh)) {
      n++;
      assert.ok(Math.floor(ids.get(id) / meta.abstracts.shard_size) === k, id + " i feil skjerv");
      assert.ok("oa x".split(" ").includes(e.s));
      assert.equal(meta.abs[ids.get(id)], e.s === "oa" ? "o" : "x");
    }
  }
  assert.equal(n, meta.counts.abs.o + meta.counts.abs.x);
});

const parityPath = path.join(searchDir, "parity.json");
const hasParity = exists(parityPath);
const pskip = skip || (!hasParity && !isCI() ? "parity.json er ikkje bygd enno" : false);

test("parity: lexical og fallback (≥ 18 av 20) og fused (≥ 8 av 10) mot parity.json", { skip: pskip }, () => {
  assert.ok(hasParity, "parity.json manglar");
  const { meta, eng } = load();
  const par = readJson(parityPath);
  const queries = par.queries || par;
  assert.ok(queries.length >= 24);
  const n = meta.n;
  const sim = (() => {
    const p = path.join(searchDir, "similar.bin");
    if (!exists(p)) return null;
    const b = fs.readFileSync(p), k = meta.similar.k;
    const ab = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
    return { nbr: new Uint16Array(ab, 0, n * k), sim: new Uint8Array(ab, n * k * 2, n * k), k };
  })();
  const vectors = (() => {
    const p = path.join(searchDir, "vectors.i8");
    if (!exists(p)) return null;
    const b = fs.readFileSync(p);
    return new Int8Array(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
  })();
  const qvs = exists(path.join(searchDir, "query_vectors.json")) ? readJson(path.join(searchDir, "query_vectors.json")).queries : {};
  const common = (a, b, k) => { const s = new Set(b.slice(0, k)); return a.slice(0, k).filter((x) => s.has(x)).length; };
  let exact = 0, total = 0;
  for (const q of queries) {
    const lex = S.lexical(eng, q.q, { glossary: false }).list.map((e) => e.d);
    assert.ok(common(lex, q.lexical, 20) >= Math.min(18, q.lexical.length), `lexical «${q.q}»: ${common(lex, q.lexical, 20)} av 20`);
    const fb = S.run(eng, q.q, { sim }).hits.map((h) => h.d);
    assert.ok(common(fb, q.fallback, 20) >= Math.min(18, q.fallback.length), `fallback «${q.q}»: ${common(fb, q.fallback, 20)} av 20`);
    const key = S.normalizeKey(q.q);
    assert.ok(qvs[key], `lagra spørjevektor manglar for «${q.q}» (nøkkel ${key})`);
    const qv = S.decodeQV(qvs[key], meta.vectors.scale);
    const fu = S.run(eng, q.q, { qv, vectors, n, dim: meta.vectors.dim }).hits.map((h) => h.d);
    assert.ok(common(fu, q.fused, 10) >= Math.min(8, q.fused.length), `fused «${q.q}»: ${common(fu, q.fused, 10)} av 10`);
    total++;
    if (JSON.stringify(lex.slice(0, 20)) === JSON.stringify(q.lexical)) exact++;
  }
  console.log(`# parity: ${queries.length} spørjingar; lexical identisk topp 20 for ${exact} av ${total}`);
});
