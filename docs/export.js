/* Eksport av metadata: BibTeX, RIS, CSV og ei enkel referanse. Berre metadata, aldri samandrag.
   Ingen DOM. Klassisk skript (UMD-hale): window.DTExport i nettlesaren, module.exports i node.
   Eit element er {w, acc, pdfUrl, url, lang, flag}; berre w er påkravd. */
(function () {
  "use strict";

  const FOLD_MAP = { "æ": "ae", "ø": "o", "ð": "d", "þ": "th", "ß": "ss", "đ": "d", "ł": "l", "œ": "oe" };
  const fold = (s) => {
    let o = "";
    for (const ch of String(s == null ? "" : s).toLowerCase()) o += Object.prototype.hasOwnProperty.call(FOLD_MAP, ch) ? FOLD_MAP[ch] : ch;
    return o.normalize("NFKD").replace(/[̀-ͯ]/g, "");
  };

  /* kind -> grupper (BibTeX/RIS). review er ein tidsskriftartikkel (endring 20); archive thesis ligg i misc/GEN. */
  function group(kind) {
    switch (kind) {
      case "article": case "review": return "article";
      case "conference-paper": case "proceedings-article": return "inproc";
      case "book-chapter": return "chapter";
      case "book": return "book";
      case "dissertation": return "phd";
      default: return "misc";
    }
  }
  const BIBTYPE = { article: "article", inproc: "inproceedings", chapter: "incollection", book: "book", phd: "phdthesis", misc: "misc" };
  const BIBVENUE = { article: "journal", inproc: "booktitle", chapter: "booktitle", book: "publisher", phd: "school", misc: "howpublished" };
  const RISTYPE = { article: "JOUR", inproc: "CONF", chapter: "CHAP", book: "BOOK", phd: "THES", misc: "GEN" };

  /* Escape berre i title, author, journal, booktitle, howpublished (og publisher/school). Aldri i doi, url, note. */
  function texEscape(s) {
    return String(s == null ? "" : s).replace(/[\\{}~^&%$#_]/g, (c) => ({
      "\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "~": "\\textasciitilde{}", "^": "\\textasciicircum{}",
      "&": "\\&", "%": "\\%", "$": "\\$", "#": "\\#", "_": "\\_",
    }[c]));
  }

  function oneLine(s) { return String(s == null ? "" : s).replace(/\s+/g, " ").trim(); }
  function bareDoi(d) { return oneLine(d).replace(/^https?:\/\/(dx\.)?doi\.org\//i, ""); }
  function venueOf(w) { return oneLine(w.venue || w.source || ""); }

  /* Namn: «Etternamn, Fornamn» vert ståande; elles delt ved siste mellomrom. */
  const PARTICLES = new Set(["de", "van", "von", "der", "den", "da", "di", "del", "della", "la", "le", "af", "av", "zu", "ten", "ter", "du", "dos", "das"]);
  function splitName(name) {
    const n = oneLine(name);
    if (!n) return { family: "", given: "" };
    const c = n.indexOf(",");
    if (c >= 0) return { family: n.slice(0, c).trim(), given: n.slice(c + 1).trim() };
    const parts = n.split(" ");
    if (parts.length < 2) return { family: n, given: "" };
    let k = parts.length - 1;
    while (k > 1 && PARTICLES.has(parts[k - 1].toLowerCase())) k--; // «Amalia de Götzen», «Jan van der Berg»
    return { family: parts.slice(k).join(" "), given: parts.slice(0, k).join(" ") };
  }
  const nameAsListed = (name) => { const { family, given } = splitName(name); return given ? family + ", " + given : family; };
  const initials = (given) => given.split(/[\s]+/).filter(Boolean).map((p) => p.split("-").map((x) => x.charAt(0).toUpperCase() + ".").join("-")).join(" ");

  function addUrl(it) {
    const w = it.w;
    if (w.doi) { const d = bareDoi(w.doi); return d ? "https://doi.org/" + d : ""; }
    return it.url || it.pdfUrl || "";
  }
  function landingOf(it) {
    const w = it.w;
    if (w.doi) { const d = bareDoi(w.doi); if (d) return "https://doi.org/" + d; }
    return it.landing || "";
  }

  function bibKeys(items) {
    const base = items.map((it) => {
      const w = it.w, a = (w.authors || [])[0];
      const fam = fold(a ? splitName(a).family : "anon").replace(/[^a-z0-9]+/g, "") || "anon";
      const tw = (fold(w.title).match(/[a-z0-9]+/) || ["verk"])[0];
      return fam + "-" + (w.year || "nd") + "-" + tw;
    });
    const seen = new Map();
    base.forEach((k) => seen.set(k, (seen.get(k) || 0) + 1));
    const idx = new Map();
    return base.map((k) => {
      if (seen.get(k) === 1) return k;
      const i = idx.get(k) || 0;
      idx.set(k, i + 1);
      return k + String.fromCharCode(97 + (i % 26)) + (i >= 26 ? String(Math.floor(i / 26)) : "");
    });
  }

  function bibtex(items) {
    const keys = bibKeys(items);
    return items.map((it, i) => {
      const w = it.w, g = group(w.kind);
      const f = [];
      const authors = (w.authors || []).map(oneLine).filter(Boolean);
      if (authors.length) f.push(["author", "{" + authors.map(texEscape).join(" and ") + "}"]);
      f.push(["title", "{{" + texEscape(oneLine(w.title)) + "}}"]);
      if (w.year) f.push(["year", "{" + w.year + "}"]);
      const v = venueOf(w);
      if (v) f.push([BIBVENUE[g], "{" + texEscape(v) + "}"]);
      const d = w.doi ? bareDoi(w.doi) : "";
      if (d) f.push(["doi", "{" + d + "}"]);
      const u = addUrl(it);
      if (u) f.push(["url", "{" + u + "}"]);
      f.push(["note", "{Frå designteori-korpuset, id " + w.id + "}"]);
      return "@" + BIBTYPE[g] + "{" + keys[i] + ",\n" + f.map(([k, val]) => "  " + k + " = " + val).join(",\n") + "\n}\n";
    }).join("\n");
  }

  function ris(items) {
    return items.map((it) => {
      const w = it.w, g = group(w.kind), L = [];
      L.push("TY  - " + RISTYPE[g]);
      for (const a of w.authors || []) { const n = nameAsListed(a); if (n) L.push("AU  - " + oneLine(n)); }
      L.push("TI  - " + oneLine(w.title));
      if (w.year) L.push("PY  - " + w.year);
      const v = venueOf(w);
      if (v) L.push("T2  - " + v);
      const d = w.doi ? bareDoi(w.doi) : "";
      if (d) L.push("DO  - " + d);
      const u = addUrl(it);
      if (u) L.push("UR  - " + u);
      L.push("N1  - id " + w.id);
      L.push("ER  - ");
      return L.join("\r\n") + "\r\n";
    }).join("\r\n");
  }

  const CSV_COLS = ["id", "title", "authors", "year", "type", "venue", "doi", "citations", "language", "access", "pdf_url", "landing_url", "flag"];
  function csv(items) {
    const q = (v) => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
    const rows = [CSV_COLS.map(q).join(",")];
    for (const it of items) {
      const w = it.w;
      rows.push([
        w.id, oneLine(w.title), (w.authors || []).join("; "), w.year || "", w.kind || "", venueOf(w),
        w.doi ? bareDoi(w.doi) : "", w.citations == null ? "" : w.citations, it.lang || w.language || "",
        it.acc || "", it.pdfUrl || "", landingOf(it), it.flag || "",
      ].map(q).join(","));
    }
    return "﻿" + rows.join("\r\n") + "\r\n";
  }

  /* Éi linje: «Etternamn, F., Etternamn, F. (år). Tittel. Kjelde. DOI-lenkje» */
  function reference(it) {
    const w = it.w || it;
    const au = (w.authors || []).map((a) => { const { family, given } = splitName(a); return given ? family + ", " + initials(given) : family; }).filter(Boolean).join(", ");
    const parts = [];
    const head = (au ? au + " " : "") + (w.year ? "(" + w.year + ")." : "(utan år).");
    parts.push(head);
    const t = oneLine(w.title);
    if (t) parts.push(/[.?!]$/.test(t) ? t : t + ".");
    const v = venueOf(w);
    if (v) parts.push(v + ".");
    const d = w.doi ? bareDoi(w.doi) : "";
    if (d) parts.push("https://doi.org/" + d);
    return parts.join(" ");
  }

  function ymd(date) {
    const d = date || new Date();
    const p = (n) => String(n).padStart(2, "0");
    return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate());
  }
  const EXT = { bibtex: "bib", ris: "ris", csv: "csv" };
  const MIME = { bibtex: "application/x-bibtex;charset=utf-8", ris: "application/x-research-info-systems;charset=utf-8", csv: "text/csv;charset=utf-8" };
  function filename(kind, which, date) { return "designteori-" + (which === "leseliste" ? "leseliste" : "treff") + "-" + ymd(date) + "." + EXT[kind]; }
  function build(kind, items) { return kind === "bibtex" ? bibtex(items) : kind === "ris" ? ris(items) : csv(items); }

  const API = { group, texEscape, splitName, bibtex, ris, csv, reference, filename, build, ymd, EXT, MIME, CSV_COLS, LIMIT: 1000 };
  if (typeof module === "object" && module.exports) { module.exports = API; } else { window.DTExport = API; }
})();
