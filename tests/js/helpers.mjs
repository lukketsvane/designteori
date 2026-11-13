// Felles hjelparar for node-testane. Ikkje ein test (filnamnet sluttar ikkje på .test.mjs).
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
export const here = path.dirname(fileURLToPath(import.meta.url));
export const root = path.resolve(here, "..", "..");
export const docs = path.join(root, "docs");
export const searchDir = path.join(docs, "data", "search");

export const Search = require(path.join(docs, "search.js"));
export const Ui = require(path.join(docs, "ui.js"));
export const Exp = require(path.join(docs, "export.js"));
export const Emb = require(path.join(docs, "embed.js"));
export const Om = require(path.join(docs, "om.js"));

export const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
export const readText = (p) => fs.readFileSync(p, "utf8");
export const exists = (p) => fs.existsSync(p);

/* Bygg ein liten lex.json i kontraktformat frå dokument {title, authors, venue, affil, abstract}. */
export function buildLex(docsIn, stopwords = []) {
  const stop = new Set(stopwords);
  const W = { title: 4, authors: 2, venue: 2, affil: 2, abstract: 1 };
  const post = new Map();
  const doclen = [];
  docsIn.forEach((d, i) => {
    const tf = new Map();
    for (const [field, wt] of Object.entries(W)) {
      for (const t of Search.tokenize(d[field] || "")) {
        if (stop.has(t)) continue;
        tf.set(t, (tf.get(t) || 0) + wt);
      }
    }
    let dl = 0;
    for (const [t, v] of tf) {
      const f = Math.min(255, v);
      dl += f;
      if (!post.has(t)) post.set(t, []);
      post.get(t).push(i, f);
    }
    doclen.push(dl);
  });
  const terms = Array.from(post.keys()).sort();
  const flat = terms.map((t) => {
    const p = post.get(t), o = [];
    let prev = 0;
    for (let k = 0; k < p.length; k += 2) { o.push(k === 0 ? p[0] : p[k] - prev, p[k + 1]); prev = p[k]; }
    return o;
  });
  const avgdl = doclen.reduce((a, b) => a + b, 0) / (docsIn.length || 1);
  return { schema: 1, n: docsIn.length, avgdl, k1: 1.2, b: 0.75, weights: W, doclen, terms, post: flat };
}

/* Meta-strengar for n verk: acc, abs, lang, flag */
export function buildMeta(n, o = {}) {
  const rep = (c) => c.repeat(n);
  return { acc: o.acc || rep("d"), abs: o.abs || rep("o"), lang: o.lang || rep("e"), flag: o.flag || rep("0") };
}

export function isCI() { return !!process.env.CI; }
