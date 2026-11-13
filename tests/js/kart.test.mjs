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

test("søk i titlar: alle orda må finnast, utan omsyn til store bokstavar og diakritikk", () => {
  const m = Kart.makeMatcher("Ærlig  DESIGN");
  assert.ok(m(Kart.fold("Ærlig design i Norden")));
  assert.ok(m(Kart.fold("Designing aerlig things")));
  assert.ok(!m(Kart.fold("Design i Norden")));
  assert.equal(Kart.makeMatcher("   "), null);
  assert.ok(Kart.makeMatcher("café")(Kart.fold("Cafe culture")));
  assert.ok(Kart.makeMatcher("søm")(Kart.fold("Som")));
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
  const line = Kart.introLine(d, null);
  assert.ok(!/—/.test(line), "ingen lange tankestrekar");
  assert.ok(line.length < 260);
});

test("escaping av tekst frå data", () => {
  assert.equal(Kart.esc(`<img src=x onerror="a('b')">&`), "&lt;img src=x onerror=&quot;a(&#39;b&#39;)&quot;&gt;&amp;");
});
