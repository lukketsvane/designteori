// Fetching: manifest, files with ?v=, JSON and binary decoding, one promise per file,
// CDN scripts with SRI. Errors are returned as values, never thrown.

let BASE = "../data/vis/";
try {
  if (["localhost", "127.0.0.1"].includes(location.hostname)) {
    const p = new URLSearchParams(location.search).get("data");
    if (p && /^[A-Za-z0-9_./-]+$/.test(p)) BASE = p.endsWith("/") ? p : p + "/";
  }
} catch (e) { /* keep default */ }
export const DATA = BASE;

let manifest = null;
const lova = new Map();   // name -> Promise<{ok, data, feil}>
const status = new Map(); // name -> "lastar" | "ok" | "feil"
const lyttarar = new Set();

export const filStatus = (namn) => status.get(namn);
export const paStatus = (fn) => { lyttarar.add(fn); return () => lyttarar.delete(fn); };
const melde = (namn) => { for (const fn of lyttarar) { try { fn(namn, status.get(namn)); } catch (e) { console.error(e); } } };

export async function lastManifest() {
  try {
    const r = await fetch(BASE + "manifest.json", { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    manifest = await r.json();
    return { ok: true, data: manifest };
  } catch (e) {
    return { ok: false, feil: String(e && e.message || e) };
  }
}
export const hentManifest = () => manifest;

function url(namn) {
  const f = manifest && manifest.filer && manifest.filer[namn];
  return BASE + namn + (f && f.sha256 ? `?v=${f.sha256.slice(0, 10)}` : "");
}

// hent("verk.json") or hent("naboar.bin", {bin: true}); {hoy: true} for high priority.
export function hent(namn, { bin = namn.endsWith(".bin"), hoy = false } = {}) {
  if (lova.has(namn)) return lova.get(namn);
  status.set(namn, "lastar");
  melde(namn);
  const p = (async () => {
    try {
      const r = await fetch(url(namn), hoy ? { priority: "high" } : {});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = bin ? await r.arrayBuffer() : await r.json();
      status.set(namn, "ok");
      melde(namn);
      return { ok: true, data };
    } catch (e) {
      status.set(namn, "feil");
      lova.delete(namn);
      melde(namn);
      return { ok: false, feil: namn };
    }
  })();
  lova.set(namn, p);
  return p;
}

// Synchronous access to a file that has loaded (or undefined).
const ferdige = new Map();
export async function last(namn, opt) {
  if (ferdige.has(namn)) return { ok: true, data: ferdige.get(namn) };
  const r = await hent(namn, opt);
  if (r.ok) ferdige.set(namn, r.data);
  return r;
}
export const ferdig = (namn) => ferdige.get(namn);

// CDN scripts (classic UMD), loaded once, sequentially where they depend on d3.
const SKRIPT = {
  sankey: { src: "https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js", sri: "sha256-gobbXWqgScxuilRnCJQ7ed+02q77DM9Cr2dOwO5Mhr4=", sjekk: () => window.d3 && window.d3.sankey },
  topojson: { src: "https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js", sri: "sha256-Jc0CrkhsxQY+AhWk5M+xXeg3AMh6xIusTVfcaq8+u4k=", sjekk: () => window.topojson },
};
const skriptLova = new Map();
export function lastSkript(namn) {
  if (namn === "d3") return Promise.resolve(window.d3 ? { ok: true } : { ok: false, feil: "d3" });
  const s = SKRIPT[namn];
  if (!s) return Promise.resolve({ ok: false, feil: namn });
  if (s.sjekk()) return Promise.resolve({ ok: true });
  if (skriptLova.has(namn)) return skriptLova.get(namn);
  const p = new Promise((res) => {
    const el = document.createElement("script");
    el.src = s.src;
    el.integrity = s.sri;
    el.crossOrigin = "anonymous";
    el.onload = () => res(s.sjekk() ? { ok: true } : { ok: false, feil: namn });
    el.onerror = () => { el.remove(); skriptLova.delete(namn); res({ ok: false, feil: namn }); };
    document.head.appendChild(el);
  });
  skriptLova.set(namn, p);
  return p;
}

let atlas = null;
export function verdsAtlas() {
  if (atlas) return atlas;
  atlas = (async () => {
    try {
      const r = await fetch("https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json", { integrity: "sha256-BDQs3B4wFrzX2xYw3pVoTWe3n+PIxGAyHoeu9GlQI5Q=" });
      if (!r.ok) throw new Error();
      return { ok: true, data: await r.json() };
    } catch (e) {
      atlas = null;
      return { ok: false, feil: "countries-50m.json" };
    }
  })();
  return atlas;
}
