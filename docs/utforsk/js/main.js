// Boot: manifest, verk.json, first view; tab routing; global keys and errors;
// idle load of lenker.json and the search index.
import * as hjelp from "./hjelp.js?v=1";
import * as data from "./data.js?v=1";
import * as T from "./tilstand.js?v=1";
import * as filterlinje from "./filterlinje.js?v=1";
import * as liste from "./liste.js?v=1";
import { lagScene, lagIndeks, innanfor } from "./scene.js?v=1";
import { initMaal } from "./maal.js?v=1";

const { S, D } = T;
const { esc, fmt, kort, tooltip, smal } = hjelp;

const LASTARAR = {
  kart: () => import("./visningar/kart.js?v=1"),
  nett: () => import("./visningar/nett.js?v=1"),
  verda: () => import("./visningar/verda.js?v=1"),
  siteringar: () => import("./visningar/siteringar.js?v=1"),
  tid: () => import("./visningar/tid.js?v=1"),
};
const NAMN = { kart: "kartet", nett: "nettet", verda: "verdskartet", siteringar: "siteringane", tid: "tidslina" };
const visingar = {}; // id -> {el, ramme, mod, klar, skitten, lastar, feil}
const flate = document.getElementById("visflate");
const errLogga = new Set();

window.addEventListener("error", (e) => { if (e && e.message && !errLogga.has(e.message)) errLogga.add(e.message); });
window.addEventListener("unhandledrejection", (e) => { console.error("Utforsk:", e.reason); e.preventDefault(); });

async function start() {
  const sm = document.getElementById("startmelding");
  const m = await data.lastManifest();
  if (!m.ok) { sm.innerHTML = `<p>Kunne ikkje laste manifest.json.</p><button type="button" class="knapp" onclick="location.reload()">Prøv igjen</button>`; return; }
  const r = await data.last("verk.json", { hoy: true });
  if (!r.ok) { sm.innerHTML = `<p>Kunne ikkje laste verk.json.</p><button type="button" class="knapp" onclick="location.reload()">Prøv igjen</button>`; return; }
  T.forbredVerk(r.data);
  T.fraUrl({ start: true });
  sm.remove();
  filterlinje.init();
  liste.init(listeApi);
  T.abonner(vedEndring);
  liste.oppdater(S, { filter: true, sort: true, verk: true });
  settFane(S.vis);
  await visVis(S.vis);
  initMaal({ visingar, liste, filterlinje });
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
      liste.settArk("halv");
      if (v && v.klar && v.mod.sentrer) setTimeout(() => v.mod.sentrer(i), 30);
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
  if (v && v.ramme) hjelp.visMelding(v.ramme, { tittel: `Kunne ikkje teikne ${NAMN[id]}.`, knapp: { tekst: "Prøv igjen", gjer: () => { hjelp.visMelding(v.ramme, null); oppdaterVis(id, alleEndringar()); } } });
}
const alleEndringar = () => ({ filter: true, vis: true, verk: true, sort: true, visning: new Set(["kart.farge", "nett.modus", "sit.del", "sit.ego", "sit.straum", "tid.termar", "tid.tv"]), dims: T.DIMS });

function oppdaterVis(id, e) {
  const v = visingar[id];
  if (!v || !v.klar) return;
  const t0 = performance.now();
  try { v.mod.oppdater(S, e); } catch (err) { feil(id, err); }
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
      await mod.init(v.el, api(id));
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

function vedEndring(s, e) {
  if (e.filter || e.vis || e.verk || e.sort || e.popstate) filterlinje.oppdater();
  liste.oppdater(s, e);
  if (e.vis) { settFane(s.vis); visVis(s.vis); }
  for (const [id, v] of Object.entries(visingar)) {
    if (id === s.vis && !v.el.hidden) { if (!e.vis || !v.skitten) oppdaterVis(id, e); }
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

// ---------- copy link ----------
const kopier = document.getElementById("kopier");
kopier.addEventListener("click", async () => {
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
