// The list of works (virtual, sortable, keyboard), the detail of one work, and the
// bottom sheet below 900 px.
import { esc, fmt, kutt, PALETTE_TEMA, KATALOG_LENKE, smal, veldigSmal, annonserMerke } from "./hjelp.js?v=1";
import * as T from "./tilstand.js?v=1";
import * as data from "./data.js?v=1";
import { hentSamandrag } from "./samandrag.js?v=1";

const { S, D } = T;
let api = null;
let el = {};
let rekkje = new Int32Array(0); // current order of selected works
let aktiv = -1;                 // position in rekkje of the active row
let H = 76;
const ORDNAR = {};
let arkTilstand = "peek";
let lenkeStatus = "ingen"; // ingen | lastar | ok | feil

export function init(a) {
  api = a;
  const p = document.getElementById("listepanel");
  p.innerHTML = `
    <button type="button" class="handtak" id="handtak" aria-expanded="false" aria-controls="listeinnhald" aria-label="Vis lista">
      <span class="handtak-strek" aria-hidden="true"></span><span class="handtak-tekst"></span>
    </button>
    <div class="listeinnhald" id="listeinnhald">
      <div class="liste-visning" id="listevisning">
        <div class="liste-topp">
          <span class="liste-tal" aria-hidden="true"></span>
          <label class="sortval"><span>Sorter</span>
            <select id="sort" aria-label="Sorter lista"></select>
          </label>
        </div>
        <p class="liste-hint">Enter: opne · P: opne PDF</p>
        <div class="liste-tom" hidden></div>
        <div class="liste" id="liste" role="listbox" tabindex="0" aria-label="Verk i utvalet">
          <div class="liste-hoyde"></div>
        </div>
      </div>
      <div class="detalj" id="detalj" hidden></div>
    </div>`;
  el = {
    p, handtak: p.querySelector("#handtak"), handtakTekst: p.querySelector(".handtak-tekst"),
    visning: p.querySelector("#listevisning"), tal: p.querySelector(".liste-tal"), sort: p.querySelector("#sort"),
    tom: p.querySelector(".liste-tom"), liste: p.querySelector("#liste"), hoyde: p.querySelector(".liste-hoyde"),
    detalj: p.querySelector("#detalj"),
  };
  lagOrdnar();
  el.sort.addEventListener("change", () => T.endre((s) => { s.sort = el.sort.value; }));
  el.liste.addEventListener("scroll", () => teiknRader(), { passive: true });
  el.liste.addEventListener("click", (e) => {
    const m = e.target.closest(".merke");
    if (m) {
      e.stopPropagation();
      if (m.tagName !== "A") { e.preventDefault(); sikreLenker(); }
      return;
    }
    const r = e.target.closest(".rad");
    if (!r) return;
    const i = +r.dataset.i;
    aktiv = rekkje.indexOf(i);
    sikreLenker();
    api.opneVerk(i, { fraListe: true });
  });
  el.liste.addEventListener("pointerover", (e) => {
    if (e.pointerType !== "mouse") return;
    const r = e.target.closest(".rad");
    api.merk(r ? +r.dataset.i : null);
  });
  el.liste.addEventListener("pointerleave", () => api.merk(aktivI()));
  el.liste.addEventListener("keydown", tast);
  el.liste.addEventListener("focus", () => { if (aktiv < 0 && rekkje.length) settAktiv(0); else api.merk(aktivI()); });
  el.liste.addEventListener("blur", () => api.merk(null));
  el.tom.addEventListener("click", (e) => { const b = e.target.closest("button[data-fjern]"); if (b) T.fjern(b.dataset.fjern); });
  el.detalj.addEventListener("click", detaljKlikk);
  // sheet
  el.handtak.addEventListener("click", () => { if (!dratt) settArk(arkTilstand === "peek" ? "halv" : "peek"); });
  drag();
  window.addEventListener("resize", () => { const nh = veldigSmal() ? 88 : 76; if (nh !== H) { H = nh; teiknListe(); } settArk(arkTilstand, true); });
  H = veldigSmal() ? 88 : 76;
  document.addEventListener("utforsk:lenker", () => sikreLenker());
  settArk("peek", true);
}

// ---------- orders ----------
function lagOrdnar() {
  const n = D.n, idx = Array.from({ length: n }, (_, i) => i);
  const sitV = (i) => D.sit[i];
  ORDNAR.sitert = Int32Array.from(idx.slice().sort((a, b) => sitV(b) - sitV(a) || D.ar[b] - D.ar[a] || a - b));
  ORDNAR.nyast = Int32Array.from(idx.slice().sort((a, b) => D.ar[b] - D.ar[a] || a - b));
  ORDNAR.eldst = Int32Array.from(idx.slice().sort((a, b) => D.ar[a] - D.ar[b] || a - b));
  const coll = new Intl.Collator("nn");
  ORDNAR.tittel = Int32Array.from(idx.slice().sort((a, b) => coll.compare(D.kol.tittel[a], D.kol.tittel[b]) || a - b));
  ORDNAR.sitRang = new Int32Array(n);
  ORDNAR.sitert.forEach((i, r) => { ORDNAR.sitRang[i] = r; });
}
export const effektivSort = () => (S.sort === "auto" ? (S.f.q ? "relevans" : "sitert") : S.sort === "relevans" && !S.f.q ? "sitert" : S.sort);

function lagRekkje() {
  const sort = effektivSort(), u = T.utval;
  const ut = new Int32Array(T.valt);
  let c = 0;
  if (sort === "relevans") {
    const sel = [];
    for (let i = 0; i < D.n; i++) if (u[i]) sel.push(i);
    const sc = new Map(sel.map((i) => [i, T.relevans(i)]));
    sel.sort((a, b) => sc.get(b) - sc.get(a) || ORDNAR.sitRang[a] - ORDNAR.sitRang[b]);
    for (const i of sel) ut[c++] = i;
  } else {
    for (const i of ORDNAR[sort]) if (u[i]) ut[c++] = i;
  }
  rekkje = ut;
}

// ---------- render ----------
export function oppdater(s, e) {
  if (e.filter || e.sort || !rekkje.length && T.valt) {
    const forI = aktivI();
    lagRekkje();
    aktiv = forI != null ? rekkje.indexOf(forI) : -1;
    if (e.filter) el.liste.scrollTop = 0;
    teiknListe();
  }
  if (e.verk || e.filter) visDetalj();
  if (e.filter || e.verk) teiknHandtak();
}
export const listeLengd = () => rekkje.length;
export const listeInnhald = () => rekkje;

function teiknListe() {
  const sort = effektivSort();
  el.sort.innerHTML = [["sitert", "Mest sitert"], ["nyast", "Nyast"], ["eldst", "Eldst"], ["tittel", "Tittel A til Å"], ...(S.f.q ? [["relevans", "Relevans"]] : [])]
    .map(([k, t]) => `<option value="${k}" ${k === sort ? "selected" : ""}>${t}</option>`).join("");
  el.tal.textContent = `${fmt(T.valt)} verk`;
  el.liste.setAttribute("aria-setsize", String(T.valt));
  el.hoyde.style.height = `${rekkje.length * H}px`;
  if (!T.valt) {
    const b = T.bestFjerning();
    el.tom.hidden = false;
    el.tom.innerHTML = `<p>Ingen verk passar alle filtera.</p>${b ? `<button type="button" class="knapp" data-fjern="${b.dim}">Fjern «${esc(b.tekst)}»</button>` : ""}`;
  } else el.tom.hidden = true;
  teiknRader(true);
  teiknHandtak();
}

let sisteVindauge = "";
function teiknRader(tving) {
  const top = el.liste.scrollTop, hh = el.liste.clientHeight || 600;
  const a = Math.max(0, Math.floor(top / H) - 10), b = Math.min(rekkje.length, Math.ceil((top + hh) / H) + 10);
  const key = `${a}-${b}-${aktiv}-${lenkeStatus}`;
  if (!tving && key === sisteVindauge) return;
  sisteVindauge = key;
  const v = D.verk;
  let html = "";
  for (let p = a; p < b; p++) {
    const i = rekkje[p];
    const f = D.kol.forf[i];
    const forf = f.length ? v.forfattarar[f[0]].namn + (f.length > 1 ? " m.fl." : "") : "Ukjend forfattar";
    const kanal = D.kanal[i] >= 0 ? v.kanalar[D.kanal[i]].namn : D.lenker && D.lenker.kjelde[i] ? D.lenker.kjelde[i] : (D.lag[i] ? "Arkiv" : "");
    html += `<div class="rad${p === aktiv ? " aktiv" : ""}" role="option" id="rad-${i}" data-i="${i}" aria-selected="${p === aktiv}" aria-posinset="${p + 1}" aria-setsize="${rekkje.length}" style="transform:translateY(${p * H}px)">
      <div class="rad-tekst"><span class="rad-tittel">${esc(D.kol.tittel[i])}</span><span class="rad-meta">${esc(forf)} · ${D.ar[i]}${kanal ? " · " + esc(kutt(kanal, 60)) : ""}</span></div>
      <div class="rad-hogre">${merke(i)}${D.sit[i] >= 0 ? `<span class="rad-sit" title="Siteringar (OpenAlex)">${fmt(D.sit[i])}</span>` : ""}</div>
    </div>`;
  }
  el.hoyde.innerHTML = html;
  if (aktiv >= 0) el.liste.setAttribute("aria-activedescendant", `rad-${rekkje[aktiv]}`);
  else el.liste.removeAttribute("aria-activedescendant");
}

function lenkeFor(i) {
  if (!D.lenker) return null;
  if (D.pdf[i] <= 1 && D.lenker.pdf[i]) return D.lenker.pdf[i];
  if (D.lenker.doi[i]) return `https://doi.org/${D.lenker.doi[i]}`;
  return null;
}
function merke(i) {
  const st = D.pdf[i];
  if (st === 3) return "";
  const ord = st === 0 ? "PDF" : st === 1 ? "Lenke" : "DOI";
  const kl = st === 0 ? "pdf" : st === 1 ? "lenke" : "doi";
  const tittel = st === 0 ? "Open PDF, stadfest" : st === 1 ? "Lenke frå metadata, ikkje stadfest at det er PDF" : "Berre utgjevarside (DOI)";
  const u = lenkeFor(i);
  if (u) return `<a class="merke ${kl}" href="${esc(u)}" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true" title="${tittel}">${ord}</a>`;
  return `<span class="merke ${kl}" aria-hidden="true" title="${tittel}">${ord}</span>`;
}

function teiknHandtak() {
  const ope = arkTilstand !== "peek";
  el.handtakTekst.textContent = S.verk ? `${fmt(T.valt)} verk · eitt ope` : `${fmt(T.valt)} verk`;
  el.handtak.setAttribute("aria-label", ope ? "Gøym lista" : "Vis lista");
  el.handtak.setAttribute("aria-expanded", String(ope));
}

// ---------- keyboard ----------
const aktivI = () => (aktiv >= 0 && aktiv < rekkje.length ? rekkje[aktiv] : null);
function settAktiv(p) {
  if (!rekkje.length) return;
  aktiv = Math.max(0, Math.min(rekkje.length - 1, p));
  const top = aktiv * H, hh = el.liste.clientHeight;
  if (top < el.liste.scrollTop) el.liste.scrollTop = top;
  else if (top + H > el.liste.scrollTop + hh) el.liste.scrollTop = top + H - hh;
  teiknRader(true);
  const i = rekkje[aktiv];
  api.merk(i);
  annonserMerke(`${D.kol.tittel[i]}, ${D.ar[i]}`);
}
function tast(e) {
  const side = Math.max(1, Math.floor(el.liste.clientHeight / H) - 1);
  switch (e.key) {
    case "ArrowDown": settAktiv(aktiv + 1); break;
    case "ArrowUp": settAktiv(aktiv - 1); break;
    case "PageDown": settAktiv(aktiv + side); break;
    case "PageUp": settAktiv(aktiv - side); break;
    case "Home": settAktiv(0); break;
    case "End": settAktiv(rekkje.length - 1); break;
    case "Enter": case " ": if (aktiv >= 0) { sikreLenker(); api.opneVerk(rekkje[aktiv], { fraListe: true }); } break;
    case "p": case "P": if (aktiv >= 0) opnePdf(rekkje[aktiv]); break;
    default: return;
  }
  e.preventDefault();
}
async function opnePdf(i) {
  if (!D.lenker) { const r = await sikreLenker(); if (!r) return; }
  const u = lenkeFor(i);
  if (u) window.open(u, "_blank", "noopener");
}

// ---------- links file (amendment 6) ----------
export async function sikreLenker() {
  if (D.lenker) return true;
  if (lenkeStatus === "lastar") return false;
  lenkeStatus = "lastar";
  if (S.verk) visDetalj();
  const r = await T.sikre("lenker.json");
  lenkeStatus = r.ok ? "ok" : "feil";
  teiknRader(true);
  if (S.verk) visDetalj();
  return r.ok;
}
export const lenkeTilstand = () => lenkeStatus;

// ---------- detail ----------
let visaVerk = null;
function visDetalj() {
  const id = S.verk;
  if (!id) {
    if (!el.detalj.hidden) {
      el.detalj.hidden = true;
      el.visning.hidden = false;
      const fokus = el.detalj.contains(document.activeElement);
      teiknRader(true);
      if (fokus) el.liste.focus();
    }
    visaVerk = null;
    return;
  }
  const i = D.idx.get(id);
  if (i == null) return;
  const ny = visaVerk !== id;
  visaVerk = id;
  el.visning.hidden = true;
  el.detalj.hidden = false;
  el.detalj.innerHTML = detaljHtml(i);
  if (ny) {
    el.detalj.scrollTop = 0;
    sikreLenker();
    T.sikre("naboar.bin").then(() => { if (S.verk === id) fyllNaboar(i); });
    T.sikre("siteringar.json").then((r) => { if (S.verk === id) fyllSit(i, r.ok); });
    fyllSamandrag(i, id);
    const h = el.detalj.querySelector("h2");
    if (h && !smal()) h.focus({ preventScroll: true });
  } else {
    if (T.harFil("naboar.bin")) fyllNaboar(i);
    if (T.harFil("siteringar.json")) fyllSit(i, true);
    fyllSamandrag(i, id);
  }
}

function detaljHtml(i) {
  const v = D.verk, k = D.kol;
  const forf = k.forf[i].map((f) => {
    const a = v.forfattarar[f];
    return a.k.startsWith("A")
      ? `<button type="button" class="lenkeknapp" data-forf="${esc(a.k)}" title="Vis verka til ${esc(a.namn)}">${esc(a.namn)}</button>`
      : `<button type="button" class="lenkeknapp" data-sok="${esc(a.namn)}" title="Søk etter ${esc(a.namn)}">${esc(a.namn)}</button>`;
  }).join(", ");
  const kanal = D.kanal[i] >= 0 ? `<button type="button" class="lenkeknapp" data-kanal="${esc(v.kanalar[D.kanal[i]].k)}">${esc(v.kanalar[D.kanal[i]].namn)}</button>` : (D.lag[i] ? "Ukjend kanal" : "Ukjend kanal");
  const t = v.tema[D.tema[i]];
  const inst = k.inst[i].map((j) => { const x = v.institusjonar[j]; return `<li><button type="button" class="lenkeknapp" data-inst="${esc(x.k)}">${esc(x.namn)}</button>${x.land ? ` <span class="dim">${esc(T.landNamn(x.land))}</span>` : ""}</li>`; }).join("");
  const st = D.pdf[i];
  let lenkerHtml = "";
  if (st === 3) lenkerHtml = `<p class="lenkenotat">Inga lenke i dataa</p>`;
  else if (!D.lenker) {
    lenkerHtml = lenkeStatus === "feil"
      ? `<p class="lenkenotat">Lenkene kunne ikkje lastast <button type="button" class="knapp liten" data-handling="lenker">Prøv igjen</button></p>`
      : `<p class="lenkenotat">Hentar lenke …</p>`;
  } else {
    const u = D.lenker.pdf[i];
    if (st === 0 && u) lenkerHtml = `<a class="knapp primar" href="${esc(u)}" target="_blank" rel="noopener">Opne PDF</a><span class="lenkenotat">Open PDF, stadfest</span>`;
    else if (st === 1 && u) lenkerHtml = `<a class="knapp" href="${esc(u)}" target="_blank" rel="noopener">Opne lenke</a><span class="lenkenotat">Lenke frå metadata, ikkje stadfest at det er PDF</span>`;
    else if (st === 2) lenkerHtml = `<span class="lenkenotat">Berre utgjevarside (DOI)</span>`;
    else lenkerHtml = `<span class="lenkenotat">Inga lenke i dataa</span>`;
  }
  const doi = D.lenker && D.lenker.doi[i] ? `<a class="knapp" href="https://doi.org/${esc(D.lenker.doi[i])}" target="_blank" rel="noopener">DOI</a>` : "";
  const kjelde = D.lenker && D.lenker.kjelde[i] ? D.lenker.kjelde[i] : "";
  const sitLinje = D.sit[i] >= 0 ? `Sitert ${fmt(D.sit[i])} gonger (OpenAlex)` : `Arkivverk${kjelde ? ` frå ${esc(kjelde)}` : ""}, ikkje gjennomgått${D.merk[i] & 1 ? " · Mogleg dublett" : ""}`;
  return `
    <div class="detalj-topp"><button type="button" class="knapp liten" data-handling="lista">← Lista</button></div>
    <h2 tabindex="-1">${esc(k.tittel[i])}</h2>
    <p class="detalj-forf">${forf || "Ukjend forfattar"}</p>
    <p class="detalj-meta">${D.ar[i]} · ${kanal} · ${esc(v.typar[D.type[i]].namn)} · <button type="button" class="lenkeknapp" data-tema="${esc(t.k)}"><span class="prikk" style="background:${PALETTE_TEMA[D.tema[i]]}"></span>${esc(t.namn)}</button></p>
    ${inst ? `<ul class="detalj-inst">${inst}</ul>` : ""}
    <div class="detalj-lenker">${lenkerHtml}${doi}
      <a class="knapp" href="${esc(KATALOG_LENKE(k.id[i]))}">Opne i katalogen</a>
      <button type="button" class="knapp" data-handling="nabolag">Vis nabolag</button></div>
    <section class="detalj-del"><h3>Samandrag</h3><div class="samandrag" data-samandrag><p class="dim">Hentar samandrag …</p></div></section>
    <section class="detalj-del"><h3>Tal</h3><p>${sitLinje}</p><p class="sitlinje" data-sitlinje>…</p></section>
    <section class="detalj-del"><h3>Liknande verk</h3><div data-naboar><p class="dim">Lastar …</p></div></section>`;
}

const samCache = new Map();
async function fyllSamandrag(i, id) {
  const boks = el.detalj.querySelector("[data-samandrag]");
  if (!boks) return;
  let r = samCache.get(id);
  if (r === undefined) { r = await hentSamandrag(id); samCache.set(id, r); }
  if (S.verk !== id) return;
  const b = el.detalj.querySelector("[data-samandrag]");
  if (!b) return;
  if (r && r.tekst) {
    b.innerHTML = "";
    const p = document.createElement("p");
    p.textContent = r.tekst;
    const k = document.createElement("p");
    k.className = "dim";
    k.textContent = `Kjelde: ${r.kjelde}`;
    b.append(p, k);
  } else {
    b.innerHTML = `<p class="dim">Samandrag er ikkje publisert her. Sjå utgjevarsida.</p><p><a href="${esc(KATALOG_LENKE(id))}">Opne i katalogen</a></p>`;
  }
}

function fyllSit(i, ok) {
  const b = el.detalj.querySelector("[data-sitlinje]");
  if (!b) return;
  if (!ok) { b.textContent = "Siteringsdata kunne ikkje lastast."; return; }
  if (D.lag[i]) { b.textContent = "Arkivverk har inga referanseliste i dataa."; }
  else {
    const a = D.refOff[i + 1] - D.refOff[i];
    b.textContent = `Siterer ${fmt(a)} verk i korpuset eller kanon · sitert av ${fmt(D.nSitert[i])} verk i korpuset`;
  }
}

function fyllNaboar(i) {
  const b = el.detalj.querySelector("[data-naboar]");
  if (!b) return;
  const v = D.verk;
  let html = `<ol class="naboar">`;
  for (let r = 0; r < 10; r++) {
    const j = D.nabo[i * 10 + r], c = D.naboCos[i * 10 + r] / 255;
    const f = D.kol.forf[j];
    const forf = f.length ? v.forfattarar[f[0]].namn.split(/[ ,]/)[0] : "";
    html += `<li><button type="button" class="nabo" data-opne="${j}"><span class="nabo-tittel">${esc(kutt(D.kol.tittel[j], 90))}</span>
      <span class="nabo-meta">${esc(forf)} ${D.ar[j]}</span><span class="likskap" title="Likskap ${Math.round(c * 100)} av 100"><span style="width:${Math.round(c * 100)}%"></span></span></button></li>`;
  }
  html += `</ol><button type="button" class="knapp" data-handling="lik">Vis desse ti i kartet</button>`;
  b.innerHTML = html;
}

function detaljKlikk(e) {
  const b = e.target.closest("button");
  if (!b) return;
  const d = b.dataset;
  if (d.handling === "lista") return api.lukkVerk();
  if (d.handling === "lenker") { lenkeStatus = "ingen"; return sikreLenker(); }
  if (d.handling === "nabolag") return api.nabolag(S.verk);
  if (d.handling === "lik") return T.endre((s) => { s.f.lik = s.verk; s.vis = s.vis === "kart" ? s.vis : "kart"; });
  if (d.forf) return T.veksle("forf", d.forf, { erstatt: true });
  if (d.inst) return T.veksle("inst", d.inst, { erstatt: true });
  if (d.kanal) return T.veksle("kanal", d.kanal, { erstatt: true });
  if (d.tema) return T.veksle("tema", d.tema, { erstatt: true });
  if (d.sok) return api.sok(d.sok);
  if (d.opne) return api.opneVerk(+d.opne, { fraListe: true });
}

export const detaljOpe = () => !!S.verk;

// ---------- bottom sheet ----------
let dratt = false;
function arkHoyder() {
  const vh = window.innerHeight;
  const topp = (document.querySelector(".topp") || { offsetHeight: 48 }).offsetHeight;
  return { peek: 64, halv: Math.round(vh * 0.5), full: vh - topp };
}
export function settArk(t, utanAnim) {
  arkTilstand = t;
  if (!smal()) { el.p.style.height = ""; el.p.classList.remove("ark-peek", "ark-halv", "ark-full"); return; }
  const h = arkHoyder()[t];
  el.p.classList.toggle("utan-anim", !!utanAnim);
  el.p.style.height = `${h}px`;
  el.p.classList.remove("ark-peek", "ark-halv", "ark-full");
  el.p.classList.add(`ark-${t}`);
  document.documentElement.style.setProperty("--ark", `${h}px`);
  teiknHandtak();
  setTimeout(() => teiknRader(true), 260);
  document.dispatchEvent(new CustomEvent("utforsk:ark", { detail: { h } }));
}
export const arkStatus = () => arkTilstand;
function drag() {
  let y0 = 0, h0 = 0, t0 = 0, sisteY = 0, sisteT = 0, fart = 0, aktivDrag = false;
  el.handtak.addEventListener("pointerdown", (e) => {
    if (!smal()) return;
    aktivDrag = true; dratt = false;
    y0 = e.clientY; h0 = el.p.getBoundingClientRect().height; t0 = performance.now();
    sisteY = y0; sisteT = t0; fart = 0;
    el.handtak.setPointerCapture(e.pointerId);
    el.p.classList.add("utan-anim");
  });
  el.handtak.addEventListener("pointermove", (e) => {
    if (!aktivDrag) return;
    const dy = e.clientY - y0;
    if (Math.abs(dy) > 6) dratt = true;
    const now = performance.now();
    fart = (e.clientY - sisteY) / Math.max(1, now - sisteT);
    sisteY = e.clientY; sisteT = now;
    const hs = arkHoyder();
    el.p.style.height = `${Math.max(hs.peek, Math.min(hs.full, h0 - dy))}px`;
  });
  const slutt = () => {
    if (!aktivDrag) return;
    aktivDrag = false;
    el.p.classList.remove("utan-anim");
    if (!dratt) return;
    const h = el.p.getBoundingClientRect().height, hs = arkHoyder();
    let mal;
    const val = [["peek", hs.peek], ["halv", hs.halv], ["full", hs.full]];
    if (Math.abs(fart) > 0.5) {
      const opp = fart < 0;
      const kand = val.filter(([, v]) => (opp ? v > h : v < h));
      mal = kand.length ? (opp ? kand[0] : kand[kand.length - 1])[0] : (opp ? "full" : "peek");
    } else mal = val.reduce((a, b) => (Math.abs(b[1] - h) < Math.abs(a[1] - h) ? b : a))[0];
    settArk(mal);
    setTimeout(() => { dratt = false; }, 50);
  };
  el.handtak.addEventListener("pointerup", slutt);
  el.handtak.addEventListener("pointercancel", slutt);
  el.handtak.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); settArk(arkTilstand === "peek" ? "halv" : "peek"); } });
}
export function fokusListe() { el.liste.focus(); }
