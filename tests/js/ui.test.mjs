import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { Ui, docs, readText } from "./helpers.mjs";

const W = { id: "W1", title: "Tittel <script>alert(1)</script>", doi: "https://doi.org/10.1/abc", oa_url: "https://example.org/a.pdf", pdf: "https://raw.githubusercontent.com/lukketsvane/designteori/main/pdf/W1.pdf", license: "CC BY 4.0" };

test("tilgangsmerkelapp: tekst, lenkje og rel for h, v, u, d og 0", () => {
  const h = Ui.accessInfo("h", W, ["h", W.pdf, "CC BY-NC-ND 4.0", "https://ext.example/x.pdf"]);
  assert.equal(h.label, "Open PDF (kopi i arkivet)");
  assert.equal(h.href, W.pdf);
  assert.ok(h.tag.includes("CC BY-NC-ND 4.0"));
  const v = Ui.accessInfo("v", W, ["v", "https://mau.diva-portal.org/smash/get/diva2:1408077/FULLTEXT01.pdf"]);
  assert.equal(v.label, "Open PDF");
  assert.equal(v.tag, "", "knappen seier alt at lenkja er kontrollert");
  const u = Ui.accessInfo("u", W, ["u", "https://example.org/a.pdf"]);
  assert.equal(u.label, "PDF (ikkje kontrollert)");
  assert.ok(u.help.includes("Adressa er ikkje kontrollert; ho kan føre til ei utgjevarside eller ein betalingsmur"));
  const d = Ui.accessInfo("d", W, null);
  assert.equal(d.label, "Utgjevarside");
  assert.equal(d.href, "https://doi.org/10.1/abc");
  const d2 = Ui.accessInfo("d", { id: "W9", doi: "", oa_url: "https://doi.org/10.9/x" }, null); // DOI berre i oa_url
  assert.equal(d2.href, "https://doi.org/10.9/x");
  assert.equal(Ui.accessInfo("d", { id: "n", doi: "" }, ["d", "https://doi.org/10.8/y"]).href, "https://doi.org/10.8/y");
  const z = Ui.accessInfo("0", W, null);
  assert.equal(z.label, "");
  for (const info of [h, v, u, d]) {
    const html = Ui.accessLinkHtml(info);
    assert.ok(/target="_blank"/.test(html) && /rel="noopener noreferrer"/.test(html), html);
    assert.ok(/<a class="act act-link acc-[hvud]/.test(html));
  }
  assert.equal(Ui.accessLinkHtml(z), "");
  assert.ok(Ui.accessLinkHtml(h).includes(">Open PDF (kopi i arkivet)</a>"));
  assert.ok(Ui.accessLinkHtml(u).includes(">PDF (ikkje kontrollert)</a>"));
});

test("tilgang: verifisert adresse som ikkje er lasta er ikkje klikkbar; h og u fell tilbake på metadata", () => {
  const v = Ui.accessInfo("v", W, null);
  assert.equal(v.href, "");
  assert.ok(v.pending);
  const html = Ui.accessLinkHtml(v);
  assert.ok(!html.includes("<a "));
  assert.ok(html.includes("aria-disabled=\"true\""));
  assert.ok(html.includes("lastar…"));
  assert.equal(Ui.accessInfo("h", W, null).href, W.pdf);
  assert.equal(Ui.accessInfo("u", W, null).href, W.oa_url);
});

test("tilgang: berre http(s)-adresser kjem med", () => {
  assert.equal(Ui.safeHref("javascript:alert(1)"), "");
  assert.equal(Ui.safeHref("data:text/html,x"), "");
  assert.equal(Ui.safeHref("https://a.org/x?y=1"), "https://a.org/x?y=1");
  assert.equal(Ui.safeHref('https://a.org/"onmouseover="x'), "");
  const bad = Ui.accessInfo("u", W, ["u", "javascript:alert(1)"]);
  assert.equal(bad.href, "");
  assert.equal(Ui.accessLinkHtml(bad), "");
});

test("tekst frå data vert escapa", () => {
  const html = Ui.abstractHtml({ t: "<img src=x onerror=alert(1)> & 'quote' \"dq\"", s: "oa", l: "en" });
  assert.ok(!/<img/.test(html));
  assert.ok(html.includes("&lt;img src=x onerror=alert(1)&gt; &amp; &#39;quote&#39; &quot;dq&quot;"));
  const tag = Ui.accessTagHtml(Ui.accessInfo("h", { license: '"><script>' }, null));
  assert.ok(!tag.includes("<script>"));
  assert.equal(Ui.esc(null), "");
  assert.equal(Ui.esc("<>&\"'"), "&lt;&gt;&amp;&quot;&#39;");
});

test("samandrag: OpenAlex-merking, uttrekk med kjeldelenkje, språk og utheving", () => {
  const oa = Ui.abstractHtml({ t: "A text.", s: "oa", l: "en" });
  assert.ok(oa.includes("Samandrag frå OpenAlex (metadata)"));
  assert.ok(!oa.includes("samandrag på"));
  const x = Ui.abstractHtml({ t: "Extracted text.", s: "x", l: "nb", u: "https://example.org/f.pdf" });
  assert.ok(x.includes("Samandrag trekt ut av den opne PDF-en (automatisk, kan innehalde feil)"));
  assert.ok(x.includes('href="https://example.org/f.pdf"'));
  assert.ok(/rel="noopener noreferrer"/.test(x));
  assert.ok(x.includes("samandrag på bokmål"));
  const noUrl = Ui.abstractHtml({ t: "Extracted.", s: "x", l: "en", u: "javascript:alert(1)" });
  assert.ok(!noUrl.includes("javascript:"));
});

test("utheving: escapar først, markerer foldede ord, rører ikkje taggar", () => {
  const terms = new Set(["malmo", "design"]);
  assert.equal(Ui.highlight("Malmö <b>design</b> & Co", terms), "<mark>Malmö</mark> &lt;b&gt;<mark>design</mark>&lt;/b&gt; &amp; Co");
  assert.equal(Ui.highlight("<i>x</i>", new Set()), "&lt;i&gt;x&lt;/i&gt;");
  assert.equal(Ui.highlight("co-design", terms), "co-<mark>design</mark>");
});

test("«Ingen samandrag i korpuset»: utgjevarlenkje med DOI først, så tilgangsadresse, så OpenAlex (R7)", () => {
  const withDoi = Ui.noAbstractHtml(W, ["u", "https://example.org/a.pdf"]);
  assert.ok(withDoi.includes("Ingen samandrag i korpuset"));
  assert.ok(withDoi.includes('href="https://doi.org/10.1/abc"'));
  assert.ok(withDoi.includes("Utgjevarside"));
  const noDoi = Ui.noAbstractHtml({ id: "W2", title: "t" }, ["v", "https://host.example/f.pdf"]);
  assert.ok(noDoi.includes('href="https://host.example/f.pdf"'));
  const onlyOa = Ui.noAbstractHtml({ id: "W3", title: "t", doi: "", oa_url: "" }, null);
  assert.ok(onlyOa.includes('href="https://openalex.org/W3"'));
  assert.ok(onlyOa.includes("Opne i OpenAlex"));
  for (const html of [withDoi, noDoi, onlyOa]) assert.ok(/rel="noopener noreferrer"/.test(html));
  assert.equal(Ui.publisherLink({ id: "nordic:x:1", title: "t" }, null), null); // arkivverk har alltid source_url
  assert.equal(Ui.publisherLink({ id: "nordic:x:1", source_url: "https://arch.example/1" }, null).href, "https://arch.example/1");
});

test("flagg og likskap", () => {
  assert.equal(Ui.flagInfo("d").label, "Mogleg dublett");
  assert.equal(Ui.flagInfo("u").label, "Tilknyting ukjend");
  assert.equal(Ui.flagInfo("0"), null);
  assert.equal(Ui.simPercent(255), 100);
  assert.equal(Ui.simPercent(128), 50);
  assert.equal(Ui.simPercent(0), 0);
  assert.ok(Ui.SIM_NOTE.startsWith("Likskap i meining mellom tittel og samandrag"));
});

/* ---------- statiske kontrollar av dei nye filene ---------- */
const NEW_FILES = ["search.js", "export.js", "embed.js", "om.js", "ui.js", "app.js"];
const src = Object.fromEntries(NEW_FILES.map((f) => [f, readText(path.join(docs, f))]));

test("ingen innerHTML med rå data: kvar ${…} med dataeigenskap går gjennom esc/fmt/hjelpar", () => {
  const bad = [];
  const DATA = /\b(w|sw|cw|r|a|i|c|t|g|it|o|x|e|pl|info|entry|ctx|b|best|rec)\.(title|name|doi|source|venue|authors|label|term|nn|en|no|q|id|oa_url|source_url|pdf|license|country|topic|href|tag|help|t|u)\b/;
  for (const f of ["app.js", "om.js", "ui.js"]) {
    for (const line of src[f].split("\n")) {
      // tekst som berre vert søkt i (folding, match) og klassenamn er ikkje HTML-utdata
      if (line.includes("Search.fold(") || line.includes("match(`") || line.includes("S.clusterFilter ===")) continue;
      const re = /\$\{([^}]*)\}/g;
      let m;
      while ((m = re.exec(line))) {
        const expr = m[1];
        if (!DATA.test(expr)) continue;
        if (/esc\(|fmt\(|encodeURIComponent\(|Html\(|U\.(esc|safeHref)\(/.test(expr)) continue;
        bad.push(f + ": ${" + expr + "}");
      }
    }
  }
  assert.deepEqual(bad, []);
});

test("ingen innerHTML-tilordning med strengsamansetting av rå data utanfor mal", () => {
  for (const f of ["app.js", "om.js", "ui.js"]) {
    for (const line of src[f].split("\n")) {
      if (!/innerHTML\s*[+]?=/.test(line)) continue;
      assert.ok(!/innerHTML\s*[+]?=\s*[A-Za-z_.]*(title|name|doi|source|authors|value)\b/.test(line), f + ": " + line.trim());
    }
  }
});

test("R11: spørjinga forlèt ikkje nettlesaren (ingen sendBeacon, XHR, bilde eller fetch med søketekst)", () => {
  for (const f of NEW_FILES) {
    const t = src[f];
    assert.ok(!/sendBeacon|XMLHttpRequest|new Image\(|WebSocket|EventSource/.test(t), f);
    assert.ok(!/<img\b/.test(t), f);
  }
  const app = src["app.js"];
  const fetches = app.match(/fetch\([^)]*\)/g) || [];
  for (const f of fetches) assert.ok(!/(\.q\b|qInput|S\.st\.q|query)/.test(f), f);
  // alle jget/sget-kall har statiske adresser eller filnamn frå meta
  for (const m of app.matchAll(/\bjget\(([^,)]+)/g)) assert.ok(!/(\.q\b|qInput|S\.st\.q)/.test(m[1]), m[1]);
  // modellast startar berre frå enable() (klikk) eller silent() (lagra val)
  assert.ok(/onModelAction\(b\.dataset\.model\)/.test(app));
  assert.ok(/store\.get\(LS\.model\) !== "pa"/.test(app));
  assert.ok(!/importer\(|import\(/.test(app.replace(/\/\*[\s\S]*?\*\//g, "")), "app.js skal ikkje importere biblioteket direkte");
});

test("R13: alle target=\"_blank\"-lenkjer har rel=\"noopener noreferrer\"", () => {
  const files = Object.assign({}, src, { "index.html": readText(path.join(docs, "index.html")) });
  for (const [f, t] of Object.entries(files)) {
    for (const m of t.matchAll(/target=\\?"_blank\\?"([^>]{0,160})/g)) {
      const rest = m[1];
      const ok = /rel=\\?"noopener noreferrer\\?"/.test(rest) || /rel=\\?"noopener noreferrer\\?"/.test(t.slice(Math.max(0, m.index - 120), m.index)) ||
        (rest.includes("rel=\"' + REL + '\"") && t.includes("const REL = \"noopener noreferrer\""));
      assert.ok(ok, f + ": " + m[0].slice(0, 100));
    }
  }
});

test("nye filer er klassiske skript utan ESM-syntaks, med UMD-hale", () => {
  for (const f of ["search.js", "export.js", "ui.js", "om.js", "embed.js"]) {
    assert.ok(!/^\s*(import|export)\s/m.test(src[f]), f + " har ESM-syntaks");
    assert.ok(/typeof module === "object" && module\.exports/.test(src[f]), f + " manglar UMD-hale");
  }
  assert.ok(!/1900/.test(src["om.js"]), "om.js skal ikkje seie 1900");
});

test("kode v utan access.json: lenkje til utgjevarsida eller metadata-adressa, aldri evig «lastar…»", () => {
  const pending = Ui.accessInfo("v", W, null);
  assert.equal(pending.pending, true);
  assert.equal(pending.href, "");
  const viaDoi = Ui.accessInfo("v", W, null, { unavailable: true });
  assert.equal(viaDoi.pending, false);
  assert.equal(viaDoi.href, "https://doi.org/10.1/abc");
  assert.equal(viaDoi.label, "Utgjevarside");
  const viaMeta = Ui.accessInfo("v", { id: "n:1", source_url: "https://arkiv.example/x" }, null, { unavailable: true });
  assert.equal(viaMeta.href, "https://arkiv.example/x");
  assert.equal(viaMeta.label, "PDF (ikkje kontrollert)");
  const none = Ui.accessInfo("v", { id: "n:2" }, null, { unavailable: true });
  assert.equal(none.pending, false);
  assert.equal(Ui.accessLinkHtml(none), "");
  assert.ok(!Ui.accessLinkHtml(viaDoi).includes("lastar"));
});
