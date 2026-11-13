/* Rein vising: escaping, adressegrammatikk, tilgangsmerkelappar, samandragskort, utheving.
   Ingen DOM. Klassisk skript (UMD-hale): window.DTUi i nettlesaren, module.exports i node. */
(function () {
  "use strict";

  const FOLD_MAP = { "æ": "ae", "ø": "o", "ð": "d", "þ": "th", "ß": "ss", "đ": "d", "ł": "l", "œ": "oe" };
  const TABS = ["korpus", "siteringar", "kart", "analyse", "teorielement", "om"];
  const SORTS = ["rel", "first", "cited", "new", "old"];
  const KINDS = ["article", "conf", "chapter", "book", "thesis", "other"];
  const LANGS = ["e", "b", "n", "d", "s", "o"];
  const TILGS = ["pdf", "open", "abs"];

  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  const fmt = (n) => (typeof n === "number" && isFinite(n) ? n.toLocaleString("nn-NO") : "");
  const safeHref = (u) => (typeof u === "string" && /^https?:\/\/[^\s<>"']+$/i.test(u.trim()) ? u.trim() : "");
  const REL = "noopener noreferrer";

  /* ---------- adressegrammatikk (F9) ---------- */
  function dec(s) { try { return decodeURIComponent(s); } catch (e) { return s; } }
  function emptyState() { return { tab: "korpus", q: "", sort: "", yr: null, cc: "", kind: "", lang: "", tilg: "", inst: "", au: "", dup: false, sim: "", work: "", list: null, anchor: "" }; }

  function parseHash(hash) {
    const st = emptyState();
    let h = String(hash == null ? "" : hash).replace(/^#/, "");
    if (!h) return st;
    if (h === "pdf") { st.tilg = "open"; return st; }
    if (h === "ordliste") { st.tab = "om"; st.anchor = "ordliste"; return st; }
    if (h.startsWith("verk/")) { st.work = dec(h.slice(5)); return st; }
    if (h.startsWith("liste=")) {
      st.list = h.slice(6).split("~").map(dec).filter(Boolean).slice(0, 60);
      return st;
    }
    const qi = h.indexOf("?");
    const tab = qi >= 0 ? h.slice(0, qi) : h;
    if (TABS.indexOf(tab) < 0) return st;
    st.tab = tab;
    if (qi < 0 || tab !== "korpus") return st;
    for (const part of h.slice(qi + 1).split("&")) {
      const eq = part.indexOf("=");
      if (eq < 0) continue;
      const k = part.slice(0, eq), v = dec(part.slice(eq + 1));
      switch (k) {
        case "q": st.q = v; break;
        case "sort": if (SORTS.indexOf(v) >= 0) st.sort = v; break;
        case "yr": {
          const m = /^(\d{4})?-(\d{4})?$/.exec(v);
          if (m && (m[1] || m[2])) st.yr = [m[1] ? +m[1] : 0, m[2] ? +m[2] : 0];
          break;
        }
        case "cc": if (/^[A-Z]{2}$/.test(v)) st.cc = v; break;
        case "kind": if (KINDS.indexOf(v) >= 0) st.kind = v; break;
        case "lang": if (LANGS.indexOf(v) >= 0) st.lang = v; break;
        case "tilg": if (TILGS.indexOf(v) >= 0) st.tilg = v; break;
        case "inst": if (/^I\d+$/.test(v)) st.inst = v; break;
        case "au": st.au = v; break;
        case "dup": st.dup = v === "1"; break;
        case "sim": st.sim = v; break;
        default: break; // ukjende parameter vert ignorerte
      }
    }
    return st;
  }

  function buildHash(st) {
    st = Object.assign(emptyState(), st || {});
    if (st.list && st.list.length) return "#liste=" + st.list.slice(0, 60).map(encodeURIComponent).join("~");
    if (st.work) return "#verk/" + encodeURIComponent(st.work);
    if (st.tab !== "korpus") return "#" + st.tab;
    const p = [];
    if (st.q) p.push("q=" + encodeURIComponent(st.q));
    if (st.sort) p.push("sort=" + encodeURIComponent(st.sort));
    if (st.yr && (st.yr[0] || st.yr[1])) p.push("yr=" + (st.yr[0] || "") + "-" + (st.yr[1] || ""));
    if (st.cc) p.push("cc=" + encodeURIComponent(st.cc));
    if (st.kind) p.push("kind=" + encodeURIComponent(st.kind));
    if (st.lang) p.push("lang=" + encodeURIComponent(st.lang));
    if (st.tilg) p.push("tilg=" + encodeURIComponent(st.tilg));
    if (st.inst) p.push("inst=" + encodeURIComponent(st.inst));
    if (st.au) p.push("au=" + encodeURIComponent(st.au));
    if (st.dup) p.push("dup=1");
    if (st.sim) p.push("sim=" + encodeURIComponent(st.sim));
    return p.length ? "#korpus?" + p.join("&") : "#korpus";
  }

  /* tal aktive filter (utan søk og sortering); dublettar som standard skjulte tel ikkje */
  function filterCount(st) {
    let n = 0;
    if (st.yr && (st.yr[0] || st.yr[1])) n++;
    for (const k of ["cc", "kind", "lang", "tilg", "inst", "au"]) if (st[k]) n++;
    if (st.dup) n++;
    return n;
  }

  /* ---------- tilgang (F4) ---------- */
  function doiHref(w) {
    let d = w && w.doi ? String(w.doi).trim() : "";
    if (!d) return "";
    if (/^10\./.test(d)) d = "https://doi.org/" + d;
    return safeHref(d);
  }
  function openAlexHref(w) { return w && /^W\d+$/.test(w.id || "") ? "https://openalex.org/" + w.id : ""; }

  /* code: h|v|u|d|0. item: oppføring frå access.json eller null. Gir {code,label,href,pending,tag,help,cls}. */
  function accessInfo(code, w, item) {
    w = w || {};
    const info = { code, label: "", href: "", pending: false, tag: "", help: "", cls: "acc-" + code };
    if (code === "h") {
      info.label = "Open PDF (kopi i arkivet)";
      info.href = safeHref(item ? item[1] : w.pdf);
      info.tag = "kopi i arkivet" + (item && item[2] ? " · lisens " + item[2] : (w.license ? " · lisens " + w.license : ""));
      info.help = "Kopi som ligg i arkivet fordi verket har open lisens";
      info.ext = item && item[3] ? safeHref(item[3]) : "";
    } else if (code === "v") {
      info.label = "Open PDF";
      info.href = safeHref(item ? item[1] : "");
      info.pending = !info.href;
      info.tag = "kontrollert lenkje, fila ligg hos eigaren";
      info.help = "Adressa er kontrollert og peikar på ei open PDF-fil hos eigaren";
    } else if (code === "u") {
      info.label = "PDF (ikkje kontrollert)";
      info.href = safeHref(item ? item[1] : (w.oa_url || w.source_url));
      info.tag = "ikkje kontrollert";
      info.help = "Adressa er ikkje kontrollert; ho kan føre til ei utgjevarside eller ein betalingsmur";
    } else if (code === "d") {
      info.label = "Utgjevarside";
      info.href = doiHref(w) || safeHref(item ? item[1] : "") || safeHref([w.oa_url, w.source_url].filter((u) => /^https?:\/\/(dx\.)?doi\.org\//i.test(u || ""))[0]);
      info.help = "Berre DOI-lenkja til utgjevaren er kjend";
    }
    return info;
  }

  function accessLinkHtml(info, cls) {
    if (!info || !info.label) return "";
    const c = "act act-link " + info.cls + (cls ? " " + cls : "");
    if (info.href) return '<a class="' + c + '" href="' + esc(info.href) + '" target="_blank" rel="' + REL + '" title="' + esc(info.help) + '">' + esc(info.label) + "</a>";
    if (info.pending) return '<span class="' + c + ' act-pending" aria-disabled="true" title="' + esc(info.help) + '">' + esc(info.label) + " · lastar…</span>";
    return "";
  }
  function accessTagHtml(info) {
    if (!info || !info.tag) return "";
    return '<span class="tag tag-' + esc(info.code) + '" title="' + esc(info.help) + '">' + esc(info.tag) + "</span>";
  }

  /* Utgjevarlenkje for verk utan samandrag (endring 19): DOI, så adressa frå access.json, så OpenAlex. */
  function publisherLink(w, item) {
    let h = doiHref(w);
    if (h) return { href: h, label: "Opne hos utgjevaren" };
    h = safeHref(item ? item[1] : "") || safeHref(w && (w.oa_url || w.source_url));
    if (h) return { href: h, label: "Opne hos utgjevaren" };
    h = openAlexHref(w);
    if (h) return { href: h, label: "Opne i OpenAlex" };
    return null;
  }
  function publisherLinkHtml(pl, cls) {
    if (!pl) return "";
    return '<a class="act act-block ' + (cls || "") + '" href="' + esc(pl.href) + '" target="_blank" rel="' + REL + '">' + esc(pl.label) + "</a>";
  }

  /* ---------- flagg (F14) ---------- */
  function flagInfo(flag) {
    if (flag === "d") return { label: "Mogleg dublett", help: "Eit anna verk i korpuset har same tittel, år og forfattar. Skjult som standard." };
    if (flag === "u") return { label: "Tilknyting ukjend", help: "Arkivverket har ingen landkode, så nordisk tilknyting er ikkje kontrollert." };
    return null;
  }

  /* ---------- utheving ---------- */
  /* Teksten vert escapa først; <mark> leggast på ord (etter folding) som er i termmengda. */
  function highlight(text, termSet, fm, prefixTokens) {
    const s = String(text == null ? "" : text);
    if (!termSet || !termSet.size) return esc(s);
    fm = fm || FOLD_MAP;
    const foldWord = (x) => {
      x = x.toLowerCase();
      let o = "";
      for (const ch of x) o += Object.prototype.hasOwnProperty.call(fm, ch) ? fm[ch] : ch;
      return o.normalize("NFKD").replace(/[̀-ͯ]/g, "");
    };
    let out = "", last = 0;
    const re = /[\p{L}\p{N}]+/gu;
    let m;
    while ((m = re.exec(s))) {
      const f = foldWord(m[0]);
      let hit = termSet.has(f);
      if (!hit && prefixTokens) for (const t of prefixTokens) if (t.length >= 4 && f.startsWith(t)) { hit = true; break; }
      out += esc(s.slice(last, m.index));
      out += hit ? "<mark>" + esc(m[0]) + "</mark>" : esc(m[0]);
      last = m.index + m[0].length;
    }
    return out + esc(s.slice(last));
  }

  /* ---------- samandrag (F1) ---------- */
  const LANG_NAME = { en: "engelsk", nb: "bokmål", nn: "nynorsk", da: "dansk", sv: "svensk", fi: "finsk", de: "tysk", und: "ukjend språk" };

  function abstractHtml(entry, opts) {
    opts = opts || {};
    if (!entry) return "";
    const body = highlight(entry.t, opts.terms, opts.fm, opts.prefix);
    let src;
    if (entry.s === "x") {
      const u = safeHref(entry.u);
      src = '<p class="abs-src">Samandrag trekt ut av den opne PDF-en (automatisk, kan innehalde feil)</p>' +
        (u ? '<a class="act act-block" href="' + esc(u) + '" target="_blank" rel="' + REL + '">Kjelde: opne PDF-en</a>' : "");
    } else {
      src = '<p class="abs-src">Samandrag frå OpenAlex (metadata)</p>';
    }
    const lang = entry.l && entry.l !== "en" ? '<span class="tag tag-lang">samandrag på ' + esc(LANG_NAME[entry.l] || entry.l) + "</span>" : "";
    return '<div class="abs" data-src="' + esc(entry.s) + '"><p class="abs-text">' + body + "</p>" + src + lang + "</div>";
  }

  function noAbstractHtml(w, item) {
    const pl = publisherLink(w, item);
    return '<div class="abs abs-none"><p class="abs-text">Ingen samandrag i korpuset</p>' + publisherLinkHtml(pl) + "</div>";
  }

  /* Tilstand for samandragsfeltet medan skjerven lastar eller feilar */
  function abstractStateHtml(kind) {
    if (kind === "loading") return '<div class="abs abs-wait"><p class="abs-text">Lastar samandrag…</p></div>';
    return '<div class="abs abs-wait"><p class="abs-text">Samandraget kunne ikkje lastast.</p></div>';
  }

  function simPercent(u8) { return Math.round(((u8 > 255 ? 255 : u8 < 0 ? 0 : u8) / 255) * 100); }
  const SIM_NOTE = "Likskap i meining mellom tittel og samandrag; ikkje ein kvalitetsmåling";

  function plural(n, one, many) { return n === 1 ? one : many; }

  const API = {
    FOLD_MAP, TABS, SORTS, KINDS, LANGS, TILGS, LANG_NAME, SIM_NOTE,
    esc, fmt, safeHref, doiHref, openAlexHref, plural,
    emptyState, parseHash, buildHash, filterCount,
    accessInfo, accessLinkHtml, accessTagHtml, publisherLink, publisherLinkHtml, flagInfo,
    highlight, abstractHtml, noAbstractHtml, abstractStateHtml, simPercent,
  };
  if (typeof module === "object" && module.exports) { module.exports = API; } else { window.DTUi = API; }
})();
