// Filter bar: search with term suggestions, year slider with histogram, Nordic land
// toggles, popovers (tema, kanal, type), lag, PDF; chips row with count; mobile panel.
import { esc, fmt, fold, termNokkel, kutt, PALETTE_TEMA, KGR_FARGE, annonser, smal, settInnhald } from "./hjelp.js?v=23";
import * as T from "./tilstand.js?v=23";

const { S, D } = T;
let el = {};
let opnePop = null;

export function init() {
  const rot = document.getElementById("filterlinje");
  const v = D.verk;
  rot.innerHTML = `
    <div class="sokfelt">
      <input type="search" id="sok" class="sok" placeholder="Klargjer søk …" aria-label="Søk i tittel, forfattar, kanal, institusjon"
        autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" enterkeyhint="search" aria-describedby="sokinfo" aria-autocomplete="list" aria-controls="sokforslag">
      <div class="sok-info" id="sokinfo" aria-live="off"></div>
      <ul class="forslag" id="sokforslag" role="listbox" aria-label="Ord i titlar" hidden></ul>
    </div>
    <button type="button" class="knapp filterknapp" id="filterknapp" aria-expanded="false" aria-controls="filterpanel">Filter</button>
    <div class="filterpanel" id="filterpanel" role="group" aria-label="Filter">
      <div class="panel-topp"><span class="panel-tittel">Filter</span><button type="button" class="knapp" id="panelferdig">Ferdig</button></div>
      <div class="kontroll kontroll-ar" id="arkontroll"></div>
      <div class="kontroll kontroll-land" role="group" aria-label="Nordisk land" title="Nordisk land verket høyrer til, ikkje forfattaren sitt land">
        <span class="kontroll-namn">Nordisk land</span>
        <div class="toggles" id="landtoggles">
          ${["NO", "SE", "DK", "FI", "IS", "X"].map((c) => `<button type="button" class="toggle" data-land="${c}" aria-pressed="false"><span>${c === "X" ? "Ukjend" : c}</span><span class="tal" data-tal></span></button>`).join("")}
        </div>
      </div>
      ${["tema", "kanal", "type"].map((p) => `
        <div class="kontroll kontroll-pop" data-pop="${p}">
          <button type="button" class="knapp popknapp" id="popknapp-${p}" aria-expanded="false" aria-controls="pop-${p}">${p === "tema" ? "Tema" : p === "kanal" ? "Kanal" : "Type"}<span class="aktivtal" data-aktivtal></span></button>
          <div class="popover" id="pop-${p}" role="group" aria-label="${p === "tema" ? "Tema" : p === "kanal" ? "Kanal" : "Type"}" hidden></div>
        </div>`).join("")}
      <div class="kontroll kontroll-lag" role="group" aria-label="Lag">
        <span class="kontroll-namn">Lag</span>
        <div class="toggles">
          <button type="button" class="toggle" data-lag="openalex" aria-pressed="false"><span>OpenAlex</span><span class="tal" data-tal></span></button>
          <button type="button" class="toggle" data-lag="arkiv" aria-pressed="false"><span>Arkiv</span><span class="tal" data-tal></span></button>
        </div>
      </div>
      <div class="kontroll kontroll-pdf">
        <button type="button" class="toggle" id="pdftoggle" aria-pressed="false" title="Verk med ein stadfest open PDF. Talet tel verk, ikkje filer: same PDF kan høyre til to verk (til dømes same artikkel i arkivet og i OpenAlex)."><span>Berre open PDF</span><span class="tal" data-tal></span></button>
      </div>
    </div>`;
  el = {
    rot, sok: rot.querySelector("#sok"), sokinfo: rot.querySelector("#sokinfo"), forslag: rot.querySelector("#sokforslag"),
    knapp: rot.querySelector("#filterknapp"), panel: rot.querySelector("#filterpanel"),
    land: rot.querySelector("#landtoggles"), pdf: rot.querySelector("#pdftoggle"),
  };
  el.slider = lagArSlider(rot.querySelector("#arkontroll"), { id: "fl" });

  // search
  let sokTid = 0, slutTid = 0, ko = null;
  const brukSok = (verdi) => {
    clearTimeout(sokTid);
    sokTid = setTimeout(() => {
      if (!T.sokKlar()) { ko = verdi; return; }
      T.endre((s) => { const nq = verdi.trim(); if (nq !== s.f.q) s.f.qv = false; s.f.q = nq; }, { hist: "kont:q", utsett: 300 });
      clearTimeout(slutTid);
      slutTid = setTimeout(() => T.avsluttGest("q"), 1500);
    }, 200);
  };
  el.brukKo = () => { if (ko != null) { const q = ko; ko = null; T.endre((s) => { s.f.q = q.trim(); s.f.qv = false; }, { hist: "kont:q", utsett: 300 }); } el.sok.placeholder = "Søk i tittel, forfattar, kanal, institusjon"; };
  el.sok.addEventListener("input", () => { brukSok(el.sok.value); visForslag(); });
  // suggestions: words in titles (tid.json) and cited works (siteringar.json), loaded on first focus
  el.sok.addEventListener("focus", () => { T.sikre("tid.json").then(() => visForslag()); T.sikre("siteringar.json").then(() => visForslag()); });
  el.sok.addEventListener("blur", () => { T.avsluttGest("q"); setTimeout(() => { if (!el.forslag.contains(document.activeElement)) lukkForslag(); }, 150); });
  el.sok.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" && !el.forslag.hidden) { const b = el.forslag.querySelector("button"); if (b) { b.focus(); e.preventDefault(); } }
    else if (e.key === "Enter") { clearTimeout(sokTid); if (T.sokKlar()) T.endre((s) => { const nq = el.sok.value.trim(); if (nq !== s.f.q) s.f.qv = false; s.f.q = nq; }); T.avsluttGest("q"); lukkForslag(); }
  });
  el.avbrytSok = () => { clearTimeout(sokTid); clearTimeout(slutTid); ko = null; };
  el.forslag.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-term], button[data-kanon]");
    if (!b) return;
    if (b.dataset.kanon) veljKanon(b.dataset.kanon); else veljTerm(b.dataset.term);
  });
  el.forslag.addEventListener("keydown", (e) => {
    const bs = [...el.forslag.querySelectorAll("button")];
    const i = bs.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { (bs[i + 1] || bs[i]).focus(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { (i > 0 ? bs[i - 1] : el.sok).focus(); e.preventDefault(); }
  });

  // land, lag, pdf
  el.land.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-land]");
    if (b) T.veksle("land", b.dataset.land);
  });
  rot.querySelector(".kontroll-lag").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-lag]");
    if (b) T.veksle("lag", b.dataset.lag);
  });
  el.pdf.addEventListener("click", () => { T.endre((s) => { s.f.pdf = !s.f.pdf; }); if (S.f.pdf) document.dispatchEvent(new CustomEvent("utforsk:lenker")); });

  // popovers
  for (const k of rot.querySelectorAll(".kontroll-pop")) {
    const p = k.dataset.pop;
    const b = k.querySelector(".popknapp");
    b.addEventListener("click", () => (opnePop === p && !erPanel() ? lukkPop(true) : opnePopover(p)));
    k.querySelector(".popover").addEventListener("focusout", (e) => {
      if (erPanel()) return;
      if (!k.contains(e.relatedTarget) && e.relatedTarget) lukkPop(false);
    });
    k.querySelector(".popover").addEventListener("change", (e) => {
      const c = e.target.closest("input[type=checkbox][data-dim]");
      if (c) T.veksle(c.dataset.dim, c.value);
    });
    k.querySelector(".popover").addEventListener("input", (e) => {
      if (e.target.matches(".kanalsok")) teiknPop("kanal");
    });
  }
  document.addEventListener("pointerdown", (e) => {
    if (opnePop && !erPanel() && !e.target.closest(".kontroll-pop")) lukkPop(false);
  });

  // mobile panel
  el.knapp.addEventListener("click", () => opnePanel(true));
  rot.querySelector("#panelferdig").addEventListener("click", () => opnePanel(false));

  // chips row
  const rad = document.getElementById("chiprad");
  rad.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.fjern) { T.fjern(b.dataset.fjern, b.dataset.verdi || null); return; }
    if (b.id === "nullstill") { T.nullstillFilter(); return; }
    if (b.dataset.prov) T.provIgjen(b.dataset.prov);
    if (b.dataset.qv) { T.endre((s) => { s.f.qv = b.dataset.qv === "1"; }); return; }
    if (b.dataset.frase) { if (el.avbrytSok) el.avbrytSok(); el.sok.value = ""; T.endre((s) => { s.f.term.add(b.dataset.frase); s.f.q = ""; }); }
  });
  oppdater();
}

const erPanel = () => smal();

export function opnePanel(ope) {
  el.panel.classList.toggle("ope", ope);
  el.knapp.setAttribute("aria-expanded", String(ope));
  document.body.classList.toggle("panel-ope", ope);
  if (ope) {
    for (const p of ["tema", "kanal", "type"]) teiknPop(p);
    el.panel.querySelector("#panelferdig").focus();
  } else el.knapp.focus();
}
export const panelOpe = () => el.panel && el.panel.classList.contains("ope");

function opnePopover(p) {
  if (opnePop && opnePop !== p) lukkPop(false);
  opnePop = p;
  const k = el.rot.querySelector(`.kontroll-pop[data-pop="${p}"]`);
  k.querySelector(".popknapp").setAttribute("aria-expanded", "true");
  const pop = k.querySelector(".popover");
  pop.hidden = false;
  teiknPop(p);
  const f = pop.querySelector("input");
  if (f) f.focus();
}
export function lukkPop(fokus) {
  if (!opnePop) return false;
  const k = el.rot.querySelector(`.kontroll-pop[data-pop="${opnePop}"]`);
  k.querySelector(".popknapp").setAttribute("aria-expanded", "false");
  if (!erPanel()) k.querySelector(".popover").hidden = true;
  if (fokus) k.querySelector(".popknapp").focus();
  opnePop = null;
  return true;
}
export const popOpe = () => !!opnePop;

function teiknPop(p) {
  const pop = document.getElementById(`pop-${p}`);
  if (!pop || (pop.hidden && !erPanel())) return;
  const v = D.verk;
  // Boxes are only replaced when their content changed, and keyboard focus stays on the same
  // checkbox: a toggled box is never destroyed under the reader's hand.
  if (p === "tema") {
    const c = T.fasettal("tema");
    settInnhald(pop, `<p class="pop-tittel">Tema</p>` + v.tema.map((t, j) => `
      <label class="sjekk"><input type="checkbox" data-dim="tema" value="${esc(t.k)}" ${S.f.tema.has(t.k) ? "checked" : ""}>
      <span class="prikk" style="background:${PALETTE_TEMA[j]}"></span><span class="sjekk-namn">${esc(t.namn)}</span><span class="tal" title="${esc(lagDel(j))}">${fmt(c.get(t.k) || 0)}</span></label>`).join("")
      + `<p class="pop-merk">Tema er grupper av verk med like titlar, kanalar og emneord, ikkje emne sett av nokon. Nokre tema er mest arkivverk eller mest norskspråklege (sjå talet med musa over), så å velje dei er nesten å velje lag eller språk.</p>`);
    synkSjekk(pop, "tema");
  } else if (p === "type") {
    const c = T.fasettal("type");
    settInnhald(pop, `<p class="pop-tittel">Type</p>` + v.typar.map((t) => `
      <label class="sjekk"><input type="checkbox" data-dim="type" value="${esc(t.k)}" ${S.f.type.has(t.k) ? "checked" : ""}>
      <span class="sjekk-namn">${esc(t.namn)}</span><span class="tal">${fmt(c.get(t.k) || 0)}</span></label>`).join("")
      + `<p class="pop-merk">«Ukjend»: arkivverk der kjelda ikkje oppgir type. Alle OpenAlex-verk har type.</p>`);
    synkSjekk(pop, "type");
  } else if (p === "kanal") {
    if (!pop.querySelector(".kanalsok")) {
      pop.innerHTML = `<p class="pop-tittel">Kanaltype</p><div class="kgrliste"></div><p class="pop-tittel">Kanal</p>
        <input type="search" class="kanalsok" placeholder="Skriv for å finne ein kanal" aria-label="Finn kanal" autocomplete="off">
        <div class="kanalliste"></div><p class="pop-merk kanal-fleire"></p>
        <p class="pop-merk">${fmt(utanKanal())} verk har ingen kanal i dataa (mest arkivverk). Same kanal kan stå med fleire skrivemåtar.</p>`;
    }
    const cg = T.fasettal("kgr"), ck = T.fasettal("kanal");
    const fq = fold(pop.querySelector(".kanalsok").value);
    let liste = v.kanalar.map((k, j) => ({ k, j, c: ck.get(k.k) || 0 }));
    if (fq) liste = liste.filter((x) => fold(x.k.namn).includes(fq));
    liste.sort((a, b) => (S.f.kanal.has(b.k.k) - S.f.kanal.has(a.k.k)) || b.c - a.c || a.j - b.j);
    settInnhald(pop.querySelector(".kgrliste"), v.kanalgrupper.map((g) => `
      <label class="sjekk"><input type="checkbox" data-dim="kgr" value="${esc(g.k)}" ${S.f.kgr.has(g.k) ? "checked" : ""}>
      <span class="prikk" style="background:${KGR_FARGE[g.k] || "#9a9a9a"}"></span><span class="sjekk-namn">${esc(g.namn)}</span><span class="tal">${fmt(cg.get(g.k) || 0)}</span></label>`).join(""));
    settInnhald(pop.querySelector(".kanalliste"), liste.slice(0, 50).map((x) => `
      <label class="sjekk"><input type="checkbox" data-dim="kanal" value="${esc(x.k.k)}" ${S.f.kanal.has(x.k.k) ? "checked" : ""}>
      <span class="sjekk-namn">${esc(kutt(x.k.namn, 70))}</span><span class="tal">${fmt(x.c)}</span></label>`).join(""));
    pop.querySelector(".kanal-fleire").textContent = liste.length > 50 ? `Viser 50 av ${fmt(liste.length)}. Skriv for å finne fleire.` : "";
    synkSjekk(pop, "kgr");
    synkSjekk(pop, "kanal");
  }
}
// The checked state follows the state after Back, Forward or a removed chip, also where the
// html string did not change (a checkbox the reader clicked keeps its own checked property).
function synkSjekk(pop, dim) {
  for (const c of pop.querySelectorAll(`input[type=checkbox][data-dim="${dim}"]`)) {
    const p = S.f[dim].has(c.value);
    if (c.checked !== p) c.checked = p;
  }
}

let utanK = null;
function utanKanal() { if (utanK == null) { utanK = 0; for (let i = 0; i < D.n; i++) if (D.kanal[i] < 0) utanK++; } return utanK; }
const lagCache = new Map();
function lagDel(j) {
  if (!lagCache.has(j)) {
    let a = 0, o = 0;
    for (let i = 0; i < D.n; i++) if (D.tema[i] === j) { if (D.lag[i]) a++; else o++; }
    lagCache.set(j, `Heile korpuset: ${fmt(o)} OpenAlex, ${fmt(a)} arkiv (${Math.round((100 * a) / Math.max(1, a + o))} % arkiv)`);
  }
  return lagCache.get(j);
}

// ---------- term suggestions (amendments 2, 22) ----------
function visForslag() {
  const q = el.sok.value.trim();
  if (q.length < 2) { lukkForslag(); return; }
  const ut = [];
  if (T.harFil("tid.json")) {
    const key = termNokkel(q), fk = fold(key), utan = fk.replace(/ /g, "");
    const td = D.tidd;
    const sett = new Set();
    for (const pass of [0, 1]) {
      for (let t = 0; t < td.termar.k.length && sett.size < 3; t++) {
        const f = D.termFold[t];
        const ok = pass === 0 ? f.startsWith(fk) || (utan && f.startsWith(utan)) : f.includes(fk);
        if (ok && !sett.has(t)) { sett.add(t); ut.push(`<li role="option"><button type="button" data-term="${esc(td.termar.k[t])}">Ord i titlar: <b>${esc(td.termar.vis[t])}</b> · ${fmt(td.termar.df[t])} titlar</button></li>`); }
      }
    }
  }
  for (const v of sitertForslag(q)) {
    ut.push(`<li role="option"><button type="button" data-kanon="${esc(T.nodeKey(v))}" aria-label="Sitert verk: ${esc(T.merkelapp(v))}, ${esc(T.nodeTittel(v))}, sitert av ${fmt(D.nSitert[v])} verk i korpuset. Vel verka som siterer det.">Sitert verk: <b>${esc(T.merkelapp(v))}</b> ${esc(kutt(T.nodeTittel(v), 46))} · sitert av ${fmt(D.nSitert[v])} verk</button></li>`);
  }
  if (!ut.length) { lukkForslag(); return; }
  el.forslag.innerHTML = ut.join("");
  el.forslag.hidden = false;
}
// Cited works (corpus works and cited items outside it) whose title has every typed word
// as a word prefix; at most 3, most cited first. Choosing one selects the works citing it.
let sitertOrd = null;
function sitertForslag(q) {
  if (!T.harFil("siteringar.json")) return [];
  const tok = T.sokTokens(q).map((t) => t.p);
  if (!tok.length) return [];
  if (!sitertOrd) {
    sitertOrd = [];
    const NM = D.n + D.m;
    for (let v = 0; v < NM; v++) if (D.nSitert[v] >= 3) sitertOrd.push({ v, ord: fold(T.nodeTittel(v)).split(/[^\p{L}\p{N}]+/u).filter(Boolean) });
    sitertOrd.sort((a, b) => D.nSitert[b.v] - D.nSitert[a.v] || a.v - b.v);
  }
  const ut = [];
  for (const x of sitertOrd) {
    if (tok.every((p) => x.ord.some((w) => w.startsWith(p)))) { ut.push(x.v); if (ut.length >= 3) break; }
  }
  return ut;
}
function veljKanon(key) {
  lukkForslag();
  if (el.avbrytSok) el.avbrytSok();
  el.sok.value = "";
  T.endre((s) => { s.f.kanon = new Set([key]); s.f.q = ""; });
  el.sok.focus();
}
function lukkForslag() { if (el.forslag) { el.forslag.hidden = true; el.forslag.innerHTML = ""; } }
export const forslagOpe = () => el.forslag && !el.forslag.hidden;
export function lukkForslagListe() { const o = forslagOpe(); lukkForslag(); if (o) el.sok.focus(); return o; }
function veljTerm(key) {
  lukkForslag();
  // the word replaces the typed search: it is the exact version of what was typed
  if (el.avbrytSok) el.avbrytSok();
  el.sok.value = "";
  T.endre((s) => { s.f.term.add(key); s.f.q = ""; });
  el.sok.focus();
}
export function fokuserSok() { if (smal() && !panelOpe()) {} el.sok.focus(); el.sok.select(); }
export function sokKlar() { el.brukKo(); }
export function tomSok() {
  if (document.activeElement === el.sok && el.sok.value) { el.sok.value = ""; T.endre((s) => { s.f.q = ""; }); lukkForslag(); return true; }
  return false;
}

// ---------- year slider ----------
const sliders = new Set();
export function lagArSlider(rot, { id }) {
  const a0 = T.AR_MIN, a1 = T.AR_MAX;
  rot.innerHTML = `
    <div class="arslider">
      <span class="kontroll-namn">År</span>
      <div class="arspor">
        <svg class="arhist" viewBox="0 0 ${a1 - a0 + 1} 20" preserveAspectRatio="none" aria-hidden="true"></svg>
        <input type="range" class="fra" min="${a0}" max="${a1}" step="1" value="${a0}" aria-label="Frå år">
        <input type="range" class="til" min="${a0}" max="${a1}" step="1" value="${a1}" aria-label="Til år">
      </div>
      <span class="artekst" aria-hidden="true">${a0} til ${a1}</span>
    </div>`;
  const fra = rot.querySelector(".fra"), til = rot.querySelector(".til"), tekst = rot.querySelector(".artekst"), svg = rot.querySelector(".arhist");
  const gest = `ar-${id}`;
  const skriv = () => {
    let a = +fra.value, b = +til.value;
    if (a > b) { if (document.activeElement === fra) { a = b; fra.value = a; } else { b = a; til.value = b; } }
    tekst.textContent = `${a} til ${b}`;
    T.endre((s) => { s.f.ar = a <= a0 && b >= a1 ? null : [a, b]; }, { hist: `kont:${gest}` });
  };
  for (const inp of [fra, til]) {
    inp.addEventListener("input", skriv);
    inp.addEventListener("change", () => T.avsluttGest(gest));
  }
  const s = {
    oppdater() {
      const [a, b] = S.f.ar || [a0, a1];
      if (document.activeElement !== fra) fra.value = a;
      if (document.activeElement !== til) til.value = b;
      tekst.textContent = `${a} til ${b}`;
      const c = T.fasettal("ar");
      let mx = 1;
      for (const x of c) mx = Math.max(mx, x);
      let html = "";
      for (let j = 0; j < c.length; j++) {
        if (!c[j]) continue;
        const h = Math.max(0.6, (c[j] / mx) * 20);
        const inne = a0 + j >= a && a0 + j <= b;
        html += `<rect x="${j + 0.1}" y="${20 - h}" width="0.8" height="${h}" class="${inne ? "inne" : "ute"}${a0 + j === 2026 ? " ufull" : ""}"/>`;
      }
      svg.innerHTML = html;
    },
  };
  sliders.add(s);
  return s;
}

// ---------- redraw ----------
export function oppdater(e = {}) {
  if (!el.rot) return;
  const v = D.verk;
  for (const s of sliders) s.oppdater();
  const cl = T.fasettal("land");
  for (const b of el.land.querySelectorAll("button")) {
    const c = b.dataset.land;
    b.setAttribute("aria-pressed", String(S.f.land.has(c)));
    b.querySelector("[data-tal]").textContent = fmt(cl.get(c) || 0);
    b.setAttribute("aria-label", `${c === "X" ? "Ukjend land" : v.land[D.landIdx.get(c)].namn}, ${cl.get(c) || 0} verk`);
  }
  const clag = T.fasettal("lag");
  for (const b of el.rot.querySelectorAll("button[data-lag]")) {
    b.setAttribute("aria-pressed", String(S.f.lag.has(b.dataset.lag)));
    b.querySelector("[data-tal]").textContent = fmt(clag.get(b.dataset.lag) || 0);
  }
  const cp = T.fasettal("pdf");
  el.pdf.setAttribute("aria-pressed", String(S.f.pdf));
  el.pdf.querySelector("[data-tal]").textContent = fmt(cp.get("1") || 0);
  for (const p of ["tema", "kanal", "type"]) {
    const n = p === "kanal" ? S.f.kanal.size + S.f.kgr.size : S.f[p].size;
    el.rot.querySelector(`#popknapp-${p} [data-aktivtal]`).textContent = n ? ` (${n})` : "";
    teiknPop(p);
  }
  // Back/Forward always gives the field the value from the link, also while it has focus;
  // otherwise the next keystroke would silently bring back a search the reader undid
  if (e.popstate) { if (el.avbrytSok) el.avbrytSok(); if (el.sok.value !== S.f.q) el.sok.value = S.f.q; lukkForslag(); }
  else if (document.activeElement !== el.sok && el.sok.value.trim() !== S.f.q) el.sok.value = S.f.q;
  const toks = T.sokTokens(S.f.q);
  el.sokinfo.textContent = S.f.q && toks.length ? `Søkjer etter: ${toks.map((t) => t.p + "*").join(", ")}` : "";
  const chips = T.chipar();
  el.knapp.textContent = `Filter (${chips.length})`;
  el.panel.querySelector(".panel-tittel").textContent = `Filter · ${fmt(T.valt)} verk`;
  teiknChipar(chips);
}

function teiknChipar(chips) {
  const rad = document.getElementById("chiprad");
  const n = D.n;
  const status = [];
  if (T.ventar()) status.push(`<span class="status">Lastar …</span>`);
  const si = T.sokInfo;
  if (S.f.q && si.delvis && T.brukt("q")) {
    const nt = si.tokens.length;
    status.push(`<span class="status" title="Færre enn 10 verk hadde alle orda, så lista viser verk med minst ${nt - 1} av dei ${nt}. Dei med alle orda står øvst.">Delvis treff: minst ${fmt(nt - 1)} av ${fmt(nt)} ord</span>`);
  }
  // two or more words: the strict set is the default; the wide set is an offer, never the default
  if (S.f.q && T.brukt("q") && si.tokens.length > 1 && !si.delvis) {
    if (si.vid) status.push(`<button type="button" class="lenkeknapp status-knapp" data-qv="0" title="Vis berre verk som har alle orda">Berre verk med alle orda (${fmt(si.streng)})</button>`);
    else if (si.streng < 10 && si.minst1 > si.streng) status.push(`<button type="button" class="lenkeknapp status-knapp" data-qv="1" title="Vis verk som har minst eitt av orda. Dei med alle orda står øvst.">Vis ${fmt(si.minst1)} med minst eitt av orda</button>`);
  }
  // the exact phrase as one click, when it is a word in the title list
  if (S.f.q && T.sokInfo.tokens.length > 1 && T.harFil("tid.json")) {
    const key = termNokkel(S.f.q);
    const t = D.termIdx.get(key) ?? D.termIdx.get(key.replace(/ /g, ""));
    if (t != null && !S.f.term.has(D.tidd.termar.k[t])) status.push(`<button type="button" class="lenkeknapp status-knapp" data-frase="${esc(D.tidd.termar.k[t])}">Berre «${esc(D.tidd.termar.vis[t])}» i tittelen (${fmt(D.tidd.termar.df[t])})</button>`);
  }
  for (const d of T.ikkjeIBruk()) status.push(`<span class="status feil">Filteret «${esc(T.DIM_NAMN[d] || d)}» er ikkje i bruk fordi fila kunne ikkje lastast. <button type="button" class="lenkeknapp" data-prov="${d}">Prøv igjen</button></span>`);
  // keep keyboard focus on the same chip (or its neighbour) when the row is rebuilt
  const a = document.activeElement;
  let fokus = null;
  if (a && rad.contains(a)) {
    const xs = [...rad.querySelectorAll(".chip-x")];
    fokus = { id: a.id, fjern: a.dataset.fjern, verdi: a.dataset.verdi, prov: a.dataset.prov, qv: a.dataset.qv, frase: a.dataset.frase, pos: xs.indexOf(a) };
  }
  rad.innerHTML = `
    <span class="teljar"><b>${fmt(T.valt)}</b> av ${fmt(n)} verk</span>${status.join("")}
    <div class="chipar">${chips.map((c) => `<span class="chip${c.feil ? " feil" : ""}"><span class="chip-tekst">${esc(c.tekst)}</span><button type="button" class="chip-x" data-fjern="${c.dim}" ${c.verdi != null ? `data-verdi="${esc(c.verdi)}"` : ""} aria-label="Fjern ${esc(c.tekst)}">×</button></span>`).join("")}</div>
    ${chips.length ? `<button type="button" class="knapp liten" id="nullstill">Nullstill alt</button>` : ""}`;
  rad.classList.toggle("tom", !chips.length && !status.length);
  if (fokus) {
    let m = null;
    if (fokus.id) m = rad.querySelector(`#${fokus.id}`);
    else if (fokus.fjern) m = [...rad.querySelectorAll(".chip-x")].find((b) => b.dataset.fjern === fokus.fjern && (b.dataset.verdi || "") === (fokus.verdi || ""));
    else if (fokus.prov) m = rad.querySelector(`[data-prov="${fokus.prov}"]`);
    else if (fokus.qv != null) m = rad.querySelector("[data-qv]");
    if (!m && fokus.pos >= 0) { const xs = rad.querySelectorAll(".chip-x"); m = xs[Math.min(fokus.pos, xs.length - 1)] || null; }
    if (!m) m = rad.querySelector("#nullstill");
    (m || el.sok).focus({ preventScroll: true });
  }
  annonser(`${fmt(T.valt)} av ${fmt(n)} verk`);
}
