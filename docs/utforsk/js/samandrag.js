// The only module that knows where abstracts come from (3.6).
// Contract of the main page (steg7 spesifikasjon 4.2 and 4.6): ../data/search/meta.json
// gives ids, build_id and the shard pattern; shard k holds positions 128k..128k+127 as
// { "<id>": {"t": text, "s": "oa"|"x", "l": lang, "u": url} }.
// Fallback: ../data/abstracts.json as { "<id>": {"text", "src"} } or { "items": {...} }.

const SOK = "../data/search/";
let meta = null;
const skjervar = new Map();
let reserve;

const KJELDE = {
  oa: "OpenAlex (metadata)",
  x: "trekt ut av den opne PDF-en (automatisk, kan innehalde feil)",
};

async function json(url, opt) {
  try {
    const r = await fetch(url, opt);
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    return null;
  }
}

async function hentMeta() {
  if (meta !== null) return meta;
  meta = (await json(SOK + "meta.json", { cache: "no-store" })) || false;
  if (meta && Array.isArray(meta.ids)) meta.pos = new Map(meta.ids.map((id, i) => [id, i]));
  return meta;
}

async function fraSkjerv(id) {
  const m = await hentMeta();
  if (!m || !m.pos || !m.abstracts) return undefined;
  const i = m.pos.get(id);
  if (i == null) return null;
  const size = m.abstracts.shard_size || 128;
  const k = Math.floor(i / size);
  const namn = (m.abstracts.pattern || "a{NNN}.json").replace("{NNN}", String(k).padStart(3, "0"));
  if (!skjervar.has(namn)) {
    const v = m.build_id ? `?v=${encodeURIComponent(m.build_id)}` : "";
    skjervar.set(namn, json(`${SOK}${m.abstracts.dir || "abstracts"}/${namn}${v}`));
  }
  const s = await skjervar.get(namn);
  if (!s) { skjervar.delete(namn); return undefined; }
  const x = s[id];
  if (!x || !x.t) return null;
  // Uttrekk frå PDF (s:"x") skal lenkje til kjelda (u), slik rettsregelen krev.
  const lenkje = x.s === "x" && typeof x.u === "string" && /^https?:\/\/[^\s<>"']+$/i.test(x.u) ? x.u : "";
  return { tekst: String(x.t), kjelde: KJELDE[x.s] || String(x.s || "ukjend"), lenkje };
}

async function fraReserve(id) {
  if (reserve === undefined) reserve = (await json("../data/abstracts.json")) || null;
  if (!reserve) return null;
  const tab = reserve.items && typeof reserve.items === "object" ? reserve.items : reserve;
  const x = tab[id];
  if (!x || !x.text) return null;
  return { tekst: String(x.text), kjelde: KJELDE[x.src] || String(x.src || "ukjend") };
}

// Returns {tekst, kjelde} or null. Never throws. Caches the loaded files.
export async function hentSamandrag(id) {
  try {
    const a = await fraSkjerv(id);
    if (a !== undefined) return a;
    return await fraReserve(id);
  } catch (e) {
    return null;
  }
}
