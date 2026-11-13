import test from "node:test";
import assert from "node:assert/strict";
import { Om } from "./helpers.mjs";

const COUNTS = {
  acc: { h: 23, v: 3239, u: 1387, d: 1439, "0": 344 }, abs: { o: 3916, x: 311, "0": 2205 },
  lang: { e: 5945, b: 311, n: 13, d: 37, s: 33, f: 3, o: 12, u: 78 }, flag: { "0": 5846, d: 187, u: 399 },
  layers: { openalex: 4694, nordic: 1738 }, year_range: [1983, 2026],
  sources: [{ name: "OpenAlex", n: 4694 }, { name: "Nasjonalt vitenarkiv / Cristin", n: 1161 }, { name: "Nordes / Design Research Society", n: 408 }],
  pdf_verified_total: 3262,
};

test("startpanel: fire linjer med tal frå meta.counts, utan 1900 og utan fast tal", () => {
  const lines = Om.startLines(COUNTS);
  assert.equal(lines.length, 4);
  const all = lines.join(" ");
  assert.ok(all.includes("6"), "total");
  assert.ok(/4.694/.test(all) && /1.738/.test(all));
  assert.ok(all.includes("1983–2026"));
  assert.ok(!all.includes("1900"));
  assert.ok(/3.262 har ei kontrollert open PDF-lenkje/.test(all));
  assert.ok(/187 verk er moglege dublettar/.test(all));
  assert.ok(lines[0].startsWith("<strong>Kva:"));
  assert.ok(lines[1].startsWith("<strong>Kor sikkert:"));
  assert.ok(lines[2].startsWith("<strong>Språk og samandrag:"));
  assert.ok(lines[3].startsWith("<strong>Manglar:"));
});

test("språknotis: «Fire av fem» vert rekna frå meta.counts.lang", () => {
  assert.ok(Om.langNote(COUNTS).startsWith("Ni av ti verk er på engelsk."), Om.langNote(COUNTS)); // 92 % i dag, rekna frå talet
  assert.ok(Om.langNote(Object.assign({}, COUNTS, { lang: { e: 5146, b: 1286 } })).startsWith("Åtte av ti verk"));
  const half = Object.assign({}, COUNTS, { lang: { e: 3000, b: 3432 } });
  assert.ok(/^\d+\u00a0% av verka er på engelsk\./.test(Om.langNote(half)));
});

test("om-fana: seksjonane og tabellane ligg i overflow-wrapper, tal frå fila", () => {
  const quality = {
    n_queries: 26, model: "m", metrics: { recall_at_10: { lexical: { all: 0.31 }, fused: { all: 0.5 } }, success_at_10: { lexical: { all: 0.6 } } }, caveats: ["Vurderaren er ein språkmodell."],
  };
  const html = Om.aboutHtml(COUNTS, { openalex_generated_at: "2026-11-12T03:43:41+00:00", review: { human_checked: 0, kind_unknown: 671, without_citations: 1738, affiliation_unknown: 408 }, countries: { NO: { openalex: 970, nordic: 1161 } } }, quality, { terms: [{ id: "rtd", term: "research through design", nn: "Forklaring.", en: ["RtD"], no: [], q: "research through design" }] }, { built: "2026-11-13T10:06:19+00:00" });
  for (const h of ["Kva som er med", "Korleis verk vart valde", "Kva som manglar", "Samandrag og PDF", "Språk", "Korleis søket verkar", "Målt søkjekvalitet", "Ordliste"]) assert.ok(html.includes(h), h);
  assert.ok(html.includes("12.11.2026"));
  assert.ok(html.includes("13.11.2026"));
  assert.ok(html.includes("408 arkivverk"), "same tal som i metaanalysen og Utforsk");
  assert.ok(html.includes("0,31"));
  assert.ok(html.includes("Vurderaren er ein språkmodell."));
  assert.ok(html.includes('id="ordliste"'));
  const tables = (html.match(/<table/g) || []).length;
  const wraps = (html.match(/<div class="table-wrap">/g) || []).length;
  assert.equal(tables, wraps);
  assert.ok(!html.includes("1900"));
});

test("ordliste: escapa tekst og søkeknapp", () => {
  const html = Om.glossaryHtml({ terms: [{ id: "x", term: "<b>t</b>", nn: "a & b", en: ["e"], no: ["n"], q: "q\"q" }] });
  assert.ok(!html.includes("<b>t</b>"));
  assert.ok(html.includes("&lt;b&gt;t&lt;/b&gt;"));
  assert.ok(html.includes('data-q="q&quot;q"'));
  assert.ok(html.includes(">Søk</button>"));
});

test("om-fana medan filene lastar: «Lastar …», ingen falske feilmeldingar", () => {
  const pending = { about: true, quality: true, glossary: true };
  const html = Om.aboutHtml(COUNTS, null, null, null, { built: "2026-11-13T10:06:19+00:00", pending });
  assert.ok((html.match(/Lastar …/g) || []).length >= 3);
  for (const bad of ["ikkje tilgjengeleg no", "OpenAlex-uttrekk: ukjend", "Ordlista er ikkje tilgjengeleg"]) assert.ok(!html.includes(bad), bad);
  assert.ok(!/ingen landkode/.test(html), "ikkje eit anna tal enn det frå about.json");
  // fila svarte ikkje: då er feilmeldinga rett
  const failed = Om.aboutHtml(COUNTS, null, null, null, { pending: { about: false, quality: false, glossary: false } });
  assert.ok(failed.includes("Målt søkjekvalitet er ikkje tilgjengeleg no."));
  assert.ok(failed.includes("Ordlista er ikkje tilgjengeleg no."));
  assert.ok(!/ingen landkode/.test(failed), "399 frå flagget er ikkje det same som 408 frå about.json");
});
