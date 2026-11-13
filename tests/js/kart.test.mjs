// Reine funksjonar i docs/kart.js (kartfana). Køyr: node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { docs } from "./helpers.mjs";

const require = createRequire(import.meta.url);
const Kart = require(path.join(docs, "kart.js"));
const Ui = require(path.join(docs, "ui.js"));

test("kart-adresse: les og skriv klynge, underklynge og fargeval", () => {
  assert.deepEqual(Kart.parseKartHash("#kart"), { k: -1, u: -1, f: "klynge" });
  assert.deepEqual(Kart.parseKartHash("#kart?k=3&f=ar"), { k: 3, u: -1, f: "ar" });
  assert.deepEqual(Kart.parseKartHash("#kart?k=2&u=17&f=kanal"), { k: 2, u: 17, f: "kanal" });
  assert.equal(Kart.parseKartHash("#korpus?q=kart"), null);
  assert.equal(Kart.parseKartHash("#verk/W1"), null);
  assert.deepEqual(Kart.parseKartHash("#kart?k=x&f=<script>&u=-1"), { k: -1, u: -1, f: "klynge" }, "ugyldige verdiar blir ignorerte");
  assert.equal(Kart.buildKartHash({ k: -1, u: -1, f: "klynge" }), "#kart");
  assert.equal(Kart.buildKartHash({ k: 4, u: -1, f: "land" }), "#kart?k=4&f=land");
  for (const h of ["#kart?k=4&f=land", "#kart?k=0&u=3", "#kart?f=ar"]) assert.equal(Kart.buildKartHash(Kart.parseKartHash(h)), h);
});

test("kart-adresse: katalogen les kart-adressa som kartfana og bryt ikkje", () => {
  const st = Ui.parseHash("#kart?k=3&f=ar");
  assert.equal(st.tab, "kart");
  assert.equal(st.q, "");
  assert.equal(st.work, "");
});

test("søk i titlar: alle orda må starte eit ord i tittelen, utan omsyn til store bokstavar og diakritikk", () => {
  const m = Kart.makeMatcher("Ærlig  DESIGN");
  assert.ok(m(Kart.foldTitle("Ærlig design i Norden")));
  assert.ok(m(Kart.foldTitle("Designing aerlig things")));
  assert.ok(!m(Kart.foldTitle("Design i Norden")));
  assert.equal(Kart.makeMatcher("   "), null);
  assert.ok(Kart.makeMatcher("café")(Kart.foldTitle("Cafe culture")));
  assert.ok(Kart.makeMatcher("søm")(Kart.foldTitle("Som")));
  assert.ok(Kart.makeMatcher("art")(Kart.foldTitle("Arts-based research")));
  assert.ok(!Kart.makeMatcher("art")(Kart.foldTitle("Participatory design")), "ikkje midt i eit ord");
  assert.ok(Kart.makeMatcher("co design")(Kart.foldTitle("Co-design with children")));
});

test("lenkje frå søket til katalogen: liste ved få treff, søk ved mange", () => {
  assert.equal(Kart.hitsHref("tekstil", ["W1", "nordic:nva:a b"]), "#liste=W1~nordic%3Anva%3Aa%20b");
  assert.deepEqual(Ui.parseHash(Kart.hitsHref("tekstil", ["W1", "nordic:nva:ab"])).list, ["W1", "nordic:nva:ab"]);
  const many = Array.from({ length: 61 }, (_, i) => "W" + i);
  assert.equal(Kart.hitsHref(" design & co ", many), "#korpus?q=design%20%26%20co");
  assert.equal(Ui.parseHash(Kart.hitsHref("design & co", null)).q, "design & co");
});

test("språk frå flagga og fargeplass for klynger", () => {
  assert.equal(Kart.langIndex(8), 0);
  assert.equal(Kart.langIndex(4 | 1), 1);
  assert.equal(Kart.langIndex(2), 2);
  assert.equal(Kart.clusterSlot({ id: 3, farge: 6 }, 8), 6, "fargeplass frå dataa går føre");
  assert.equal(Kart.clusterSlot({ id: 3 }, 8), Kart.SLOT8[3], "reserve for eit eldre kart med åtte klynger");
  assert.equal(Kart.clusterSlot({ id: 3 }, 10), 3);
  assert.equal(Kart.clusterSlot({ id: 9 }, 10), -1, "ingen plass: grå, ikkje ein lånt farge");
  assert.equal(Kart.clusterSlot({ id: 2, farge: 9 }, 8), Kart.SLOT8[2], "ugyldig plass blir ignorert");
});

test("språklina i panelet: berre når gruppa er tydeleg meir nordiskspråkleg enn korpuset", () => {
  assert.match(Kart.languageNote(0.541, 0.062, "klynga"), /^54\s%\sav verka i klynga er på eit nordisk språk, mot 6\s%/);
  assert.equal(Kart.languageNote(0.1, 0.062, "klynga"), "");
  assert.equal(Kart.languageNote(0.25, 0.2, "gruppa"), "");
  assert.equal(Kart.languageNote(undefined, 0.06, "klynga"), "");
});

test("periode, land og kanalgruppe", () => {
  assert.equal(Kart.periodIndex(1985), 0);
  assert.equal(Kart.periodIndex(1999), 0);
  assert.equal(Kart.periodIndex(2000), 1);
  assert.equal(Kart.periodIndex(2004), 1);
  assert.equal(Kart.periodIndex(2024), 5);
  assert.equal(Kart.periodIndex(2026), 6);
  assert.equal(Kart.periodIndex(2031), 6);
  assert.equal(Kart.periodIndex(0), -1);
  assert.equal(Kart.countryIndex(["NO"]), 0);
  assert.equal(Kart.countryIndex(["IS"]), 4);
  assert.equal(Kart.countryIndex(["NO", "SE"]), 5);
  assert.equal(Kart.countryIndex(["US"]), 5);
  assert.equal(Kart.countryIndex([]), 6);
  assert.equal(Kart.countryIndex(undefined), 6);
  const name = (s, arch) => { const i = Kart.venueIndex(s, arch); return i < Kart.VENUES.length ? Kart.VENUES[i][0] : i === Kart.VENUES.length ? "arkiv" : "andre"; };
  assert.equal(name("Nordic Design Research Conference"), "Nordes");
  assert.equal(name("Nordic design research conference"), "Nordes");
  assert.equal(name("Proceedings of DRS"), "DRS");
  assert.equal(name("Nordic Conference on Human-Computer Interaction"), "HCI-konferansar");
  assert.equal(name("Design Studies"), "Designtidsskrift");
  assert.equal(name("ServDes Service Design and Innovation Conference (ServDes)"), "ServDes");
  assert.equal(name("DiVA", true), "arkiv");
  assert.equal(name("Springer eBooks"), "andre");
  assert.equal(name(""), "andre");
});

test("etikettar: overlappande etikettar med lågare prioritet blir gøymde, og ingen overlappar", () => {
  const items = [
    { x: 100, y: 100, w: 80, h: 20 },
    { x: 110, y: 100, w: 80, h: 20 }, // same stad: flyttar seg over eller under
    { x: 105, y: 100, w: 80, h: 20 },
    { x: 105, y: 100, w: 80, h: 20 },
    { x: 105, y: 100, w: 80, h: 20 },
    { x: 105, y: 100, w: 80, h: 20 }, // sjette på same stad: ingen ledig plass att
    { x: 300, y: 300, w: 80, h: 20 },
    { x: -50, y: 100, w: 80, h: 20 }, // midtpunkt utanfor flata
    { x: 395, y: 5, w: 80, h: 20 }, // blir skyvd inn
  ];
  const r = Kart.placeLabels(items, 400, 400, 3);
  const res = { l: 344, t: 0, r: 400, b: 104 };
  const rr = Kart.placeLabels([{ x: 360, y: 20, w: 80, h: 20 }, { x: 360, y: 60, w: 160, h: 60 }], 400, 400, 3, [res]);
  for (const x of rr.filter(Boolean)) assert.ok(x.r <= res.l || x.t >= res.b, "ingen etikett under zoomknappane");
  assert.ok(r[0] && r[6] && r[8]);
  assert.ok(r[1], "nest viktigaste finn plass over eller under");
  assert.equal(r[5], null, "den lågast prioriterte på same stad blir gøymd");
  assert.equal(r[7], null);
  assert.ok(r[8].r <= 398 && r[8].t >= 2, "skyvd innanfor kanten");
  const shown = r.filter(Boolean);
  for (let i = 0; i < shown.length; i++) for (let j = i + 1; j < shown.length; j++) {
    const a = shown[i], b = shown[j];
    assert.ok(a.r <= b.l || b.r <= a.l || a.b <= b.t || b.b <= a.t, "ingen overlapp");
  }
});

test("ombryting av namn", () => {
  const measure = (t) => t.length * 7;
  assert.deepEqual(Kart.wrapLines("Norske fagmiljø: handverk, didaktikk, tenestedesign", 120, measure), ["Norske fagmiljø:", "handverk,", "didaktikk,", "tenestedesign"]);
  assert.deepEqual(Kart.wrapLines("Kort", 120, measure), ["Kort"]);
  assert.deepEqual(Kart.wrapLines("", 120, measure), []);
});

test("rutenett: næraste punkt er det same som eit fullt søk", () => {
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const n = 2000, xs = new Float32Array(n), ys = new Float32Array(n);
  for (let i = 0; i < n; i++) { xs[i] = rnd() * 10000; ys[i] = rnd() * 10000; }
  const g = Kart.buildGrid(xs, ys, n, 120);
  for (let t = 0; t < 300; t++) {
    const qx = rnd() * 10000, qy = rnd() * 10000, rad = 50 + rnd() * 300;
    let best = -1, bd = rad * rad;
    for (let i = 0; i < n; i++) { const d = (xs[i] - qx) ** 2 + (ys[i] - qy) ** 2; if (d < bd) { bd = d; best = i; } }
    assert.equal(Kart.nearest(g, xs, ys, qx, qy, rad), best);
  }
  assert.equal(Kart.nearest(g, xs, ys, 5000, 5000, 1e5, () => 0), -1, "vekt 0 hoppar over alle");
});

test("tips-boksen held seg innanfor grensene", () => {
  const b = { x0: 0, y0: 0, x1: 375, y1: 400 };
  for (const [px, py] of [[10, 10], [370, 10], [10, 395], [370, 395], [187, 200]]) {
    const p = Kart.clampBox(px, py, 220, 120, b, 12);
    assert.ok(p.left >= 4 && p.left + 220 <= 371, `vassrett ${px},${py}`);
    assert.ok(p.top >= 4 && p.top + 120 <= 396, `loddrett ${px},${py}`);
  }
  const p = Kart.clampBox(50, 50, 220, 120, { x0: 0, y0: 100, x1: 375, y1: 400 }, 12);
  assert.ok(p.top >= 104, "boksen held seg under toppen av synsfeltet");
});

test("sentrale verk: dei fem frå analysen først, så kjerneverk nærast midten, høgst 60", () => {
  const d = { ids: ["a", "b", "c", "d", "e", "f"], x: [0, 10, 20, 1, 2, 100], y: [0, 0, 0, 0, 0, 0], f: [0, 0, 0, 1, 0, 0] };
  const idIndex = new Map(d.ids.map((id, i) => [id, i]));
  const out = Kart.centralIds(d, { sentrale: ["a"] }, [0, 1, 2, 3, 4, 5], idIndex, 60);
  assert.deepEqual(out, ["a", "e", "b", "c", "f", "d"], "grenseverket d kjem sist");
  assert.equal(Kart.centralIds(d, { sentrale: ["a"] }, [0, 1, 2, 3, 4, 5], idIndex, 3).length, 3);
  assert.deepEqual(Kart.centralIds(d, { sentrale: ["a"], sentrale60: ["f", "e"] }, [], idIndex, 60), ["f", "e"]);
  assert.deepEqual(Kart.centralIds(d, { sentrale: ["a"], sentrale60: [5, 4, 0] }, [], idIndex, 2), ["f", "e"], "radnummer i ids");
  assert.ok(Kart.hasRanked({ sentrale60: [1] }));
  assert.ok(!Kart.hasRanked({ sentrale: ["a"] }));
});

test("delt liste til katalogen: formatet katalogen les", () => {
  const ids = ["W1", "nordic:diva:aa"];
  const h = "#liste=" + ids.map(encodeURIComponent).join("~");
  assert.deepEqual(Ui.parseHash(h).list, ids);
});

test("lys/mørk: luminans av fargevariablane", () => {
  assert.ok(Kart.luminance("#FFFFFF") > 0.9);
  assert.ok(Kart.luminance("#000000") < 0.1);
  assert.ok(Kart.luminance("rgb(10, 10, 10)") < 0.1);
  assert.ok(Kart.luminance("#fff") > 0.9);
});

test("kart.json frå bygget: gyldig, og alle verk har ein plass", () => {
  const p = path.join(docs, "data", "klynger", "kart.json");
  if (!fs.existsSync(p)) return;
  const d = JSON.parse(fs.readFileSync(p, "utf8"));
  assert.ok(Kart.validData(d));
  assert.ok(!Kart.validData({ ids: ["a"], x: [1], y: [], k: [0], klynger: [{ id: 0 }] }));
  const ks = new Set(d.klynger.map((c) => c.id));
  for (const k of d.k) assert.ok(ks.has(k));
  if (d.klynger.length === 8) assert.deepEqual([...Kart.SLOT8].sort(), [0, 1, 2, 3, 4, 5, 6, 7]);
  const slots = d.klynger.map((c) => Kart.clusterSlot(c, d.klynger.length));
  assert.ok(slots.every((s) => s >= 0 && s < 8), "kvar klynge har ein fargeplass");
  assert.equal(new Set(slots).size, slots.length, "ingen to klynger deler farge");
  for (const g of d.klynger.concat(d.under || [])) {
    assert.ok(Kart.hasRanked(g), "sentrale60 er eksportert");
    const ids = Kart.centralIds(d, g, [], new Map(), 60);
    assert.equal(new Set(ids).size, ids.length);
    for (const id of ids) assert.equal(d[g.k === undefined ? "k" : "u"][d.ids.indexOf(id)], g.id, "sentrale verk høyrer til gruppa");
  }
  for (const om of [null, JSON.parse(fs.readFileSync(path.join(docs, "data", "klynger", "om.json"), "utf8"))]) {
    const line = Kart.introLine(d, om);
    assert.ok(!/—/.test(line), "ingen lange tankestrekar");
    assert.ok(line.length < 130, "lina over kartet er kort, så kartet byrjar høgt på ein telefon");
    assert.match(line, /mjuke/);
    const head = Kart.legendHead(d, om);
    assert.ok(!/—/.test(head));
    assert.match(head, /av verk med lik tekst/, "forbehald: grupper av verk med lik tekst");
    assert.ok(!/algoritme/.test(head), "ikkje fagordet algoritme");
    assert.ok(!/mjuke|skarpe|landskap/.test(head), "at grensene er mjuke står berre i lina over kartet");
    assert.match(head, /nordiske språk/, "forklaringa seier at språk speler inn");
  }
});

test("lina over kartet og forbehaldet utan om.json", () => {
  const d = { tal: { grense_del: 0.324, nordisk_sprak_klynge: 1 }, klynger: [{ namn: "A" }, { namn: "Nordisk ting: x, y" }, { namn: "C" }] };
  assert.match(Kart.introLine(d, null), /^Eitt verk per prikk, og like tekstar ligg nær kvarandre\. Grensene er mjuke: 32\s% av verka ligg mellom klynger\.$/);
  const h = Kart.legendHead(d, null);
  assert.match(h, /^Tre klynger av verk med lik tekst\./);
  assert.match(h, /«Nordisk ting»/);
  assert.equal(Kart.legendHead(d, { forbehald: "F.", sprak: "S." }), "F. S. Vel ei klynge for å sjå kva ho består av.");
  assert.equal(Kart.talord(8), "åtte");
  assert.equal(Kart.talord(40), "40");
});

test("søket startar ved to teikn i eitt ord", () => {
  assert.ok(!Kart.searchReady("a"));
  assert.ok(!Kart.searchReady("ø"), "ø blir folda til o");
  assert.ok(!Kart.searchReady("a b"));
  assert.ok(Kart.searchReady("ab"));
  assert.ok(Kart.searchReady("a co"));
  assert.ok(!Kart.searchReady("  "));
});

test("teiknerekkjefølgje: største kategori først, sjeldne sist (øvst)", () => {
  assert.deepEqual(Kart.paintOrder([259, 0, 3000, 900, 20]), [2, 3, 0, 4]);
  assert.deepEqual(Kart.paintOrder([5, 5, 1]), [0, 1, 2], "likt tal: fast rekkjefølgje");
  assert.deepEqual(Kart.paintOrder(new Int32Array([0, 0])), []);
});

test("periodar: delar mot korpuset, korte etikettar og delår", () => {
  const r = Kart.periodShares([10, 20, 0], [100, 400, 0]);
  assert.deepEqual(r.share, [0.1, 0.05, 0]);
  assert.equal(r.base, 30 / 500);
  assert.equal(Kart.shortPeriod("2005–09"), "’05–09");
  assert.equal(Kart.shortPeriod("før 2000"), "før ’00");
  assert.equal(Kart.shortPeriod("anna"), "anna");
  assert.equal(Kart.periodSpan("2025–26"), 2);
  assert.equal(Kart.periodSpan("2020–24"), 5);
  assert.equal(Kart.periodSpan("før 2000"), 0);
  assert.equal(Kart.pctFine(0.024), "2,4 %");
  assert.equal(Kart.pctFine(0.35), "35 %");
  assert.equal(Kart.pctFine(undefined), "");
});

test("merknad om verk med berre tittel blant dei sentrale", () => {
  assert.match(Kart.titleOnlyNote(277, 643, 0, "klynga"), /^Ingen av dei 277 verka med berre tittel \(43\s%\)/);
  assert.equal(Kart.titleOnlyNote(277, 643, 1, "klynga"), "", "ein av dei fem har berre tittel: ingen merknad");
  assert.equal(Kart.titleOnlyNote(10, 643, 0, "klynga"), "", "få med berre tittel: ingen merknad");
  assert.equal(Kart.titleOnlyNote(0, 0, 0, "klynga"), "");
});

test("escaping av tekst frå data", () => {
  assert.equal(Kart.esc(`<img src=x onerror="a('b')">&`), "&lt;img src=x onerror=&quot;a(&#39;b&#39;)&quot;&gt;&amp;");
});
