// Kart: every work as a point, similar works near each other.
import { esc, fmt, kutt, PALETTE_TEMA, LAND_FARGE, FLEIRE_LAND, UKJEND, KGR_FARGE, FADE, FADE_ALFA, lys, tween, rorsle, plasserEtikettar, teiknEtikettar, tooltip, kort, segmentert, smal, settInnhald, KL, klyngeTekst } from "../hjelp.js?v=28";

let A, T, D, S, ramme, scene;
let qt;
let rBase;
let kat, katFarge = [], katNamn = [];
let grupper = null;     // {lyse: [Int32Array per kat], blek: Int32Array, inn: [...], ut: [...]}
let tweenA = 1, stoppTween = null;
let forrigeLys = null;
let merkI = null;
let etikettar = [], forrigePlass = new Map();
let sitOrd;
let fargeSeg, lassoKnapp, zoomKnapp;
const ARR = 1, R_MAX = 9;
let invitasjonBrukt = false;
let puls = null, stoppPuls = null;   // a short pulse round the work just opened
let temaTal = null, temaTalV = -1;   // works in the selection per theme
// Under this many works in the selection, the bright points are drawn larger and ringed.
const LITE = 200;
const liteUtval = () => T.harFilter() && T.valt > 0 && T.valt <= LITE;

const AR_FARGE = (ar) => {
  const t = (Math.max(1990, Math.min(2026, ar)) - 1990) / 36;
  return window.d3.interpolatePlasma(0.2 + 0.8 * t);
};

export default {
  id: "kart",
  filer: [],
  skript: [],
  async init(el, api) {
    A = api; T = api.T; D = api.D; S = api.S; ramme = api.ramme;
    const n = D.n;
    rBase = new Float32Array(n);
    for (let i = 0; i < n; i++) rBase[i] = 1.8 + 1.1 * Math.log10(1 + Math.max(D.sit[i], 0));
    sitOrd = Int32Array.from(Array.from({ length: n }, (_, i) => i).sort((a, b) => D.sit[b] - D.sit[a] || a - b));
    qt = api.lagIndeks(n, (i) => D.x[i], (i) => D.y[i]);
    fargeSeg = segmentert(ramme.kontroll, {
      namn: "Farge", verdi: S.kart.farge,
      val: [{ k: "tema", namn: "Klynge" }, { k: "land", namn: "Land" }, { k: "kanal", namn: "Kanal" }, { k: "ar", namn: "År" }],
      ved: (v) => T.endre((s) => { s.kart.farge = v; }),
    });
    fargeSeg.el.insertAdjacentHTML("beforebegin", `<span class="kontroll-namn">Farge</span>`);
    scene = api.lagScene(ramme.flate, {
      verd: [10000, 10000], skala: [0.8, 40], rolle: "kart over verk",
      teiknBase, teiknOverlay, finn, tips, klikk, kort: kortFor, tapHandling, finnId,
      tomKlikk: () => {},
      vedZoom: (z) => T.settZoom("kart", z),
      lasso: { ferdig: lassoFerdig },
      fokusListe, fokusHandling: (id) => A.opneVerk(id),
      feil: api.feil,
    });
    ramme.flate.insertAdjacentHTML("beforeend", `<div class="verktoy" role="toolbar" aria-label="Verktøy for kartet">
      <button type="button" class="knapp" data-v="lasso" aria-pressed="false" title="Dra ein ring rundt verk for å velje dei. Skift-dra gjer det same.">Vel område</button>
      <button type="button" class="knapp" data-v="zoomutval" title="Zoom til verka i utvalet">Zoom til utvalet</button>
    </div>`);
    lassoKnapp = ramme.flate.querySelector('[data-v="lasso"]');
    zoomKnapp = ramme.flate.querySelector('[data-v="zoomutval"]');
    lassoKnapp.addEventListener("click", () => settLasso(!scene.lassoModus()));
    zoomKnapp.addEventListener("click", zoomTilUtval);
    ramme.teikn.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-dim]");
      if (b) T.veksle(b.dataset.dim, b.dataset.k);
    });
    scene.storleik();
    if (S.kart.z) scene.settZ(S.kart.z);
    // a one-line invitation over the first screen; it goes at the first filter or opened work
    ramme.flate.insertAdjacentHTML("beforeend", `<p class="invitasjon" hidden>Søk, klikk ei klynge eller dra ein ring rundt punkt for å starte.</p>`);
  },
  oppdater(s, e) {
    if (!kat || e.visning.has("kart.farge")) { lagFargar(); fargeSeg.set(S.kart.farge); }
    if (!grupper || e.filter || e.visning.has("kart.farge")) byggGrupper(e.filter && !e.popstate && grupper && !e.visning.has("kart.farge"));
    if (e.popstate || e.vis) { const z = S.kart.z; const n = scene.zNo(); if (!z || Math.abs(z[0] - n[0]) > 0.01 || Math.abs(z[1] - n[1]) > 1 || Math.abs(z[2] - n[2]) > 1) scene.settZ(z); }
    if (e.verk && S.verk) startPuls();
    teiknTeikn();
    teiknLinje();
    zoomKnapp.disabled = !(T.valt > 0 && T.valt < D.n);
    // a small selection is easy to lose among 6 432 dots: the zoom button is then the obvious next step
    zoomKnapp.classList.toggle("primar", liteUtval());
    const inv = ramme.flate.querySelector(".invitasjon");
    if (T.harFilter() || S.verk) invitasjonBrukt = true;
    if (inv) inv.hidden = invitasjonBrukt;
    scene.teikn();
  },
  storleik() { scene.storleik(); },
  merk(i) { merkI = i; scene.teiknOverlay(); },
  sentrer(i) {
    const ark = document.getElementById("listepanel").getBoundingClientRect();
    const r = ramme.flate.getBoundingClientRect();
    const dekt = Math.max(0, r.bottom - ark.top);
    scene.sentrer(D.x[i], D.y[i], dekt);
  },
  // opened from the list: bring the work into the middle part of the map, so its mark (and the
  // pulse) is where the eye is, not at an edge or under a control
  panTil(i) {
    const sc = scene.sc;
    const [px, py] = sc.tilSkjerm(D.x[i], D.y[i]);
    if (px < sc.w * 0.2 || px > sc.w * 0.8 || py < sc.h * 0.2 || py > sc.h * 0.8) scene.sentrer(D.x[i], D.y[i]);
  },
  vis() { scene.storleik(); },
  skjul() { tooltip.skjul(); },
  avbrytLasso() { return scene.avbrytLasso(); },
  fokusUt() { return scene.fokusUt(); },
  // for measuring
  scene: () => scene,
  etikettar: () => etikettar,
  finn: (px, py, type = "mouse") => finn(px, py, type),
};

function settLasso(v) {
  scene.settLassoModus(v);
  lassoKnapp.setAttribute("aria-pressed", String(v));
  lassoKnapp.textContent = v ? "Flytt" : "Vel område";
  lassoKnapp.title = v ? "Tilbake til å flytte kartet" : "Dra ein ring rundt verk for å velje dei. Skift-dra gjer det same.";
}

function lassoFerdig(poly, peikar) {
  T.endre((s) => { s.f.omr = poly; });
  if (peikar !== "mouse") settLasso(false);
}

function zoomTilUtval() {
  const xs = [], ys = [];
  for (let i = 0; i < D.n; i++) if (T.utval[i]) { xs.push(D.x[i]); ys.push(D.y[i]); }
  if (!xs.length) return;
  xs.sort((a, b) => a - b); ys.sort((a, b) => a - b);
  const c = Math.floor(xs.length * 0.02), d = xs.length - 1 - c;
  const ark = document.getElementById("listepanel").getBoundingClientRect();
  const r = ramme.flate.getBoundingClientRect();
  const dekt = smal() ? Math.max(0, r.bottom - ark.top) : 0;
  const pad = 60;
  scene.zoomTilBoks([xs[c] - pad, ys[c] - pad, xs[d] + pad, ys[d] + pad], 300, dekt);
}

// ---------- colours and groups ----------
function lagFargar() {
  const n = D.n, v = D.verk, modus = S.kart.farge;
  kat = new Uint8Array(n);
  if (modus === "tema") {
    katFarge = PALETTE_TEMA.slice(0, v.tema.length); katNamn = v.tema.map((t) => t.namn);
    for (let i = 0; i < n; i++) kat[i] = D.tema[i];
  } else if (modus === "land") {
    const kodar = v.land.map((l) => l.k);
    katFarge = [...kodar.map((c) => LAND_FARGE[c]), FLEIRE_LAND, UKJEND];
    katNamn = [...v.land.map((l) => l.namn), "Fleire land", "Ukjend"];
    for (let i = 0; i < n; i++) {
      const b = D.landBits[i];
      if (!b) kat[i] = kodar.length + 1;
      else if (b & (b - 1)) kat[i] = kodar.length;
      else kat[i] = Math.log2(b);
    }
  } else if (modus === "kanal") {
    katFarge = v.kanalgrupper.map((g) => KGR_FARGE[g.k] || "#9fb3c8"); katNamn = v.kanalgrupper.map((g) => g.namn);
    for (let i = 0; i < n; i++) kat[i] = D.kgrAv[i];
  } else {
    katFarge = []; katNamn = [];
    for (let a = 1983; a <= 2026; a++) { katFarge.push(AR_FARGE(a)); katNamn.push(String(a)); }
    for (let i = 0; i < n; i++) kat[i] = D.ar[i] - 1983;
  }
}

function byggGrupper(anim) {
  const n = D.n, K = katFarge.length, u = T.utval;
  const ny = new Uint8Array(n);
  for (let i = 0; i < n; i++) ny[i] = u[i];
  const prev = forrigeLys;
  forrigeLys = ny;
  const tel = (pred) => { const c = new Int32Array(K); for (let i = 0; i < n; i++) if (pred(i)) c[kat[i]]++; return c; };
  const fyll = (pred, c) => {
    const arr = Array.from({ length: K }, (_, k) => new Int32Array(c[k]));
    const p = new Int32Array(K);
    for (let i = 0; i < n; i++) if (pred(i)) { const k = kat[i]; arr[k][p[k]++] = i; }
    return arr;
  };
  const harEndring = anim && prev && !rorsle.redusert;
  let blek = [];
  for (let i = 0; i < n; i++) if (!ny[i] && !(harEndring && prev[i])) blek.push(i);
  if (harEndring) {
    const lyse = fyll((i) => ny[i] && prev[i], tel((i) => ny[i] && prev[i]));
    const inn = fyll((i) => ny[i] && !prev[i], tel((i) => ny[i] && !prev[i]));
    const ut = fyll((i) => !ny[i] && prev[i], tel((i) => !ny[i] && prev[i]));
    grupper = { lyse, blek: Int32Array.from(blek), inn, ut };
    if (stoppTween) stoppTween();
    tweenA = 0;
    stoppTween = tween(250, (t) => { tweenA = t; scene.teikn(); }, () => { stoppTween = null; byggGrupper(false); scene.teikn(); });
  } else {
    if (stoppTween) { stoppTween(); stoppTween = null; }
    grupper = { lyse: fyll((i) => ny[i], tel((i) => ny[i])), blek: Int32Array.from(blek), inn: null, ut: null };
    tweenA = 1;
  }
}

// ---------- drawing ----------
function radius(i, sc) {
  const r = Math.min(R_MAX, rBase[i] * Math.min(sc.k, 4) ** 0.5);
  return T.utval[i] && liteUtval() ? Math.max(4, r) : r;
}
function sti(ctx, ids, sc, vb) {
  const K = sc.K;
  const s = Math.min(sc.k, 4) ** 0.5;
  const [x0, y0, x1, y1] = vb;
  for (let j = 0; j < ids.length; j++) {
    const i = ids[j];
    const x = D.x[i], y = D.y[i];
    if (x < x0 || x > x1 || y < y0 || y > y1) continue;
    const r = Math.min(R_MAX, rBase[i] * s) / K;
    ctx.moveTo(x + r, y);
    ctx.arc(x, y, r, 0, 6.2832);
  }
}
function teiknBase(ctx, sc) {
  if (!grupper) return;
  sc.setVerd(ctx);
  const m = 12 / sc.K;
  const [a0, b0, a1, b1] = sc.verdBoks();
  const vb = [a0 - m, b0 - m, a1 + m, b1 + m];
  const a = tweenA;
  const g = grupper;
  const fyllGrupper = (arr, alfa, farge) => {
    if (alfa <= 0.003) return;
    ctx.globalAlpha = alfa;
    for (let k = 0; k < arr.length; k++) {
      if (!arr[k].length) continue;
      ctx.fillStyle = farge || katFarge[k];
      ctx.beginPath(); sti(ctx, arr[k], sc, vb); ctx.fill();
    }
  };
  // faded first
  ctx.fillStyle = FADE;
  ctx.globalAlpha = FADE_ALFA;
  ctx.beginPath(); sti(ctx, g.blek, sc, vb); ctx.fill();
  if (g.ut) fyllGrupper(g.ut, FADE_ALFA * a, FADE);
  if (g.inn) fyllGrupper(g.inn, FADE_ALFA * (1 - a), FADE);
  fyllGrupper(g.lyse, 1);
  if (g.inn) fyllGrupper(g.inn, a);
  if (g.ut) fyllGrupper(g.ut, 1 - a);
  ctx.globalAlpha = 1;
  if (liteUtval()) teiknLite(ctx, sc, vb, g.inn ? a : 1);
}

// A small selection: every bright point at least 4 px, with a dark gap and a white ring,
// so 8 works among 6 432 can be counted by eye.
function teiknLite(ctx, sc, vb, alfa) {
  const K = sc.K, s = Math.min(sc.k, 4) ** 0.5;
  const [x0, y0, x1, y1] = vb;
  const grupper = grupperLyse();
  ctx.globalAlpha = alfa;
  const ring = new Path2D(), svart = new Path2D();
  for (let k = 0; k < grupper.length; k++) {
    const ids = grupper[k];
    if (!ids.length) continue;
    ctx.fillStyle = katFarge[k];
    ctx.beginPath();
    for (let j = 0; j < ids.length; j++) {
      const i = ids[j], x = D.x[i], y = D.y[i];
      if (x < x0 || x > x1 || y < y0 || y > y1) continue;
      const r = Math.max(4, Math.min(R_MAX, rBase[i] * s)) / K;
      ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, 6.2832);
      svart.moveTo(x + r + 1.5 / K, y); svart.arc(x, y, r + 1.5 / K, 0, 6.2832);
      ring.moveTo(x + r + 3 / K, y); ring.arc(x, y, r + 3 / K, 0, 6.2832);
    }
    ctx.fill();
  }
  ctx.strokeStyle = KL.kontur; ctx.lineWidth = 2 / K; ctx.stroke(svart);
  ctx.strokeStyle = KL.ring9; ctx.lineWidth = 1.25 / K; ctx.stroke(ring);
  ctx.globalAlpha = 1;
}
function grupperLyse() {
  const g = grupper;
  if (!g.inn) return g.lyse;
  return g.lyse.map((l, k) => Int32Array.from([...l, ...g.inn[k]]));
}

function ring(ctx, sc, i, ekstra = 3) {
  const [px, py] = sc.tilSkjerm(D.x[i], D.y[i]);
  const r = radius(i, sc) + ekstra;
  ctx.beginPath(); ctx.arc(px, py, r, 0, 6.2832);
  ctx.strokeStyle = KL.kontur; ctx.lineWidth = 3.5; ctx.stroke();
  ctx.strokeStyle = KL.ring; ctx.lineWidth = 1.5; ctx.stroke();
}

function teiknOverlay(ctx, sc) {
  sc.setSkjerm(ctx);
  // outline of omr
  if (S.f.omr) {
    ctx.beginPath();
    S.f.omr.forEach(([x, y], j) => { const [px, py] = sc.tilSkjerm(x, y); if (j) ctx.lineTo(px, py); else ctx.moveTo(px, py); });
    ctx.closePath();
    ctx.setLineDash([4, 4]); ctx.strokeStyle = KL.ring; ctx.lineWidth = 1; ctx.stroke(); ctx.setLineDash([]);
  }
  etikettar = lagEtikettar(sc);
  for (const l of etikettar) {
    if (l.data && l.data.alfa != null) teiknEtikettar(ctx, [l], { alfa: l.data.alfa });
  }
  teiknEtikettar(ctx, etikettar.filter((l) => !l.data || l.data.alfa == null));
  const vi = S.verk ? D.idx.get(S.verk) : null;
  const vist = new Set([vi]);
  for (const i of [merkI, typeof sc.hoverId === "number" ? sc.hoverId : null, typeof sc.fokusId === "number" ? sc.fokusId : null]) {
    if (i == null || vist.has(i)) continue;
    vist.add(i);
    ring(ctx, sc, i);
  }
  if (vi != null) opneMerke(ctx, sc, vi);
}

// The open work has its own mark, unlike any other ring on the map: a thick outer ring with
// four ticks, a dark halo, a pulse when it opens, and its title as a label.
function opneMerke(ctx, sc, i) {
  const [px, py] = sc.tilSkjerm(D.x[i], D.y[i]);
  if (px < -40 || px > sc.w + 40 || py < -40 || py > sc.h + 40) return;
  const r = radius(i, sc);
  if (puls) {
    for (const d of [0, 0.35]) {
      const t = puls.t - d;
      if (t <= 0 || t >= 1) continue;
      ctx.beginPath(); ctx.arc(px, py, r + 6 + 34 * t, 0, 6.2832);
      ctx.globalAlpha = 0.9 * (1 - t); ctx.strokeStyle = KL.ring; ctx.lineWidth = 2; ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  ctx.beginPath(); ctx.arc(px, py, r + 3, 0, 6.2832);
  ctx.strokeStyle = KL.kontur; ctx.lineWidth = 3.5; ctx.stroke();
  ctx.strokeStyle = KL.ring; ctx.lineWidth = 1.5; ctx.stroke();
  const R = r + 9;
  ctx.beginPath(); ctx.arc(px, py, R, 0, 6.2832);
  ctx.strokeStyle = KL.kontur; ctx.lineWidth = 5; ctx.stroke();
  ctx.strokeStyle = KL.ring; ctx.lineWidth = 2.5; ctx.stroke();
  // four short ticks outside the ring: the mark reads as "here" even among ringed points
  ctx.beginPath();
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { ctx.moveTo(px + dx * (R + 3), py + dy * (R + 3)); ctx.lineTo(px + dx * (R + 10), py + dy * (R + 10)); }
  ctx.strokeStyle = KL.kontur; ctx.lineWidth = 4.5; ctx.stroke();
  ctx.strokeStyle = KL.ring; ctx.lineWidth = 2; ctx.stroke();
}
function startPuls() {
  if (stoppPuls) stoppPuls();
  if (rorsle.redusert) { puls = null; return; }
  puls = { t: 0 };
  stoppPuls = tween(1100, (t) => { if (puls) puls.t = t * 1.35; scene.teiknOverlay(); }, () => { puls = null; stoppPuls = null; scene.teiknOverlay(); });
}
let dublettTal = null;
function talDublettar() { if (dublettTal == null) { dublettTal = 0; for (let i = 0; i < D.n; i++) if (D.merk[i] & 5) dublettTal++; } return dublettTal; }
function reknTemaTal() {
  if (temaTalV === T.versjonNo() && temaTal) return temaTal;
  const c = new Int32Array(D.verk.tema.length), u = T.utval;
  for (let i = 0; i < D.n; i++) if (u[i]) c[D.tema[i]]++;
  temaTal = c; temaTalV = T.versjonNo();
  return c;
}

function lagEtikettar(sc) {
  const k = sc.k, v = D.verk, kand = [];
  const smalt = sc.w < 600;
  let alfa = 1;
  const vi = S.verk ? D.idx.get(S.verk) : null;
  if (vi != null && sc.synleg(D.x[vi], D.y[vi])) {
    const [px, py] = sc.tilSkjerm(D.x[vi], D.y[vi]);
    kand.push({ id: `v${vi}`, x: px, y: py, r: radius(vi, sc) + 11, tekst: `${kutt(D.kol.tittel[vi], 44)} (${D.ar[vi]})`, font: "600 12px Literata, Georgia, serif", h: 16, farge: KL.sterk, forst: true, prio: 1e9 });
  }
  if (k < 3.0) {
    alfa = k < 2.5 ? 1 : 1 - (k - 2.5) / 0.5;
    const font = `600 ${smalt ? 13 : 15}px Literata, Georgia, serif`;
    // with a filter, each theme name carries its count in the selection and fades where it has
    // none, as the points do: the eye goes to where the matches are
    const filt = T.harFilter(), c = filt ? reknTemaTal() : null;
    v.tema.forEach((t, j) => {
      const [px, py] = sc.tilSkjerm(t.lx, t.ly);
      const tom = filt && !c[j];
      const a = alfa * (tom ? 0.5 : 1);
      kand.push({ id: `t${j}`, x: px, y: py, r: 0, tekst: filt ? `${t.namn} · ${fmt(c[j])}` : t.namn, font, h: smalt ? 16 : 18, sentrert: true, farge: tom ? KL.dim : klyngeTekst(PALETTE_TEMA[j]), prio: t.n, data: { tema: j, alfa: a < 1 ? a : null, synleg: alfa } });
    });
  }
  if (k >= 2.5 && k < 6) {
    const font = "13px Literata, Georgia, serif";
    const ut = v.undertema.map((u, j) => ({ u, j })).filter(({ u }) => sc.synleg(u.lx, u.ly)).sort((a, b) => b.u.n - a.u.n);
    for (const { u, j } of ut) {
      const [px, py] = sc.tilSkjerm(u.lx, u.ly);
      kand.push({ id: `u${j}`, x: px, y: py, r: 0, tekst: u.namn, font, h: 16, sentrert: true, farge: KL.tekst3, prio: u.n });
    }
  }
  if (k >= 6) {
    const font = "12px Literata, Georgia, serif";
    let c = 0;
    for (const i of sitOrd) {
      if (D.sit[i] < 0) break;
      if ((!T.utval[i] && T.harFilter()) || i === vi) continue;
      if (!sc.synleg(D.x[i], D.y[i])) continue;
      const [px, py] = sc.tilSkjerm(D.x[i], D.y[i]);
      kand.push({ id: i, x: px, y: py, r: radius(i, sc), tekst: kutt(D.kol.tittel[i], 48), font, h: 15, farge: KL.tekst2, prio: D.sit[i] });
      if (++c >= 40) break;
    }
  }
  const plass = plasserEtikettar(kand, { w: sc.w, h: sc.h, blokk: sc.dekkaNo(), forrige: forrigePlass, maks: k >= 6 ? 25 : 80 });
  forrigePlass = new Map(plass.map((p) => [p.id, p.pos]));
  return plass;
}

// ---------- picking (amendments 28, 29, 32) ----------
function finn(px, py, type) {
  const sc = scene.sc;
  const [x, y] = sc.tilVerd(px, py);
  const touch = type !== "mouse";
  const R = (touch ? 22 : Math.max(R_MAX, 6)) / sc.K;
  // A theme name wins over the points under it: the names sit in the middle of their clusters,
  // so "only where no point is near" left almost no clickable pixels. The points under a name
  // are reached by zooming in (the names fade out from k = 2.5) or from the list.
  for (const l of etikettar) {
    if (!l.data || l.data.tema == null || (l.data.synleg != null && l.data.synleg < 0.5)) continue;
    const b = l.boks;
    if (px >= b.x0 && px <= b.x1 && py >= b.y0 && py <= b.y1) return { id: `tema${l.data.tema}`, type: "tema", tema: l.data.tema };
  }
  const kand = A.innanfor(qt, x, y, R, (i) => D.x[i], (i) => D.y[i]);
  const filt = T.harFilter();
  const treff = [];
  for (const i of kand) {
    const d = Math.hypot(D.x[i] - x, D.y[i] - y) * sc.K;
    const rp = touch ? 22 : Math.max(radius(i, sc), 6);
    if (d <= rp) treff.push({ i, d, lys: !filt || T.utval[i] });
  }
  if (treff.length) {
    treff.sort((a, b) => (b.lys - a.lys) || a.d - b.d);
    const best = treff[0];
    if (touch) {
      const naer = treff.filter((t) => t.d <= 16);
      if (naer.length >= 3) return { id: `k${best.i}`, type: "klynge", i: best.i, liste: naer.map((t) => t.i), x, y };
    }
    return { id: best.i, type: "verk", i: best.i, fleire: treff.length - 1 };
  }
  return null;
}
function finnId(id) { return typeof id === "number" ? { id, type: "verk", i: id, fleire: 0 } : null; }

function verkHtml(i, fleire) {
  const v = D.verk;
  const f = D.kol.forf[i];
  const forf = f.length ? v.forfattarar[f[0]].namn + (f.length > 1 ? " m.fl." : "") : "Ukjend forfattar";
  const kanal = D.kanal[i] >= 0 ? v.kanalar[D.kanal[i]].namn : "";
  const t = v.tema[D.tema[i]];
  const pdfOrd = ["Open PDF, stadfest", "Lenkje, ikkje stadfest", "Berre DOI", "Inga lenkje"][D.pdf[i]];
  const sit = D.sit[i] >= 0 ? `${fmt(D.sit[i])} siteringar` : `Arkiv${D.lenker && D.lenker.kjelde[i] ? ": " + esc(D.lenker.kjelde[i]) : ""}`;
  return `<div class="tt-tittel">${esc(D.kol.tittel[i])}</div>
    <div class="tt-meta">${esc(forf)} · ${D.ar[i]}${kanal ? " · " + esc(kutt(kanal, 50)) : ""}</div>
    <div class="tt-meta"><span class="prikk" style="background:${PALETTE_TEMA[D.tema[i]]}"></span>${esc(t.namn)} · ${sit} · ${pdfOrd}</div>
    ${fleire ? `<div class="tt-fot">+${fmt(fleire)} til her</div>` : ""}`;
}
function temaHtml(j) {
  const t = D.verk.tema[j];
  const c = reknTemaTal()[j];
  const del = T.harFilter() ? `${fmt(c)} av ${fmt(t.n)} verk i utvalet` : `${fmt(t.n)} verk`;
  return `<div class="tt-tittel"><span class="prikk" style="background:${PALETTE_TEMA[j]}"></span>${esc(t.namn)}</div><div class="tt-meta">Klynge · ${del}</div>${S.f.tema.has(t.k) ? `<div class="tt-meta">Valt no</div>` : ""}`;
}
function tips(hit) {
  if (hit.type === "tema") return temaHtml(hit.tema) + `<div class="tt-fot">Klikk for å velje klynge · Skift-klikk: legg til</div>`;
  if (hit.type === "verk") return verkHtml(hit.i, hit.fleire) + `<div class="tt-fot">Klikk: opne verket</div>`;
  return "";
}
function klikk(hit, ev) {
  if (hit.type === "tema") T.veksle("tema", D.verk.tema[hit.tema].k, { erstatt: !(ev.shiftKey || ev.ctrlKey || ev.metaKey) });
  else if (hit.type === "verk") A.opneVerk(hit.i);
}
function kortFor(hit) {
  if (hit.type === "verk") return { html: verkHtml(hit.i, hit.fleire), knappar: [{ tekst: "Opne verket", primar: true, gjer: () => A.opneVerk(hit.i) }] };
  if (hit.type === "tema") return { html: temaHtml(hit.tema), knappar: [{ tekst: "Vel", primar: true, gjer: () => T.veksle("tema", D.verk.tema[hit.tema].k, { erstatt: true }) }, { tekst: "Legg til", gjer: () => T.veksle("tema", D.verk.tema[hit.tema].k) }] };
  const topp = hit.liste.slice().sort((a, b) => D.sit[b] - D.sit[a] || a - b).slice(0, 3);
  return {
    html: `<div class="tt-tittel">${fmt(hit.liste.length)} verk her</div>${topp.map((i) => `<div class="tt-meta">${esc(kutt(D.kol.tittel[i], 70))} · ${D.ar[i]}</div>`).join("")}`,
    knappar: [
      { tekst: "Vel desse", primar: true, gjer: () => velSirkel(hit.x, hit.y) },
      { tekst: "Zoom hit", gjer: () => { const r = 60 / scene.sc.K; scene.zoomTilBoks([hit.x - r, hit.y - r, hit.x + r, hit.y + r], 300); } },
    ],
  };
}
function velSirkel(x, y) {
  const r = 16 / scene.sc.K;
  const poly = [];
  for (let j = 0; j < 12; j++) poly.push([Math.round(x + r * Math.cos((j * Math.PI) / 6)), Math.round(y + r * Math.sin((j * Math.PI) / 6))]);
  T.endre((s) => { s.f.omr = poly; });
}
function tapHandling(hit) {
  if (hit.type === "verk") A.opneVerk(hit.i);
  else if (hit.type === "tema") T.veksle("tema", D.verk.tema[hit.tema].k, { erstatt: true });
  else velSirkel(hit.x, hit.y);
}
function fokusListe() {
  const ut = [];
  for (const i of sitOrd) { if (T.utval[i]) ut.push({ id: i, x: D.x[i], y: D.y[i] }); if (ut.length >= 30) break; }
  return ut;
}

// ---------- line and legend ----------
function teiknLinje() {
  const n = D.n;
  let t = `Kvart punkt er eitt verk. Verk med lik tekst (tittel og samandrag) ligg nær kvarandre.${T.harFilter() ? ` ${fmt(T.valt)} av ${fmt(n)} verk i utvalet.` : ""}`;
  if (S.kart.farge === "land") {
    let m = 0;
    for (let i = 0; i < n; i++) if (T.utval[i] && D.landBits[i]) m++;
    t += ` Land (nordisk tilknyting, elles kjelda): ${fmt(m)} av ${fmt(T.valt)} har nordisk land.`;
  } else if (S.kart.farge === "kanal") {
    let m = 0;
    for (let i = 0; i < n; i++) if (T.utval[i] && D.kanal[i] >= 0) m++;
    t += ` ${fmt(m)} av ${fmt(T.valt)} har kjend kanal.`;
  }
  ramme.linje.textContent = t;
  scene.settLabel(`${t} Lista ved sida av viser dei same verka.`);
}
function teiknTeikn() {
  const v = D.verk, modus = S.kart.farge, u = T.utval, n = D.n;
  let html = "";
  if (modus === "ar") {
    const g = [0, 0.25, 0.5, 0.75, 1].map((t) => `${window.d3.interpolatePlasma(0.2 + 0.8 * t)} ${t * 100}%`).join(",");
    html = `<span class="teikn-post"><span class="gradient" style="background:linear-gradient(90deg,${g})"></span></span><span class="teikn-merk">1990 · 2000 · 2010 · 2020 · 2026</span>`;
  } else {
    const c = new Int32Array(katFarge.length);
    if (modus === "land") {
      for (let i = 0; i < n; i++) if (u[i]) { const b = D.landBits[i]; if (!b) c[v.land.length + 1]++; else { for (let j = 0; j < 5; j++) if (b & (1 << j)) c[j]++; if (b & (b - 1)) c[v.land.length]++; } }
    } else for (let i = 0; i < n; i++) if (u[i]) c[kat[i]]++;
    const dim = modus === "tema" ? "tema" : modus === "land" ? "land" : "kgr";
    html = katFarge.map((f, k) => {
      let key, aktiv;
      if (modus === "tema") key = v.tema[k].k;
      else if (modus === "land") key = k < v.land.length ? v.land[k].k : k === v.land.length ? null : "X";
      else key = v.kanalgrupper[k].k;
      const inner = `<span class="prikk" style="background:${f}"></span>${esc(katNamn[k])} <span class="tal">${fmt(c[k])}</span>`;
      if (!key) return `<span class="teikn-post" title="Berre vist, ikkje eit filter">${inner}</span>`;
      aktiv = S.f[dim].has(key);
      return `<button type="button" class="teikn-post" data-dim="${dim}" data-k="${esc(key)}" aria-pressed="${aktiv}">${inner}</button>`;
    }).join("");
    if (modus === "land") html += `<span class="teikn-merk">Land (nordisk tilknyting, elles kjelda). Verk med fleire land tel under kvart land.</span>`;
    if (modus === "tema") html += `<span class="teikn-merk">Dei same åtte klyngene som i Kart-fana på hovudsida: grupper av verk med lik tekst, ikkje emne sett av nokon. Dei to siste har mest arkivverk (43 og 45 %).</span>`;
  }
  html += `<span class="teikn-merk">Storleik: siteringar (berre OpenAlex)</span>`;
  html += `<span class="teikn-merk">${fmt(talDublettar())} verk (${Math.round((100 * talDublettar()) / D.n)} %) står truleg to gonger, i arkivet og i OpenAlex; dei er med i tala og merkte i detaljen.</span>`;
  settInnhald(ramme.teikn, html);
}
