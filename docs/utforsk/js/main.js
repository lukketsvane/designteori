// Boot: manifest, verk.json, first view; tab routing; global keys and errors;
// idle load of lenker.json and the search index.
import * as hjelp from "./hjelp.js?v=25";
import * as data from "./data.js?v=25";
import * as T from "./tilstand.js?v=25";
import * as filterlinje from "./filterlinje.js?v=25";
import * as liste from "./liste.js?v=25";
import { lagScene, lagIndeks, innanfor } from "./scene.js?v=25";
import { initMaal } from "./maal.js?v=25";

const { S, D } = T;
const { esc, fmt, kort, tooltip, smal } = hjelp;
// every module has loaded: the boot fallback in index.html stands down
window.__utforskStarta = true;

const LASTARAR = {
  kart: () => import("./visningar/kart.js?v=25"),
  nett: () => import("./visningar/nett.js?v=25"),
  verda: () => import("./visningar/verda.js?v=25"),
  siteringar: () => import("./visningar/siteringar.js?v=25"),
  tid: () => import("./visningar/tid.js?v=25"),
};
const NAMN = { kart: "kartet", nett: "nettet", verda: "verdskartet", siteringar: "siteringane", tid: "tidslina" };
const visingar = {}; // id -> {el, ramme, mod, klar, skitten, lastar, feil}
const flate = document.getElementById("visflate");
const errLogga = new Set();

window.addEventListener("error", (e) => { if (e && e.message && !errLogga.has(e.message)) errLogga.add(e.message); });
window.addEventListener("unhandledrejection", (e) => { console.error("Utforsk:", e.reason); e.preventDefault(); });

async function start() {
  settFane(T.lesHash(location.hash).vis);
  const sm = document.getElementById("startmelding");
  // without the manifest the files load without their version suffix; the page still works
  const m = await data.lastManifest();
  if (!m.ok) console.info("Utforsk: manifest.json kunne ikkje lastast; hentar filene utan versjonsmerke.");
  const r = await data.last("verk.json", { hoy: true });
  if (!r.ok) {
    sm.innerHTML = `<p>Kunne ikkje laste verk.json.</p><button type="button" class="knapp">Prøv igjen</button>`;
    sm.querySelector("button").addEventListener("click", () => location.reload());
    return;
  }
  T.forbredVerk(r.data);
  T.fraUrl({ start: true });
  sm.remove();
  filterlinje.init();
  liste.init(listeApi);
  T.abonner(vedEndring);
  liste.oppdater(S, { filter: true, sort: true, verk: true });
  // a shared or reloaded link with a work opens on a phone with the work's card showing, not
  // only a label on the map under a closed sheet
  if (S.verk && smal()) liste.settArk("kort", true);
  settFane(S.vis);
  await visVis(S.vis);
  // ... and the work's mark sits in the part of the picture above the card
  if (S.verk && smal()) {
    const v = visingar[S.vis], i = D.idx.get(S.verk);
    if (v && v.klar && v.mod.sentrer && i != null) setTimeout(() => { if (D.kol.id[i] === S.verk) { try { v.mod.sentrer(i); } catch (e) { feil(S.vis, e); } } }, 60);
  }
  initMaal({ visingar, liste, filterlinje });
  // label widths measured with the fallback font are wrong once the web font is in
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => {
    hjelp.tomMalCache();
    for (const v of Object.values(visingar)) if (v.klar && v.mod.scene) { const s = v.mod.scene(); if (s) s.teikn(); }
  });
  // idle: search index, then links
  const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 60));
  idle(() => {
    T.klargjerSok();
    filterlinje.sokKlar();
    filterlinje.oppdater();
    idle(() => liste.sikreLenker());
  }, { timeout: 400 });
}

// ---------- api for the list ----------
const listeApi = {
  opneVerk(i, { fraListe = false } = {}) {
    const id = D.kol.id[i];
    T.endre((s) => { s.verk = id; });
    const v = visingar[S.vis];
    if (smal()) {
      // a lower card than the half sheet; a sheet already higher (the reader pulled it up) stays
      const st = liste.arkStatus();
      if (st === "peek" || st === "kort") liste.settArk("kort");
      else if (st === "full") liste.settArk("halv");
      // centre once the sheet has reached its height (0.25 s), in the part of the picture above it
      if (v && v.klar && v.mod.sentrer) setTimeout(() => { if (S.verk === id) v.mod.sentrer(i); }, 280);
    } else if (fraListe && v && v.klar && v.mod.panTil) v.mod.panTil(i);
  },
  lukkVerk() { T.endre((s) => { s.verk = null; }); },
  merk(i) { const v = visingar[S.vis]; if (v && v.klar && v.mod.merk) { try { v.mod.merk(i); } catch (e) { feil(S.vis, e); } } },
  nabolag(id) { T.endre((s) => { s.vis = "siteringar"; s.sit.del = "nabolag"; s.sit.ego = id; }); },
  sok(namn) { T.endre((s) => { s.f.q = namn; }); },
};

// ---------- views ----------
function feil(id, e) {
  const v = visingar[id];
  const k = `${id}:${e && e.message}`;
  if (!errLogga.has(k)) { errLogga.add(k); console.error(`Utforsk (${id}):`, e); }
  if (v) v.feilMelding = true;
  if (v && v.ramme) hjelp.visMelding(v.ramme, { tittel: `Kunne ikkje teikne ${NAMN[id]}.`, knapp: { tekst: "Prøv igjen", gjer: () => {
    hjelp.visMelding(v.ramme, null);
    if (v.klar) oppdaterVis(id, alleEndringar());
    else { v.lastar = null; lastVis(id).then(() => { if (S.vis === id) visVis(id); }); }
  } } });
}
const alleEndringar = () => ({ filter: true, vis: true, verk: true, sort: true, visning: new Set(["kart.farge", "nett.modus", "sit.del", "sit.ego", "sit.straum", "tid.termar", "tid.tv"]), dims: T.DIMS });

function oppdaterVis(id, e) {
  const v = visingar[id];
  if (!v || !v.klar) return;
  const t0 = performance.now();
  // a "could not draw" banner from an earlier failure goes once the view draws again
  if (v.feilMelding) { v.feilMelding = false; hjelp.visMelding(v.ramme, null); }
  try {
    const p = v.mod.oppdater(S, e);
    if (p && typeof p.catch === "function") p.catch((err) => feil(id, err));
  } catch (err) { feil(id, err); }
  v.sisteTid = performance.now() - t0;
  tomTilstand(id);
}

function tomTilstand(id) {
  const v = visingar[id];
  if (!v || !v.tom) return;
  if (T.valt === 0 && D.klar) {
    const b = T.bestFjerning();
    v.tom.hidden = false;
    v.tom.innerHTML = `<div class="melding-boks"><p class="melding-tittel">Ingen verk i utvalet</p>${b ? `<button type="button" class="knapp">Fjern «${esc(b.tekst)}»</button>` : ""}</div>`;
    const k = v.tom.querySelector("button");
    if (k) k.addEventListener("click", () => T.fjern(b.dim));
  } else v.tom.hidden = true;
}

async function visVis(id) {
  for (const [k, v] of Object.entries(visingar)) if (k !== id && !v.el.hidden) { v.el.hidden = true; if (v.klar && v.mod.skjul) v.mod.skjul(); }
  kort.lukk(); tooltip.skjul();
  let v = visingar[id];
  if (!v) {
    const el = document.createElement("div");
    el.className = "vis";
    el.dataset.vis = id;
    flate.appendChild(el);
    const ramme = hjelp.lagRamme(el);
    const tom = document.createElement("div");
    tom.className = "vis-tom";
    tom.hidden = true;
    ramme.flate.appendChild(tom);
    v = visingar[id] = { el, ramme, tom, klar: false, skitten: true };
  }
  v.el.hidden = false;
  if (!v.klar) await lastVis(id);
  if (S.vis !== id) return;
  if (v.klar) {
    if (v.mod.vis) v.mod.vis();
    if (v.skitten) { v.skitten = false; oppdaterVis(id, alleEndringar()); }
  }
}

async function lastVis(id) {
  const v = visingar[id];
  if (v.lastar) return v.lastar;
  const r = v.ramme;
  v.lastar = (async () => {
    hjelp.visMelding(r, { tekst: `Lastar ${NAMN[id]} …` });
    hjelp.framdrift(r, 0.05);
    if (!window.d3) {
      hjelp.framdrift(r, null);
      hjelp.visMelding(r, { tekst: "Teiknebiblioteket kunne ikkje lastast. Lista over verk fungerer framleis." });
      v.lastar = null;
      return;
    }
    let mod;
    try { mod = (await LASTARAR[id]()).default; } catch (e) {
      hjelp.framdrift(r, null);
      hjelp.visMelding(r, { tittel: `Kunne ikkje laste ${NAMN[id]}.`, knapp: { tekst: "Prøv igjen", gjer: () => { v.lastar = null; lastVis(id).then(() => visVis(S.vis)); } } });
      v.lastar = null;
      return;
    }
    const filer = mod.filer || [], skript = mod.skript || [];
    let ferdige = 0;
    const steg = filer.length + skript.length || 1;
    const res = await Promise.all([
      ...skript.map((s) => data.lastSkript(s).then((x) => { hjelp.framdrift(r, ++ferdige / steg); return x; })),
      ...filer.map((f) => T.sikre(f).then((x) => { hjelp.framdrift(r, ++ferdige / steg); return x.ok ? x : { ok: false, feil: f }; })),
    ]);
    const mangel = res.find((x) => !x.ok);
    hjelp.framdrift(r, null);
    if (mangel) {
      hjelp.visMelding(r, { tittel: `Kunne ikkje laste ${mangel.feil}.`, knapp: { tekst: "Prøv igjen", gjer: () => { v.lastar = null; lastVis(id).then(() => visVis(S.vis)); } } });
      v.lastar = null;
      return;
    }
    hjelp.visMelding(r, null);
    try {
      if (!v.initert) { await mod.init(v.el, api(id)); v.initert = true; }
      if (id === "kart" || id === "nett" || id === "verda") r.settTeiknFlyt(true);
      v.mod = mod;
      v.klar = true;
      v.skitten = true;
    } catch (e) {
      feil(id, e);
    }
    v.lastar = null;
  })();
  return v.lastar;
}

const api = (id) => ({
  id, T, D, S, data, hjelp, ramme: visingar[id].ramme, lagScene, lagIndeks, innanfor,
  opneVerk: (i) => listeApi.opneVerk(i),
  liste, filterlinje,
  feil: (e) => feil(id, e),
});

let merktBrukt = false;
function vedEndring(s, e) {
  if (!merktBrukt && e.filter && !e.popstate) { merktBrukt = true; try { localStorage.setItem("utforsk.brukt", "1"); } catch (err) { /* storage blocked */ } }
  if (e.filter || e.vis || e.verk || e.sort || e.popstate) filterlinje.oppdater(e);
  liste.oppdater(s, e);
  // below 900 px a new tab or a new selection drops the sheet to its handle, so the picture
  // the reader asked for is not hidden under half a screen of list
  // Back/Forward to a state with an open work shows its card, as a fresh link does
  if (smal()) {
    const st = liste.arkStatus();
    if (e.popstate) { if (s.verk) { if (st === "peek") liste.settArk("kort"); } else if (st !== "peek") liste.settArk("peek"); }
    else if (e.vis && st !== "peek") liste.settArk("peek");
    else if (e.filter && st === "halv" && !e.verk) liste.settArk("peek");
  }
  if (e.vis) {
    settFane(s.vis);
    // the view that comes into sight is drawn once, by visVis, with every change
    const ny = visingar[s.vis];
    if (ny) ny.skitten = true;
    visVis(s.vis);
  }
  for (const [id, v] of Object.entries(visingar)) {
    if (id === s.vis) { if (!e.vis && !v.el.hidden) oppdaterVis(id, e); }
    else v.skitten = true;
  }
}

// ---------- tabs ----------
const faner = [...document.querySelectorAll(".fane")];
function settFane(id) {
  for (const f of faner) {
    const sel = f.dataset.vis === id;
    f.setAttribute("aria-selected", String(sel));
    f.tabIndex = sel ? 0 : -1;
  }
  flate.setAttribute("aria-labelledby", `fane-${id}`);
}
document.querySelector(".faner").addEventListener("click", (e) => {
  const f = e.target.closest(".fane");
  if (f && f.dataset.vis !== S.vis) T.endre((s) => { s.vis = f.dataset.vis; });
});
document.querySelector(".faner").addEventListener("keydown", (e) => {
  if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
  const i = faner.indexOf(document.activeElement);
  if (i < 0) return;
  const j = e.key === "Home" ? 0 : e.key === "End" ? faner.length - 1 : (i + (e.key === "ArrowRight" ? 1 : faner.length - 1)) % faner.length;
  faner[j].focus();
  e.preventDefault();
});

document.getElementById("hopp").addEventListener("click", () => { if (smal()) liste.settArk("halv"); liste.fokusListe(); });

// ---------- copy link ----------
const kopier = document.getElementById("kopier");
kopier.addEventListener("click", async () => {
  T.skrivUrlNo();
  try { await navigator.clipboard.writeText(location.href); } catch (e) {
    const t = document.createElement("textarea"); t.value = location.href; document.body.appendChild(t); t.select();
    try { document.execCommand("copy"); } catch (e2) { /* ignore */ } t.remove();
  }
  const sp = kopier.querySelector(".kopier-tekst");
  sp.textContent = "Kopiert";
  kopier.setAttribute("aria-label", "Kopiert");
  hjelp.annonserMerke("Lenka er kopiert");
  setTimeout(() => { sp.textContent = "Kopier lenke"; kopier.setAttribute("aria-label", "Kopier lenke"); }, 2000);
});

// ---------- global keys (amendment 35) ----------
document.addEventListener("keydown", (e) => {
  const tag = (e.target && e.target.tagName) || "";
  const iFelt = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  if (e.key === "/" && !iFelt) { e.preventDefault(); if (smal() && !filterlinje.panelOpe()) {} filterlinje.fokuserSok(); return; }
  if (e.key !== "Escape") return;
  if (escSteg()) e.preventDefault();
});
export function escSteg() {
  const v = visingar[S.vis];
  const m = v && v.klar ? v.mod : null;
  if (m && m.avbrytLasso && m.avbrytLasso()) return "lasso";
  if (m && m.stoppSpel && m.stoppSpel()) return "spel";
  if (filterlinje.popOpe()) { filterlinje.lukkPop(true); return "popover"; }
  if (filterlinje.forslagOpe()) { filterlinje.lukkForslagListe(); return "forslag"; }
  if (filterlinje.panelOpe()) { filterlinje.opnePanel(false); return "panel"; }
  const a = document.activeElement;
  if (a && (a.tagName === "INPUT") && a.type !== "range" && a.type !== "checkbox" && a.value) {
    if (filterlinje.tomSok()) return "tekst";
    a.value = ""; a.dispatchEvent(new Event("input", { bubbles: true })); return "tekst";
  }
  if (kort.ope) { kort.lukk(); if (m && m.lukkKort) m.lukkKort(); return "kort"; }
  if (m && m.fokusUt && m.fokusUt()) return "kort";
  if (tooltip.synleg) { tooltip.skjul(); return "kort"; }
  if (S.verk) { listeApi.lukkVerk(); return "detalj"; }
  if (smal() && liste.arkStatus() !== "peek") { liste.settArk("peek"); return "ark"; }
  return "";
}
window.__utforskEsc = escSteg;

document.getElementById("kort").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-kort]");
  if (!b) return;
  if (b.dataset.kort === "lukk") kort.lukk(); else kort.handling(+b.dataset.kort);
});

window.addEventListener("popstate", () => { if (D.klar) T.fraUrl(); });
window.addEventListener("hashchange", () => { if (D.klar && T.lagHash() !== location.hash) T.fraUrl(); });
document.addEventListener("utforsk:ark", () => { if (kort.ope) kort.plasser(0, 0); });

start().catch((e) => {
  console.error("Utforsk:", e);
  const sm = document.getElementById("startmelding");
  if (sm) sm.innerHTML = "<p>Noko gjekk gale ved oppstart.</p>";
});
