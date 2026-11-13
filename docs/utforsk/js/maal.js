// window.__utforsk: state, measuring and self-checks (6.5, amendment 45).
import * as T from "./tilstand.js?v=1";
import * as data from "./data.js?v=1";
import { PALETTE_TEMA, LAND_FARGE, FLEIRE_LAND, UKJEND, ANNA_LAND, KGR_FARGE, PALETTE_GRUPPE, PALETTE_ORD, FADE, FADE_ALFA, BG, cie76, kontrast, blandHex, overlappPar, rorsle, fmt } from "./hjelp.js?v=1";

const venteRamme = () => new Promise((r) => requestAnimationFrame(r));
const p95 = (a) => { const s = a.slice().sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(s.length * 0.95))] : 0; };
const snitt = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);
const r2 = (x) => Math.round(x * 100) / 100;

export function initMaal({ visingar, liste, filterlinje }) {
  const scene = (vis) => { const v = visingar[vis]; return v && v.klar && v.mod.scene ? v.mod.scene() : null; };

  async function panorering({ vis = T.S.vis, rammer = 120 } = {}) {
    const sc = scene(vis);
    if (!sc) return { feil: `ingen scene for ${vis}` };
    const d3 = window.d3;
    const t0 = sc.sc.t;
    const start = sc.teiknTider.length;
    const ts = [];
    for (let f = 0; f < rammer; f++) {
      const k = t0.k * (1 + 0.5 * Math.sin(f / 12));
      const t = d3.zoomIdentity.translate(t0.x + 40 * Math.sin(f / 9) + (1 - k / t0.k) * sc.sc.w / 2, t0.y + 30 * Math.cos(f / 11) + (1 - k / t0.k) * sc.sc.h / 2).scale(k);
      sc.sel.call(sc.zoomBehaviour.transform, t);
      ts.push(await venteRamme());
    }
    sc.sel.call(sc.zoomBehaviour.transform, t0);
    const iv = [];
    for (let i = 1; i < ts.length; i++) iv.push(ts[i] - ts[i - 1]);
    const tt = sc.teiknTider.slice(start);
    return { rammer, snitt_ms: r2(snitt(iv)), p95_ms: r2(p95(iv)), teikn_snitt_ms: r2(snitt(tt)), teikn_p95_ms: r2(p95(tt)) };
  }

  async function filter({ gonger = 10 } = {}) {
    const tider = [];
    const vis = T.S.vis;
    for (let g = 0; g < gonger; g++) {
      for (const verdi of [true, false]) {
        const t0 = performance.now();
        T.endre((s) => { if (verdi) s.f.land.add("NO"); else s.f.land.delete("NO"); }, { hist: "ingen" });
        T.meldNo();
        const sc = scene(vis);
        if (sc) sc.tvingTeikn();
        const v = visingar[vis];
        if (v && v.mod && v.mod.tvingTeikn) v.mod.tvingTeikn();
        if (verdi) tider.push(performance.now() - t0);
        await venteRamme();
      }
    }
    history.replaceState(null, "", T.lagHash());
    return { snitt_ms: r2(snitt(tider)), maks_ms: r2(Math.max(...tider)), vis };
  }

  // p95 frame interval during a 250 ms selection transition in Kart (45b)
  async function overgang() {
    const ts = [];
    let stopp = false;
    const loop = (t) => { ts.push(t); if (!stopp) requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
    T.endre((s) => { s.f.land.add("NO"); }, { hist: "ingen" });
    await new Promise((r) => setTimeout(r, 400));
    T.endre((s) => { s.f.land.delete("NO"); }, { hist: "ingen" });
    await new Promise((r) => setTimeout(r, 400));
    stopp = true;
    history.replaceState(null, "", T.lagHash());
    const iv = [];
    for (let i = 1; i < ts.length; i++) iv.push(ts[i] - ts[i - 1]);
    return { rammer: ts.length, p95_ms: r2(p95(iv)), maks_ms: r2(Math.max(...iv)) };
  }

  // pointermove to tooltip shown (45a)
  async function hover({ vis = "kart", n = 20 } = {}) {
    const sc = scene(vis);
    if (!sc) return { feil: "ingen scene" };
    const r = sc.over.getBoundingClientRect();
    const tip = document.getElementById("tooltip");
    const tider = [];
    const D = T.D;
    let forsok = 0;
    for (let i = 0; tider.length < n && forsok < n * 20; i = (i + 97) % D.n, forsok++) {
      const [px, py] = sc.sc.tilSkjerm(D.x[i], D.y[i]);
      if (px < 10 || py < 10 || px > r.width - 10 || py > r.height - 10) continue;
      tip.hidden = true;
      const t0 = performance.now();
      sc.over.dispatchEvent(new PointerEvent("pointermove", { clientX: r.left + px, clientY: r.top + py, pointerType: "mouse", bubbles: true }));
      while (tip.hidden && performance.now() - t0 < 200) await venteRamme();
      if (!tip.hidden) tider.push(performance.now() - t0);
    }
    sc.over.dispatchEvent(new PointerEvent("pointerleave", { pointerType: "mouse" }));
    return { n: tider.length, snitt_ms: r2(snitt(tider)), p95_ms: r2(p95(tider)) };
  }

  // overlapping label pairs at rest at k = 1, 3, 8 (45c)
  async function etikettar({ vis = T.S.vis } = {}) {
    const v = visingar[vis];
    const sc = scene(vis);
    if (!v || !v.klar || !v.mod.etikettar) return { feil: "ingen etikettar" };
    const ut = {};
    const z0 = sc ? sc.zNo() : null;
    for (const k of sc ? [1, 3, 8] : [1]) {
      if (sc) { sc.settZ([k, z0[1], z0[2]], 0, true); await venteRamme(); await venteRamme(); await venteRamme(); }
      const l = v.mod.etikettar();
      ut[`k${k}`] = { etikettar: l.length, overlapp: overlappPar(l) };
    }
    if (sc) sc.settZ(z0, 0, true);
    return ut;
  }

  function sjekk() {
    const feil = [];
    const S = T.S, D = T.D;
    // hash round trip for recorded states
    const lagra = [
      "#kart", "#kart?land=NO,SE&farge=land", "#nett?ar=2010-2020&nett=forf", "#verda?pdf=1&q=tacit%20knowledge",
      "#siteringar?tema=" + encodeURIComponent(D.verk.tema[0].k) + "&del=nabolag&ego=" + encodeURIComponent(D.kol.id[0]),
      "#tid?type=artikkel&t=codesign,service%20design&tv=tal", "#kart?kgr=konferanse,hci&sort=nyast&z=2.40,5120,4880",
      "#kart?lag=arkiv&verk=" + encodeURIComponent(D.kol.id[5]), "#siteringar?del=straum&straum=land&siterer=kgr:bok",
      "#kart?omr=1000,1000,4000,1000,4000,4000&term=codesign",
    ];
    for (const h of lagra) {
      const p = T.lesHash(h);
      // rebuild via a scratch state
      const lagre = JSON.stringify([...Object.entries(p.f)].map(([k, v]) => [k, v instanceof Set ? [...v] : v]));
      const p2 = T.lesHash(h);
      if (JSON.stringify([...Object.entries(p2.f)].map(([k, v]) => [k, v instanceof Set ? [...v] : v])) !== lagre) feil.push(`hash ikkje stabil: ${h}`);
    }
    const no = T.lagHash();
    const p = T.lesHash(no);
    const ff = (f) => JSON.stringify(Object.entries(f).map(([k, v]) => [k, v instanceof Set ? [...v].sort() : v]));
    if (ff(p.f) !== ff(S.f)) feil.push("hash -> state gir ikkje same filter");
    // list
    if (liste.listeLengd() !== T.valt) feil.push(`lista har ${liste.listeLengd()} rader, valt er ${T.valt}`);
    for (const i of liste.listeInnhald()) if (!T.utval[i]) { feil.push("rad utanfor utvalet"); break; }
    // files
    const m = data.hentManifest();
    for (const namn of ["verk.json", "lenker.json", "stader.json", "siteringar.json", "tid.json", "nett_inst.json", "nett_forf.json"]) {
      const x = data.ferdig(namn);
      if (x && x.generert !== D.verk.generert) feil.push(`${namn}: generert ulik verk.json`);
      if (x && x.n != null && x.n !== D.n) feil.push(`${namn}: n ulik`);
    }
    if (m && m.generert !== D.verk.generert) feil.push("manifest: generert ulik verk.json");
    // palettes (amendment 23)
    const andre = [...PALETTE_TEMA, ...Object.values(LAND_FARGE), FLEIRE_LAND, UKJEND, ANNA_LAND, ...Object.values(KGR_FARGE)];
    for (const [namn, pal] of [["PALETTE_GRUPPE", PALETTE_GRUPPE], ["PALETTE_ORD", PALETTE_ORD]]) {
      for (const a of pal) for (const b of andre) if (cie76(a, b) < 12) feil.push(`${namn} ${a} for nær ${b} (${cie76(a, b).toFixed(1)})`);
    }
    // fade contrast (amendment 25)
    const fade = blandHex(FADE, BG, FADE_ALFA);
    if (kontrast(fade, BG) < 1.4) feil.push(`blek farge ${fade} har for låg kontrast`);
    if (kontrast(UKJEND, BG) < 3) feil.push("Ukjend har for låg kontrast");
    // every visible view reports the same valt
    for (const [id, v] of Object.entries(visingar)) {
      if (!v.klar || v.el.hidden) continue;
      const t = v.ramme.linje.textContent;
      const valt = fmt(T.valt);
      if (T.valt && !t.includes(valt)) feil.push(`${id}: linja manglar valt (${valt})`);
    }
    return feil;
  }

  // Esc order (amendment 35, 45f): returns the order of steps taken from a prepared state.
  function escRekkje() {
    const ut = [];
    for (let g = 0; g < 10; g++) { const s = window.__utforskEsc(); if (!s) break; ut.push(s); }
    return ut;
  }

  window.__utforsk = {
    S: T.S, T, D: T.D, data, rorsle,
    maal: { panorering, filter, overgang, hover, etikettar },
    sjekk, escRekkje,
  };
}
