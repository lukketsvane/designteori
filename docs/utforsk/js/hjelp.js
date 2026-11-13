// Shared helpers: escaping, numbers, folding, palettes, tooltip and card,
// label placer, motion flag, catalogue link.

export const KATALOG_LENKE = (id) => `../#verk/${encodeURIComponent(id)}`;

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ESC[c]);

// Thousands with a no-break space, decimal comma (nn-NO), independent of the browser's locale data.
export const fmt = (x) => {
  const n = Math.round(Number(x) || 0);
  const s = String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return (n < 0 ? "−" : "") + s;
};
export const pst = (x, d = 0) => (Number.isFinite(x) ? x.toFixed(d).replace(".", ",") : "–");

const FOLDMAP = { "ø": "o", "æ": "ae", "ß": "ss", "ð": "d", "þ": "th", "ł": "l", "đ": "d", "œ": "oe" };
const FOLDRE = /[øæßðþłđœ]/g;
export function fold(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(FOLDRE, (c) => FOLDMAP[c])
    .replace(/\s+/g, " ")
    .trim();
}

// Term key, the same function as the builder (5.8, amendment 49).
// as Python's \w: letters, numbers and _, no combining marks (lowercase İ leaves one)
const TOKRE = /[\p{L}\p{N}_][\p{L}\p{N}_'’-]*[\p{L}\p{N}_]|[\p{L}\p{N}_]/gu;
export function termNokkel(s) {
  const t = String(s || "").normalize("NFC").toLowerCase();
  const toks = t.match(TOKRE) || [];
  return toks.map((x) => x.replace(/[-'’]/g, "")).filter(Boolean).join(" ");
}

export const kutt = (s, n) => {
  s = String(s || "");
  return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
};
// Archive names come as "Etternamn, Fornamn", OpenAlex names as "Fornamn Etternamn". In a list
// of authors joined with commas "Dindler, Christian" reads as two people, so names are shown
// as "Fornamn Etternamn" (display only; keys and search keep the stored form).
export function visNamn(s) {
  const t = String(s || "").trim();
  const m = /^([^,]+),\s*([^,]+)$/.exec(t);
  if (!m) return t;
  const etter = m[1].trim(), fore = m[2].trim();
  // "Smith, Jr." and initials-only suffixes are not given names
  if (/^(jr|sr|ii|iii|iv)\.?$/i.test(fore)) return t;
  return `${fore} ${etter}`;
}

// ---------- colour ----------
// The page follows the colour scheme of the device (reloads when it changes; the state sits in the address).
export const MORK = (() => {
  try {
    const t = document.documentElement.dataset.theme;
    if (t === "dark") return true;
    if (t === "light") return false;
    return matchMedia("(prefers-color-scheme: dark)").matches;
  } catch (e) { return false; }
})();
try { matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => location.reload()); } catch (e) { /* old browser: no live switch */ }
// Darkens a pastel until it has contrast with white (the palettes below were drawn for a black page).
function paHvit(h, mal = 3.2) {
  const [r, g, b] = hexRgb(h);
  let f = 1, hex = h;
  while (kontrast(hex, "#ffffff") < mal && f > 0.25) {
    f -= 0.03;
    hex = "#" + [r, g, b].map((c) => Math.round(c * f).toString(16).padStart(2, "0")).join("");
  }
  return hex;
}
const modus = (h) => (MORK ? h : paHvit(h));
const kartPal = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, modus(v)]));
// The eight clusters have the colours of the Kart tab on the main page (kart.js PAL, slot per cluster).
const KLYNGE_FARGE = {
  lys: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
  mork: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
};
export const KLYNGE_PLASS = [5, 7, 4, 0, 6, 3, 1, 2];
export const PALETTE_TEMA = KLYNGE_PLASS.map((s) => KLYNGE_FARGE[MORK ? "mork" : "lys"][s]);
export const LAND_FARGE = kartPal({ DK: "#ff6b5e", SE: "#4da3ff", FI: "#5ee6c8", NO: "#ffd166", IS: "#f472b6", GB: "#c77dff", US: "#8fe388", NL: "#ff9f45" });
export const FLEIRE_LAND = MORK ? "#e8e8e8" : "#4a4a4a";
export const UKJEND = "#6b6b6b";
export const ANNA_LAND = MORK ? "#9a9a9a" : "#8a8a8a";
export const KGR_FARGE = kartPal({ tidsskrift: "#4da3ff", konferanse: "#ff9f45", hci: "#c77dff", bok: "#8fe388", repositorium: "#ffd166", anna: "#9fb3c8", ukjend: "#6b6b6b" });
// Second and third palettes (amendment 23): CIE76 >= 12 from every hex above.
export const PALETTE_GRUPPE = ["#e0e048", "#3dd6f5", "#ff4fa0", "#a0a0ff", "#7cff6b", "#ffb3c6", "#00e5a0", "#ffa07a", "#e45cff", "#d2b4ff"].map(modus);
export const PALETTE_ORD = ["#b5f23d", "#70f0ff", "#ff5c8a", "#ffd0a0", "#c8c8ff", "#ff7a3d"].map(modus);
export const ORD_MERKE = ["sirkel", "firkant", "trekant", "ruter", "kryss", "ring"];
export const ORD_STREK = ["", "6 3", "2 3", "8 3 2 3", "1 2", "10 4"];
export const FADE = "#808080";
export const FADE_ALFA = 0.35;
export const BG = MORK ? "#000000" : "#ffffff";
// Colours the canvas and the SVG drawings use for text, outlines and lines (the CSS has the same pairs as custom properties).
export const KL = MORK
  ? { tekst: "#f2f2f2", tekst2: "#e8e8e8", tekst3: "#d8d8d8", sterk: "#ffffff", dim: "#9a9a9a", halo: "rgba(0,0,0,0.9)", boks: "rgba(0,0,0,0.62)",
      kontur: "#000000", ring: "#ffffff", ring9: "rgba(255,255,255,0.9)", kant: "#dcdcdc", bar: "#cfcfcf", flate: "#141414", linjeNorm: "#555", linjeUte: "#333",
      lassoFyll: "rgba(255,255,255,0.1)", land: "#1d1d1d", landNordisk: "#2b2b2b", landKant: "#4a4a4a", landNordiskKant: "#5e5e5e", boge: "#f2f2f2", nokkelDim: "#8a8a8a", sirkel: "#bbb", gruppeAnna: "#d6d6d6" }
  : { tekst: "#111111", tekst2: "#1a1a1a", tekst3: "#333333", sterk: "#000000", dim: "#6b6b6b", halo: "rgba(255,255,255,0.92)", boks: "rgba(255,255,255,0.75)",
      kontur: "#ffffff", ring: "#000000", ring9: "rgba(0,0,0,0.9)", kant: "#8c8c8c", bar: "#555555", flate: "#f0f0f0", linjeNorm: "#b0b0b0", linjeUte: "#d0d0d0",
      lassoFyll: "rgba(0,0,0,0.08)", land: "#eeeeee", landNordisk: "#e0e0e0", landKant: "#c8c8c8", landNordiskKant: "#aaaaaa", boge: "#222222", nokkelDim: "#8a8a8a", sirkel: "#777", gruppeAnna: "#555555" };
// Label colour of a cluster: lightened on black, darkened on white.
export const klyngeTekst = (h) => (MORK ? lys(h, 0.3) : paHvit(h, 4.5));

export function landFarge(kode) {
  if (!kode) return UKJEND;
  return LAND_FARGE[kode] || ANNA_LAND;
}

export function hexRgb(h) {
  const x = parseInt(h.slice(1), 16);
  return [(x >> 16) & 255, (x >> 8) & 255, x & 255];
}
export function lys(h, t) {
  const [r, g, b] = hexRgb(h);
  const f = (c) => Math.round(c + (255 - c) * t);
  return `rgb(${f(r)},${f(g)},${f(b)})`;
}
function lab(h) {
  const [r0, g0, b0] = hexRgb(h).map((c) => c / 255);
  const f = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const r = f(r0), g = f(g0), b = f(b0);
  const X = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047;
  const Y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  const Z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883;
  const ff = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  const fx = ff(X), fy = ff(Y), fz = ff(Z);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}
export function cie76(a, b) {
  const A = lab(a), B = lab(b);
  return Math.hypot(A[0] - B[0], A[1] - B[1], A[2] - B[2]);
}
function lum(h) {
  const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const [r, g, b] = hexRgb(h);
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
export function kontrast(a, b) {
  const x = lum(a), y = lum(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
export function blandHex(fg, bg, alfa) {
  const A = hexRgb(fg), B = hexRgb(bg);
  return "#" + A.map((c, i) => Math.round(c * alfa + B[i] * (1 - alfa)).toString(16).padStart(2, "0")).join("");
}

// ---------- motion ----------
const mqRedusert = typeof matchMedia === "function" ? matchMedia("(prefers-reduced-motion: reduce)") : null;
export const rorsle = {
  overstyr: null,
  get redusert() { return this.overstyr != null ? this.overstyr : !!(mqRedusert && mqRedusert.matches); },
};
export const ease = (t) => 1 - (1 - t) ** 3;
// Runs fn(t) per frame for ms; instant under reduced motion. Returns a stop function.
export function tween(ms, fn, ferdig) {
  if (rorsle.redusert || ms <= 0) { fn(1); if (ferdig) ferdig(); return () => {}; }
  let stopp = false;
  const t0 = performance.now();
  const steg = (now) => {
    if (stopp) return;
    const t = Math.min(1, (now - t0) / ms);
    fn(ease(t));
    if (t < 1) requestAnimationFrame(steg); else if (ferdig) ferdig();
  };
  requestAnimationFrame(steg);
  return () => { stopp = true; };
}

export const smal = () => window.matchMedia("(max-width: 899px)").matches;
export const veldigSmal = () => window.matchMedia("(max-width: 599px)").matches;

// ---------- live regions ----------
let liveTid = 0;
export function annonser(tekst) {
  clearTimeout(liveTid);
  liveTid = setTimeout(() => { const el = document.getElementById("live"); if (el) el.textContent = tekst; }, 500);
}
export function annonserMerke(tekst) {
  const el = document.getElementById("live-merke");
  if (el) el.textContent = tekst;
}

// ---------- tooltip and pinned card ----------
const tipEl = () => document.getElementById("tooltip");
export const tooltip = {
  synleg: false,
  _html: null,
  _raf: 0,
  _pos: null,
  // The same content is only moved (no rebuild); moves are batched to one per frame.
  vis(html, cx, cy) {
    const el = tipEl();
    if (!el) return;
    if (html !== this._html || el.hidden) {
      el.innerHTML = html;
      this._html = html;
      el.hidden = false;
      this.synleg = true;
      this.flytt(cx, cy);
      return;
    }
    this._pos = [cx, cy];
    if (!this._raf) this._raf = requestAnimationFrame(() => { this._raf = 0; if (this._pos) this.flytt(this._pos[0], this._pos[1]); });
  },
  flytt(cx, cy) {
    const el = tipEl();
    if (!el || el.hidden) return;
    const W = window.innerWidth, H = window.innerHeight;
    const r = el.getBoundingClientRect();
    let x = cx + 14, y = cy + 14;
    if (x + r.width > W - 8) x = cx - 14 - r.width;
    if (y + r.height > H - 8) y = cy - 14 - r.height;
    x = Math.max(8, Math.min(x, W - r.width - 8));
    y = Math.max(8, Math.min(y, H - r.height - 8));
    el.style.transform = `translate(${Math.round(x)}px,${Math.round(y)}px)`;
  },
  skjul() {
    const el = tipEl();
    if (el && !el.hidden) { el.hidden = true; el.innerHTML = ""; }
    this.synleg = false;
    this._html = null;
    this._pos = null;
  },
};

// Pinned card: content plus action buttons. {id, html, knappar:[{tekst, gjer, primar}], x, y}
export const kort = {
  id: null,
  ope: false,
  _knappar: [],
  opne({ id, html, knappar = [], x, y }) {
    const el = document.getElementById("kort");
    if (!el) return;
    this.id = id;
    this.ope = true;
    this._knappar = knappar;
    el.innerHTML = `<button type="button" class="kort-lukk" data-kort="lukk" aria-label="Lukk kortet">×</button>
      <div class="kort-innhald">${html}</div>
      ${knappar.length ? `<div class="kort-knappar">${knappar.map((k, i) => `<button type="button" class="knapp${k.primar ? " primar" : ""}" data-kort="${i}">${esc(k.tekst)}</button>`).join("")}</div>` : ""}`;
    el.hidden = false;
    this.plasser(x, y);
    annonserMerke(el.textContent.replace(/\s+/g, " ").trim());
  },
  plasser(x, y) {
    const el = document.getElementById("kort");
    if (!el || el.hidden) return;
    const W = window.innerWidth, H = window.innerHeight;
    const r = el.getBoundingClientRect();
    let px, py;
    const ark = document.getElementById("listepanel");
    if (smal() && ark) {
      const topp = ark.getBoundingClientRect().top;
      px = Math.max(8, Math.min((W - r.width) / 2, W - r.width - 8));
      py = Math.max(8, topp - 8 - r.height);
    } else {
      px = x + 16; py = y - r.height / 2;
      if (px + r.width > W - 8) px = x - 16 - r.width;
      px = Math.max(8, Math.min(px, W - r.width - 8));
      py = Math.max(8, Math.min(py, H - r.height - 8));
    }
    el.style.transform = `translate(${Math.round(px)}px,${Math.round(py)}px)`;
  },
  lukk() {
    const el = document.getElementById("kort");
    if (el) { el.hidden = true; el.innerHTML = ""; }
    this.id = null;
    this.ope = false;
    this._knappar = [];
  },
  handling(i) {
    const k = this._knappar[i];
    if (k) { this.lukk(); k.gjer(); }
  },
};

// ---------- text measuring and labels ----------
const malCtx = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
const malCache = new Map();
// widths measured before the web font arrived are wrong: start over when fonts are ready
export const tomMalCache = () => malCache.clear();
export function tekstBreidd(tekst, font) {
  const k = font + "|" + tekst;
  let w = malCache.get(k);
  if (w == null) {
    malCtx.font = font;
    w = malCtx.measureText(tekst).width;
    if (malCache.size > 20000) malCache.clear();
    malCache.set(k, w);
  }
  return w;
}

// Label placer (2.0 + amendment 33). kandidatar: [{id, x, y, r, tekst, font, h, prio}] in screen px,
// sorted by priority. hindringar: [{x, y, r}] marks the labels must avoid. forrige: Map id -> pos.
// Returns [{id, x, y, w, h, tekst, font, align, pos}] where (x, y) is the text anchor (left or right, middle).
export function plasserEtikettar(kandidatar, { w, h, hindringar = [], blokk = [], forrige = null, maks = 80, pad = 3 } = {}) {
  const CELL = 64;
  const grid = new Map();
  const nokkel = (cx, cy) => cx * 100003 + cy;
  const leggTil = (b) => {
    const x0 = Math.floor(b.x0 / CELL), x1 = Math.floor(b.x1 / CELL), y0 = Math.floor(b.y0 / CELL), y1 = Math.floor(b.y1 / CELL);
    for (let cx = x0; cx <= x1; cx++) for (let cy = y0; cy <= y1; cy++) {
      const k = nokkel(cx, cy);
      let l = grid.get(k);
      if (!l) { l = []; grid.set(k, l); }
      l.push(b);
    }
  };
  const kolliderer = (b, egen, rang) => {
    const x0 = Math.floor(b.x0 / CELL), x1 = Math.floor(b.x1 / CELL), y0 = Math.floor(b.y0 / CELL), y1 = Math.floor(b.y1 / CELL);
    for (let cx = x0; cx <= x1; cx++) for (let cy = y0; cy <= y1; cy++) {
      const l = grid.get(nokkel(cx, cy));
      if (!l) continue;
      for (const o of l) if (!(o.hindring && (o.id === egen || (rang != null && o.rang != null && o.rang >= rang))) && b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0) return true;
    }
    return false;
  };
  for (const o of hindringar) {
    if (o.r <= 0) continue;
    leggTil({ x0: o.x - o.r, x1: o.x + o.r, y0: o.y - o.r, y1: o.y + o.r, hindring: true, id: o.id, rang: o.rang });
  }
  // boxes of controls floating over the drawing: no label goes under them
  for (const b of blokk) leggTil({ x0: b.x0, x1: b.x1, y0: b.y0, y1: b.y1, hindring: true, id: "\u0000blokk" });
  // sticky: previously placed candidates first
  let liste = kandidatar.slice(0, maks * 2);
  if (forrige && forrige.size) {
    const a = [], b = [];
    for (const k of liste) (forrige.has(k.id) ? a : b).push(k);
    liste = a.concat(b);
  }
  // a candidate marked forst (the open work) is always placed first
  const forst = liste.filter((k) => k.forst);
  if (forst.length) liste = forst.concat(liste.filter((k) => !k.forst));
  liste = liste.slice(0, maks);
  const ut = [];
  for (const k of liste) {
    const tw = tekstBreidd(k.tekst, k.font);
    const th = k.h || 14;
    const r = (k.r || 0) + 3;
    const val = [
      { pos: "h", x: k.x + r, y: k.y, align: "left" },
      { pos: "v", x: k.x - r, y: k.y, align: "right" },
      { pos: "o", x: k.x - tw / 2, y: k.y - r - th / 2, align: "left" },
      { pos: "u", x: k.x - tw / 2, y: k.y + r + th / 2, align: "left" },
    ];
    if (k.sentrert) {
      const ekstra = [0, th + 4, -(th + 4), 2 * (th + 4), -2 * (th + 4)].map((dy, j) => ({ pos: `s${j}`, x: k.x - tw / 2, y: k.y + dy, align: "left" }));
      val.unshift(...ekstra);
    }
    const fp = forrige && forrige.get(k.id);
    if (fp) { const i = val.findIndex((v) => v.pos === fp); if (i > 0) val.unshift(val.splice(i, 1)[0]); }
    for (const v of val) {
      const x0 = v.align === "left" ? v.x : v.x - tw;
      const b = { x0: x0 - pad, x1: x0 + tw + pad, y0: v.y - th / 2 - pad, y1: v.y + th / 2 + pad };
      if (b.x0 < 0 || b.x1 > w || b.y0 < 0 || b.y1 > h) continue;
      if (kolliderer(b, k.id, k.rang)) continue;
      leggTil(b);
      ut.push({ id: k.id, x: v.x, y: v.y, w: tw, h: th, tekst: k.tekst, font: k.font, align: v.align, pos: v.pos, farge: k.farge, boks: b, data: k.data, bakgrunn: !!k.sentrert || !!k.forst });
      break;
    }
  }
  return ut;
}

export function teiknEtikettar(ctx, plasserte, { farge = KL.tekst, alfa = 1 } = {}) {
  ctx.save();
  ctx.globalAlpha = alfa;
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";
  ctx.lineWidth = 4;
  ctx.strokeStyle = KL.halo;
  for (const p of plasserte) {
    ctx.font = p.font;
    ctx.textAlign = p.align;
    // labels set over the middle of a dense area (theme names) get a dark backing
    if (p.bakgrunn) {
      const x0 = p.align === "left" ? p.x : p.x - p.w;
      ctx.fillStyle = KL.boks;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(x0 - 5, p.y - p.h / 2 - 1, p.w + 10, p.h + 2, 4); else ctx.rect(x0 - 5, p.y - p.h / 2 - 1, p.w + 10, p.h + 2);
      ctx.fill();
    }
    ctx.strokeText(p.tekst, p.x, p.y);
    ctx.fillStyle = p.farge || farge;
    ctx.fillText(p.tekst, p.x, p.y);
  }
  ctx.restore();
}

export function overlappPar(plasserte) {
  let n = 0;
  for (let i = 0; i < plasserte.length; i++) for (let j = i + 1; j < plasserte.length; j++) {
    const a = plasserte[i].boks, b = plasserte[j].boks;
    // boxes include padding; overlap means the text boxes touch
    if (a.x0 + 3 < b.x1 - 3 && a.x1 - 3 > b.x0 + 3 && a.y0 + 3 < b.y1 - 3 && a.y1 - 3 > b.y0 + 3) n++;
  }
  return n;
}

// Vertical placer for line ends (Tid): items [{y, h}] sorted; returns new y's at least gap apart within [y0, y1].
export function plasserVertikalt(items, gap, y0, y1) {
  const s = items.map((it, i) => ({ i, y: it.y })).sort((a, b) => a.y - b.y);
  for (let k = 1; k < s.length; k++) if (s[k].y < s[k - 1].y + gap) s[k].y = s[k - 1].y + gap;
  const over = s.length ? s[s.length - 1].y - y1 : 0;
  if (over > 0) {
    s[s.length - 1].y = y1;
    for (let k = s.length - 2; k >= 0; k--) if (s[k].y > s[k + 1].y - gap) s[k].y = s[k + 1].y - gap;
  }
  if (s.length && s[0].y < y0) return null;
  const ut = new Array(items.length);
  for (const x of s) ut[x.i] = x.y;
  return ut;
}

// A small frame in a view element: header strip (line, legend, controls), progress, area, message.
export function lagRamme(el, { kontrollTekst } = {}) {
  el.innerHTML = `
    <div class="vis-topp">
      <div class="vis-tekst">
        <p class="forklaring" aria-live="off"></p>
        <div class="teikn-wrap">
          <button type="button" class="knapp liten teikn-knapp" aria-expanded="false">Forklaring</button>
          <div class="forklaring-teikn"></div>
        </div>
      </div>
      <div class="viskontroll" role="toolbar" aria-label="${esc(kontrollTekst || "Val for visinga")}"></div>
    </div>
    <div class="framdrift" hidden><span></span></div>
    <div class="teikneflate"></div>
    <div class="vis-melding" hidden></div>`;
  const r = {
    el,
    linje: el.querySelector(".forklaring"),
    teikn: el.querySelector(".forklaring-teikn"),
    teiknKnapp: el.querySelector(".teikn-knapp"),
    kontroll: el.querySelector(".viskontroll"),
    flate: el.querySelector(".teikneflate"),
    framdrift: el.querySelector(".framdrift"),
    melding: el.querySelector(".vis-melding"),
  };
  const wrap = el.querySelector(".teikn-wrap"), heim = el.querySelector(".vis-tekst");
  // On wide screens the legend of a canvas view floats over the drawing area, so the
  // drawing gets the height; below 900 px it sits under the line behind "Forklaring".
  let flyt = false, flytOpe = null, flytMal = null;
  let kjend = false; // a reader who has used the page before starts with the legend folded
  try { const v = localStorage.getItem("utforsk.forklaring"); if (v) flytOpe = v !== "lukka"; kjend = !!localStorage.getItem("utforsk.brukt"); } catch (e) { /* storage blocked */ }
  if (flytOpe == null && kjend) flytOpe = false;
  const bruk = () => {
    const f = flyt && !smal();
    const mal = flytMal || r.flate;
    // open by default only where the legend leaves room for the drawing
    if (f && flytOpe == null) flytOpe = (mal.clientWidth || window.innerWidth - 400) >= 1000;
    if (f && wrap.parentElement !== mal) mal.appendChild(wrap);
    if (!f && wrap.parentElement !== heim) heim.appendChild(wrap);
    el.classList.toggle("teikn-flyt", f);
    const ope = f ? flytOpe : el.classList.contains("teikn-ope");
    el.classList.toggle("teikn-lukka", f && !flytOpe);
    r.teiknKnapp.setAttribute("aria-expanded", String(ope));
    r.teiknKnapp.textContent = f ? (ope ? "Gøym forklaringa" : "Forklaring") : "Forklaring";
    mal.dispatchEvent(new CustomEvent("utforsk:teikn"));
  };
  r.settTeiknFlyt = (v, m) => { flyt = !!v; if (m) flytMal = m; bruk(); };
  if (typeof matchMedia === "function") matchMedia("(max-width: 899px)").addEventListener("change", bruk);
  r.teiknKnapp.addEventListener("click", () => {
    if (flyt && !smal()) {
      flytOpe = !flytOpe;
      try { localStorage.setItem("utforsk.forklaring", flytOpe ? "ope" : "lukka"); } catch (e) { /* storage blocked */ }
      bruk();
      return;
    }
    const ope = r.teiknKnapp.getAttribute("aria-expanded") !== "true";
    r.teiknKnapp.setAttribute("aria-expanded", String(ope));
    el.classList.toggle("teikn-ope", ope);
  });
  return r;
}

// Rebuild a box (innerHTML) without losing keyboard focus: the focused control, or the one
// with the same data attributes after the rebuild, or its nearest neighbour, gets focus back.
const FOKUSERBAR = "button, a[href], input, select, [tabindex]";
export function bevarFokus(boks, fn) {
  const a = document.activeElement;
  let key = null;
  if (a && a !== boks && boks.contains(a)) {
    key = { tag: a.tagName, data: { ...a.dataset }, verdi: a.tagName === "INPUT" && a.type === "checkbox" ? a.value : null, cls: a.className, idx: [...boks.querySelectorAll(FOKUSERBAR)].indexOf(a) };
    if (a.tagName === "INPUT" && a.type !== "checkbox") { key.tekst = a.value; key.sel = [a.selectionStart, a.selectionEnd]; }
  }
  fn();
  if (!key || boks.contains(document.activeElement)) return;
  const alle = [...boks.querySelectorAll(FOKUSERBAR)].filter((e) => !e.hidden && e.tabIndex >= 0);
  const dk = Object.entries(key.data);
  const lik = alle.find((e) => e.tagName === key.tag && (dk.length || key.verdi != null || key.tekst != null)
    && dk.every(([k, v]) => e.dataset[k] === v)
    && (key.verdi == null || e.value === key.verdi)
    && (key.tekst == null || e.className === key.cls));
  const m = lik || alle[Math.max(0, Math.min(key.idx, alle.length - 1))];
  if (m) {
    m.focus({ preventScroll: true });
    if (key.tekst != null && m === lik) { try { m.setSelectionRange(key.sel[0], key.sel[1]); } catch (e) { /* not a text field */ } }
  } else { if (!boks.hasAttribute("tabindex")) boks.setAttribute("tabindex", "-1"); boks.focus({ preventScroll: true }); }
}
// Replace a box's content only when it changed, keeping keyboard focus (amendment: focus is
// never dropped to the body when a control rebuilds its own box).
export function settInnhald(boks, html) {
  if (!boks) return;
  if (boks._html === html) return;
  boks._html = html;
  bevarFokus(boks, () => { boks.innerHTML = html; });
}

// Message overlay in a frame: {tittel, tekst, knapp: {tekst, gjer}}; null clears.
export function visMelding(ramme, m) {
  const el = ramme.melding;
  if (!m) { el.hidden = true; el.innerHTML = ""; return; }
  el.hidden = false;
  el.innerHTML = `<div class="melding-boks">${m.tittel ? `<p class="melding-tittel">${esc(m.tittel)}</p>` : ""}${m.tekst ? `<p>${esc(m.tekst)}</p>` : ""}${m.knapp ? `<button type="button" class="knapp">${esc(m.knapp.tekst)}</button>` : ""}</div>`;
  if (m.knapp) el.querySelector("button").addEventListener("click", m.knapp.gjer);
}

export function framdrift(ramme, del) {
  const el = ramme.framdrift;
  if (del == null || del >= 1) { el.hidden = true; return; }
  el.hidden = false;
  el.firstElementChild.style.width = `${Math.round(del * 100)}%`;
}

export function segmentert(container, { namn, val, verdi, ved }) {
  container.insertAdjacentHTML("beforeend", `<div class="segment" role="radiogroup" aria-label="${esc(namn)}">${val.map((v) => `<button type="button" role="radio" class="seg" data-v="${esc(v.k)}" aria-checked="${v.k === verdi}">${esc(v.namn)}</button>`).join("")}</div>`);
  const g = container.lastElementChild;
  g.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-v]");
    if (b) ved(b.dataset.v);
  });
  g.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    const bs = [...g.querySelectorAll("button")];
    const i = bs.indexOf(document.activeElement);
    if (i < 0) return;
    const j = (i + (e.key === "ArrowRight" ? 1 : bs.length - 1)) % bs.length;
    bs[j].focus();
    e.preventDefault();
  });
  return {
    el: g,
    set(v) { for (const b of g.querySelectorAll("button")) b.setAttribute("aria-checked", String(b.dataset.v === v)); },
  };
}
