/* Søkekjerne for designteori-sida: folding, BM25, ordliste, naboutviding, RRF og filtermaske.
   Ingen DOM. Klassisk skript (UMD-hale): window.DTSearch i nettlesaren, module.exports i node.
   Algoritmen følgjer spesifikasjonen del 5 og er identisk med designteori/search_eval.py. */
(function () {
  "use strict";

  const FOLD_MAP = { "æ": "ae", "ø": "o", "ð": "d", "þ": "th", "ß": "ss", "đ": "d", "ł": "l", "œ": "oe" };
  const PARAMS = { k1: 1.2, b: 0.75, rrfK: 60, wLex: 1.0, wSem: 1.0, wSemLong: 2.0, longQuery: 4, wPrf: 0.6, glossW: 1.0, litBonus: 0.75, topN: 200, cap: 300, fullCap: 2000, extraMax: 6, prfSeeds: 5 };
  const NORDIC = ["NO", "SE", "DK", "FI", "IS"];

  /* ---------- 5.1 folding og tokenisering ---------- */
  function fold(s, fm) {
    fm = fm || FOLD_MAP;
    s = String(s == null ? "" : s).toLowerCase();
    let out = "";
    for (const ch of s) out += Object.prototype.hasOwnProperty.call(fm, ch) ? fm[ch] : ch;
    return out.normalize("NFKD").replace(/[̀-ͯ]/g, "");
  }
  function tokenize(s, fm) {
    const m = fold(s, fm).match(/[a-z0-9]+/g) || [];
    return m.filter((t) => t.length >= 2);
  }
  /* Nøkkel for lagra spørjevektorar (4.9): trim, ein mellomrom, toLowerCase. Ingen anna normalisering. */
  function normalizeKey(q) { return String(q == null ? "" : q).trim().replace(/\s+/g, " ").toLowerCase(); }

  function b64ToBytes(b64) {
    if (typeof atob === "function") {
      const bin = atob(b64), out = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
      return out;
    }
    return new Uint8Array(Buffer.from(b64, "base64"));
  }
  /* base64 av int8 -> Float32Array (verdi/127) */
  function decodeQV(b64, scale) {
    const u = b64ToBytes(b64), out = new Float32Array(u.length), sc = scale || 127;
    for (let i = 0; i < u.length; i++) out[i] = (u[i] > 127 ? u[i] - 256 : u[i]) / sc;
    return out;
  }
  function l2normalize(v) {
    let s = 0;
    for (let i = 0; i < v.length; i++) s += v[i] * v[i];
    s = Math.sqrt(s) || 1;
    const o = new Float32Array(v.length);
    for (let i = 0; i < v.length; i++) o[i] = v[i] / s;
    return o;
  }

  /* ---------- indeks (4.4) ---------- */
  function createIndex(lex) {
    const terms = lex.terms, T = terms.length, N = lex.n;
    const docs = new Array(T), tfs = new Array(T), termMap = new Map();
    for (let j = 0; j < T; j++) {
      const p = lex.post[j], m = p.length >> 1;
      const d = new Uint32Array(m), f = new Uint8Array(m);
      let cur = 0;
      for (let k = 0; k < m; k++) {
        cur = k === 0 ? p[0] : cur + p[2 * k];
        d[k] = cur;
        f[k] = p[2 * k + 1];
      }
      docs[j] = d; tfs[j] = f;
      termMap.set(terms[j], j);
    }
    const doclen = Float64Array.from(lex.doclen);
    let sum = 0;
    for (let i = 0; i < doclen.length; i++) sum += doclen[i];
    const avgdl = sum / (N || 1); // F reknar avgdl sjølv (endring 4)
    const k1 = lex.k1 != null ? lex.k1 : PARAMS.k1, b = lex.b != null ? lex.b : PARAMS.b;
    const kn = new Float64Array(N);
    for (let i = 0; i < N; i++) kn[i] = k1 * (1 - b + b * doclen[i] / avgdl);
    return { N, terms, docs, tfs, termMap, doclen, avgdl, k1, b, kn };
  }

  function lowerBound(terms, q) {
    let lo = 0, hi = terms.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (terms[mid] < q) lo = mid + 1; else hi = mid; }
    return lo;
  }

  /* 5.2 gruppe for eitt token (med morfologi frå endring 3) */
  function buildGroup(ix, q) {
    const g = [], seen = new Set();
    const add = (j, w) => { if (j !== undefined && !seen.has(j)) { seen.add(j); g.push({ j, w }); } };
    const ex = ix.termMap.get(q);
    if (ex !== undefined) add(ex, 1.0);
    else if (q.endsWith("s") && q.length >= 5) add(ix.termMap.get(q.slice(0, -1)), 1.0);
    else if (q.endsWith("es") && q.length >= 6) add(ix.termMap.get(q.slice(0, -2)), 1.0);
    const pick = (prefix, maxLen) => {
      const out = [];
      for (let j = lowerBound(ix.terms, prefix); j < ix.terms.length && ix.terms[j].startsWith(prefix); j++) {
        if (seen.has(j) || ix.terms[j].length > maxLen) continue;
        out.push(j);
      }
      out.sort((a, b) => (ix.docs[b].length - ix.docs[a].length) || (ix.terms[a] < ix.terms[b] ? -1 : 1));
      return out.slice(0, 8);
    };
    if (q.length >= 4) {
      const exJ = ex;
      for (const j of pick(q, q.length + 4)) if (j !== exJ) add(j, 0.5);
    }
    if (q.length >= 8) {
      for (const j of pick(q.slice(0, q.length - 3), q.length + 4)) add(j, 0.8);
    }
    return g;
  }

  const PHRASE_BONUS = 1000;

  /* ---------- søkemotor ---------- */
  function createEngine(config, lex, params) {
    const P = Object.assign({}, PARAMS, params || {});
    const fm = (config && config.fold_map) || FOLD_MAP;
    const stop = new Set((config && config.stopwords) || []);
    const ix = createIndex(lex);
    const gloss = ((config && config.glossary) || []).map((e) => ({
      from: (e.from || []).map((ph) => ph.map((t) => fold(t, fm))),
      to: (e.to || []).map((ph) => tokenize(ph, fm).filter((t) => !stop.has(t))),
      toFull: (e.to || []).map((ph) => tokenize(ph, fm)),
      w: e.w != null ? e.w : P.glossW,
    }));
    return { ix, fm, stop, gloss, P };
  }

  function coreTokens(eng, query) {
    const all = tokenize(query, eng.fm);
    const kept = all.filter((t) => !eng.stop.has(t));
    const base = kept.length ? kept : all;
    const seen = new Set(), core = [];
    for (const t of base) if (!seen.has(t)) { seen.add(t); core.push(t); }
    return { all, core: core.slice(0, 32) };
  }

  function phraseMatch(phrase, core) {
    const hit = [];
    for (const t of phrase) {
      let found = false;
      for (let i = 0; i < core.length; i++) {
        const q = core[i];
        if (q === t || (t.length >= 5 && q.startsWith(t))) { found = true; hit.push(i); }
      }
      if (!found) return null;
    }
    return hit;
  }

  function popcount(x) {
    x = x >>> 0;
    x = (x - ((x >>> 1) & 0x55555555)) >>> 0;
    x = ((x & 0x33333333) + ((x >>> 2) & 0x33333333)) >>> 0;
    return Math.imul((x + (x >>> 4)) & 0x0f0f0f0f, 0x01010101) >>> 24;
  }

  /* 5.2 + 5.3. Eigne ord frå brukaren går føre ordlisteomsetjingar: poenget vert gonga med (1 + litBonus × del kjerne-token dekt av eiga gruppe). opts: {mask, topN, glossary, full} */
  function lexical(eng, query, opts) {
    opts = opts || {};
    const ix = eng.ix, P = eng.P, N = ix.N;
    const mask = opts.mask || null;
    const topN = opts.topN || P.topN;
    const { all, core } = coreTokens(eng, query);
    const res = { tokens: all, core, extra: [], list: [], full: [], terms: [], glossHits: [], phraseHits: 0 };
    const m = core.length;
    if (!m) return res;

    const score = new Float64Array(N), cov = new Uint32Array(N), lit = new Uint32Array(N), gv = new Float64Array(N), touchedAll = new Uint8Array(N);
    const all_touched = [];
    const termSet = new Set();

    const runGroup = (group, mult, onTouch) => {
      const touched = [];
      for (const { j, w } of group) {
        termSet.add(ix.terms[j]);
        const docs = ix.docs[j], tfs = ix.tfs[j], df = docs.length;
        const idf = Math.log(1 + (N - df + 0.5) / (df + 0.5));
        const wm = w * mult * idf * (ix.k1 + 1);
        for (let k = 0; k < docs.length; k++) {
          const d = docs[k];
          if (mask && !mask[d]) continue;
          const f = tfs[k];
          if (gv[d] === 0) touched.push(d);
          gv[d] += wm * f / (f + ix.kn[d]);
        }
      }
      for (const d of touched) {
        const v = gv[d]; gv[d] = 0;
        score[d] += v;
        if (!touchedAll[d]) { touchedAll[d] = 1; all_touched.push(d); }
        onTouch(d);
      }
    };

    for (let i = 0; i < m; i++) {
      const bit = (1 << i) >>> 0;
      runGroup(buildGroup(ix, core[i]), 1, (d) => { cov[d] |= bit; lit[d] |= bit; });
    }

    const gPhrases = [];
    if (opts.glossary !== false && eng.gloss.length) {
      const coreSet = new Set(core), added = new Map(), order = [];
      for (const e of eng.gloss) {
        const sources = new Set();
        let hit = false;
        for (const ph of e.from) {
          if (!ph.length) continue;
          const ps = new Set();
          let ok = true;
          for (const t of ph) {
            let any = false;
            for (let i = 0; i < core.length; i++) { const q = core[i]; if (q === t || (t.length >= 5 && q.startsWith(t))) { ps.add(i); any = true; } }
            if (!any) { ok = false; break; }
          }
          if (ok) { hit = true; ps.forEach((i) => sources.add(i)); }
        }
        if (!hit) continue;
        if (sources.size === core.length) { // oppføringa dekkjer heile spørjinga: ordlistefrasen er «spørjinga omsett»
          for (const tf of e.toFull) {
            if (tf.length < 2) continue;
            const key = " " + tf.join(" ") + " ";
            if (gPhrases.indexOf(key) < 0) gPhrases.push(key);
          }
        }
        for (const ph of e.to) for (const tok of ph) {
          if (coreSet.has(tok)) continue;
          if (added.has(tok)) sources.forEach((i) => added.get(tok).sources.add(i));
          else if (order.length < P.extraMax) { added.set(tok, { sources: new Set(sources), w: e.w }); order.push(tok); }
        }
      }
      for (const tok of order) {
        const g = added.get(tok);
        let bits = 0;
        g.sources.forEach((i) => { bits |= (1 << i); });
        bits >>>= 0;
        res.extra.push(tok);
        res.glossHits.push({ token: tok, core: Array.from(g.sources).map((i) => core[i]) });
        runGroup(buildGroup(ix, tok), g.w, (d) => { cov[d] = (cov[d] | bits) >>> 0; });
      }
    }

    /* Tittelfrase-påslag (same i designteori/search_eval.py; ikkje i «lexical» utan ordliste). Påslaget vert lagt til éin gong per verk når
       (a) heile spørjefrasen, stoppord med, står rett etter kvarandre i tittelen, eller
       (b) spørjinga (utan stoppord) er heilt dekt av éi ordlisteoppføring og ein engelsk frase med fleire ord frå oppføringa står i tittelen
       (til dømes «design thinking» for «designtenking», «service design» for «tenestedesign»). */
    const userKey = opts.titles && all.length >= 2 ? " " + all.join(" ") + " " : "";
    const gKeys = opts.titles ? gPhrases.filter((k) => k !== userKey) : [];
    const cand = [];
    const full = [];
    for (const d of all_touched) {
      const dek = popcount(cov[d]) / m;
      let s = score[d] * (0.6 + 0.4 * dek) * (1 + P.litBonus * popcount(lit[d]) / m);
      if (s > 0 && opts.titles && opts.titles[d]) {
        const t = opts.titles[d];
        let hit = userKey !== "" && t.indexOf(userKey) >= 0;
        if (!hit) for (const k of gKeys) if (t.indexOf(k) >= 0) { hit = true; break; }
        if (hit) { s += PHRASE_BONUS; res.phraseHits++; }
      }
      score[d] = s;
      if (s > 0) { cand.push(d); if (dek === 1) full.push(d); }
    }
    const cmp = (a, b) => (score[b] - score[a]) || (a - b);
    cand.sort(cmp);
    res.list = cand.slice(0, topN).map((d) => ({ d, score: score[d] }));
    if (opts.full) {
      full.sort(cmp);
      res.full = full.slice(0, P.fullCap).map((d) => ({ d, score: score[d] }));
    }
    res.terms = Array.from(termSet);
    res.matched = cand.length;
    return res;
  }

  /* 5.4 semantisk del */
  function semanticTop(vectors, n, dim, qv, mask, topN) {
    const sc = new Float64Array(n), idx = [];
    for (let i = 0; i < n; i++) {
      if (mask && !mask[i]) continue;
      let dot = 0;
      const b = i * dim;
      for (let j = 0; j < dim; j++) dot += vectors[b + j] * qv[j];
      sc[i] = dot / 127;
      idx.push(i);
    }
    idx.sort((a, b) => (sc[b] - sc[a]) || (a - b));
    return idx.slice(0, topN || PARAMS.topN).map((d) => ({ d, score: sc[d] }));
  }

  /* 5.4 naboutviding. sim = {nbr:Uint16Array, sim:Uint8Array, k} */
  function prfTop(seeds, sim, mask, topN) {
    const acc = new Map();
    const add = (d, v) => { acc.set(d, (acc.get(d) || 0) + v); };
    seeds.slice(0, PARAMS.prfSeeds).forEach((s, r) => {
      const wt = 1 / (1 + (r + 1));
      add(s, wt);
      for (let e = 0; e < sim.k; e++) add(sim.nbr[s * sim.k + e], wt * (sim.sim[s * sim.k + e] / 255));
    });
    const out = [];
    for (const [d, v] of acc) if (v > 0 && (!mask || mask[d])) out.push({ d, score: v });
    out.sort((a, b) => (b.score - a.score) || (a.d - b.d));
    return out.slice(0, topN || PARAMS.topN);
  }

  /* 5.5 reciprocal rank fusion. lists: [{list:[{d}], w}] */
  function fuse(lists, k) {
    k = k || PARAMS.rrfK;
    const acc = new Map();
    for (const L of lists) {
      L.list.forEach((e, r) => { acc.set(e.d, (acc.get(e.d) || 0) + L.w / (k + r + 1)); });
    }
    const out = [];
    for (const [d, v] of acc) out.push({ d, rrf: v });
    out.sort((a, b) => (b.rrf - a.rrf) || (a.d - b.d));
    return out;
  }

  /* Samla køyring. ctx: {mask, qv, vectors, dim, n, sim}. Gir hits (posisjonar), lister, modus. */
  function run(eng, query, ctx) {
    ctx = ctx || {};
    const P = eng.P;
    const lex = lexical(eng, query, { mask: ctx.mask, glossary: ctx.glossary !== false, full: ctx.full !== false, titles: ctx.titles });
    const lists = [{ list: lex.list, w: P.wLex, name: "lex" }];
    let mode = "ord";
    let sem = null, prf = null;
    if (ctx.qv && ctx.vectors) {
      sem = semanticTop(ctx.vectors, ctx.n, ctx.dim || 256, ctx.qv, ctx.mask, P.topN);
      /* spørjing som liknar ein tittel eller ei setning (>= 4 token): meininga får dobbel vekt, målt på dev-spørjingane */
      lists.push({ list: sem, w: lex.tokens.length >= P.longQuery ? P.wSemLong : P.wSem, name: "sem" });
      mode = "sem";
    } else if (ctx.sim && lex.list.length) {
      prf = prfTop(lex.list.slice(0, P.prfSeeds).map((e) => e.d), ctx.sim, ctx.mask, P.topN);
      lists.push({ list: prf, w: P.wPrf, name: "prf" });
      mode = "prf";
    }
    const fused = fuse(lists.filter((L) => L.list.length || L.name === "lex"));
    const cap = lists.length >= 2 ? P.cap : P.topN;
    const hits = fused.slice(0, cap);
    return { mode, lex, sem, prf, fused, hits, cap, capped: fused.length > cap || lex.matched > P.topN, lists };
  }

  /* 5.6 «Les først» */
  function readFirstScore(rrf, maxRrf, citations, acc) {
    const c = citations > 0 ? Math.min(1, Math.log10(1 + citations) / 3) : 0;
    return (maxRrf ? rrf / maxRrf : 0) * (1 + 0.2 * c) * ((acc === "h" || acc === "v") ? 1.05 : 1);
  }

  /* ---------- korpus og filtermaske (F8, F13 endring 8, F14 endring 10) ---------- */
  function kindGroup(kind) {
    switch (kind) {
      case "article": return "article";
      case "conference-paper": case "proceedings-article": return "conf";
      case "book-chapter": return "chapter";
      case "book": return "book";
      case "dissertation": case "thesis": return "thesis";
      default: return "other";
    }
  }
  const LANG_GROUP = { e: "e", b: "b", n: "n", d: "d", s: "s", f: "o", o: "o", u: "o" };

  function createCorpus(works, meta, fm) {
    const n = works.length;
    const year = new Int16Array(n), kg = new Array(n), cc = new Array(n);
    for (let i = 0; i < n; i++) {
      const w = works[i];
      year[i] = w.year || 0;
      kg[i] = kindGroup(w.kind);
      const set = new Set(w.countries || []);
      if (w.source_country) set.add(w.source_country);
      cc[i] = set;
    }
    let authTok = null;
    const authTokens = () => {
      if (!authTok) authTok = works.map((w) => new Set(tokenize((w.authors || []).join(" "), fm)));
      return authTok;
    };
    function mask(f) {
      f = f || {};
      const yr = f.yr && (f.yr[0] || f.yr[1]) ? f.yr : null;
      const au = f.au ? tokenize(f.au, fm) : null;
      const active = yr || f.cc || f.kind || f.lang || f.tilg || f.inst || (au && au.length) || !f.dup;
      if (!active) return null;
      const out = new Uint8Array(n);
      const at = au && au.length ? authTokens() : null;
      for (let i = 0; i < n; i++) {
        if (!f.dup && meta.flag && meta.flag[i] === "d") continue;
        if (yr) {
          const y = year[i];
          if (!y) continue;
          if (yr[0] && y < yr[0]) continue;
          if (yr[1] && y > yr[1]) continue;
        }
        if (f.cc && !cc[i].has(f.cc)) continue;
        if (f.kind && kg[i] !== f.kind) continue;
        if (f.lang && LANG_GROUP[meta.lang[i]] !== f.lang) continue;
        if (f.tilg) {
          const a = meta.acc[i];
          if (f.tilg === "pdf" && !(a === "h" || a === "v" || a === "u")) continue;
          if (f.tilg === "open" && !(a === "h" || a === "v")) continue;
          if (f.tilg === "abs" && meta.abs[i] === "0") continue;
        }
        if (f.inst && !f.inst.has(works[i].id)) continue;
        if (at) {
          const s = at[i];
          let ok = true;
          for (const t of au) if (!s.has(t)) { ok = false; break; }
          if (!ok) continue;
        }
        out[i] = 1;
      }
      return out;
    }
    function sortList(positions, mode, extra) {
      const cit = (i) => works[i].citations || 0;
      const arr = positions.slice();
      if (mode === "cited") arr.sort((a, b) => (cit(b) - cit(a)) || (a - b));
      else if (mode === "new") arr.sort((a, b) => ((year[b] || 0) - (year[a] || 0)) || (cit(b) - cit(a)) || (a - b));
      else if (mode === "old") arr.sort((a, b) => ((year[a] || 9999) - (year[b] || 9999)) || (cit(b) - cit(a)) || (a - b));
      else if (mode === "first" && extra) {
        const sc = extra.scores, mx = extra.max;
        const rf = (i) => readFirstScore(sc.get(i) || 0, mx, cit(i), meta.acc[i]);
        arr.sort((a, b) => (rf(b) - rf(a)) || (a - b));
      }
      return arr;
    }
    let titleK = null;
    const titleKeys = () => {
      if (!titleK) titleK = works.map((w) => " " + tokenize(w.title || "", fm).join(" ") + " ");
      return titleK;
    };
    return { n, works, meta, year, mask, sortList, kindGroup: kg, titleKeys };
  }

  /* Kandidatpool for andre sorteringar enn relevans (endring 3): dekning == 1 pluss treffmengda */
  function sortPool(result) {
    const seen = new Set(), pool = [];
    for (const e of result.lex.full) if (!seen.has(e.d)) { seen.add(e.d); pool.push(e.d); }
    for (const e of result.hits) if (!seen.has(e.d)) { seen.add(e.d); pool.push(e.d); }
    return pool;
  }

  /* Gammal delstrengsøking (før lex.json er lasta). qf = føreberekna foldet streng per verk. */
  function legacySearch(qf, query, fm, mask, limit) {
    const toks = tokenize(query, fm);
    if (!toks.length) return [];
    const out = [];
    for (let i = 0; i < qf.length; i++) {
      if (mask && !mask[i]) continue;
      let ok = true;
      for (const t of toks) if (qf[i].indexOf(t) < 0) { ok = false; break; }
      if (ok) out.push(i);
    }
    return limit ? out.slice(0, limit) : out;
  }

  const API = {
    FOLD_MAP, PARAMS, NORDIC,
    fold, tokenize, normalizeKey, decodeQV, l2normalize,
    createIndex, createEngine, buildGroup, coreTokens, lexical, semanticTop, prfTop, fuse, run,
    readFirstScore, kindGroup, createCorpus, sortPool, legacySearch,
  };
  if (typeof module === "object" && module.exports) { module.exports = API; } else { window.DTSearch = API; }
})();
