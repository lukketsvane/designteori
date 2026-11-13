/* KART - semantisk kart over korpuset: klynger, underklynger, søk i titlar og fargeval.
   Fyller #view-kart når skriptet er lasta.
   Klassisk skript (UMD-hale): window.DTKart i nettlesaren, module.exports i node (reine funksjonar). */
(function () {
  "use strict";

  /* ---------- reine hjelparar (testa i tests/js/kart.test.mjs) ---------- */
  const FOLD_MAP = { "æ": "ae", "ø": "o", "ð": "d", "þ": "th", "ß": "ss", "đ": "d", "ł": "l", "œ": "oe" };
  const MODES = ["klynge", "ar", "land", "kanal", "sprak"];
  const MODE_LABEL = { klynge: "klynge", ar: "år", land: "land", kanal: "kanal", sprak: "språk" };

  /* Kategorisk palett: åtte fargar, validerte for lys og mørk flate (fargeblinde naboar ΔE ≥ 8). */
  const PAL = {
    light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  };
  /* Reserve for kart.json utan fargeplass (farge): klynge -> plass for dei åtte klyngene frå bygget 13.11.2026. */
  const SLOT8 = [5, 7, 4, 0, 6, 3, 1, 2];
  /* År: trinnvis skala der kvar periode skiftar både kulør og lysstyrke (gull, grøn, blågrøn, blå, fiolett),
     så nabotrinn er lette å skilje. Eldst først. */
  const SEQ = {
    light: ["#c08a00", "#7d9a1e", "#2f9a5c", "#14837f", "#2369b0", "#4648a8", "#5e2a84"],
    dark: ["#f0c040", "#b5d24a", "#5ccc8a", "#3fc0c0", "#62a4ea", "#9490ee", "#c58ae0"],
  };
  const LANGS = [["Engelsk", 8], ["Nordiske språk", 4], ["Anna eller ukjent", 0]];
  const LANG_SLOTS = [0, 1, -1];
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
  /* Tittelen folda til « ord ord ord» (mellomrom framfor kvart ord), slik makeMatcher les han. */
  function foldTitle(t) { return " " + queryTokens(t).join(" "); }
  /* Kvart ord i spørjinga må vere starten på eit ord i tittelen («art» finn «arts», ikkje «participatory»).
     Tek ein folda tittel frå foldTitle. null = inga spørjing. */
  function makeMatcher(q) {
    const toks = queryTokens(q).map((t) => " " + t);
    if (!toks.length) return null;
    return (folded) => { for (const t of toks) if (folded.indexOf(t) < 0) return false; return true; };
  }
  /* Lenkje frå eit søk til katalogen: få treff som liste over verka, mange som søk på same ord. */
  function hitsHref(q, ids) {
    if (ids && ids.length && ids.length <= 60) return "#liste=" + ids.map(encodeURIComponent).join("~");
    return "#korpus?q=" + encodeURIComponent(String(q || "").trim());
  }
  function langIndex(flag) {
    for (let i = 0; i < LANGS.length - 1; i++) if (flag & LANGS[i][1]) return i;
    return LANGS.length - 1;
  }
  /* Fargeplass for ei klynge: frå dataa (farge), elles reserven SLOT8 for eit kart med åtte klynger. -1 = ingen farge. */
  function clusterSlot(c, nClusters) {
    if (!c) return -1;
    if (Number.isInteger(c.farge) && c.farge >= 0 && c.farge < 8) return c.farge;
    if (nClusters === 8 && c.id >= 0 && c.id < 8) return SLOT8[c.id];
    return c.id >= 0 && c.id < 8 ? c.id : -1;
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
  function intersects(a, b, gap) { return a.l < b.r + gap && a.r > b.l - gap && a.t < b.b + gap && a.b > b.t - gap; }
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
     Prøver midt, over og under; kolliderer alle, blir han gøymd. Gir rektangel eller null per item.
     reserved: rektangel {l, t, r, b} som ingen etikett får dekkje (til dømes zoomknappane). */
  function placeLabels(items, W, H, gap, reserved) {
    gap = gap == null ? 3 : gap;
    const placed = (reserved || []).slice();
    const out = new Array(items.length).fill(null);
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      if (!(it.x >= 0 && it.x <= W && it.y >= 0 && it.y <= H)) continue;
      if (it.w > W - 4 || it.h > H - 4) continue;
      const tries = [0, -0.6 * it.h - gap, 0.6 * it.h + gap, -it.h - 2 * gap, it.h + 2 * gap];
      /* Først rett over eller under punktet, så litt til sides (ein tredel av breidda). */
      const moves = [];
      for (const dx of [0, it.w / 3, -it.w / 3]) for (const dy of tries) moves.push([dx, dy]);
      for (const [dx, dy] of moves) {
        let l = it.x - it.w / 2 + dx, t = it.y - it.h / 2 + dy;
        l = Math.max(2, Math.min(W - 2 - it.w, l));
        t = Math.max(2, Math.min(H - 2 - it.h, t));
        const r = { l, t, r: l + it.w, b: t + it.h };
        let hit = false;
        for (const p of placed) if (intersects(r, p, gap)) { hit = true; break; }
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

  /* Verk til lenkja til katalogen (høgst limit).
     Brukar den ferdige lista frå dataa om ho finst (sentrale60, rangert i tekstrommet; radnummer i ids eller id-ar).
     Elles (eldre kart.json): dei fem sentrale frå analysen, så verk som ikkje ligg på ei grense, sorterte etter
     avstand i kartet til midten av dei fem. Det er kjernen i biletet, ikkje sentralitet i tekstrommet. */
  function hasRanked(grp) { return !!grp && Array.isArray(grp.sentrale60) && grp.sentrale60.length > 0; }
  function centralIds(d, grp, members, idIndex, limit) {
    limit = limit || 60;
    if (hasRanked(grp)) {
      return grp.sentrale60.slice(0, limit).map((v) => (typeof v === "number" ? d.ids[v] : v)).filter((v) => typeof v === "string");
    }
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

  /* Kort namn til oversikta på smal skjerm: delen før første kolon eller komma. */
  function shortName(name) {
    const s = String(name == null ? "" : name).trim();
    const m = /^[^:,]+/.exec(s);
    const t = m ? m[0].trim() : s;
    return t.length >= 4 ? t : s;
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

  const TALORD = ["null", "éin", "to", "tre", "fire", "fem", "seks", "sju", "åtte", "ni", "ti", "elleve", "tolv", "tretten", "fjorten", "femten", "seksten"];
  function talord(n) { return n >= 0 && n < TALORD.length ? TALORD[n] : fmt(n); }
  const cap = (s) => String(s).charAt(0).toUpperCase() + String(s).slice(1);

  /* Éi kort line over kartet: frå om.json om ho finst, elles sett saman av tala i kart.json.
     Ho skal vere kort, så kartet byrjar høgt på ein telefon; resten står ved forklaringa under kartet. */
  function introLine(d, om) {
    if (om && typeof om.linje === "string" && om.linje.trim()) return om.linje.trim();
    const t = (d && d.tal) || {};
    let s = "Eitt verk per prikk, og like tekstar ligg nær kvarandre.";
    if (typeof t.grense_del === "number") s += " Grensene er mjuke: " + pct(t.grense_del) + " av verka ligg mellom klynger.";
    return s;
  }
  /* «ein algoritme har funne» er fagspråk: «av verk med lik tekst» seier det same. */
  function plain(t) { return String(t).replace(/(\d+|[Åå]tte|[Ss]eks|[Ss]ju|[Nn]i|[Tt]i)\s+(grupper|klynger) som ein algoritme har funne/, "$1 $2 av verk med lik tekst"); }
  /* Overskrifta over klyngelista: kor mykje klyngene er verdt (forbehald), kvar språk speler inn, og kva ein kan gjere. */
  function legendHead(d, om) {
    const t = (d && d.tal) || {}, cl = (d && d.klynger) || [], n = cl.length;
    const str = (k) => (om && typeof om[k] === "string" && om[k].trim() ? plain(om[k].trim()) : "");
    /* Berre første setning: at grensene er mjuke står alt i lina over kartet. */
    const hedge = (str("forbehald") || cap(talord(n)) + " grupper av verk med lik tekst.").split(/(?<=\.)\s+/)[0].replace(/^(\S+) grupper/, "$1 klynger");
    let lang = str("sprak");
    if (!lang && Number.isInteger(t.nordisk_sprak_klynge) && cl[t.nordisk_sprak_klynge]) {
      lang = "Verk på nordiske språk samlar seg i klynga «" + shortName(cl[t.nordisk_sprak_klynge].namn) + "», så der speler språk like mykje inn som tema.";
    }
    return [hedge, lang, "Vel ei klynge for å sjå kva ho består av."].filter(Boolean).join(" ");
  }
  /* Søket startar først ved minst to teikn i eitt ord: «a» og «ø» (folda til «o») treffer kvar tredje tittel. */
  function searchReady(q) { return queryTokens(q).some((t) => t.length >= 2); }
  /* Kategoriane i teiknerekkjefølgje: største først, så sjeldne kategoriar blir teikna sist og ikkje dekte. */
  function paintOrder(counts) {
    const o = [];
    for (let i = 0; i < counts.length; i++) if (counts[i] > 0) o.push(i);
    return o.sort((a, b) => counts[b] - counts[a] || a - b);
  }
  /* Del av verka frå kvar periode som er i gruppa, og delen i heile korpuset (alle periodar saman). */
  function periodShares(per, totals) {
    const share = per.map((v, i) => (totals[i] > 0 ? v / totals[i] : 0));
    const sp = per.reduce((a, b) => a + b, 0), st = totals.reduce((a, b) => a + (b || 0), 0);
    return { share, base: st > 0 ? sp / st : 0 };
  }
  /* «2005–09» -> «’05–09», «før 2000» -> «før ’00»: plass til sju periodar side om side på ein telefon, og apostrofen viser at det er årstal. */
  function shortPeriod(label) {
    const s = String(label == null ? "" : label);
    let m = /^(\d{2})(\d{2})\s*[–-]\s*(\d{2})$/.exec(s);
    if (m) return "’" + m[2] + "–" + m[3];
    m = /^(\D*?)\s*\d{2}(\d{2})$/.exec(s);
    return m ? (m[1] ? m[1] + " " : "") + "’" + m[2] : s;
  }
  /* Tal år i ein periode som «2025–26» (2); 0 når etiketten ikkje er eit slikt spenn. */
  function periodSpan(label) {
    const m = /(\d{4})\s*[–-]\s*(\d{2,4})$/.exec(String(label == null ? "" : label));
    if (!m) return 0;
    const a = +m[1], b = m[2].length === 2 ? Math.floor(a / 100) * 100 + +m[2] : +m[2];
    return b >= a ? b - a + 1 : 0;
  }
  /* Prosent med éin desimal under 10 %, elles heile prosent. */
  function pctFine(x) {
    if (!(x >= 0)) return "";
    const p = x * 100;
    return (p < 10 ? (Math.round(p * 10) / 10).toFixed(1).replace(".", ",") : String(Math.round(p))) + " %";
  }
  /* Merknad når mange i gruppa har berre tittel, men ingen av dei er blant dei sentrale som blir viste. */
  function titleOnlyNote(nTitle, n, shownTitleOnly, what) {
    if (!(n > 0) || !(nTitle / n >= 0.25) || shownTitleOnly > 0) return "";
    return "Ingen av dei " + fmt(nTitle) + " verka med berre tittel (" + pct(nTitle / n) + ") er blant dei fem, så lista viser berre den delen av " + what + " som har samandrag.";
  }
  /* Ei line i panelet når ei gruppe er mykje meir nordiskspråkleg enn korpuset (minst dobbel del og minst 20 %). */
  function languageNote(share, base, what) {
    if (typeof share !== "number" || typeof base !== "number" || !(share >= 0.2) || share < 2 * base) return "";
    return pct(share) + " av verka i " + what + " er på eit nordisk språk, mot " + pct(base) + " i heile korpuset. " +
      "Ein del av det som held " + what + " saman, er difor språket, ikkje berre temaet.";
  }

  const API = {
    MODES, PAL, SEQ, SLOT8, COUNTRIES, VENUES, LANGS,
    esc, fmt, fold, foldTitle, queryTokens, makeMatcher, hitsHref, periodIndex, countryIndex, venueIndex, langIndex, clusterSlot,
    parseKartHash, buildKartHash, wrapLines, placeLabels, shortName, buildGrid, nearest, clampBox, hasRanked, centralIds, validData,
    luminance, introLine, languageNote, legendHead, plain, talord, searchReady, paintOrder, periodShares, shortPeriod, pctFine,
    titleOnlyNote, periodSpan,
  };
  if (typeof module === "object" && module.exports) { module.exports = API; return; }
  window.DTKart = API;

  /* =================================================================== nettlesar */
  const SUBZ = 1.9;   // underklynger kjem fram frå denne zoomen
  const DEEPZ = 3.2;  // herifrå går underklyngene føre klyngene
  const ZMAX = 40;
  const TEMPLATE = `
    <p class="kart-linje"></p>
    <div class="kart-styring">
      <div class="kart-kontroll">
        <input type="search" class="kart-sok" placeholder="Finn titlar" aria-label="Finn titlar på kartet" autocomplete="off" spellcheck="false">
        <span class="kart-farge-l" aria-hidden="true">Farge</span>
        <select class="kart-farge" aria-label="Farge etter">
          <option value="klynge">klynge</option>
          <option value="ar">år</option>
          <option value="land">land</option>
          <option value="kanal">kanal</option>
          <option value="sprak">språk</option>
        </select>
      </div>
      <label class="check kart-kjerne"><input type="checkbox" class="kart-kjerne-av"> Tone ned verk som ligg mellom klynger</label>
      <p class="kart-treff" aria-live="polite"><span class="kart-treff-t"></span> <a class="kart-treff-a" hidden></a></p>
    </div>
    <div class="kart-ramme">
      <div class="kart-flate">
        <canvas class="kart-dens" aria-hidden="true"></canvas>
        <canvas class="kart-cv" tabindex="0" role="img" aria-label="Kart over verka i korpuset" aria-describedby="kart-tastar"></canvas>
        <canvas class="kart-over" aria-hidden="true"></canvas>
        <span class="kart-sr" id="kart-tastar">Piltastane flyttar kartet, pluss og minus zoomar, 0 nullstiller. Enter opnar verket som er valt. Klyngene står òg i lista under kartet.</span>
        <div class="kart-zoom">
          <button type="button" data-kz="inn" aria-label="Zoom inn">+</button>
          <button type="button" data-kz="ut" aria-label="Zoom ut">−</button>
        </div>
        <a class="kart-tips" hidden></a>
        <p class="kart-status" role="status">Lastar kartet…</p>
      </div>
      <div class="kart-mini" role="group" aria-label="Fargeforklaring" hidden></div>
      <div class="kart-linjeverk">
        <p class="kart-hint"></p>
        <button type="button" class="act" data-kz="null">Nullstill utsnitt</button>
        <button type="button" class="act" data-kz="stor" aria-pressed="false">Stort kart</button>
      </div>
    </div>
    <div class="kart-panel" hidden tabindex="-1"></div>
    <p class="kart-lg-hovud"></p>
    <div class="kart-forklaring" role="group" aria-label="Fargeforklaring"></div>
    <div class="kart-klynger" role="group" aria-label="Klynger" hidden></div>
    <details class="kart-om" hidden><summary>Korleis kartet er laga</summary><div class="kart-om-tekst"></div></details>`;

  function boot() {
    const sec = document.getElementById("view-kart");
    if (!sec || sec.querySelector(".kart")) return;
    const root = document.createElement("div");
    root.className = "kart";
    root.innerHTML = TEMPLATE;
    sec.insertBefore(root, sec.firstChild);
    const $ = (s) => root.querySelector(s);
    const el = {
      line: $(".kart-linje"), search: $(".kart-sok"), mode: $(".kart-farge"), hits: $(".kart-treff"),
      hitsT: $(".kart-treff-t"), hitsA: $(".kart-treff-a"), styring: $(".kart-styring"), core: $(".kart-kjerne-av"),
      frame: $(".kart-ramme"), wrap: $(".kart-flate"), cv: $(".kart-cv"), dens: $(".kart-dens"), over: $(".kart-over"),
      tip: $(".kart-tips"), status: $(".kart-status"),
      hint: $(".kart-hint"), big: $('[data-kz="stor"]'), lgHead: $(".kart-lg-hovud"), legend: $(".kart-forklaring"),
      panel: $(".kart-panel"), om: $(".kart-om"), clList: $(".kart-klynger"), omText: $(".kart-om-tekst"), mini: $(".kart-mini"),
    };
    const fine = window.matchMedia ? window.matchMedia("(hover: hover) and (pointer: fine)") : { matches: true };

    const K = {
      started: false, d: null, n: 0, xs: null, ys: null, ks: null, us: null, fs: null, grid: null, idx: new Map(),
      cl: [], sb: new Map(), subsOf: [], members: [], works: null, worksFailed: false,
      mode: "klynge", sel: -1, sub: -1, cat: -1, match: null, matchCl: null, matchN: 0, matchIds: null,
      focus: null, cats: {}, catIdx: {}, coreOnly: false, dens: null, densKey: "",
      W: 0, H: 0, dpr: 1, s0: 1, z: 1, cx: 0, cy: 0, bx: null, moving: 0, engaged: false, bigSave: null,
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
    let warnedSlot = false;
    function clusterColour(id) {
      if (id < 0) return K.theme.dim;
      const slot = clusterSlot(K.cl[id], K.cl.length);
      if (slot < 0 && !warnedSlot) { warnedSlot = true; try { console.warn("kart.js: klynge " + id + " har ingen fargeplass (farge) i kart.json; ho blir grå."); } catch (e) { /* ingen konsoll */ } }
      return slot >= 0 ? pal()[slot] : K.theme.dim;
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
      if (mode === "sprak") return LANG_SLOTS[i] >= 0 ? P[LANG_SLOTS[i]] : K.theme.dim;
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
      el.line.textContent = "Kartet kunne ikkje lastast. Last sida på nytt for å prøve igjen.";
      el.line.classList.add("kart-feil");
      for (const x of [el.frame, el.styring, el.lgHead, el.legend, el.clList, el.panel, el.om]) x.hidden = true;
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
      /* Språk står i flagga (4 nordisk, 8 engelsk). Eit eldre kart.json utan dei får ikkje fargevalet. */
      if (K.fs.some((f) => f & 12)) {
        const li = new Uint8Array(n), cl = new Array(LANGS.length).fill(0);
        for (let i = 0; i < n; i++) { li[i] = langIndex(K.fs[i]); cl[li[i]]++; }
        K.catIdx.sprak = li;
        K.cats.sprak = LANGS.map((l, i) => ({ name: l[0], n: cl[i] }));
      } else {
        const o = el.mode.querySelector('option[value="sprak"]');
        if (o) o.remove();
      }
      K.focus = new Uint8Array(n).fill(1);

      el.line.textContent = introLine(d, om);
      renderOm(om);
      el.cv.setAttribute("aria-label", "Kart over " + fmt(n) + " verk i " + K.cl.filter(Boolean).length + " klynger.");
      K.om = om;
      /* Verk per periode i heile korpuset, til delane i panelet. */
      K.perTotal = (d.periodar || []).map((_, p) => d.klynger.reduce((a, c) => a + ((c.periode && c.periode[p]) || 0), 0));
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
        works[i] = { t: String(w.title || ""), y: w.year || 0, v: String(w.source || w.venue || ""), f: null, cs: w.countries };
      }
      for (let i = 0; i < n; i++) {
        const w = works[i];
        if (!w) { ar[i] = nper; land[i] = COUNTRIES.length + 1; kanal[i] = VENUES.length + 1; continue; }
        const p = periodIndex(w.y, nper);
        ar[i] = p < 0 ? nper : p;
        land[i] = countryIndex(w.cs);
        w.cs = null;
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
      const f = captureFocus();
      runSearch();
      renderLegend();
      renderPanel();
      restoreFocus(f);
      if (K.pinned >= 0) showTip(K.pinned, true);
      schedule();
    }

    /* ---------- tilstand ---------- */
    function applyState(st, write) {
      if (!K.d) return;
      K.mode = MODES.indexOf(st.f) >= 0 && (st.f !== "sprak" || K.catIdx.sprak) ? st.f : "klynge";
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
    function select(k, u, reveal) {
      K.sel = k; K.sub = u == null ? -1 : u;
      if (K.mode === "klynge") K.cat = -1;
      computeFocus(); renderLegend(); renderPanel(); writeHash(); schedule();
      if (reveal) revealPanel();
    }
    /* Valt frå ei liste under kartet: panelet står rett under kartet, over lista, så det kan liggje utanfor skjermen. */
    function revealPanel() {
      if (el.panel.hidden || el.frame.classList.contains("kart-stor")) return;
      const r = el.panel.getBoundingClientRect(), vh = window.innerHeight || document.documentElement.clientHeight;
      if (r.top < 56 || r.top > vh - 120) {
        try { el.panel.scrollIntoView({ block: "start", behavior: "smooth" }); } catch (e) { el.panel.scrollIntoView(true); }
      }
    }
    function clearAll() {
      K.sel = -1; K.sub = -1; K.cat = -1;
      computeFocus(); renderLegend(); renderPanel(); writeHash(); schedule();
    }

    /* ---------- søk ---------- */
    let searchTmr = 0;
    function runSearch() {
      if (!K.d) return;
      const m = searchReady(el.search.value) ? makeMatcher(el.search.value) : null;
      if (!m || !K.works) { K.match = null; K.matchN = 0; K.matchCl = null; K.matchIds = null; renderHits(); renderLegend(); schedule(); return; }
      const n = K.n, match = new Uint8Array(n), per = new Array(K.cl.length).fill(0), ids = [];
      let c = 0;
      for (let i = 0; i < n; i++) {
        const w = K.works[i];
        if (!w) continue;
        if (w.f == null) w.f = foldTitle(w.t);
        if (m(w.f)) { match[i] = 1; c++; if (per[K.ks[i]] != null) per[K.ks[i]]++; if (ids.length <= 60) ids.push(K.d.ids[i]); }
      }
      K.match = match; K.matchN = c; K.matchCl = per; K.matchIds = ids;
      renderHits(); renderLegend(); schedule();
    }
    function renderHits() {
      const q = el.search.value.trim();
      let s = "", href = "", label = "";
      if (q && !searchReady(q)) s = "Skriv minst to bokstavar.";
      else if (q && !K.works) s = K.worksFailed ? "Titlane kunne ikkje lastast, så søket verkar ikkje no." : "Lastar titlar…";
      else if (q && K.match) {
        if (!K.matchN) s = "Ingen titlar passar. Søket finn ord som byrjar slik i titlane.";
        else {
          const top = K.matchCl.map((v, id) => [id, v]).filter((x) => x[1] > 0).sort((a, b) => b[1] - a[1]);
          s = fmt(K.matchN) + (K.matchN === 1 ? " tittel passar" : " titlar passar") + ", i " + top.length + (top.length === 1 ? " klynge" : " klynger") + ". " +
            (top.length === 1 ? "Alle i " : "Flest i ") + top.slice(0, 2).map((x) => "«" + (K.cl[x[0]].namn || "") + "» (" + fmt(x[1]) + ")").join(" og ") + ".";
          if (K.matchN > K.n * 0.3) s += " Ordet er vanleg, så treffa ligg over heile kartet.";
          href = hitsHref(q, K.matchN <= 60 ? K.matchIds : null);
          label = K.matchN <= 60 ? (K.matchN === 1 ? "Opne treffet i katalogen" : "Opne dei " + fmt(K.matchN) + " treffa i katalogen") : "Søk etter «" + q + "» i katalogen";
        }
      }
      el.hitsT.textContent = s;
      el.hitsA.hidden = !href;
      if (href) { el.hitsA.href = href; el.hitsA.textContent = label; } else el.hitsA.removeAttribute("href");
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
      el.over.width = Math.round(W * dpr); el.over.height = Math.round(H * dpr);
      /* Tettleikslaget er eit mjukt bilete: halv oppløysing held, og det sparer mykje på ein telefon med dpr 3. */
      K.ddpr = Math.min(dpr, 1.5);
      el.dens.width = Math.round(W * K.ddpr); el.dens.height = Math.round(H * K.ddpr);
      K.densView = null;
      const bw = Math.max(1, K.bx.maxx - K.bx.minx), bh = Math.max(1, K.bx.maxy - K.bx.miny);
      K.s0 = Math.min(W / bw, H / bh) * 0.94;
      el.cv.style.touchAction = K.z > 1.001 ? "none" : "pan-y";
      schedule();
      if (!el.tip.hidden) { const i = K.pinned >= 0 ? K.pinned : K.hover; if (i >= 0) requestAnimationFrame(() => placeTip(i)); }
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
      clampView(); hideTip(); moved(); schedule();
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
      const full = o.namn || (big ? "Klynge " : "Underklynge ") + o.id;
      const short = big && K.W < 480 && K.z < SUBZ && o.id !== K.sel;
      const key = type + o.id + "|" + font + "|" + maxW + "|" + short;
      let lb = K.lines.get(key);
      if (!lb) {
        const lines = wrapLines(short ? shortName(full) : full, maxW, (t) => measureText(ctx, font, t));
        const w = Math.max(...lines.map((t) => measureText(ctx, font, t)));
        lb = { lines, font, lh, w: w + (big ? 13 : 0) + 4, h: lines.length * lh + 2, dot: big };
        K.lines.set(key, lb);
      }
      const [x, y] = toScreen(o.lx, o.ly);
      return { type, id: o.id, o, x, y, w: lb.w, h: lb.h, lb };
    }
    function labelItems(ctx) {
      const d = K.d, maxK = Math.min(190, K.W * 0.46), maxU = Math.min(150, K.W * 0.38);
      /* Når det ikkje er plass til alle namna, vinn klyngene med tydelegast kjerne (kjerne = del av verka som ikkje
         ligg på ei grense): eit namn i eit samanhengande område seier meir enn eit namn midt i ei blanding. */
      const prio = (c) => (typeof c.kjerne === "number" ? c.kjerne : 0);
      const cls = d.klynger.slice().sort((a, b) => ((b.id === K.sel) - (a.id === K.sel)) || prio(b) - prio(a) || b.n - a.n).map((c) => labelBox(ctx, "k", c, maxK));
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
      /* Flata er gjennomsiktig: bakgrunnen og tettleikslaget ligg i eigne lag under (sjå drawDensity). */
      ctx.clearRect(0, 0, W, H);
      const s = scale(), ox = W / 2 - K.cx * s, oy = H / 2 - K.cy * s;
      const r = Math.min(4.6, Math.max(1.7, 1.25 * Math.sqrt(K.z) + 0.5)), rf = r * 0.8;
      const ci = K.catIdx[K.mode];
      const modeReady = !!ci;
      const cats = K.cats[K.mode] || [];
      const anyF = K.sel >= 0 || K.sub >= 0 || K.cat >= 0, match = K.match, focus = K.focus, fs = K.fs, core = K.coreOnly;
      /* Små prikkar og prikkar i rørsle blir teikna som firkantar (fillRect): same flate, langt mindre rasterarbeid.
         Rundingar berre når kartet står i ro og prikkane er store nok til at forma syner. */
      const sq = K.moving > 0 || r < 2.4;
      drawDensity(s, ox, oy);
      const xs = K.xs, ys = K.ys, TAU = Math.PI * 2, nb = cats.length + 2;
      const code = K.code && K.code.length === n ? K.code : (K.code = new Int16Array(n));
      const sxa = K.sxa && K.sxa.length === n ? K.sxa : (K.sxa = new Float32Array(n)), sya = K.sya && K.sya.length === n ? K.sya : (K.sya = new Float32Array(n));
      const cnt = new Int32Array(nb);
      let nFaded = 0;
      for (let i = 0; i < n; i++) {
        const sx = ox + xs[i] * s, sy = oy + ys[i] * s;
        sxa[i] = sx; sya[i] = sy;
        if (sx < -6 || sx > W + 6 || sy < -6 || sy > H + 6) { code[i] = -1; continue; }
        if ((anyF && !focus[i]) || (match && !match[i]) || (core && fs[i] & 1)) { code[i] = -2; nFaded++; continue; }
        const c = modeReady ? ci[i] : cats.length + 1;
        code[i] = c; cnt[c]++;
      }
      /* Største kategori først: sjeldne (verk frå før 2005, Island) blir teikna sist og ligg øvst. */
      const order = paintOrder(cnt);
      const paint = (want, rad) => {
        if (sq) {
          const side = rad * 1.77, h = side / 2;
          for (let i = 0; i < n; i++) if (code[i] === want) ctx.fillRect(sxa[i] - h, sya[i] - h, side, side);
        } else {
          ctx.beginPath();
          for (let i = 0; i < n; i++) if (code[i] === want) { ctx.moveTo(sxa[i] + rad, sya[i]); ctx.arc(sxa[i], sya[i], rad, 0, TAU); }
          ctx.fill();
        }
      };
      if (nFaded) { ctx.fillStyle = T.dim; ctx.globalAlpha = T.dark ? 0.32 : 0.22; paint(-2, rf); }
      if (match) {
        ctx.globalAlpha = 1; ctx.fillStyle = T.fg;
        for (const c of order) paint(c, r + 1.8);
      }
      ctx.globalAlpha = match || anyF ? 1 : (T.dark ? 0.85 : 0.8);
      for (const c of order) {
        ctx.fillStyle = modeReady ? catColour(K.mode, c) : T.dim;
        paint(c, r);
      }
      ctx.globalAlpha = 1;
      K.r = r;
      drawLabels(ctx);
      drawOverlay();
      K.lastDraw = performance.now() - t0;
    }
    /* Ringen rundt verket under peikaren ligg i eit eige lag, så ein musepeikar over prikkane ikkje teiknar heile kartet. */
    function drawOverlay() {
      const ctx = el.over.getContext("2d");
      ctx.setTransform(K.dpr, 0, 0, K.dpr, 0, 0);
      ctx.clearRect(0, 0, K.W, K.H);
      const hv = K.pinned >= 0 ? K.pinned : K.hover;
      if (hv < 0 || !K.d) return;
      const [sx, sy] = toScreen(K.xs[hv], K.ys[hv]);
      ctx.beginPath(); ctx.arc(sx, sy, (K.r || 3) + 4, 0, Math.PI * 2);
      ctx.lineWidth = 2; ctx.strokeStyle = K.theme.fg; ctx.stroke();
    }

    /* Tettleik: eit svakt, glatta lag under prikkane som viser kvar verka ligg tettast når prikkane dekkjer
       kvarandre. Rekna éin gong (128 x 128 ruter i datarommet, gaussisk glatting) og skalert med utsnittet. */
    function rgbOf(c) {
      const s = String(c || "").trim();
      let m;
      if ((m = /^#([0-9a-f]{3})$/i.exec(s))) return m[1].split("").map((h) => parseInt(h + h, 16));
      if ((m = /^#([0-9a-f]{6})/i.exec(s))) return [0, 2, 4].map((o) => parseInt(m[1].slice(o, o + 2), 16));
      if ((m = /rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)/i.exec(s))) return [+m[1], +m[2], +m[3]];
      return [128, 128, 128];
    }
    function buildDensity() {
      const G = 128, b = K.bx, pad = 6;
      const w = Math.max(1, b.maxx - b.minx), h = Math.max(1, b.maxy - b.miny), cell = Math.max(w, h) / (G - 2 * pad);
      const x0 = b.minx - pad * cell, y0 = b.miny - pad * cell;
      const g = new Float32Array(G * G);
      for (let i = 0; i < K.n; i++) {
        const cx = Math.floor((K.xs[i] - x0) / cell), cy = Math.floor((K.ys[i] - y0) / cell);
        if (cx >= 0 && cx < G && cy >= 0 && cy < G) g[cy * G + cx]++;
      }
      const sig = 1.8, rad = 5, ker = [];
      let ks = 0;
      for (let d = -rad; d <= rad; d++) { const v = Math.exp(-(d * d) / (2 * sig * sig)); ker.push(v); ks += v; }
      const tmp = new Float32Array(G * G), out = new Float32Array(G * G);
      for (let y = 0; y < G; y++) for (let x = 0; x < G; x++) {
        let a = 0;
        for (let d = -rad; d <= rad; d++) { const xx = x + d; if (xx >= 0 && xx < G) a += g[y * G + xx] * ker[d + rad]; }
        tmp[y * G + x] = a / ks;
      }
      let max = 0;
      for (let y = 0; y < G; y++) for (let x = 0; x < G; x++) {
        let a = 0;
        for (let d = -rad; d <= rad; d++) { const yy = y + d; if (yy >= 0 && yy < G) a += tmp[yy * G + x] * ker[d + rad]; }
        out[y * G + x] = a / ks;
        if (a / ks > max) max = a / ks;
      }
      const cv = document.createElement("canvas");
      cv.width = G; cv.height = G;
      const c2 = cv.getContext("2d"), img = c2.createImageData(G, G), [R, Gc, B] = rgbOf(K.theme.fg);
      for (let p = 0; p < G * G; p++) {
        const v = max ? out[p] / max : 0;
        /* fem trinn, så tette område får ein synleg kant utan å teikne skarpe grenser */
        const step = Math.floor(Math.pow(v, 0.8) * 5) / 5;
        img.data[p * 4] = R; img.data[p * 4 + 1] = Gc; img.data[p * 4 + 2] = B; img.data[p * 4 + 3] = Math.round(step * 255);
      }
      c2.putImageData(img, 0, 0);
      return { cv, x0, y0, size: G * cell };
    }
    /* Tettleiken står i sitt eige lerret under prikkane. Det blir teikna på nytt berre når kartet står i ro;
       under flytting og zoom følgjer det med som ein CSS-transform (nesten gratis), så det verken blinkar eller
       sprett fram når kartet stoppar. */
    function drawDensity(s, ox, oy) {
      const key = K.theme.fg + "|" + K.n;
      if (!K.dens || K.densKey !== key) { K.dens = buildDensity(); K.densKey = key; K.densView = null; }
      const look = key + "|" + K.coreOnly + "|" + K.W + "x" + K.H;
      const V = K.densView;
      if (V && V.look === look) {
        if (V.s === s && V.ox === ox && V.oy === oy) { if (V.tf) { el.dens.style.transform = ""; V.tf = false; } return; }
        if (K.moving) {
          const k = s / V.s;
          el.dens.style.transform = `translate(${ox - V.ox * k}px, ${oy - V.oy * k}px) scale(${k})`;
          V.tf = true;
          return;
        }
      }
      const D = K.dens, ctx = el.dens.getContext("2d");
      ctx.setTransform(K.ddpr, 0, 0, K.ddpr, 0, 0);
      ctx.clearRect(0, 0, K.W, K.H);
      ctx.imageSmoothingEnabled = true;
      ctx.globalAlpha = (K.coreOnly ? 0.2 : 0.1) * (K.theme.dark ? 1.3 : 1);
      ctx.drawImage(D.cv, ox + D.x0 * s, oy + D.y0 * s, D.size * s, D.size * s);
      el.dens.style.transform = "";
      K.densView = { look, s, ox, oy, tf: false };
    }

    function drawLabels(ctx) {
      const T = K.theme;
      const items = labelItems(ctx);
      /* Hjørnet med zoomknappane (8 px inn, to knappar på 44 px) skal ingen namn dekkje. */
      const rects = placeLabels(items, K.W, K.H, 4, [{ l: K.W - 56, t: 0, r: K.W, b: 104 }]);
      K.placed = [];
      ctx.textBaseline = "middle";
      ctx.lineJoin = "round";
      for (let i = 0; i < items.length; i++) {
        const r = rects[i];
        if (!r) continue;
        const it = items[i], lb = it.lb;
        const k = it.type === "k" ? it.id : it.o.k;
        const dimmed = (K.sel >= 0 && k !== K.sel) || (K.match && K.matchCl && !K.matchCl[k]) || (K.sub >= 0 && it.type === "u" && it.id !== K.sub);
        ctx.globalAlpha = dimmed ? 0.6 : 1;
        ctx.font = lb.font;
        const x0 = r.l + 2 + (lb.dot ? 13 : 0);
        let y = r.t + 1 + lb.lh / 2;
        if (lb.dot) {
          ctx.beginPath(); ctx.arc(r.l + 7, y, 4.5, 0, Math.PI * 2);
          ctx.fillStyle = K.mode === "klynge" ? clusterColour(it.id) : T.fg;
          ctx.lineWidth = 2; ctx.strokeStyle = T.bg; ctx.stroke(); ctx.fill();
        }
        ctx.lineWidth = 4; ctx.strokeStyle = T.bg; ctx.fillStyle = it.type === "u" && it.o.slag ? T.dim : T.fg;
        for (const t of lb.lines) { ctx.strokeText(t, x0, y); ctx.fillText(t, x0, y); y += lb.lh; }
        K.placed.push({ type: it.type, id: it.id, r });
      }
      ctx.globalAlpha = 1;
    }

    /* ---------- treff-testing ---------- */
    /* pad: kor mange px utanfor teksten eit trykk enno tel som treff på namnet. */
    /* minH: trykkflata blir utvida loddrett til minst så mange px. */
    function hitLabel(px, py, pad, minH) {
      pad = pad == null ? 3 : pad;
      for (let i = K.placed.length - 1; i >= 0; i--) {
        const p = K.placed[i], r = p.r;
        const py0 = Math.max(pad, minH ? (minH - (r.b - r.t)) / 2 : 0);
        if (px >= r.l - pad && px <= r.r + pad && py >= r.t - py0 && py <= r.b + py0) return p;
      }
      return null;
    }
    function hitPoint(px, py, radPx) {
      if (!K.grid) return -1;
      const [qx, qy] = toData(px, py);
      const anyF = K.sel >= 0 || K.sub >= 0 || K.cat >= 0;
      return nearest(K.grid, K.xs, K.ys, qx, qy, radPx / scale(),
        (i) => ((anyF && !K.focus[i]) || (K.match && !K.match[i]) || (K.coreOnly && K.fs[i] & 1) ? 4 : 1));
    }

    /* ---------- tips ---------- */
    function showTip(i, pinned) {
      if (i < 0 || !K.d) return hideTip();
      const id = K.d.ids[i], w = K.works ? K.works[i] : null;
      const c = K.cl[K.ks[i]], u = K.sb.get(K.us[i]);
      const meta = [w && w.y ? String(w.y) : "", w ? w.v : ""].filter(Boolean).join(" · ");
      /* Korte merke; title gir forklaringa med peikar, og «Om kartet» forklarer dei i lengre form. */
      const flags = [];
      if (K.fs[i] & 2) flags.push(["berre tittel", "Verket har ikkje samandrag, så plasseringa byggjer på tittelen."]);
      if (K.fs[i] & 1) flags.push(["mellom klynger", "Færre enn halvparten av dei næraste naboane er i same klynge."]);
      el.tip.innerHTML =
        `<strong class="kt-t">${esc(w ? w.t : id)}</strong>` +
        (meta ? `<span class="kt-m">${esc(meta)}</span>` : "") +
        `<span class="kt-k"><i class="kart-sw" style="background:${esc(clusterColour(c ? c.id : -1))}"></i>${esc(c ? c.namn : "")}${u ? ` <span class="kt-u">› ${esc(u.namn)}</span>` : ""}</span>` +
        (flags.length ? `<span class="kt-fl">${flags.map((f) => `<span class="kt-f" title="${esc(f[1])}">${esc(f[0])}</span>`).join("")}</span>` : "") +
        `<span class="kt-o">${pinned ? (fine.matches ? "Klikk her eller trykk Enter" : "Trykk her") + " for å opne verket i katalogen" : "Klikk på prikken for å feste boksen"}</span>`;
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
      if (K.pinned >= 0 || K.hover >= 0) { K.pinned = -1; K.hover = -1; drawOverlay(); }
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
        renderMini();
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
        ? legendHead(K.d, K.om)
        : "Farge etter " + MODE_LABEL[mode] + ". Vel ein farge for å framheve han." + (mode === "ar" || mode === "land" ? " Dei minste gruppene er teikna øvst." : "");
      renderMini();
      /* Med ei klynge vald viser panelet klynga, og «Vis alle klynger» tek lista tilbake. */
      const chosen = mode === "klynge" && K.sel >= 0;
      el.lgHead.hidden = chosen; el.legend.hidden = chosen;
      el.legend.innerHTML = cats.map((c, i) => {
        if (!c || (!c.n && mode !== "klynge")) return "";
        const on = mode === "klynge" ? K.sel === i : K.cat === i;
        const h = hitsFor(i);
        const attr = mode === "klynge" ? `data-kk="${esc(i)}"` : `data-kc="${esc(i)}"`;
        return `<button type="button" class="kart-lg${on ? " on" : ""}${K.match && !h ? " kart-lg-av" : ""}" ${attr} aria-pressed="${on}">` +
          `<span class="kart-sw" style="background:${esc(catColour(mode, i))}"></span><span class="kart-lg-n">${esc(c.name)}</span>` +
          `<span class="kart-lg-c">${fmt(c.n)}${K.match ? ` · <b>${fmt(h)} treff</b>` : ""}</span></button>`;
      }).join("");
      /* Klyngelista er tekstalternativet til kartet, så ho står der i alle fargeval. */
      if (mode === "klynge") { el.clList.hidden = true; el.clList.innerHTML = ""; return; }
      el.clList.innerHTML = `<p class="kart-lg-hovud">Klynger</p><div class="kart-forklaring">` +
        K.cl.map((c, i) => c ? `<button type="button" class="kart-lg${K.sel === i ? " on" : ""}${K.match && !(K.matchCl[i] || 0) ? " kart-lg-av" : ""}" data-kk="${esc(i)}" aria-pressed="${K.sel === i}">` +
          `<span class="kart-lg-n">${esc(c.namn || "Klynge " + i)}</span><span class="kart-lg-c">${fmt(c.n || 0)}${K.match ? ` · <b>${fmt(K.matchCl[i] || 0)} treff</b>` : ""}</span></button>` : "").join("") + `</div>`;
      el.clList.hidden = false;
    }

    /* Kompakt fargeforklaring inne i det store kartet: ein rad med knappar som kan rullast sidelengs. */
    function renderMini() {
      if (!el.frame.classList.contains("kart-stor")) { el.mini.hidden = true; el.mini.innerHTML = ""; return; }
      const mode = K.mode, cats = K.cats[mode];
      if (!cats) { el.mini.hidden = true; return; }
      el.mini.innerHTML = cats.map((c, i) => {
        if (!c || (!c.n && mode !== "klynge")) return "";
        const on = mode === "klynge" ? K.sel === i : K.cat === i;
        const attr = mode === "klynge" ? `data-kk="${esc(i)}"` : `data-kc="${esc(i)}"`;
        const name = mode === "klynge" ? shortName(c.name) : c.name;
        return `<button type="button" class="kart-chip${on ? " on" : ""}" ${attr} aria-pressed="${on}" title="${esc(c.name)}">` +
          `<span class="kart-sw" style="background:${esc(catColour(mode, i))}"></span>${esc(name)}</button>`;
      }).join("");
      el.mini.hidden = false;
    }

    function workLink(id) {
      const i = K.idx.get(id), w = K.works && i != null ? K.works[i] : null;
      const label = w ? (w.y ? w.y + " · " : "") + w.t : id;
      return `<a href="#verk/${esc(encodeURIComponent(id))}" data-jump="${esc(id)}">${esc(label)}</a>${i != null && K.fs[i] & 2 ? ' <span class="kp-merk">berre tittel</span>' : ""}`;
    }
    /* Del av alle verk frå kvar periode som er i gruppa, mot delen i heile korpuset (streken). Delar, ikkje tal:
       korpuset veks, så tal ville få kvar gruppe til å sjå ut som ho veks. Siste periode er berre to år. */
    function periodBars(per, what) {
      const labels = K.d.periodar || [], tot = K.perTotal || [];
      const { share, base } = periodShares(per, tot);
      const max = Math.max(base * 1.6, ...share, 1e-6);
      const last = labels.length - 1;
      const part = last >= 1 && periodSpan(labels[last]) > 0 && periodSpan(labels[last]) < periodSpan(labels[last - 1]) ? last : -1;
      const aria = labels.map((l, i) => l + (i === part ? " (delår)" : "") + ": " + pctFine(share[i]) + " (" + (per[i] || 0) + " av " + (tot[i] || 0) + ")").join(", ");
      const bl = ((base / max) * 100).toFixed(1);
      return `<div class="kp-periode" role="img" aria-label="${esc("Del av verka frå kvar periode som er i " + what + ". " + aria + ". I heile korpuset: " + pctFine(base) + ".")}">` +
        per.map((v, i) => `<div class="kp-p" title="${esc((labels[i] || "") + ": " + fmt(v) + " av " + fmt(tot[i] || 0) + " verk")}"><span class="kp-pv">${pctFine(share[i])}</span>` +
          `<span class="kp-pb"><i style="height:${((share[i] / max) * 100).toFixed(1)}%"></i><b style="bottom:${bl}%"></b></span>` +
          `<span class="kp-pl">${esc(shortPeriod(labels[i] || ""))}${i === part ? "*" : ""}</span></div>`).join("") +
        `</div>` +
        `<p class="kp-note">Stolpen er delen av alle verk frå perioden som er i ${what}; streken er delen i heile korpuset (${pctFine(base)}). ` +
        `Over streken er ${what} sterkare i perioden enn elles.${part >= 0 ? ` * ${esc(labels[part])} er berre to år, og det siste året er ikkje over.` : ""}</p>`;
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
      const t = K.d.tal || {};
      const lang = languageNote(o.nordisk, t.nordisk_sprak_del_alle, u ? "gruppa" : "klynga");
      const ranked = hasRanked(o);
      const what = u ? "gruppa" : "klynga";
      const shown = (o.sentrale || []).slice(0, 5);
      /* Grupper som ikkje er tema (konferansebind, blandingar) og grupper som ikkje kjem att når metoden blir køyrd på nytt. */
      const kind = u && u.slag === "dokument" ? "Denne gruppa er halden saman av dokumenttypen, til dømes konferansebind og innleiingar, ikkje av eit tema."
        : u && u.slag === "blanda" ? "Ei lita, blanda gruppe. Namnet passar midten av gruppa, ikkje alle verka i ho." : "";
      const unstable = u && typeof u.stabilitet === "number" && u.stabilitet < 0.4
        ? `Gruppa er ustabil: køyrer ein metoden på nytt, overlappar ho i snitt berre ${pct(u.stabilitet)} med den gruppa som liknar mest.` : "";
      el.panel.innerHTML =
        `<button type="button" class="kp-knapp kp-alle" data-kx="alle">← Alle klynger</button>` +
        `<div class="kp-hovud"><span class="kart-sw kp-sw" style="background:${esc(clusterColour(c.id))}"></span><h3>${esc(o.namn || "")}</h3></div>` +
        (u ? `<p class="kp-sti">Underklynge i <button type="button" class="kp-knapp" data-kk="${esc(c.id)}">${esc(c.namn)}</button></p>` : "") +
        `<p class="kp-note kp-namn">${o.namn_sjekka === false ? "Namnet er laga automatisk av dei skiljande orda." : "Namnet er sett for hand ut frå orda og titlane under."} Ingen fagperson har kontrollert det.</p>` +
        (kind || unstable ? `<p class="kp-tal kp-slag">${esc([kind, unstable].filter(Boolean).join(" "))}</p>` : "") +
        `<p class="kp-tal">${fmt(o.n || members.length)} verk, ${pct(share)} av korpuset.${sure}${titleOnly}</p>` +
        (lang ? `<p class="kp-tal kp-sprak">${esc(lang)}</p>` : "") +
        (o.ord && o.ord.length ? `<h4>Engelske ord som skil ${u ? "gruppa" : "klynga"} frå resten</h4><p class="kp-ord">${o.ord.map((t) => `<span class="tag">${esc(t)}</span>`).join(" ")}</p>` : "") +
        (Array.isArray(o.periode) && o.periode.length ? `<h4>Når verka kom ut</h4>${periodBars(o.periode, what)}` : "") +
        `<div class="kp-to"><div><h4>Kanalar (verk)</h4>${list(o.kanalar)}</div><div><h4>Land (verk)</h4>${list(o.land, countryName)}</div></div>` +
        (shown.length ? `<h4>Mest sentrale verk</h4><ol class="kp-verk">${shown.map((id) => `<li>${workLink(id)}</li>`).join("")}</ol>` +
          `<p class="kp-note">Sentrale verk liknar mest på snittet av ${what} i tekstrommet, ikkje i biletet.${ranked ? " Verk med samandrag kjem først." : ""}</p>` : "") +
        (subs.length ? `<h4>Underklynger</h4><p class="kp-note">Zoom inn for å sjå namna på kartet.${subs.some((s) => s.slag) ? " Grå namn er konferansebind eller ei blanding, ikkje tema." : ""}</p><div class="kp-under">${subs.map((s) => `<button type="button" class="kart-lg${s.slag ? " kart-lg-slag" : ""}" data-ku="${esc(s.id)}"><span class="kart-lg-n">${esc(s.namn)}</span><span class="kart-lg-c">${fmt(s.n)}</span></button>`).join("")}</div>` : "") +
        `<div class="kp-knappar"><a class="act act-block" href="#liste=${ids.map((id) => esc(encodeURIComponent(id))).join("~")}">${ranked ? `Opne dei ${ids.length} mest sentrale i katalogen` : `Opne ${ids.length} verk frå kjernen av ${what}`}</a>` +
        `</div>`;
      el.panel.hidden = false;
      renderHint();
    }
    function renderHint() {
      const o = K.sel >= 0 && K.cl[K.sel] ? (K.sub >= 0 ? K.sb.get(K.sub) : K.cl[K.sel]) : null;
      if (o && el.frame.classList.contains("kart-stor")) {
        el.hint.textContent = "Vald: " + o.namn + ". Lukk det store kartet for å sjå detaljane.";
        return;
      }
      if (o) { el.hint.textContent = ""; return; }
      el.hint.textContent = fine.matches
        ? "Dra for å flytte. Klikk i kartet og rull, hald Ctrl og rull, eller dobbeltklikk for å zoome. Klikk på ein prikk for å sjå verket."
        : "Knip for å zoome. Trykk på ein prikk for å sjå verket.";
    }
    function renderOm(om) {
      if (!om || !Array.isArray(om.bolkar) || !om.bolkar.length) { el.om.hidden = true; return; }
      el.omText.innerHTML = (om.ingress ? `<p>${esc(plain(om.ingress))}</p>` : "") +
        om.bolkar.map((b) => `${b && b.tittel === "Korleis kartet er laga" ? "" : `<h4>${esc(b && b.tittel)}</h4>`}<p>${esc(b && b.tekst)}</p>`).join("");
      el.om.hidden = false;
    }

    /* ---------- stort kart ---------- */
    /* Det store kartet er ein modal dialog: søk og fargeval blir flytte inn, ei kompakt forklaring står nedst,
       Tab blir verande i dialogen, og ved lukking kjem sida tilbake til same rulleposisjon og same fokus. */
    function setBig(on, keepScroll) {
      const isOn = el.frame.classList.contains("kart-stor");
      if (!on && keepScroll) K.bigSave = null;
      if (on === isOn) return;
      if (on) {
        K.bigSave = { y: window.scrollY || window.pageYOffset || 0, focus: document.activeElement };
        el.frame.insertBefore(el.styring, el.wrap);
        el.frame.setAttribute("role", "dialog");
        el.frame.setAttribute("aria-modal", "true");
        el.frame.setAttribute("aria-label", "Stort kart");
      } else {
        root.insertBefore(el.styring, el.frame);
        el.frame.removeAttribute("role");
        el.frame.removeAttribute("aria-modal");
        el.frame.removeAttribute("aria-label");
      }
      el.frame.classList.toggle("kart-stor", on);
      document.documentElement.classList.toggle("kart-stor-open", on);
      el.big.textContent = on ? "Lukk stort kart" : "Stort kart";
      el.big.setAttribute("aria-pressed", String(on));
      renderHint();
      renderMini();
      resize();
      requestAnimationFrame(resize);
      if (on) { try { el.big.focus({ preventScroll: true }); } catch (e) { el.big.focus(); } }
      else if (K.bigSave) {
        const s = K.bigSave;
        K.bigSave = null;
        /* Straks, ikkje i neste bilete: sida har alt fått att høgda si når klassen er fjerna. */
        window.scrollTo(0, s.y);
        const f = s.focus && document.contains(s.focus) && s.focus !== document.body ? s.focus : el.big;
        try { f.focus({ preventScroll: true }); } catch (e) { /* fokus er ikkje kritisk */ }
      }
    }
    el.frame.addEventListener("keydown", (e) => {
      if (e.key !== "Tab" || !el.frame.classList.contains("kart-stor")) return;
      const f = [...el.frame.querySelectorAll("button, [href], input, select, canvas[tabindex]")]
        .filter((x) => !x.hidden && !x.disabled && x.offsetParent !== null && x.getAttribute("tabindex") !== "-1");
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { last.focus(); e.preventDefault(); }
      else if (!e.shiftKey && document.activeElement === last) { first.focus(); e.preventDefault(); }
    });

    /* ---------- fokus ---------- */
    /* Forklaringa, klyngelista, den kompakte lista og panelet blir bygde på nytt ved kvart val. Då forsvinn knappen som
       hadde fokus, og ein tastaturbrukar ville hamne øvst på sida. Difor: hugs kva knapp som hadde fokus, og set fokus
       på same knapp (same data-attributt i same liste) etter at lista er bygd på nytt. */
    const FOCUS_ATTRS = ["data-kk", "data-kc", "data-ku", "data-kx", "data-kz", "data-kd"];
    function captureFocus() {
      const a = document.activeElement;
      if (!a || a === document.body || !root.contains(a)) return null;
      const zone = [el.mini, el.clList, el.legend, el.panel, el.hint].find((z) => z.contains(a)) || null;
      const attr = FOCUS_ATTRS.find((x) => a.hasAttribute(x));
      return { node: a, zone, attr, val: attr ? a.getAttribute(attr) : null, sel: K.sel };
    }
    const visible = (x) => !!x && document.contains(x) && !x.hidden && x.getClientRects().length > 0;
    function focusEl(x) { try { x.focus({ preventScroll: true }); } catch (e) { x.focus(); } }
    function restoreFocus(f) {
      if (!f) return;
      const a = document.activeElement;
      /* Fokus er flytt med vilje (til panelet, til knappen for stort kart): la det vere. */
      if (a && a !== document.body && a !== document.documentElement && document.contains(a)) {
        if (a !== f.node || visible(a)) return;
      }
      if (visible(f.node)) { focusEl(f.node); return; }
      let t = null;
      if (f.zone && f.attr) t = [...f.zone.querySelectorAll(`[${f.attr}]`)].find((x) => x.getAttribute(f.attr) === f.val && visible(x)) || null;
      /* Knappen finst ikkje lenger (til dømes «Vis alle klynger» i panelet): panelet om det står, elles klynga i lista. */
      if (!t && (f.zone === el.panel || f.zone === el.legend) && visible(el.panel)) t = el.panel;
      if (!t) {
        const k = K.sel >= 0 ? K.sel : f.sel;
        const lists = [el.mini, el.legend, el.clList].filter(visible);
        for (const z of lists) { t = k >= 0 ? z.querySelector(`[data-kk="${k}"]`) : null; if (visible(t)) break; t = null; }
        if (!t) for (const z of lists) { t = z.querySelector("button"); if (visible(t)) break; t = null; }
      }
      if (t) focusEl(t);
    }

    /* ---------- hendingar ---------- */
    root.addEventListener("click", (e) => {
      const t = e.target.closest("[data-kk],[data-ku],[data-kc],[data-kx],[data-kz],[data-kd]");
      if (!t || !root.contains(t)) return;
      const f = captureFocus();
      onControl(t);
      restoreFocus(f);
    });
    function onControl(t) {
      /* Val i listene under panelet flyttar panelet inn i synsfeltet; val inne i panelet eller i det store kartet gjer ikkje. */
      const fromList = !!t.closest(".kart-forklaring, .kart-klynger") && !t.closest(".kart-panel");
      if (t.hasAttribute("data-kd")) { revealPanel(); try { el.panel.focus({ preventScroll: true }); } catch (err) { /* ikkje kritisk */ } return; }
      if (t.hasAttribute("data-kk")) {
        const k = +t.getAttribute("data-kk");
        if (K.sel === k && K.sub < 0 && (t.classList.contains("kart-lg") || t.classList.contains("kart-chip"))) clearAll(); else select(k, -1, fromList);
        return;
      }
      if (t.hasAttribute("data-ku")) { const u = K.sb.get(+t.getAttribute("data-ku")); if (u) select(u.k, u.id); return; }
      if (t.hasAttribute("data-kc")) { const c = +t.getAttribute("data-kc"); K.cat = K.cat === c ? -1 : c; computeFocus(); renderLegend(); schedule(); return; }
      if (t.getAttribute("data-kx") === "alle") { clearAll(); return; }
      const z = t.getAttribute("data-kz");
      if (!K.d) return;
      if (z === "inn") zoomAt(K.W / 2, K.H / 2, 1.6);
      else if (z === "ut") zoomAt(K.W / 2, K.H / 2, 1 / 1.6);
      else if (z === "null") resetView();
      else if (z === "stor") setBig(!el.frame.classList.contains("kart-stor"));
    }
    /* Klikk på «kart» i menyen når kartet alt er ope: app.js skriv då berre «#kart» og fjernar valet frå adressa,
       utan at klassen på fana endrar seg. Skriv adressa på nytt etter app.js. */
    document.addEventListener("click", (e) => {
      const b = e.target && e.target.closest ? e.target.closest('[data-tab="kart"]') : null;
      if (b && !root.contains(b)) setTimeout(writeHash, 0);
    });
    el.mode.addEventListener("change", () => {
      K.mode = MODES.indexOf(el.mode.value) >= 0 ? el.mode.value : "klynge";
      K.cat = -1; computeFocus(); renderLegend(); writeHash(); schedule();
    });
    el.search.addEventListener("input", () => { clearTimeout(searchTmr); searchTmr = setTimeout(runSearch, 120); });
    el.core.addEventListener("change", () => { K.coreOnly = el.core.checked; hideTip(); schedule(); });
    /* Under rørsle blir prikkane teikna som firkantar; når kartet har stått i ro ei lita stund, kjem rundingane att. */
    let moveTmr = 0;
    function moved() {
      K.moving = 1;
      clearTimeout(moveTmr);
      moveTmr = setTimeout(() => { K.moving = 0; schedule(); }, 160);
    }
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape" || !sec.classList.contains("active")) return;
      if (el.frame.classList.contains("kart-stor")) { setBig(false); e.preventDefault(); return; }
      if (!root.contains(e.target) && e.target !== document.body && e.target !== document.documentElement) return;
      if (!el.tip.hidden) { hideTip(); return; }
      if (K.sel >= 0 || K.sub >= 0 || K.cat >= 0) { const f = captureFocus(); clearAll(); restoreFocus(f); e.preventDefault(); return; }
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
      else if (e.key === "Enter" && K.pinned >= 0) { openWork(K.pinned); return e.preventDefault(); }
      else used = false;
      if (used) { e.preventDefault(); clampView(); hideTip(); moved(); schedule(); }
    });

    /* Peikarar: mus, penn og fingrar. Éin peikar flyttar, to knip. */
    const ptrs = new Map();
    let drag = null, pinch = null, hoverRaf = 0, hoverAt = null;
    const local = (e) => { const r = el.cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    el.cv.addEventListener("pointerdown", (e) => {
      if (!K.d) return;
      if (e.pointerType === "mouse" && e.button !== 0) return;
      K.engaged = true;
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
            clampView(); moved(); schedule();
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
        const lab = labelAt(hoverAt[0], hoverAt[1], true);
        const i = lab ? -1 : hitPoint(hoverAt[0], hoverAt[1], 9);
        el.cv.style.cursor = lab || i >= 0 ? "pointer" : "";
        if (i !== K.hover) { K.hover = i; if (i >= 0) showTip(i, false); else el.tip.hidden = true; drawOverlay(); }
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
      if (K.hover >= 0) { K.hover = -1; el.tip.hidden = true; drawOverlay(); }
    });
    function tap(px, py, type) {
      const mouse = type === "mouse";
      let lab = labelAt(px, py, mouse);
      /* Eit fingertrykk i margen rundt eit namn går til ein prikk som ligg like ved, så prikkar under namna kan nåast. */
      if (lab && !mouse && !hitLabel(px, py, 0) && hitPoint(px, py, 6) >= 0) lab = null;
      if (lab) {
        hideTip();
        if (lab.type === "k") { if (K.sel === lab.id && K.sub < 0) clearAll(); else select(lab.id, -1, true); }
        else { const u = K.sb.get(lab.id); if (u) select(u.k, u.id, true); }
        return;
      }
      /* Eit klikk festar boksen ved verket (som eit trykk på ein telefon); verket blir opna frå boksen eller med Enter.
         Då kan ein dobbeltklikke for å zoome inn der prikkane ligg tett, utan å forlate kartet. */
      const i = hitPoint(px, py, mouse ? 9 : 16);
      if (i < 0) { hideTip(); return; }
      if (K.pinned === i) return;
      K.pinned = i; K.hover = -1;
      showTip(i, true);
      drawOverlay();
    }
    /* Namnet under peikaren. Med mus går ein prikk rett under peikaren (innan 3 px) føre namnet, så prikkar under eit
       namn kan nåast. Med finger er trykkflata rundt eit namn minst 44 px høg. */
    function labelAt(px, py, mouse) {
      if (mouse) return hitPoint(px, py, 3) >= 0 ? null : hitLabel(px, py, 3);
      return hitLabel(px, py, 3, 44);
    }
    /* Rull zoomar berre når kartet er teke i bruk (klikka i eller fokusert) eller med Ctrl, Cmd eller Shift.
       Elles rullar sida forbi kartet som før, og lina under kartet seier korleis ein zoomar. */
    el.cv.addEventListener("focus", () => { K.engaged = true; });
    el.cv.addEventListener("blur", () => { K.engaged = false; });
    el.frame.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") K.engaged = false; });
    let wheelNote = 0;
    el.cv.addEventListener("wheel", (e) => {
      if (!K.d) return;
      const raw = e.deltaY || (e.shiftKey ? e.deltaX : 0);
      const dy = e.deltaMode === 1 ? raw * 16 : e.deltaMode === 2 ? raw * 400 : raw;
      const mod = e.ctrlKey || e.metaKey || e.shiftKey;
      if (!mod && !K.engaged && !el.frame.classList.contains("kart-stor")) {
        if (!wheelNote) {
          el.hint.textContent = "Klikk i kartet først, eller hald Ctrl og rull, for å zoome.";
          wheelNote = setTimeout(() => { wheelNote = 0; renderHint(); }, 2200);
        }
        return;
      }
      if (K.z <= 1.0001 && dy > 0 && !mod) return; // lat sida rulle når kartet alt er heilt ute
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
    const retheme = () => { if (!K.d) return; const f = captureFocus(); readTheme(); renderLegend(); renderPanel(); restoreFocus(f); schedule(); };
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      if (mq.addEventListener) mq.addEventListener("change", retheme); else if (mq.addListener) mq.addListener(retheme);
      if (fine.addEventListener) fine.addEventListener("change", renderHint);
    }
    new MutationObserver(retheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    /* Fana: last ved første opning, skriv adressa når fana blir aktiv. */
    const onActive = () => {
      if (!sec.classList.contains("active")) { if (el.frame.classList.contains("kart-stor")) setBig(false, true); hideTip(); return; }
      if (!K.started) { start(); return; }
      requestAnimationFrame(() => { resize(); schedule(); });
      writeHash();
    };
    new MutationObserver(onActive).observe(sec, { attributes: true, attributeFilter: ["class"] });
    window.addEventListener("hashchange", () => { const st = parseKartHash(location.hash); if (st && K.d) { const f = captureFocus(); applyState(st, false); restoreFocus(f); } });
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
