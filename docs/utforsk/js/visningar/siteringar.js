// Siteringar: what is cited together, the neighbourhood of one work, flows of
// who cites what, and how what is cited has moved over time.
import { esc, fmt, pst, kutt, visNamn, PALETTE_TEMA, PALETTE_GRUPPE, KGR_FARGE, FADE, FADE_ALFA, UKJEND, landFarge, plasserEtikettar, teiknEtikettar, tooltip, kort, segmentert, smal, veldigSmal, tween, rorsle, settInnhald } from "../hjelp.js?v=24";

let A, T, D, S, ramme, d3, scene, delSeg, straumSeg;
let el = {};
let K = null;          // co-citation map
let sNode = null;      // selected citing works per map node
let sAlle = null;      // per node index (n + m)
let citers = null;     // reverse CSR {off, til}
let merkPos = new Set();
let etikettar = [], forrigePlass = new Map();
let sankeyStatus = "ingen";
let naboStatus = "ingen";
let utvidaKol = new Set();
const hogreCache = {};

const DELAR = [{ k: "saman", namn: "Sitert saman" }, { k: "nabolag", namn: "Nabolag" }, { k: "straum", namn: "Straumar" }, { k: "tid", namn: "Over tid" }];

export default {
  id: "siteringar",
  filer: ["siteringar.json"],
  skript: [],
  async init(rot, api) {
    A = api; T = api.T; D = api.D; S = api.S; ramme = api.ramme; d3 = window.d3;
    delSeg = segmentert(ramme.kontroll, { namn: "Del av siteringane", verdi: S.sit.del, val: DELAR, ved: (v) => T.endre((s) => { s.sit.del = v; }) });
    ramme.flate.insertAdjacentHTML("beforeend", `<div class="sit-saman"></div><div class="sit-svg svgflate" hidden></div><div class="sidepanel sit-rang" hidden></div>`);
    el = { saman: ramme.flate.querySelector(".sit-saman"), svg: ramme.flate.querySelector(".sit-svg"), rang: ramme.flate.querySelector(".sit-rang") };
    el.saman.style.cssText = "position:absolute;inset:0";
    if (smal()) el.rang.classList.add("lukka");
    lagKart();
    lagCiters();
    scene = api.lagScene(el.saman, {
      verd: [10000, 10000], skala: [0.6, 12], rolle: "kart over siterte verk",
      teiknBase, teiknOverlay, finn, tips, klikk, kort: kortFor, tapHandling: (h) => velKanon(h.id, false), finnId: (id) => ({ id, fleire: 0 }),
      hoverEndra: () => scene.teikn(),
      vedZoom: (z) => T.settZoom("siteringar", z),
      fokusListe: () => K.storst.slice(0, 30).map((p) => ({ id: p, x: K.x[p], y: K.y[p] })),
      fokusHandling: (id) => velKanon(id, false),
      dekkaEkstra: () => [el.rang],
      heim: heimBoks,
      feil: api.feil,
    });
    el.rang.addEventListener("click", (e) => {
      const n = e.target.closest("button[data-nabolag]");
      if (n) { opneNabolag(+n.dataset.nabolag); return; }
      const b = e.target.closest("button[data-v]");
      if (b) T.veksle("kanon", T.nodeKey(+b.dataset.v), { erstatt: !(e.shiftKey || e.ctrlKey || e.metaKey) });
      const t = e.target.closest("button[data-rang]");
      if (t) { el.rang.classList.toggle("lukka"); t.setAttribute("aria-expanded", String(!el.rang.classList.contains("lukka"))); t.textContent = el.rang.classList.contains("lukka") ? "Vis" : "Gøym"; scene.storleik(); }
    });
    ramme.teikn.addEventListener("click", (e) => { const b = e.target.closest("button[data-straum]"); if (b) T.endre((s) => { s.sit.straum = b.dataset.straum; }); });
    el.svg.addEventListener("click", svgKlikk);
    el.rang.addEventListener("pointerover", rangHover);
    el.rang.addEventListener("focusin", rangHover);
    el.rang.addEventListener("pointerleave", () => { if (rangMerk.size) { rangMerk = new Set(); scene.teiknOverlay(); } });
    el.rang.addEventListener("focusout", (e) => { if (!el.rang.contains(e.relatedTarget) && rangMerk.size) { rangMerk = new Set(); scene.teiknOverlay(); } });
    el.svg.addEventListener("pointerleave", () => tooltip.skjul());
    new ResizeObserver(() => { if (S.sit.del !== "saman") teiknDel(); }).observe(ramme.flate);
    scene.storleik();
    if (S.sit.z) scene.settZ(S.sit.z);
  },
  oppdater(s, e) {
    delSeg.set(S.sit.del);
    if (e.filter || !sAlle) reknUtval();
    const saman = S.sit.del === "saman";
    el.saman.hidden = !saman;
    el.svg.hidden = saman;
    // the map is resized only when it comes into sight or the part changed (not per filter)
    if (saman) {
      // a new map (the selection's own, or back to the corpus map) starts at its home view
      const bytt = kartByte;
      if (bytt) {
        kartByte = false;
        // the home box changed: fit it first, then keep a zoom from the link only on Back/Forward
        scene.settZ(null, 0, true);
        scene.storleik();
        if ((e.popstate || e.vis) && S.sit.z) scene.settZ(S.sit.z);
        else if (S.sit.z) T.settZoom("siteringar", null);
      } else {
        if (e.vis || e.popstate || e.visning.has("sit.del")) scene.storleik();
        if (e.popstate || e.vis) scene.settZ(S.sit.z);
      }
      scene.teikn();
    }
    teiknDel();
  },
  merk(i) {
    merkPos = new Set();
    if (i != null && K) { for (let r = D.refOff[i]; r < D.refOff[i + 1]; r++) { const p = K.pos.get(D.refTil[r]); if (p != null) merkPos.add(p); } const p = K.pos.get(i); if (p != null) merkPos.add(p); }
    if (S.sit.del === "saman") scene.teiknOverlay();
    else if (S.sit.del === "nabolag") for (const b of el.svg.querySelectorAll("[data-ego-i]")) b.classList.toggle("merka", +b.dataset.egoI === i);
  },
  vis() { if (S.sit.del === "saman") scene.storleik(); },
  skjul() { tooltip.skjul(); },
  fokusUt() { return scene ? scene.fokusUt() : false; },
  scene: () => (S.sit.del === "saman" ? scene : null),
  etikettar: () => (S.sit.del === "saman" ? etikettar : []),
  sentrer(i) { const p = K && K.pos.get(i); if (p != null && S.sit.del === "saman") scene.sentrer(K.x[p], K.y[p]); },
};

// ---------- data ----------
let KG = null;   // the precomputed map of the whole corpus
let lokalNokkel = "";
function byggK(k, n) {
  const N = k.noder.length;
  const pos = new Map(k.noder.map((v, p) => [v, p]));
  const naboar = Array.from({ length: N }, () => []);
  for (const [a, b, c, w] of k.kantar) { naboar[a].push([b, w, c]); naboar[b].push([a, w, c]); }
  for (const l of naboar) l.sort((u, v) => v[1] - u[1] || u[0] - v[0]);
  const qt = A.lagIndeks(N, (p) => k.x[p], (p) => k.y[p]);
  const storst = Array.from({ length: N }, (_, p) => p).sort((a, b) => n[b] - n[a] || a - b);
  const nMaks = Math.max(1, ...n);
  return { N, noder: k.noder, x: k.x, y: k.y, gr: k.gr, kantar: k.kantar, grupper: k.grupper, pos, n, naboar, qt, storst, lokal: !!k.lokal, rMaks: (sc) => (4 + 1.15 * Math.sqrt(nMaks)) * sc.rf * Math.min(sc.k, 3) ** 0.4 };
}
function lagKart() {
  const k = D.sitd.kart;
  KG = byggK(k, k.noder.map((v) => D.nSitert[v]));
  K = KG;
}
// A small selection gets its own map: the items its works cite most, linked where at least two
// works in the selection cite both, laid out with a force layout. The whole-corpus map would
// show what the corpus cites (Dunne, Escobar) with the selection's own items missing.
const LOKAL_MAKS_VERK = 1500, LOKAL_NODAR = 45;
function lagLokal() {
  if (!T.harFilter() || T.valt > LOKAL_MAKS_VERK || K_medRef < 2) return null;
  const NM = D.n + D.m;
  const min = K_medRef >= 12 ? 2 : 1;
  const kand = [];
  for (let v = 0; v < NM; v++) if (sAlle[v] >= min && !utanTittel(v)) kand.push(v);
  if (kand.length < 6) return null;
  kand.sort((a, b) => sAlle[b] - sAlle[a] || D.nSitert[b] - D.nSitert[a] || a - b);
  const noder = kand.slice(0, LOKAL_NODAR);
  const nokkel = noder.join(",");
  if (nokkel === lokalNokkel && K && K.lokal) return K;
  const pos = new Map(noder.map((v, p) => [v, p]));
  // co-citation inside the selection
  const par = new Map();
  for (let i = 0; i < D.n; i++) {
    if (!T.utval[i]) continue;
    const ps = [];
    for (let r = D.refOff[i]; r < D.refOff[i + 1]; r++) { const p = pos.get(D.refTil[r]); if (p != null) ps.push(p); }
    for (let a = 0; a < ps.length; a++) for (let b = a + 1; b < ps.length; b++) {
      const lo = Math.min(ps[a], ps[b]), hi = Math.max(ps[a], ps[b]), key = lo * 1000 + hi;
      par.set(key, (par.get(key) || 0) + 1);
    }
  }
  const minPar = K_medRef >= 12 ? 2 : 1;
  let cMaks = 1;
  for (const c of par.values()) if (c > cMaks) cMaks = c;
  const kantar = [];
  for (const [key, c] of par) if (c >= minPar) kantar.push([Math.floor(key / 1000), key % 1000, c, c / cMaks]);
  // layout: deterministic (d3 starts nodes on a phyllotaxis spiral), 300 ticks, no animation
  const nodar = noder.map((v, p) => ({ p, r: 6 + 2.2 * Math.sqrt(sAlle[v]) }));
  const lenker = kantar.map(([a, b, , w]) => ({ source: a, target: b, w }));
  const sim = d3.forceSimulation(nodar)
    .force("link", d3.forceLink(lenker).distance((l) => 60 - 30 * l.w).strength((l) => 0.15 + 0.6 * l.w))
    .force("charge", d3.forceManyBody().strength(-90))
    .force("x", d3.forceX(0).strength(0.07)).force("y", d3.forceY(0).strength(0.07))
    .force("collide", d3.forceCollide((d) => d.r + 4))
    .stop();
  for (let t = 0; t < 300; t++) sim.tick();
  const xs = nodar.map((d) => d.x), ys = nodar.map((d) => d.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const s = 8000 / Math.max(1, x1 - x0, y1 - y0);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const x = Float64Array.from(xs, (v) => 5000 + (v - cx) * s), y = Float64Array.from(ys, (v) => 5000 + (v - cy) * s);
  // keep the group colours of the corpus map where the item is in it; the rest are grey
  const gr = noder.map((v) => { const p = KG.pos.get(v); return p != null ? KG.gr[p] : 99; });
  lokalNokkel = nokkel;
  return byggK({ noder, x, y, gr, kantar, grupper: KG.grupper, lokal: true }, noder.map((v) => sAlle[v]));
}
let K_medRef = 0;
function lagCiters() {
  const NM = D.n + D.m, cnt = new Int32Array(NM + 1);
  for (let r = 0; r < D.refTil.length; r++) cnt[D.refTil[r] + 1]++;
  for (let v = 0; v < NM; v++) cnt[v + 1] += cnt[v];
  const til = new Int32Array(D.refTil.length), fyll = cnt.slice(0, NM);
  for (let i = 0; i < D.n; i++) for (let r = D.refOff[i]; r < D.refOff[i + 1]; r++) til[fyll[D.refTil[r]]++] = i;
  citers = { off: cnt, til };
}
function reknUtval() {
  const NM = D.n + D.m;
  sAlle = new Int32Array(NM);
  let med = 0;
  for (let i = 0; i < D.n; i++) {
    if (!T.utval[i]) continue;
    const a = D.refOff[i], b = D.refOff[i + 1];
    if (D.sitd.ref_alle[i] > 0) med++;
    for (let r = a; r < b; r++) sAlle[D.refTil[r]]++;
  }
  K_medRef = med;
  const forK = K;
  K = lagLokal() || KG;
  if (K !== forK) { kartByte = true; forrigePlass = new Map(); merkPos = new Set(); rangMerk = new Set(); }
  sNode = K.noder.map((v) => sAlle[v]);
  K.medRef = med;
}
let kartByte = false;
// the box the home view fits: the box around the nodes of the map in use, so the graph fills
// the free area (not the whole square world, which leaves empty bands)
function heimBoks() {
  if (!K || !K.N) return [0, 0, 10000, 10000];
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let p = 0; p < K.N; p++) { x0 = Math.min(x0, K.x[p]); x1 = Math.max(x1, K.x[p]); y0 = Math.min(y0, K.y[p]); y1 = Math.max(y1, K.y[p]); }
  // room for the largest circle and a label beside it
  const pad = Math.max(250, 0.06 * Math.max(x1 - x0, y1 - y0));
  return [x0 - pad, y0 - pad, x1 + pad, y1 + pad];
}
const gruppeFarge = (g) => (g < PALETTE_GRUPPE.length ? PALETTE_GRUPPE[g] : g === 99 ? "#d6d6d6" : "#9a9a9a");
const lysNode = (p) => !T.harFilter() || sNode[p] > 0;
const radius = (p, sc) => (4 + 1.15 * Math.sqrt(K.n[p])) * sc.rf * Math.min(sc.k, 3) ** 0.4;
function felles() {
  const t = D.sitd.tal;
  return `Referanselister finst for ${fmt(t.siterande_verk)} av ${fmt(D.verk.n_openalex)} OpenAlex-verk. Arkivverka har ingen.`;
}

// ---------- part routing ----------
let sistFlyt = null;
function teiknDel() {
  const del = S.sit.del;
  el.rang.hidden = del !== "saman";
  // moving the legend in or out of the map is needed only when the part changes
  if (sistFlyt !== (del === "saman")) { sistFlyt = del === "saman"; ramme.settTeiknFlyt(sistFlyt, el.saman); }
  if (del === "saman") { teiknRang(); teiknSamanLinje(); return; }
  if (del === "nabolag") teiknNabolag();
  else if (del === "straum") teiknStraum();
  else teiknOverTid();
}

// ---------- 1. co-citation map ----------
function teiknBase(ctx, sc) {
  if (!K) return;
  sc.setVerd(ctx);
  const hov = typeof sc.hoverId === "number" ? sc.hoverId : null;
  const nab = new Set();
  if (hov != null) { nab.add(hov); for (const [b] of K.naboar[hov]) nab.add(b); }
  const mult = (p, a) => (hov != null && !nab.has(p) ? Math.max(0.06, a * 0.25) : a);
  for (const [a, b, c, w] of K.kantar) {
    let alfa = 0.1 + 0.5 * w;
    if (T.harFilter() && !(lysNode(a) && lysNode(b))) alfa = 0.04;
    if (hov != null) alfa = a === hov || b === hov ? 0.9 : Math.max(0.02, alfa * 0.25);
    ctx.globalAlpha = alfa;
    ctx.strokeStyle = hov != null && (a === hov || b === hov) ? "#fff" : "#dcdcdc";
    ctx.lineWidth = (0.5 + 2.5 * w) / sc.K;
    ctx.beginPath(); ctx.moveTo(K.x[a], K.y[a]); ctx.lineTo(K.x[b], K.y[b]); ctx.stroke();
    void c;
  }
  const ord = K.storst.slice().reverse();
  for (const pass of [0, 1]) {
    for (const p of ord) {
      const l = lysNode(p);
      if ((pass === 0) === l) continue;
      ctx.globalAlpha = mult(p, l ? 1 : FADE_ALFA);
      ctx.fillStyle = l ? gruppeFarge(K.gr[p]) : FADE;
      const r = radius(p, sc) / sc.K;
      ctx.beginPath(); ctx.arc(K.x[p], K.y[p], r, 0, 6.2832); ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
}
function ring(ctx, sc, p, e, w = 1.5) {
  const [px, py] = sc.tilSkjerm(K.x[p], K.y[p]);
  ctx.beginPath(); ctx.arc(px, py, radius(p, sc) + e, 0, 6.2832);
  ctx.strokeStyle = "#000"; ctx.lineWidth = w + 2; ctx.stroke();
  ctx.strokeStyle = "#fff"; ctx.lineWidth = w; ctx.stroke();
}
function teiknOverlay(ctx, sc) {
  if (!K) return;
  sc.setSkjerm(ctx);
  for (const key of S.f.kanon) { const p = K.pos.get(T.nodeAv(key)); if (p != null) ring(ctx, sc, p, 2, 2); }
  for (const p of merkPos) ring(ctx, sc, p, 3);
  for (const p of rangMerk) ring(ctx, sc, p, 4, 2.5);
  if (typeof sc.hoverId === "number") ring(ctx, sc, sc.hoverId, 2);
  if (typeof sc.fokusId === "number") ring(ctx, sc, sc.fokusId, 4);
  const kand = [], hind = [];
  const font = "12px Literata, Georgia, serif";
  const rang = K.storst.filter((p) => sc.synleg(K.x[p], K.y[p]));
  rang.forEach((p, j) => { const [px, py] = sc.tilSkjerm(K.x[p], K.y[p]); hind.push({ id: p, x: px, y: py, r: radius(p, sc), rang: j }); });
  rang.slice(0, 60).forEach((p, j) => {
    const [px, py] = sc.tilSkjerm(K.x[p], K.y[p]);
    kand.push({ id: p, x: px, y: py, r: radius(p, sc), tekst: T.merkelapp(K.noder[p]), font, h: 15, rang: j, farge: lysNode(p) ? "#f2f2f2" : "#9a9a9a" });
  });
  etikettar = plasserEtikettar(kand, { w: sc.w, h: sc.h, hindringar: hind, blokk: sc.dekkaNo(), forrige: forrigePlass, maks: Math.min(60, Math.round(30 * Math.max(1, sc.k))) });
  forrigePlass = new Map(etikettar.map((q) => [q.id, q.pos]));
  teiknEtikettar(ctx, etikettar);
}
function finn(px, py, type) {
  if (!K) return null;
  const sc = scene.sc;
  const [x, y] = sc.tilVerd(px, py);
  const touch = type !== "mouse";
  const kand = A.innanfor(K.qt, x, y, (K.rMaks(sc) + 24) / sc.K, (p) => K.x[p], (p) => K.y[p]);
  const treff = [];
  for (const p of kand) {
    const d = Math.hypot(K.x[p] - x, K.y[p] - y) * sc.K, r = radius(p, sc);
    if (d <= (touch ? Math.max(r, 22) : Math.max(r, 6))) treff.push({ p, d, r, inne: d <= r, lys: lysNode(p) });
  }
  if (!treff.length) return null;
  treff.sort((a, b) => (b.lys - a.lys) || (b.inne - a.inne) || (a.inne && b.inne ? a.r - b.r : a.d - b.d));
  return { id: treff[0].p, fleire: treff.length - 1 };
}
function nodeTittel(v) { return v < D.n ? D.kol.tittel[v] : D.sitd.kjelder.tittel[v - D.n]; }
function nodeHtml(p, fleire) {
  const v = K.noder[p];
  const saman = K.naboar[p].slice(0, 3).map(([b]) => esc(T.merkelapp(K.noder[b]))).join(", ");
  return `<div class="tt-tittel">${esc(T.merkelapp(v))}</div><div class="tt-meta">${esc(kutt(nodeTittel(v), 160))}</div>
    <div class="tt-meta">Sitert av ${fmt(D.nSitert[v])} verk i korpuset (${fmt(sNode[p])} i utvalet)</div>
    ${saman ? `<div class="tt-meta">Mest sitert saman med: ${saman}</div>` : ""}
    <div class="tt-meta"><span class="prikk" style="background:${gruppeFarge(K.gr[p])}"></span>Gruppe: ${esc(K.grupper[K.gr[p]] ? K.grupper[K.gr[p]].namn : "")}</div>
    ${fleire ? `<div class="tt-fot">+${fmt(fleire)} til her</div>` : ""}`;
}
const tips = (h) => nodeHtml(h.id, h.fleire) + `<div class="tt-fot">Klikk: vel verka som siterer dette · Skift-klikk: legg til</div>`;
function velKanon(p, leggTil) { T.veksle("kanon", T.nodeKey(K.noder[p]), { erstatt: !leggTil }); }
const klikk = (h, ev) => velKanon(h.id, ev.shiftKey || ev.ctrlKey || ev.metaKey);
function kortFor(h) {
  return { html: nodeHtml(h.id, h.fleire), knappar: [
    { tekst: "Vel", primar: true, gjer: () => velKanon(h.id, false) },
    { tekst: "Legg til", gjer: () => velKanon(h.id, true) },
    { tekst: "Opne nabolag", gjer: () => T.endre((s) => { s.sit.del = "nabolag"; s.sit.ego = T.nodeKey(K.noder[h.id]); }) },
  ] };
}
function teiknSamanLinje() {
  const lok = K.lokal;
  const min2 = K.medRef >= 12;
  const t = lok
    ? `Det utvalet siterer mest: ${K.N} verk, kvart sitert av minst ${min2 ? 2 : 1} verk i utvalet. Linje = sitert saman av minst ${min2 ? 2 : 1} verk i utvalet. ${fmt(K.medRef)} av ${fmt(T.valt)} verk i utvalet har referanseliste.`
    : `Dei ${K.N} mest siterte verka i heile korpuset${T.harFilter() && K.medRef ? "; det utvalet siterer er lyst" : ""}. Linje = sitert saman av minst 2 verk. ${fmt(K.medRef)} av ${fmt(T.valt)} verk i utvalet har referanseliste.`;
  ramme.linje.textContent = t;
  scene.settLabel(t);
  const brukt = new Set(K.gr);
  settInnhald(ramme.teikn, `<span class="teikn-merk">${felles()}</span><span class="teikn-merk">Grupper av verk som ofte blir siterte saman i heile korpuset (ikkje tema):</span>` +
    K.grupper.map((g, j) => (lok && !brukt.has(j) ? "" : `<span class="teikn-post"><span class="prikk" style="background:${gruppeFarge(j)}"></span>${esc(g.namn)} <span class="tal">${fmt(g.n)}</span></span>`)).join("") +
    (lok && brukt.has(99) ? `<span class="teikn-post"><span class="prikk" style="background:${gruppeFarge(99)}"></span>Ikkje i korpuskartet</span>` : "") +
    `<span class="teikn-merk">Storleik: ${lok ? "verk i utvalet som siterer" : "verk i korpuset som siterer"}.</span>`);
  if (T.harFilter() && T.valt > 0 && K.medRef === 0) {
    // a strict word search can leave works without reference lists: offer the wider set here too
    const si = T.sokInfo;
    const vid = S.f.q && !S.f.qv && si && si.tokens && si.tokens.length > 1 && si.minst1 > si.streng;
    A.hjelp.visMelding(ramme, {
      tekst: "Ingen av verka i utvalet har referanseliste i dataa (arkivverk har ingen).",
      knapp: vid ? { tekst: `Vis ${fmt(si.minst1)} med minst eitt av orda`, gjer: () => T.endre((s) => { s.f.qv = true; }) } : null,
    });
  } else A.hjelp.visMelding(ramme, null);
}
// How often each node is cited, decade by decade, over the whole corpus: the share of all
// citing works (with reference lists) from the 2000s, 2010s and 2020s that cite it. Used where
// a selection is too small to rank by decade on its own.
let profil = null;
function tiarProfil() {
  if (profil) return profil;
  const NM = D.n + D.m, c = new Int32Array(NM * 3), nT = [0, 0, 0];
  for (let i = 0; i < D.n; i++) {
    if (D.lag[i] || D.refOff[i] === D.refOff[i + 1]) continue;
    const a = D.ar[i], d = a >= 2020 ? 2 : a >= 2010 ? 1 : a >= 2000 ? 0 : -1;
    if (d < 0) continue;
    nT[d]++;
    for (let r = D.refOff[i]; r < D.refOff[i + 1]; r++) c[D.refTil[r] * 3 + d]++;
  }
  profil = { c, nT };
  return profil;
}
const TIAR_NAMN = ["2000-åra", "2010-åra", "2020-åra"];
function profilDel(v) { const p = tiarProfil(); return [0, 1, 2].map((d) => (p.nT[d] ? (100 * p.c[v * 3 + d]) / p.nT[d] : 0)); }
function profilTekst(v) { const d = profilDel(v); return TIAR_NAMN.map((t, j) => `${t} ${pst(d[j], 1)} %`).join(", "); }
function miniStolpar(v, h = 14) {
  const d = profilDel(v), mx = Math.max(...d, 0.001);
  return `<svg class="ministolpar" width="26" height="${h}" aria-hidden="true">${d.map((x, j) => { const bh = Math.max(1, Math.round((h - 1) * x / mx)); return `<rect x="${j * 9}" y="${h - bh}" width="7" height="${bh}" fill="${j === 2 ? "#e8e8e8" : "#8a8a8a"}"/>`; }).join("")}</svg>`;
}

// ranked list (amendment 13)
function teiknRang() {
  const NM = D.n + D.m;
  const topp = [];
  for (let v = 0; v < NM; v++) {
    const c = sAlle[v];
    if (!c || utanTittel(v)) continue;
    if (topp.length < 20 || c > topp[topp.length - 1][1] || (c === topp[topp.length - 1][1] && v < topp[topp.length - 1][0])) {
      topp.push([v, c]);
      topp.sort((a, b) => b[1] - a[1] || a[0] - b[0]);
      if (topp.length > 20) topp.pop();
    }
  }
  const mx = topp.length ? topp[0][1] : 1;
  const lukka = el.rang.classList.contains("lukka");
  A.hjelp.bevarFokus(el.rang, () => {
    const kv = S.f.kanon.size === 1 ? T.nodeAv([...S.f.kanon][0]) : -1;
    el.rang.innerHTML = `<div class="sidepanel-topp"><span>Mest sitert av utvalet</span><button type="button" class="knapp liten" data-rang aria-expanded="${!lukka}">${lukka ? "Vis" : "Gøym"}</button></div>
    ${kv >= 0 ? `<p class="rang-valt">Utvalet: verk som siterer <b>${esc(T.merkelapp(kv))}</b>. <button type="button" class="lenkeknapp" data-nabolag="${kv}">Kven siterer det, per tiår og land</button></p>` : ""}
    ${topp.length ? `<p class="rang-nokkel" aria-hidden="true"><svg width="26" height="8"><rect x="0" y="2" width="7" height="6" fill="#8a8a8a"/><rect x="9" y="2" width="7" height="6" fill="#8a8a8a"/><rect x="18" y="2" width="7" height="6" fill="#e8e8e8"/></svg> 2000-, 2010-, 2020-åra · tal i utvalet</p>
    <ol>${topp.map(([v, c]) => { const iKart = K.pos.has(v); return `<li class="rangrad"><button type="button" class="rang-namn" data-v="${v}" title="${esc(nodeTittel(v))}${iKart ? "" : ` (ikkje mellom dei ${K.N} i kartet)`}" aria-label="${esc(T.merkelapp(v))}, ${esc(nodeTittel(v))}: sitert av ${fmt(c)} verk i utvalet. I heile korpuset: ${profilTekst(v)} av dei siterande verka.${iKart ? "" : " Ikkje i kartet."}">${esc(T.merkelapp(v))}${iKart ? "" : ` <span class="ikkje-kart">ikkje i kartet</span>`}</button><span class="rang-tal" title="Del av alle siterande verk i korpuset: ${profilTekst(v)}">${miniStolpar(v)} ${fmt(c)}</span><button type="button" class="knapp liten rang-nabo" data-nabolag="${v}" aria-label="Opne nabolaget til ${esc(T.merkelapp(v))}: kven siterer det, per tiår og land" title="Nabolag: kven siterer det, per tiår og land">↗</button><span class="rang-bar"><span style="width:${Math.round((100 * c) / mx)}%"></span></span></li>`; }).join("")}</ol>
      <p class="sidepanel-merk">Tal: verk i utvalet som siterer. Små stolpar: del av alle siterande verk i korpuset i 2000-, 2010- og 2020-åra (lys = 2020-åra). Peik på eit namn for å finne det i kartet.</p>` : `<p class="dim" style="padding:0 10px">Ingen verk i utvalet har referanseliste.</p>`}`;
  });
}
// hovering (or focusing) a row of the ranked list rings that node in the map, or the row says
// it is not among the nodes of the map
let rangMerk = new Set();
function rangHover(e) {
  const b = e.target.closest && e.target.closest("button[data-v]");
  const v = b ? +b.dataset.v : null;
  const p = v != null ? K.pos.get(v) : null;
  const ny = new Set(p != null ? [p] : []);
  if ([...ny].join() !== [...rangMerk].join()) { rangMerk = ny; scene.teiknOverlay(); }
  if (e.type === "focusin" && p != null && !scene.sc.synleg(K.x[p], K.y[p], -20)) scene.panTilOmUte(K.x[p], K.y[p]);
}

// ---------- 2. neighbourhood ----------
// Items with a blank title (or the text "null" from the source) carry no information a reader
// can use; they stay in the counts but are not listed.
function utanTittel(v) { const t = String(nodeTittel(v) || "").trim(); return !t || t.toLowerCase() === "null"; }
function opneNabolag(v) { utvidaKol = new Set(); T.endre((s) => { s.sit.del = "nabolag"; s.sit.ego = T.nodeKey(v); }); }
// Who cites a work, by decade and by author country of the citing works (whole corpus).
function sitertAvProfil(v, sitertAv) {
  const p = tiarProfil(), d = profilDel(v);
  const perTiar = [0, 0, 0];
  const land = new Map();
  for (const i of sitertAv) {
    const a = D.ar[i], t = a >= 2020 ? 2 : a >= 2010 ? 1 : a >= 2000 ? 0 : -1;
    if (t >= 0) perTiar[t]++;
    for (const j of D.kol.fland[i]) land.set(j, (land.get(j) || 0) + 1);
  }
  const lt = [...land.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, 5);
  const mx = Math.max(...d, 0.001);
  const stolpar = TIAR_NAMN.map((t, j) => `<div class="profil-rad"><span>${t}${j === 2 ? "*" : ""}</span><span class="profil-bar"><span style="width:${Math.round((100 * d[j]) / mx)}%"></span></span><span>${fmt(perTiar[j])} av ${fmt(p.nT[j])} (${pst(d[j], 1)} %)</span></div>`).join("");
  return `<div class="ego-profil"><p class="ego-merk">Sitert av, per tiår (verk med referanseliste)</p>${stolpar}
    <p class="ego-merk">* 2020-åra er ikkje ferdige.${d[2] < d[0] ? " Mindre sitert no enn i 2000-åra." : d[2] > d[0] ? " Meir sitert no enn i 2000-åra." : ""}${sitertAv.length > perTiar[0] + perTiar[1] + perTiar[2] ? ` ${fmt(sitertAv.length - perTiar[0] - perTiar[1] - perTiar[2])} av dei ${fmt(sitertAv.length)} siterande verka er frå før 2000 og står ikkje i stolpane.` : ""} Arkivverk har inga referanseliste og kan ikkje telje som siterande.</p>
    ${lt.length ? `<p class="ego-merk">Forfattarland til dei som siterer: ${lt.map(([j, c]) => `${esc(T.landNamn(D.verk.land_alle[j].k))} ${fmt(c)}`).join(", ")}</p>` : ""}</div>`;
}
function etterAr(v) { const a = T.malAr(v); return a == null ? 9999 : a; }
function plukk(liste) {
  // at most 40 by n_sitert desc, then ordered by year (amendment 16)
  const best = liste.filter((v) => !utanTittel(v)).sort((a, b) => D.nSitert[b] - D.nSitert[a] || a - b);
  return { vist: best.slice(0, 40).sort((a, b) => etterAr(a) - etterAr(b) || a - b), resten: best.slice(40).sort((a, b) => etterAr(a) - etterAr(b) || a - b) };
}
function itemHtml(v, kol) {
  const iKorpus = v < D.n;
  const ute = iKorpus && T.harFilter() && !T.utval[v];
  const farge = iKorpus ? PALETTE_TEMA[D.tema[v]] : "#9a9a9a";
  return `<button type="button" class="ego-item${ute ? " ute" : ""}" data-v="${v}" ${iKorpus ? `data-ego-i="${v}"` : ""} data-kol="${kol}">
    <span class="prikk" style="background:${farge}"></span><span class="ego-tekst"><b>${esc(T.merkelapp(v))}</b>: ${esc(nodeTittel(v))}</span></button>`;
}
function teiknNabolag() {
  const egoKey = S.sit.ego;
  el.svg.innerHTML = "";
  if (!egoKey || T.nodeAv(egoKey) < 0) {
    const topp = [];
    for (let i = 0; i < D.n; i++) if (T.utval[i] && D.sit[i] >= 0) topp.push(i);
    topp.sort((a, b) => D.sit[b] - D.sit[a] || a - b);
    el.svg.innerHTML = `<div class="ego-tom"><p>Vel eit verk i lista eller i kartet for å sjå nabolaget.</p>${topp.slice(0, 5).map((i) => `<button type="button" class="knapp" data-nyego="${esc(D.kol.id[i])}">${esc(kutt(D.kol.tittel[i], 60))} (${D.ar[i]})</button>`).join("")}</div>`;
    ramme.linje.textContent = `Nabolaget til eitt verk: kva det siterer, kva som siterer det, og kva som liknar. ${fmt(T.valt)} verk i utvalet.`;
    settInnhald(ramme.teikn, `<span class="teikn-merk">${felles()}</span>`);
    return;
  }
  const v = T.nodeAv(egoKey);
  const iKorpus = v < D.n;
  const siterer = iKorpus ? Array.from(D.refTil.subarray(D.refOff[v], D.refOff[v + 1])) : [];
  const sitertAv = Array.from(citers.til.subarray(citers.off[v], citers.off[v + 1]));
  const liknar = iKorpus && T.harFil("naboar.bin") ? Array.from(D.nabo.subarray(v * 10, v * 10 + 10)) : [];
  // load the neighbours once; a failure is said in the column, not retried in a loop
  if (iKorpus && !T.harFil("naboar.bin") && naboStatus !== "feil" && naboStatus !== "lastar") {
    naboStatus = "lastar";
    T.sikre("naboar.bin").then((r) => { naboStatus = r.ok ? "ok" : "feil"; if (S.sit.del === "nabolag" && S.vis === "siteringar") teiknNabolag(); });
  }
  const kol = (namn, l, key) => {
    const { vist, resten } = key === "liknar" ? { vist: l, resten: [] } : plukk(l);
    const alle = utvidaKol.has(key) ? vist.concat(resten).sort((a, b) => etterAr(a) - etterAr(b) || a - b) : vist;
    return `<section class="ego-kol" data-kol="${key}"><h3>${namn} (${fmt(l.length)})</h3>
      <div class="ego-liste">${alle.map((x) => itemHtml(x, key)).join("") || `<p class="dim">Ingen.</p>`}</div>
      ${resten.length && !utvidaKol.has(key) ? `<button type="button" class="knapp liten" data-utvid="${key}">+ ${fmt(resten.length)} til</button>` : ""}</section>`;
  };
  const forf = iKorpus && D.kol.forf[v].length ? D.verk.forfattarar[D.kol.forf[v][0]].namn : "";
  const kanal = iKorpus ? (D.kanal[v] >= 0 ? D.verk.kanalar[D.kanal[v]].namn : "") : D.sitd.kjelder.kanalnamn[v - D.n];
  el.svg.innerHTML = `<div class="ego">
    <svg class="ego-boge" aria-hidden="true"></svg>
    ${kol("Siterer", siterer, "siterer")}
    <div class="ego-midt"><div class="ego-kort" id="egokort"><p class="ego-merk">${esc(T.merkelapp(v))}</p><h3>${esc(nodeTittel(v))}</h3>
      <p class="dim">${esc(forf)}${forf ? " · " : ""}${T.malAr(v) || ""}${kanal ? " · " + esc(kutt(kanal, 50)) : ""}</p>
      ${iKorpus ? `<button type="button" class="knapp liten" data-opneverk="${v}">Opne verket</button>` : ""}
      <button type="button" class="knapp liten" data-velkanon="${v}">Vel verka som siterer det (${fmt(sitertAv.length)})</button>
      ${sitertAv.length ? sitertAvProfil(v, sitertAv) : ""}</div></div>
    ${kol("Sitert av", sitertAv, "sitertav")}
    ${iKorpus ? (naboStatus === "feil" && !T.harFil("naboar.bin") ? `<section class="ego-kol" data-kol="liknar"><h3>Liknar</h3><p class="dim">Liknande verk kunne ikkje lastast. <button type="button" class="knapp liten" data-provnabo>Prøv igjen</button></p></section>` : kol("Liknar", liknar, "liknar")) : ""}
  </div>`;
  const r = D.sitd.ref_alle[v];
  ramme.linje.textContent = iKorpus && D.lag[v]
    ? "Arkivverk har inga referanseliste i dataa. Viser berre liknande verk."
    : `${T.merkelapp(v)}: siterer ${fmt(siterer.length)} verk med kjende metadata${iKorpus ? ` (av ${fmt(Math.max(r, 0))} referansar)` : ""}, sitert av ${fmt(sitertAv.length)} verk i korpuset${iKorpus ? `, liknar ${fmt(liknar.length)} verk` : ""}.${T.harFilter() ? ` Bleike: utanfor utvalet (${fmt(T.valt)} av ${fmt(D.n)} verk).` : ` Utvalet: alle ${fmt(D.n)} verk.`}`;
  settInnhald(ramme.teikn, `<span class="teikn-merk">${felles()}</span><span class="teikn-post"><span class="prikk" style="background:#9a9a9a"></span>utanfor korpuset</span><span class="teikn-merk">Farge: tema. Kolonnane viser dei 40 mest siterte, ordna etter år. Klikk eit verk for å gjere det til midten.</span>`);
  requestAnimationFrame(teiknBogar);
}
function teiknBogar() {
  const svg = el.svg.querySelector(".ego-boge");
  const kortEl = el.svg.querySelector("#egokort");
  if (!svg || !kortEl || smal()) { if (svg) svg.innerHTML = ""; return; }
  const box = svg.parentElement.getBoundingClientRect();
  svg.setAttribute("width", box.width); svg.setAttribute("height", svg.parentElement.scrollHeight);
  const k = kortEl.getBoundingClientRect();
  let html = "";
  for (const b of el.svg.querySelectorAll(".ego-item")) {
    const r = b.getBoundingClientRect();
    const kol = b.dataset.kol;
    const y1 = r.top + r.height / 2 - box.top;
    let x1, x2, y2 = k.top + k.height / 2 - box.top;
    if (kol === "siterer") { x1 = r.right - box.left; x2 = k.left - box.left; }
    else if (kol === "sitertav") { x1 = r.left - box.left; x2 = k.right - box.left; }
    else { x1 = r.left + 20 - box.left; x2 = k.left + k.width / 2 - box.left; y2 = k.bottom - box.top; }
    const mx = (x1 + x2) / 2;
    html += `<path d="M${x1},${y1}C${mx},${y1} ${mx},${y2} ${x2},${y2}" fill="none" stroke="${b.classList.contains("ute") ? "#333" : "#555"}" stroke-width="1"/>`;
  }
  svg.innerHTML = html;
}

// ---------- 3. flows ----------
async function teiknStraum() {
  el.svg.innerHTML = "";
  if (!window.d3.sankey) {
    // one attempt per "Prøv igjen": a failed load shows the message and stops
    if (sankeyStatus === "feil") { el.svg.innerHTML = `<div class="ego-tom"><p>Kunne ikkje laste d3-sankey.min.js.</p><button type="button" class="knapp" data-provsankey>Prøv igjen</button></div>`; return; }
    el.svg.innerHTML = `<p class="ego-tom">Lastar straumane …</p>`;
    if (sankeyStatus === "lastar") return;
    sankeyStatus = "lastar";
    const r = await A.data.lastSkript("sankey");
    sankeyStatus = r.ok ? "ok" : "feil";
    if (S.sit.del === "straum" && S.vis === "siteringar") teiknStraum();
    return;
  }
  const modus = S.sit.straum;
  const v = D.verk;
  const topp = (D.sitd.land_topp || []).map((j) => v.land_alle[j].k);
  const landGr = (l) => (l.length ? l.map((j) => (topp.includes(v.land_alle[j].k) ? v.land_alle[j].k : "andre")) : ["X"]);
  const lenker = new Map(); // "l|r" -> {v, verk:Set}
  let ref = 0, utanMal = 0, utan = 0;
  const verkMed = new Set();
  // target groups do not depend on the selection: cache them per mode
  if (!hogreCache[modus]) {
    const NM = D.n + D.m, arr = new Array(NM);
    for (let t = 0; t < NM; t++) {
      if (modus === "kanal") arr[t] = [v.kanalgrupper[T.malKgr(t)].k];
      else if (modus === "tiar") arr[t] = [T.tiarAv(T.malAr(t))];
      else arr[t] = landGr(T.malLand(t));
    }
    hogreCache[modus] = arr;
  }
  const hc = hogreCache[modus];
  for (let i = 0; i < D.n; i++) {
    if (!T.utval[i] || D.lag[i]) continue;
    utan += Math.max(0, D.sitd.ref_utan ? D.sitd.ref_utan[i] : 0);
    const a = D.refOff[i], b = D.refOff[i + 1];
    if (a === b) continue;
    verkMed.add(i);
    const venstre = modus === "land" ? landGr(D.kol.fland[i]) : [v.kanalgrupper[D.kgrAv[i]].k];
    for (let r = a; r < b; r++) {
      const hogre = hc[D.refTil[r]];
      ref++;
      if ((modus === "land" && hogre[0] === "X") || (modus === "kanal" && hogre[0] === "ukjend")) utanMal++;
      const w = 1 / (venstre.length * hogre.length);
      for (const l of venstre) for (const h of hogre) {
        const k = l + "|" + h;
        let o = lenker.get(k);
        if (!o) { o = { v: 0, w: 0, sist: -1 }; lenker.set(k, o); }
        o.v += w;
        if (o.sist !== i) { o.sist = i; o.w++; }
      }
    }
  }
  const namnFor = (k, side) => {
    if (modus !== "land" && (side === "v" || modus === "kanal")) { const g = D.kgrIdx.get(k); return g != null ? v.kanalgrupper[g].namn : k; }
    if (modus === "tiar") { const t = T.TIAR.find((x) => x.k === k); return t ? t.namn : k; }
    return k === "andre" ? "Andre land" : k === "X" ? "Ukjend" : T.landNamn(k);
  };
  const fargeFor = (k, side) => {
    if (modus !== "land" && (side === "v" || modus === "kanal")) return KGR_FARGE[k] || "#9fb3c8";
    if (modus === "tiar") { const j = T.TIAR.findIndex((x) => x.k === k); return k === "u" ? UKJEND : d3.interpolateGreys(0.35 + 0.1 * j).replace(/rgb/, "rgb"); }
    return k === "andre" ? "#9a9a9a" : k === "X" ? UKJEND : landFarge(k);
  };
  const W = Math.max(320, el.svg.clientWidth), H = Math.max(420, el.svg.clientHeight - 8);
  const linje = () => {
    let t = `Referansar frå dei ${fmt(T.valt)} verka i utvalet: ${fmt(ref)} frå ${fmt(verkMed.size)} verk har kjent mål; ${fmt(utan)} peikar på verk utan metadata og er ikkje med. Sjølvsiteringar er tekne ut, og fleire referansar frå eitt verk til same siterte verk tel éin gong.`;
    if (modus === "land") t += ` ${pst((100 * utanMal) / Math.max(1, ref))} % av måla manglar land.`;
    if (modus === "kanal") t += ` ${pst((100 * utanMal) / Math.max(1, ref))} % av måla manglar kanal.`;
    if (S.f.siterer) t += ` Straumane viser alle referansane frå dei valde verka, ikkje berre dei til ${T.siterarNamn(S.f.siterer)}.`;
    ramme.linje.textContent = `${t}`;
  };
  settInnhald(ramme.teikn, [["kanal", "Kanal til kanal"], ["land", "Land til land"], ["tiar", "Kanal til tiår"]].map(([k, n]) => `<button type="button" class="teikn-post" data-straum="${k}" aria-pressed="${modus === k}">${n}</button>`).join("") + `<span class="teikn-merk">Venstre: verka i utvalet. Høgre: det dei siterer. ${felles()}</span>`);
  linje();
  if (!lenker.size) { el.svg.innerHTML = `<p class="ego-tom">${T.valt ? "Ingen av verka i utvalet har referanseliste i dataa." : ""}</p>`; return; }
  // limit to 8 nodes per side below 600 px
  let liste = [...lenker.entries()].map(([k, o]) => { const [l, h] = k.split("|"); return { l, h, v: o.v, w: o.w }; });
  if (veldigSmal()) {
    for (const side of ["l", "h"]) {
      const sum = new Map();
      for (const x of liste) sum.set(x[side], (sum.get(x[side]) || 0) + x.v);
      const behald = new Set([...sum.entries()].sort((a, b) => b[1] - a[1]).slice(0, 7).map((e) => e[0]));
      if (sum.size > 8) for (const x of liste) if (!behald.has(x[side])) x[side] = "andre";
    }
  }
  const nodar = new Map();
  for (const x of liste) { nodar.set(`v:${x.l}`, { id: `v:${x.l}`, k: x.l, side: "v" }); nodar.set(`h:${x.h}`, { id: `h:${x.h}`, k: x.h, side: "h" }); }
  const slatt = new Map();
  for (const x of liste) { const k = `v:${x.l}|h:${x.h}`; const o = slatt.get(k) || { source: `v:${x.l}`, target: `h:${x.h}`, value: 0, w: 0 }; o.value += x.v; o.w = Math.max(o.w, x.w); slatt.set(k, o); }
  const lab = veldigSmal() ? 0 : 130;
  const sk = d3.sankey().nodeId((d) => d.id).nodeWidth(14).nodePadding(10).nodeAlign(d3.sankeyJustify).iterations(32)
    .nodeSort((a, b) => b.value - a.value).extent([[lab + 4, 8], [W - lab - 4, H - 8]]);
  const g = sk({ nodes: [...nodar.values()].map((d) => ({ ...d })), links: [...slatt.values()].map((d) => ({ ...d })) });
  const svg = d3.select(el.svg).append("svg").attr("width", W).attr("height", H).attr("class", "straum");
  const lenkeSel = svg.append("g").attr("fill", "none").selectAll("path").data(g.links).join("path")
    .attr("d", d3.sankeyLinkHorizontal()).attr("stroke", (d) => fargeFor(d.source.k, "v")).attr("stroke-opacity", 0.45)
    .attr("stroke-width", (d) => Math.max(1, d.width)).style("cursor", "pointer")
    .attr("tabindex", 0).attr("role", "button").attr("class", "straum-lenke")
    .attr("aria-label", (d) => `${namnFor(d.source.k, "v")} til ${namnFor(d.target.k, "h")}: ${fmt(Math.round(d.value))} referansar. Enter vel begge.`);
  const nodeSel = svg.append("g").selectAll("rect").data(g.nodes).join("rect")
    .attr("x", (d) => d.x0).attr("y", (d) => d.y0).attr("width", (d) => d.x1 - d.x0).attr("height", (d) => Math.max(1, d.y1 - d.y0))
    .attr("fill", (d) => fargeFor(d.k, d.side)).style("cursor", "pointer")
    .attr("tabindex", 0).attr("role", "button").attr("class", "straum-node")
    .attr("aria-label", (d) => `${d.side === "v" ? "Verk i utvalet" : "Siterte verk"}: ${namnFor(d.k, d.side)}, ${fmt(Math.round(d.value))} referansar. Enter vel.`);
  // keyboard: Enter or space on a node or a link does what a click does; focus shows the same highlight
  nodeSel.on("keydown", (ev, d) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); if (d.side === "v") velVenstre(d.k); else velHogre(d.k); } })
    .on("focus", (ev, d) => lenkeSel.attr("stroke-opacity", (q) => (q.source === d || q.target === d ? 0.8 : 0.15)))
    .on("blur", () => lenkeSel.attr("stroke-opacity", 0.45));
  lenkeSel.on("keydown", (ev, d) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); velStraum(d.source.k, d.target.k); } })
    .on("focus", (ev, d) => lenkeSel.attr("stroke-opacity", (q) => (q === d ? 0.8 : 0.15)))
    .on("blur", () => lenkeSel.attr("stroke-opacity", 0.45));
  svg.append("g").selectAll("text").data(g.nodes).join("text").attr("class", "etikett")
    .attr("x", (d) => (d.side === "v" ? (lab ? d.x0 - 6 : d.x1 + 6) : (lab ? d.x1 + 6 : d.x0 - 6)))
    .attr("y", (d) => (d.y0 + d.y1) / 2 + 4)
    .attr("text-anchor", (d) => ((d.side === "v") === !!lab ? "end" : "start"))
    .text((d) => `${namnFor(d.k, d.side)} ${fmt(Math.round(d.value))}`).attr("pointer-events", "none");
  const verkTal = (d) => { let s = 0; for (const x of liste) if (`v:${x.l}` === d.source.id && `h:${x.h}` === d.target.id) s = Math.max(s, x.w); return s; };
  let framheva = null; // restyle the links only when the hovered mark changes
  lenkeSel.on("pointermove", (ev, d) => {
    if (framheva !== d) { framheva = d; lenkeSel.attr("stroke-opacity", (q) => (q === d ? 0.8 : 0.15)); }
    if (ev.pointerType === "mouse") tooltip.vis(`<div class="tt-tittel">${esc(namnFor(d.source.k, "v"))} til ${esc(namnFor(d.target.k, "h"))}</div><div class="tt-meta">${fmt(Math.round(d.value))} referansar frå ${fmt(verkTal(d))} verk</div><div class="tt-fot">Klikk: vel begge</div>`, ev.clientX, ev.clientY);
  }).on("pointerleave", () => { framheva = null; lenkeSel.attr("stroke-opacity", 0.45); tooltip.skjul(); })
    .on("click", (ev, d) => straumHandling(ev, `lenke:${d.source.k}|${d.target.k}`, () => velStraum(d.source.k, d.target.k), `<div class="tt-tittel">${esc(namnFor(d.source.k, "v"))} til ${esc(namnFor(d.target.k, "h"))}</div><div class="tt-meta">${fmt(Math.round(d.value))} referansar frå ${fmt(verkTal(d))} verk</div>`));
  nodeSel.on("pointermove", (ev, d) => {
    if (framheva !== d) { framheva = d; lenkeSel.attr("stroke-opacity", (q) => (q.source === d || q.target === d ? 0.8 : 0.15)); }
    if (ev.pointerType === "mouse") tooltip.vis(`<div class="tt-tittel">${esc(namnFor(d.k, d.side))}</div><div class="tt-meta">${fmt(Math.round(d.value))} referansar</div><div class="tt-fot">Klikk: ${d.side === "v" ? "vel desse verka" : "vel verk som siterer hit"}</div>`, ev.clientX, ev.clientY);
  }).on("pointerleave", () => { framheva = null; lenkeSel.attr("stroke-opacity", 0.45); tooltip.skjul(); })
    .on("click", (ev, d) => straumHandling(ev, `node:${d.id}`, () => (d.side === "v" ? velVenstre(d.k) : velHogre(d.k)), `<div class="tt-tittel">${esc(namnFor(d.k, d.side))}</div><div class="tt-meta">${fmt(Math.round(d.value))} referansar</div>`));
}
function straumHandling(ev, id, gjer, html) {
  if (ev.pointerType && ev.pointerType !== "mouse") {
    if (kort.ope && kort.id === id) { kort.lukk(); gjer(); return; }
    kort.opne({ id, html, knappar: [{ tekst: "Vel", primar: true, gjer }], x: ev.clientX, y: ev.clientY });
    return;
  }
  gjer();
}
function velVenstre(k) {
  if (k === "andre") return;
  if (S.sit.straum === "land") { if (k !== "X") T.veksle("fland", k, { erstatt: true }); }
  else T.veksle("kgr", k, { erstatt: true });
}
const hogreModus = () => (S.sit.straum === "kanal" ? "kgr" : S.sit.straum);
function velHogre(k) { T.endre((s) => { s.f.siterer = { modus: hogreModus(), nokkel: k }; }); }
function velStraum(l, h) {
  T.endre((s) => {
    if (l !== "andre") {
      if (s.sit.straum === "land") { if (l !== "X") { s.f.fland.clear(); s.f.fland.add(l); } }
      else { s.f.kgr.clear(); s.f.kgr.add(l); }
    }
    s.f.siterer = { modus: hogreModus(), nokkel: h };
  });
}

// ---------- 4. over time (amendment 14) ----------
function teiknOverTid() {
  el.svg.innerHTML = "";
  const tiar = [1980, 1990, 2000, 2010, 2020];
  const verkPerTiar = new Map(), tel = new Map();
  for (let i = 0; i < D.n; i++) {
    if (!T.utval[i] || D.lag[i] || D.refOff[i] === D.refOff[i + 1]) continue;
    const t = Math.max(1980, Math.min(2020, Math.floor(D.ar[i] / 10) * 10));
    verkPerTiar.set(t, (verkPerTiar.get(t) || 0) + 1);
    let m = tel.get(t);
    if (!m) { m = new Map(); tel.set(t, m); }
    for (let r = D.refOff[i]; r < D.refOff[i + 1]; r++) m.set(D.refTil[r], (m.get(D.refTil[r]) || 0) + 1);
  }
  const kolonnar = tiar.filter((t) => t >= 2000 || (verkPerTiar.get(t) || 0) >= 20);
  const rangar = kolonnar.map((t) => {
    const n = verkPerTiar.get(t) || 0;
    if (n < 20) return { t, n, liste: null };
    const l = [...(tel.get(t) || new Map()).entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, 8);
    return { t, n, liste: l };
  });
  const W = Math.max(320, el.svg.clientWidth), rad = 40, topp = 54;
  const H = topp + rad * 8 + 20;
  const kw = (W - 40) / kolonnar.length;
  const x = (j) => 20 + kw * j + 8;
  const boksB = Math.min(170, kw - 30);
  let html = `<svg width="${W}" height="${H}" class="bump">`;
  // lines between columns
  const posAv = rangar.map((r) => new Map((r.liste || []).map(([v], q) => [v, q])));
  for (let j = 0; j + 1 < rangar.length; j++) {
    for (const [v, q] of posAv[j]) {
      const q2 = posAv[j + 1].get(v);
      if (q2 == null) continue;
      const y1 = topp + q * rad + rad / 2 - 6, y2 = topp + q2 * rad + rad / 2 - 6;
      const x1 = x(j) + boksB, x2 = x(j + 1);
      html += `<path d="M${x1},${y1}C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}" fill="none" stroke="#8a8a8a" stroke-width="2" stroke-opacity="0.7"/>`;
    }
  }
  rangar.forEach((r, j) => {
    const ufull = r.t === 2020;
    html += `<text x="${x(j)}" y="18" class="bump-hovud">${r.t}-åra${ufull ? " (ufullstendig)" : ""}</text><text x="${x(j)}" y="34">${fmt(r.n)} verk med referanseliste</text>`;
    if (!r.liste) { html += `<text x="${x(j)}" y="${topp + 20}" class="dim">For få verk</text>`; return; }
    r.liste.forEach(([v, c], q) => {
      const y = topp + q * rad;
      const pst_ = (100 * c) / r.n;
      html += `<g class="bump-node" data-v="${v}" data-t="${r.t}" tabindex="0" role="button" aria-label="${esc(T.merkelapp(v))}, ${c} av ${r.n} verk i ${r.t}-åra">
        <rect x="${x(j)}" y="${y}" width="${boksB}" height="${rad - 12}" rx="3" fill="#141414" stroke="${S.f.kanon.has(T.nodeKey(v)) ? "#fff" : "#333"}"/>
        <rect x="${x(j)}" y="${y + rad - 15}" width="${Math.max(2, (boksB * pst_) / 40)}" height="3" fill="#bdbdbd"/>
        <text x="${x(j) + 6}" y="${y + 16}" class="bump-tekst">${q + 1}. ${esc(kutt(T.merkelapp(v), 18))}</text>
        <text x="${x(j) + boksB - 6}" y="${y + 16}" text-anchor="end">${pst(pst_)} %</text></g>`;
    });
  });
  html += `</svg>`;
  // a selection too small to rank per decade: show how its most cited works moved in the whole corpus
  if (rangar.every((r) => !r.liste)) {
    const topp = [];
    for (let v = 0; v < D.n + D.m; v++) if (sAlle[v]) topp.push([v, sAlle[v]]);
    topp.sort((a, b) => b[1] - a[1] || a[0] - b[0]);
    const p = tiarProfil();
    const rader = topp.slice(0, 8).map(([v, c]) => {
      const d = profilDel(v);
      const ned = d[2] < d[0];
      // number and % never part over two lines; the trend is an arrow and one short word
      const trend = ned ? ["↓", "lågare", "lågare i 2020-åra enn i 2000-åra"] : d[2] > d[0] ? ["↑", "høgare", "høgare i 2020-åra enn i 2000-åra"] : ["=", "likt", "likt i 2020-åra og 2000-åra"];
      return `<tr><th scope="row"><button type="button" class="lenkeknapp" data-v="${v}" title="${esc(nodeTittel(v))}">${esc(T.merkelapp(v))}</button> <span class="dim">${fmt(c)} i utvalet</span></th>${d.map((x) => `<td>${pst(x, 1)}&nbsp;%</td>`).join("")}<td class="trend" aria-label="${trend[2]}"><span aria-hidden="true">${trend[0]}&nbsp;${trend[1]}</span></td></tr>`;
    }).join("");
    const KORT = ["00-åra", "10-åra", "20-åra"];
    html = `<div class="tiar-tabell"><p class="melding-tittel">For få verk i utvalet til å rangere kvart tiår for seg (minst 20 med referanseliste).</p>
      <p class="dim">Dei mest siterte verka i utvalet, og kor stor del av alle siterande verk i heile korpuset som siterte dei i kvart tiår.</p>
      ${topp.length ? `<table><thead><tr><th scope="col">Verk</th>${TIAR_NAMN.map((t, j) => `<th scope="col"><span aria-hidden="true">${KORT[j]}${j === 2 ? "*" : ""}</span><span class="sr">${t}${j === 2 ? ", ufullstendig" : ""}</span></th>`).join("")}<th scope="col" class="trend"><span aria-hidden="true">No</span><span class="sr">2020-åra mot 2000-åra</span></th></tr></thead><tbody>${rader}</tbody></table>
      <p class="dim tiar-fot">Prosent: del av siterande verk i korpuset (${TIAR_NAMN.map((t, j) => `${t} ${fmt(p.nT[j])}`).join(", ")}). * 2020-åra er ikkje ferdige. «No»: 2020-åra mot 2000-åra.</p>` : `<p>Ingen verk i utvalet har referanseliste.</p>`}<p class="dim">Per tiår i utvalet: ${rangar.map((r) => `${r.t}-åra ${fmt(r.n)} verk med referanseliste`).join(", ")}.</p></div>`;
  }
  el.svg.innerHTML = html;
  ramme.linje.textContent = `Dei 8 mest siterte verka per tiår, rekna frå dei ${fmt(T.valt)} verka i utvalet etter tiåret dei kom ut. Prosent = del av desse verka som siterer.`;
  settInnhald(ramme.teikn, `<span class="teikn-merk">${felles()}</span><span class="teikn-merk">Linjer bind saman same verk. Tiår med under 20 verk med referanseliste får ingen rangering.</span>`);
  el.svg._rangar = { rangar, verkPerTiar, tel };
}
function bumpTips(v) {
  const info = el.svg._rangar;
  if (!info) return "";
  const rader = [...info.verkPerTiar.keys()].sort().map((t) => {
    const n = info.verkPerTiar.get(t), c = (info.tel.get(t) || new Map()).get(v) || 0;
    return `<div class="tt-meta">${t}-åra: ${fmt(c)} av ${fmt(n)} verk (${pst((100 * c) / Math.max(1, n))} %)</div>`;
  }).join("");
  return `<div class="tt-tittel">${esc(T.merkelapp(v))}</div><div class="tt-meta">${esc(kutt(nodeTittel(v), 140))}</div>${rader}<div class="tt-fot">Klikk: vel verka som siterer dette</div>`;
}

// ---------- svg-part clicks and hover ----------
function svgKlikk(e) {
  const t = e.target;
  const b = t.closest("button");
  if (b && b.dataset.provsankey != null) { sankeyStatus = "ingen"; teiknStraum(); return; }
  if (b && b.dataset.provnabo != null) { naboStatus = "ingen"; teiknNabolag(); return; }
  if (b && b.dataset.v != null && b.closest(".tiar-tabell")) { const v = +b.dataset.v; T.endre((s) => { s.sit.del = "nabolag"; s.sit.ego = T.nodeKey(v); }); return; }
  if (b && b.dataset.nyego) { T.endre((s) => { s.sit.ego = b.dataset.nyego; }); return; }
  if (b && b.dataset.utvid) { utvidaKol.add(b.dataset.utvid); teiknNabolag(); return; }
  if (b && b.dataset.opneverk) { A.opneVerk(+b.dataset.opneverk); return; }
  if (b && b.dataset.velkanon) { T.veksle("kanon", T.nodeKey(+b.dataset.velkanon), { erstatt: true }); return; }
  if (b && b.classList.contains("ego-item")) {
    const v = +b.dataset.v;
    if (v < D.n) { utvidaKol = new Set(); T.endre((s) => { s.sit.ego = D.kol.id[v]; }); return; }
    const j = v - D.n, doi = D.sitd.kjelder.doi[j];
    const html = `<div class="tt-tittel">${esc(T.merkelapp(v))}</div><div class="tt-meta">${esc(nodeTittel(v))}</div>${doi ? `<p><a href="https://doi.org/${esc(doi)}" target="_blank" rel="noopener">Opne DOI</a></p>` : ""}`;
    const r = b.getBoundingClientRect();
    kort.opne({ id: `kj${v}`, html, knappar: [{ tekst: "Vis verka som siterer dette", primar: true, gjer: () => T.veksle("kanon", T.nodeKey(v), { erstatt: true }) }, { tekst: "Gjer til midten", gjer: () => T.endre((s) => { s.sit.ego = T.nodeKey(v); }) }], x: r.right, y: r.top });
    return;
  }
  const g = t.closest(".bump-node");
  if (g) T.veksle("kanon", T.nodeKey(+g.dataset.v), { erstatt: !(e.shiftKey || e.ctrlKey || e.metaKey) });
}
let sistHov = null;
function hoverSvg(e) {
  if (e.pointerType !== "mouse") return;
  const it = e.target.closest(".ego-item");
  const mal = it || e.target.closest(".bump-node");
  // the text is built once per item; moving within it only moves the box
  if (mal && mal === sistHov && tooltip.synleg) { tooltip.flytt(e.clientX, e.clientY); return; }
  sistHov = mal;
  if (it) {
    const v = +it.dataset.v;
    const iK = v < D.n;
    const forf = iK ? D.kol.forf[v].map((f) => visNamn(D.verk.forfattarar[f].namn)).slice(0, 4).join(", ") : "";
    const kanal = iK ? (D.kanal[v] >= 0 ? D.verk.kanalar[D.kanal[v]].namn : "") : D.sitd.kjelder.kanalnamn[v - D.n];
    tooltip.vis(`<div class="tt-tittel">${esc(nodeTittel(v))}</div><div class="tt-meta">${esc(forf)} · ${T.malAr(v) || "ukjent år"}${kanal ? " · " + esc(kutt(kanal, 40)) : ""}</div>
      <div class="tt-meta">Sitert av ${fmt(D.nSitert[v])} verk i korpuset${iK && D.sit[v] >= 0 ? ` · ${fmt(D.sit[v])} siteringar i OpenAlex` : ""}</div><div class="tt-fot">${iK ? "Klikk: gjer til midten" : "Klikk: vis kortet"}</div>`, e.clientX, e.clientY);
    return;
  }
  const g = e.target.closest(".bump-node");
  if (g) { tooltip.vis(bumpTips(+g.dataset.v), e.clientX, e.clientY); return; }
  if (!e.target.closest("path,rect")) tooltip.skjul();
}
document.addEventListener("pointermove", (e) => { if (el.svg && !el.svg.hidden && el.svg.contains(e.target)) hoverSvg(e); });
document.addEventListener("keydown", (e) => {
  if ((e.key === "Enter" || e.key === " ") && e.target.closest && e.target.closest(".bump-node")) { e.preventDefault(); T.veksle("kanon", T.nodeKey(+e.target.closest(".bump-node").dataset.v), { erstatt: true }); }
});
void tween; void rorsle;
