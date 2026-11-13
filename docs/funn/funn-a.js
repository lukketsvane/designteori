/* FUNN - seksjon 1 og 2: materialet, vekst og samarbeid (f01 til f08). */
(function () {
  "use strict";
  const F = window.FUNN, n0 = F.n, P = F.p;
  const short = (p) => p.replace(/^før 2000$/, "<2000").replace(/^(\d\d)(\d\d)–(\d\d)$/, "$2–$3");
  const cap = (el, t) => F.d("h4", { text: t }, el);
  const b = (t) => Object.assign(document.createElement("b"), { textContent: t });

  /* ---------- f01: frå rader til verk (vertikal sankey) ---------- */
  F.del.d01 = function (m, d, ctx) {
    const W = ctx.w, mob = W < 560, pad = 2;
    const H = mob ? 400 : 390;
    const L = [28, 150, 262, 372].map((v) => (mob ? v * 1.02 : v * 0.95));
    const svg = F.svg(m, W, H, "Frå 24 812 hente rader til 6 432 registrerte postar, og kva som har fulltekst");
    const ids = {}; d.nodar.forEach((n) => (ids[n.id] = Object.assign({}, n)));
    const gap = mob ? 5 : 9, nh = 20;
    const tot = 27044;
    const s = (W - pad * 2 - gap * 4) / tot;
    const lay = {};
    let x = pad;
    ["ut", "liste", "andre", "ark_att", "fjerna"].forEach((k, i) => { lay[k] = { x, w: ids[k].n * s, lv: 1 }; x += ids[k].n * s + gap; });
    lay.hent_oa = { x: lay.ut.x, w: (ids.ut.n + ids.liste.n + ids.andre.n) * s + gap * 2, lv: 0 };
    lay.hent_ark = { x: lay.ark_att.x, w: (ids.ark_att.n + ids.fjerna.n) * s + gap, lv: 0 };
    lay.reg = { x: lay.liste.x, w: ids.reg.n * s, lv: 2 };
    lay.reg.x = W - pad - lay.reg.w - (mob ? 0 : 0);
    lay.ft = { x: lay.reg.x, w: ids.ft.n * s, lv: 3 };
    lay.utan = { x: lay.reg.x + lay.ft.w, w: ids.utan.n * s, lv: 3 };
    const Y = [14, 112, 222, 322].map((v, i) => (mob ? v * 1.04 : v * 1)), ln = nh;
    const colr = { hent_oa: "var(--oa)", hent_ark: "var(--ark)", ut: "var(--hair)", liste: "var(--oa)", andre: F.hatch(svg, "var(--oa)"), ark_att: "var(--ark)", fjerna: F.hatch(svg, "var(--ark)"), reg: "var(--fg)", ft: "var(--fg)", utan: F.hatch(svg, "var(--dim)") };
    const lcol = { hent_oa: "var(--oa)", hent_ark: "var(--ark)", ut: "var(--dim)", liste: "var(--oa)", andre: "var(--oa)", ark_att: "var(--ark)", fjerna: "var(--ark)", reg: "var(--fg)", ft: "var(--fg)", utan: "var(--dim)" };
    const outOff = {}, inOff = {};
    Object.keys(lay).forEach((k) => { outOff[k] = 0; inOff[k] = 0; });
    const nodeOrderOut = { hent_oa: ["ut", "liste", "andre"], hent_ark: ["ark_att", "fjerna"], liste: ["reg"], andre: ["reg"], ark_att: ["reg"], reg: ["ft", "utan"] };
    const links = svg.appendChild(F.s("g"));
    const inOrder = { reg: ["liste", "andre", "ark_att"], ft: ["reg"], utan: ["reg"], ut: ["hent_oa"], liste: ["hent_oa"], andre: ["hent_oa"], ark_att: ["hent_ark"], fjerna: ["hent_ark"] };
    Object.keys(nodeOrderOut).forEach((a) => nodeOrderOut[a].forEach((b) => {
      const lk = d.lenkjer.find((q) => q.fra === a && q.til === b); if (!lk) return;
      const wd = lk.n * s;
      const oa = lay[a], ob = lay[b];
      const x0 = oa.x + outOff[a], x1 = ob.x + inOff[b];
      outOff[a] += wd; inOff[b] += wd;
      const y0 = Y[oa.lv] + ln, y1 = Y[ob.lv], ym = (y0 + y1) / 2;
      const dpath = "M" + x0 + "," + y0 + " C" + x0 + "," + ym + " " + x1 + "," + ym + " " + x1 + "," + y1 + " L" + (x1 + wd) + "," + y1 + " C" + (x1 + wd) + "," + ym + " " + (x0 + wd) + "," + ym + " " + (x0 + wd) + "," + y0 + " Z";
      const tipt = ids[a].namn + " til " + ids[b].namn.toLowerCase() + "|" + n0(lk.n) + " rader";
      F.s("path", { d: dpath, fill: a === "reg" ? lcol[b] : lcol[a], opacity: b === "ut" ? 0.1 : (a === "reg" ? (b === "ft" ? 0.4 : 0.16) : 0.26), cls: "mk fd", tip: tipt }, links);
    }));
    /* nodar */
    const labels = [];
    Object.keys(lay).forEach((k) => {
      const nd = lay[k], info = ids[k];
      const r = F.s("rect", { x: nd.x, y: Y[nd.lv], width: Math.max(1.5, nd.w), height: ln, fill: colr[k], stroke: (k === "fjerna" || k === "utan") ? "var(--dim)" : null, "stroke-width": 1, cls: "mk fd", tip: info.namn + "|" + n0(info.n) + (k === "ft" ? " verk: " + n0(d.fulltekst.oa) + " frå OpenAlex-laget og " + n0(d.fulltekst.ark) + " frå arkivlaget" : (k === "reg" ? " verk" : " rader")) }, svg);
    });
    /* namn og tal */
    const tw = (t) => t.length * 6.6;
    const put = (t, x, y, anc, b) => { const e = F.s("text", { x, y, "text-anchor": anc, text: t, cls: "halo" + (b ? " b" : " fg") }, svg); return e; };
    const lab = (k, nm) => nm + " " + n0(ids[k].n);
    put(lab("hent_oa", mob ? "OpenAlex-rader" : "OpenAlex-rader henta"), lay.hent_oa.x, Y[0] - 5, "start", true);
    put(lab("hent_ark", "Arkivposter"), W - pad, Y[0] - 5, "end", true);
    put(lab("ut", "Utanfor scope"), lay.ut.x, Y[1] - 5, "start", true);
    put(lab("reg", "Registrerte postar"), lay.reg.x - 8, Y[2] + 14, "end", true);
    /* små nodar: etikettar i ei rekkje under dei, samla i ei forklaring */
    const small = [["liste", "Via tidsskriftlista"], ["andre", "Via tittel eller emne"], ["ark_att", "Arkivverk att"], ["fjerna", "Fjerna på DOI-treff"]];
    const sy = Y[1] + ln + 16;
    const leg = F.d("div", { cls: "leg", style: "margin-top:12px" }, m);
    [["liste", "Via tidsskriftlista"], ["andre", "Via tittel eller emne"], ["ark_att", "Arkivverk att etter dublettsjekk"], ["fjerna", "Fjerna på DOI-treff"] ].forEach(([k, t]) => {
      const sp = F.d("span", null, leg);
      const i = F.d("i", null, sp);
      i.style.background = k === "fjerna" ? "repeating-linear-gradient(45deg,var(--ark) 0 2px,transparent 2px 5px)" : (k === "andre" ? "repeating-linear-gradient(45deg,var(--oa) 0 2px,transparent 2px 5px)" : colr[k]);
      sp.appendChild(document.createTextNode(t + " "));
      F.d("b", { text: n0(ids[k].n), style: "color:var(--fg);font-weight:500" }, sp);
    });
    F.s("text", { x: lay.ft.x - 8, y: Y[3] + 14, "text-anchor": "end", text: "Med fulltekst " + n0(ids.ft.n), cls: "halo b" }, svg);
    F.s("text", { x: W - pad, y: Y[3] + ln + 15, "text-anchor": "end", text: "Utan fulltekst " + n0(ids.utan.n), cls: "halo" }, svg);
  };

  /* ---------- f02: når verka kom, og kva slag dei er ---------- */
  F.del.d02 = function (m, d, ctx) {
    const W = ctx.w, mob = W < 560;
    F.legend(m, [{ c: "var(--oa)", t: "OpenAlex-laget" }, { c: "var(--ark)", t: "Arkivlaget" }]);
    const H = mob ? 190 : 250, pl = 30, pr = 2, pt = 8, pb = 20, strip = 54;
    const svg = F.svg(m, W, H + strip + 8, "Verk per år 1983 til 2026 i to lag, med periodesummar");
    const ar = d.ar, tot = ar.map((_, i) => d.oa[i] + d.ark[i]);
    const x = d3.scaleBand().domain(ar).range([pl, W - pr]).paddingInner(0.14).paddingOuter(0);
    const y = d3.scaleLinear().domain([0, d3.max(tot) * 1.04]).nice().range([H - pb, pt]);
    F.axisY(svg, y, pl, W - pl - pr, { n: 4 });
    const hz = F.hatch(svg, "var(--oa)"), hz2 = F.hatch(svg, "var(--ark)");
    ar.forEach((a, i) => {
      const last = a === d.ufullstendig;
      const g = F.s("g", { cls: "mk", tip: a + (last ? " (ufullstendig, til 4. november)" : "") + "|OpenAlex-laget " + n0(d.oa[i]) + "|Arkivlaget " + n0(d.ark[i]) }, svg);
      F.s("rect", { x: x(a) - 1, y: pt, width: x.bandwidth() + 2, height: H - pb - pt, fill: "transparent" }, g);
      F.s("rect", { x: x(a), y: y(d.oa[i]), width: x.bandwidth(), height: Math.max(0, y(0) - y(d.oa[i])), fill: last ? hz : "var(--oa)", stroke: last ? "var(--oa)" : null, "stroke-width": 1, cls: "gy" }, g);
      F.s("rect", { x: x(a), y: y(tot[i]), width: x.bandwidth(), height: Math.max(0, y(d.oa[i]) - y(tot[i])), fill: last ? hz2 : "var(--ark)", stroke: last ? "var(--ark)" : null, "stroke-width": 1, cls: "gy" }, g);
      if (a % (mob ? 10 : 5) === 0 || a === ar[0]) F.s("text", { x: x(a) + x.bandwidth() / 2, y: H - pb + 14, "text-anchor": "middle", text: a }, svg);
    });
    F.s("text", { x: x(2026) + x.bandwidth(), y: y(tot[tot.length - 1]) - 14, "text-anchor": "end", text: "2026 ufullstendig", cls: "sm halo" }, svg);
    /* periodestripe */
    const ranges = d.periodar.map((p) => { const mt = p.match(/(\d{4})\D+(\d\d)/); if (p.indexOf("før") === 0) return [1983, 1999]; const a = +mt[1]; return [a, Math.floor(a / 100) * 100 + +mt[2]]; });
    ranges.forEach((r, i) => {
      const x0 = x(r[0]), x1 = x(Math.min(r[1], 2026)) + x.bandwidth();
      const g = F.s("g", { cls: "mk fd", tip: d.periodar[i] + "|OpenAlex-laget " + n0(d.per_oa[i]) + "|Arkivlaget " + n0(d.per_ark[i]) }, svg);
      F.s("rect", { x: x0 + 1, y: H + 4, width: Math.max(1, x1 - x0 - 2), height: strip - 4, fill: "var(--soft)", stroke: "var(--line)", "stroke-width": 1, rx: 2 }, g);
      if (x1 - x0 > 30) {
        /* smale periodar: overskrifta på to linjer, så ho ikkje rennar saman med nabokolonnen */
        const lab = short(d.periodar[i]), two = x1 - x0 < 58 && lab.indexOf("–") > 0;
        const lines = two ? [lab.split("–")[0] + "–", lab.split("–")[1]] : [lab];
        lines.forEach((t, k) => F.s("text", { x: (x0 + x1) / 2, y: H + 17 + k * 12, "text-anchor": "middle", text: t }, g));
        F.s("text", { x: (x0 + x1) / 2, y: H + 17 + lines.length * 12 + 3, "text-anchor": "middle", text: n0(d.per_oa[i] + d.per_ark[i]), cls: "b", style: two ? "font-size:10.5px" : null }, g);
      }
    });
    /* slag */
    const head = F.d("div", { style: "margin-top:26px" }, m);
    F.d("h4", { text: "Slag per lag, del av verka (prosent)", style: "font:400 12px/1.35 var(--mono);color:var(--dim);margin:0 0 6px" }, head);
    const types = d.typar, nm = ["artikkel", "konferansebidrag", "bok eller kapittel", "avhandling", "anna", "ukjend"];
    const fills = ["var(--k4)", "var(--k3)", "var(--k2)", { hatch: "var(--k3)" }, "var(--k1)", { outline: true }];
    const lg = F.legend(head, types.map((t, i) => ({ c: i === 3 ? "repeating-linear-gradient(45deg,var(--k3) 0 2px,transparent 2px 5px)" : (i === 5 ? "transparent" : fills[i]), t: nm[i], open: i === 5 })));
    const sv2 = F.svg(m, W, 112, "Slag per lag, del av verka i kvart lag");
    [["OpenAlex-laget", d.typ_sum_oa, 4694, 4], ["Arkivlaget", d.typ_sum_ark, 1738, 62]].forEach(([nme, arr, tt, y0]) => {
      F.s("rect", { x: 0, y: y0 - 2, width: 10, height: 10, rx: 2, fill: y0 < 10 ? "var(--oa)" : "var(--ark)" }, sv2);
      F.s("text", { x: 16, y: y0 + 8, text: nme + " ", cls: "fg" }, sv2).appendChild(Object.assign(F.s("tspan", { text: n0(tt), cls: "b" })));
      let acc = 0;
      arr.forEach((v, i) => {
        if (!v) return;
        const wd = (v / tt) * W;
        const g = F.s("g", { cls: "mk fd", tip: nme + ": " + nm[i] + "|" + n0(v) + " av " + n0(tt) + " (" + F.n(v / tt * 100, 1) + " %)" }, sv2);
        F.s("rect", { x: acc, y: y0 + 16, width: Math.max(0.8, wd - 1.5), height: 22, fill: fillOf(sv2, fills[i]), stroke: i === 5 ? "var(--dim)" : null, "stroke-dasharray": i === 5 ? "3 2" : null }, g);
        if (wd > 34) F.s("text", { x: acc + wd / 2, y: y0 + 52, "text-anchor": "middle", text: F.n(v / tt * 100, 0) + " %" }, g);
        acc += wd;
      });
    });
    function fillOf(s, f) { return F.fillOf(s, f); }
    const av = d.avhandling_ark;
    F.d("p", { cls: "sm" }, m).append("Slaget avhandling i arkivlaget (", b(String(av.thesis)), ") er ", b(av.doktor + " doktor"), " og ", b(av.master + " master"), ". Slag manglar for 671 arkivverk.");
  };

  /* ---------- f03: språk ---------- */
  F.del.d03 = function (m, d, ctx) {
    const [A, B, C] = F.pans(m, 3, "", ["Språkmerking, 4 694 verk", "Verk på landets eige språk, per land", "FormAkademisk: del som ikkje er engelsk, prosent per periode, med n"]);
    /* A: to stolpar med utvida del. Kategoriar i blågrøn skala (svart er reservert for observert) */
    const W = A.w, svg = F.svg(A, W, 128, "Del av verka som er merkte engelsk, og kvar dei ikkje-engelske står");
    const tt = d.engelsk + d.ikkje_engelsk, wI = Math.max(2, (d.ikkje_engelsk / tt) * W);
    F.s("rect", { x: 0, y: 8, width: W - wI - 1, height: 22, fill: "var(--k2)", cls: "mk gx", tip: "Merkt engelsk|" + n0(d.engelsk) + " av " + n0(tt) + " verk" }, svg);
    F.s("rect", { x: W - wI, y: 8, width: wI, height: 22, fill: "var(--k4)", cls: "mk", tip: "Merkt anna enn engelsk|" + n0(d.ikkje_engelsk) + " verk" }, svg);
    F.s("text", { x: 0, y: 46, text: "Engelsk " + n0(d.engelsk), cls: "fg" }, svg);
    F.s("text", { x: W, y: 46, "text-anchor": "end", text: "Ikkje engelsk " + n0(d.ikkje_engelsk), cls: "b" }, svg);
    F.s("path", { d: "M" + (W - wI) + ",31 L" + W + ",31 L" + W + ",64 L0,64 Z", fill: "var(--k4)", opacity: 0.14 }, svg);
    const fa = d.formakademisk.ikkje_engelsk, an = d.ikkje_engelsk - fa;
    F.s("rect", { x: 0, y: 64, width: (fa / d.ikkje_engelsk) * W - 1, height: 22, fill: "var(--k4)", cls: "mk gx", tip: "FormAkademisk|" + n0(fa) + " av " + n0(d.ikkje_engelsk) + " ikkje-engelske verk" }, svg);
    F.s("rect", { x: (fa / d.ikkje_engelsk) * W, y: 64, width: (an / d.ikkje_engelsk) * W, height: 22, fill: F.hatch(svg, "var(--k4)"), stroke: "var(--k4)", "stroke-width": 1, cls: "mk gx", tip: "Andre kanalar|" + n0(an) + " av " + n0(d.ikkje_engelsk) + " ikkje-engelske verk" }, svg);
    F.s("text", { x: 0, y: 102, text: "FormAkademisk " + n0(fa), cls: "b" }, svg);
    F.s("text", { x: W, y: 102, "text-anchor": "end", text: "andre kanalar " + n0(an), cls: "fg" }, svg);
    F.s("text", { x: 0, y: 120, text: "Nedre stolpe: dei " + n0(d.ikkje_engelsk) + " ikkje-engelske, utvida", cls: "sm" }, svg);
    /* B */
    const rows = d.land.map((l) => ({ label: d.land.length && F.landNamn[l.k] + " · " + n0(l.n) + " verk", v: l.del, vtxt: n0(l.eige) + " (" + F.n(l.del, 1) + " %)", color: F.cc(l.k), tip: F.landNamn[l.k] + "|" + n0(l.eige) + " av " + n0(l.n) + " verk med eitt land er på landets eige språk" }));
    F.rows(B, { w: B.w }, { rows, max: 20, ticks: [0, 5, 10, 15, 20], fmt: (v) => F.n(v, 0) + " %", tfmt: (v) => v + " %", label: "Del av verka på landets eige språk", rowH: 36, valW: 7.2 });
    /* C */
    const ps = d.periodar.slice(2), items = ps.map((p, i) => ({ label: short(p), sub: "n " + n0(d.fa_per_n[i + 2]), fade: d.fa_per_n[i + 2] < 40, vals: [d.fa_per_ikkje_engelsk[i + 2]], tip: p + "|" + F.n(d.fa_per_ikkje_engelsk[i + 2], 1) + " % av " + n0(d.fa_per_n[i + 2]) + " FormAkademisk-verk" }));
    F.cols(C, C.w, 200, { items, max: 100, color: "var(--k4)", fmt: (v) => F.n(v, 0), yfmt: (v) => v + "", ticks: [0, 50, 100], label: "FormAkademisk, del som ikkje er engelsk, prosent", always: true });
    F.d("p", { cls: "sm", text: "Totalt " + n0(d.formakademisk.ikkje_engelsk) + " av " + n0(d.formakademisk.n) + " FormAkademisk-verk. Bleike søyler: færre enn 40 verk." }, C);
  };

  /* ---------- f04: fulltekst ---------- */
  F.del.d04 = function (m, d, ctx) {
    const mk = (g, col, group) => ({ label: g.namn + " · " + n0(g.n), v: g.del, vtxt: F.p(g.del, 1), color: col || "var(--fg)", group, tip: g.namn + "|" + n0(g.fulltekst) + " av " + n0(g.n) + " verk med fulltekst (" + F.n(g.del, 1) + " %)" });
    const gr = d.grupper, by = (nm) => gr.find((g) => g.namn === nm);
    const land = { "Norske verk": "NO", "Svenske verk": "SE", "Finske verk": "FI", "Danske verk": "DK" };
    /* tilgang, kanal, land, periode og lag er nå dekte av open PDF (d32); her står berre slag og siteringar */
    const rows = [mk(by("Bokkapittel")), mk(by("Artiklar")), mk(by("Minst 100 siteringar"))];
    F.rows(m, ctx, { rows, max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", fmt: (v) => F.n(v, 1), refs: [{ v: d.alle.del, label: "OpenAlex-laget " + F.p(d.alle.del, 1), left: false }], label: "Del med fulltekst etter slag og siteringar", rowH: ctx.mob ? 33 : 34, gH: 26, valW: 7 });
  };

  /* ---------- f05: rangering mellom land etter teljemåte, og land over tid ---------- */
  F.del.d05 = function (m, d, ctx) {
    const st = ctx.st; st.lag = st.lag || "oa"; st.vis = st.vis || "antal";
    const W = ctx.w, mob = W < 560;
    /* A: rang 2020-24 etter tre teljemåtar */
    F.d("h4", { text: "Rang " + d.rang.periode + ", " + n0(d.rang.verk) + " OpenAlex-verk: same verk, tre teljemåtar", style: "font:400 12px/1.35 var(--mono);color:var(--dim);margin:0 0 8px" }, m);
    const mt = ["Heile verk per land", "Brøkdel per land", "Berre forfattarland"];
    const ks = ["NO", "SE", "DK", "FI", "IS"];
    const rk = {}, dl = d.rang.del;
    for (let j = 0; j < 3; j++) ks.slice().sort((p, q) => dl[q][j] - dl[p][j]).forEach((k, i) => { (rk[k] = rk[k] || [])[j] = i + 1; });
    const lw = mob ? 64 : 112, rw = mob ? 64 : 112, hh = 232, pt = 40;
    const svg = F.svg(m, W, hh, "Rang mellom nordiske land under tre teljemåtar");
    const xs = [0, 1, 2].map((j) => lw + (W - lw - rw) * j / 2), ys = (r) => pt + (r - 1) * ((hh - pt - 14) / 4);
    xs.forEach((x, j) => { F.s("line", { x1: x, x2: x, y1: pt - 10, y2: hh - 10, stroke: "var(--hair)" }, svg); F.s("text", { x: Math.min(Math.max(x, 40), W - 40), y: 12, "text-anchor": j === 0 ? "start" : (j === 2 ? "end" : "middle"), text: mob ? ["Heile", "Brøkdel", "Forf.land"][j] : mt[j], cls: "fg", style: "font-size:12px" }, svg); if (j === 0 && mob) F.s("text", { x: 0, y: 26, text: "verk", cls: "sm" }, svg); });
    ks.forEach((k) => {
      const c = F.cc(k), pts = rk[k].map((r, j) => [xs[j], ys(r)]);
      const g = F.s("g", { cls: "mk fd", tip: F.landNamn[k] + "|rang " + rk[k].join(" · ") + "|del " + dl[k].map((v) => F.n(v, 1) + " %").join(" · ") }, svg);
      F.s("path", { d: d3.line()(pts), fill: "none", stroke: c, "stroke-width": 3, "stroke-linejoin": "round" }, g);
      pts.forEach((q, j) => { F.s("circle", { cx: q[0], cy: q[1], r: 6, fill: c, stroke: "var(--bg)", "stroke-width": 2 }, g); F.s("text", { x: q[0], y: q[1] + 4, "text-anchor": "middle", text: rk[k][j], style: "fill:#fff;font-size:11px;font-weight:500;pointer-events:none" }, g); });
      F.s("text", { x: pts[1][0], y: pts[1][1] - 10, "text-anchor": "middle", text: F.n(dl[k][1], 1), cls: "fg halo", style: "font-size:11.5px" }, g);
      F.s("text", { x: pts[0][0] - 12, y: pts[0][1] + 4, "text-anchor": "end", text: (mob ? k : F.landNamn[k]) + " " + F.n(dl[k][0], 1), cls: "fg", style: "font-size:12px" }, g);
      F.s("text", { x: pts[2][0] + 12, y: pts[2][1] + 4, text: F.n(dl[k][2], 1) + " " + (mob ? k : F.landNamn[k]), cls: "fg", style: "font-size:12px" }, g);
    });
    const sm = d.del_samla, srt = ["NO", "DK", "SE", "FI"].sort((p, q) => sm[q][5] - sm[p][5]);
    F.d("p", { cls: "sm" }, m).append("Tala er del av kredittane i prosent. ", b("Med arkivlaget"), " (1 738 verk til) er Noreg størst 2020–24: " + srt.map((k) => F.landNamn[k] + " " + F.n(sm[k][5], 1) + " %").join(", ") + ". Finland har 0 arkivverk (sjå arkivlaget i første figur). Utan kvitlista held plasseringa Noreg mot Finland ikkje (" + F.n(d.utan_kvitlista.NO, 1) + " mot " + F.n(d.utan_kvitlista.FI, 1) + " %).");
    /* B: land over tid (sekundært) */
    const ctl = F.d("div", { cls: "ctl", style: "margin-top:34px" }, m);
    const host = F.d("div", null, m);
    F.seg(ctl, [{ k: "antal", t: "Antal" }, { k: "andel", t: "Andel" }], st.vis, (k) => { st.vis = k; draw(); }, "Vis");
    F.seg(ctl, [{ k: "oa", t: "OpenAlex-laget" }, { k: "samla", t: "Med arkivlaget" }], st.lag, (k) => { st.lag = k; draw(); }, "Lag");
    function draw() {
      host.textContent = "";
      const samla = st.lag === "samla", share = st.vis === "andel";
      const keys = ["NO", "SE", "DK", "FI", "IS"].concat(samla ? ["utan"] : []);
      const H = mob ? 270 : 330, pl = 34, pr = 28, pt = 8, pb = 22;
      const svg = F.svg(host, W, H, "Verk per år fordelt på land");
      const rows = d.ar.map((a, i) => { const o = { ar: a }; keys.forEach((k) => (o[k] = (d.oa[k] ? d.oa[k][i] : 0) + (samla ? (d.ark[k][i]) : 0))); return o; });
      const stack = d3.stack().keys(keys).offset(share ? d3.stackOffsetExpand : d3.stackOffsetNone)(rows);
      const x = d3.scaleLinear().domain([2000, 2026]).range([pl, W - pr]);
      const ymax = share ? 1 : d3.max(stack[stack.length - 1], (q) => q[1]);
      const y = d3.scaleLinear().domain([0, ymax]).nice().range([H - pb, pt]);
      F.axisY(svg, y, pl, W - pl - pr, { n: 4, fmt: (v) => (share ? Math.round(v * 100) + "" : n0(v)) });
      [2000, 2005, 2010, 2015, 2020, 2025].forEach((a) => { if (!mob || a % 10 === 0 || a === 2025) F.s("text", { x: x(a), y: H - pb + 14, "text-anchor": "middle", text: a }, svg); });
      const area = d3.area().x((q) => x(q.data.ar)).y0((q) => y(q[0])).y1((q) => y(q[1])).curve(d3.curveLinear);
      const hz = F.hatch(svg, "var(--ANNA)");
      stack.forEach((s) => F.s("path", { d: area(s), fill: s.key === "utan" ? hz : F.cc(s.key), opacity: 0.92, cls: "fd" }, svg));
      F.s("rect", { x: x(2025), y: pt, width: x(2026) - x(2025), height: H - pb - pt, fill: "var(--bg)", opacity: 0.45, "pointer-events": "none" }, svg);
      F.s("text", { x: x(2026) - 3, y: pt + 10, "text-anchor": "end", text: "2026 ufullstendig", cls: "sm halo" }, svg);
      const last = rows.length - 2;
      const ends = stack.map((s, i) => ({ y: y((s[last][0] + s[last][1]) / 2) + 4, i }));
      const ny = F.nudge(ends, 12, pt + 8, H - pb);
      stack.forEach((s, i) => { const hgt = y(s[last][0]) - y(s[last][1]); if (hgt > 6 || s.key === "NO") F.s("text", { x: x(2026) + 4, y: ny[i], text: s.key === "utan" ? "–" : s.key, style: "fill:" + (s.key === "utan" ? "var(--dim)" : F.cc(s.key)), cls: "b" }, svg); });
      const names = Object.assign({ utan: "Arkivverk utan land" }, F.landNamn);
      F.xhover(svg, { x0: pl, x1: W - pr, y0: pt, y1: H - pb }, d.ar.length, (i) => x(d.ar[i]), (i) => {
        const tot = keys.reduce((a, k) => a + rows[i][k], 0);
        return d.ar[i] + "|" + keys.map((k) => names[k] + " " + (share ? F.n(rows[i][k] / tot * 100, 1) + " %" : F.n(rows[i][k], 1))).join("|");
      });
      F.legend(host, keys.filter((k) => k !== "utan").map((k) => ({ c: F.cc(k), t: F.landNamn[k] })).concat(samla ? [{ c: "var(--ANNA)", t: "Arkivverk utan land" }] : []));
    }
    draw();
  };

  /* ---------- f06: team og grenser ---------- */
  F.del.d06 = function (m, d, ctx) {
    const [A, B, C] = F.pans(m, 3, "p3", ["Lagstorleik per periode, del av verka (prosent)", "Samarbeid over grenser, del av fleirforfattarverk (prosent)", "Snitt forfattarar per verk (tal)"]);
    const cats = d.periodar.map((p) => ({ label: short(p) }));
    const keys = [{ k: "ein", name: "ein forfattar", fill: "var(--k1)", ink: "var(--fg)" }, { k: "to", name: "to", fill: "var(--k2)", ink: "var(--fg)" }, { k: "tre", name: "tre", fill: "var(--k3)", ink: "var(--bg)" }, { k: "fire", name: "fire eller fleire", fill: "var(--k4)", ink: "var(--bg)" }];
    F.stackCols(A, A.w, 240, { cats, keys, vals: d.per, n: d.per.map((q) => q.n), inside: true, label: "Lagstorleik per periode" });
    F.legend(A, keys.map((k) => ({ c: k.fill, t: k.name })));
    F.lines(B, B.w, 240, { cats: d.periodar, short, series: [{ name: "fleire institusjonar", vals: d.per.map((q) => q.fleire_inst), color: "var(--k4)", w: 2.6 }, { name: "nordisk og utanfor", vals: d.per.map((q) => q.nord_og_utanfor), color: "var(--k3)", dash: "5 3" }, { name: "fleire nordiske land", vals: d.per.map((q) => q.fleire_nordiske), color: "var(--k2)", dash: "1.5 3", hollow: true, w: 2.4 }], min: 0, max: 70, fmt: (v) => F.n(v, 1) + " %", yfmt: (v) => v + "", n: 3, labels: true, above: 8, pr: 4, label: "Samarbeid over grenser" });
    F.lines(C, C.w, 240, { cats: d.periodar, short, series: [{ name: "alle verk", vals: d.per.map((q) => q.snitt), color: "var(--fg)", w: 2.4, lab: { i: 0, dy: -11, a: "start" } }, { name: "artiklar", vals: d.snitt_type.artikkel, color: "var(--k4)", dash: "5 3", w: 1.8, lab: { i: 3, dy: 18 } }, { name: "konferansebidrag", vals: d.snitt_type.konferansebidrag, color: "var(--k3)", w: 1.8, hollow: true, lab: { i: 3, dx: -8, dy: -7, a: "end" } }], min: 1, max: 4.5, fmt: (v) => F.n(v, 2), yfmt: (v) => F.n(v, 1), n: 3, labels: true, above: 8, label: "Snitt forfattarar per verk" });
    F.d("p", { cls: "sm", text: "Artiklar og konferansebidrag er med frå 2010." }, C);
  };

  /* ---------- f07: nullmodell ---------- */
  F.del.d07 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Nordiske land i same verk: observert mot venta ved tilfeldig val", "Tre utanlandske par: observert mot venta"]);
    const W = A.w, H = 150;
    const svg = F.svg(A, W, H, "Nordisk samarbeid mot nullmodell");
    const x = d3.scaleLinear().domain([0, 1700]).range([0, W - 2]);
    const hz = F.hatch(svg, "var(--dim)");
    [["Verk med fleire nordiske land", d.verk, 0], ["Landpar", d.landpar, 1]].forEach(([t, o, i]) => {
      const y0 = 4 + i * 72;
      F.s("text", { x: 0, y: y0 + 8, text: t, cls: "fg" }, svg);
      F.s("rect", { x: 0, y: y0 + 16, width: x(o.venta), height: 18, fill: hz, stroke: "var(--ref)", cls: "mk gx", tip: t + "|Venta ved tilfeldig val: om lag " + n0(o.venta) }, svg);
      F.s("rect", { x: 0, y: y0 + 38, width: x(o.obs), height: 18, fill: "var(--fg)", cls: "mk gx", tip: t + "|Observert: " + n0(o.obs) }, svg);
      /* venteverdien står utanfor det skraverte feltet: til høgre for det om det er plass, elles på tittellinja */
      const vt = "venta om lag " + n0(o.venta);
      if (W - x(o.venta) - 6 >= vt.length * 6.9) F.s("text", { x: x(o.venta) + 6, y: y0 + 29, text: vt, cls: "halo" }, svg);
      else F.s("text", { x: W, y: y0 + 8, "text-anchor": "end", text: vt }, svg);
      F.s("text", { x: x(o.obs) + 6, y: y0 + 51, text: "observert " + n0(o.obs), cls: "b" }, svg);
    });
    const rows = d.utanlandske_par.map((q) => ({ label: q.par, vtxt: n0(q.obs) + " mot " + F.n(q.venta, 1), mark: "none", dots: [{ v: q.venta, color: "var(--ref)", hollow: true }, { v: q.obs, color: "var(--fg)" }], linkc: "var(--ref)", tip: q.par + "|Observert " + n0(q.obs) + "|Venta " + F.n(q.venta, 1) }));
    const mx = d3.max(d.utanlandske_par, (q) => Math.max(q.obs, q.venta)) * 1.15;
    F.rows(B, { w: B.w }, { rows, min: 0, max: Math.ceil(mx / 50) * 50, rowH: 40, label: "Utanlandske par mot venta" });
    F.legend(B, [{ c: "var(--fg)", t: "observert", r: true }, { c: "var(--ref)", t: "venta", r: true, open: true }]);
  };

  /* ---------- f08: institusjonar og forfattarar ---------- */
  F.del.d08 = function (m, d, ctx) {
    const [A, B, C] = F.pans(m, 3, "p3", ["Aktive institusjonar per periode (tal)", "Forfattarar: del av forfattarane mot del av plassane (prosent)", "Del av eigne verk i scope per forfattar, forfattarar med minst fem verk i heile tabellen"]);
    /* A */
    const cats = d.periodar.map((p, i) => ({ label: short(p), vlIn: i === 0, vals: [d.aktive[i]], tip: d.periodar[i] + "|" + d.aktive[i] + " aktive institusjonar|topp ti har " + F.n(d.topp10[i], 1) + " % av verka|" + d.k50[i] + " institusjonar for halvparten" }));
    const h1 = F.cols(A, A.w, 130, { items: cats, max: 160, color: "var(--fg)", ticks: [0, 80, 160], yfmt: (v) => v, label: "Aktive institusjonar" });
    F.s("circle", { cx: h1.x(0) + h1.x.bandwidth() / 2, cy: h1.y(42), r: 4.5, fill: "var(--bg)", stroke: "var(--ref)", "stroke-width": 2 }, h1.svg);
    F.d("h4", { text: "Del av verka i dei ti største institusjonane, prosent", style: "margin-top:18px" }, A);
    const l1 = F.lines(A, A.w, 150, { cats: d.periodar, short, series: [{ name: "topp ti, del av verka", vals: d.topp10, color: "var(--fg)" }], min: 0, max: 100, fmt: (v) => F.n(v, 1) + " %", yfmt: (v) => v + "", n: 2, above: 10, label: "Topp-ti-del av verka" });
    F.s("circle", { cx: l1.x(0), cy: l1.y(55), r: 4.5, fill: "var(--bg)", stroke: "var(--ref)", "stroke-width": 2 }, l1.svg);
    F.d("p", { cls: "sm", text: "Ring: tilfeldige 69 verk, " + d.ref_tilfeldig_69.aktive + " institusjonar og " + d.ref_tilfeldig_69.topp10 + " % i topp ti. Nordiske institusjonar i alt: " + n0(d.institusjonar) + ", av dei " + n0(d.ein_verk) + " med eitt verk." }, A);
    /* B */
    const tp = d.forf_plassar, tf = d.forf_n;
    const bins = d.forf_hist.map((q) => ({ label: q.namn.replace("10 eller fleire", "10+").replace("10+ ", "10+"), vals: [q.forfattarar / tf * 100, q.plassar / tp * 100], tip: q.namn + " verk|" + n0(q.forfattarar) + " forfattarar (" + F.n(q.forfattarar / tf * 100, 1) + " %)|" + n0(q.plassar) + " forfattarplassar (" + F.n(q.plassar / tp * 100, 1) + " %)" }));
    F.cols(B, B.w, 240, { items: bins, series: [{ name: "forfattarar", color: "var(--fg)" }, { name: "plassar", color: "var(--ref)" }], max: 80, fmt: (v) => F.n(v, 0), ticks: [0, 20, 40, 60, 80], vlMax: 7, label: "Verk per forfattar", yfmt: (v) => v });
    F.legend(B, [{ c: "var(--fg)", t: "forfattarar" }, { c: "var(--ref)", t: "forfattarplassar" }]);
    F.d("p", { cls: "sm", text: "Verk per forfattar i scope (4 694 verk): 1, 2, 3, 4, 5–9, 10 eller fleire. " + n0(d.forf_ge5) + " forfattarar har minst fem verk i scope og " + F.n(d.forf_ge5_plassar / tp * 100, 1) + " % av plassane." }, B);
    /* C */
    const g = d.grense, hist = g.hist.map((v, i) => ({ label: F.n(i / 10, 1).replace(",0", "") , vals: [v], color: i < 5 ? "var(--fg)" : "var(--t2)", tip: "Del " + F.n(i / 10, 1) + " til " + F.n((i + 1) / 10, 1) + "|" + v + " forfattarar" }));
    const hh = F.cols(C, C.w, 240, { items: hist, max: 300, color: "var(--fg)", ticks: [0, 100, 200, 300], vl: false, label: "Fordeling av del av eigne verk i feltet", yfmt: (v) => v, pad: 0.1 });
    const mx = hh.x(0) + (g.median * 10) * hh.x.step();
    const hw = hh.x.step() * 5 - 2;
    /* to ulike meldingar, to merke: klammer over dei fem mørke søylene, og medianen på strek */
    F.s("path", { d: "M" + hh.x(0) + ",24 V19 H" + (hh.x(0) + hw) + " V24", fill: "none", stroke: "var(--fg)", "stroke-width": 1.5 }, hh.svg);
    F.s("text", { x: hh.x(0), y: 12, text: F.n(g.under_halv_pct, 1) + " % har under halvparten", cls: "sm b" }, hh.svg);
    F.s("line", { x1: mx, x2: mx, y1: 30, y2: 240 - 24, cls: "ref", style: "stroke:var(--fg);stroke-dasharray:3 3" }, hh.svg);
    F.s("text", { x: mx + 5, y: 44, text: "median " + F.n(g.median, 2), cls: "sm b halo" }, hh.svg);
    F.d("p", { cls: "sm" }, C).append(b(n0(g.n_ge5) + " av " + n0(d.forf_n) + " forfattarar"), " har minst fem verk i heile tabellen (" + n0(d.tabell_rader) + " rader); søylene viser delen av dei som ligg i scope. Berre " + F.n(g.rein_pct, 1) + " % har alle verka sine i scope. Dei under halvparten held " + F.n(g.plassdel_under_halv, 1) + " % av plassane (" + F.n(g.plassdel_under_halv_ge3, 1) + " % blant dei med minst tre verk). Mørke søyler: under halvparten.");
  };
})();
