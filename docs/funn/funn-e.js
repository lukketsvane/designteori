/* FUNN - runde 2: dekning, grenser, arkiv, panel, samanlikning, tilgang, avhandlingar, språk, praksis og vekting (d27 til d36). */
(function () {
  "use strict";
  const F = window.FUNN, n0 = F.n;
  const b = (t) => Object.assign(document.createElement("b"), { textContent: t });
  const cap = (el, t, mt) => F.d("h4", { text: t, style: "font:400 12px/1.35 var(--mono);color:var(--dim);margin:" + (mt == null ? 0 : mt) + "px 0 6px" }, el);
  const sm = (el, ...parts) => { const p = F.d("p", { cls: "sm" }, el); p.append(...parts); return p; };
  const pc = (v, d) => F.n(v, d == null ? 1 : d) + " %";
  const cap1 = (s) => s.replace(/^./, (c) => c.toUpperCase());

  /* ---------- hjelpar: opne ved trykk, markørar ---------- */
  /* ei samanbrett flate som bygger innhaldet først når ho blir opna (breidda finst først då) */
  F.tap = function (p, title, build, st, key) {
    const det = F.d("details", { cls: "mer" }, p);
    F.d("summary", { text: title }, det);
    const body = F.d("div", { cls: "mer-in" }, det);
    let done = false;
    const go = () => { if (done) return; done = true; body.w = Math.floor(body.getBoundingClientRect().width); build(body, body.w); };
    det.addEventListener("toggle", () => { if (st && key) st[key] = det.open; if (det.open) go(); });
    if (st && key && st[key]) { det.open = true; go(); }
    return det;
  };
  /* forklaringsikon: held, flyttar, held ikkje */
  const SYM = 4.4;
  function sym(svg, kind, x, y, extra) {
    const g = F.s("g", extra || {}, svg);
    if (kind === "h") F.s("circle", { cx: x, cy: y, r: SYM, fill: "var(--fg)" }, g);
    else if (kind === "f") { F.s("circle", { cx: x, cy: y, r: SYM, fill: "var(--bg)", stroke: "var(--fg)", "stroke-width": 1.6 }, g); F.s("path", { d: "M" + x + "," + (y - SYM) + " A" + SYM + "," + SYM + " 0 0 0 " + x + "," + (y + SYM) + " Z", fill: "var(--fg)" }, g); }
    else F.s("circle", { cx: x, cy: y, r: SYM, fill: "var(--bg)", stroke: "var(--fg)", "stroke-width": 1.6, "stroke-dasharray": "2.2 1.6" }, g);
    return g;
  }

  /* ---------- d27: postar, ulike verk og kva som er fanga ---------- */
  F.del.d27 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Postar og ulike verk", "Kor mykje av kjende lister som er registrert"]);
    const u = d.ulike, du = d.dublettar;
    F.rows(A, { w: A.w }, { rows: [
      { label: "Registrerte postar", v: d.poster, mark: "knob", r: 4.5, vtxt: n0(d.poster), color: "var(--fg)", tip: "Registrerte postar|" + n0(d.poster) + ": 4 694 i OpenAlex-laget og 1 738 i arkivlaget" },
      { label: "Ulike verk, same tittel, år og førsteforfattar", v: u.m, lo: u.lo, hi: u.hi, mark: "dot", vtxt: n0(u.m), color: "var(--fg)", tip: "Ulike verk|" + n0(u.m) + " med tittel, år og førsteforfattar|intervall " + n0(u.lo) + " til " + n0(u.hi) }],
      min: 6150, max: 6450, ticks: [6200, 6300, 6400], tfmt: (v) => n0(v), rowH: 40, label: "Postar og ulike verk" });
    sm(A, "Dei ", b(n0(du.sum) + " dublettpostar (" + pc(du.pct) + ")"), " fordeler seg slik:");
    const w = A.w, segs = [["innan OpenAlex-laget", du.oa, "var(--oa)"], ["innan arkivlaget", du.ark, "var(--ark)"], ["i begge lag", du.begge, null]];
    const svg = F.svg(A, w, 58, "Dublettpostar etter lag");
    let x = 0;
    segs.forEach(([t, v, c], i) => {
      const sw = Math.max(2, v / du.sum * w) - 2;
      const g = F.s("g", { cls: "mk fd", tip: "Dublettpostar " + t + "|" + v + " av " + du.sum }, svg);
      F.s("rect", { x, y: 4, width: sw, height: 22, fill: c || F.hatch(svg, "var(--oa)", "var(--ark)") }, g);
      F.s("text", { x: x + sw / 2, y: 20, "text-anchor": "middle", text: v, cls: "b", style: "fill:" + (c ? "var(--bg)" : "var(--fg)") + (c ? "" : ";paint-order:stroke;stroke:var(--bg);stroke-width:3px") }, g);
      F.s("text", { x: x + (i === 0 ? 0 : (i === 2 ? sw : sw / 2)), y: 42 + (i === 1 ? 12 : 0), "text-anchor": i === 0 ? "start" : (i === 2 ? "end" : "middle"), text: t, cls: "sm" }, g);
      x += sw + 2;
    });
    const ai = d.arkiv_i_oa, li = d.lister;
    F.rows(B, { w: B.w }, { rows: [
      { label: "Nordes-lister 2005–2025 (om lag " + li[0].n + ")", v: li[0].pct, vtxt: "om lag " + pc(li[0].pct, 0), mark: "bar", color: "var(--fg)", group: "Lister over kva som finst", tip: "Nordes|om lag " + li[0].k + " av om lag " + li[0].n + " oppføringar registrerte" },
      { label: "FormAkademisk, 55 utgåver (" + li[1].n + ")", lo: li[1].lo, hi: li[1].hi, v: null, vtxt: F.n(li[1].lo, 1) + "–" + F.n(li[1].hi, 1) + " %", mark: "range", color: "var(--fg)", tip: "FormAkademisk|" + li[1].k + " av " + li[1].n + " med tittelkopling|" + F.n(li[1].lo, 1) + " til " + F.n(li[1].hi, 1) + " %" },
      { label: "Funne i OpenAlex-laget", v: ai.funne[0], vtxt: "om lag " + pc(ai.funne[0], 0), mark: "bar", color: "var(--fg)", group: "Av " + n0(ai.n) + " arkivposter", tip: "Arkivposter funne i OpenAlex-laget|" + F.n(ai.funne[1], 1) + " til " + F.n(ai.funne[2], 1) + " %" },
      { label: "Berre i tabellen utanfor scope", v: ai.berre_utanfor[0], vtxt: "om lag " + pc(ai.berre_utanfor[0], 0), mark: "bar", color: "var(--t3)", tip: "Berre utanfor scope|" + ai.berre_utanfor[1] + " til " + ai.berre_utanfor[2] + " poster" },
      { label: "Ikkje funne i det hente materialet", v: ai.ikkje[0], vtxt: "om lag " + pc(ai.ikkje[0], 0), mark: "bar", color: "var(--ref)", tip: "Ikkje funne|" + n0(ai.ikkje[1]) + " til " + n0(ai.ikkje[2]) + " poster" }],
      min: 0, max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 38, gH: 26, label: "Dekning" });
    sm(B, "Dei ", b(n0(ai.fjerna)), " postane som vart fjerna på DOI-treff tel som funne av konstruksjon.");
    sm(m, "Fangst-attfangst gir formelt ", b(n0(d.fangst.verk)), " verk (", n0(d.fangst.lo), " til ", n0(d.fangst.hi), "), ", F.n(d.fangst.forhold, 1), " gonger dei ", n0(d.fangst.sett), " ulike verka sett i begge lag. Føresetnadene held ikkje, så talet seier at laga ikkje er uavhengige utval, ikkje kor stort feltet er.");
  };

  /* ---------- d28: kva held når grensa flyttar seg ---------- */
  F.del.d28 = function (m, d, ctx) {
    const W = ctx.w, mob = W < 560;
    const hd = [["utan", "liste"], ["utan", "HCI"], ["med", "ord"], ["alle", "tre"]];
    const full = ["utan kvitlista", "utan HCI-kanalar", "med designordkrav i tittel eller samandrag", "alle tre samstundes"];
    const labW = mob ? 120 : Math.min(300, W * 0.36), r1W = mob ? 42 : 76, cw = (W - labW - r1W) / 4;
    const lh = 13, top = 60;
    const rows = d.tal.map((r) => ({ r, ln: F.wrap(r.namn, Math.floor((labW - 4) / 6.7), mob ? 3 : 2) }));
    rows.forEach((o) => { o.h = Math.max(30, o.ln.length * lh + 9); });
    let H = top;
    rows.forEach((o) => { o.y = H; H += o.h; });
    const foot = H + 6;
    H = foot + 54;
    const svg = F.svg(m, W, H, "Kva av dei 17 kjernetala frå første runde som held under tre snevrare grenser");
    const cx0 = labW + r1W;
    F.s("text", { x: 0, y: 14, text: "Kjernetal", cls: "fg" }, svg);
    F.s("text", { x: labW + r1W - 2, y: 14, "text-anchor": "end", text: "runde 1", cls: "sm" }, svg);
    d.grenser.forEach((g, i) => {
      const x = cx0 + i * cw + cw / 2;
      const gg = F.s("g", { cls: "mk", tip: cap1(full[i]) + "|" + n0(g.n) + " av 4 694 OpenAlex-verk (" + F.n(g.pct, 1) + " %)" }, svg);
      hd[i].forEach((t, k) => F.s("text", { x, y: 14 + k * 13, "text-anchor": "middle", text: t, cls: "fg" }, gg));
      F.s("text", { x, y: 14 + 2 * 13 + 3, "text-anchor": "middle", text: n0(g.n), cls: "sm" }, gg);
      F.s("rect", { x: x - cw / 2, y: 0, width: cw, height: 52, fill: "transparent" }, gg);
    });
    F.s("line", { x1: 0, x2: W, y1: top - 4, y2: top - 4, stroke: "var(--line)" }, svg);
    const kn = { h: "held", f: "flyttar seg", i: "held ikkje" };
    rows.forEach((o, ri) => {
      const r = o.r, y = o.y, cy = y + o.h / 2;
      const g = F.s("g", { cls: "mk fd", tip: r.namn + "|runde 1: " + F.n(r.r1, r.d) + "|" + r.per.map((p, i) => cap1(full[i]) + ": " + (p.v == null ? "talet står ikkje i funnteksten" : F.n(p.v, r.d)) + " (" + kn[p.dom] + ")").join("|") }, svg);
      F.s("rect", { x: 0, y, width: W, height: o.h, fill: ri % 2 ? "transparent" : "var(--soft)" }, g);
      o.ln.forEach((t, k) => F.s("text", { x: 0, y: cy + 4 + (k - (o.ln.length - 1) / 2) * lh, text: t, cls: "fg", style: "font-size:11.5px" }, g));
      F.s("text", { x: labW + r1W - 2, y: cy + 4, "text-anchor": "end", text: F.n(r.r1, r.d), cls: "b" }, g);
      r.per.forEach((p, i) => {
        const x = cx0 + i * cw;
        sym(g, p.dom, x + 8, cy);
        F.s("text", { x: x + cw - 2, y: cy + 4, "text-anchor": "end", text: p.v == null ? "–" : F.n(p.v, r.d), cls: p.dom === "i" ? "b" : "", style: "font-size:11.5px" }, g);
      });
    });
    F.s("line", { x1: 0, x2: W, y1: foot - 4, y2: foot - 4, stroke: "var(--line)" }, svg);
    F.s("text", { x: 0, y: foot + 14, text: "Tal som", cls: "sm" }, svg);
    ["h", "f", "i"].forEach((k, j) => F.s("text", { x: 0, y: foot + 14 + (j + 1) * 13, text: kn[k], cls: "sm" }, svg));
    Object.keys(d.teljing).forEach((key, i) => {
      const t = d.teljing[key], x = cx0 + i * cw;
      t.forEach((v, j) => { sym(svg, ["h", "f", "i"][j], x + 8, foot + 11 + (j + 1) * 13); F.s("text", { x: x + 18, y: foot + 14 + (j + 1) * 13, text: v, cls: "b" }, svg); });
    });
    const lg = F.d("div", { cls: "leg", style: "margin-top:10px" }, m);
    [["h", "held"], ["f", "flyttar seg"], ["i", "held ikkje"]].forEach(([k, t]) => { const s = F.d("span", null, lg); const sv = F.svg(s, 12, 12, ""); sym(sv, k, 6, 6); s.appendChild(document.createTextNode(t)); });
    sm(m, d.regel + " – betyr at klassen er gitt, men talet står ikkje i funnteksten.");
    const k = d.ikkjeforsking;
    F.tap(m, "Utan postar flagga som ikkje-forsking", (body) => {
      sm(body, b(n0(k.flagga) + " postar"), " er flagga med vid regel, ", b(n0(k.kjerne)), " i kjernen. Utan kjernen: median siteringar ", b(k.median[1]), " (framleis ", k.median[0], "), registrert utan sitering ", b(pc(k.usiterte[1])), " mot ", pc(k.usiterte[0]), ", ti største kanalfamiliar ", b(pc(k.topp10[1])), " mot ", pc(k.topp10[0]), ", FormAkademisk ", b(n0(k.fa[1])), " mot ", n0(k.fa[0]), " verk.");
    }, ctx.st, "tap_ik");
  };

  /* ---------- d29: arkivlaget, arkiv for arkiv ---------- */
  F.del.d29 = function (m, d, ctx) {
    const W = ctx.w, mob = W < 560;
    const t = F.d("table", { cls: "tab" }, m);
    const th = F.d("tr", null, F.d("thead", null, t));
    ["Arkiv", "Rå rader", "Gjennom porten", "DOI-treff fjerna", "Verk att"].forEach((x, i) => F.d("th", { text: x, scope: "col", style: i ? "text-align:right" : "" }, th));
    const tb = F.d("tbody", null, t);
    d.arkiv.forEach((a) => {
      const tr = F.d("tr", null, tb);
      F.d("th", { text: a.namn, scope: "row", title: a.namn_full }, tr);
      [a.raa, a.port, a.doi_treff + (a.dobbel ? " + " + a.dobbel : ""), a.att].forEach((v, i) => F.d("td", { text: typeof v === "number" ? n0(v) : v, style: i === 3 ? "font-weight:500" : "" }, tr));
    });
    const tr = F.d("tr", { cls: "sum" }, F.d("tfoot", null, t));
    F.d("th", { text: "Til saman", scope: "row" }, tr);
    const rsum = d.arkiv.reduce((s, a) => s + a.raa, 0);
    [rsum, d.port_sum, n0(d.fjerna_doi) + " + " + d.fjerna_dobbel, d.att].forEach((v, i) => F.d("td", { text: typeof v === "number" ? n0(v) : v, style: i === 3 ? "font-weight:500" : "" }, tr));
    sm(m, "Dei tre første talkolonnene er rader, den siste er verk. «+ 9» er rader fjerna på dobbel DOI. Nordes-merkte verk (408) er 380 Nordes-bidrag og 28 DRS-prefiks-verk.");
    const [A, B] = F.pans(m, 2, "p2", ["Kvart arkiv: del av verka med DOI, open PDF-adresse og ukjend slag", "Tema: del av verka i klynge, arkivlaget mot OpenAlex-laget"]);
    const rowsA = d.arkiv.filter((a) => a.att >= 3).map((a) => {
      const dots = [];
      if (a.doi != null) dots.push({ v: a.doi / a.att * 100, color: "var(--fg)", hollow: true });
      if (a.pdf != null) dots.push({ v: a.pdf / a.att * 100, color: "var(--fg)" });
      if (a.ukjend != null) dots.push({ v: a.ukjend / a.att * 100, color: "var(--fg)", tick: true });
      return { label: a.namn + " · " + n0(a.att) + " verk", mark: "none", dots, link: false, vtxt: " ", tip: (a.namn_full || a.namn) + "|" + n0(a.att) + " verk|DOI " + (a.doi != null ? n0(a.doi) : "ikkje oppgjeve") + "|open PDF-adresse " + (a.pdf != null ? n0(a.pdf) : "ikkje oppgjeve") + "|ukjend slag " + (a.ukjend != null ? n0(a.ukjend) : "ikkje oppgjeve") };
    });
    F.rows(A, { w: A.w }, { rows: rowsA, min: 0, max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 36, label: "Arkiv" });
    F.legend(A, [{ c: "var(--fg)", t: "har DOI", r: true, open: true }, { c: "var(--fg)", t: "open PDF-adresse", r: true }, { c: "var(--fg)", t: "ukjend slag", ln: "solid" }]);
    sm(A, b(pc(d.doi[2])), " av alle ", n0(d.att), " har DOI, ", b(pc(d.pdf[2])), " open PDF-adresse, ", b(pc(d.ukjend[2])), " ukjend slag. Slag manglar for alle DiVA-verk og for 543 av 1 161 NVA-verk.");
    const tm = d.tema;
    F.rows(B, { w: B.w }, { rows: tm.klynger.map((k) => ({ label: k.bokstav + " " + k.namn, mark: "none", dots: [{ v: k.oa, color: "var(--oa)" }, { v: k.ark, color: "var(--ark)" }], linkc: "var(--ref)", vtxt: F.n(k.oa, 1) + " / " + F.n(k.ark, 1), tip: k.namn + "|OpenAlex-laget " + F.n(k.oa, 1) + " %|arkivlaget " + F.n(k.ark, 1) + " %" })), min: 0, max: 20, ticks: [0, 5, 10, 15, 20], tfmt: (v) => v + "", rowH: 38, label: "Tema etter lag" });
    F.legend(B, [{ c: "var(--oa)", t: "OpenAlex-laget", r: true }, { c: "var(--ark)", t: "arkivlaget", r: true }]);
    sm(B, "Seks av tolv klynger er viste: ", n0(tm.arkiv_n), " arkivverk mot ", n0(tm.oa_n), " OpenAlex-verk med fulltekstklynge. Avstanden mellom fordelingane er ", b(F.n(tm.avstand, 1)), ". Berre retninga er brukt, ikkje alle tal.");
  };

  /* ---------- d30: vekst i eit fast panel ---------- */
  F.del.d30 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Verk per periode, " + d.periodar[0] + " og " + d.periodar[1], "Del av verka som ligg i panelet, per periode"]);
    const f = d.faktor, r = d.rate;
    const mk = (label, a, c, fk, rt, extra) => Object.assign({ label: label + " · faktor " + F.n(fk, 2), mark: "none", dots: [{ v: a[0], color: c, hollow: true }, { v: a[1], color: c }], link: true, linkc: c, vtxt: n0(a[0]) + " → " + n0(a[1]), tip: label + "|" + n0(a[0]) + " til " + n0(a[1]) + " verk|faktor " + F.n(fk, 2) + ", årsrate " + F.n(rt, 1) + " %" }, extra || {});
    F.rows(A, { w: A.w }, { rows: [mk("Heile laget", d.alle, "var(--fg)", f.alle, r.alle), mk("Panel av 27 kanalar", d.panel, "var(--fg)", f.panel, r.panel), mk("Utanfor panelet", d.utanfor, "var(--dim)", f.utanfor, r.utanfor)], min: 0, max: 1600, ticks: [0, 400, 800, 1200, 1600], tfmt: (v) => n0(v), rowH: 44, label: "Verk per periode i panelet og utanfor" });
    F.legend(A, [{ c: "var(--fg)", t: d.periodar[0], r: true, open: true }, { c: "var(--fg)", t: d.periodar[1], r: true }]);
    sm(A, "Årsratar ", b(F.n(r.alle, 1) + " %"), " for heile laget, ", b(F.n(r.panel, 1) + " %"), " i panelet og ", b(F.n(r.utanfor, 1) + " %"), " utanfor.");
    F.lines(B, B.w, 190, { cats: d.panelandel_per, series: [{ name: "panelandel", vals: d.panelandel, color: "var(--fg)" }], min: 0, max: 100, fmt: (v) => F.n(v, 1) + " %", yfmt: (v) => v + "", n: 2, label: "Panelandel per periode" });
    sm(B, "Panelet er ", b(d.utval.panel + " av " + n0(d.utval.kanalar) + " kanalar (" + pc(d.utval.pct) + ")"), " med ", b(n0(d.utval.verk) + " av " + n0(d.utval.av) + " verk (" + pc(d.utval.verk_pct) + ")"), ". ", d.bidrag[0] + " av dei " + n0(d.bidrag[1]) + " ekstra verka (" + pc(d.bidrag[2]) + ") kjem frå panelet. Faktor 2010–14 til 2020–24: ", F.n(d.faktor_sist.alle, 2), " for heile laget, ", F.n(d.faktor_sist.panel, 2), " i panelet, ", F.n(d.faktor_sist.utanfor, 2), " utanfor.");
    F.tap(m, "Utan FormAkademisk, og dei siste åra", (body) => {
      const u = d.utan_fa, s = d.sist;
      sm(body, "FormAkademisk har ", b(n0(u.fa_verk) + " av " + n0(d.utval.verk) + " panelverk (" + pc(u.fa_pct) + ")"), ". Utan han er panelfaktoren ", b(F.n(u.faktor, 2)), " og årsrata ", b(F.n(u.rate, 1) + " %"), "; ", u.stig, " av 27 kanalar stig, ", u.like, " er like og ", u.fell, " fell.");
      sm(body, "2025 har ", b(n0(s.y2025) + " verk"), " mot ", n0(s.y2024), " i 2024 (", F.n(s.forhold, 3), "); begge åra er ufullstendige eller har få kjelder.");
    }, ctx.st, "tap_fa");
  };

  /* ---------- d31: samanlikning med nordiske verk utanfor scope ---------- */
  F.del.d31 = function (m, d, ctx) {
    const wide = ctx.w >= 900;
    const host = F.d("div", { cls: "pans " + (wide ? "p3" : "") }, m);
    const col = { A: "var(--fg)", B: "var(--t3)", C: "var(--ref)" }, nm = { A: "Scope", B: "Utanfor, med designord", C: "Utanfor, utan designord" };
    d.rader.forEach((r) => {
      const el = F.d("div", { cls: "pan" }, host);
      F.d("h4", { text: r.namn + (r.eining === "prosent" ? " (prosent)" : ""), style: "color:var(--fg)" }, el);
      el.w = Math.floor(el.getBoundingClientRect().width);
      const rows = ["A", "B", "C"].map((k) => ({ label: nm[k], mark: "none", dots: [{ v: r[k][0], color: col[k], hollow: true }, { v: r[k][1], color: col[k] }], link: true, linkc: col[k], vtxt: F.n(r[k][0], r.d) + " → " + F.n(r[k][1], r.d), tip: nm[k] + "|" + d.periodar[0] + ": " + F.n(r[k][0], r.d) + "|" + d.periodar[1] + ": " + F.n(r[k][1], r.d) }));
      F.rows(el, { w: el.w }, { rows, min: r.akse[0], max: r.akse[1], tfmt: (v) => F.n(v, v % 1 ? 1 : 0), fmt: (v) => F.n(v, r.d), rowH: 28, valW: 7, label: r.namn });
      if (r.diff) F.d("p", { cls: "sm", text: cap1(r.diff) + "." }, el);
    });
    const nn = d.nordiske, el = F.d("div", { cls: "pan" }, host);
    F.d("h4", { text: "To eller fleire nordiske land (prosent)", style: "color:var(--fg)" }, el);
    el.w = Math.floor(el.getBoundingClientRect().width);
    F.rows(el, { w: el.w }, { rows: [{ label: "Auke 2010–14 til 2020–24, scope", v: nn.auke[0], color: col.A, mark: "bar", vtxt: "+" + F.n(nn.auke[0], 1) }, { label: "Auke, utanfor med designord", v: nn.auke[1], color: col.B, mark: "bar", vtxt: "+" + F.n(nn.auke[1], 1) }, { label: "Auke, utanfor utan designord", v: nn.auke[2], color: col.C, mark: "bar", vtxt: "+" + F.n(nn.auke[2], 1) }], min: 0, max: 5, ticks: [0, 1, 2, 3, 4, 5], tfmt: (v) => v + "", rowH: 28, label: "Samarbeid mellom nordiske land" });
    F.d("p", { cls: "sm" }, el).append("Delen 2020–24 er ", b(F.n(nn.a, 1)), " i scope mot ", b(F.n(nn.b, 1)), " utanfor med designord. Tal i poeng.");
    const lg = F.legend(m, [{ c: "var(--fg)", t: "scope", r: true }, { c: "var(--t3)", t: "utanfor, med designord i tittelen", r: true }, { c: "var(--ref)", t: "utanfor, utan designord", r: true }, { c: "var(--fg)", t: d.periodar[0] + " (ring) → " + d.periodar[1] + " (fylt)", r: true, open: true }]);
    lg.style.marginTop = "14px";
    sm(m, "Alle har eit nordisk forfattarland. Der skilnaden i endring har eit intervall som inkluderer 0, skil utvalet ikkje gruppene; det viser ikkje at utviklinga er lik.");
  };

  /* ---------- d32: open PDF ---------- */
  F.del.d32 = function (m, d, ctx) {
    const W = ctx.w;
    cap(m, "Del av OpenAlex-verka med verifisert offentleg PDF, per periode, prosent", 0);
    F.lines(m, W, ctx.mob ? 220 : 260, { cats: d.periodar, short: (p) => p.replace(/^før 2000$/, "<2000").replace(/^(\d\d)(\d\d)–(\d\d)$/, "$2–$3"), series: [
      { name: "alle verk", vals: d.pdf, color: "var(--fg)", w: 2.6 },
      { name: "same kanalmiks", vals: d.fast_miks, color: "var(--t3)", dash: "5 3", w: 2 },
      { name: "utan FormAkademisk og Nordes", vals: d.utan_fa_nordes, color: "var(--dim)", dash: "1.5 3", w: 2, hollow: true }], min: 0, max: 80, fmt: (v) => F.n(v, 1) + " %", yfmt: (v) => v + "", n: 4, label: "Verifisert PDF per periode" });
    F.legend(m, [{ c: "var(--fg)", ln: "solid", t: "alle verk" }, { c: "var(--t3)", ln: "dashed", t: "same kanalmiks" }, { c: "var(--dim)", ln: "dotted", t: "utan FormAkademisk og Nordes" }]);
    sm(m, "Verk per periode: " + d.k.map((q, i) => d.periodar[i] + " " + n0(q[1])).join(", ") + ". Delen står i fylte verdiar for alle verk; same kanalmiks og utan FormAkademisk og Nordes startar 2005.");
    cap(m, "Verifisert PDF, berre uverifisert adresse, berre DOI eller ingenting, per lag", 20);
    const w = W, labW = ctx.mob ? 0 : 110, rh = ctx.mob ? 50 : 34, svg = F.svg(m, w, d.lag.length * rh + 8, "Tilgangsklasse per lag");
    const fills = ["var(--k4)", "var(--k3)", "var(--k2)", "var(--bg)"];
    d.lag.forEach(([nmn, n, v], i) => {
      const y = i * rh + 2, x0 = labW, bw = w - labW;
      if (ctx.mob) F.s("text", { x: 0, y: y + 11, text: nmn + " · " + n0(n) + " verk", cls: "fg" }, svg);
      else F.s("text", { x: 0, y: y + 16, text: nmn, cls: "fg" }, svg);
      let acc = x0;
      v.forEach((p, k) => {
        const sw = p / 100 * bw;
        const g = F.s("g", { cls: "mk fd", tip: nmn + "|" + d.klassar[k] + " " + F.n(p, 1) + " %|" + n0(n) + " verk" }, svg);
        if (sw > 0) F.s("rect", { x: acc, y: y + (ctx.mob ? 18 : 2), width: Math.max(0, sw - 1), height: 22, fill: fills[k], stroke: k === 3 ? "var(--dim)" : null, "stroke-dasharray": k === 3 ? "3 2" : null }, g);
        if (sw > 30) F.s("text", { x: acc + sw / 2, y: y + (ctx.mob ? 33 : 17), "text-anchor": "middle", text: F.n(p, 0), cls: "sm", style: "fill:" + (k < 2 ? "var(--bg)" : "var(--fg)") }, g);
        acc += sw;
      });
    });
    F.legend(m, d.klassar.map((t, i) => ({ c: i === 3 ? "transparent" : fills[i], t, open: i === 3 })));
    sm(m, "Fulltekst i den private cachen er 3 272 verk i sankeyen; verifisert PDF er ", b(n0(d.fulltekst.verifisert)), ". Berre ", d.fulltekst.andre[0], " av ", n0(d.fulltekst.andre[1]), " i dei andre klassane har fulltekst.");
    F.tap(m, "Kanal, land og merking som open", (body, bw) => {
      cap(body, "Del med verifisert PDF per kanalgruppe, OpenAlex-laget", 0);
      F.rows(body, { w: bw }, { rows: d.kanal.map(([t, k, n]) => ({ label: t + " · n " + n0(n), v: k / n * 100, vtxt: F.n(k / n * 100, 1), mark: "bar", color: "var(--k4)", tip: t + "|" + n0(k) + " av " + n0(n) })), max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 32, label: "Verifisert PDF per kanalgruppe" });
      cap(body, "Del med verifisert PDF per land: alle verk, og utan FormAkademisk og Nordes", 22);
      F.rows(body, { w: bw }, { rows: d.land.map(([k, p, kk, n, u]) => ({ label: F.landNamn[k] + " · n " + n0(n), mark: "none", vtxt: F.n(p, 1) + (u != null ? " / " + F.n(u, 1) : ""), dots: [{ v: p, color: F.cc(k) }].concat(u != null ? [{ v: u, color: F.cc(k), hollow: true }] : []), linkc: F.cc(k), tip: F.landNamn[k] + "|" + n0(kk) + " av " + n0(n) + ": " + F.n(p, 1) + " %" + (u != null ? "|utan FormAkademisk og Nordes: " + F.n(u, 1) + " %" : "") })), min: 0, max: 80, ticks: [0, 20, 40, 60, 80], tfmt: (v) => v + "", rowH: 38, label: "Verifisert PDF per land" });
      F.legend(body, [{ c: "var(--fg)", t: "alle verk", r: true }, { c: "var(--fg)", t: "utan FormAkademisk og Nordes", r: true, open: true }]);
      const o = d.oa_status;
      sm(body, "Av ", b(n0(o.opne[0]) + " verk merkte opne"), " har ", b(pc(o.opne[1])), " verifisert PDF og ", pc(o.opne[2]), " berre ein uverifisert adresse. Av ", b(n0(o.stengde[0]) + " merkte stengde"), " har ", b(pc(o.stengde[1])), " verifisert PDF, ", pc(o.stengde[2]), " berre DOI og ", pc(o.stengde[3]), " ingenting. Merkinga stemmer ikkje over eitt med sjekken av PDF-ane.");
    }, ctx.st, "tap_k");
  };

  /* ---------- d33: doktoravhandlingar ---------- */
  F.del.d33 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Doktorpostar etter periode og land", "Del med verifisert open PDF"]);
    const per = d.periode;
    F.cols(A, A.w, 170, { items: per.map(([t, k]) => ({ label: t.replace(/^(\d\d)(\d\d)–(\d\d)$/, "$2–$3").replace("før 2010", "<2010"), vals: [k], tip: t + "|" + k + " doktorpostar" })), max: 36, color: "var(--fg)", fmt: (v) => v + "", ticks: [0, 12, 24, 36], yfmt: (v) => v + "", label: "Doktorpostar per periode", always: true });
    F.rows(A, { w: A.w }, { rows: d.land.map(([k, n]) => ({ label: F.landNamn[k], v: n, vtxt: n + "", mark: "bar", color: F.cc(k), tip: F.landNamn[k] + "|" + n + " doktorpostar" })), max: 40, ticks: [0, 10, 20, 30, 40], tfmt: (v) => v + "", rowH: 30, label: "Doktorpostar etter land" });
    const p = d.pdf;
    const rw = (t, a, c, extra) => Object.assign({ label: t + " · " + a[0] + " av " + n0(a[1]), v: a[2], vtxt: F.n(a[2], 1), mark: "bar", color: c || "var(--fg)", tip: t + "|" + a[0] + " av " + n0(a[1]) + " (" + F.n(a[2], 1) + " %)" }, extra || {});
    F.rows(B, { w: B.w }, { rows: [rw("Doktor, begge lag", p.dr, "var(--fg)", { group: "Doktor mot master og bachelor" }), rw("Master og bachelor", p.ma, "var(--t3)"), rw("Doktor, OpenAlex-laget", p.oa, "var(--oa)", { group: "Doktor etter lag" }), rw("Doktor, arkivlaget", p.ark, "var(--ark)"), rw("Andre arkivverk", p.andre_ark, "var(--ref)", { group: "Til samanlikning" })], max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 34, gH: 26, label: "Open PDF for avhandlingar" });
  };

  /* ---------- d34: nordiskspråklege verk og tekstar ---------- */
  F.del.d34 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Nordiskspråklege verk: del av verka i gruppa", "Ordbruk i fulltekst: del av tekstane som har ordet"]);
    const nd = d.nordisk, pt = d.port, fk = nd.fa;
    const bar = (t, k, n, c, extra) => Object.assign({ label: t + " · " + n0(k) + " av " + n0(n), v: k / n * 100, vtxt: F.n(k / n * 100, 1), mark: "bar", color: c || "var(--fg)", tip: t + "|" + n0(k) + " av " + n0(n) }, extra || {});
    F.rows(A, { w: A.w }, { rows: [
      bar("Alle postar", nd.n, nd.av, "var(--fg)", { group: "Nordisk språk" }), bar("OpenAlex-laget", nd.oa[0], nd.oa[1], "var(--oa)"), bar("Arkivlaget", nd.ark[0], nd.ark[1], "var(--ark)"), bar("FormAkademisk", nd.fa[0], nd.fa[1], "var(--fg)"),
      bar("Alle nordiske", pt.treff[0], pt.treff[1], "var(--fg)", { group: "Tittelen treff i porten" }), bar("Arkivlaget", pt.ark[0], pt.ark[1], "var(--ark)"), bar("OpenAlex-laget", pt.oa[0], pt.oa[1], "var(--oa)"), bar("FormAkademisk", pt.fa[0], pt.fa[1], "var(--fg)")],
      max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 32, gH: 26, label: "Nordiskspråklege verk" });
    sm(A, "FormAkademisk har ", b(fk[0] + " av " + fk[1]), " verk på nordisk språk. Språk og tidsskrift kan ikkje skiljast i data.");
    const o = d.ord, fa = d.fa;
    const ws = o.ord.map(([t, nor, eng]) => {
      const dots = []; if (nor != null) dots.push({ v: nor, color: "var(--fg)" }); if (eng != null) dots.push({ v: eng, color: "var(--fg)", hollow: true });
      return { label: t, mark: "none", dots, linkc: "var(--ref)", link: dots.length > 1, vtxt: (nor != null ? F.n(nor, 1) : "–") + " / " + (eng != null ? F.n(eng, 1) : "–"), tip: t + "|nordiske tekstar " + (nor != null ? F.n(nor, 1) + " %" : "ikkje kontrollert") + "|engelske tekstar " + (eng != null ? F.n(eng, 1) + " %" : "ikkje kontrollert") };
    });
    ws.push({ label: "forsking gjennom design", mark: "none", dots: [{ v: o.rtd[0] / o.rtd[1] * 100, color: "var(--fg)" }, { v: o.rtd[4], color: "var(--fg)", hollow: true }], linkc: "var(--ref)", vtxt: "0 / " + F.n(o.rtd[4], 1), tip: "Forsking gjennom design|" + o.rtd[0] + " av " + o.rtd[1] + " nordiske|" + o.rtd[2] + " av " + n0(o.rtd[3]) + " engelske" });
    ws.push({ label: "formgiving, innan FormAkademisk", mark: "none", dots: [{ v: fa.formgiving[0], color: "var(--fg)" }, { v: fa.formgiving[1], color: "var(--fg)", hollow: true }], linkc: "var(--ref)", vtxt: F.n(fa.formgiving[0], 1) + " / " + F.n(fa.formgiving[1], 1), group: "Same tidsskrift", tip: "Formgiving i FormAkademisk|" + fa.nordisk_n + " nordiske og " + fa.engelsk_n + " engelske tekstar" });
    ws[0].group = o.nordisk_n + " nordiske og " + n0(o.engelsk_n) + " engelske tekstar";
    F.rows(B, { w: B.w }, { rows: ws, min: 0, max: 80, ticks: [0, 20, 40, 60, 80], tfmt: (v) => v + "", rowH: 34, gH: 26, label: "Ordbruk i nordiske og engelske tekstar" });
    F.legend(B, [{ c: "var(--fg)", t: "nordiske tekstar", r: true }, { c: "var(--fg)", t: "engelske tekstar", r: true, open: true }]);
    sm(B, "– betyr ikkje kontrollert. Medverknad er ikkje med: orda i søket er ikkje jamnbyrdige mellom språka. Nullane for ord som står i inngangsporten er bygde inn av porten.");
    F.tap(m, "Bokmål og nynorsk: skrivemåten følgjer teksten", (body, bw) => {
      const s = d.skrivemate, h = s.handverk;
      F.rows(body, { w: bw }, { rows: [
        { label: "håndverk, bokmålstekstar · n " + s.bokmal_n, v: h.bokmal[0] / s.bokmal_n * 100, vtxt: h.bokmal[0] + " av " + s.bokmal_n, mark: "bar", color: "var(--fg)", group: "Skrivemåte i bokmålstekstar" },
        { label: "handverk, bokmålstekstar", v: h.bokmal[1] / s.bokmal_n * 100, vtxt: h.bokmal[1] + " av " + s.bokmal_n, mark: "bar", color: "var(--fg)" },
        { label: "handverk, nynorsktekstar · n " + s.nynorsk_n, v: h.nynorsk[1] / s.nynorsk_n * 100, vtxt: h.nynorsk[1] + " av " + s.nynorsk_n, mark: "bar", color: "var(--fg)", group: "Skrivemåte i nynorsktekstar" },
        { label: "håndverk, nynorsktekstar", v: h.nynorsk[0] / s.nynorsk_n * 100, vtxt: h.nynorsk[0] + " av " + s.nynorsk_n, mark: "bar", color: "var(--fg)" }], max: 100, ticks: [0, 50, 100], tfmt: (v) => v + "", rowH: 32, gH: 26, label: "Skrivemåte for handverk" });
      sm(body, "Summert over fem omgrep utan overlapp har bokmålstekstane bokmålsform i ", b(s.fem.bokmal[0] + " tilfelle"), " og nynorsk form i ", s.fem.bokmal[1], "; nynorsktekstane har nynorsk form i ", b(s.fem.nynorsk[1] + " tilfelle"), " og bokmålsform i ", s.fem.nynorsk[0], ". Svenske (32) og danske (6) fulltekstar er for få til å skildrast.");
    }, ctx.st, "tap_nn");
  };

  /* ---------- d35: praksis, utstilling og handverk som vokabular ---------- */
  F.del.d35 = function (m, d, ctx) {
    const wide = ctx.w >= 900;
    const host = F.d("div", { cls: "pans " + (wide ? "p3" : "") }, m);
    const mkpan = (t) => { const el = F.d("div", { cls: "pan" }, host); F.d("h4", { text: t }, el); el.w = Math.floor(el.getBoundingClientRect().width); return el; };
    const A = mkpan("Tre ordlister: del av " + n0(d.lag.n) + " verk med vokabularet");
    const nm = { praksis: "praksisbasert og kunstnarleg forsking", utstilling: "utstilling", handverk: "handverk" };
    F.rows(A, { w: A.w }, { rows: d.familie.map(([k, t, s, f]) => ({ label: cap1(nm[k]), mark: "none", link: false, dots: [{ v: t, color: "var(--fg)", hollow: true }, { v: s, color: "var(--t3)" }, { v: f, color: "var(--fg)" }], vtxt: F.n(t, 1) + " / " + F.n(s, 1) + " / " + F.n(f, 1), tip: cap1(nm[k]) + "|tittel " + F.n(t, 1) + " %|samandrag " + F.n(s, 1) + " %|fulltekst " + F.n(f, 1) + " %" })), min: 0, max: 16, ticks: [0, 4, 8, 12, 16], tfmt: (v) => v + "", rowH: 42, valW: 7, label: "Vokabular per ordliste" });
    F.legend(A, [{ c: "var(--fg)", t: "tittel", r: true, open: true }, { c: "var(--t3)", t: "tittel eller samandrag", r: true }, { c: "var(--fg)", t: "alle tre", r: true }]);
    sm(A, b(n0(d.lag.tittel[0]) + " verk (" + pc(d.lag.tittel[1]) + ")"), " i tittelen, ", b(n0(d.lag.samandrag[0]) + " (" + pc(d.lag.samandrag[1]) + ")"), " i tittel eller samandrag, ", b(n0(d.lag.fulltekst[0]) + " (" + pc(d.lag.fulltekst[1]) + ")"), " i tittel, samandrag eller fulltekst. Vokabular er ikkje praksis, og nivåa hengjer på ordlista.");
    const B = mkpan("Tradisjonar: del av verka i OpenAlex-laget");
    F.rows(B, { w: B.w }, { rows: d.tradisjon.map(([t, k, p]) => ({ label: t, v: p, vtxt: n0(k) + " · " + F.n(p, 1), mark: "bar", color: "var(--k4)", tip: t + "|" + n0(k) + " verk (" + F.n(p, 1) + " %)" })), max: 25, ticks: [0, 5, 10, 15, 20, 25], tfmt: (v) => v + "", rowH: 32, label: "Tradisjonar" });
    sm(B, b(n0(d.tradisjon_sum[0]) + " verk (" + pc(d.tradisjon_sum[1]) + ")"), " får minst ein av seks tradisjonar, ", b(n0(d.tradisjon_sum[2]) + " (" + pc(d.tradisjon_sum[3]) + ")"), " ingen. Regelen stemmer med lesing for ", d.regel[0], " av ", d.regel[1], " treff (", F.n(d.regel[2], 1), " %). Ein deskriptiv regel, ikkje ei klassifisering.");
    const C = mkpan("Over tid i engelske samandrag, utan FormAkademisk, prosent");
    const t = d.tid;
    F.lines(C, C.w, 210, { cats: t.periodar, series: [
      { name: "praksis", vals: t.praksis, color: "var(--fg)", w: 2.4 },
      { name: "handverk", vals: t.handverk, color: "var(--t3)", dash: "5 3", w: 2 },
      { name: "utstilling", vals: t.utstilling, color: "var(--dim)", dash: "1.5 3", w: 2, hollow: true }], min: 0, max: 10, fmt: (v) => F.n(v, 1) + " %", yfmt: (v) => v + "", n: 5, label: "Vokabular over tid" });
    F.legend(C, [{ c: "var(--fg)", ln: "solid", t: "praksis" }, { c: "var(--t3)", ln: "dashed", t: "handverk" }, { c: "var(--dim)", ln: "dotted", t: "utstilling" }]);
    sm(C, "Handverk er ", b(F.n(t.handverk_alle[0], 1) + " % til 2009 og " + F.n(t.handverk_alle[3], 1) + " % 2020–25"), " med FormAkademisk, men auken er mest dette tidsskriftet: ", t.fa[0] + " av " + t.fa[1], " samandrag med handverk-ord (", F.n(t.fa[2], 1), " %) står der, mot ", F.n(t.fa[3], 1), " % av alle samandrag.");
    F.tap(m, "Tradisjon og ord, norske samandrag og arkivlaget", (body, bw) => {
      const rows = [];
      d.samandrag.forEach((q, i) => {
        const dd = [], tp = [];
        [["handverk", "var(--fg)", false], ["praksis", "var(--t3)", false], ["utstilling", "var(--dim)", true]].forEach(([k, c, h]) => { if (q[k]) { dd.push({ v: q[k][1], color: c, hollow: h }); tp.push(k + " " + q[k][0] + " av " + q.n + " (" + F.n(q[k][1], 1) + " %)"); } });
        rows.push({ label: q.namn + " · n " + n0(q.n), mark: "none", link: false, dots: dd, vtxt: dd.map((x) => F.n(x.v, 1)).join(" / "), tip: q.namn + "|" + tp.join("|") });
      });
      cap(body, "Del av engelske samandrag per tradisjon som har handverk (strek), praksis (grå) eller utstilling (ring)", 0);
      F.rows(body, { w: bw }, { rows, min: 0, max: 35, ticks: [0, 10, 20, 30], tfmt: (v) => v + "", rowH: 36, label: "Vokabular per tradisjon" });
      sm(body, "Handverk i tekstilsamandrag: ", b(pc(d.tekstil_utan_fa[2])), " utan FormAkademisk (", d.tekstil_utan_fa[0], " av ", d.tekstil_utan_fa[1], ").");
      const nr = d.norsk, ak = d.arkiv;
      sm(body, "Av ", b(nr.samandrag + " norske samandrag"), " har ", nr.handverk[0], " (", pc(nr.handverk[1]), ") eit handverk-ord, ", nr.utan_fagnamn[0], " (", pc(nr.utan_fagnamn[1]), ") utan fagnamnet, og ", nr.faget[0], " (", pc(nr.faget[1]), ") nemner skulefaget Kunst og håndverk. ", nr.fa[0], " av dei ", nr.fa[1], " norske samandraga er frå FormAkademisk, så funnet gjeld tidsskriftet.");
      sm(body, "Arkivlaget har samandrag for ", b(ak.samandrag + " verk"), "; ", ak.titlar[0], " titlar (", pc(ak.titlar[1]), ") har vokabularet. I ", ak.fulltekst, " engelske fulltekstar: praksis ", pc(ak.praksis), ", utstilling ", pc(ak.utstilling), ", handverk ", pc(ak.handverk), ". Minst ein tradisjon: ", ak.tradisjon[0], " verk (", pc(ak.tradisjon[1]), "), tenestedesign ", ak.tenestedesign[0], " (", pc(ak.tenestedesign[1]), ").");
    }, ctx.st, "tap_tr");
  };

  /* ---------- d36: same tal etter vekting ---------- */
  F.del.d36 = function (m, d, ctx) {
    const grp = { markør: "Markørdel, engelske fulltekstar (2 176)", omgrep: "Omgrep, engelske fulltekstar", klynge: "Tekstklynger, OpenAlex-kartet", arkiv: "Tekstklynger, med arkivlaget" };
    const rows = [];
    d.rader.filter((r) => r.eining === "prosent").forEach((r) => {
      const g = r.gruppe === "klynge" && /arkivlaget/.test(r.namn) ? "arkiv" : r.gruppe;
      const [lo, hi] = r.etter, dots = [{ v: r.for, color: "var(--fg)", hollow: true }, { v: lo, color: "var(--fg)" }];
      if (hi > lo) dots.push({ v: hi, color: "var(--fg)", tick: true });
      const first = !rows.some((x) => x.group === grp[g]);
      rows.push({ label: r.namn.replace(/, med arkivlaget$/, "").replace(/ \(.*\)$/, "").replace(", markørdel", ""), mark: "none", link: true, linkc: "var(--ref)", dots, vtxt: F.n(r.for, 1) + " → " + F.n(lo, 1) + (hi > lo ? "–" + F.n(hi, 1) : ""), group: first ? grp[g] : null, tip: r.namn + "|uvekta " + F.n(r.for, 1) + " %|vekta " + F.n(lo, 1) + (hi > lo ? " til " + F.n(hi, 1) : "") + " %" });
    });
    F.rows(m, { w: ctx.w }, { rows, min: 0, max: 70, ticks: [0, 10, 20, 30, 40, 50, 60, 70], tfmt: (v) => v + "", rowH: 34, gH: 28, valW: 7.2, label: "Same tal før og etter vekting" });
    F.legend(m, [{ c: "var(--fg)", t: "uvekta", r: true, open: true }, { c: "var(--fg)", t: "vekta mot alle verk (strek: øvre verdi)", r: true }]);
    const sn = d.rader.find((r) => r.eining === "tal");
    sm(m, "Markørdel og omgrepsbreidd flyttar seg lite: markørdelen ligg mellom ", b(F.n(d.spenn_marker[0], 1)), " og ", b(F.n(d.spenn_marker[1], 1) + " %"), " i alle vektingar, og snittet av omgrep er ", F.n(sn.for, 2), " mot ", F.n(sn.etter[0], 2), " til ", F.n(sn.etter[1], 2), ". Klyngeandelar flyttar seg med høgst ", b(F.n(d.maks_klynge_pp, 1) + " poeng"), ". Mønsteret etter periode og slag held seg: ", F.n(d.monster.periode[0], 1), " % mot ", F.n(d.monster.periode[1], 1), " % (2010–14 mot 2015–19), artiklar ", F.n(d.monster.slag[0], 1), " % mot konferansebidrag ", F.n(d.monster.slag[1], 1), " %.");
  };
})();
