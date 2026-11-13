/* Tekst og tal for startpanelet, om-fana og ordlista. Ingen DOM; gir HTML-strengar der all data er escapa.
   Klassisk skript (UMD-hale): window.DTOm i nettlesaren, module.exports i node. */
(function () {
  "use strict";
  const U = (typeof module === "object" && module.exports) ? require("./ui.js") : window.DTUi;
  const { esc, fmt } = U;

  const DEFAULT_EXAMPLES = [
    "participation in service design in the public sector", "research through design", "infrastructuring", "sustainable design",
    "taus kunnskap i handverk", "korleis involverer ein innbyggjarar i offentlege tenester", "co-design with children",
    "speculative design", "tjenestedesign i helse og omsorg", "designutdanning og studiopedagogikk",
  ];
  const WORDS = ["Null", "Ein", "To", "Tre", "Fire", "Fem", "Seks", "Sju", "Åtte", "Ni", "Ti"];
  const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);
  const num = (o, k) => (o && typeof o[k] === "number" ? o[k] : 0);

  /* Tal for startpanelet frå meta.counts (T0). */
  function figures(c) {
    c = c || {};
    const total = (c.layers ? num(c.layers, "openalex") + num(c.layers, "nordic") : 0) || 0;
    const abs = c.abs || {}, acc = c.acc || {}, lang = c.lang || {}, flag = c.flag || {};
    const withAbs = num(abs, "o") + num(abs, "x");
    const yr = c.year_range || [];
    const shareEn = total ? num(lang, "e") / total : 0;
    const k = Math.round(shareEn * 10);
    return {
      total, openalex: num(c.layers, "openalex"), nordic: num(c.layers, "nordic"),
      sources: (c.sources || []).filter((s) => s.name !== "OpenAlex"),
      y0: yr[0], y1: yr[1],
      dup: num(flag, "d"), unk: num(flag, "u"),
      pctEn: pct(num(lang, "e"), total), pctAbs: pct(withAbs, total), withAbs,
      nPdf: num(acc, "h") + num(acc, "v"), shareEn, enWord: Math.abs(shareEn - k / 10) <= 0.03 ? WORDS[k] + " av ti" : "",
    };
  }

  function startLines(c) {
    const f = figures(c);
    const srcs = f.sources.map((s) => esc(s.name)).join(", ");
    const span = f.y0 && f.y1 ? ", " + esc(f.y0) + "–" + esc(f.y1) : "";
    return [
      "<strong>Kva:</strong> " + esc(fmt(f.total)) + " verk om design og designforsking frå Norden" + span + ": " + esc(fmt(f.openalex)) + " henta frå OpenAlex og " + esc(fmt(f.nordic)) + " frå nordiske arkiv" + (srcs ? " (" + srcs + ")" : "") + ".",
      "<strong>Kor sikkert:</strong> Ingen verk er kontrollerte av eit menneske. OpenAlex-verka er valde automatisk etter tittel. " + esc(fmt(f.dup)) + " verk er moglege dublettar og er skjulte som standard; " + esc(fmt(f.unk)) + " arkivverk har ukjend tilknyting.",
      "<strong>Språk og samandrag:</strong> " + esc(f.pctEn) + " % av verka er på engelsk. " + esc(f.pctAbs) + " % har samandrag. " + esc(fmt(f.nPdf)) + " har ei kontrollert open PDF-lenkje.",
      "<strong>Manglar:</strong> Fulltekst vert ikkje publisert her. Arkiva er ujamne (Finland har ingen arkivverk), arkivverk har ingen sitattal, og bøker utan open adresse finst berre som referanse.",
    ];
  }

  function langNote(c) {
    const f = figures(c);
    const lead = f.enWord ? f.enWord + " verk er på engelsk." : f.pctEn + " % av verka er på engelsk.";
    return lead + " Søk gjerne på norsk; for beste treff på tvers av språk, slå på språkmodell.";
  }

  /* ---------- om-fana ---------- */
  function table(head, rows, cls) {
    return '<div class="table-wrap"><table class="tbl-clean ' + (cls || "") + '"><thead><tr>' +
      head.map((h, i) => '<th' + (i ? ' class="r"' : "") + ">" + esc(h) + "</th>").join("") + "</tr></thead><tbody>" +
      rows.map((r) => "<tr>" + r.map((c, i) => "<td" + (i ? ' class="r"' : "") + ">" + (i ? esc(c) : "<strong>" + esc(c) + "</strong>") + "</td>").join("") + "</tr>").join("") +
      "</tbody></table></div>";
  }
  const dateOnly = (s) => (s ? String(s).slice(0, 10) : "");
  const CC = { NO: "Noreg", SE: "Sverige", DK: "Danmark", FI: "Finland", IS: "Island" };
  const LANGN = { e: "Engelsk", b: "Bokmål", n: "Nynorsk", d: "Dansk", s: "Svensk", f: "Finsk", o: "Anna", u: "Ukjend" };
  const SYSTEMS = [["lexical", "Ordsøk"], ["semantic", "Meining"], ["fused", "Samla (med språkmodell)"], ["fallback", "Reservemodus (ord og ordliste)"]];
  const GROUPS = [["all", "Alle"], ["known-item", "Kjent verk"], ["topical-en", "Emne, engelsk"], ["cross-lingual", "Tvers av språk"], ["dev", "dev"], ["test", "test"]];

  function qualityHtml(q) {
    if (!q || !q.metrics) return "<p>Målt søkjekvalitet er ikkje tilgjengeleg no.</p>";
    const one = (key) => {
      const m = q.metrics[key] || {};
      return table(["System"].concat(GROUPS.map((g) => g[1])), SYSTEMS.map(([k, name]) => [name].concat(GROUPS.map(([g]) => {
        const v = m[k] && m[k][g];
        return typeof v === "number" ? v.toFixed(2).replace(".", ",") : "–";
      }))));
    };
    const cav = (q.caveats || []).map((c) => "<li>" + esc(c) + "</li>").join("");
    /* Kva tala tyder for ein vanleg vitjar (utan språkmodell). Alle tal vert lesne frå fila. */
    const val = (key, sys, g) => { const v = q.metrics[key] && q.metrics[key][sys] && q.metrics[key][sys][g]; return typeof v === "number" ? v : null; };
    const p = (v) => (v == null ? "–" : Math.round(v * 100) + " %");
    const d2 = (v) => (v == null ? "–" : v.toFixed(2).replace(".", ","));
    const plain = val("success_at_10", "fallback", "all") == null ? "" :
      "<div class=\"om-plain\"><h4>I kva grad kan du stole på søket?</h4><p>Utan språkmodell, som er standard, fann søket minst eitt relevant verk blant dei ti første i " + esc(p(val("success_at_10", "fallback", "all"))) +
      " av testspørjingane. Når du leitar etter eitt enkelt verk du hugsar med eigne ord, er delen " + esc(p(val("success_at_10", "fallback", "known-item"))) +
      " (emnesøk på engelsk: " + esc(p(val("success_at_10", "fallback", "topical-en"))) + "). Med språkmodell er tala " + esc(p(val("success_at_10", "fused", "all"))) + " og " + esc(p(val("success_at_10", "fused", "known-item"))) +
      ". Samla søk er svakare enn reint meiningssøk for kjende verk (recall@10 " + esc(d2(val("recall_at_10", "fused", "known-item"))) + " mot " + esc(d2(val("recall_at_10", "semantic", "known-item"))) + ").</p>" +
      "<p>Tala er rettleiing, ikkje garanti: søkereglane vart justerte mot ein tredel av testspørjingane (dev), relevans er vurdert av ein språkmodell ut frå dei same systema, og det er få spørjingar. Prøv fleire ord og både norsk og engelsk dersom du ikkje finn det du leitar etter, og bruk «Liknande» frå eit verk som passar.</p></div>";
    return "<p>" + esc(fmt(q.n_queries)) + " testspørjingar" + (q.model ? ", modell " + esc(q.model) : "") + ". Relevans er vurdert av ein språkmodell, ikkje av ein domeneekspert. Tala er lesne frå fila <code>search_quality.json</code>.</p>" +
      plain +
      "<h4>Del av relevante verk i topp 10 (recall@10)</h4>" + one("recall_at_10") +
      "<h4>Del spørjingar med minst eitt relevant verk i topp 10 (success@10)</h4>" + one("success_at_10") +
      (cav ? "<h4>Avgrensingar</h4><ul class=\"plain\">" + cav + "</ul>" : "");
  }

  function glossaryHtml(g) {
    const terms = g && g.terms ? g.terms : [];
    if (!terms.length) return "<p>Ordlista er ikkje tilgjengeleg no.</p>";
    return terms.map((t) =>
      '<article class="gl-item" id="gl-' + esc(t.id) + '"><h4>' + esc(t.term) + "</h4><p>" + esc(t.nn) + "</p>" +
      '<p class="gl-eq">' + (t.en && t.en.length ? "Engelsk: " + esc(t.en.join(", ")) : "") + (t.no && t.no.length ? (t.en && t.en.length ? " · " : "") + "Norsk: " + esc(t.no.join(", ")) : "") + "</p>" +
      '<button type="button" class="act act-block gl-search" data-q="' + esc(t.q || t.term) + '">Søk på dette</button></article>').join("");
  }

  /* c: meta.counts, a: about.json eller null, q: search_quality.json eller null, g: glossary.json eller null, m: {built} */
  function aboutHtml(c, a, q, g, m) {
    c = c || {}; a = a || {}; m = m || {};
    const f = figures(c);
    const sources = (c.sources || a.sources || []);
    const rev = a.review || {};
    const countries = a.countries || {};
    const acc = c.acc || a.access || {};
    const abs = c.abs || {};
    const secs = [];

    secs.push("<section class=\"om-sec\"><h3>Kva som er med</h3>" +
      "<p>" + esc(fmt(f.total)) + " verk om design og designforsking" + (f.y0 && f.y1 ? ", " + esc(f.y0) + "–" + esc(f.y1) : "") + ". To lag: " + esc(fmt(f.openalex)) + " frå OpenAlex og " + esc(fmt(f.nordic)) + " frå nordiske arkiv.</p>" +
      table(["Kjelde", "Verk"], sources.map((s) => [s.name, fmt(s.n)])) +
      (Object.keys(countries).length ? table(["Land", "OpenAlex", "Arkiv"], Object.keys(countries).map((k) => [CC[k] || k, fmt(countries[k].openalex), fmt(countries[k].nordic)])) : "") +
      "<p class=\"om-dates\">OpenAlex-uttrekk: " + esc(dateOnly(a.openalex_generated_at) || "ukjend") + ". Søkedata bygd: " + esc(dateOnly(m.built || a.built) || "ukjend") + ".</p></section>");

    secs.push("<section class=\"om-sec\"><h3>Korleis verk vart valde, og kva det betyr</h3><ul class=\"plain\">" +
      "<li>OpenAlex-verka er valde automatisk etter tittel. Ingen er kontrollerte av eit menneske (" + esc(fmt(rev.human_checked != null ? rev.human_checked : 0)) + " av " + esc(fmt(f.openalex)) + " sjekka).</li>" +
      "<li>Arkivverka er ukontrollerte metadata frå arkiva" + (rev.kind_unknown != null ? "; " + esc(fmt(rev.kind_unknown)) + " har typen «ukjend»" : "") + (rev.without_citations != null ? " og " + esc(fmt(rev.without_citations)) + " har ingen sitattal" : "") + ".</li>" +
      "<li>" + esc(fmt(f.dup)) + " verk er merkte som moglege dublettar (same tittel, same år, felles forfattar). Dei er skjulte som standard.</li>" +
      "<li>" + esc(fmt(rev.affiliation_unknown != null ? rev.affiliation_unknown : f.unk)) + " arkivverk (Nordes) har ingen landkode, så nordisk tilknyting er ikkje kontrollert.</li>" +
      "<li>«Nordisk» tyder her at minst éin forfattar har ei nordisk tilknyting i OpenAlex, eller at arkivet er nordisk. Det tyder ikkje at emnet er nordisk.</li></ul></section>");

    secs.push("<section class=\"om-sec\"><h3>Kva som manglar</h3><ul class=\"plain\">" +
      "<li>Fulltekst vert ikkje publisert her, og søket går ikkje i fulltekst.</li>" +
      "<li>Arkiva er ujamne. Finland har ingen arkivverk. Arkivverk har ingen sitattal og berre tittel i meiningssøket.</li>" +
      "<li>Bøker utan open adresse finst berre som referanse.</li></ul></section>");

    secs.push("<section class=\"om-sec\"><h3>Samandrag og PDF</h3>" +
      table(["Samandrag", "Verk"], [["Frå OpenAlex (metadata)", fmt(num(abs, "o"))], ["Trekt ut av open PDF (automatisk)", fmt(num(abs, "x"))], ["Ingen samandrag i korpuset", fmt(num(abs, "0"))]]) +
      table(["Tilgang", "Verk"], [
        ["Open PDF, kopi i arkivet (open lisens)", fmt(num(acc, "h"))],
        ["Open PDF, kontrollert lenkje (fila ligg hos eigaren)", fmt(num(acc, "v"))],
        ["PDF, ikkje kontrollert adresse", fmt(num(acc, "u"))],
        ["Berre utgjevarside (DOI)", fmt(num(acc, "d"))],
        ["Ingen lenkje", fmt(acc["0"] != null ? acc["0"] : acc.none)],
      ]) +
      "<p>«Kontrollert» tyder at adressa svarte med ei open PDF-fil då ho vart sjekka. Fila ligg hos eigaren og kan flytte seg. «Ikkje kontrollert» kjem frå metadata og kan føre til ei utgjevarside eller ein betalingsmur.</p></section>");

    const lang = c.lang || {};
    secs.push("<section class=\"om-sec\"><h3>Språk</h3>" +
      table(["Språk", "Verk"], Object.keys(lang).sort((x, y) => lang[y] - lang[x]).map((k) => [LANGN[k] || k, fmt(lang[k])])) + "</section>");

    secs.push("<section class=\"om-sec\"><h3>Korleis søket verkar</h3>" +
      "<p><strong>Ordsøk</strong> leitar i tittel, forfattar, tidsskrift, tilknyting og samandrag, og tek ikkje omsyn til ø/ö/å eller målform. <strong>Ordlista</strong> legg til engelske fagord når du skriv norske (taus kunnskap gir òg tacit knowledge). <strong>Språkmodellen</strong> finn verk som liknar på meining, òg på tvers av språk.</p>" +
      "<p>Spørjinga vert rekna ut i nettlesaren og vert ikkje sendt nokon stad. Utan språkmodell brukar søket ord, ordliste og verk som liknar dei beste treffa.</p></section>");

    secs.push("<section class=\"om-sec\"><h3>Målt søkjekvalitet</h3>" + qualityHtml(q) + "</section>");
    secs.push("<section class=\"om-sec\" id=\"ordliste\"><h3>Ordliste</h3><div id=\"glossaryBox\">" + glossaryHtml(g) + "</div></section>");

    secs.push("<section class=\"om-sec\"><h3>Data og kjeldekode</h3><p><a href=\"data/korpus.csv\" download>korpus.csv</a> (heile korpuset som tabell) · <a href=\"https://github.com/lukketsvane/designteori\" target=\"_blank\" rel=\"noopener noreferrer\">GitHub-repoet</a></p></section>");
    return secs.join("");
  }

  const API = { DEFAULT_EXAMPLES, figures, startLines, langNote, qualityHtml, glossaryHtml, aboutHtml };
  if (typeof module === "object" && module.exports) { module.exports = API; } else { window.DTOm = API; }
})();
