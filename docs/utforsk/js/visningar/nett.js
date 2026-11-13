// Nett: who writes together. Institutions (or authors) as nodes, shared works as lines.
import { esc, fmt, kutt, landFarge, UKJEND, FADE, FADE_ALFA, plasserEtikettar, teiknEtikettar, tooltip, kort, segmentert, smal, LAND_FARGE } from "../hjelp.js?v=21";

let A, T, D, S, ramme, scene, modSeg;
let G = null;            // current graph
const grafar = {};       // modus -> prepared graph
let s = null;            // works in selection per node
let wValt = null;        // Map pairKey -> shared works in selection
let merkNoder = new Set();
let opneNoder = new Set(); // nodes of the open work (S.verk)
let etikettar = [], forrigePlass = new Map();
let panelOpe = !smal();
let status = {};

export default {
  id: "nett",
  filer: ["nett_inst.json"],
  skript: [],
  async init(el, api) {
    A = api; T = api.T; D = api.D; S = api.S; ramme = api.ramme;
    modSeg = segmentert(ramme.kontroll, {
      namn: "Nettet viser", verdi: S.nett.modus,
      val: [{ k: "inst", namn: "Institusjonar" }, { k: "forf", namn: "Forfattarar" }],
      ved: (v) => T.endre((st) => { st.nett.modus = v; }),
    });
    scene = api.lagScene(ramme.flate, {
      verd: [10000, 10000], skala: [0.25, 20], rolle: "nettverk",
      heim: () => (G ? G.heim : [0, 0, 10000, 10000]),
      teiknBase, teiknOverlay, finn, tips, klikk, kort: kortFor, tapHandling: (h) => vel(h, false), finnId,
      hoverEndra: () => scene.teikn(),
      vedZoom: (z) => T.settZoom("nett", z),
      fokusListe, fokusHandling: (id) => vel({ id }, false),
      feil: api.feil,
    });
    ramme.flate.insertAdjacentHTML("beforeend", `<div class="sidepanel" id="nett-partnar" hidden></div>`);
    ramme.flate.querySelector("#nett-partnar").addEventListener("click", partnarKlikk);
    ramme.teikn.addEventListener("click", () => {});
    scene.storleik();
  },
  async oppdater(st, e) {
    const modus = S.nett.modus;
    modSeg.set(modus);
    if (!grafar[modus]) {
      const fil = modus === "inst" ? "nett_inst.json" : "nett_forf.json";
      if (status[modus] === "lastar") return;
      status[modus] = "lastar";
      A.hjelp.visMelding(ramme, { tekst: "Lastar nettet …" });
      const r = await T.sikre(fil);
      status[modus] = r.ok ? "ok" : "feil";
      // the reader may have switched mode while the file was loading: that call drew already
      if (S.nett.modus !== modus || S.vis !== "nett") { if (r.ok) grafar[modus] = lagGraf(A.data.ferdig(fil), modus); return; }
      if (!r.ok) {
        A.hjelp.visMelding(ramme, { tittel: `Kunne ikkje laste ${fil}.`, knapp: { tekst: "Prøv igjen", gjer: () => { status[modus] = null; this.oppdater(S, { ...e, vis: true }); } } });
        return;
      }
      A.hjelp.visMelding(ramme, null);
      grafar[modus] = lagGraf(A.data.ferdig(fil), modus);
      e = { ...e, vis: true };
    }
    const nyGraf = G !== grafar[modus];
    G = grafar[modus];
    rekn();
    if (nyGraf) scene.storleik();
    if (nyGraf || e.popstate || e.vis) {
      const z = S.nett.z;
      if (nyGraf && !e.popstate && !e.vis) scene.settZ(null); else scene.settZ(z);
    }
    verkNoder();
    teiknLinje();
    teiknPartnar();
    if (T.harFilter() && T.valt > 0 && G.medNode === 0) A.hjelp.visMelding(ramme, { tekst: `Ingen av verka i utvalet har ${G.modus === "inst" ? "institusjon" : "forfattar med OpenAlex-id"} i dataa.` });
    else A.hjelp.visMelding(ramme, null);
    scene.teikn();
  },
  merk(i) {
    merkNoder = new Set();
    if (i != null && G) for (const p of G.verkNoder(i)) merkNoder.add(p);
    scene.teiknOverlay();
  },
  sentrer(i) { if (!G) return; const p = G.verkNoder(i)[0]; if (p != null) scene.sentrer(G.x[p], G.y[p], dekt()); },
  panTil(i) { if (!G) return; const p = G.verkNoder(i)[0]; if (p != null) scene.panTilOmUte(G.x[p], G.y[p]); },
  vis() { scene.storleik(); },
  skjul() { tooltip.skjul(); },
  fokusUt() { return scene.fokusUt(); },
  scene: () => scene,
  etikettar: () => etikettar,
};

function verkNoder() {
  opneNoder = new Set();
  const i = S.verk ? D.idx.get(S.verk) : null;
  if (i != null && G) for (const p of G.verkNoder(i)) opneNoder.add(p);
}

function dekt() {
  const ark = document.getElementById("listepanel").getBoundingClientRect();
  const r = ramme.flate.getBoundingClientRect();
  return Math.max(0, r.bottom - ark.top);
}

// ---------- graph ----------
function lagGraf(f, modus) {
  const no = f.noder, N = no.ref.length;
  const dict = modus === "inst" ? D.verk.institusjonar : D.verk.forfattarar;
  const pos = new Map(no.ref.map((r, p) => [r, p]));
  const kol = modus === "inst" ? D.kol.inst : D.kol.forf;
  const verkN = new Array(D.n);
  for (let i = 0; i < D.n; i++) {
    const l = [];
    for (const r of kol[i]) { const p = pos.get(r); if (p != null) l.push(p); }
    verkN[i] = l;
  }
  const nmax = Math.max(...no.n);
  const r0 = new Float32Array(N);
  for (let p = 0; p < N; p++) r0[p] = 3 + 17 * Math.sqrt(no.n[p] / nmax);
  const farge = no.land.map((j) => (j >= 0 ? landFarge(D.verk.land_alle[j].k) : UKJEND));
  const naboar = Array.from({ length: N }, () => []);
  for (const [a, b, w] of f.kantar) { naboar[a].push([b, w]); naboar[b].push([a, w]); }
  for (const l of naboar) l.sort((u, v) => v[1] - u[1] || no.n[v[0]] - no.n[u[0]] || u[0] - v[0]);
  const namn = (p) => (modus === "inst" ? dict[no.ref[p]].kort || dict[no.ref[p]].namn : dict[no.ref[p]].namn);
  const fulltNamn = (p) => dict[no.ref[p]].namn;
  const key = (p) => dict[no.ref[p]].k;
  const keyPos = new Map(no.ref.map((r, p) => [dict[r].k, p]));
  const qt = A.lagIndeks(N, (p) => no.x[p], (p) => no.y[p]);
  const storst = Array.from({ length: N }, (_, p) => p).sort((a, b) => no.n[b] - no.n[a] || a - b);
  // home view: 1 % to 99 % of the nodes on each axis, so the whole network is in the picture
  const kv = (arr) => { const s = Float64Array.from(arr).sort(); return [s[Math.floor(N * 0.01)], s[Math.ceil(N * 0.99) - 1]]; };
  const [hx0, hx1] = kv(no.x), [hy0, hy1] = kv(no.y);
  const heim = [hx0 - 150, hy0 - 150, hx1 + 150, hy1 + 150];
  return { heim, modus, N, x: no.x, y: no.y, n: no.n, land: no.land, kantar: f.kantar, tal: f.tal, r0, farge, naboar, namn, fulltNamn, key, keyPos, qt, storst, verkNoder: (i) => verkN[i], verkN, dim: modus === "inst" ? "inst" : "forf" };
}

function rekn() {
  const N = G.N, u = T.utval;
  s = new Int32Array(N);
  wValt = new Map();
  let medNode = 0;
  for (let i = 0; i < D.n; i++) {
    if (!u[i]) continue;
    const l = G.verkN[i];
    if (l.length) medNode++;
    for (let a = 0; a < l.length; a++) {
      s[l[a]]++;
      for (let b = a + 1; b < l.length; b++) {
        const p = Math.min(l[a], l[b]), q = Math.max(l[a], l[b]);
        const k = p * N + q;
        wValt.set(k, (wValt.get(k) || 0) + 1);
      }
    }
  }
  G.medNode = medNode;
  // works in the selection with any institution / OpenAlex author at all
  // (authors: at least one with an OpenAlex id, key starting with "A"; name-only keys do not count)
  let harLag = 0;
  const forf = D.verk.forfattarar;
  if (G.modus === "inst") { for (let i = 0; i < D.n; i++) if (u[i] && D.kol.inst[i].length) harLag++; }
  else for (let i = 0; i < D.n; i++) if (u[i] && D.kol.forf[i].some((f) => forf[f].k.charCodeAt(0) === 65)) harLag++;
  G.harLag = harLag;
  G.valdeNoder = new Set([...S.f[G.dim]].map((k) => G.keyPos.get(k)).filter((p) => p != null));
}

const lys = (p) => !T.harFilter() || s[p] > 0;
function radius(p, sc) { return G.r0[p] * sc.rf * Math.min(sc.k, 3) ** 0.5; }

// ---------- drawing ----------
// Edge buckets and node groups depend on the selection and the hovered node only;
// they are cached so pan and zoom replay them (one path per bucket).
let teiknCache = null;
function byggTeiknCache(hov) {
  const filt = T.harFilter(), N = G.N;
  const hovNabo = new Set();
  if (hov != null) { hovNabo.add(hov); for (const [b] of G.naboar[hov]) hovNabo.add(b); }
  const botter = new Map();
  const leggKant = (a, b, w, alfa, farge) => {
    const bw = Math.round((0.4 + 0.8 * Math.sqrt(w)) * 2) / 2;
    const ba = Math.round(alfa * 50) / 50;
    const k = `${bw}|${ba}|${farge}`;
    let l = botter.get(k);
    if (!l) { l = { bw, ba, farge, idx: [] }; botter.set(k, l); }
    l.idx.push(a, b);
  };
  for (const [a, b, w] of G.kantar) {
    let ww = w, alfa;
    if (filt) {
      ww = wValt.get(a * N + b) || 0;
      alfa = ww > 0 ? Math.min(0.08 + 0.05 * ww, 0.6) + 0.1 : 0.04;
      if (ww === 0) ww = 1;
    } else alfa = Math.min(0.08 + 0.05 * w, 0.6);
    if (hov != null) {
      if (a === hov || b === hov) { leggKant(a, b, ww, 0.9, "#ffffff"); continue; }
      alfa = Math.max(0.02, alfa * 0.25);
    }
    leggKant(a, b, ww, alfa, "#dcdcdc");
  }
  const kantar = [...botter.values()].sort((u, v) => u.ba - v.ba);
  for (const k of kantar) {
    const f = new Float32Array(k.idx.length * 2);
    for (let j = 0; j < k.idx.length; j += 2) { f[2 * j] = G.x[k.idx[j]]; f[2 * j + 1] = G.y[k.idx[j]]; f[2 * j + 2] = G.x[k.idx[j + 1]]; f[2 * j + 3] = G.y[k.idx[j + 1]]; }
    k.xy = f;
  }
  const grupper = new Map();
  for (let p = N - 1; p >= 0; p--) {
    const b = lys(p);
    const base = b ? 1 : FADE_ALFA;
    const a = hov != null && !hovNabo.has(p) ? Math.max(0.06, base * 0.25) : base;
    const key = `${b ? G.farge[p] : FADE}|${a}|${b ? 1 : 0}`;
    let l = grupper.get(key);
    if (!l) { l = { farge: b ? G.farge[p] : FADE, a, lys: b ? 1 : 0, p: [] }; grupper.set(key, l); }
    l.p.push(p);
  }
  const noder = [...grupper.values()].sort((u, v) => u.lys - v.lys || u.a - v.a);
  return { kantar, noder };
}
function teiknBase(ctx, sc) {
  if (!G) return;
  sc.setVerd(ctx);
  const hov = typeof sc.hoverId === "number" ? sc.hoverId : null;
  const key = `${T.versjonNo()}|${hov}|${G.modus}`;
  if (!teiknCache || teiknCache.key !== key) { teiknCache = byggTeiknCache(hov); teiknCache.key = key; }
  for (const k of teiknCache.kantar) {
    ctx.strokeStyle = k.farge;
    ctx.globalAlpha = k.ba;
    ctx.lineWidth = k.bw / sc.K;
    ctx.beginPath();
    const f = k.xy;
    for (let j = 0; j < f.length; j += 4) { ctx.moveTo(f[j], f[j + 1]); ctx.lineTo(f[j + 2], f[j + 3]); }
    ctx.stroke();
  }
  const [x0, y0, x1, y1] = sc.verdBoks();
  const m = 300;
  const s3 = sc.rf * Math.min(sc.k, 3) ** 0.5 / sc.K;
  for (const g of teiknCache.noder) {
    ctx.fillStyle = g.farge;
    ctx.globalAlpha = g.a;
    ctx.beginPath();
    for (const p of g.p) {
      const x = G.x[p], y = G.y[p];
      if (x < x0 - m || x > x1 + m || y < y0 - m || y > y1 + m) continue;
      const r = G.r0[p] * s3;
      ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, 6.2832);
    }
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function ringSkjerm(ctx, sc, p, ekstra, farge = "#fff", w = 1.5) {
  const [px, py] = sc.tilSkjerm(G.x[p], G.y[p]);
  ctx.beginPath(); ctx.arc(px, py, radius(p, sc) + ekstra, 0, 6.2832);
  ctx.strokeStyle = "#000"; ctx.lineWidth = w + 2; ctx.stroke();
  ctx.strokeStyle = farge; ctx.lineWidth = w; ctx.stroke();
}
function teiknOverlay(ctx, sc) {
  if (!G) return;
  sc.setSkjerm(ctx);
  for (const p of G.valdeNoder) ringSkjerm(ctx, sc, p, 2, "#fff", 2);
  for (const p of merkNoder) ringSkjerm(ctx, sc, p, 3);
  for (const p of opneNoder) ringSkjerm(ctx, sc, p, 5, "#fff", 1.5);
  if (typeof sc.hoverId === "number") ringSkjerm(ctx, sc, sc.hoverId, 2);
  if (typeof sc.fokusId === "number") ringSkjerm(ctx, sc, sc.fokusId, 4);
  etikettar = lagEtikettar(sc);
  teiknEtikettar(ctx, etikettar);
}

function lagEtikettar(sc) {
  const filt = T.harFilter();
  const maks = Math.min(60, Math.round((sc.w < 600 ? 8 : 15) * Math.max(1, sc.k)));
  const kand = [], hind = [];
  const inne = [];
  for (const p of G.storst) {
    if (!sc.synleg(G.x[p], G.y[p], -4)) continue;
    inne.push(p);
    if (inne.length > 400) break;
  }
  const rang = inne.slice().sort((a, b) => (filt ? s[b] - s[a] : 0) || G.n[b] - G.n[a] || a - b);
  const font = "12px Literata, Georgia, serif";
  rang.slice(0, 200).forEach((p, j) => {
    const [px, py] = sc.tilSkjerm(G.x[p], G.y[p]);
    hind.push({ id: p, x: px, y: py, r: radius(p, sc), rang: j });
  });
  rang.slice(0, maks * 2).forEach((p, j) => {
    if (filt && s[p] === 0) return;
    const [px, py] = sc.tilSkjerm(G.x[p], G.y[p]);
    kand.push({ id: p, x: px, y: py, r: radius(p, sc), tekst: kutt(G.namn(p), 28), font, h: 15, rang: j });
  });
  // the open work's nodes are always named
  const fast = [...opneNoder].filter((p) => sc.synleg(G.x[p], G.y[p], -4)).map((p) => { const [px, py] = sc.tilSkjerm(G.x[p], G.y[p]); return { id: p, x: px, y: py, r: radius(p, sc) + 5, tekst: kutt(G.namn(p), 28), font, h: 15, rang: -1 }; });
  const plass = plasserEtikettar(fast.concat(kand.filter((k) => !opneNoder.has(k.id))).slice(0, 80), { w: sc.w, h: sc.h, hindringar: hind, blokk: sc.dekkaNo(), forrige: forrigePlass, maks: maks + fast.length });
  forrigePlass = new Map(plass.map((q) => [q.id, q.pos]));
  return plass;
}

// ---------- picking ----------
function finn(px, py, type) {
  if (!G) return null;
  const sc = scene.sc;
  const [x, y] = sc.tilVerd(px, py);
  const touch = type !== "mouse";
  const R = (touch ? 22 : 28) / sc.K;
  const kand = A.innanfor(G.qt, x, y, R + 20 / sc.K, (p) => G.x[p], (p) => G.y[p]);
  const treff = [];
  for (const p of kand) {
    const d = Math.hypot(G.x[p] - x, G.y[p] - y) * sc.K;
    const r = radius(p, sc);
    const rp = touch ? Math.max(r, 22) : Math.max(r, 6);
    if (d <= rp) treff.push({ p, d, r, inne: d <= r, lys: lys(p) });
  }
  if (!treff.length) return null;
  treff.sort((a, b) => (b.lys - a.lys) || (b.inne - a.inne) || (a.inne && b.inne ? a.r - b.r : a.d - b.d));
  return { id: treff[0].p, fleire: treff.length - 1 };
}
const finnId = (id) => ({ id, fleire: 0 });

function partnarar(p, n = 3) {
  const filt = T.harFilter();
  if (!filt) return G.naboar[p].slice(0, n).map(([b, w]) => [b, w]);
  const l = [];
  for (const [b] of G.naboar[p]) {
    const k = Math.min(p, b) * G.N + Math.max(p, b);
    const w = wValt.get(k) || 0;
    if (w > 0) l.push([b, w]);
  }
  l.sort((u, v) => v[1] - u[1] || G.n[v[0]] - G.n[u[0]] || u[0] - v[0]);
  return l.slice(0, n);
}
function nodeHtml(p, fleire) {
  const land = G.land[p] >= 0 ? D.verk.land_alle[G.land[p]].namn : "Ukjent land";
  const filt = T.harFilter();
  const pa = partnarar(p);
  const paTekst = pa.length ? pa.map(([b]) => esc(kutt(G.namn(b), 26))).join(", ") : "ingen";
  return `<div class="tt-tittel">${esc(G.fulltNamn(p))}</div>
    <div class="tt-meta">${esc(land)} · ${fmt(G.n[p])} verk (${fmt(s[p])} i utvalet)</div>
    <div class="tt-meta">${filt ? "Skriv mest med i utvalet" : "Skriv mest med"}: ${paTekst}</div>
    ${fleire ? `<div class="tt-fot">+${fmt(fleire)} til her</div>` : ""}`;
}
function tips(hit) { return nodeHtml(hit.id, hit.fleire) + `<div class="tt-fot">Klikk: vel · Skift-klikk: legg til</div>`; }
function vel(hit, leggTil) { T.veksle(G.dim, G.key(hit.id), { erstatt: !leggTil }); }
function klikk(hit, ev) { vel(hit, ev.shiftKey || ev.ctrlKey || ev.metaKey); }
function kortFor(hit) {
  return { html: nodeHtml(hit.id, hit.fleire), knappar: [{ tekst: "Vel", primar: true, gjer: () => vel(hit, false) }, { tekst: "Legg til", gjer: () => vel(hit, true) }] };
}
function fokusListe() { return G ? G.storst.slice(0, 30).map((p) => ({ id: p, x: G.x[p], y: G.y[p] })) : []; }

// ---------- partner panel (amendment 10) ----------
function teiknPartnar() {
  const el = ramme.flate.querySelector("#nett-partnar");
  const forBreidd = el.hidden ? 0 : el.offsetWidth;
  A.hjelp.bevarFokus(el, () => teiknPartnarInnhald(el));
  if ((el.hidden ? 0 : el.offsetWidth) !== forBreidd) ramme.flate.dispatchEvent(new CustomEvent("utforsk:teikn"));
}
function teiknPartnarInnhald(el) {
  if (G.valdeNoder.size !== 1) { teiknTopp(el); return; }
  const p = [...G.valdeNoder][0];
  const pa = partnarar(p, 10);
  const mx = pa.length ? pa[0][1] : 1;
  el.hidden = false;
  el.innerHTML = `<div class="sidepanel-topp"><span>Skriv saman med: ${esc(kutt(G.namn(p), 24))}</span>
    <button type="button" class="knapp liten" data-p="veksle" aria-expanded="${panelOpe}">${panelOpe ? "Gøym" : "Vis"}</button></div>
    ${panelOpe ? (pa.length ? `<ol>${pa.map(([b, w]) => `<li class="rangrad">
      <button type="button" class="rang-namn" data-p="vel" data-b="${b}" title="${esc(G.fulltNamn(b))}">${esc(kutt(G.namn(b), 30))}</button>
      <span class="rang-tal">${fmt(w)} <button type="button" class="knapp liten leggtil" data-p="legg" data-b="${b}" aria-label="Legg ${esc(G.fulltNamn(b))} til i filteret">+</button></span>
      <span class="rang-bar"><span style="width:${Math.round((100 * w) / mx)}%"></span></span></li>`).join("")}</ol>` : `<p class="dim" style="padding:0 10px">Ingen felles verk i utvalet.</p>`) : ""}`;
}
// Without one chosen node: the ten nodes with most works in the selection, so the
// reader can answer "who works on this" without hunting for bright dots.
function teiknTopp(el) {
  const filt = T.harFilter();
  const N = G.N, l = [];
  for (let p = 0; p < N; p++) { const c = filt ? s[p] : G.n[p]; if (c > 0) l.push([p, c]); }
  l.sort((a, b) => b[1] - a[1] || G.n[b[0]] - G.n[a[0]] || a[0] - b[0]);
  const pa = l.slice(0, 10);
  const mx = pa.length ? pa[0][1] : 1;
  const ord = G.modus === "inst" ? "institusjonar" : "forfattarar";
  el.hidden = false;
  el.innerHTML = `<div class="sidepanel-topp"><span>${filt ? `Flest verk i utvalet` : `Flest verk`}</span>
    <button type="button" class="knapp liten" data-p="veksle" aria-expanded="${panelOpe}">${panelOpe ? "Gøym" : "Vis"}</button></div>
    ${panelOpe ? (pa.length ? `<ol>${pa.map(([b, w]) => `<li class="rangrad">
      <button type="button" class="rang-namn" data-p="velsjolv" data-b="${b}" title="${esc(G.fulltNamn(b))}" aria-label="${esc(G.fulltNamn(b))}, ${fmt(w)} verk: vel og sjå kven dei skriv med">${esc(kutt(G.namn(b), 30))}</button>
      <span class="rang-tal">${fmt(w)} <button type="button" class="knapp liten leggtil" data-p="legg" data-b="${b}" aria-label="Legg ${esc(G.fulltNamn(b))} til i filteret">+</button></span>
      <span class="rang-bar"><span style="width:${Math.round((100 * w) / mx)}%"></span></span></li>`).join("")}</ol>
      <p class="sidepanel-merk">Klikk eit namn for å sjå kven dei skriv saman med.</p>` : `<p class="dim" style="padding:0 10px">Ingen ${ord} har verk i utvalet.</p>`) : ""}`;
}

function partnarKlikk(e) {
  const b = e.target.closest("button[data-p]");
  if (!b) return;
  if (b.dataset.p === "veksle") { panelOpe = !panelOpe; teiknPartnar(); return; }
  const q = +b.dataset.b;
  if (b.dataset.p === "legg") T.veksle(G.dim, G.key(q));
  else if (b.dataset.p === "velsjolv") vel({ id: q }, e.shiftKey || e.ctrlKey || e.metaKey);
  else { scene.sentrer(G.x[q], G.y[q]); }
}

// ---------- line and legend ----------
function teiknLinje() {
  const inst = G.modus === "inst";
  const alle = G.tal.alle, vist = G.tal.vist;
  let t = `${inst ? "Institusjonar" : "Forfattarar"} som skriv saman. Linje = minst eitt felles verk. Viser ${fmt(vist)} av ${fmt(alle)} ${inst ? "institusjonar" : "forfattarar"} (minst ${G.tal.min_verk} verk). Berre OpenAlex: ${fmt(G.harLag)} av ${fmt(T.valt)} verk i utvalet har ${inst ? "institusjon" : "forfattar med id"}.`;
  if (!inst) t += " Verk der ein person berre står med namn (mest arkivverk) er ikkje talde under personen.";
  if (S.verk && D.idx.has(S.verk) && !opneNoder.size) t += " Det opne verket har ingen node i nettet.";
  ramme.linje.textContent = t;
  scene.settLabel(t);
  const tel = new Map();
  for (let p = 0; p < G.N; p++) { const k = G.land[p] >= 0 ? D.verk.land_alle[G.land[p]].k : ""; const f = G.farge[p]; const key = LAND_FARGE[k] ? k : f === UKJEND ? "" : "andre"; tel.set(key, (tel.get(key) || 0) + 1); }
  const post = [...tel.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => {
    const namn = k === "" ? "Ukjend" : k === "andre" ? "Andre land" : D.verk.land_alle[D.flandIdx.get(k)].namn;
    const f = k === "" ? UKJEND : k === "andre" ? "#9a9a9a" : LAND_FARGE[k];
    return `<span class="teikn-post"><span class="prikk" style="background:${f}"></span>${esc(namn)}</span>`;
  }).join("");
  ramme.teikn.innerHTML = `${post}<span class="teikn-merk">Farge: hovudland. Storleik: verk. Linje: felles verk${T.harFilter() ? " i utvalet" : ""}.</span>`;
}
