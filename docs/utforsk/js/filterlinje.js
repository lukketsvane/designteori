// Filter bar: search with term suggestions, year slider with histogram, Nordic land
// toggles, popovers (tema, kanal, type), lag, PDF; chips row with count; mobile panel.
import { esc, fmt, fold, termNokkel, kutt, PALETTE_TEMA, KGR_FARGE, annonser, smal } from "./hjelp.js?v=1";
import * as T from "./tilstand.js?v=1";

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
        <button type="button" class="toggle" id="pdftoggle" aria-pressed="false"><span>Berre open PDF</span><span class="tal" data-tal></span></button>
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
      T.endre((s) => { s.f.q = verdi.trim(); }, { hist: "kont:q", utsett: 300 });
      clearTimeout(slutTid);
      slutTid = setTimeout(() => T.avsluttGest("q"), 1500);
    }, 200);
  };
  el.brukKo = () => { if (ko != null) { const q = ko; ko = null; T.endre((s) => { s.f.q = q.trim(); }, { hist: "kont:q", utsett: 300 }); } el.sok.placeholder = "Søk i tittel, forfattar, kanal, institusjon"; };
  el.sok.addEventListener("input", () => { brukSok(el.sok.value); visForslag(); });
  el.sok.addEventListener("focus", () => { T.sikre("tid.json").then(() => visForslag()); });
  el.sok.addEventListener("blur", () => { T.avsluttGest("q"); setTimeout(() => { if (!el.forslag.contains(document.activeElement)) lukkForslag(); }, 150); });
  el.sok.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" && !el.forslag.hidden) { const b = el.forslag.querySelector("button"); if (b) { b.focus(); e.preventDefault(); } }
    else if (e.key === "Enter") { clearTimeout(sokTid); if (T.sokKlar()) T.endre((s) => { s.f.q = el.sok.value.trim(); }); T.avsluttGest("q"); lukkForslag(); }
  });
  el.forslag.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-term]");
    if (!b) return;
    veljTerm(b.dataset.term);
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
      if (e.target.matches(".kanalsok")) teiknPop("kanal", true);
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
  });
  oppdater();
}

const erPanel = () => smal();

export function opnePanel(ope) {
  el.panel.classList.toggle("ope", ope);
  el.knapp.setAttribute("aria-expanded", String(ope));
  document.body.classList.toggle("panel-ope", ope);
  if (ope) {
    for (const p of ["tema", "kanal", "type"]) teiknPop(p, true);
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
  teiknPop(p, true);
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

function teiknPop(p, heilt) {
  const pop = document.getElementById(`pop-${p}`);
  if (!pop || (pop.hidden && !erPanel())) return;
  const v = D.verk;
  if (p === "tema") {
    const c = T.fasettal("tema");
    pop.innerHTML = `<p class="pop-tittel">Tema</p>` + v.tema.map((t, j) => `
      <label class="sjekk"><input type="checkbox" data-dim="tema" value="${esc(t.k)}" ${S.f.tema.has(t.k) ? "checked" : ""}>
      <span class="prikk" style="background:${PALETTE_TEMA[j]}"></span><span class="sjekk-namn">${esc(t.namn)}</span><span class="tal">${fmt(c.get(t.k) || 0)}</span></label>`).join("");
  } else if (p === "type") {
    const c = T.fasettal("type");
    pop.innerHTML = `<p class="pop-tittel">Type</p>` + v.typar.map((t) => `
      <label class="sjekk"><input type="checkbox" data-dim="type" value="${esc(t.k)}" ${S.f.type.has(t.k) ? "checked" : ""}>
      <span class="sjekk-namn">${esc(t.namn)}</span><span class="tal">${fmt(c.get(t.k) || 0)}</span></label>`).join("");
  } else if (p === "kanal") {
    const cg = T.fasettal("kgr"), ck = T.fasettal("kanal");
    const sokEl = pop.querySelector(".kanalsok");
    const sokv = sokEl ? sokEl.value : "";
    const fq = fold(sokv);
    let liste = v.kanalar.map((k, j) => ({ k, j, c: ck.get(k.k) || 0 }));
    if (fq) liste = liste.filter((x) => fold(x.k.namn).includes(fq));
    liste.sort((a, b) => (S.f.kanal.has(b.k.k) - S.f.kanal.has(a.k.k)) || b.c - a.c || a.j - b.j);
    const topp = liste.slice(0, 50);
    const grupper = `<p class="pop-tittel">Kanaltype</p>` + v.kanalgrupper.map((g) => `
      <label class="sjekk"><input type="checkbox" data-dim="kgr" value="${esc(g.k)}" ${S.f.kgr.has(g.k) ? "checked" : ""}>
      <span class="prikk" style="background:${KGR_FARGE[g.k] || "#9a9a9a"}"></span><span class="sjekk-namn">${esc(g.namn)}</span><span class="tal">${fmt(cg.get(g.k) || 0)}</span></label>`).join("");
    const kanalar = topp.map((x) => `
      <label class="sjekk"><input type="checkbox" data-dim="kanal" value="${esc(x.k.k)}" ${S.f.kanal.has(x.k.k) ? "checked" : ""}>
      <span class="sjekk-namn">${esc(kutt(x.k.namn, 70))}</span><span class="tal">${fmt(x.c)}</span></label>`).join("");
    if (heilt || !sokEl) {
      pop.innerHTML = `${grupper}<p class="pop-tittel">Kanal</p>
        <input type="search" class="kanalsok" placeholder="Skriv for å finne ein kanal" aria-label="Finn kanal" value="${esc(sokv)}" autocomplete="off">
        <div class="kanalliste">${kanalar}</div><p class="pop-merk">${liste.length > 50 ? `Viser 50 av ${fmt(liste.length)}. Skriv for å finne fleire.` : ""}</p>`;
      if (sokEl && document.activeElement === sokEl) pop.querySelector(".kanalsok").focus();
    }
    if (!heilt && sokEl) {
      pop.querySelector(".kanalliste").innerHTML = kanalar;
      pop.querySelector(".pop-merk").textContent = liste.length > 50 ? `Viser 50 av ${fmt(liste.length)}. Skriv for å finne fleire.` : "";
    }
  }
}

// ---------- term suggestions (amendments 2, 22) ----------
function visForslag() {
  const q = el.sok.value.trim();
  if (!T.harFil("tid.json") || q.length < 2) { lukkForslag(); return; }
  const key = termNokkel(q), fk = fold(key), utan = fk.replace(/ /g, "");
  const td = D.tidd, ut = [];
  const sett = new Set();
  for (const pass of [0, 1]) {
    for (let t = 0; t < td.termar.k.length && ut.length < 3; t++) {
      const f = D.termFold[t];
      const ok = pass === 0 ? f.startsWith(fk) || (utan && f.startsWith(utan)) : f.includes(fk);
      if (ok && !sett.has(t)) { sett.add(t); ut.push(t); }
    }
  }
  if (!ut.length) { lukkForslag(); return; }
  el.forslag.innerHTML = ut.map((t) => `<li role="option"><button type="button" data-term="${esc(td.termar.k[t])}">Ord i titlar: <b>${esc(td.termar.vis[t])}</b> · ${fmt(td.termar.df[t])} titlar</button></li>`).join("");
  el.forslag.hidden = false;
}
function lukkForslag() { if (el.forslag) { el.forslag.hidden = true; el.forslag.innerHTML = ""; } }
export const forslagOpe = () => el.forslag && !el.forslag.hidden;
export function lukkForslagListe() { const o = forslagOpe(); lukkForslag(); if (o) el.sok.focus(); return o; }
function veljTerm(key) {
  lukkForslag();
  T.endre((s) => { s.f.term.add(key); });
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
export function oppdater() {
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
    teiknPop(p, false);
  }
  if (document.activeElement !== el.sok && el.sok.value.trim() !== S.f.q) el.sok.value = S.f.q;
  const toks = T.sokTokens(S.f.q);
  el.sokinfo.textContent = S.f.q && toks.length ? `Søkjer etter: ${toks.map((t) => t.p + "*").join(", ")}` : "";
  const chips = T.chipar();
  el.knapp.textContent = `Filter (${chips.length})`;
  teiknChipar(chips);
}

function teiknChipar(chips) {
  const rad = document.getElementById("chiprad");
  const n = D.n;
  const status = [];
  if (T.ventar()) status.push(`<span class="status">Lastar …</span>`);
  if (S.f.q && T.sokInfo.delvis && T.brukt("q")) status.push(`<span class="status">Delvis treff</span>`);
  for (const d of T.ikkjeIBruk()) status.push(`<span class="status feil">Filteret «${esc(T.DIM_NAMN[d] || d)}» er ikkje i bruk fordi fila kunne ikkje lastast. <button type="button" class="lenkeknapp" data-prov="${d}">Prøv igjen</button></span>`);
  rad.innerHTML = `
    <span class="teljar"><b>${fmt(T.valt)}</b> av ${fmt(n)} verk</span>${status.join("")}
    <div class="chipar">${chips.map((c) => `<span class="chip${c.feil ? " feil" : ""}"><span class="chip-tekst">${esc(c.tekst)}</span><button type="button" class="chip-x" data-fjern="${c.dim}" ${c.verdi != null ? `data-verdi="${esc(c.verdi)}"` : ""} aria-label="Fjern ${esc(c.tekst)}">×</button></span>`).join("")}</div>
    ${chips.length ? `<button type="button" class="knapp liten" id="nullstill">Nullstill alt</button>` : ""}`;
  annonser(`${fmt(T.valt)} av ${fmt(n)} verk`);
}
