// The selection model: state S, data columns D, masks, utval, facet counts,
// subscribers, URL hash and history rules. Nothing else mutates S.
import { fold, termNokkel, kutt } from "./hjelp.js?v=27";
import * as data from "./data.js?v=27";

export const VISNINGAR = ["kart", "nett", "verda", "siteringar", "tid"];
const SIT_DELAR = ["saman", "nabolag", "straum", "tid"];
const STRAUM = ["kanal", "land", "tiar"];
const FARGAR = ["tema", "land", "kanal", "ar"];
const SORTAR = ["auto", "sitert", "nyast", "eldst", "tittel", "relevans"];
export const AR_MIN = 1983, AR_MAX = 2026;

export const tomeFilter = () => ({
  ar: null, land: new Set(), tema: new Set(), kanal: new Set(), kgr: new Set(), type: new Set(), lag: new Set(),
  pdf: false, q: "", qv: false, qd: false, inst: new Set(), forf: new Set(), fland: new Set(), stad: new Set(), par: null,
  kanon: new Set(), siterer: null, term: new Set(), lik: null, omr: null,
});

export const S = {
  vis: "kart",
  f: tomeFilter(),
  verk: null,
  kart: { farge: "tema", z: null },
  nett: { modus: "inst", z: null },
  verda: { z: null },
  sit: { del: "saman", ego: null, straum: "kanal", z: null },
  tid: { termar: [], tv: "del", termarSett: false },
  sort: "auto",
};

export const DIMS = ["ar", "land", "tema", "kanal", "kgr", "type", "lag", "pdf", "q", "inst", "forf", "fland", "stad", "par", "kanon", "siterer", "term", "lik", "omr"];
const LAT = { stad: ["stader.json"], par: ["stader.json"], kanon: ["siteringar.json"], siterer: ["siteringar.json"], term: ["tid.json", "termar.bin"], lik: ["naboar.bin"] };
export const DIM_NAMN = { term: "Ord", stad: "Stad", par: "Stader", kanon: "Siterer", siterer: "Referansar til", lik: "Liknar" };

// ---------- data ----------
export const D = { n: 0, klar: false };

export function forbredVerk(v) {
  const k = v.kol, n = v.n;
  D.n = n; D.verk = v; D.kol = k;
  D.ar = Int16Array.from(k.ar); D.lag = Uint8Array.from(k.lag); D.type = Uint8Array.from(k.type);
  D.kanal = Int16Array.from(k.kanal); D.sit = Int32Array.from(k.sit); D.pdf = Uint8Array.from(k.pdf);
  D.tema = Uint8Array.from(k.tema); D.x = Float32Array.from(k.x); D.y = Float32Array.from(k.y);
  D.merk = Uint8Array.from(k.merk);
  D.kgrAv = new Uint8Array(n);
  const ukjendKgr = v.kanalgrupper.findIndex((g) => g.k === "ukjend");
  for (let i = 0; i < n; i++) D.kgrAv[i] = D.kanal[i] < 0 ? ukjendKgr : v.kanalar[D.kanal[i]].g;
  D.landBits = new Uint8Array(n);
  for (let i = 0; i < n; i++) { let b = 0; for (const j of k.land[i]) b |= 1 << j; D.landBits[i] = b; }
  D.idx = new Map(k.id.map((id, i) => [id, i]));
  const kart = (arr) => new Map(arr.map((x, i) => [x.k, i]));
  D.temaIdx = kart(v.tema); D.kanalIdx = kart(v.kanalar); D.kgrIdx = kart(v.kanalgrupper); D.typeIdx = kart(v.typar);
  D.instIdx = kart(v.institusjonar); D.forfIdx = kart(v.forfattarar); D.flandIdx = kart(v.land_alle); D.landIdx = kart(v.land);
  D.ukjendKgr = ukjendKgr;
  D.klar = true;
}

const forberedde = new Set();
// Loads and prepares a lazy file (or pair). Resolves {ok, feil}.
export async function sikre(namn) {
  if (forberedde.has(namn)) return { ok: true };
  const r = await data.last(namn, { hoy: namn === "lenker.json" });
  if (!r.ok) return r;
  if (!forberedde.has(namn)) {
    // a broken file (odd length, wrong shape) is a failed file, not an endless "Lastar"
    try { forbered(namn, r.data); } catch (e) {
      console.error(`Utforsk: ${namn} kunne ikkje lesast`, e);
      data.merkFeil(namn);
      return { ok: false, feil: namn };
    }
    forberedde.add(namn);
  }
  return { ok: true };
}
export const harFil = (namn) => forberedde.has(namn);

function forbered(namn, x) {
  const n = D.n;
  if (namn === "lenker.json") D.lenker = x;
  else if (namn === "naboar.bin") {
    D.nabo = new Uint16Array(x, 0, n * 10);
    D.naboCos = new Uint8Array(x, n * 20, n * 10);
  } else if (namn === "stader.json") {
    D.stader = x;
    D.stadIdx = new Map(x.stader.map((s, i) => [s.k, i]));
    const is = x.inst_stad;
    D.verkStader = new Array(n);
    for (let i = 0; i < n; i++) {
      const s = [];
      for (const j of D.kol.inst[i]) { const p = is[j]; if (p >= 0 && !s.includes(p)) s.push(p); }
      D.verkStader[i] = s;
    }
  } else if (namn === "siteringar.json") {
    D.sitd = x;
    D.refOff = Int32Array.from(x.ref_off); D.refTil = Int32Array.from(x.ref_til);
    D.nSitert = Int32Array.from(x.n_sitert);
    D.m = x.kjelder.k.length;
    D.kjeldeIdx = new Map(x.kjelder.k.map((k, j) => [k, n + j]));
    // unique labels for the nodes of the co-citation map (two different works can share
    // "Schön 1992" as surname and year; the builder makes the map labels unique)
    D.kartMerk = new Map();
    if (x.kart && x.kart.merkelapp) x.kart.noder.forEach((v, p) => D.kartMerk.set(v, x.kart.merkelapp[p]));
  } else if (namn === "tid.json") {
    D.tidd = x;
    D.termIdx = new Map(x.termar.k.map((k, t) => [k, t]));
    D.termFold = x.termar.k.map((k) => fold(k));
  } else if (namn === "termar.bin") {
    D.postingar = new Uint16Array(x);
  }
}

// Node index for a cited key: corpus work id or kjelde key.
export function nodeAv(key) {
  if (D.idx.has(key)) return D.idx.get(key);
  if (D.kjeldeIdx && D.kjeldeIdx.has(key)) return D.kjeldeIdx.get(key);
  return -1;
}
export function nodeKey(v) {
  return v < D.n ? D.kol.id[v] : D.sitd.kjelder.k[v - D.n];
}
export function nodeTittel(v) {
  return v < D.n ? D.kol.tittel[v] : D.sitd.kjelder.tittel[v - D.n];
}
export function merkelapp(v) {
  if (D.kartMerk && D.kartMerk.has(v)) return D.kartMerk.get(v);
  if (v >= D.n) return D.sitd.kjelder.merkelapp[v - D.n];
  const f = D.kol.forf[v];
  const nm = f.length ? D.verk.forfattarar[f[0]].namn : "";
  const etter = nm.includes(",") ? nm.split(",")[0].trim() : nm.trim().split(/\s+/).pop();
  return `${etter || kutt(D.kol.tittel[v], 20)} ${D.ar[v]}`;
}

// ---------- search index (amendments 1, 47) ----------
const STOPP = new Set(["in", "of", "the", "and", "og", "for", "i", "på", "pa", "med", "av", "til"]);
let sok = null; // {ord: sorted words, post: Map word -> Int32Array}
export const sokKlar = () => !!sok;
export function byggSok() {
  if (sok) return;
  const n = D.n, k = D.kol, v = D.verk;
  const post = new Map();
  const tittelOrd = new Array(n);
  for (let i = 0; i < n; i++) {
    const deler = [k.tittel[i]];
    for (const f of k.forf[i]) deler.push(v.forfattarar[f].namn);
    if (D.kanal[i] >= 0) deler.push(v.kanalar[D.kanal[i]].namn);
    for (const j of k.inst[i]) deler.push(v.institusjonar[j].namn);
    const ord = new Set();
    for (const w of fold(deler.join(" ")).split(/[^\p{L}\p{N}-]+/u)) {
      if (!w) continue;
      if (w.includes("-")) { ord.add(w.replace(/-/g, "")); for (const d of w.split("-")) if (d) ord.add(d); }
      else ord.add(w);
    }
    for (const o of ord) {
      if (!o) continue;
      let l = post.get(o);
      if (!l) { l = []; post.set(o, l); }
      l.push(i);
    }
    tittelOrd[i] = fold(k.tittel[i]).split(/[^\p{L}\p{N}-]+/u).flatMap((w) => (w.includes("-") ? [w.replace(/-/g, ""), ...w.split("-")] : [w])).filter(Boolean);
  }
  const ord = [...post.keys()].sort();
  sok = { ord, post, tittelOrd };
}
export function klargjerSok() {
  if (sok) return;
  byggSok();
  if (aktiv("q")) { rekn(["q"]); meld({ filter: true, dims: ["q"] }); }
}
export function sokTokens(q) {
  // hyphenated words are joined ("co-design" -> "codesign"), as in the haystack
  const alle = fold(q).split(/[^\p{L}\p{N}-]+/u).map((w) => w.replace(/-/g, "")).filter(Boolean);
  let t = alle.filter((x) => x.length > 3 && !STOPP.has(x));
  if (!t.length) t = alle.filter((x) => x.length >= 2 && !STOPP.has(x));
  t = [...new Set(t)];
  return t.map((x) => ({ heil: x, p: x.length >= 7 ? x.slice(0, 6) : x }));
}
function prefiksTreff(p, stempel, tal, runde) {
  const o = sok.ord;
  let lo = 0, hi = o.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (o[mid] < p) lo = mid + 1; else hi = mid; }
  for (let j = lo; j < o.length && o[j].startsWith(p); j++) {
    for (const i of sok.post.get(o[j])) if (stempel[i] !== runde) { stempel[i] = runde; tal[i]++; }
  }
}
export const sokInfo = { tokens: [], delvis: false };
function qMaske(q) {
  const n = D.n, M = new Uint8Array(n);
  const tokens = sokTokens(q);
  sokInfo.tokens = tokens; sokInfo.delvis = false;
  if (!tokens.length) { M.fill(1); return M; }
  const tal = new Uint8Array(n), stempel = new Int32Array(n).fill(-1);
  tokens.forEach((t, r) => prefiksTreff(t.p, stempel, tal, r));
  const T = tokens.length;
  let c = 0, minst1 = 0;
  for (let i = 0; i < n; i++) { if (tal[i] === T) { M[i] = 1; c++; } if (tal[i] > 0) minst1++; }
  let utanEin = 0;
  if (T > 2) for (let i = 0; i < n; i++) if (tal[i] >= T - 1) utanEin++;
  sokInfo.streng = c; sokInfo.minst1 = minst1; sokInfo.utanEin = utanEin; sokInfo.vid = false;
  if (T > 1 && S.f.qv) {
    // the reader chose "at least one of the words"
    for (let i = 0; i < n; i++) M[i] = tal[i] > 0 ? 1 : 0;
    sokInfo.vid = true;
  } else if (T > 2 && (c === 0 || S.f.qd)) {
    // three or more words: the works with every word come first, as for two words; the set
    // with all but one word is the default only when no work has them all, and otherwise an
    // offer the reader can take (qd)
    const min = T - 1;
    for (let i = 0; i < n; i++) M[i] = tal[i] >= min ? 1 : 0;
    sokInfo.delvis = true;
  }
  sokInfo.tal = tal;
  return M;
}
export function relevans(i) {
  const toks = sokInfo.tokens;
  if (!toks.length || !sok) return 0;
  const to = sok.tittelOrd[i];
  let s = 0;
  for (const t of toks) {
    if (to.includes(t.heil)) s += 3;
    else if (to.some((w) => w.startsWith(t.p))) s += 2;
    else s += 1;
  }
  return s;
}

// ---------- masks ----------
const M = {};            // dim -> Uint8Array
export let utval = new Uint8Array(0);
export let valt = 0;
let versjon = 0;
export const versjonNo = () => versjon;
const aktiv = (d, f = S.f) => {
  const v = f[d];
  if (v == null || v === false || v === "") return false;
  if (v instanceof Set) return v.size > 0;
  return true;
};
export const aktiveDims = () => DIMS.filter((d) => aktiv(d));
export const harFilter = () => DIMS.some((d) => aktiv(d));
// Status of a lazy dim: "ok" | "lastar" | "feil"
export function dimStatus(d) {
  const f = LAT[d];
  if (!f) return d === "q" && !sok ? "lastar" : "ok";
  if (f.every((x) => forberedde.has(x))) return "ok";
  return f.some((x) => data.filStatus(x) === "feil") ? "feil" : "lastar";
}
export const brukt = (d) => aktiv(d) && dimStatus(d) === "ok";

function polygonInne(poly, x, y) {
  let inne = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inne = !inne;
  }
  return inne;
}

function lagMaske(d) {
  const n = D.n, f = S.f, k = D.kol, m = new Uint8Array(n);
  const forKvar = (fn) => { for (let i = 0; i < n; i++) m[i] = fn(i) ? 1 : 0; };
  const fraSett = (sett, idxMap) => new Set([...sett].map((x) => idxMap.get(x)).filter((x) => x != null));
  switch (d) {
    case "ar": { const [a, b] = f.ar; forKvar((i) => D.ar[i] >= a && D.ar[i] <= b); break; }
    case "land": {
      let bits = 0; const ukj = f.land.has("X");
      for (const c of f.land) { const j = D.landIdx.get(c); if (j != null) bits |= 1 << j; }
      forKvar((i) => (D.landBits[i] & bits) !== 0 || (ukj && D.landBits[i] === 0));
      break;
    }
    case "tema": { const s = fraSett(f.tema, D.temaIdx); forKvar((i) => s.has(D.tema[i])); break; }
    case "kanal": { const s = fraSett(f.kanal, D.kanalIdx); forKvar((i) => D.kanal[i] >= 0 && s.has(D.kanal[i])); break; }
    case "kgr": { const s = fraSett(f.kgr, D.kgrIdx); forKvar((i) => s.has(D.kgrAv[i])); break; }
    case "type": { const s = fraSett(f.type, D.typeIdx); forKvar((i) => s.has(D.type[i])); break; }
    case "lag": { const a = f.lag.has("openalex"), b = f.lag.has("arkiv"); forKvar((i) => (D.lag[i] === 0 ? a : b)); break; }
    case "pdf": forKvar((i) => D.pdf[i] === 0); break;
    case "q": return qMaske(f.q);
    case "inst": { const s = fraSett(f.inst, D.instIdx); forKvar((i) => k.inst[i].some((j) => s.has(j))); break; }
    case "forf": { const s = fraSett(f.forf, D.forfIdx); forKvar((i) => k.forf[i].some((j) => s.has(j))); break; }
    case "fland": { const s = fraSett(f.fland, D.flandIdx); forKvar((i) => k.fland[i].some((j) => s.has(j))); break; }
    case "stad": { const s = fraSett(f.stad, D.stadIdx); forKvar((i) => D.verkStader[i].some((p) => s.has(p))); break; }
    case "par": {
      const a = D.stadIdx.get(f.par[0]), b = D.stadIdx.get(f.par[1]);
      forKvar((i) => { const s = D.verkStader[i]; return s.includes(a) && s.includes(b); });
      break;
    }
    case "kanon": {
      const s = new Set([...f.kanon].map(nodeAv).filter((v) => v >= 0));
      forKvar((i) => { for (let r = D.refOff[i]; r < D.refOff[i + 1]; r++) if (s.has(D.refTil[r])) return true; return false; });
      break;
    }
    case "siterer": {
      const mal = siterarMal(f.siterer);
      forKvar((i) => { for (let r = D.refOff[i]; r < D.refOff[i + 1]; r++) if (mal(D.refTil[r])) return true; return false; });
      break;
    }
    case "term": {
      for (const key of f.term) {
        const t = D.termIdx.get(key);
        if (t == null) continue;
        const o = D.tidd.off;
        for (let p = o[t]; p < o[t + 1]; p++) m[D.postingar[p]] = 1;
      }
      break;
    }
    case "lik": {
      const i = D.idx.get(f.lik);
      if (i != null) { m[i] = 1; for (let r = 0; r < 10; r++) m[D.nabo[i * 10 + r]] = 1; }
      break;
    }
    case "omr": forKvar((i) => polygonInne(f.omr, D.x[i], D.y[i])); break;
    default: m.fill(1);
  }
  return m;
}

// Target predicate for the `siterer` filter and the flows. modus kgr|land|tiar.
export const TIAR = [
  { k: "f1980", namn: "før 1980" }, { k: "1980", namn: "1980-åra" }, { k: "1990", namn: "1990-åra" }, { k: "2000", namn: "2000-åra" },
  { k: "2010", namn: "2010-åra" }, { k: "2020", namn: "2020-åra" }, { k: "u", namn: "Ukjent år" },
];
export function tiarAv(ar) {
  if (ar == null) return "u";
  if (ar < 1980) return "f1980";
  return String(Math.min(2020, Math.floor(ar / 10) * 10));
}
export function malKgr(v) { return v < D.n ? D.kgrAv[v] : D.sitd.kjelder.kgr[v - D.n]; }
export function malLand(v) { return v < D.n ? D.kol.fland[v] : D.sitd.kjelder.fland[v - D.n]; }
export function malAr(v) { return v < D.n ? D.ar[v] : D.sitd.kjelder.ar[v - D.n]; }
export function landGruppe(j) {
  const topp = D.sitd.land_topp || [];
  return topp.includes(j) ? D.verk.land_alle[j].k : "andre";
}
function siterarMal(s) {
  if (s.modus === "kgr") { const g = D.kgrIdx.get(s.nokkel); return (v) => malKgr(v) === g; }
  if (s.modus === "tiar") return (v) => tiarAv(malAr(v)) === s.nokkel;
  if (s.modus === "land") {
    return (v) => {
      const l = malLand(v);
      if (!l.length) return s.nokkel === "X";
      return l.some((j) => landGruppe(j) === s.nokkel);
    };
  }
  return () => false;
}

function rekn(dims) {
  for (const d of dims) {
    if (brukt(d)) M[d] = lagMaske(d);
    else delete M[d];
  }
  const n = D.n;
  if (utval.length !== n) utval = new Uint8Array(n);
  const ms = Object.keys(M).map((d) => M[d]);
  let c = 0;
  for (let i = 0; i < n; i++) {
    let ok = 1;
    for (let j = 0; j < ms.length; j++) if (!ms[j][i]) { ok = 0; break; }
    utval[i] = ok; c += ok;
  }
  valt = c;
  versjon++;
  utanCache.clear();
}

const utanCache = new Map();
// Selection with some masks left out (facets, Tid, term curves).
export function utvalUtan(dims) {
  const key = dims.slice().sort().join(",");
  if (utanCache.has(key)) return utanCache.get(key);
  const ms = Object.keys(M).filter((d) => !dims.includes(d)).map((d) => M[d]);
  const n = D.n, u = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    let ok = 1;
    for (let j = 0; j < ms.length; j++) if (!ms[j][i]) { ok = 0; break; }
    u[i] = ok;
  }
  utanCache.set(key, u);
  return u;
}
export const tal = (u) => { let c = 0; for (let i = 0; i < u.length; i++) c += u[i]; return c; };

// Facet counts for dimension d (1.3, amendment 60 for land).
export function fasettal(d) {
  const u = utvalUtan([d]), n = D.n, v = D.verk;
  if (d === "ar") {
    const c = new Int32Array(AR_MAX - AR_MIN + 1);
    for (let i = 0; i < n; i++) if (u[i]) c[D.ar[i] - AR_MIN]++;
    return c;
  }
  const c = new Map();
  const inc = (k) => c.set(k, (c.get(k) || 0) + 1);
  for (let i = 0; i < n; i++) {
    if (!u[i]) continue;
    switch (d) {
      case "land": { const b = D.landBits[i]; if (!b) inc("X"); else for (let j = 0; j < 5; j++) if (b & (1 << j)) inc(v.land[j].k); break; }
      case "tema": inc(v.tema[D.tema[i]].k); break;
      case "kanal": if (D.kanal[i] >= 0) inc(v.kanalar[D.kanal[i]].k); break;
      case "kgr": inc(v.kanalgrupper[D.kgrAv[i]].k); break;
      case "type": inc(v.typar[D.type[i]].k); break;
      case "lag": inc(D.lag[i] ? "arkiv" : "openalex"); break;
      case "pdf": if (D.pdf[i] === 0) inc("1"); break;
      default: break;
    }
  }
  return c;
}

// ---------- subscribers ----------
const abonnentar = new Set();
export const abonner = (fn) => { abonnentar.add(fn); return () => abonnentar.delete(fn); };
let ventande = null;
function meld(e) {
  if (!ventande) {
    ventande = { filter: false, vis: false, verk: false, sort: false, popstate: false, visning: new Set(), dims: new Set() };
    requestAnimationFrame(() => {
      if (!ventande) return;
      const ev = ventande; ventande = null;
      for (const fn of abonnentar) { try { fn(S, ev); } catch (err) { console.error(err); } }
    });
  }
  for (const k of ["filter", "vis", "verk", "sort", "popstate"]) if (e[k]) ventande[k] = true;
  if (e.visning) for (const x of e.visning) ventande.visning.add(x);
  if (e.dims) for (const x of e.dims) ventande.dims.add(x);
}
// Synchronous flush for measuring.
export function meldNo() {
  if (!ventande) return;
  const ev = ventande; ventande = null;
  for (const fn of abonnentar) { try { fn(S, ev); } catch (err) { console.error(err); } }
}

// ---------- serialisation ----------
const lst = (s) => [...s].map(encodeURIComponent).join(",");
function dimTekst(d, f = S.f) {
  const v = f[d];
  if (!aktiv(d, f)) return "";
  switch (d) {
    case "ar": return `${v[0]}-${v[1]}`;
    case "pdf": return "1";
    case "q": return encodeURIComponent(v);
    case "par": return v.map(encodeURIComponent).join("~");
    case "siterer": return `${v.modus}:${encodeURIComponent(v.nokkel)}`;
    case "lik": return encodeURIComponent(v);
    case "omr": return v.map((p) => `${Math.round(p[0])},${Math.round(p[1])}`).join(",");
    default: return lst(v);
  }
}
const VIS_NOKLAR = () => ({
  "kart.farge": S.kart.farge, "nett.modus": S.nett.modus, "sit.del": S.sit.del, "sit.ego": S.sit.ego || "",
  "sit.straum": S.sit.straum, "tid.termar": S.tid.termar.join("|"), "tid.tv": S.tid.tv,
});
function zFor(vis) {
  const z = vis === "siteringar" ? (S.sit.del === "saman" ? S.sit.z : null) : vis === "tid" ? null : S[vis].z;
  return z ? `${z[0].toFixed(2)},${Math.round(z[1])},${Math.round(z[2])}` : "";
}
export function lagHash() {
  const p = [];
  for (const d of DIMS) { const t = dimTekst(d); if (t) p.push(`${d}=${t}`); if (d === "q" && t && S.f.qv) p.push("qv=1"); if (d === "q" && t && S.f.qd) p.push("qd=1"); }
  if (S.verk) p.push(`verk=${encodeURIComponent(S.verk)}`);
  // view settings go in the link only for the view on screen, so links stay short
  const v = S.vis;
  if (v === "kart" && S.kart.farge !== "tema") p.push(`farge=${S.kart.farge}`);
  if (v === "nett" && S.nett.modus !== "inst") p.push(`nett=${S.nett.modus}`);
  if (v === "siteringar") {
    if (S.sit.del !== "saman") p.push(`del=${S.sit.del}`);
    if (S.sit.ego && S.sit.del === "nabolag") p.push(`ego=${encodeURIComponent(S.sit.ego)}`);
    if (S.sit.straum !== "kanal" && S.sit.del === "straum") p.push(`straum=${S.sit.straum}`);
  }
  if (v === "tid") {
    if (S.tid.termarSett) p.push(`t=${S.tid.termar.map(encodeURIComponent).join(",")}`);
    if (S.tid.tv !== "del") p.push(`tv=${S.tid.tv}`);
  }
  if (S.sort !== "auto") p.push(`sort=${S.sort}`);
  const z = zFor(S.vis);
  if (z) p.push(`z=${z}`);
  return `#${S.vis}${p.length ? "?" + p.join("&") : ""}`;
}

const ID_RE = /^[A-Za-z0-9:_.-]+$/;
let infoGitt = false;
function ugyldig(k, v) {
  if (!infoGitt) { console.info(`Utforsk: ignorerte ugyldig verdi i lenka (${k}=${v}).`); infoGitt = true; }
}
// Parse a hash into a fresh partial state. Returns {vis, f, verk, kart, nett, sit, tid, sort, z}.
export function lesHash(hash) {
  const h = (hash || "").replace(/^#/, "");
  const [visDel, q = ""] = h.split("?");
  const ut = { vis: VISNINGAR.includes(visDel) ? visDel : "kart", f: tomeFilter(), verk: null, farge: "tema", nett: "inst", del: "saman", ego: null, straum: "kanal", t: null, tv: "del", sort: "auto", z: null };
  if (visDel && !VISNINGAR.includes(visDel)) ugyldig("vis", visDel);
  for (const del of q.split("&")) {
    if (!del) continue;
    const i = del.indexOf("=");
    const k = i < 0 ? del : del.slice(0, i);
    const raw = i < 0 ? "" : del.slice(i + 1);
    let v;
    try { v = decodeURIComponent(raw); } catch (e) { ugyldig(k, raw); continue; }
    const liste = () => raw.split(",").map((x) => { try { return decodeURIComponent(x); } catch (e) { return ""; } }).filter((x) => x && ID_RE.test(x) || (k === "term" && x));
    const f = ut.f;
    switch (k) {
      case "ar": {
        const m = /^(\d{4})-(\d{4})$/.exec(v);
        const a = m ? Math.max(AR_MIN, +m[1]) : 0, b = m ? Math.min(AR_MAX, +m[2]) : 0;
        if (m && a <= b) f.ar = [a, b]; else ugyldig(k, v);
        break;
      }
      case "land": f.land = new Set(liste().filter((x) => /^[A-Z]{1,2}$/.test(x))); break;
      case "tema": case "kanal": case "kgr": case "type": case "inst": case "forf": case "fland": case "stad": case "kanon":
        f[k] = new Set(liste()); break;
      case "lag": f.lag = new Set(liste().filter((x) => x === "openalex" || x === "arkiv")); break;
      case "term": f.term = new Set(liste().map(termNokkel).filter(Boolean)); break;
      case "pdf": f.pdf = v === "1"; break;
      case "q": f.q = v.slice(0, 200); break;
      case "qv": f.qv = v === "1"; break;
      case "qd": f.qd = v === "1"; break;
      case "par": { const a = raw.split("~").map((x) => decodeURIComponent(x)); if (a.length === 2 && a.every((x) => ID_RE.test(x))) f.par = a; else ugyldig(k, v); break; }
      case "siterer": { const m = /^(kgr|land|tiar):([A-Za-z0-9_]+)$/.exec(v); if (m) f.siterer = { modus: m[1], nokkel: m[2] }; else ugyldig(k, v); break; }
      case "lik": if (ID_RE.test(v)) f.lik = v; else ugyldig(k, v); break;
      case "omr": {
        const t = v.split(",").map(Number);
        if (t.length >= 6 && t.length % 2 === 0 && t.length <= 48 && t.every(Number.isFinite)) { f.omr = []; for (let j = 0; j < t.length; j += 2) f.omr.push([t[j], t[j + 1]]); } else ugyldig(k, v);
        break;
      }
      case "verk": if (ID_RE.test(v)) ut.verk = v; else ugyldig(k, v); break;
      case "farge": if (FARGAR.includes(v)) ut.farge = v; else ugyldig(k, v); break;
      case "nett": if (v === "inst" || v === "forf") ut.nett = v; else ugyldig(k, v); break;
      case "del": { const vv = v === "kart" ? "saman" : v; if (SIT_DELAR.includes(vv)) ut.del = vv; else ugyldig(k, v); break; }
      case "ego": if (ID_RE.test(v)) ut.ego = v; else ugyldig(k, v); break;
      case "straum": if (STRAUM.includes(v)) ut.straum = v; else ugyldig(k, v); break;
      case "t": ut.t = raw ? raw.split(",").map((x) => { try { return termNokkel(decodeURIComponent(x)); } catch (e) { return ""; } }).filter(Boolean).slice(0, 6) : []; break;
      case "tv": if (v === "del" || v === "tal") ut.tv = v; else ugyldig(k, v); break;
      case "sort": if (SORTAR.includes(v)) ut.sort = v; else ugyldig(k, v); break;
      case "z": { const t = v.split(",").map(Number); if (t.length === 3 && t.every(Number.isFinite) && t[0] > 0) ut.z = t; else ugyldig(k, v); break; }
      default: break;
    }
  }
  return ut;
}

// The link holds the settings of the view on screen only (lagHash); on Back/Forward the
// other views keep what they had.
function bruk(p, start) {
  S.vis = p.vis; S.f = p.f; S.verk = p.verk; S.sort = p.sort;
  if (start || p.vis === "kart") S.kart.farge = p.farge;
  if (start || p.vis === "nett") S.nett.modus = p.nett;
  if (start || p.vis === "siteringar") { S.sit.del = p.del; S.sit.ego = p.ego; S.sit.straum = p.straum; }
  if (start || p.vis === "tid") {
    S.tid.tv = p.tv;
    if (p.t) { S.tid.termar = p.t; S.tid.termarSett = true; } else { S.tid.termarSett = false; S.tid.termar = []; }
  }
  const z = p.z;
  if (p.vis === "kart") S.kart.z = z;
  else if (p.vis === "nett") S.nett.z = z;
  else if (p.vis === "verda") S.verda.z = z;
  else if (p.vis === "siteringar") S.sit.z = z;
}

// ---------- history ----------
let sisteGest = null;
let urlTid = 0;
let urlModus = null;
function skrivUrl(modus) {
  const h = lagHash();
  const no = location.hash || "#kart";
  if (h === no && modus !== "push-alltid") return;
  if (modus === "replace") { history.replaceState(null, "", h); return; }
  if (modus.startsWith("kont:")) {
    const key = modus.slice(5);
    if (sisteGest !== key) { history.pushState(null, "", h); sisteGest = key; } else history.replaceState(null, "", h);
    return;
  }
  sisteGest = null;
  history.pushState(null, "", h);
}
export function avsluttGest(key) { if (!key || sisteGest === key) sisteGest = null; }

// Snapshot of comparable parts, for diffing.
function bilete() {
  const f = {};
  for (const d of DIMS) f[d] = dimTekst(d);
  if (S.f.qv && S.f.q) f.q += "|v";
  if (S.f.qd && S.f.q) f.q += "|d";
  return { vis: S.vis, verk: S.verk, f, v: VIS_NOKLAR(), sort: S.sort };
}

// endre(fn, {hist: "push"|"replace"|"kont:<key>"|"ingen", utsett: ms})
export function endre(fn, { hist = "push", utsett = 0 } = {}) {
  const for_ = bilete();
  fn(S);
  // normalise
  if (S.f.ar && S.f.ar[0] <= AR_MIN && S.f.ar[1] >= AR_MAX) S.f.ar = null;
  if (!S.f.q) { S.f.qv = false; S.f.qd = false; }
  const etter = bilete();
  const dims = DIMS.filter((d) => for_.f[d] !== etter.f[d]);
  const visning = new Set(Object.keys(etter.v).filter((k) => for_.v[k] !== etter.v[k]));
  const e = { filter: dims.length > 0, dims, vis: for_.vis !== etter.vis, verk: for_.verk !== etter.verk, visning, sort: for_.sort !== etter.sort };
  if (e.filter) {
    rekn(dims);
    for (const d of dims) if (aktiv(d) && LAT[d] && dimStatus(d) !== "ok") lastDim(d);
  }
  if (e.filter || e.vis || e.verk || visning.size || e.sort) meld(e);
  if (hist === "ingen") return e;
  clearTimeout(urlTid);
  if (utsett) { urlModus = hist; urlTid = setTimeout(() => { urlTid = 0; skrivUrl(urlModus); }, utsett); }
  else { urlTid = 0; skrivUrl(hist); }
  return e;
}
// Write a pending delayed URL now (before the link is copied).
export function skrivUrlNo() {
  if (urlTid) { clearTimeout(urlTid); urlTid = 0; skrivUrl(urlModus); }
  clearTimeout(zTid);
  const h = lagHash();
  if (h !== location.hash) history.replaceState(null, "", h);
}

// Zoom of a view: always replaceState in the current entry, no notification.
let zTid = 0;
export function settZoom(vis, z) {
  if (vis === "siteringar") S.sit.z = z; else S[vis].z = z;
  clearTimeout(zTid);
  zTid = setTimeout(() => { if (S.vis === vis) { const h = lagHash(); if (h !== location.hash) history.replaceState(null, "", h); } }, 150);
}

const lastar = new Set();
let navToken = 0;
function lastDim(d) {
  for (const namn of LAT[d]) {
    if (forberedde.has(namn) || lastar.has(namn)) continue;
    lastar.add(namn);
    const token = navToken;
    sikre(namn).then((r) => {
      lastar.delete(namn);
      void token;
      // words from a link that are not in the word list are dropped (like other invalid values),
      // so the count never shows a filter that cannot match anything
      if (r.ok && namn === "tid.json") {
        for (const k of [...S.f.term]) if (!D.termIdx.has(k)) { S.f.term.delete(k); ugyldig("term", k); }
        const h = lagHash();
        if (h !== location.hash) history.replaceState(null, "", h);
      }
      const dims = DIMS.filter((x) => LAT[x] && LAT[x].includes(namn) && aktiv(x));
      if (dims.length) { rekn(dims); meld({ filter: true, dims }); }
      else meld({ filter: true, dims: [] });
    });
  }
}
export function provIgjen(d) {
  if (LAT[d]) lastDim(d);
}
export const ventar = () => aktiveDims().some((d) => dimStatus(d) === "lastar");
export const ikkjeIBruk = () => aktiveDims().filter((d) => dimStatus(d) === "feil");

// Apply the current URL (start and popstate). Never writes history.
export function fraUrl({ start = false } = {}) {
  const p = lesHash(location.hash);
  navToken++;
  sisteGest = null;
  // a pending delayed write (typing) belongs to the entry we are leaving
  clearTimeout(urlTid); urlTid = 0;
  bruk(p, start);
  // validate keys that need verk.json
  const f = S.f, sjekk = (d, map) => { for (const x of [...f[d]]) if (!map.has(x)) { f[d].delete(x); ugyldig(d, x); } };
  sjekk("tema", D.temaIdx); sjekk("kanal", D.kanalIdx); sjekk("kgr", D.kgrIdx); sjekk("type", D.typeIdx);
  sjekk("inst", D.instIdx); sjekk("forf", D.forfIdx); sjekk("fland", D.flandIdx);
  for (const c of [...f.land]) if (c !== "X" && !D.landIdx.has(c)) { f.land.delete(c); ugyldig("land", c); }
  if (S.verk && !D.idx.has(S.verk)) { ugyldig("verk", S.verk); S.verk = null; }
  if (f.lik && !D.idx.has(f.lik)) { ugyldig("lik", f.lik); f.lik = null; }
  if (D.termIdx) for (const k of [...f.term]) if (!D.termIdx.has(k)) { f.term.delete(k); ugyldig("term", k); }
  if (S.f.ar && S.f.ar[0] <= AR_MIN && S.f.ar[1] >= AR_MAX) S.f.ar = null;
  if (!f.q) { f.qv = false; f.qd = false; }
  if (f.q && !sok) byggSok();
  rekn(DIMS);
  for (const d of aktiveDims()) if (LAT[d] && dimStatus(d) !== "ok") lastDim(d);
  if (!start) meld({ filter: true, vis: true, verk: true, sort: true, visning: Object.keys(VIS_NOKLAR()), dims: DIMS, popstate: true });
}

export function nullstillFilter() {
  endre((s) => { s.f = tomeFilter(); });
}

// ---------- convenience setters ----------
// Toggle one value in a set dimension. erstatt: replace the set with only this value (plain click).
export function veksle(d, key, { erstatt = false, hist = "push" } = {}) {
  endre((s) => {
    const set = s.f[d];
    if (erstatt) {
      const berreDenne = set.size === 1 && set.has(key);
      set.clear();
      if (!berreDenne) set.add(key);
    } else if (set.has(key)) set.delete(key);
    else set.add(key);
  }, { hist });
}
export function fjern(d, key) {
  endre((s) => {
    const v = s.f[d];
    if (v instanceof Set) { if (key != null) v.delete(key); else v.clear(); }
    else if (d === "pdf") s.f.pdf = false;
    else if (d === "q") { s.f.q = ""; s.f.qv = false; s.f.qd = false; }
    else s.f[d] = null;
  });
}

// ---------- chips ----------
const STAD_NN = { copenhagen: "København", gothenburg: "Göteborg", helsinki: "Helsingfors", reykjavik: "Reykjavík", stockholm: "Stockholm", oslo: "Oslo" };
export function stadNamn(key) {
  if (D.stadIdx && D.stadIdx.has(key)) {
    const s = D.stader.stader[D.stadIdx.get(key)];
    return STAD_NN[fold(s.by)] || s.by;
  }
  return key;
}
export function landNamn(code) {
  if (code === "X") return "Ukjend";
  const j = D.flandIdx.get(code);
  return j != null ? D.verk.land_alle[j].namn : code;
}
export function siterarNamn(s) {
  if (!s) return "";
  if (s.modus === "kgr") { const g = D.kgrIdx.get(s.nokkel); return g != null ? D.verk.kanalgrupper[g].namn : s.nokkel; }
  if (s.modus === "tiar") { const t = TIAR.find((x) => x.k === s.nokkel); return t ? t.namn : s.nokkel; }
  if (s.nokkel === "andre") return "Andre land";
  return landNamn(s.nokkel);
}
export function termVis(key) {
  if (D.termIdx && D.termIdx.has(key)) return D.tidd.termar.vis[D.termIdx.get(key)];
  return key;
}
export function chipar() {
  const f = S.f, v = D.verk, ut = [];
  const leggTil = (dim, verdi, tekst) => {
    const st = dimStatus(dim);
    ut.push({ dim, verdi, tekst: st === "feil" ? `${tekst} (ikkje i bruk)` : tekst, feil: st === "feil" });
  };
  if (f.ar) leggTil("ar", null, `År: ${f.ar[0]} til ${f.ar[1]}`);
  for (const c of f.land) leggTil("land", c, `Nordisk land: ${c === "X" ? "Ukjend" : (v.land[D.landIdx.get(c)] || { namn: c }).namn}`);
  for (const k of f.tema) leggTil("tema", k, `Tema: ${v.tema[D.temaIdx.get(k)].namn}`);
  for (const k of f.kanal) leggTil("kanal", k, `Kanal: ${kutt(v.kanalar[D.kanalIdx.get(k)].namn, 40)}`);
  for (const k of f.kgr) leggTil("kgr", k, `Kanaltype: ${v.kanalgrupper[D.kgrIdx.get(k)].namn}`);
  for (const k of f.type) leggTil("type", k, `Type: ${v.typar[D.typeIdx.get(k)].namn}`);
  for (const k of f.lag) leggTil("lag", k, `Lag: ${k === "arkiv" ? "Arkiv" : "OpenAlex"}`);
  if (f.pdf) leggTil("pdf", null, "Berre open PDF");
  if (f.q) leggTil("q", null, `Søk: «${kutt(f.q, 30)}»${f.qv && sokInfo.tokens.length > 1 ? " (minst eitt av orda)" : sokInfo.delvis ? ` (minst ${sokInfo.tokens.length - 1} av ${sokInfo.tokens.length} ord)` : ""}`);
  for (const k of f.inst) leggTil("inst", k, `Institusjon: ${kutt(v.institusjonar[D.instIdx.get(k)].namn, 40)}`);
  for (const k of f.forf) leggTil("forf", k, `Forfattar: ${v.forfattarar[D.forfIdx.get(k)].namn}`);
  for (const k of f.fland) leggTil("fland", k, `Forfattarland: ${landNamn(k)}`);
  for (const k of f.stad) leggTil("stad", k, `Stad: ${stadNamn(k)}`);
  if (f.par) leggTil("par", null, `Stader: ${stadNamn(f.par[0])} og ${stadNamn(f.par[1])}`);
  for (const k of f.kanon) { const nv = D.sitd ? nodeAv(k) : -1; leggTil("kanon", k, `Siterer: ${nv >= 0 ? merkelapp(nv) : k}`); }
  if (f.siterer) {
    const ka = { kgr: "kanaltype ", land: "forfattarland ", tiar: "verk frå " }[f.siterer.modus] || "";
    leggTil("siterer", null, `Referansar til ${ka}${D.sitd ? siterarNamn(f.siterer) : f.siterer.nokkel}`);
  }
  for (const k of f.term) leggTil("term", k, `Ord: ${termVis(k)}`);
  if (f.lik) { const i = D.idx.get(f.lik); leggTil("lik", null, `Liknar: ${kutt(i != null ? D.kol.tittel[i] : f.lik, 30)}`); }
  if (f.omr) leggTil("omr", null, "Område i kartet");
  return ut;
}

// The filter whose removal gives the most works (amendment 37).
export function bestFjerning() {
  let best = null;
  for (const d of aktiveDims()) {
    const c = tal(utvalUtan([d]));
    if (!best || c > best.c) best = { d, c };
  }
  if (!best) return null;
  const tekst = chipar().filter((c) => c.dim === best.d).map((c) => c.tekst).join(", ");
  return { dim: best.d, tal: best.c, tekst };
}
