import test from "node:test";
import assert from "node:assert/strict";
import { Ui } from "./helpers.mjs";

const base = () => Ui.emptyState();

test("adresse: rundtur for søk og alle filter", () => {
  const states = [
    {},
    { q: "participation in service design" },
    { q: "taus kunnskap i håndverk & «tester»", sort: "first" },
    { q: "x", sort: "cited", yr: [2015, 2024], cc: "SE", kind: "article", lang: "e", tilg: "open", inst: "I183111857", au: "Min Jae Kim", dup: true },
    { yr: [2015, 0] },
    { yr: [0, 2024] },
    { tilg: "abs" },
    { kind: "thesis", lang: "o" },
    { q: "a", sim: "nordic:nva:00094b8101b6c8b7abf0" },
    { au: "Åsheim, Øyvind" },
  ];
  for (const s of states) {
    const st = Object.assign(base(), s);
    const h = Ui.buildHash(st);
    assert.ok(h.startsWith("#korpus"), h);
    assert.deepEqual(Ui.parseHash(h), st, h);
  }
});

test("adresse: standardtilstand gir #korpus", () => {
  assert.equal(Ui.buildHash(base()), "#korpus");
  assert.deepEqual(Ui.parseHash(""), base());
  assert.deepEqual(Ui.parseHash("#korpus"), base());
});

test("adresse: verdiar er encodeURIComponent", () => {
  const h = Ui.buildHash(Object.assign(base(), { q: "a b&c=d?e#f" }));
  assert.equal(h, "#korpus?q=a%20b%26c%3Dd%3Fe%23f");
});

test("adresse: eitt verk, delt liste, gamal #pdf og faner", () => {
  const w = Ui.buildHash(Object.assign(base(), { work: "nordic:nva:abc" }));
  assert.equal(w, "#verk/nordic%3Anva%3Aabc");
  assert.equal(Ui.parseHash(w).work, "nordic:nva:abc");
  assert.equal(Ui.parseHash("#verk/W2885298853").work, "W2885298853");
  assert.equal(Ui.parseHash("#pdf").tilg, "open");
  const l = Ui.buildHash(Object.assign(base(), { list: ["W1", "nordic:diva:aa", "W3"] }));
  assert.equal(l, "#liste=W1~nordic%3Adiva%3Aaa~W3");
  assert.deepEqual(Ui.parseHash(l).list, ["W1", "nordic:diva:aa", "W3"]);
  for (const t of ["siteringar", "kart", "analyse", "teorielement", "om"]) {
    assert.equal(Ui.parseHash("#" + t).tab, t);
    assert.equal(Ui.buildHash(Object.assign(base(), { tab: t })), "#" + t);
  }
  assert.equal(Ui.parseHash("#ordliste").tab, "om");
  assert.equal(Ui.parseHash("#ordliste").anchor, "ordliste");
});

test("adresse: delt liste tek høgst 60 id-ar", () => {
  const ids = Array.from({ length: 80 }, (_, i) => "W" + i);
  assert.equal(Ui.parseHash("#liste=" + ids.join("~")).list.length, 60);
  assert.equal(Ui.buildHash(Object.assign(base(), { list: ids })).split("~").length, 60);
});

test("adresse: ukjende parameter og ugyldige verdiar vert ignorerte", () => {
  const st = Ui.parseHash("#korpus?zzz=1&q=ok&sort=bogus&kind=nope&cc=norway&yr=abc&tilg=x&inst=Q1&dup=0&lang=zz");
  assert.equal(st.q, "ok");
  assert.equal(st.sort, "");
  assert.equal(st.kind, "");
  assert.equal(st.cc, "");
  assert.equal(st.yr, null);
  assert.equal(st.tilg, "");
  assert.equal(st.inst, "");
  assert.equal(st.dup, false);
  assert.equal(st.lang, "");
  assert.equal(Ui.parseHash("#finst-ikkje").tab, "korpus");
  assert.equal(Ui.parseHash("#korpus?q=%E0%A4%A").q, "%E0%A4%A"); // øydelagd prosentkoding krasjar ikkje
});

test("adresse: teljar for aktive filter ignorerer søk og sortering", () => {
  assert.equal(Ui.filterCount(base()), 0);
  assert.equal(Ui.filterCount(Object.assign(base(), { q: "x", sort: "old" })), 0);
  assert.equal(Ui.filterCount(Object.assign(base(), { yr: [2000, 0], cc: "NO", dup: true })), 3);
});
