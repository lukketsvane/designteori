// Verda: a real map. Places as bubbles, collaboration as arcs, with time.
import { esc, fmt, kutt, landFarge, FADE, plasserEtikettar, teiknEtikettar, tooltip, kort, rorsle, settInnhald } from "../hjelp.js?v=25";

const NORDISK_ID = new Set(["578", "752", "208", "246", "352"]);
const VW = 1000;
let A, T, D, S, ramme, d3, scene;
let proj, land = null, landNordisk = null, landFeil = false;
let P = null;                  // places: x, y, n, ...
let sVal = null, bogar = [], bogarTotalt = 0, wmax = 1, smax = 1;
let merkStader = new Set();
let etikettar = [], forrigePlass = new Map();
let spel = null;               // {ar, tid}
let eigaEndring = false;
let slider = null;
let hoverBoge = null;

export default {
  id: "verda",
  filer: ["stader.json"],
  // topojson is loaded with the country outlines; without it the places are still drawn
  skript: [],
  async init(rot, api) {
    A = api; T = api.T; D = api.D; S = api.S; ramme = api.ramme; d3 = window.d3;
    proj = d3.geoAzimuthalEqualArea().rotate([-15, -62]).precision(0.3);
    const boks = { type: "MultiPoint", coordinates: [[4, 54], [32, 54], [4, 71.5], [32, 71.5], [18, 54], [18, 71.5], [-24.5, 63.3], [-24.5, 66.6], [-13.5, 66.6]] };
    proj.fitExtent([[0, 0], [VW, VW]], boks);
    lagStader();
    scene = api.lagScene(ramme.flate, {
      verd: [VW, VW], skala: [0.05, 30], rolle: "verdskart", fri: true, marg: 0.02,
      teiknBase, teiknOverlay, finn, tips, klikk, kort: kortFor, tapHandling: (h) => handling(h, false), finnId: (id) => ({ id, type: "stad", p: id, fleire: 0 }),
      hoverEndra: (h) => { hoverBoge = h && h.type === "boge" ? h.b : null; scene.teikn(); },
      vedZoom: (z) => T.settZoom("verda", z),
      fokusListe: () => P.storst.slice(0, 30).map((p) => ({ id: p, x: P.x[p], y: P.y[p] })),
      fokusHandling: (id) => handling({ type: "stad", p: id }, false),
      stopp: () => stoppSpel(),
      feil: api.feil,
    });
    ramme.flate.insertAdjacentHTML("beforeend", `<div class="verktoy" role="toolbar" aria-label="Utsnitt">
      <button type="button" class="knapp" data-v="verda">Heile verda</button><button type="button" class="knapp" data-v="norden">Norden</button></div>`);
    ramme.flate.querySelector(".verktoy").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-v]");
      if (!b) return;
      if (b.dataset.v === "verda") scene.settZ([0.08, VW / 2, VW / 2], 600, false);
      else scene.settZ(null, 600, false);
    });
    // time control
    ramme.el.insertAdjacentHTML("beforeend", `<div class="tidskontroll"><div class="verda-ar"></div><button type="button" class="knapp spel" aria-pressed="false">Spel av</button><span class="speltekst" aria-live="polite"></span></div>`);
    slider = api.filterlinje.lagArSlider(ramme.el.querySelector(".verda-ar"), { id: "verda" });
    ramme.el.querySelector(".spel").addEventListener("click", () => (spel ? stoppSpel() : startSpel()));
    scene.storleik();
    if (S.verda.z) scene.settZ(S.verda.z);
    lastLand();
  },
  oppdater(s, e) {
    if (e.filter && spel && !eigaEndring) stoppSpel();
    eigaEndring = false;
    rekn();
    if (e.popstate || e.vis) scene.settZ(S.verda.z);
    slider.oppdater();
    teiknLinje();
    scene.teikn();
  },
  merk(i) { merkStader = new Set(i != null ? D.verkStader[i] : []); scene.teiknOverlay(); },
  sentrer(i) { const p = D.verkStader[i][0]; if (p != null) scene.sentrer(P.x[p], P.y[p], dekt()); },
  panTil(i) { const p = D.verkStader[i][0]; if (p != null) scene.panTilOmUte(P.x[p], P.y[p]); },
  vis() { scene.storleik(); },
  skjul() { stoppSpel(); tooltip.skjul(); },
  stoppSpel() { return stoppSpel(); },
  fokusUt() { return scene.fokusUt(); },
  scene: () => scene,
  etikettar: () => etikettar,
};

function dekt() {
  const ark = document.getElementById("listepanel").getBoundingClientRect();
  const r = ramme.flate.getBoundingClientRect();
  return Math.max(0, r.bottom - ark.top);
}

async function lastLand() {
  const [r, tj] = await Promise.all([A.data.verdsAtlas(), A.data.lastSkript("topojson")]);
  if (!r.ok || !tj.ok || !window.topojson) { landFeil = true; if (sVal) teiknLinje(); scene.teikn(); return; }
  const topo = r.data;
  const fc = window.topojson.feature(topo, topo.objects.countries);
  const sti = d3.geoPath(proj);
  const alle = [], nord = [];
  for (const f of fc.features) (f.id != null && NORDISK_ID.has(String(f.id)) ? nord : alle).push(f);
  land = new Path2D(sti({ type: "FeatureCollection", features: alle }) || "");
  landNordisk = new Path2D(sti({ type: "FeatureCollection", features: nord }) || "");
  scene.teikn();
}

function lagStader() {
  const st = D.stader.stader, N = st.length;
  const x = new Float32Array(N), y = new Float32Array(N);
  st.forEach((s, p) => { const q = proj([s.lon, s.lat]); x[p] = q[0]; y[p] = q[1]; });
  const n = st.map((s) => s.n);
  smax = Math.max(1, ...n);
  // whole-corpus arc maximum (stable widths, rule 1.6.1)
  const w = new Map();
  for (let i = 0; i < D.n; i++) parVerk(D.verkStader[i], w);
  wmax = Math.max(1, ...w.values());
  const qt = A.lagIndeks(N, (p) => x[p], (p) => y[p]);
  const storst = Array.from({ length: N }, (_, p) => p).sort((a, b) => n[b] - n[a] || a - b);
  const instAv = Array.from({ length: N }, () => []);
  D.stader.inst_stad.forEach((p, j) => { if (p >= 0) instAv[p].push(j); });
  P = { N, x, y, n, st, qt, storst, instAv };
}
function parVerk(l, m) {
  for (let a = 0; a < l.length; a++) for (let b = a + 1; b < l.length; b++) {
    const p = Math.min(l[a], l[b]), q = Math.max(l[a], l[b]);
    const k = p * 100000 + q;
    m.set(k, (m.get(k) || 0) + 1);
  }
}

function rekn() {
  sVal = new Int32Array(P.N);
  const w = new Map();
  let med = 0;
  for (let i = 0; i < D.n; i++) {
    if (!T.utval[i]) continue;
    const l = D.verkStader[i];
    if (l.length) med++;
    for (const p of l) sVal[p]++;
    parVerk(l, w);
  }
  P.med = med;
  const alle = [...w.entries()].map(([k, v]) => ({ a: Math.floor(k / 100000), b: k % 100000, w: v }));
  alle.sort((u, v) => v.w - u.w || u.a - v.a || u.b - v.b);
  bogarTotalt = alle.length;
  const cx = VW / 2, cy = VW / 2;
  bogar = alle.slice(0, 600).map((o) => {
    const x1 = P.x[o.a], y1 = P.y[o.a], x2 = P.x[o.b], y2 = P.y[o.b];
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1;
    let nx = -dy / L, ny = dx / L;
    if ((mx + nx - cx) ** 2 + (my + ny - cy) ** 2 < (mx - nx - cx) ** 2 + (my - ny - cy) ** 2) { nx = -nx; ny = -ny; }
    const qx = mx + nx * 0.18 * L, qy = my + ny * 0.18 * L;
    const lang = L <= VW * 0.35 ? 1 : Math.max(0.35, 1 - (L - VW * 0.35) / (VW * 0.9));
    return { ...o, x1, y1, x2, y2, qx, qy, lang, x0: Math.min(x1, x2, qx), x3: Math.max(x1, x2, qx), y0: Math.min(y1, y2, qy), y3: Math.max(y1, y2, qy) };
  });
  bogar.reverse(); // weakest first, strongest drawn on top
}

const radius = (p, s, sc) => (3 + 22 * Math.sqrt(s / smax)) * sc.rf * Math.pow(Math.max(sc.k, 0.05), 0.35);

// ---------- drawing ----------
function teiknBase(ctx, sc) {
  sc.setVerd(ctx);
  if (land) {
    // land a step above black and coasts visible on an ordinary screen; the Nordic countries lighter
    ctx.fillStyle = "#1d1d1d"; ctx.fill(land);
    ctx.fillStyle = "#2b2b2b"; ctx.fill(landNordisk);
    ctx.strokeStyle = "#4a4a4a"; ctx.lineWidth = 0.7 / sc.K;
    ctx.stroke(land);
    ctx.strokeStyle = "#5e5e5e"; ctx.stroke(landNordisk);
  }
  if (!P || !sVal) return;
  const hovStad = typeof sc.hoverId === "number" ? sc.hoverId : null;
  // arcs
  for (const b of bogar) {
    const r = b.w / wmax;
    // weak arcs are faint and long arcs (out of the Nordic frame) fainter still, so the strong
    // links read first instead of a white tangle
    let alfa = (0.05 + 0.6 * r ** 0.7) * b.lang, bw = 0.6 + 5 * r ** 0.8;
    const aktiv = (hovStad != null && (b.a === hovStad || b.b === hovStad)) || hoverBoge === b;
    if (aktiv) { alfa = 0.9; bw += 1.5; } else if (hovStad != null || hoverBoge) alfa = 0.04;
    ctx.globalAlpha = alfa;
    ctx.strokeStyle = "#f2f2f2";
    ctx.lineWidth = bw / sc.K;
    ctx.beginPath(); ctx.moveTo(b.x1, b.y1); ctx.quadraticCurveTo(b.qx, b.qy, b.x2, b.y2); ctx.stroke();
  }
  ctx.globalAlpha = 1;
  // bubbles: ghost rings, then fills by s descending (small on top)
  const ord = Array.from({ length: P.N }, (_, p) => p).sort((a, b) => sVal[b] - sVal[a] || P.n[b] - P.n[a] || a - b);
  ctx.strokeStyle = FADE; ctx.globalAlpha = 0.6; ctx.lineWidth = 1 / sc.K;
  ctx.beginPath();
  for (const p of ord) { const r = radius(p, P.n[p], sc) / sc.K; ctx.moveTo(P.x[p] + r, P.y[p]); ctx.arc(P.x[p], P.y[p], r, 0, 6.2832); }
  ctx.stroke();
  for (const p of ord) {
    if (!sVal[p]) continue;
    ctx.globalAlpha = hovStad != null && hovStad !== p ? 0.5 : 0.85;
    ctx.fillStyle = landFarge(P.st[p].land);
    const r = radius(p, sVal[p], sc) / sc.K;
    ctx.beginPath(); ctx.arc(P.x[p], P.y[p], r, 0, 6.2832); ctx.fill();
  }
  ctx.globalAlpha = 1;
}
function ring(ctx, sc, p, e, w = 1.5) {
  const [px, py] = sc.tilSkjerm(P.x[p], P.y[p]);
  ctx.beginPath(); ctx.arc(px, py, radius(p, Math.max(sVal[p], 1), sc) + e, 0, 6.2832);
  ctx.strokeStyle = "#000"; ctx.lineWidth = w + 2; ctx.stroke();
  ctx.strokeStyle = "#fff"; ctx.lineWidth = w; ctx.stroke();
}
function teiknOverlay(ctx, sc) {
  if (!P || !sVal) return;
  sc.setSkjerm(ctx);
  for (const k of S.f.stad) { const p = D.stadIdx.get(k); if (p != null) ring(ctx, sc, p, 2, 2); }
  if (S.f.par) for (const k of S.f.par) { const p = D.stadIdx.get(k); if (p != null) ring(ctx, sc, p, 2, 2); }
  for (const p of merkStader) ring(ctx, sc, p, 3);
  const vi = S.verk ? D.idx.get(S.verk) : null;
  if (vi != null) for (const p of D.verkStader[vi]) ring(ctx, sc, p, 5, 1.5);
  if (typeof sc.hoverId === "number") ring(ctx, sc, sc.hoverId, 2);
  if (typeof sc.fokusId === "number") ring(ctx, sc, sc.fokusId, 4);
  const inne = P.storst.filter((p) => sVal[p] > 0 && sc.synleg(P.x[p], P.y[p], 30)).sort((a, b) => sVal[b] - sVal[a] || a - b);
  const hind = inne.slice(0, 200).map((p, j) => { const [px, py] = sc.tilSkjerm(P.x[p], P.y[p]); return { id: p, x: px, y: py, r: radius(p, sVal[p], sc), rang: j }; });
  // at deep zoom a bubble can be wider than the gap to its neighbour: a label may then sit on
  // its own bubble (centred), so the places in view keep their names
  const djup = sc.k >= 3;
  const kand = inne.slice(0, 40).map((p, j) => { const [px, py] = sc.tilSkjerm(P.x[p], P.y[p]); return { id: p, x: px, y: py, r: radius(p, sVal[p], sc), tekst: T.stadNamn(P.st[p].k), font: "12px Literata, Georgia, serif", h: 15, rang: j, sentrert: djup }; });
  etikettar = plasserEtikettar(kand, { w: sc.w, h: sc.h, hindringar: djup ? [] : hind, blokk: sc.dekkaNo(), forrige: forrigePlass, maks: Math.min(40, Math.round(20 * Math.max(1, sc.k ** 0.5))) });
  forrigePlass = new Map(etikettar.map((q) => [q.id, q.pos]));
  teiknEtikettar(ctx, etikettar);
}

// ---------- picking (amendment 42) ----------
function finn(px, py, type) {
  if (!P || !sVal) return null;
  const sc = scene.sc;
  const [x, y] = sc.tilVerd(px, py);
  const touch = type !== "mouse";
  // search as far as the largest bubble can reach at this zoom
  const rMaks = radius(0, smax, sc) + 24;
  const kand = A.innanfor(P.qt, x, y, rMaks / sc.K, (p) => P.x[p], (p) => P.y[p]);
  const treff = [];
  for (const p of kand) {
    const r = radius(p, Math.max(sVal[p], 1), sc), d = Math.hypot(P.x[p] - x, P.y[p] - y) * sc.K;
    if (d <= (touch ? Math.max(r, 22) : Math.max(r, 6))) treff.push({ p, d, r, inne: d <= r, lys: sVal[p] > 0 });
  }
  if (treff.length) {
    treff.sort((a, b) => (b.lys - a.lys) || (b.inne - a.inne) || (a.inne && b.inne ? a.r - b.r : a.d - b.d));
    return { id: treff[0].p, type: "stad", p: treff[0].p, fleire: treff.length - 1 };
  }
  const grense = (touch ? 12 : 6) / sc.K;
  let best = null;
  for (const b of bogar) {
    if (x < b.x0 - grense || x > b.x3 + grense || y < b.y0 - grense || y > b.y3 + grense) continue;
    let dmin = Infinity;
    for (let t = 0; t <= 1; t += 0.05) {
      const u = 1 - t;
      const bx = u * u * b.x1 + 2 * u * t * b.qx + t * t * b.x2, by = u * u * b.y1 + 2 * u * t * b.qy + t * t * b.y2;
      dmin = Math.min(dmin, Math.hypot(bx - x, by - y));
    }
    if (dmin <= grense && (!best || dmin < best.d - 1e-9 || (Math.abs(dmin - best.d) < 1e-9 && b.w > best.b.w))) best = { b, d: dmin };
  }
  if (best) return { id: `b${best.b.a}-${best.b.b}`, type: "boge", b: best.b };
  return null;
}
function stadHtml(p, fleire) {
  const s = P.st[p];
  const tel = new Map();
  const inst = new Set(P.instAv[p]);
  for (let i = 0; i < D.n; i++) if (T.utval[i]) for (const j of D.kol.inst[i]) if (inst.has(j)) tel.set(j, (tel.get(j) || 0) + 1);
  const topp = [...tel.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, 3);
  return `<div class="tt-tittel">${esc(T.stadNamn(s.k))}, ${esc(T.landNamn(s.land))}</div>
    <div class="tt-meta">${fmt(sVal[p])} verk i utvalet (av ${fmt(s.n)})</div>
    ${topp.map(([j, c]) => `<div class="tt-meta">${esc(kutt(D.verk.institusjonar[j].namn, 40))}: ${fmt(c)}</div>`).join("")}
    ${fleire ? `<div class="tt-fot">+${fmt(fleire)} til her</div>` : ""}`;
}
function bogeHtml(b) {
  return `<div class="tt-tittel">${esc(T.stadNamn(P.st[b.a].k))} og ${esc(T.stadNamn(P.st[b.b].k))}</div><div class="tt-meta">${fmt(b.w)} felles verk</div>`;
}
function tips(h) {
  if (h.type === "stad") return stadHtml(h.p, h.fleire) + `<div class="tt-fot">Klikk: vel · Skift-klikk: legg til</div>`;
  return bogeHtml(h.b) + `<div class="tt-fot">Klikk: vel verka med forfattarar begge stader</div>`;
}
function handling(h, leggTil) {
  if (h.type === "stad") T.veksle("stad", P.st[h.p].k, { erstatt: !leggTil });
  else T.endre((s) => { s.f.par = [P.st[h.b.a].k, P.st[h.b.b].k]; });
}
const klikk = (h, ev) => handling(h, ev.shiftKey || ev.ctrlKey || ev.metaKey);
function kortFor(h) {
  if (h.type === "stad") return { html: stadHtml(h.p, h.fleire), knappar: [{ tekst: "Vel", primar: true, gjer: () => handling(h, false) }, { tekst: "Legg til", gjer: () => handling(h, true) }] };
  return { html: bogeHtml(h.b), knappar: [{ tekst: "Vis verka", primar: true, gjer: () => handling(h, false) }] };
}

// ---------- play ----------
function startSpel() {
  if (spel) return;
  const knapp = ramme.el.querySelector(".spel");
  knapp.textContent = "Stopp"; knapp.setAttribute("aria-pressed", "true");
  spel = { ar: 1995 };
  const steg = () => {
    if (!spel) return;
    const a = spel.ar;
    eigaEndring = true;
    T.endre((s) => { s.f.ar = [a, a + 4]; }, { hist: "kont:spel" });
    ramme.el.querySelector(".speltekst").textContent = `${a} til ${a + 4}`;
    spel.ar++;
    if (spel.ar > 2021) { spel.tid = setTimeout(() => stoppSpel(), 800); return; }
    spel.tid = setTimeout(steg, 800);
  };
  steg();
}
function stoppSpel() {
  if (!spel) return false;
  clearTimeout(spel.tid);
  spel = null;
  T.avsluttGest("spel");
  const knapp = ramme.el.querySelector(".spel");
  knapp.textContent = "Spel av"; knapp.setAttribute("aria-pressed", "false");
  ramme.el.querySelector(".speltekst").textContent = "";
  return true;
}

// ---------- line and legend ----------
function teiknLinje() {
  let t = `Stader der forfattarane høyrer til (byen til institusjonen). Boble = verk, og eit verk kan stå i fleire bobler. Boge = felles verk mellom to stader. Berre OpenAlex: ${fmt(P.med || 0)} av ${fmt(T.valt)} verk i utvalet har stad.`;
  if (bogarTotalt > bogar.length) t += ` Viser ${fmt(bogar.length)} av ${fmt(bogarTotalt)} bogar.`;
  if (landFeil) t += " Landkartet kunne ikkje lastast; stadene er rett plasserte.";
  ramme.linje.textContent = t;
  scene.settLabel(t);
  const ref = [Math.round(smax), Math.round(smax / 4), Math.max(1, Math.round(smax / 20))];
  const sirklar = ref.map((v) => { const r = (3 + 22 * Math.sqrt(v / smax)) * (scene ? scene.sc.rf : 1); return `<span class="teikn-post"><svg width="${2 * r + 2}" height="${2 * r + 2}" aria-hidden="true"><circle cx="${r + 1}" cy="${r + 1}" r="${r}" fill="none" stroke="#bbb"/></svg>${fmt(v)}</span>`; }).join("");
  const bw = [wmax, Math.round(wmax / 3), 1].map((v) => `<span class="teikn-post"><svg width="24" height="10" aria-hidden="true"><line x1="0" y1="5" x2="24" y2="5" stroke="#f2f2f2" stroke-width="${0.6 + 5 * (v / wmax) ** 0.8}"/></svg>${fmt(v)}</span>`).join("");
  const land = ["NO", "SE", "DK", "FI", "IS", "GB", "US", "NL"].map((k) => `<span class="teikn-post"><span class="prikk" style="background:${landFarge(k)}"></span>${esc(T.landNamn(k))}</span>`).join("");
  // short legend: sizes on two lines, the colours in two columns, so it covers little of the map
  settInnhald(ramme.teikn, `<span class="teikn-linje"><span class="teikn-merk">Verk</span>${sirklar}</span><span class="teikn-linje"><span class="teikn-merk">Felles verk</span>${bw}</span><span class="teikn-kol">${land}<span class="teikn-post"><span class="prikk" style="background:#9a9a9a"></span>Andre</span></span><span class="teikn-merk">Grå ring: heile korpuset. Nabobyar er eigne stader (København og Lyngby, Espoo og Helsinki), så nokre bogar går mellom campusar i same byområde.</span>`);
  if (T.harFilter() && T.valt > 0 && !P.med) A.hjelp.visMelding(ramme, { tekst: "Ingen av verka i utvalet har stad i dataa." });
  else if (ramme.melding.textContent.startsWith("Ingen av verka")) A.hjelp.visMelding(ramme, null);
}
void rorsle;
