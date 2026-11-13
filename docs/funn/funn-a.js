/* FUNN - seksjon 1 og 2: materialet, vekst og samarbeid (f01 til f08). */
(function () {
  "use strict";
  const F = window.FUNN, n0 = F.n, P = F.p;
  const short = (p) => p.replace(/^før 2000$/, "<2000").replace(/^(\d\d)(\d\d)–(\d\d)$/, "$2–$3");
  const cap = (el, t) => F.d("h4", { text: t }, el);

  /* ---------- f01: frå rader til verk (vertikal sankey) ---------- */
  F.fig.f01 = function (m, d, ctx) {
    const W = ctx.w, mob = W < 560, pad = 2;
    const H = mob ? 400 : 390;
    const L = [28, 150, 262, 372].map((v) => (mob ? v * 1.02 : v * 0.95));
    const svg = F.svg(m, W, H, "Frå 24 812 hente rader til 6 432 registrerte verk, og kva som har fulltekst");
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
    const colr = { hent_oa: "var(--oa)", hent_ark: "var(--ark)", ut: "var(--hair)", liste: "var(--oa)", andre: "var(--t3)", ark_att: "var(--ark)", fjerna: F.hatch(svg, "var(--ark)"), reg: "var(--fg)", ft: "var(--fg)", utan: F.hatch(svg, "var(--dim)") };
    const lcol = { hent_oa: "var(--oa)", hent_ark: "var(--ark)", ut: "var(--dim)", liste: "var(--oa)", andre: "var(--t3)", ark_att: "var(--ark)", fjerna: "var(--ark)", reg: "var(--fg)", ft: "var(--fg)", utan: "var(--dim)" };
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
    put(lab("reg", mob ? "Registrerte verk" : "Registrerte verk"), lay.reg.x - 8, Y[2] + 14, "end", true);
    /* små nodar: etikettar i ei rekkje under dei, samla i ei forklaring */
    const small = [["liste", "Via tidsskriftlista"], ["andre", "Via tittel eller emne"], ["ark_att", "Arkivverk att"], ["fjerna", "Fjerna på DOI-treff"]];
    const sy = Y[1] + ln + 16;
    const leg = F.d("div", { cls: "leg", style: "margin-top:12px" }, m);
    [["liste", "Via tidsskriftlista"], ["andre", "Via tittel eller emne"], ["ark_att", "Arkivverk att etter dublettsjekk"], ["fjerna", "Fjerna på DOI-treff"] ].forEach(([k, t]) => {
      const sp = F.d("span", null, leg);
      const i = F.d("i", null, sp);
      i.style.background = (k === "fjerna" || k === "utan") ? "repeating-linear-gradient(45deg,var(--dim) 0 2px,transparent 2px 5px)" : colr[k];
      sp.appendChild(document.createTextNode(t + " "));
      F.d("b", { text: n0(ids[k].n), style: "color:var(--fg);font-weight:500" }, sp);
    });
    F.s("text", { x: lay.ft.x - 8, y: Y[3] + 14, "text-anchor": "end", text: "Med fulltekst " + n0(ids.ft.n), cls: "halo b" }, svg);
    F.s("text", { x: W - pad, y: Y[3] + ln + 15, "text-anchor": "end", text: "Utan fulltekst " + n0(ids.utan.n), cls: "halo" }, svg);
  };

  /* ---------- f02: når verka kom, og kva slag dei er ---------- */
  F.fig.f02 = function (m, d, ctx) {
    const W = ctx.w, mob = W < 560;
    F.legend(m, [{ c: "var(--oa)", t: "OpenAlex-laget" }, { c: "var(--ark)", t: "Arkivlaget" }]);
    const H = mob ? 190 : 250, pl = 30, pr = 2, pt = 8, pb = 20, strip = 40;
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
        F.s("text", { x: (x0 + x1) / 2, y: H + 19, "text-anchor": "middle", text: short(d.periodar[i]) }, g);
        F.s("text", { x: (x0 + x1) / 2, y: H + 33, "text-anchor": "middle", text: n0(d.per_oa[i] + d.per_ark[i]), cls: "b" }, g);
      }
    });
    /* slag */
    const head = F.d("div", { style: "margin-top:26px" }, m);
    const types = d.typar, nm = ["artikkel", "konferansebidrag", "bok eller kapittel", "avhandling", "anna", "ukjend"];
    const fills = ["var(--t4)", "var(--t3)", "var(--t2)", { hatch: "var(--t3)" }, "var(--t1)", { outline: true }];
    const lg = F.legend(head, types.map((t, i) => ({ c: i === 3 ? "repeating-linear-gradient(45deg,var(--t3) 0 2px,transparent 2px 5px)" : (i === 5 ? "transparent" : fills[i]), t: nm[i], open: i === 5 })));
    const sv2 = F.svg(m, W, 112, "Slag per lag");
    [["OpenAlex-laget", d.typ_sum_oa, 4694, 4], ["Arkivlaget", d.typ_sum_ark, 1738, 62]].forEach(([nme, arr, tt, y0]) => {
      F.s("text", { x: 0, y: y0 + 8, text: nme + " ", cls: "fg" }, sv2).appendChild(Object.assign(F.s("tspan", { text: n0(tt), cls: "b" })));
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
  };

  /* ---------- f03: språk ---------- */
  F.fig.f03 = function (m, d, ctx) {
    const [A, B, C] = F.pans(m, 3, "", ["Språkmerking, 4 694 verk", "Verk på landets eige språk, per land", "FormAkademisk: del som ikkje er engelsk, per periode"]);
    /* A: to stolpar med utvida del */
    const W = A.w, svg = F.svg(A, W, 118, "Del av verka som er merkte engelsk");
    const tt = d.engelsk + d.ikkje_engelsk, wI = (d.ikkje_engelsk / tt) * W;
    F.s("rect", { x: 0, y: 8, width: W - wI - 1, height: 22, fill: "var(--t3)", cls: "mk gx", tip: "Merkt engelsk|" + n0(d.engelsk) + " av " + n0(tt) + " verk" }, svg);
    F.s("rect", { x: W - wI, y: 8, width: wI, height: 22, fill: "var(--fg)", cls: "mk", tip: "Merkt anna enn engelsk|" + n0(d.ikkje_engelsk) + " verk" }, svg);
    F.s("text", { x: 0, y: 46, text: "Engelsk " + n0(d.engelsk), cls: "fg" }, svg);
    F.s("path", { d: "M" + (W - wI) + ",32 L0,66 M" + W + ",32 L" + W + ",66", stroke: "var(--ref)", fill: "none" }, svg);
    const fa = d.formakademisk.ikkje_engelsk, an = d.ikkje_engelsk - fa;
    F.s("rect", { x: 0, y: 66, width: (fa / d.ikkje_engelsk) * W - 1, height: 22, fill: "var(--fg)", cls: "mk gx", tip: "FormAkademisk|" + n0(fa) + " av " + n0(d.ikkje_engelsk) + " ikkje-engelske verk" }, svg);
    F.s("rect", { x: (fa / d.ikkje_engelsk) * W, y: 66, width: (an / d.ikkje_engelsk) * W, height: 22, fill: "var(--fg)", opacity: 0.4, cls: "mk gx", tip: "Andre kanalar|" + n0(an) + " av " + n0(d.ikkje_engelsk) + " ikkje-engelske verk" }, svg);
    F.s("text", { x: 0, y: 104, text: "Ikkje engelsk " + n0(d.ikkje_engelsk) + ": FormAkademisk " + n0(fa), cls: "fg" }, svg);
    /* B */
    const rows = d.land.map((l) => ({ label: d.land.length && F.landNamn[l.k] + " · " + n0(l.n) + " verk", v: l.del, vtxt: n0(l.eige) + " (" + F.n(l.del, 1) + " %)", color: F.cc(l.k), tip: F.landNamn[l.k] + "|" + n0(l.eige) + " av " + n0(l.n) + " verk med eitt land er på landets eige språk" }));
    F.rows(B, { w: B.w }, { rows, max: 20, ticks: [0, 5, 10, 15, 20], fmt: (v) => F.n(v, 0) + " %", tfmt: (v) => v + " %", label: "Del av verka på landets eige språk", rowH: 36, valW: 7.2 });
    /* C */
    const ps = d.periodar.slice(2), items = ps.map((p, i) => ({ label: short(p), vals: [d.fa_per_ikkje_engelsk[i + 2]], tip: p + "|" + F.n(d.fa_per_ikkje_engelsk[i + 2], 1) + " % av " + n0(d.fa_per_n[i + 2]) + " FormAkademisk-verk" }));
    F.cols(C, C.w, 190, { items, max: 100, color: "var(--fg)", fmt: (v) => F.n(v, 0), yfmt: (v) => v + "", ticks: [0, 50, 100], label: "FormAkademisk, del som ikkje er engelsk" });
    F.d("p", { cls: "sm", text: "Totalt " + n0(d.formakademisk.ikkje_engelsk) + " av " + n0(d.formakademisk.n) + " FormAkademisk-verk." }, C);
  };

  /* ---------- f04: fulltekst ---------- */
  F.fig.f04 = function (m, d, ctx) {
    const mk = (g, col, group) => ({ label: g.namn + " · " + n0(g.n), v: g.del, vtxt: F.p(g.del, 1), color: col || "var(--fg)", group, tip: g.namn + "|" + n0(g.fulltekst) + " av " + n0(g.n) + " verk med fulltekst (" + F.n(g.del, 1) + " %)" });
    const gr = d.grupper, by = (nm) => gr.find((g) => g.namn === nm);
    const land = { "Norske verk": "NO", "Svenske verk": "SE", "Finske verk": "FI", "Danske verk": "DK" };
    const rows = [
      mk(by("Verk med open lenkje"), null, "Tilgang"), mk(by("Verk utan open lenkje")),
      mk(by("FormAkademisk"), null, "Kanal"),
      mk(by("Norske verk"), F.cc("NO"), "Land"), mk(by("Svenske verk"), F.cc("SE")), mk(by("Finske verk"), F.cc("FI")), mk(by("Danske verk"), F.cc("DK")),
      mk(by("Før 2000"), null, "Alder"), ].concat(d.periodar.map((p) => mk(p)),
      [mk(by("Bokkapittel"), null, "Slag og siteringar"), mk(by("Artiklar")), mk(by("Minst 100 siteringar")),
       mk({ namn: "Arkivlaget", n: d.arkiv.n, fulltekst: d.arkiv.fulltekst, del: d.arkiv.del }, "var(--ark)", "Lag")]);
    F.rows(m, ctx, { rows, max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", fmt: (v) => F.n(v, 1), refs: [{ v: d.alle.del, label: "alle " + F.p(d.alle.del, 1), left: false }], label: "Del med fulltekst per gruppe", rowH: ctx.mob ? 33 : 34, gH: 26, valW: 7 });
  };

  /* ---------- f05: land over tid ---------- */
  F.fig.f05 = function (m, d, ctx) {
    const st = ctx.st; st.lag = st.lag || "oa"; st.vis = st.vis || "antal";
    const ctl = F.d("div", { cls: "ctl" }, m);
    const host = F.d("div", null, m), note = F.d("div", { style: "margin-top:26px" }, m);
    F.seg(ctl, [{ k: "antal", t: "Antal" }, { k: "andel", t: "Andel" }], st.vis, (k) => { st.vis = k; draw(); }, "Vis");
    F.seg(ctl, [{ k: "oa", t: "OpenAlex-laget" }, { k: "samla", t: "Med arkivlaget" }], st.lag, (k) => { st.lag = k; draw(); }, "Lag");
    const W = ctx.w, mob = W < 560;
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
      const area = d3.area().x((q) => x(q.data.ar)).y0((q) => y(q[0])).y1((q) => y(q[1])).curve(d3.curveMonotoneX);
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
    /* kva avgjer rangeringa: Noreg og Finland 2020-24 med tre måtar å telje på */
    const idx = 5;
    const no = [d.del_oa.NO[idx], d.del_samla.NO[idx], d.forf_2020_24.NO], fi = [d.del_oa.FI[idx], d.del_samla.FI[idx], d.forf_2020_24.FI];
    F.d("h4", { text: "Noreg og Finland 2020–24: same verk, tre måtar å telje på (del av verka, prosent)", cls: "", style: "font:400 11.5px/1.35 var(--mono);color:var(--dim);margin:0 0 6px" }, note);
    const nm = ["Berre OpenAlex-laget", "Med arkivlaget", "Berre forfattarland"];
    F.rows(note, ctx, { rows: nm.map((t, i) => ({ label: t, vtxt: "NO " + F.n(no[i], 1) + " · FI " + F.n(fi[i], 1), mark: "none", dots: [{ v: no[i], color: "var(--NO)" }, { v: fi[i], color: "var(--FI)" }], linkc: "var(--ref)", tip: t + "|Noreg " + F.n(no[i], 1) + " %|Finland " + F.n(fi[i], 1) + " %" })), min: 0, max: 40, ticks: [0, 10, 20, 30, 40], tfmt: (v) => v + "", rowH: 36, label: "Noreg og Finland med tre måtar å telje på" });
  };

  /* ---------- f06: team og grenser ---------- */
  F.fig.f06 = function (m, d, ctx) {
    const [A, B, C] = F.pans(m, 3, "p3", ["Lagstorleik per periode, del av verka (prosent)", "Samarbeid over grenser, del av fleirforfattarverk", "Snitt forfattarar per verk"]);
    const cats = d.periodar.map((p) => ({ label: short(p) }));
    const keys = [{ k: "ein", name: "ein forfattar", fill: "var(--t1)", ink: "var(--fg)" }, { k: "to", name: "to", fill: "var(--t2)", ink: "var(--fg)" }, { k: "tre", name: "tre", fill: "var(--t3)" }, { k: "fire", name: "fire eller fleire", fill: "var(--t4)", ink: "var(--bg)" }];
    F.stackCols(A, A.w, 240, { cats, keys, vals: d.per, n: d.per.map((q) => q.n), inside: true, label: "Lagstorleik per periode" });
    F.legend(A, keys.map((k) => ({ c: k.fill, t: k.name })));
    F.lines(B, B.w, 240, { cats: d.periodar, short, series: [{ name: "fleire institusjonar", vals: d.per.map((q) => q.fleire_inst), color: "var(--fg)" }, { name: "nordisk og ikkje-nordisk", vals: d.per.map((q) => q.nord_og_utanfor), color: "var(--dim)", dash: "5 3" }, { name: "to nordiske land eller fleire", vals: d.per.map((q) => q.fleire_nordiske), color: "var(--fg)", dash: "1.5 3", hollow: true }], min: 0, max: 70, fmt: (v) => F.n(v, 1) + " %", yfmt: (v) => v + "", n: 3, label: "Samarbeid over grenser" });
    F.legend(B, [{ c: "var(--fg)", ln: "solid", t: "fleire institusjonar" }, { c: "var(--dim)", ln: "dashed", t: "nordisk og ikkje-nordisk" }, { c: "var(--fg)", ln: "dotted", t: "to nordiske land eller fleire" }]);
    F.lines(C, C.w, 240, { cats: d.periodar, short, series: [{ name: "alle verk", vals: d.per.map((q) => q.snitt), color: "var(--fg)", w: 2.4 }, { name: "artiklar", vals: d.snitt_type.artikkel, color: "var(--dim)", dash: "5 3", w: 1.6 }, { name: "konferansebidrag", vals: d.snitt_type.konferansebidrag, color: "var(--dim)", w: 1.6, hollow: true }], min: 1, max: 4.5, fmt: (v) => F.n(v, 2), yfmt: (v) => F.n(v, 1), n: 3, above: 8, label: "Snitt forfattarar per verk" });
    F.legend(C, [{ c: "var(--fg)", ln: "solid", t: "alle verk" }, { c: "var(--dim)", ln: "dashed", t: "artiklar" }, { c: "var(--dim)", ln: "solid", t: "konferansebidrag" }]);
    F.d("p", { cls: "sm", text: "Artiklar og konferansebidrag er med frå 2010." }, C);
  };

  /* ---------- f07: nullmodell ---------- */
  F.fig.f07 = function (m, d, ctx) {
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
      F.s("text", { x: x(o.venta) - 6, y: y0 + 29, "text-anchor": "end", text: "venta om lag " + n0(o.venta), cls: "halo" }, svg);
      F.s("text", { x: x(o.obs) + 6, y: y0 + 51, text: "observert " + n0(o.obs), cls: "b" }, svg);
    });
    F.d("p", { cls: "sm", text: "Observert er " + F.n(d.forhald, 2) + " av venta for verk og " + F.n(d.forhald_par, 2) + " for landpar." }, A);
    const rows = d.utanlandske_par.map((q) => ({ label: q.par, vtxt: n0(q.obs) + " mot " + F.n(q.venta, 1), mark: "none", dots: [{ v: q.venta, color: "var(--ref)", hollow: true }, { v: q.obs, color: "var(--fg)" }], linkc: "var(--ref)", tip: q.par + "|Observert " + n0(q.obs) + "|Venta " + F.n(q.venta, 1) }));
    const mx = d3.max(d.utanlandske_par, (q) => Math.max(q.obs, q.venta)) * 1.15;
    F.rows(B, { w: B.w }, { rows, min: 0, max: Math.ceil(mx / 50) * 50, rowH: 40, label: "Utanlandske par mot venta" });
    F.legend(B, [{ c: "var(--fg)", t: "observert", r: true }, { c: "var(--ref)", t: "venta", r: true, open: true }]);
  };

  /* ---------- f08: institusjonar og forfattarar ---------- */
  F.fig.f08 = function (m, d, ctx) {
    const [A, B, C] = F.pans(m, 3, "p3", ["Aktive institusjonar per periode", "Forfattarar: del av forfattarane mot del av plassane", "Del av eigne verk i feltet, forfattarar med minst fem verk"]);
    /* A */
    const cats = d.periodar.map((p, i) => ({ label: short(p), vals: [d.aktive[i]], tip: d.periodar[i] + "|" + d.aktive[i] + " aktive institusjonar|topp ti har " + F.n(d.topp10[i], 1) + " % av verka|" + d.k50[i] + " institusjonar for halvparten" }));
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
    F.d("p", { cls: "sm", text: "Verk per forfattar: 1, 2, 3, 4, 5–9, 10 eller fleire. " + n0(d.forf_ge5) + " forfattarar med minst fem verk har " + F.n(d.forf_ge5_plassar / tp * 100, 1) + " % av plassane." }, B);
    /* C */
    const g = d.grense, hist = g.hist.map((v, i) => ({ label: F.n(i / 10, 1).replace(",0", "") , vals: [v], color: i < 5 ? "var(--fg)" : "var(--t2)", tip: "Del " + F.n(i / 10, 1) + " til " + F.n((i + 1) / 10, 1) + "|" + v + " forfattarar" }));
    const hh = F.cols(C, C.w, 240, { items: hist, max: 300, color: "var(--fg)", ticks: [0, 100, 200, 300], vl: false, label: "Fordeling av del av eigne verk i feltet", yfmt: (v) => v, pad: 0.1 });
    const mx = hh.x(0) + (g.median * 10) * hh.x.step() ;
    F.s("line", { x1: mx, x2: mx, y1: 14, y2: 240 - 24, cls: "ref" }, hh.svg);
    F.s("text", { x: mx + 4, y: 26, text: "median " + F.n(g.median, 2), cls: "sm halo b" }, hh.svg);
    F.s("text", { x: C.w - 2, y: 26, "text-anchor": "end", text: F.n(g.under_halv_pct, 1) + " % under halvparten", cls: "sm halo b" }, hh.svg);
    F.s("text", { x: C.w - 2, y: 39, "text-anchor": "end", text: "(mørke søyler)", cls: "sm halo" }, hh.svg);
    F.d("p", { cls: "sm", text: n0(g.n_ge5) + " forfattarar. Berre " + F.n(g.rein_pct, 1) + " % har alle verka sine i feltet. Dei under halvparten held " + F.n(g.plassdel_under_halv, 1) + " % av plassane (" + F.n(g.plassdel_under_halv_ge3, 1) + " % blant dei med minst tre verk)." }, C);
  };
})();
