import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { Exp, here, readJson } from "./helpers.mjs";

const WORKS = readJson(path.join(here, "fixtures", "export_works.json"));
const items = WORKS.map((w) => ({ w, acc: w.oa_url ? "u" : "d", pdfUrl: w.oa_url || "", url: w.oa_url || w.source_url || "", lang: "en", flag: "" }));

/* Liten BibTeX-kontrollerar: gir [{type,key,fields}] og kastar ved ubalanserte klammer */
function parseBib(text) {
  const out = [];
  let i = 0;
  const skipWs = () => { while (i < text.length && /\s/.test(text[i])) i++; };
  while (true) {
    skipWs();
    if (i >= text.length) break;
    assert.equal(text[i], "@", `venta @ ved ${i}: ${text.slice(i, i + 20)}`);
    i++;
    const t = /^[a-z]+/.exec(text.slice(i))[0];
    i += t.length;
    assert.equal(text[i], "{"); i++;
    const k = /^[^,\s]+/.exec(text.slice(i))[0];
    i += k.length;
    assert.equal(text[i], ","); i++;
    const fields = {};
    while (true) {
      skipWs();
      if (text[i] === "}") { i++; break; }
      const name = /^[a-z]+/.exec(text.slice(i))[0];
      i += name.length; skipWs();
      assert.equal(text[i], "="); i++; skipWs();
      assert.equal(text[i], "{"); i++;
      let depth = 1, val = "";
      while (depth > 0) {
        const c = text[i];
        assert.ok(c !== undefined, "ubalansert klamme i " + name);
        if (c === "\\") { val += c + text[i + 1]; i += 2; continue; }
        if (c === "{") depth++;
        if (c === "}") { depth--; if (depth === 0) { i++; break; } }
        val += c; i++;
      }
      fields[name] = val;
      skipWs();
      if (text[i] === ",") i++;
    }
    out.push({ type: t, key: k, fields });
  }
  return out;
}

function parseCsv(text) {
  const rows = [];
  let row = [], cur = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(cur); cur = ""; }
    else if (c === "\r") { /* hopp */ }
    else if (c === "\n") { row.push(cur); rows.push(row); row = []; cur = ""; }
    else cur += c;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  return rows;
}

test("BibTeX: typar etter kind, review er article, thesis er misc", () => {
  const bib = parseBib(Exp.bibtex(items));
  assert.equal(bib.length, WORKS.length);
  const types = bib.map((e) => e.type);
  assert.deepEqual(types, ["article", "inproceedings", "incollection", "book", "phdthesis", "misc", "article", "misc"]);
});

test("BibTeX: escape berre i title, author og venue-felt, ikkje i doi, url og note", () => {
  const e = parseBib(Exp.bibtex(items))[0];
  assert.equal(e.fields.title, "{Infrastructuring urban commons over time: R\\&D, 50\\% of A\\_B and \\#1 \\{care\\}}"); // dobbel klamme rundt, escapa innhald
  assert.equal(e.fields.journal, "CoDesign \\& Practice");
  assert.equal(e.fields.doi, "10.1080/15710882.2018.1531_x%y"); // ingen backslash
  assert.equal(e.fields.url, "https://doi.org/10.1080/15710882.2018.1531_x%y");
  assert.equal(e.fields.note, "Frå designteori-korpuset, id W2885298853");
  assert.ok(!/\\/.test(e.fields.doi + e.fields.url + e.fields.note));
  assert.equal(e.fields.year, "2018");
  assert.equal(e.fields.author, "Anna Seravalli and Per-Anders Hillgren");
});

test("BibTeX: to forfattarformer, UTF-8, venue frå venue for arkivverk, doi utan prefiks", () => {
  const bib = parseBib(Exp.bibtex(items));
  assert.equal(bib[1].fields.author, "Kim, Min Jae and Øyvind Åsheim");
  assert.equal(bib[1].fields.booktitle, "Nordes 2025");
  assert.equal(bib[1].fields.url, "https://uu.diva-portal.org/smash/get/diva2:1970592/FULLTEXT01.pdf");
  assert.equal(bib[2].fields.doi, "10.1234/chapter.1");
  assert.equal(bib[2].fields.title, "{Making \\textasciitilde{} and \\textasciicircum{} matter: a chapter}");
  assert.equal(bib[3].fields.publisher, "Springer");
  assert.equal(bib[4].fields.title, "{A study of \\textbackslash{} backslashes and \\$ dollars}");
  assert.equal(bib[5].fields.howpublished, "Nasjonalt vitenarkiv / Cristin");
  assert.equal(bib[5].fields.url, "https://hdl.handle.net/11250/1");
  assert.ok(!("author" in bib[7].fields));
});

test("BibTeX: nøklar er unike og foldede (etternamn-år-ord), kollisjon gir a, b", () => {
  const keys = parseBib(Exp.bibtex(items)).map((e) => e.key);
  assert.deepEqual(keys.slice(0, 3), ["seravalli-2018-infrastructuring", "kim-2025-imagining", "brodsted-2014-making"]);
  assert.equal(keys[7], "anon-2022-editorial");
  assert.equal(new Set(keys).size, keys.length);
  const dup = [{ w: { id: "1", title: "Same title", year: 2020, authors: ["A Smith"] } }, { w: { id: "2", title: "Same title again", year: 2020, authors: ["B Smith"] } }, { w: { id: "3", title: "Other", year: 2020, authors: ["C Smith"] } }];
  const k2 = parseBib(Exp.bibtex(dup)).map((e) => e.key);
  assert.deepEqual(k2, ["smith-2020-samea", "smith-2020-sameb", "smith-2020-other"]);
});

test("RIS: TY…ER per post, namn delt ved siste mellomrom, UTF-8", () => {
  const ris = Exp.ris(items);
  const recs = ris.split(/ER  - \r?\n/).filter((s) => s.trim());
  assert.equal(recs.length, WORKS.length);
  for (const r of recs) assert.ok(/^TY  - (JOUR|CONF|CHAP|BOOK|THES|GEN)\r?\n/.test(r.trim() + "\n"), r.slice(0, 30));
  assert.deepEqual(recs.map((r) => /^TY  - (\w+)/.exec(r.trim())[1]), ["JOUR", "CONF", "CHAP", "BOOK", "THES", "GEN", "JOUR", "GEN"]);
  assert.ok(ris.includes("AU  - Seravalli, Anna\r\n"));
  assert.ok(ris.includes("AU  - Hillgren, Per-Anders\r\n"));
  assert.ok(ris.includes("AU  - Kim, Min Jae\r\n")); // vart ståande
  assert.ok(ris.includes("AU  - Åsheim, Øyvind\r\n"));
  assert.ok(ris.includes("DO  - 10.1080/15710882.2018.1531_x%y\r\n")); // ingen escaping
  assert.ok(ris.includes("N1  - id W2885298853\r\n"));
  assert.ok(ris.includes("T2  - Nordes 2025\r\n"));
});

test("CSV: BOM, kolonnar, alle felt i hermeteikn, authors med «; »", () => {
  const csv = Exp.csv(items);
  assert.equal(csv.charCodeAt(0), 0xfeff);
  const rows = parseCsv(csv.slice(1));
  assert.deepEqual(rows[0], ["id", "title", "authors", "year", "type", "venue", "doi", "citations", "language", "access", "pdf_url", "landing_url", "flag"]);
  assert.equal(rows.length, WORKS.length + 1);
  assert.equal(rows[1][2], "Anna Seravalli; Per-Anders Hillgren");
  assert.equal(rows[1][6], "10.1080/15710882.2018.1531_x%y");
  assert.equal(rows[1][9], "d");
  assert.equal(rows[2][9], "u");
  assert.equal(rows[2][10], "https://uu.diva-portal.org/smash/get/diva2:1970592/FULLTEXT01.pdf");
  assert.ok(csv.split("\r\n")[1].startsWith('"W2885298853","Infrastructuring'));
  const quoted = Exp.csv([{ w: { id: "q", title: 'Han sa "hei", ok', authors: [] } }]);
  assert.ok(quoted.includes('"Han sa ""hei"", ok"'));
});

test("R12: ingen samandragstekst i nokon eksport", () => {
  for (const kind of ["bibtex", "ris", "csv"]) assert.ok(!Exp.build(kind, items).includes("SECRET-ABSTRACT"), kind);
  assert.ok(!Exp.reference(items[0]).includes("SECRET-ABSTRACT"));
});

test("referanse: éi linje med forbokstavar, år, tittel, kjelde og DOI-lenkje", () => {
  assert.equal(Exp.reference(items[0]), "Seravalli, A., Hillgren, P.-A. (2018). Infrastructuring urban commons over time: R&D, 50% of A_B and #1 {care}. CoDesign & Practice. https://doi.org/10.1080/15710882.2018.1531_x%y");
  assert.equal(Exp.reference(items[1]), "Kim, M. J., Åsheim, Ø. (2025). Imagining Human-Robot Future Homes. Nordes 2025.");
  assert.ok(!Exp.reference(items[3]).includes("\n"));
});

test("filnamn og grense", () => {
  assert.equal(Exp.filename("bibtex", "leseliste", new Date(2026, 10, 13)), "designteori-leseliste-20261113.bib");
  assert.equal(Exp.filename("ris", "treff", new Date(2026, 0, 5)), "designteori-treff-20260105.ris");
  assert.equal(Exp.filename("csv", "treff", new Date(2026, 10, 13)), "designteori-treff-20261113.csv");
  assert.equal(Exp.LIMIT, 1000);
});

test("kind-gruppering: review er artikkel (endring 20)", () => {
  assert.equal(Exp.group("review"), "article");
  assert.equal(Exp.group("thesis"), "misc");
  assert.equal(Exp.group("dissertation"), "phd");
  assert.equal(Exp.group("conference-paper"), "inproc");
});
