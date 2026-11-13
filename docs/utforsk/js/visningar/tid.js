// Tid: themes as bands over time, and term curves for words the reader types.
import { esc, fmt, pst, kutt, PALETTE_TEMA, PALETTE_ORD, ORD_MERKE, ORD_STREK, termNokkel, fold, tween, rorsle, tooltip, kort, segmentert, plasserVertikalt, veldigSmal, smal, settInnhald, tekstBreidd, KL, BG } from "../hjelp.js?v=35";

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
let sisteSmaa = false;     // so few works per year that smoothing would invent shapes: steps instead
let undertrykkKlikk = false;

export default {
  id: "tid",
  filer: [],
  skript: [],
  async init(rot, api) {
    A = api; T = api.T; D = api.D; S = api.S; ramme = api.ramme; d3 = window.d3;
    ramme.flate.insertAdjacentHTML("beforeend", `
      <div class="tid">
        <div class="tid-band" role="group" aria-label="Klynger over tid. Dra sidelengs over diagrammet for å velje år."><svg></svg><div class="tid-dragboks" hidden></div></div>
        <div class="tid-stripe brushstripe"><svg aria-label="Dra for å velje år"></svg></div>
        <div class="tid-ordboks">
          <div class="ordfelt">
            <input type="text" class="ordinput" placeholder="Skriv eit ord, til dømes co-design" aria-label="Legg til eit ord" autocomplete="off" autocapitalize="off" spellcheck="false" role="combobox" aria-expanded="false" aria-controls="ordforslag" aria-autocomplete="list">
            <ul class="forslag ordforslag" id="ordforslag" role="listbox" aria-label="Ord i titlar" hidden></ul>
          </div>
          <div class="ordchipar"></div>
          <p class="ordmelding" aria-live="polite"></p>
        </div>
        <div class="tid-ord" role="group" aria-label="Ord over tid"><svg></svg><p class="ord-tom" hidden></p></div>
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
    el.melding.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.prov != null) { lastOrd(); return; }
      if (b.dataset.sokord) { const q = b.dataset.sokord; ukjendMelding = ""; T.endre((s) => { s.f.q = q; s.f.qv = false; s.f.qd = false; }); }
      // the errand "what is cited around this word, and how did it move": the same words in Siteringar
      if (b.dataset.sitord) { const q = b.dataset.sitord; ukjendMelding = ""; T.endre((s) => { s.f.q = q; s.f.qv = false; s.f.qd = false; s.vis = "siteringar"; s.sit.del = "saman"; }); }
    });
    new ResizeObserver(() => teikn(false)).observe(ramme.flate);
    bindBandDrag();
    lastOrd();
  },
  oppdater(s, e) {
    tvSeg.set(S.tid.tv);
    // Back to an entry without t= in the link: the default words again, not an empty panel
    if (ordStatus === "ok" && !S.tid.termarSett && !S.tid.termar.length) { T.endre((st) => { st.tid.termar = D.tidd.standard.slice(); }, { hist: "ingen" }); return; }
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
    if (S.tid.termar.length >= 6) { ukjendMelding = "Du kan samanlikne opptil seks ord. Fjern eitt først."; teikn(false); visOrdboks(); return; }
    T.endre((s) => { s.tid.termar = [...s.tid.termar, key]; s.tid.termarSett = true; });
    visOrdboks();
  };
  const provSkriven = () => {
    const q = inp.value.trim();
    if (!q || ordStatus !== "ok") return;
    const key = termNokkel(q);
    let t = D.termIdx.get(key);
    if (t == null) t = D.termIdx.get(key.replace(/ /g, ""));
    if (t != null) leggTil(t);
    else {
      // say how many titles do have the word, and offer them as a search: "tacit" is in 3 titles,
      // too few for a curve, but the reader still wants those works
      const n = titlarMed(q);
      const min = D.tidd.tal.min_df || 5;
      const tekst = !n ? `Ingen titlar har «${q}», så det blir inga kurve.`
        : n < min ? `«${q}» står i ${n === 1 ? "berre éin tittel" : `berre ${fmt(n)} titlar`}. Ei kurve treng minst ${min}.`
        : `«${q}» står i ${fmt(n)} titlar, så mange at ordet ikkje skil verka frå kvarandre, og det har inga kurve.`;
      ukjendMelding = { q, n, tekst };
      lukk(); teikn(false);
      visOrdboks();
    }
  };
  inp.addEventListener("input", () => { valt = -1; vis(); });
  // on a phone the word box sits below the fold: bring it and the curves up when the reader uses it
  inp.addEventListener("focus", () => { if (smal()) visOrdboks(); });
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

// Scroll the Tid column so the word box (message, chips) and the curves under it are in view.
// On a wide screen everything fits and nothing moves.
function visOrdboks() {
  const tid = el.band && el.band.parentElement;
  const boks = el.input && el.input.closest(".tid-ordboks");
  if (!tid || !boks || tid.scrollHeight <= tid.clientHeight + 1) return;
  const mal = Math.min(boks.offsetTop - 4, tid.scrollHeight - tid.clientHeight);
  if (Math.abs(tid.scrollTop - mal) < 2) return;
  if (tid.scrollTo) tid.scrollTo({ top: mal, behavior: rorsle.redusert ? "auto" : "smooth" });
  else tid.scrollTop = mal;
}

// Titles with every typed word as a word (or word prefix for words of 7 letters or more), as
// the search does. Used when a word is not in the word list.
let tittelOrd = null;
function titlarMed(q) {
  const toks = fold(q).split(/[^\p{L}\p{N}]+/u).filter((w) => w.length >= 2);
  if (!toks.length) return 0;
  if (!tittelOrd) tittelOrd = D.kol.tittel.map((t) => fold(t).replace(/[-'’]/g, "").split(/[^\p{L}\p{N}]+/u));
  let n = 0;
  for (const ord of tittelOrd) if (toks.every((t) => ord.some((w) => w === t || (t.length >= 7 && w.startsWith(t.slice(0, 6))) || w === t + "s"))) n++;
  return n;
}

const arTal = new Map();
function talAr(a) { if (!arTal.has(a)) { let c = 0; for (let i = 0; i < D.n; i++) if (D.ar[i] === a) c++; arTal.set(a, c); } return arTal.get(a); }

// ---------- data ----------
function bandData() {
  const u = T.utvalUtan(["ar"]);
  const K = D.verk.tema.length;
  const rows = AR.map(() => new Float64Array(K));
  let foer = 0, med = 0;
  for (let i = 0; i < D.n; i++) {
    if (!u[i]) continue;
    const a = D.ar[i];
    if (a >= A0) rows[a - A0][D.tema[i]]++;
  }
  // works before 1990 that are in the selection (with the year filter) and so not drawn
  for (let i = 0; i < D.n; i++) if (T.utval[i]) { if (D.ar[i] >= A0) med++; else foer++; }
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
  // shares from years with a handful of works jump about (co-design 2.7 % in 1996 from one or
  // two titles): the curve is faint up to the first year with at least 20 works in the selection
  let j0 = m.findIndex((c) => c >= 20);
  if (j0 < 0) j0 = AR.length;
  return { kurver, m, sikkerFra: AR[Math.min(j0, AR.length - 1)], j0 };
}

// ---------- drawing ----------
let namnBreidd = 0;
function marg() {
  // The right margin holds the band labels, wide enough for the longest theme name in full
  // (no ellipsis). Where that would leave the bands under 360 px, the names go to a chip row.
  const w = el.band.clientWidth;
  if (!namnBreidd) namnBreidd = Math.ceil(Math.max(...D.verk.tema.map((t) => tekstBreidd(t.namn, "12px Literata, Georgia, serif"))));
  const lw = namnBreidd + 26;
  const hogre = w - lw - 44 >= 360 ? lw : 16;
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
  ramme.linje.textContent = `Verk per år etter klynge${foer ? ` (${fmt(foer)} verk frå før 1990 er ikkje med)` : ""}. Under: delen av titlane som har ordet, glatta over tre år.`;
  const meirOpe = !!(ramme.teikn.querySelector(".teikn-meir") || {}).open;
  settInnhald(ramme.teikn, `<span class="teikn-merk">Bandbreidd: verk per år.${sisteSmaa ? " Utvalet er lite, så banda står som trapper år for år, utan glatting." : ""} ${sisteTilpassa ? "Skalaen er tilpassa det vesle utvalet, så heile korpuset er ikkje teikna som grå kontur." : T.harFilter() ? "Grå kontur: heile korpuset." : ""} Skravert: 2026 er ufullstendig (${fmt(talAr(2026))} verk mot ${fmt(talAr(2025))} i 2025: innhaustinga er ikkje ferdig, året er ikkje lite).</span>
    <details class="teikn-meir"><summary>Kva som kan forme banda og kurvene</summary><span class="teikn-merk">Dei to siste klyngene har mest arkivverk, og arkivdelen skiftar frå år til år (Nordes kjem annakvart år), så eit skift i banda kan vere eit skift i kva kjeldene dekkjer.</span>
    <span class="teikn-merk">Orda er talde per språkform: «service design» og «tjenestedesign» er to ord. Eit ord manglar når det står i færre enn ${D.tidd ? D.tidd.tal.min_df : 5} titlar. Ei kurve startar der eit treårsvindauge har minst 20 verk (for heile korpuset i 1993), og ho er blek fram til første år med minst 20 verk i utvalet, for delen i år med få verk kan hoppe mykje.</span></details>`);
  if (meirOpe) ramme.teikn.querySelector(".teikn-meir").open = true;
  void med;
}

function skuggeAr(svg, x, h) {
  const ar = S.f.ar;
  const g = svg.append("g").attr("class", "skugge").attr("pointer-events", "none");
  if (ar) {
    if (ar[0] > A0) g.append("rect").attr("x", x(A0) - 4).attr("y", 0).attr("width", x(ar[0]) - x(A0) + 4 - (x(1) - x(0)) / 2).attr("height", h).attr("fill", BG).attr("fill-opacity", 0.55);
    if (ar[1] < A1) g.append("rect").attr("x", x(ar[1]) + (x(1) - x(0)) / 2).attr("y", 0).attr("width", x(A1) - x(ar[1]) + 4).attr("height", h).attr("fill", BG).attr("fill-opacity", 0.55);
  }
}
function skravur(svg, x, h, id) {
  const defs = svg.append("defs");
  const p = defs.append("pattern").attr("id", id).attr("patternUnits", "userSpaceOnUse").attr("width", 6).attr("height", 6).attr("patternTransform", "rotate(45)");
  p.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 6).attr("stroke", KL.ring).attr("stroke-opacity", 0.25).attr("stroke-width", 2);
  svg.append("rect").attr("x", x(2025.5)).attr("y", 0).attr("width", Math.max(0, x(A1) - x(2025.5) + 4)).attr("height", h).attr("fill", `url(#${id})`).attr("pointer-events", "none");
}

function teiknBand(rows) {
  const svgEl = el.band.querySelector("svg");
  const W = el.band.clientWidth, H = el.band.clientHeight;
  if (W < 10 || H < 10) return;
  const m = marg();
  const fa = document.activeElement;
  const fokusTema = fa && svgEl.contains(fa) && fa.dataset ? fa.dataset.tema : null;
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
  // a small selection (at most a dozen works in its busiest year) is drawn as steps per year:
  // a smoothed stream through 0, 1, 0 makes diamonds that are not in the data
  sisteSmaa = T.harFilter() && selMax <= 12;
  const area = d3.area().x((d, j) => x(AR[j])).y0((d) => y(d[0])).y1((d) => y(d[1])).curve(sisteSmaa ? d3.curveStep : d3.curveMonotoneX);
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
    .attr("stroke", KL.kontur).attr("stroke-width", 0.5)
    .style("cursor", "pointer");
  skuggeAr(svg, x, H);
  skravur(svg, x, H, "skravur-band");
  // the year axis is the brush strip right below; only the incomplete year is named here
  if (m.r >= 140) svg.append("text").attr("x", W - m.r + 10).attr("y", H - 4).text("2026: ufullstendig");
  // scale bar
  const pxPer = (y(0) - y(1));
  const nice = [5, 10, 20, 50, 100, 200, 500].find((v) => v * pxPer >= 18) || 500;
  const sb = svg.append("g").attr("transform", `translate(8,${12})`);
  sb.append("line").attr("x1", 4).attr("x2", 4).attr("y1", 0).attr("y2", nice * pxPer).attr("stroke", KL.bar).attr("stroke-width", 2);
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
        const t = D.verk.tema[it.s.key];
        const valt = S.f.tema.has(t.k);
        // the names are buttons for the keyboard too (Tab, Enter or space)
        const tx = lg.append("text").attr("class", `etikett temaetikett${valt ? " valt" : ""}`).attr("x", x1).attr("y", ys[q] + 4).text(t.namn)
          .attr("tabindex", 0).attr("role", "button").attr("aria-pressed", String(valt)).attr("data-tema", t.k)
          .attr("aria-label", `${t.namn}: vel klynga`);
        tx.style("cursor", "pointer")
          .on("click", (ev) => { ev.stopPropagation(); T.veksle("tema", t.k, { erstatt: !(ev.shiftKey || ev.ctrlKey || ev.metaKey) }); })
          .on("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); T.veksle("tema", t.k, { erstatt: !ev.shiftKey }); } });
      });
      // keep keyboard focus on the same name after the redraw
      if (fokusTema) { const n = svgEl.querySelector(`[data-tema="${CSS.escape(fokusTema)}"]`); if (n) n.focus({ preventScroll: true }); }
    }
  } else {
    let rad = chipRad;
    if (!rad) { rad = document.createElement("div"); rad.className = "tid-temachipar"; el.band.after(rad); rad.addEventListener("click", (e) => { const b = e.target.closest("button[data-tema]"); if (b) T.veksle("tema", b.dataset.tema); }); }
    settInnhald(rad, D.verk.tema.map((t, k) => `<button type="button" class="teikn-post" data-tema="${esc(t.k)}" aria-pressed="${S.f.tema.has(t.k)}"><span class="prikk" style="background:${PALETTE_TEMA[k]}"></span>${esc(t.namn)}</button>`).join(""));
  }
  // interaction
  let tipsKey = null;
  paths.on("pointermove", (ev, s) => {
    const [px] = d3.pointer(ev, svgEl);
    const a = Math.max(A0, Math.min(A1, Math.round(x.invert(px))));
    const j = a - A0;
    const c = rows[j][s.key], sum = tot[j] || 1;
    if (hoverTema !== s.key) { hoverTema = s.key; paths.attr("fill-opacity", (q) => (q.key === s.key ? 0.95 : 0.35)); }
    // the text is built once per band and year; between those only the box moves
    const key = `${s.key}|${a}`;
    if (key === tipsKey && tooltip.synleg) { tooltip.flytt(ev.clientX, ev.clientY); return; }
    tipsKey = key;
    if (ev.pointerType === "mouse") tooltip.vis(`<div class="tt-tittel"><span class="prikk" style="background:${PALETTE_TEMA[s.key]}"></span>${esc(D.verk.tema[s.key].namn)}, ${a}</div><div class="tt-meta">${fmt(Math.round(c))} verk (${pst((100 * c) / sum)} % av året i utvalet)</div><div class="tt-fot">Klikk: vel klynge · Skift-klikk: legg til</div>`, ev.clientX, ev.clientY);
  }).on("pointerleave", () => { hoverTema = null; tipsKey = null; tooltip.skjul(); paths.attr("fill-opacity", (q) => (S.f.tema.size && !S.f.tema.has(D.verk.tema[q.key].k) ? 0.45 : 0.92)); })
    .on("click", (ev, s) => {
      if (undertrykkKlikk) return;
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
  settInnhald(el.chipar, S.tid.termar.map((key, q) => {
    const vis = D.termIdx && D.termIdx.has(key) ? D.tidd.termar.vis[D.termIdx.get(key)] : key;
    const iFilter = S.f.term.has(key);
    return `<span class="ordchip" style="--f:${PALETTE_ORD[q % 6]}"><svg width="14" height="14" aria-hidden="true">${merkeSvg(q, 7, 7)}</svg>
      <button type="button" class="lenkeknapp" data-filterord="${esc(key)}" aria-pressed="${iFilter}" title="${iFilter ? "Fjern frå filteret" : "Bruk som filter"}">${esc(vis)}</button>
      <button type="button" class="chip-x" data-fjernord="${esc(key)}" aria-label="Fjern ordet ${esc(vis)}">×</button></span>`;
  }).join(""));
  if (ordStatus === "feil") settInnhald(el.melding, `Ordlista kunne ikkje lastast. <button type="button" class="knapp liten" data-prov>Prøv igjen</button>`);
  else if (ukjendMelding && typeof ukjendMelding === "object") {
    const u = ukjendMelding;
    settInnhald(el.melding, `${esc(u.tekst)}${u.n ? ` <button type="button" class="knapp liten" data-sokord="${esc(u.q)}">Vis ${u.n === 1 ? "verket" : `dei ${fmt(u.n)} verka`}</button> <button type="button" class="knapp liten" data-sitord="${esc(u.q)}" title="Opnar Siteringar med verka som har ordet i tittelen: kva dei siterer, og kven som siterer det over tid">Kva siterer dei?</button>` : ""}`);
  } else settInnhald(el.melding, esc(ukjendMelding || ""));
  el.ordTom.hidden = true;
  tvSeg.el.classList.remove("framheva");
  if (ordStatus === "lastar") { el.ordTom.hidden = false; el.ordTom.textContent = "Lastar ordlista …"; return; }
  if (ordStatus !== "ok" || W < 10 || H < 30) return;
  const { kurver, m: mTot, sikkerFra } = ordData();
  const bleik = S.tid.tv === "del" ? sikkerFra : A0;
  if (!kurver.length) { el.ordTom.hidden = false; el.ordTom.textContent = "Skriv eit ord over for å teikne ei kurve."; return; }
  const mm = marg();
  const x = d3.scaleLinear().domain([A0, A1]).range([mm.l, W - mm.r]);
  // the scale follows the years that carry weight; the faint early part is clipped to it
  const ymax = d3.max(kurver, (k) => d3.max(k.pkt, (p) => (p.a >= bleik ? p.v : null))) || d3.max(kurver, (k) => d3.max(k.pkt, (p) => p.v)) || 1;
  const y = d3.scaleLinear().domain([0, ymax * 1.1]).nice().range([H - 18, 10]);
  const ay = svg.append("g").attr("class", "akse").attr("transform", `translate(${mm.l},0)`);
  ay.call(d3.axisLeft(y).ticks(4).tickFormat((d) => (S.tid.tv === "del" ? `${d} %` : d)).tickSize(3));
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
    const tidleg = k.pkt.filter((p) => p.a <= bleik && p.a <= 2025);
    const heil = k.pkt.filter((p) => p.a >= bleik && p.a <= 2025);
    const slutt = k.pkt.filter((p) => p.a >= 2025);
    const w = S.f.term.has(k.key) ? 3 : 2;
    const ytop = y.domain()[1];
    if (tidleg.length > 1) gl.append("path").attr("d", line(tidleg.map((p) => (p.v != null && p.v > ytop ? { ...p, v: ytop } : p)))).attr("fill", "none").attr("stroke", f).attr("stroke-width", 1.5).attr("stroke-opacity", 0.3).attr("class", "bleik");
    gl.append("path").attr("d", line(heil)).attr("fill", "none").attr("stroke", f).attr("stroke-width", w).attr("stroke-dasharray", ORD_STREK[q % 6] || null);
    gl.append("path").attr("d", line(slutt)).attr("fill", "none").attr("stroke", f).attr("stroke-width", w).attr("stroke-dasharray", "3 3").attr("stroke-opacity", 0.8);
    for (const p of k.pkt) if (p.v != null && p.a >= bleik && (p.a % 5 === 0 || p.a === 2025)) gl.append("g").attr("transform", `translate(${x(p.a)},${y(p.v)})`).html(merkeSvg(q, 0, 0));
    // wide invisible hit path
    gl.append("path").attr("d", line(k.pkt.map((p) => (p.v != null && p.v > ytop ? { ...p, v: ytop } : p)))).attr("fill", "none").attr("stroke", "transparent").attr("stroke-width", 14).style("cursor", "pointer")
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
  const ys = mm.r >= 140 ? plasserVertikalt(items, 17, 8, H - 20) : null;
  if (ys) items.forEach((it, j) => {
    // a thin leader from the end of the line to its label, which is spread to keep 17 px apart
    svg.append("path").attr("d", `M${it.x + 5},${it.y}L${W - mm.r + 6},${ys[j]}`).attr("stroke", PALETTE_ORD[it.q % 6]).attr("stroke-opacity", 0.6).attr("fill", "none").attr("pointer-events", "none");
    svg.append("text").attr("class", "etikett").attr("x", W - mm.r + 10).attr("y", ys[j] + 4).attr("fill", PALETTE_ORD[it.q % 6]).text(kutt(it.k.vis, mm.r >= 200 ? 30 : 20));
  });
  // hover rule
  const regel = svg.append("line").attr("y1", 8).attr("y2", H - 18).attr("stroke", KL.ring).attr("stroke-opacity", 0.5).attr("visibility", "hidden").attr("pointer-events", "none");
  let sistAr = null;
  svg.on("pointermove", (ev) => {
    const [px] = d3.pointer(ev, svgEl);
    if (px < mm.l || px > W - mm.r + 4) { regel.attr("visibility", "hidden"); tooltip.skjul(); sistAr = null; return; }
    const a = Math.max(A0, Math.min(A1, Math.round(x.invert(px))));
    // one rebuild per year, not per pixel
    if (a === sistAr && tooltip.synleg) { tooltip.flytt(ev.clientX, ev.clientY); return; }
    sistAr = a;
    regel.attr("x1", x(a)).attr("x2", x(a)).attr("visibility", "visible");
    const j = a - A0;
    const rader = kurver.map((k, q) => {
      const p = k.pkt[j];
      const v = p.v == null ? "for få verk" : S.tid.tv === "del" ? `${pst(p.v, 1)} %` : fmt(p.v);
      return `<div class="tt-meta"><span class="prikk" style="background:${PALETTE_ORD[q % 6]}"></span>${esc(k.vis)}: ${fmt(p.h)} av ${fmt(mTot[j])} verk (${v})</div>`;
    }).join("");
    const fa = a < bleik ? `<div class="tt-fot">Under 20 verk dette året: delen er usikker (blek line).</div>` : "";
    if (ev.pointerType === "mouse") tooltip.vis(`<div class="tt-tittel">${a}${a === 2026 ? " (ufullstendig)" : ""}</div>${rader}${fa}<div class="tt-fot">Klikk ei line: bruk ordet som filter</div>`, ev.clientX, ev.clientY);
  }).on("pointerleave", () => { regel.attr("visibility", "hidden"); tooltip.skjul(); });
}

// Drag sideways over the band chart to choose years (the strip below does the same).
function bindBandDrag() {
  const boks = el.band.querySelector(".tid-dragboks");
  let drag = null;
  const lokal = (ev) => ev.clientX - el.band.getBoundingClientRect().left;
  el.band.addEventListener("pointerdown", (ev) => {
    if (ev.button || !siste) return;
    drag = { id: ev.pointerId, x0: lokal(ev), x1: lokal(ev), aktiv: false };
  });
  el.band.addEventListener("pointermove", (ev) => {
    if (!drag || ev.pointerId !== drag.id) return;
    // the button was released somewhere we did not hear about: no phantom year selection
    if (ev.pointerType === "mouse" && ev.buttons === 0) { drag = null; boks.hidden = true; return; }
    drag.x1 = lokal(ev);
    if (!drag.aktiv && Math.abs(drag.x1 - drag.x0) > 6) {
      drag.aktiv = true;
      try { el.band.setPointerCapture(ev.pointerId); } catch (e) { /* pointer gone */ }
      tooltip.skjul();
    }
    if (!drag.aktiv) return;
    const { m, W } = siste;
    const a = Math.max(m.l, Math.min(drag.x0, drag.x1)), b = Math.min(W - m.r, Math.max(drag.x0, drag.x1));
    boks.hidden = false;
    boks.style.left = `${a}px`; boks.style.width = `${Math.max(1, b - a)}px`;
    const [fa, ta] = arFor(a, b);
    boks.textContent = `${fa} til ${ta}`;
    ev.preventDefault();
  });
  const slutt = (ev) => {
    if (!drag || ev.pointerId !== drag.id) return;
    const d = drag;
    drag = null;
    boks.hidden = true;
    if (!d.aktiv || ev.type === "pointercancel") return;
    undertrykkKlikk = true;
    setTimeout(() => { undertrykkKlikk = false; }, 0);
    const [fa, ta] = arFor(Math.min(d.x0, d.x1), Math.max(d.x0, d.x1));
    T.endre((s) => { s.f.ar = [fa === A0 ? T.AR_MIN : fa, ta]; });
  };
  el.band.addEventListener("pointerup", slutt);
  el.band.addEventListener("pointercancel", slutt);
  window.addEventListener("pointerup", (ev) => { if (drag && ev.pointerId === drag.id && !el.band.contains(ev.target)) { if (drag.aktiv) slutt(ev); else { drag = null; boks.hidden = true; } } });
}
function arFor(a, b) {
  const x = siste.x;
  const fa = Math.max(A0, Math.min(A1, Math.round(x.invert(a)))), ta = Math.max(A0, Math.min(A1, Math.round(x.invert(b))));
  return [Math.min(fa, ta), Math.max(fa, ta)];
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
    svg.append("line").attr("class", "merkline").attr("x1", x(merkAr)).attr("x2", x(merkAr)).attr("y1", 0).attr("y2", box.clientHeight - 16).attr("stroke", KL.ring).attr("stroke-width", 1).attr("pointer-events", "none");
  }
}
void smal; void veldigSmal;
