/* KART - semantisk kart over korpuset: klynger, underklynger, søk i titlar og fargeval.
   Tek over #view-kart når skriptet er lasta etter app.js. Det gamle kartet blir gøymt, ikkje fjerna.
   Klassisk skript (UMD-hale): window.DTKart i nettlesaren, module.exports i node (reine funksjonar). */
(function () {
  "use strict";

  /* ---------- reine hjelparar (testa i tests/js/kart.test.mjs) ---------- */
  const FOLD_MAP = { "æ": "ae", "ø": "o", "ð": "d", "þ": "th", "ß": "ss", "đ": "d", "ł": "l", "œ": "oe" };
  const MODES = ["klynge", "ar", "land", "kanal"];
  const MODE_LABEL = { klynge: "klynge", ar: "år", land: "land", kanal: "kanal" };

  /* Kategorisk palett: åtte fargar, validerte for lys og mørk flate (fargeblinde naboar ΔE ≥ 8). */
  const PAL = {
    light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  };
  /* Klynge -> fargeplass, vald slik at klynger som grensar mest mot kvarandre i kartet får fargar som skil seg best. */
  const SLOT8 = [5, 7, 4, 0, 6, 3, 1, 2];
  /* Sekvensiell blå for år: eldst lys, nyast mørk (lys modus); omvendt i mørk modus. */
  const SEQ = {
    light: ["#86b6ef", "#5598e7", "#3987e5", "#2a78d6", "#1c5cab", "#184f95", "#0d366b"],
    dark: ["#184f95", "#1c5cab", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"],
  };
  const COUNTRIES = [["NO", "Noreg"], ["DK", "Danmark"], ["SE", "Sverige"], ["FI", "Finland"], ["IS", "Island"]];
  const COUNTRY_SLOTS = [0, 1, 2, 3, 4, 6];
  const VENUES = [
    ["Nordes", /nordic design research|\bnordes\b/i],
    ["DRS", /\bdrs\b|design research society/i],
    ["FormAkademisk", /formakademisk/i],
    ["HCI-konferansar", /designing interactive systems|human factors in computing|\bchi\b|nordichi|human-computer interaction/i],
    ["PDC", /participatory design conference/i],
    ["Designtidsskrift", /^design studies|design issues|the design journal|^codesign|journal of design research|j of design research|she ji|international journal of design|^artifact|journal of design history|design and culture/i],
    ["ServDes", /servdes|service design and innovation/i],
  ];

  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  const fmt = (n) => {
    if (typeof n !== "number" || !isFinite(n)) return "";
    const [i, d] = String(Math.abs(n)).split(".");
    return (n < 0 ? "−" : "") + i.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (d ? "," + d : "");
  };
  const pct = (x) => Math.round(x * 100) + " %";

  function fold(s) {
    let o = "";
    for (const ch of String(s == null ? "" : s).toLowerCase()) o += Object.prototype.hasOwnProperty.call(FOLD_MAP, ch) ? FOLD_MAP[ch] : ch;
    return o.normalize("NFKD").replace(/[̀-ͯ]/g, "");
  }
  function queryTokens(q) { return fold(q).split(/[^\p{L}\p{N}]+/u).filter(Boolean); }
  /* Alle orda i spørjinga må finnast i den folda tittelen (som delstreng). null = inga spørjing. */
  function makeMatcher(q) {
    const toks = queryTokens(q);
    if (!toks.length) return null;
    return (foldedTitle) => { for (const t of toks) if (foldedTitle.indexOf(t) < 0) return false; return true; };
  }

  function periodIndex(year, n) {
    n = n || 7;
    if (!year || !isFinite(year)) return -1;
    if (year < 2000) return 0;
    return Math.min(n - 1, 1 + Math.floor((year - 2000) / 5));
  }
  function countryIndex(cs) {
    if (!Array.isArray(cs) || !cs.length) return COUNTRIES.length + 1;
    if (cs.length === 1) { const i = COUNTRIES.findIndex((c) => c[0] === cs[0]); return i >= 0 ? i : COUNTRIES.length; }
    return COUNTRIES.length;
  }
  function venueIndex(src, isArchive) {
    const s = String(src || "");
    if (s) for (let i = 0; i < VENUES.length; i++) if (VENUES[i][1].test(s)) return i;
    return isArchive ? VENUES.length : VENUES.length + 1;
  }

  function parseKartHash(hash) {
    const h = String(hash == null ? "" : hash).replace(/^#/, "");
    const qi = h.indexOf("?");
    if ((qi >= 0 ? h.slice(0, qi) : h) !== "kart") return null;
    const st = { k: -1, u: -1, f: "klynge" };
    if (qi < 0) return st;
    for (const part of h.slice(qi + 1).split("&")) {
      const eq = part.indexOf("=");
      if (eq < 0) continue;
      const key = part.slice(0, eq), v = part.slice(eq + 1);
      if (key === "k" && /^\d{1,3}$/.test(v)) st.k = +v;
      else if (key === "u" && /^\d{1,4}$/.test(v)) st.u = +v;
      else if (key === "f" && MODES.indexOf(v) >= 0) st.f = v;
    }
    return st;
  }
  function buildKartHash(st) {
    const p = [];
    if (st.k >= 0) p.push("k=" + st.k);
    if (st.u >= 0) p.push("u=" + st.u);
    if (st.f && st.f !== "klynge") p.push("f=" + st.f);
    return "#kart" + (p.length ? "?" + p.join("&") : "");
  }

  /* Grådig ombryting av ein tekst til liner som er høgst maxW breie (eit langt ord får eiga line). */
  function wrapLines(text, maxW, measure) {
    const words = String(text == null ? "" : text).split(/\s+/).filter(Boolean);
    const lines = [];
    let cur = "";
    for (const w of words) {
      const t = cur ? cur + " " + w : w;
      if (!cur || measure(t) <= maxW) cur = t;
      else { lines.push(cur); cur = w; }
    }
    if (cur) lines.push(cur);
    return lines;
  }

  /* Etikettplassering: items i prioritert rekkjefølgje, {x, y, w, h} med (x, y) som midtpunkt.
     Ein etikett med midtpunkt utanfor flata blir ikkje vist; elles blir han skyvd inn på flata.
     Prøver midt, over og under; kolliderer alle, blir han gøymd. Gir rektangel eller null per item. */
  function placeLabels(items, W, H, gap) {
    gap = gap == null ? 3 : gap;
    const placed = [];
    const out = new Array(items.length).fill(null);
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      if (!(it.x >= 0 && it.x <= W && it.y >= 0 && it.y <= H)) continue;
      if (it.w > W - 4 || it.h > H - 4) continue;
      const tries = [0, -0.5 * it.h - 4, 0.5 * it.h + 4];
      for (const dy of tries) {
        let l = it.x - it.w / 2, t = it.y - it.h / 2 + dy;
        l = Math.max(2, Math.min(W - 2 - it.w, l));
        t = Math.max(2, Math.min(H - 2 - it.h, t));
        const r = { l, t, r: l + it.w, b: t + it.h };
        let hit = false;
        for (const p of placed) if (r.l < p.r + gap && r.r > p.l - gap && r.t < p.b + gap && r.b > p.t - gap) { hit = true; break; }
        if (!hit) { placed.push(r); out[i] = r; break; }
      }
    }
    return out;
  }

  /* Romleg rutenett for treff-testing (koordinatar i datarommet). */
  function buildGrid(xs, ys, n, cell) {
    let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    for (let i = 0; i < n; i++) {
      if (xs[i] < minx) minx = xs[i]; if (xs[i] > maxx) maxx = xs[i];
      if (ys[i] < miny) miny = ys[i]; if (ys[i] > maxy) maxy = ys[i];
    }
    if (!n) { minx = miny = 0; maxx = maxy = 1; }
    const cols = Math.max(1, Math.floor((maxx - minx) / cell) + 1), rows = Math.max(1, Math.floor((maxy - miny) / cell) + 1);
    const cellOf = (i) => Math.floor((ys[i] - miny) / cell) * cols + Math.floor((xs[i] - minx) / cell);
    const start = new Int32Array(cols * rows + 1);
    for (let i = 0; i < n; i++) start[cellOf(i) + 1]++;
    for (let c = 0; c < cols * rows; c++) start[c + 1] += start[c];
    const fill = start.slice(0, cols * rows), items = new Int32Array(n);
    for (let i = 0; i < n; i++) items[fill[cellOf(i)]++] = i;
    return { minx, miny, maxx, maxy, cell, cols, rows, start, items };
  }
  /* Næraste punkt innan radius rad. weight(i): 0 hoppar over punktet, >1 gjer det «lenger unna». */
  function nearest(g, xs, ys, qx, qy, rad, weight) {
    const c0 = Math.max(0, Math.floor((qx - rad - g.minx) / g.cell)), c1 = Math.min(g.cols - 1, Math.floor((qx + rad - g.minx) / g.cell));
    const r0 = Math.max(0, Math.floor((qy - rad - g.miny) / g.cell)), r1 = Math.min(g.rows - 1, Math.floor((qy + rad - g.miny) / g.cell));
    let best = -1, bd = rad * rad;
    for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) {
      const cc = r * g.cols + c;
      for (let j = g.start[cc]; j < g.start[cc + 1]; j++) {
        const i = g.items[j];
        const wgt = weight ? weight(i) : 1;
        if (!wgt) continue;
        const dx = xs[i] - qx, dy = ys[i] - qy, d = (dx * dx + dy * dy) * wgt;
        if (d < bd) { bd = d; best = i; }
      }
    }
    return best;
  }

  /* Plasser ein boks (w x h) ved punktet (px, py) innanfor grensene b = {x0, y0, x1, y1}. */
  function clampBox(px, py, w, h, b, off) {
    off = off == null ? 12 : off;
    let l = px + off;
    if (l + w > b.x1 - 4) l = px - off - w;
    l = Math.max(b.x0 + 4, Math.min(b.x1 - 4 - w, l));
    let t = py + off;
    if (t + h > b.y1 - 4) t = py - off - h;
    t = Math.max(b.y0 + 4, Math.min(b.y1 - 4 - h, t));
    return { left: l, top: t };
  }

  /* Dei mest sentrale verka i ei gruppe, til lenkja til katalogen (høgst limit).
     Brukar ei ferdig liste frå dataa om ho finst (sentrale60); elles dei fem sentrale frå analysen,
     så verk som ikkje ligg på ei grense, sorterte etter avstand i kartet til midten av dei fem. */
  function centralIds(d, grp, members, idIndex, limit) {
    limit = limit || 60;
    if (Array.isArray(grp.sentrale60) && grp.sentrale60.length) return grp.sentrale60.slice(0, limit);
    const out = (grp.sentrale || []).slice(0, limit), seen = new Set(out);
    let mx = 0, my = 0, m = 0;
    for (const id of out) { const i = idIndex.get(id); if (i != null) { mx += d.x[i]; my += d.y[i]; m++; } }
    if (!m) for (const i of members) { mx += d.x[i]; my += d.y[i]; m++; }
    if (m) { mx /= m; my /= m; }
    const rest = members.filter((i) => !seen.has(d.ids[i]));
    const dist = (i) => (d.x[i] - mx) ** 2 + (d.y[i] - my) ** 2;
    rest.sort((a, b) => ((d.f ? d.f[a] & 1 : 0) - (d.f ? d.f[b] & 1 : 0)) || dist(a) - dist(b) || a - b);
    for (const i of rest) { if (out.length >= limit) break; out.push(d.ids[i]); }
    return out;
  }

  function validData(d) {
    if (!d || !Array.isArray(d.ids) || !d.ids.length || !Array.isArray(d.klynger) || !d.klynger.length) return false;
    const n = d.ids.length;
    for (const k of ["x", "y", "k"]) if (!Array.isArray(d[k]) || d[k].length !== n) return false;
    for (const c of d.klynger) if (typeof c.id !== "number" || c.id < 0 || c.id > 255) return false;
    return true;
  }

  function luminance(c) {
    const s = String(c || "").trim();
    let r, g, b, m;
    if ((m = /^#([0-9a-f]{3})$/i.exec(s))) { [r, g, b] = m[1].split("").map((h) => parseInt(h + h, 16)); }
    else if ((m = /^#([0-9a-f]{6})/i.exec(s))) { r = parseInt(m[1].slice(0, 2), 16); g = parseInt(m[1].slice(2, 4), 16); b = parseInt(m[1].slice(4, 6), 16); }
    else if ((m = /rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)/i.exec(s))) { r = +m[1]; g = +m[2]; b = +m[3]; }
    else return 1;
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  }

  /* Éi line over kartet: frå om.json om ho finst, elles sett saman av tala i kart.json. */
  function introLine(d, om) {
    if (om && typeof om.linje === "string" && om.linje.trim()) return om.linje.trim();
    const t = (d && d.tal) || {};
    const n = t.verk || (d && d.ids ? d.ids.length : 0);
    const k = t.klynger || (d && d.klynger ? d.klynger.length : 0);
    let s = fmt(n) + " verk. Kvar prikk er eitt verk, og verk som liknar kvarandre i tema, ligg nær kvarandre. Fargane er " + k + " klynger.";
    if (typeof t.grense_del === "number") s += " Grensene er mjuke: " + pct(t.grense_del) + " av verka ligg på ei grense mellom klynger.";
    return s;
  }

  const API = {
    MODES, PAL, SEQ, SLOT8, COUNTRIES, VENUES,
    esc, fmt, fold, queryTokens, makeMatcher, periodIndex, countryIndex, venueIndex,
    parseKartHash, buildKartHash, wrapLines, placeLabels, buildGrid, nearest, clampBox, centralIds, validData, luminance, introLine,
  };
  if (typeof module === "object" && module.exports) { module.exports = API; return; }
  window.DTKart = API;

  /* =================================================================== nettlesar */
  const SUBZ = 1.9;   // underklynger kjem fram frå denne zoomen
  const DEEPZ = 3.2;  // herifrå går underklyngene føre klyngene
  const ZMAX = 40;
  const TEMPLATE = `
    <p class="kart-linje"></p>
    <div class="kart-kontroll">
      <input type="search" class="kart-sok" placeholder="Finn titlar på kartet" aria-label="Finn titlar på kartet" autocomplete="off" spellcheck="false">
      <select class="kart-farge" aria-label="Farge etter">
        <option value="klynge">Farge: klynge</option>
        <option value="ar">Farge: år</option>
        <option value="land">Farge: land</option>
        <option value="kanal">Farge: kanal</option>
      </select>
    </div>
    <p class="kart-treff" aria-live="polite"></p>
    <div class="kart-ramme">
      <div class="kart-flate">
        <canvas tabindex="0" role="img" aria-label="Kart over verka i korpuset"></canvas>
        <div class="kart-zoom">
          <button type="button" data-kz="inn" aria-label="Zoom inn">+</button>
          <button type="button" data-kz="ut" aria-label="Zoom ut">−</button>
        </div>
        <a class="kart-tips" hidden></a>
        <p class="kart-status" role="status">Lastar kartet…</p>
      </div>
      <div class="kart-linjeverk">
        <p class="kart-hint"></p>
        <button type="button" class="act" data-kz="null">Nullstill</button>
        <button type="button" class="act" data-kz="stor" aria-pressed="false">Stort kart</button>
      </div>
    </div>
    <p class="kart-lg-hovud"></p>
    <div class="kart-forklaring" role="group" aria-label="Fargeforklaring"></div>
    <div class="kart-panel" hidden></div>
    <details class="kart-om" hidden><summary>Korleis kartet er laga</summary><div class="kart-om-tekst"></div></details>`;

  function boot() {
    const sec = document.getElementById("view-kart");
    if (!sec || sec.querySelector(".kart")) return;
    sec.classList.add("kart-ny");
    const root = document.createElement("div");
    root.className = "kart";
    root.innerHTML = TEMPLATE;
    sec.appendChild(root);
    const $ = (s) => root.querySelector(s);
    const el = {
      line: $(".kart-linje"), search: $(".kart-sok"), mode: $(".kart-farge"), hits: $(".kart-treff"),
      frame: $(".kart-ramme"), wrap: $(".kart-flate"), cv: $("canvas"), tip: $(".kart-tips"), status: $(".kart-status"),
      hint: $(".kart-hint"), big: $('[data-kz="stor"]'), lgHead: $(".kart-lg-hovud"), legend: $(".kart-forklaring"),
      panel: $(".kart-panel"), om: $(".kart-om"), omText: $(".kart-om-tekst"),
    };
    const fine = window.matchMedia ? window.matchMedia("(hover: hover) and (pointer: fine)") : { matches: true };

    const K = {
      started: false, d: null, n: 0, xs: null, ys: null, ks: null, us: null, fs: null, grid: null, idx: new Map(),
      cl: [], sb: new Map(), subsOf: [], members: [], works: null, worksFailed: false,
      mode: "klynge", sel: -1, sub: -1, cat: -1, match: null, matchCl: null, matchN: 0,
      focus: null, cats: {}, catIdx: {},
      W: 0, H: 0, dpr: 1, s0: 1, z: 1, cx: 0, cy: 0, bx: null,
      theme: null, raf: 0, hover: -1, pinned: -1, placed: [], measure: new Map(), lines: new Map(), lastDraw: 0,
    };

    /* ---------- tema ---------- */
    function readTheme() {
      const cs = getComputedStyle(document.documentElement);
      const g = (v, fb) => cs.getPropertyValue(v).trim() || fb;
      const bg = g("--bg", "#ffffff");
      K.theme = { bg, fg: g("--fg", "#000000"), dim: g("--dim", "#767676"), line: g("--line", "#d2d2d2"), dark: luminance(bg) < 0.4 };
    }
    const pal = () => PAL[K.theme.dark ? "dark" : "light"];
    function clusterColour(id) {
      if (id < 0) return K.theme.dim;
      const slot = K.cl.length === 8 ? SLOT8[id] : id;
      return slot != null && slot < 8 ? pal()[slot] : K.theme.dim;
    }
    function catColour(mode, i) {
      const P = pal();
      if (mode === "klynge") return clusterColour(i);
      if (mode === "ar") {
        const n = (K.d.periodar || []).length || 7, S = SEQ[K.theme.dark ? "dark" : "light"];
        return i >= 0 && i < n ? S[Math.round((i * (S.length - 1)) / Math.max(1, n - 1))] : K.theme.dim;
      }
      if (mode === "land") return i < COUNTRY_SLOTS.length ? P[COUNTRY_SLOTS[i]] : K.theme.dim;
      if (mode === "kanal") return i <= VENUES.length ? P[i] : K.theme.dim;
      return K.theme.dim;
    }

    /* ---------- lasting ---------- */
    async function jget(u) {
      const r = await fetch(u);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }
    function start() {
      if (K.started) return;
      K.started = true;
      const v = Math.round(Date.now() / 3600e3);
      Promise.all([jget("data/klynger/kart.json?v=" + v), jget("data/klynger/om.json?v=" + v).catch(() => null)])
        .then(([d, om]) => { if (!validData(d)) throw new Error("ugyldig kart.json"); setup(d, om); })
        .catch(fail);
      Promise.all([jget("data/publications.json"), jget("data/nordic_additions.json")])
        .then(([a, b]) => { K.worksRaw = (Array.isArray(a) ? a : []).concat(Array.isArray(b) ? b : []); if (K.d) attachWorks(); })
        .catch(() => { K.worksFailed = true; if (K.d) { renderHits(); renderLegend(); } });
    }
    function fail() {
      K.failed = true;
      el.status.textContent = "Kartet kunne ikkje lastast. Last sida på nytt for å prøve igjen. Under ligg det gamle kartet.";
      el.status.classList.add("kart-feil");
      el.wrap.classList.add("kart-tom");
      sec.classList.remove("kart-ny");
      try { window.dispatchEvent(new Event("resize")); } catch (e) { /* gamalt kart teiknar seg ved neste endring */ }
    }

    function setup(d, om) {
      const n = d.ids.length;
      K.d = d; K.n = n;
      K.xs = Float32Array.from(d.x); K.ys = Float32Array.from(d.y);
      K.ks = Int16Array.from(d.k);
      K.us = Array.isArray(d.u) && d.u.length === n ? Int16Array.from(d.u) : new Int16Array(n).fill(-1);
      K.fs = Array.isArray(d.f) && d.f.length === n ? Uint8Array.from(d.f) : new Uint8Array(n);
      d.ids.forEach((id, i) => K.idx.set(id, i));
      K.cl = [];
      for (const c of d.klynger) K.cl[c.id] = c;
      K.members = K.cl.map(() => []);
      for (let i = 0; i < n; i++) if (K.members[K.ks[i]]) K.members[K.ks[i]].push(i);
      K.subMembers = new Map();
      for (const u of d.under || []) { K.sb.set(u.id, u); K.subMembers.set(u.id, []); }
      for (let i = 0; i < n; i++) { const m = K.subMembers.get(K.us[i]); if (m) m.push(i); }
      K.subsOf = K.cl.map((c) => (d.under || []).filter((u) => u.k === c.id).sort((a, b) => b.n - a.n));
      K.grid = buildGrid(K.xs, K.ys, n, 120);
      const g = K.grid;
      K.bx = { minx: g.minx, miny: g.miny, maxx: g.maxx, maxy: g.maxy };
      K.cx = (g.minx + g.maxx) / 2; K.cy = (g.miny + g.maxy) / 2;
      K.cats.klynge = K.cl.map((c) => ({ name: c.namn || "Klynge " + c.id, n: c.n || K.members[c.id].length }));
      K.catIdx.klynge = K.ks;
      K.focus = new Uint8Array(n).fill(1);

      el.line.textContent = introLine(d, om);
      renderOm(om);
      el.cv.setAttribute("aria-label", "Kart over " + fmt(n) + " verk i " + K.cl.filter(Boolean).length + " klynger. Klyngene står òg i lista under kartet.");
      el.status.hidden = true;
      readTheme();
      resize();
      const st = parseKartHash(location.hash);
      applyState(st || { k: -1, u: -1, f: "klynge" }, false);
      if (K.worksRaw) attachWorks();
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { K.measure.clear(); K.lines.clear(); schedule(); });
    }

    function attachWorks() {
      const raw = K.worksRaw;
      K.worksRaw = null;
      const n = K.n, works = new Array(n);
      const nper = (K.d.periodar || []).length || 7;
      const ar = new Uint8Array(n), land = new Uint8Array(n), kanal = new Uint8Array(n);
      for (const w of raw) {
        const i = K.idx.get(w && w.id);
        if (i == null) continue;
        works[i] = { t: String(w.title || ""), y: w.year || 0, v: String(w.source || w.venue || ""), f: null };
      }
      for (let i = 0; i < n; i++) {
        const w = works[i];
        if (!w) { ar[i] = nper; land[i] = COUNTRIES.length + 1; kanal[i] = VENUES.length + 1; continue; }
        const p = periodIndex(w.y, nper);
        ar[i] = p < 0 ? nper : p;
        land[i] = countryIndex(raw[i] && raw[i].id === K.d.ids[i] ? raw[i].countries : (raw.find((x) => x && x.id === K.d.ids[i]) || {}).countries);
        kanal[i] = venueIndex(w.v, /^nordic:/.test(K.d.ids[i]));
      }
      const count = (arr, m) => { const c = new Array(m).fill(0); for (let i = 0; i < n; i++) c[arr[i]]++; return c; };
      const cAr = count(ar, nper + 1), cLand = count(land, COUNTRIES.length + 2), cKanal = count(kanal, VENUES.length + 2);
      K.catIdx.ar = ar; K.catIdx.land = land; K.catIdx.kanal = kanal;
      K.cats.ar = (K.d.periodar || []).map((p, i) => ({ name: p, n: cAr[i] })).concat([{ name: "Utan år", n: cAr[nper] }]);
      K.cats.land = COUNTRIES.map((c, i) => ({ name: c[1], n: cLand[i] }))
        .concat([{ name: "Fleire eller andre land", n: cLand[COUNTRIES.length] }, { name: "Utan land", n: cLand[COUNTRIES.length + 1] }]);
      K.cats.kanal = VENUES.map((v, i) => ({ name: v[0], n: cKanal[i] }))
        .concat([{ name: "Nordiske arkiv", n: cKanal[VENUES.length] }, { name: "Andre kanalar", n: cKanal[VENUES.length + 1] }]);
      K.works = works;
      runSearch();
      renderLegend();
      renderPanel();
      if (K.pinned >= 0) showTip(K.pinned, true);
      schedule();
    }

    /* ---------- tilstand ---------- */
    function applyState(st, write) {
      if (!K.d) return;
      K.mode = MODES.indexOf(st.f) >= 0 ? st.f : "klynge";
      el.mode.value = K.mode;
      let k = st.k >= 0 && K.cl[st.k] ? st.k : -1, u = st.u >= 0 && K.sb.has(st.u) ? st.u : -1;
      if (u >= 0 && k !== K.sb.get(u).k) k = K.sb.get(u).k;
      K.sel = k; K.sub = u; K.cat = -1;
      computeFocus();
      renderLegend(); renderPanel(); renderHits();
      schedule();
      if (write !== false) writeHash();
    }
    function writeHash() {
      if (!sec.classList.contains("active") || !K.d) return;
      const h = buildKartHash({ k: K.sel, u: K.sub, f: K.mode });
      if (location.hash !== h) { try { history.replaceState(null, "", h); } catch (e) { /* utan historikk */ } }
    }
    function computeFocus() {
      const f = K.focus, n = K.n, ci = K.catIdx[K.mode];
      for (let i = 0; i < n; i++) {
        f[i] = (K.sel < 0 || K.ks[i] === K.sel) && (K.sub < 0 || K.us[i] === K.sub) && (K.cat < 0 || (ci && ci[i] === K.cat)) ? 1 : 0;
      }
    }
    function select(k, u) {
      K.sel = k; K.sub = u == null ? -1 : u;
      if (K.mode === "klynge") K.cat = -1;
      computeFocus(); renderLegend(); renderPanel(); writeHash(); schedule();
    }
    function clearAll() {
      K.sel = -1; K.sub = -1; K.cat = -1;
      computeFocus(); renderLegend(); renderPanel(); writeHash(); schedule();
    }

    /* ---------- søk ---------- */
    let searchTmr = 0;
    function runSearch() {
      if (!K.d) return;
      const m = makeMatcher(el.search.value);
      if (!m || !K.works) { K.match = null; K.matchN = 0; K.matchCl = null; renderHits(); renderLegend(); schedule(); return; }
      const n = K.n, match = new Uint8Array(n), per = new Array(K.cl.length).fill(0);
      let c = 0;
      for (let i = 0; i < n; i++) {
        const w = K.works[i];
        if (!w) continue;
        if (w.f == null) w.f = fold(w.t);
        if (m(w.f)) { match[i] = 1; c++; if (per[K.ks[i]] != null) per[K.ks[i]]++; }
      }
      K.match = match; K.matchN = c; K.matchCl = per;
      renderHits(); renderLegend(); schedule();
    }
    function renderHits() {
      const q = el.search.value.trim();
      let s = "";
      if (q && !K.works) s = K.worksFailed ? "Titlane kunne ikkje lastast, så søket verkar ikkje no." : "Lastar titlar…";
      else if (q && K.match) {
        if (!K.matchN) s = "Ingen titlar passar.";
        else {
          const top = K.matchCl.map((v, id) => [id, v]).filter((x) => x[1] > 0).sort((a, b) => b[1] - a[1]);
          s = fmt(K.matchN) + (K.matchN === 1 ? " tittel passar" : " titlar passar") + ", i " + top.length + (top.length === 1 ? " klynge" : " klynger") + ". " +
            "Flest i " + top.slice(0, 2).map((x) => "«" + (K.cl[x[0]].namn || "") + "» (" + fmt(x[1]) + ")").join(" og ") + ".";
        }
      }
      el.hits.textContent = s;
      el.hits.hidden = !s;
    }

    /* ---------- storleik og visning ---------- */
    function resize() {
      const W = Math.round(el.wrap.clientWidth), H = Math.round(el.wrap.clientHeight);
      if (!W || !H || !K.bx) return;
      const dpr = Math.min(3, window.devicePixelRatio || 1);
      if (W === K.W && H === K.H && dpr === K.dpr) return;
      K.W = W; K.H = H; K.dpr = dpr;
      el.cv.width = Math.round(W * dpr); el.cv.height = Math.round(H * dpr);
      const bw = Math.max(1, K.bx.maxx - K.bx.minx), bh = Math.max(1, K.bx.maxy - K.bx.miny);
      K.s0 = Math.min(W / bw, H / bh) * 0.94;
      el.cv.style.touchAction = K.z > 1.001 ? "none" : "pan-y";
      hideTip();
      schedule();
    }
    function schedule() { if (!K.raf && K.d) K.raf = requestAnimationFrame(draw); }
    const scale = () => K.s0 * K.z;
    function toScreen(x, y) { const s = scale(); return [K.W / 2 + (x - K.cx) * s, K.H / 2 + (y - K.cy) * s]; }
    function toData(px, py) { const s = scale(); return [K.cx + (px - K.W / 2) / s, K.cy + (py - K.H / 2) / s]; }
    function clampView() {
      K.z = Math.max(1, Math.min(ZMAX, K.z));
      K.cx = Math.max(K.bx.minx, Math.min(K.bx.maxx, K.cx));
      K.cy = Math.max(K.bx.miny, Math.min(K.bx.maxy, K.cy));
      el.cv.style.touchAction = K.z > 1.001 ? "none" : "pan-y";
    }
    function zoomAt(px, py, f) {
      const [dx, dy] = toData(px, py);
      K.z = Math.max(1, Math.min(ZMAX, K.z * f));
      const s = scale();
      K.cx = dx - (px - K.W / 2) / s; K.cy = dy - (py - K.H / 2) / s;
      clampView(); hideTip(); schedule();
    }
    function resetView() {
      K.z = 1; K.cx = (K.bx.minx + K.bx.maxx) / 2; K.cy = (K.bx.miny + K.bx.maxy) / 2;
      clampView(); hideTip(); schedule();
    }

    /* ---------- teikning ---------- */
    function measureText(ctx, font, t) {
      const key = font + "|" + t;
      let w = K.measure.get(key);
      if (w == null) { ctx.font = font; w = ctx.measureText(t).width; K.measure.set(key, w); }
      return w;
    }
    function labelBox(ctx, type, o, maxW) {
      const big = type === "k";
      const fs = big ? (K.W < 420 ? 14 : 15) : (K.W < 420 ? 11.5 : 12.5);
      const font = (big ? "" : "italic ") + fs + "px Literata, Charter, Georgia, serif";
      const lh = Math.round(fs * 1.18);
      const key = type + o.id + "|" + font + "|" + maxW;
      let lb = K.lines.get(key);
      if (!lb) {
        const lines = wrapLines(o.namn || (big ? "Klynge " : "Underklynge ") + o.id, maxW, (t) => measureText(ctx, font, t));
        const w = Math.max(...lines.map((t) => measureText(ctx, font, t)));
        lb = { lines, font, lh, w: w + (big ? 13 : 0) + 4, h: lines.length * lh + 2, dot: big };
        K.lines.set(key, lb);
      }
      const [x, y] = toScreen(o.lx, o.ly);
      return { type, id: o.id, o, x, y, w: lb.w, h: lb.h, lb };
    }
    function labelItems(ctx) {
      const d = K.d, maxK = Math.min(190, K.W * 0.46), maxU = Math.min(150, K.W * 0.38);
      const cls = d.klynger.slice().sort((a, b) => ((b.id === K.sel) - (a.id === K.sel)) || b.n - a.n).map((c) => labelBox(ctx, "k", c, maxK));
      const showSubs = K.z >= SUBZ;
      const subs = (d.under || []).filter((u) => (showSubs && (K.sel < 0 || u.k === K.sel)) || u.k === K.sel || u.id === K.sub)
        .filter((u) => typeof u.lx === "number")
        .sort((a, b) => ((b.id === K.sub) - (a.id === K.sub)) || b.n - a.n)
        .map((u) => labelBox(ctx, "u", u, maxU));
      if (K.sub >= 0) {
        const s = subs.filter((x) => x.id === K.sub), sc = cls.filter((x) => x.id === K.sel);
        return s.concat(sc, subs.filter((x) => x.id !== K.sub), cls.filter((x) => x.id !== K.sel));
      }
      if (K.sel >= 0) return [cls[0]].concat(subs, cls.slice(1));
      return K.z >= DEEPZ ? subs.concat(cls) : cls.concat(subs);
    }

    function draw() {
      K.raf = 0;
      if (!K.d || !K.W) return;
      const t0 = performance.now();
      const ctx = el.cv.getContext("2d");
      const T = K.theme, W = K.W, H = K.H, n = K.n;
      ctx.setTransform(K.dpr, 0, 0, K.dpr, 0, 0);
      ctx.globalAlpha = 1;
      ctx.fillStyle = T.bg;
      ctx.fillRect(0, 0, W, H);
      const s = scale(), ox = W / 2 - K.cx * s, oy = H / 2 - K.cy * s;
      const r = Math.min(4.6, Math.max(1.7, 1.25 * Math.sqrt(K.z) + 0.5)), rf = r * 0.8;
      const ci = K.catIdx[K.mode];
      const modeReady = !!ci;
      const cats = K.cats[K.mode] || [];
      const anyF = K.sel >= 0 || K.sub >= 0 || K.cat >= 0, match = K.match, focus = K.focus;
      const faded = new Path2D(), ring = match ? new Path2D() : null;
      const buckets = new Array(cats.length + 2);
      const xs = K.xs, ys = K.ys, TAU = Math.PI * 2;
      for (let i = 0; i < n; i++) {
        const sx = ox + xs[i] * s, sy = oy + ys[i] * s;
        if (sx < -6 || sx > W + 6 || sy < -6 || sy > H + 6) continue;
        if ((anyF && !focus[i]) || (match && !match[i])) { faded.moveTo(sx + rf, sy); faded.arc(sx, sy, rf, 0, TAU); continue; }
        const c = modeReady ? ci[i] : cats.length + 1;
        let p = buckets[c];
        if (!p) p = buckets[c] = new Path2D();
        p.moveTo(sx + r, sy); p.arc(sx, sy, r, 0, TAU);
        if (ring) { ring.moveTo(sx + r + 1.8, sy); ring.arc(sx, sy, r + 1.8, 0, TAU); }
      }
      ctx.fillStyle = T.dim;
      ctx.globalAlpha = T.dark ? 0.32 : 0.22;
      ctx.fill(faded);
      if (ring) { ctx.globalAlpha = 1; ctx.fillStyle = T.fg; ctx.fill(ring); }
      ctx.globalAlpha = match || anyF ? 1 : (T.dark ? 0.85 : 0.8);
      for (let c = 0; c < buckets.length; c++) {
        if (!buckets[c]) continue;
        ctx.fillStyle = modeReady ? catColour(K.mode, c) : T.dim;
        ctx.fill(buckets[c]);
      }
      ctx.globalAlpha = 1;
      const hv = K.pinned >= 0 ? K.pinned : K.hover;
      if (hv >= 0) {
        const sx = ox + xs[hv] * s, sy = oy + ys[hv] * s;
        ctx.beginPath(); ctx.arc(sx, sy, r + 4, 0, TAU);
        ctx.lineWidth = 2; ctx.strokeStyle = T.fg; ctx.stroke();
      }
      drawLabels(ctx);
      K.lastDraw = performance.now() - t0;
    }

    function drawLabels(ctx) {
      const T = K.theme;
      const items = labelItems(ctx);
      const rects = placeLabels(items, K.W, K.H, 4);
      K.placed = [];
      ctx.textBaseline = "middle";
      ctx.lineJoin = "round";
      for (let i = 0; i < items.length; i++) {
        const r = rects[i];
        if (!r) continue;
        const it = items[i], lb = it.lb;
        const k = it.type === "k" ? it.id : it.o.k;
        const dimmed = (K.sel >= 0 && k !== K.sel) || (K.match && K.matchCl && !K.matchCl[k]) || (K.sub >= 0 && it.type === "u" && it.id !== K.sub);
        ctx.globalAlpha = dimmed ? 0.42 : 1;
        ctx.font = lb.font;
        const x0 = r.l + 2 + (lb.dot ? 13 : 0);
        let y = r.t + 1 + lb.lh / 2;
        if (lb.dot) {
          ctx.beginPath(); ctx.arc(r.l + 7, y, 4.5, 0, Math.PI * 2);
          ctx.fillStyle = K.mode === "klynge" ? clusterColour(it.id) : T.fg;
          ctx.lineWidth = 2; ctx.strokeStyle = T.bg; ctx.stroke(); ctx.fill();
        }
        ctx.lineWidth = 4; ctx.strokeStyle = T.bg; ctx.fillStyle = T.fg;
        for (const t of lb.lines) { ctx.strokeText(t, x0, y); ctx.fillText(t, x0, y); y += lb.lh; }
        K.placed.push({ type: it.type, id: it.id, r });
      }
      ctx.globalAlpha = 1;
    }

    /* ---------- treff-testing ---------- */
    function hitLabel(px, py) {
      for (let i = K.placed.length - 1; i >= 0; i--) {
        const p = K.placed[i], r = p.r;
        if (px >= r.l - 3 && px <= r.r + 3 && py >= r.t - 3 && py <= r.b + 3) return p;
      }
      return null;
    }
    function hitPoint(px, py, radPx) {
      if (!K.grid) return -1;
      const [qx, qy] = toData(px, py);
      const anyF = K.sel >= 0 || K.sub >= 0 || K.cat >= 0;
      return nearest(K.grid, K.xs, K.ys, qx, qy, radPx / scale(), (i) => ((anyF && !K.focus[i]) || (K.match && !K.match[i]) ? 4 : 1));
    }

    /* ---------- tips ---------- */
    function showTip(i, pinned) {
      if (i < 0 || !K.d) return hideTip();
      const id = K.d.ids[i], w = K.works ? K.works[i] : null;
      const c = K.cl[K.ks[i]], u = K.sb.get(K.us[i]);
      const meta = [w && w.y ? String(w.y) : "", w ? w.v : ""].filter(Boolean).join(" · ");
      const flags = [];
      if (K.fs[i] & 2) flags.push("Berre tittel: verket har ikkje samandrag, så plasseringa byggjer på tittelen.");
      if (K.fs[i] & 1) flags.push("Grenseverk: færre enn halvparten av dei næraste naboane er i same klynge.");
      el.tip.innerHTML =
        `<strong class="kt-t">${esc(w ? w.t : id)}</strong>` +
        (meta ? `<span class="kt-m">${esc(meta)}</span>` : "") +
        `<span class="kt-k"><i class="kart-sw" style="background:${esc(clusterColour(c ? c.id : -1))}"></i>${esc(c ? c.namn : "")}${u ? ` <span class="kt-u">› ${esc(u.namn)}</span>` : ""}</span>` +
        flags.map((f) => `<span class="kt-f">${esc(f)}</span>`).join("") +
        `<span class="kt-o">${fine.matches ? "Klikk på prikken" : "Trykk her"} for å opne verket i katalogen</span>`;
      el.tip.href = "#verk/" + encodeURIComponent(id);
      el.tip.setAttribute("data-jump", id);
      el.tip.classList.toggle("kt-pinned", !!pinned);
      el.tip.hidden = false;
      placeTip(i);
    }
    function placeTip(i) {
      const [px, py] = toScreen(K.xs[i], K.ys[i]);
      const fr = el.wrap.getBoundingClientRect();
      const vw = window.innerWidth || document.documentElement.clientWidth, vh = window.innerHeight || document.documentElement.clientHeight;
      const b = { x0: Math.max(0, -fr.left), y0: Math.max(0, -fr.top), x1: Math.min(K.W, vw - fr.left), y1: Math.min(K.H, vh - fr.top) };
      el.tip.style.maxWidth = Math.max(160, Math.min(300, K.W - 16)) + "px";
      const tw = el.tip.offsetWidth, th = el.tip.offsetHeight;
      const p = clampBox(px, py, tw, th, b, 12);
      el.tip.style.left = Math.round(p.left) + "px";
      el.tip.style.top = Math.round(p.top) + "px";
    }
    function hideTip() {
      if (!el.tip.hidden) el.tip.hidden = true;
      if (K.pinned >= 0 || K.hover >= 0) { K.pinned = -1; K.hover = -1; schedule(); }
    }
    function openWork(i) {
      if (i < 0) return;
      location.hash = "#verk/" + encodeURIComponent(K.d.ids[i]);
    }

    /* ---------- forklaring, panel, om ---------- */
    function renderLegend() {
      if (!K.d) return;
      const mode = K.mode, cats = K.cats[mode];
      if (!cats) {
        el.lgHead.textContent = K.worksFailed ? "Data for denne fargen kunne ikkje lastast." : "Lastar data for farge etter " + MODE_LABEL[mode] + "…";
        el.legend.innerHTML = "";
        return;
      }
      const hitsFor = (i) => {
        if (!K.match) return 0;
        if (mode === "klynge") return K.matchCl[i] || 0;
        const ci = K.catIdx[mode]; let c = 0;
        for (let j = 0; j < K.n; j++) if (K.match[j] && ci[j] === i) c++;
        return c;
      };
      el.lgHead.textContent = mode === "klynge"
        ? K.cl.filter(Boolean).length + " klynger. Vel ei klynge for å sjå kva ho består av."
        : "Farge etter " + MODE_LABEL[mode] + ". Vel ein farge for å framheve han.";
      el.legend.innerHTML = cats.map((c, i) => {
        if (!c || (!c.n && mode !== "klynge")) return "";
        const on = mode === "klynge" ? K.sel === i : K.cat === i;
        const h = hitsFor(i);
        const attr = mode === "klynge" ? `data-kk="${esc(i)}"` : `data-kc="${esc(i)}"`;
        return `<button type="button" class="kart-lg${on ? " on" : ""}${K.match && !h ? " kart-lg-av" : ""}" ${attr} aria-pressed="${on}">` +
          `<span class="kart-sw" style="background:${esc(catColour(mode, i))}"></span><span class="kart-lg-n">${esc(c.name)}</span>` +
          `<span class="kart-lg-c">${fmt(c.n)}${K.match ? ` · <b>${fmt(h)} treff</b>` : ""}</span></button>`;
      }).join("");
    }

    function workLink(id) {
      const i = K.idx.get(id), w = K.works && i != null ? K.works[i] : null;
      const label = w ? (w.y ? w.y + " · " : "") + w.t : id;
      return `<a href="#verk/${esc(encodeURIComponent(id))}" data-jump="${esc(id)}">${esc(label)}</a>${i != null && K.fs[i] & 2 ? ' <span class="kp-merk">berre tittel</span>' : ""}`;
    }
    function periodBars(per) {
      const labels = K.d.periodar || [];
      const max = Math.max(1, ...per);
      const aria = labels.map((l, i) => l + ": " + (per[i] || 0)).join(", ");
      return `<div class="kp-periode" role="img" aria-label="${esc("Verk per periode. " + aria)}">` +
        per.map((v, i) => `<div class="kp-p"><span class="kp-pv">${fmt(v)}</span><span class="kp-pb"><i style="height:${((v / max) * 100).toFixed(1)}%"></i></span><span class="kp-pl">${esc(labels[i] || "")}</span></div>`).join("") +
        `</div>`;
    }
    function countryName(code) { const c = COUNTRIES.find((x) => x[0] === code); return c ? c[1] : code; }

    function renderPanel() {
      if (!K.d || K.sel < 0 || !K.cl[K.sel]) { el.panel.hidden = true; el.panel.innerHTML = ""; renderHint(); return; }
      const c = K.cl[K.sel], u = K.sub >= 0 ? K.sb.get(K.sub) : null, o = u || c;
      const total = K.n;
      const members = u ? K.subMembers.get(u.id) || [] : K.members[c.id];
      const ids = centralIds(K.d, o, members, K.idx, 60);
      const share = (o.n || members.length) / total;
      const nTitle = u ? members.filter((i) => K.fs[i] & 2).length : c.tittel_berre;
      let sure = "";
      if (!u && typeof c.kjerne === "number") sure = ` ${pct(c.kjerne)} ligg trygt inne i klynga; resten ligg på ei grense mot andre klynger.`;
      else if (u) { const g = members.filter((i) => K.fs[i] & 1).length; if (members.length) sure = ` ${pct(1 - g / members.length)} ligg trygt inne i hovudklynga.`; }
      const titleOnly = typeof nTitle === "number" && nTitle > 0 ? ` ${fmt(nTitle)} av dei har berre tittel.` : "";
      const list = (arr, name) => `<ul class="plain kp-liste">${(arr || []).map((x) => `<li><span>${esc(name ? name(x[0]) : x[0])}</span><span>${fmt(x[1])}</span></li>`).join("")}</ul>`;
      const subs = u ? [] : K.subsOf[c.id] || [];
      el.panel.innerHTML =
        `<div class="kp-hovud"><span class="kart-sw kp-sw" style="background:${esc(clusterColour(c.id))}"></span><h3>${esc(o.namn || "")}</h3></div>` +
        (u ? `<p class="kp-sti">Underklynge i <button type="button" class="kp-knapp" data-kk="${esc(c.id)}">${esc(c.namn)}</button></p>` : "") +
        `<p class="kp-tal">${fmt(o.n || members.length)} verk, ${pct(share)} av korpuset.${sure}${titleOnly}</p>` +
        (o.ord && o.ord.length ? `<h4>Ord som skil ${u ? "gruppa" : "klynga"} frå resten</h4><p class="kp-ord">${o.ord.map((t) => `<span class="tag">${esc(t)}</span>`).join(" ")}</p>` : "") +
        (Array.isArray(o.periode) && o.periode.length ? `<h4>Når verka kom ut</h4>${periodBars(o.periode)}` : "") +
        `<div class="kp-to"><div><h4>Kanalar</h4>${list(o.kanalar)}</div><div><h4>Land</h4>${list(o.land, countryName)}</div></div>` +
        (o.sentrale && o.sentrale.length ? `<h4>Mest sentrale verk</h4><ol class="kp-verk">${o.sentrale.slice(0, 5).map((id) => `<li>${workLink(id)}</li>`).join("")}</ol><p class="kp-note">Sentrale verk er dei som liknar mest på snittet av ${u ? "gruppa" : "klynga"} i tekstrommet.</p>` : "") +
        (subs.length ? `<h4>Underklynger</h4><p class="kp-note">Grupper av verk med mange felles naboar inne i klynga. Zoom inn for å sjå namna på kartet.</p><div class="kp-under">${subs.map((s) => `<button type="button" class="kart-lg" data-ku="${esc(s.id)}"><span class="kart-lg-n">${esc(s.namn)}</span><span class="kart-lg-c">${fmt(s.n)}</span></button>`).join("")}</div>` : "") +
        `<div class="kp-knappar"><a class="act act-block" href="#liste=${ids.map((id) => esc(encodeURIComponent(id))).join("~")}">Opne dei ${ids.length} mest sentrale i katalogen</a>` +
        (u ? `<button type="button" class="act act-block" data-kk="${esc(c.id)}">Tilbake til klynga</button>` : "") +
        `<button type="button" class="act act-block" data-kx="alle">Vis alle klynger</button></div>`;
      el.panel.hidden = false;
      renderHint();
    }
    function renderHint() {
      if (K.sel >= 0 && K.cl[K.sel] && el.frame.classList.contains("kart-stor")) {
        const o = K.sub >= 0 ? K.sb.get(K.sub) : K.cl[K.sel];
        el.hint.textContent = "Vald: " + (o ? o.namn : "") + ". Lukk det store kartet for å sjå detaljane.";
        return;
      }
      el.hint.textContent = fine.matches
        ? "Dra for å flytte, rull for å zoome. Peik på ein prikk for å sjå verket."
        : "Knip for å zoome. Trykk på ein prikk for å sjå verket, eller på eit namn for å sjå klynga.";
    }
    function renderOm(om) {
      if (!om || !Array.isArray(om.bolkar) || !om.bolkar.length) { el.om.hidden = true; return; }
      el.omText.innerHTML = (om.ingress ? `<p>${esc(om.ingress)}</p>` : "") +
        om.bolkar.map((b) => `<h4>${esc(b && b.tittel)}</h4><p>${esc(b && b.tekst)}</p>`).join("");
      el.om.hidden = false;
    }

    /* ---------- stort kart ---------- */
    function setBig(on) {
      el.frame.classList.toggle("kart-stor", on);
      document.documentElement.classList.toggle("kart-stor-open", on);
      el.big.textContent = on ? "Lukk stort kart" : "Stort kart";
      el.big.setAttribute("aria-pressed", String(on));
      renderHint();
      requestAnimationFrame(resize);
    }

    /* ---------- hendingar ---------- */
    root.addEventListener("click", (e) => {
      const t = e.target.closest("[data-kk],[data-ku],[data-kc],[data-kx],[data-kz]");
      if (!t || !root.contains(t)) return;
      if (t.hasAttribute("data-kk")) { const k = +t.getAttribute("data-kk"); if (K.sel === k && K.sub < 0 && t.classList.contains("kart-lg")) clearAll(); else select(k, -1); return; }
      if (t.hasAttribute("data-ku")) { const u = K.sb.get(+t.getAttribute("data-ku")); if (u) select(u.k, u.id); return; }
      if (t.hasAttribute("data-kc")) { const c = +t.getAttribute("data-kc"); K.cat = K.cat === c ? -1 : c; computeFocus(); renderLegend(); schedule(); return; }
      if (t.getAttribute("data-kx") === "alle") { clearAll(); return; }
      const z = t.getAttribute("data-kz");
      if (!K.d) return;
      if (z === "inn") zoomAt(K.W / 2, K.H / 2, 1.6);
      else if (z === "ut") zoomAt(K.W / 2, K.H / 2, 1 / 1.6);
      else if (z === "null") resetView();
      else if (z === "stor") setBig(!el.frame.classList.contains("kart-stor"));
    });
    el.mode.addEventListener("change", () => {
      K.mode = MODES.indexOf(el.mode.value) >= 0 ? el.mode.value : "klynge";
      K.cat = -1; computeFocus(); renderLegend(); writeHash(); schedule();
    });
    el.search.addEventListener("input", () => { clearTimeout(searchTmr); searchTmr = setTimeout(runSearch, 120); });
    root.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (el.frame.classList.contains("kart-stor")) { setBig(false); e.preventDefault(); return; }
      if (!el.tip.hidden) { hideTip(); return; }
      if (K.sel >= 0 || K.sub >= 0 || K.cat >= 0) { clearAll(); e.preventDefault(); return; }
      if (e.target === el.search && el.search.value) { el.search.value = ""; runSearch(); }
    });
    el.cv.addEventListener("keydown", (e) => {
      if (!K.d) return;
      const step = 60 / scale();
      let used = true;
      if (e.key === "ArrowLeft") K.cx -= step; else if (e.key === "ArrowRight") K.cx += step;
      else if (e.key === "ArrowUp") K.cy -= step; else if (e.key === "ArrowDown") K.cy += step;
      else if (e.key === "+" || e.key === "=") { zoomAt(K.W / 2, K.H / 2, 1.4); return e.preventDefault(); }
      else if (e.key === "-" || e.key === "_") { zoomAt(K.W / 2, K.H / 2, 1 / 1.4); return e.preventDefault(); }
      else if (e.key === "0") { resetView(); return e.preventDefault(); }
      else used = false;
      if (used) { e.preventDefault(); clampView(); hideTip(); schedule(); }
    });

    /* Peikarar: mus, penn og fingrar. Éin peikar flyttar, to knip. */
    const ptrs = new Map();
    let drag = null, pinch = null, hoverRaf = 0, hoverAt = null;
    const local = (e) => { const r = el.cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    el.cv.addEventListener("pointerdown", (e) => {
      if (!K.d) return;
      if (e.pointerType === "mouse" && e.button !== 0) return;
      try { el.cv.setPointerCapture(e.pointerId); } catch (err) { /* ikkje kritisk */ }
      const p = local(e);
      ptrs.set(e.pointerId, p);
      if (ptrs.size === 1) drag = { x: p[0], y: p[1], sx: p[0], sy: p[1], moved: false, type: e.pointerType };
      else if (ptrs.size === 2) {
        const [a, b] = [...ptrs.values()];
        pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, mx: (a[0] + b[0]) / 2, my: (a[1] + b[1]) / 2 };
        if (drag) drag.moved = true;
      }
    });
    el.cv.addEventListener("pointermove", (e) => {
      if (!K.d) return;
      const p = local(e);
      if (ptrs.has(e.pointerId)) {
        ptrs.set(e.pointerId, p);
        if (ptrs.size >= 2 && pinch) {
          const [a, b] = [...ptrs.values()];
          const d = Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
          const s = scale();
          K.cx -= (mx - pinch.mx) / s; K.cy -= (my - pinch.my) / s;
          pinch.mx = mx; pinch.my = my;
          zoomAt(mx, my, d / pinch.d);
          pinch.d = d;
          return;
        }
        if (drag) {
          const lim = drag.type === "mouse" ? 4 : 8;
          if (!drag.moved && Math.abs(p[0] - drag.sx) + Math.abs(p[1] - drag.sy) > lim) { drag.moved = true; hideTip(); el.cv.classList.add("kart-drar"); }
          if (drag.moved) {
            const s = scale();
            K.cx -= (p[0] - drag.x) / s; K.cy -= (p[1] - drag.y) / s;
            clampView(); schedule();
          }
          drag.x = p[0]; drag.y = p[1];
        }
        return;
      }
      if (e.pointerType !== "mouse" || K.pinned >= 0) return;
      hoverAt = p;
      if (!hoverRaf) hoverRaf = requestAnimationFrame(() => {
        hoverRaf = 0;
        if (!hoverAt) return;
        const lab = hitLabel(hoverAt[0], hoverAt[1]);
        const i = lab ? -1 : hitPoint(hoverAt[0], hoverAt[1], 9);
        el.cv.style.cursor = lab || i >= 0 ? "pointer" : "";
        if (i !== K.hover) { K.hover = i; if (i >= 0) showTip(i, false); else el.tip.hidden = true; schedule(); }
      });
    });
    const endPtr = (e, cancelled) => {
      if (!ptrs.has(e.pointerId)) return;
      const p = local(e);
      ptrs.delete(e.pointerId);
      if (ptrs.size < 2) pinch = null;
      if (ptrs.size === 1) { const q = [...ptrs.values()][0]; drag = { x: q[0], y: q[1], sx: q[0], sy: q[1], moved: true, type: e.pointerType }; return; }
      if (ptrs.size) return;
      const d = drag;
      drag = null;
      el.cv.classList.remove("kart-drar");
      if (cancelled || !d || d.moved) return;
      tap(p[0], p[1], e.pointerType);
    };
    el.cv.addEventListener("pointerup", (e) => endPtr(e, false));
    el.cv.addEventListener("pointercancel", (e) => endPtr(e, true));
    el.cv.addEventListener("pointerleave", (e) => {
      if (e.pointerType !== "mouse" || K.pinned >= 0) return;
      hoverAt = null;
      if (e.relatedTarget && el.tip.contains(e.relatedTarget)) return;
      if (K.hover >= 0) { K.hover = -1; el.tip.hidden = true; schedule(); }
    });
    function tap(px, py, type) {
      const lab = hitLabel(px, py);
      if (lab) {
        hideTip();
        if (lab.type === "k") { if (K.sel === lab.id && K.sub < 0) clearAll(); else select(lab.id, -1); }
        else { const u = K.sb.get(lab.id); if (u) select(u.k, u.id); }
        return;
      }
      const i = hitPoint(px, py, type === "mouse" ? 9 : 16);
      if (type === "mouse") { if (i >= 0) openWork(i); else hideTip(); return; }
      if (i < 0) { hideTip(); return; }
      K.pinned = i; K.hover = -1;
      showTip(i, true);
      schedule();
    }
    el.cv.addEventListener("wheel", (e) => {
      if (!K.d) return;
      const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * 400 : e.deltaY;
      if (K.z <= 1.0001 && dy > 0 && !e.ctrlKey) return; // lat sida rulle når kartet alt er heilt ute
      e.preventDefault();
      const p = local(e);
      zoomAt(p[0], p[1], Math.exp(-Math.max(-300, Math.min(300, dy)) * (e.ctrlKey ? 0.01 : 0.0022)));
    }, { passive: false });
    /* Knip med to fingrar også når kartet er heilt ute (då rullar éin finger sida). */
    el.cv.addEventListener("touchmove", (e) => { if (e.touches.length > 1 && e.cancelable) e.preventDefault(); }, { passive: false });
    el.cv.addEventListener("dblclick", (e) => { if (!K.d) return; e.preventDefault(); const p = local(e); zoomAt(p[0], p[1], e.shiftKey ? 1 / 2 : 2); });

    if (typeof ResizeObserver === "function") new ResizeObserver(() => resize()).observe(el.wrap);
    window.addEventListener("resize", () => { if (sec.classList.contains("active")) resize(); });
    window.addEventListener("scroll", () => { if (!el.tip.hidden) { const i = K.pinned >= 0 ? K.pinned : K.hover; if (i >= 0) placeTip(i); } }, { passive: true });
    const retheme = () => { if (!K.d) return; readTheme(); renderLegend(); renderPanel(); schedule(); };
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      if (mq.addEventListener) mq.addEventListener("change", retheme); else if (mq.addListener) mq.addListener(retheme);
      if (fine.addEventListener) fine.addEventListener("change", renderHint);
    }
    new MutationObserver(retheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    /* Fana: last ved første opning, skriv adressa når fana blir aktiv. */
    const onActive = () => {
      if (!sec.classList.contains("active")) { if (el.frame.classList.contains("kart-stor")) setBig(false); return; }
      if (!K.started) { start(); return; }
      requestAnimationFrame(() => { resize(); schedule(); });
      writeHash();
    };
    new MutationObserver(onActive).observe(sec, { attributes: true, attributeFilter: ["class"] });
    window.addEventListener("hashchange", () => { const st = parseKartHash(location.hash); if (st && K.d) applyState(st, false); });
    renderHint();
    onActive();

    API.debug = {
      state: K,
      draw() { draw(); return K.lastDraw; },
      view(cx, cy, z) { if (cx != null) K.cx = cx; if (cy != null) K.cy = cy; if (z != null) K.z = z; clampView(); draw(); return K.lastDraw; },
    };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
