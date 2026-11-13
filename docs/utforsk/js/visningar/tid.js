// Tid: themes as bands over time, and term curves for words the reader types.
import { esc, fmt, pst, kutt, PALETTE_TEMA, PALETTE_ORD, ORD_MERKE, ORD_STREK, termNokkel, fold, tween, rorsle, tooltip, kort, segmentert, plasserVertikalt, veldigSmal, smal } from "../hjelp.js?v=20";

const A0 = 1990, A1 = 2026;
const AR = Array.from({ length: A1 - A0 + 1 }, (_, j) => A0 + j);
let A, T, D, S, ramme, d3;
let el = {};
let ordning = null;     // fixed band order
let korpusStabel = null; // whole-corpus counts [year][tema]
let forrigeVerdiar = null, stoppTween = null;
let merkAr = null;
let hoverTema = null;
let tvSeg;
let ordStatus = "ingen"; // ingen | lastar | ok | feil
let ukjendMelding = "";
let siste = null;
let sisteTilpassa = false; // band scale fitted to a small selection: the corpus outline is then not drawn

export default {
  id: "tid",
  filer: [],
  skript: [],
  async init(rot, api) {
    A = api; T = api.T; D = api.D; S = api.S; ramme = api.ramme; d3 = window.d3;
    ramme.flate.insertAdjacentHTML("beforeend", `
      <div class="tid">
        <div class="tid-band" aria-label="Tema over tid"><svg></svg></div>
        <div class="tid-stripe brushstripe"><svg aria-label="Dra for å velje år"></svg></div>
        <div class="tid-ordboks">
          <div class="ordfelt">
            <input type="text" class="ordinput" placeholder="Skriv eit ord, til dømes co-design" aria-label="Legg til eit ord" autocomplete="off" autocapitalize="off" spellcheck="false" role="combobox" aria-expanded="false" aria-controls="ordforslag" aria-autocomplete="list">
            <ul class="forslag ordforslag" id="ordforslag" role="listbox" aria-label="Ord i titlar" hidden></ul>
          </div>
          <div class="ordchipar"></div>
          <p class="ordmelding" aria-live="polite"></p>
        </div>
        <div class="tid-ord" aria-label="Ord over tid"><svg></svg><p class="ord-tom" hidden></p></div>
      </div>`);
    el = {
      band: ramme.flate.querySelector(".tid-band"), stripe: ramme.flate.querySelector(".tid-stripe"), ord: ramme.flate.querySelector(".tid-ord"),
      input: ramme.flate.querySelector(".ordinput"), forslag: ramme.flate.querySelector(".ordforslag"), chipar: ramme.flate.querySelector(".ordchipar"),
      melding: ramme.flate.querySelector(".ordmelding"), ordTom: ramme.flate.querySelector(".ord-tom"),
    };
    tvSeg = segmentert(ramme.kontroll, {
      namn: "Mål for orda", verdi: S.tid.tv,
      val: [{ k: "del", namn: "Del" }, { k: "tal", namn: "Tal" }],
      ved: (v) => T.endre((s) => { s.tid.tv = v; }),
    });
    tvSeg.el.insertAdjacentHTML("beforebegin", `<span class="kontroll-namn">Ord</span>`);
    // fixed band order from the whole corpus
    korpusStabel = AR.map(() => new Float64Array(D.verk.tema.length));
    for (let i = 0; i < D.n; i++) { const a = D.ar[i]; if (a >= A0 && a <= A1) korpusStabel[a - A0][D.tema[i]]++; }
    const keys = D.verk.tema.map((_, j) => j);
    const st = d3.stack().keys(keys).value((r, k) => r[k])(korpusStabel);
    ordning = d3.stackOrderInsideOut(st);
    bindInput();
    ramme.teikn.addEventListener("click", (e) => { const b = e.target.closest("button[data-tema]"); if (b) T.veksle("tema", b.dataset.tema); });
    el.chipar.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-fjernord]");
      if (b) T.endre((s) => { s.tid.termar = s.tid.termar.filter((t) => t !== b.dataset.fjernord); s.tid.termarSett = true; });
      const c = e.target.closest("button[data-filterord]");
      if (c) T.veksle("term", c.dataset.filterord);
    });
    new ResizeObserver(() => teikn(false)).observe(ramme.flate);
    lastOrd();
  },
  oppdater(s, e) {
    tvSeg.set(S.tid.tv);
    teikn(e.filter && !e.popstate);
  },
  merk(i) { merkAr = i == null ? null : D.ar[i]; teiknMerk(); },
  vis() { teikn(false); },
  skjul() { tooltip.skjul(); },
  etikettar: () => [],
  tvingTeikn() {},
};

async function lastOrd() {
  ordStatus = "lastar";
  const [a, b] = await Promise.all([T.sikre("tid.json"), T.sikre("termar.bin")]);
  ordStatus = a.ok && b.ok ? "ok" : "feil";
  if (ordStatus === "ok" && !S.tid.termarSett && !S.tid.termar.length) T.endre((s) => { s.tid.termar = D.tidd.standard.slice(); }, { hist: "ingen" });
  else teikn(false);
}

// ---------- term input ----------
function bindInput() {
  const inp = el.input;
  let valt = -1, liste = [];
  const lukk = () => { el.forslag.hidden = true; el.forslag.innerHTML = ""; inp.setAttribute("aria-expanded", "false"); valt = -1; liste = []; };
  const vis = () => {
    const q = inp.value.trim();
    if (!q || ordStatus !== "ok") { lukk(); return; }
    const key = termNokkel(q), fk = fold(key), utan = fk.replace(/ /g, "");
    const td = D.tidd, ut = [], sett = new Set();
    for (let t = 0; t < td.termar.k.length && ut.length < 8; t++) { const f = D.termFold[t]; if (f.startsWith(fk) || (utan && f.startsWith(utan))) { ut.push(t); sett.add(t); } }
    for (let t = 0; t < td.termar.k.length && ut.length < 8; t++) if (!sett.has(t) && D.termFold[t].includes(fk)) ut.push(t);
    liste = ut;
    if (!ut.length) { lukk(); return; }
    el.forslag.innerHTML = ut.map((t, j) => `<li role="option" id="ordf-${j}" aria-selected="${j === valt}"><button type="button" tabindex="-1" data-t="${t}"><b>${esc(td.termar.vis[t])}</b> · ${fmt(td.termar.df[t])} titlar</button></li>`).join("");
    el.forslag.hidden = false;
    inp.setAttribute("aria-expanded", "true");
  };
  const leggTil = (t) => {
    const key = D.tidd.termar.k[t];
    lukk();
    inp.value = "";
    ukjendMelding = "";
    if (S.tid.termar.includes(key)) { teikn(false); return; }
    if (S.tid.termar.length >= 6) { ukjendMelding = "Du kan samanlikne opptil seks ord. Fjern eitt først."; teikn(false); return; }
    T.endre((s) => { s.tid.termar = [...s.tid.termar, key]; s.tid.termarSett = true; });
  };
  const provSkriven = () => {
    const q = inp.value.trim();
    if (!q || ordStatus !== "ok") return;
    const key = termNokkel(q);
    let t = D.termIdx.get(key);
    if (t == null) t = D.termIdx.get(key.replace(/ /g, ""));
    if (t != null) leggTil(t);
    else { ukjendMelding = `«${q}» finst ikkje i ordlista (ord som står i minst ${D.tidd.tal.min_df} titlar, og ikkje i meir enn 4 av 10).`; lukk(); teikn(false); }
  };
  inp.addEventListener("input", () => { valt = -1; vis(); });
  inp.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" && liste.length) { valt = Math.min(liste.length - 1, valt + 1); vis(); inp.setAttribute("aria-activedescendant", `ordf-${valt}`); e.preventDefault(); }
    else if (e.key === "ArrowUp" && liste.length) { valt = Math.max(0, valt - 1); vis(); inp.setAttribute("aria-activedescendant", `ordf-${valt}`); e.preventDefault(); }
    else if (e.key === "Enter") { if (valt >= 0 && liste[valt] != null) leggTil(liste[valt]); else provSkriven(); e.preventDefault(); }
    else if (e.key === "Escape" && !el.forslag.hidden) { lukk(); e.stopPropagation(); e.preventDefault(); }
  });
  inp.addEventListener("blur", () => setTimeout(lukk, 150));
  el.forslag.addEventListener("pointerdown", (e) => e.preventDefault());
  el.forslag.addEventListener("click", (e) => { const b = e.target.closest("button[data-t]"); if (b) leggTil(+b.dataset.t); });
}

// ---------- data ----------
function bandData() {
  const u = T.utvalUtan(["ar"]);
  const K = D.verk.tema.length;
  const rows = AR.map(() => new Float64Array(K));
  let foer = 0, med = 0;
  for (let i = 0; i < D.n; i++) {
    if (!u[i]) continue;
    const a = D.ar[i];
    if (a < A0) { foer++; continue; }
    rows[a - A0][D.tema[i]]++;
  }
  for (let i = 0; i < D.n; i++) if (T.utval[i]) med += D.ar[i] >= A0 ? 1 : 0;
  return { rows, foer, med };
}

function ordData() {
  const u = T.utvalUtan(["term", "ar"]);
  const m = new Float64Array(AR.length);
  for (let i = 0; i < D.n; i++) if (u[i] && D.ar[i] >= A0) m[D.ar[i] - A0]++;
  const kurver = [];
  for (const key of S.tid.termar) {
    const t = D.termIdx.get(key);
    if (t == null) continue;
    const h = new Float64Array(AR.length);
    const o = D.tidd.off;
    for (let p = o[t]; p < o[t + 1]; p++) { const i = D.postingar[p]; if (u[i] && D.ar[i] >= A0) h[D.ar[i] - A0]++; }
    const pkt = AR.map((a, j) => {
      if (S.tid.tv === "tal") return { a, v: h[j], h: h[j], n: m[j] };
      const hs = (h[j - 1] || 0) + h[j] + (h[j + 1] || 0);
      const ns = (m[j - 1] || 0) + m[j] + (m[j + 1] || 0);
      return { a, v: ns >= 20 ? (100 * hs) / ns : null, h: h[j], n: m[j] };
    });
    kurver.push({ key, t, vis: D.tidd.termar.vis[t], pkt });
  }
  return { kurver, m };
}

// ---------- drawing ----------
function marg() {
  const w = el.band.clientWidth;
  const hogre = w >= 600 ? 150 : 16;
  return { l: 44, r: hogre, w };
}

function teikn(anim) {
  if (!el.band) return;
  const { rows, foer, med } = bandData();
  const ny = rows;
  if (anim && forrigeVerdiar && !rorsle.redusert) {
    const fra = forrigeVerdiar;
    if (stoppTween) stoppTween();
    stoppTween = tween(300, (t) => {
      const mid = ny.map((r, j) => r.map((v, k) => fra[j][k] + (v - fra[j][k]) * t));
      teiknBand(mid);
      forrigeVerdiar = mid;
    }, () => { stoppTween = null; forrigeVerdiar = ny; });
  } else { if (stoppTween) { stoppTween(); stoppTween = null; } teiknBand(ny); forrigeVerdiar = ny; }
  teiknStripe();
  teiknOrd();
  teiknMerk();
  // line and legend
  ramme.linje.textContent = `Verk per år etter tema. ${fmt(T.valt)} verk i utvalet; ${fmt(foer)} verk før 1990 er ikkje med. 2026 er ufullstendig. Orda: del av verka kvart år som har ordet i tittelen, glatta over tre år. Delen er utan ordfilteret.`;
  ramme.teikn.innerHTML = `<span class="teikn-merk">Bandbreidd: verk per år. ${sisteTilpassa ? "Skalaen er tilpassa det vesle utvalet, så heile korpuset er ikkje teikna som grå kontur." : T.harFilter() ? "Grå kontur: heile korpuset." : ""} Skravert: 2026 er ufullstendig.</span>`;
  void med;
}

function skuggeAr(svg, x, h) {
  const ar = S.f.ar;
  const g = svg.append("g").attr("class", "skugge").attr("pointer-events", "none");
  if (ar) {
    if (ar[0] > A0) g.append("rect").attr("x", x(A0) - 4).attr("y", 0).attr("width", x(ar[0]) - x(A0) + 4 - (x(1) - x(0)) / 2).attr("height", h).attr("fill", "#000").attr("fill-opacity", 0.55);
    if (ar[1] < A1) g.append("rect").attr("x", x(ar[1]) + (x(1) - x(0)) / 2).attr("y", 0).attr("width", x(A1) - x(ar[1]) + 4).attr("height", h).attr("fill", "#000").attr("fill-opacity", 0.55);
  }
}
function skravur(svg, x, h, id) {
  const defs = svg.append("defs");
  const p = defs.append("pattern").attr("id", id).attr("patternUnits", "userSpaceOnUse").attr("width", 6).attr("height", 6).attr("patternTransform", "rotate(45)");
  p.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 6).attr("stroke", "#fff").attr("stroke-opacity", 0.25).attr("stroke-width", 2);
  svg.append("rect").attr("x", x(2025.5)).attr("y", 0).attr("width", Math.max(0, x(A1) - x(2025.5) + 4)).attr("height", h).attr("fill", `url(#${id})`).attr("pointer-events", "none");
}

function teiknBand(rows) {
  const svgEl = el.band.querySelector("svg");
  const W = el.band.clientWidth, H = el.band.clientHeight;
  if (W < 10 || H < 10) return;
  const m = marg();
  const svg = d3.select(svgEl).attr("width", W).attr("height", H);
  svg.selectAll("*").remove();
  const K = D.verk.tema.length;
  const keys = D.verk.tema.map((_, j) => j);
  const stack = d3.stack().keys(keys).value((r, k) => r[k]).order(() => ordning).offset(d3.stackOffsetSilhouette);
  const ser = stack(rows);
  const ghost = stack(korpusStabel);
  const tot = rows.map((r) => r.reduce((a, b) => a + b, 0));
  const korpusMax = d3.max(korpusStabel, (r) => r.reduce((a, b) => a + b, 0));
  const selMax = d3.max(tot) || 1;
  const tilpassa = selMax < korpusMax * 0.25;
  sisteTilpassa = tilpassa && T.harFilter();
  const ymax = (tilpassa ? selMax : korpusMax) * 0.55;
  const x = d3.scaleLinear().domain([A0, A1]).range([m.l, W - m.r]);
  const y = d3.scaleLinear().domain([-ymax, ymax]).range([H - 6, 8]);
  const area = d3.area().x((d, j) => x(AR[j])).y0((d) => y(d[0])).y1((d) => y(d[1])).curve(d3.curveMonotoneX);
  // ghost outline
  if (!tilpassa && T.harFilter()) {
    const top = ghost[ghost.length - 1], bot = ghost[0];
    const lo = d3.line().x((d, j) => x(AR[j])).y((d) => y(d)).curve(d3.curveMonotoneX);
    const ord = ordning;
    const topp = AR.map((_, j) => Math.max(...ord.map((k) => ghost[k][j][1])));
    const botn = AR.map((_, j) => Math.min(...ord.map((k) => ghost[k][j][0])));
    void top; void bot;
    svg.append("path").attr("d", lo(topp)).attr("fill", "none").attr("stroke", "#8a8a8a").attr("stroke-width", 1);
    svg.append("path").attr("d", lo(botn)).attr("fill", "none").attr("stroke", "#8a8a8a").attr("stroke-width", 1);
  }
  const g = svg.append("g").attr("class", "band");
  const paths = g.selectAll("path").data(ser).join("path")
    .attr("d", area)
    .attr("fill", (s) => PALETTE_TEMA[s.key])
    .attr("fill-opacity", (s) => (hoverTema == null || hoverTema === s.key ? (S.f.tema.size && !S.f.tema.has(D.verk.tema[s.key].k) ? 0.45 : 0.92) : 0.35))
    .attr("stroke", "#000").attr("stroke-width", 0.5)
    .style("cursor", "pointer");
  skuggeAr(svg, x, H);
  skravur(svg, x, H, "skravur-band");
  // the year axis is the brush strip right below; only the incomplete year is named here
  if (m.r >= 140) svg.append("text").attr("x", W - m.r + 10).attr("y", H - 4).text("2026: ufullstendig");
  // scale bar
  const pxPer = (y(0) - y(1));
  const nice = [5, 10, 20, 50, 100, 200, 500].find((v) => v * pxPer >= 18) || 500;
  const sb = svg.append("g").attr("transform", `translate(8,${12})`);
  sb.append("line").attr("x1", 4).attr("x2", 4).attr("y1", 0).attr("y2", nice * pxPer).attr("stroke", "#cfcfcf").attr("stroke-width", 2);
  sb.append("text").attr("x", 8).attr("y", Math.min(nice * pxPer, 60) / 2 + 4).text(`= ${nice} verk`);
  // labels at 2025, or chips
  const synlege = ser.filter((s) => tot.some((t) => t > 0) && s[2025 - A0][1] - s[2025 - A0][0] > 0.01);
  const kanEtikett = m.r >= 140 && (H - 34) / 16 >= synlege.length;
  const chipRad = ramme.flate.querySelector(".tid-temachipar");
  if (kanEtikett) {
    if (chipRad) chipRad.remove();
    const j = 2025 - A0;
    const items = synlege.map((s) => ({ s, y: y((s[j][0] + s[j][1]) / 2) }));
    const ys = plasserVertikalt(items, 16, 10, H - 24);
    if (ys) {
      const lg = svg.append("g");
      items.forEach((it, q) => {
        const x0 = x(2025), x1 = W - m.r + 10;
        lg.append("path").attr("d", `M${x0},${it.y}L${x1 - 4},${ys[q]}`).attr("stroke", PALETTE_TEMA[it.s.key]).attr("fill", "none").attr("stroke-width", 1);
        lg.append("text").attr("class", "etikett").attr("x", x1).attr("y", ys[q] + 4).text(kutt(D.verk.tema[it.s.key].namn, 22))
          .style("cursor", "pointer").on("click", () => T.veksle("tema", D.verk.tema[it.s.key].k));
      });
    }
  } else {
    let rad = chipRad;
    if (!rad) { rad = document.createElement("div"); rad.className = "tid-temachipar"; el.band.after(rad); rad.addEventListener("click", (e) => { const b = e.target.closest("button[data-tema]"); if (b) T.veksle("tema", b.dataset.tema); }); }
    rad.innerHTML = D.verk.tema.map((t, k) => `<button type="button" class="teikn-post" data-tema="${esc(t.k)}" aria-pressed="${S.f.tema.has(t.k)}"><span class="prikk" style="background:${PALETTE_TEMA[k]}"></span>${esc(t.namn)}</button>`).join("");
  }
  // interaction
  paths.on("pointermove", (ev, s) => {
    const [px] = d3.pointer(ev, svgEl);
    const a = Math.max(A0, Math.min(A1, Math.round(x.invert(px))));
    const j = a - A0;
    const c = rows[j][s.key], sum = tot[j] || 1;
    if (hoverTema !== s.key) { hoverTema = s.key; paths.attr("fill-opacity", (q) => (q.key === s.key ? 0.95 : 0.35)); }
    if (ev.pointerType === "mouse") tooltip.vis(`<div class="tt-tittel"><span class="prikk" style="background:${PALETTE_TEMA[s.key]}"></span>${esc(D.verk.tema[s.key].namn)}, ${a}</div><div class="tt-meta">${fmt(Math.round(c))} verk (${pst((100 * c) / sum)} % av året i utvalet)</div><div class="tt-fot">Klikk: vel tema · Skift-klikk: legg til</div>`, ev.clientX, ev.clientY);
  }).on("pointerleave", () => { hoverTema = null; tooltip.skjul(); paths.attr("fill-opacity", 0.92); })
    .on("click", (ev, s) => {
      const key = D.verk.tema[s.key].k;
      if (ev.pointerType && ev.pointerType !== "mouse") {
        if (kort.ope && kort.id === `band${s.key}`) { kort.lukk(); T.veksle("tema", key, { erstatt: true }); return; }
        kort.opne({ id: `band${s.key}`, html: `<div class="tt-tittel">${esc(D.verk.tema[s.key].namn)}</div>`, knappar: [{ tekst: "Vel", primar: true, gjer: () => T.veksle("tema", key, { erstatt: true }) }, { tekst: "Legg til", gjer: () => T.veksle("tema", key) }], x: ev.clientX, y: ev.clientY });
        return;
      }
      T.veksle("tema", key, { erstatt: !(ev.shiftKey || ev.ctrlKey || ev.metaKey) });
    });
  siste = { x, W, H, m };
}

let brush = null, brushStille = false;
function teiknStripe() {
  const svgEl = el.stripe.querySelector("svg");
  const W = el.stripe.clientWidth, H = el.stripe.clientHeight;
  if (W < 10) return;
  const m = marg();
  const x = d3.scaleLinear().domain([A0 - 0.5, A1 + 0.5]).range([m.l - (W - m.r - m.l) / (A1 - A0) / 2, W - m.r + (W - m.r - m.l) / (A1 - A0) / 2]);
  const svg = d3.select(svgEl).attr("width", W).attr("height", H);
  svg.selectAll("*").remove();
  svg.append("text").attr("x", m.l).attr("y", 11).attr("class", "stripe-tekst").text("Dra for å velje år");
  const ax = svg.append("g").attr("class", "akse").attr("transform", `translate(0,${H - 14})`);
  const steg = W < 600 ? 10 : 5;
  ax.call(d3.axisBottom(x).tickValues(AR.filter((a) => (a % steg === 0 && a <= 2020) || a === A1)).tickFormat(d3.format("d")).tickSize(3));
  ax.select(".domain").remove();
  brush = d3.brushX().extent([[m.l - 6, 14], [W - m.r + 6, H - 14]])
    .on("end", (ev) => {
      if (brushStille) return;
      if (!ev.selection) { if (ev.sourceEvent) T.endre((s) => { s.f.ar = null; }); return; }
      const [a, b] = ev.selection.map((px) => Math.round(x.invert(px)));
      const fra = Math.max(T.AR_MIN, Math.min(a, b)), til = Math.min(T.AR_MAX, Math.max(a, b));
      if (ev.sourceEvent) T.endre((s) => { s.f.ar = [fra === A0 ? T.AR_MIN : fra, til]; });
    });
  const g = svg.append("g").call(brush);
  if (S.f.ar) { brushStille = true; g.call(brush.move, [x(Math.max(A0, S.f.ar[0]) - 0.5), x(S.f.ar[1] + 0.5)]); brushStille = false; }
}

function teiknOrd() {
  const svgEl = el.ord.querySelector("svg");
  const W = el.ord.clientWidth, H = el.ord.clientHeight;
  const svg = d3.select(svgEl).attr("width", W).attr("height", Math.max(0, H));
  svg.selectAll("*").remove();
  // chips
  el.chipar.innerHTML = S.tid.termar.map((key, q) => {
    const vis = D.termIdx && D.termIdx.has(key) ? D.tidd.termar.vis[D.termIdx.get(key)] : key;
    const iFilter = S.f.term.has(key);
    return `<span class="ordchip" style="--f:${PALETTE_ORD[q % 6]}"><svg width="14" height="14" aria-hidden="true">${merkeSvg(q, 7, 7)}</svg>
      <button type="button" class="lenkeknapp" data-filterord="${esc(key)}" aria-pressed="${iFilter}" title="${iFilter ? "Fjern frå filteret" : "Bruk som filter"}">${esc(vis)}</button>
      <button type="button" class="chip-x" data-fjernord="${esc(key)}" aria-label="Fjern ordet ${esc(vis)}">×</button></span>`;
  }).join("");
  el.melding.textContent = ordStatus === "feil" ? "Ordlista kunne ikkje lastast." : ukjendMelding;
  if (ordStatus === "feil") {
    el.melding.innerHTML = `Ordlista kunne ikkje lastast. <button type="button" class="knapp liten" data-prov>Prøv igjen</button>`;
    el.melding.querySelector("button").addEventListener("click", lastOrd);
  }
  el.ordTom.hidden = true;
  tvSeg.el.classList.remove("framheva");
  if (ordStatus === "lastar") { el.ordTom.hidden = false; el.ordTom.textContent = "Lastar ordlista …"; return; }
  if (ordStatus !== "ok" || W < 10 || H < 30) return;
  const { kurver, m: mTot } = ordData();
  if (!kurver.length) { el.ordTom.hidden = false; el.ordTom.textContent = "Skriv eit ord over for å teikne ei kurve."; return; }
  const mm = marg();
  const x = d3.scaleLinear().domain([A0, A1]).range([mm.l, W - mm.r]);
  const ymax = d3.max(kurver, (k) => d3.max(k.pkt, (p) => p.v)) || 1;
  const y = d3.scaleLinear().domain([0, ymax * 1.1]).nice().range([H - 18, 10]);
  const ay = svg.append("g").attr("class", "akse").attr("transform", `translate(${mm.l},0)`);
  ay.call(d3.axisLeft(y).ticks(4).tickFormat((d) => (S.tid.tv === "del" ? `${d} %` : d)).tickSize(3));
  ay.select(".domain").remove();
  const ax = svg.append("g").attr("class", "akse").attr("transform", `translate(0,${H - 16})`);
  ax.call(d3.axisBottom(x).tickValues(W < 600 ? [1990, 2000, 2010, 2020] : [1990, 2000, 2010, 2020, 2026]).tickFormat(d3.format("d")).tickSize(3));
  ax.select(".domain").remove();
  skuggeAr(svg, x, H - 18);
  skravur(svg, x, H - 18, "skravur-ord");
  const noko = kurver.some((k) => k.pkt.some((p) => p.v != null));
  if (!noko) {
    el.ordTom.hidden = false;
    el.ordTom.textContent = "For få verk i utvalet til å teikne kurver (minst 20 per treårsvindauge). Prøv «Tal».";
    tvSeg.el.classList.add("framheva");
  }
  const line = d3.line().defined((p) => p.v != null).x((p) => x(p.a)).y((p) => y(p.v)).curve(d3.curveMonotoneX);
  const gl = svg.append("g");
  kurver.forEach((k, q) => {
    const f = PALETTE_ORD[q % 6];
    const heil = k.pkt.filter((p) => p.a <= 2025);
    const slutt = k.pkt.filter((p) => p.a >= 2025);
    const w = S.f.term.has(k.key) ? 3 : 2;
    gl.append("path").attr("d", line(heil)).attr("fill", "none").attr("stroke", f).attr("stroke-width", w).attr("stroke-dasharray", ORD_STREK[q % 6] || null);
    gl.append("path").attr("d", line(slutt)).attr("fill", "none").attr("stroke", f).attr("stroke-width", w).attr("stroke-dasharray", "3 3").attr("stroke-opacity", 0.8);
    for (const p of k.pkt) if (p.v != null && (p.a % 5 === 0 || p.a === 2025)) gl.append("g").attr("transform", `translate(${x(p.a)},${y(p.v)})`).html(merkeSvg(q, 0, 0));
    // wide invisible hit path
    gl.append("path").attr("d", line(k.pkt)).attr("fill", "none").attr("stroke", "transparent").attr("stroke-width", 14).style("cursor", "pointer")
      .on("click", (ev) => {
        if (ev.pointerType && ev.pointerType !== "mouse") {
          if (kort.ope && kort.id === `ord${k.key}`) { kort.lukk(); T.veksle("term", k.key); return; }
          kort.opne({ id: `ord${k.key}`, html: `<div class="tt-tittel">${esc(k.vis)}</div>`, knappar: [{ tekst: S.f.term.has(k.key) ? "Fjern frå filteret" : "Bruk som filter", primar: true, gjer: () => T.veksle("term", k.key) }], x: ev.clientX, y: ev.clientY });
          return;
        }
        T.veksle("term", k.key);
      });
  });
  // labels at line ends
  const items = kurver.map((k, q) => { const p = [...k.pkt].reverse().find((pp) => pp.v != null && pp.a <= 2025); return p ? { q, k, y: y(p.v), x: x(p.a) } : null; }).filter(Boolean);
  const ys = mm.r >= 140 ? plasserVertikalt(items, 16, 8, H - 20) : null;
  if (ys) items.forEach((it, j) => svg.append("text").attr("class", "etikett").attr("x", W - mm.r + 10).attr("y", ys[j] + 4).attr("fill", PALETTE_ORD[it.q % 6]).text(kutt(it.k.vis, 20)));
  // hover rule
  const regel = svg.append("line").attr("y1", 8).attr("y2", H - 18).attr("stroke", "#fff").attr("stroke-opacity", 0.5).attr("visibility", "hidden").attr("pointer-events", "none");
  svg.on("pointermove", (ev) => {
    const [px] = d3.pointer(ev, svgEl);
    if (px < mm.l || px > W - mm.r + 4) { regel.attr("visibility", "hidden"); tooltip.skjul(); return; }
    const a = Math.max(A0, Math.min(A1, Math.round(x.invert(px))));
    regel.attr("x1", x(a)).attr("x2", x(a)).attr("visibility", "visible");
    const j = a - A0;
    const rader = kurver.map((k, q) => {
      const p = k.pkt[j];
      const v = p.v == null ? "for få verk" : S.tid.tv === "del" ? `${pst(p.v, 1)} %` : fmt(p.v);
      return `<div class="tt-meta"><span class="prikk" style="background:${PALETTE_ORD[q % 6]}"></span>${esc(k.vis)}: ${fmt(p.h)} av ${fmt(mTot[j])} verk (${v})</div>`;
    }).join("");
    if (ev.pointerType === "mouse") tooltip.vis(`<div class="tt-tittel">${a}${a === 2026 ? " (ufullstendig)" : ""}</div>${rader}<div class="tt-fot">Klikk ei line: bruk ordet som filter</div>`, ev.clientX, ev.clientY);
  }).on("pointerleave", () => { regel.attr("visibility", "hidden"); tooltip.skjul(); });
}

function merkeSvg(q, cx, cy) {
  const f = PALETTE_ORD[q % 6], m = ORD_MERKE[q % 6], r = 4;
  switch (m) {
    case "sirkel": return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${f}"/>`;
    case "firkant": return `<rect x="${cx - r}" y="${cy - r}" width="${2 * r}" height="${2 * r}" fill="${f}"/>`;
    case "trekant": return `<path d="M${cx},${cy - r - 1}L${cx + r + 1},${cy + r}L${cx - r - 1},${cy + r}Z" fill="${f}"/>`;
    case "ruter": return `<path d="M${cx},${cy - r - 1}L${cx + r + 1},${cy}L${cx},${cy + r + 1}L${cx - r - 1},${cy}Z" fill="${f}"/>`;
    case "kryss": return `<path d="M${cx - r},${cy - r}L${cx + r},${cy + r}M${cx + r},${cy - r}L${cx - r},${cy + r}" stroke="${f}" stroke-width="2"/>`;
    default: return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${f}" stroke-width="2"/>`;
  }
}

function teiknMerk() {
  for (const box of [el.band, el.ord]) {
    if (!box) continue;
    const svg = d3.select(box.querySelector("svg"));
    svg.selectAll(".merkline").remove();
    if (merkAr == null || !siste || merkAr < A0) continue;
    const x = d3.scaleLinear().domain([A0, A1]).range([siste.m.l, siste.W - siste.m.r]);
    svg.append("line").attr("class", "merkline").attr("x1", x(merkAr)).attr("x2", x(merkAr)).attr("y1", 0).attr("y2", box.clientHeight - 16).attr("stroke", "#fff").attr("stroke-width", 1).attr("pointer-events", "none");
  }
}
void smal; void veldigSmal;
