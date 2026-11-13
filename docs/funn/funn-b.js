/* FUNN - seksjon 3 og 4: kanalar og siteringar (f10 til f12, f14 til f17). */
(function () {
  "use strict";
  const F = window.FUNN, n0 = F.n, P = F.p;
  const short = (p) => p.replace(/^før 2000$/, "<2000").replace(/^(\d\d)(\d\d)–(\d\d)$/, "$2–$3");
  const chShort = (n) => (/^Architecture, Design and Conservation/.test(n) ? "KADK-serien" : /^International Conference on Engineering/.test(n) ? "EPDE" : /^VBN/.test(n) ? "VBN" : /^Lecture notes/.test(n) ? "LNCS" : n.replace(/^Proceedings of /, "").replace(/ \(.*\)$/, ""));
  const b = (t) => Object.assign(document.createElement("b"), { textContent: t });

  /* ---------- f10: konsentrasjon ---------- */
  F.fig.f10 = function (m, d, ctx) {
    const st = ctx.st; st.vis = st.vis || "alle";
    const ctl = F.d("div", { cls: "ctl" }, m);
    const [A, B, C] = F.pans(m, 3, "p3", ["Lorenz-kurve: kor samla verka ligg i få kanalar", "Dei ti største kanalane, verk", "Per periode"]);
    F.seg(ctl, [{ k: "alle", t: "Alle verk" }, { k: "port", t: "Etter port" }], st.vis, (k) => { st.vis = k; lor(); }, "Vis");
    A.parentNode.insertBefore(ctl, A.parentNode.firstChild);
    const hostA = F.d("div", null, A);
    function lor() {
      hostA.textContent = "";
      const w = A.w, h = Math.min(w, 330), pl = 32, pb = 24, pt = 8, pr = 6;
      const svg = F.svg(hostA, w, h, "Lorenz-kurver for kanalfamiliar");
      const x = d3.scaleLinear().domain([0, 1]).range([pl, w - pr]), y = d3.scaleLinear().domain([0, 1]).range([h - pb, pt]);
      F.axisY(svg, y, pl, w - pl - pr, { values: [0, 0.5, 1], fmt: (v) => v * 100 + "" });
      F.axisX(svg, x, h - pb, h - pb - pt, { values: [0, 0.5, 1], fmt: (v) => v * 100 + "" });
      F.s("line", { x1: x(0), y1: y(0), x2: x(1), y2: y(1), cls: "ref" }, svg);
      F.s("text", { x: x(1) - 4, y: y(1) + 14, "text-anchor": "end", text: "jamn fordeling", cls: "sm halo" }, svg);
      F.s("text", { x: pl + (w - pl - pr) / 2, y: h - 1, "text-anchor": "middle", text: "del av kanalfamiliane, minste først (prosent)", cls: "sm" }, svg);
      const line = (o, col, wd, dash, key, name) => {
        const pts = o.x.map((v, i) => [x(v), y(o.y[i])]);
        F.s("path", { d: d3.line()(pts), fill: "none", stroke: col, "stroke-width": wd, "stroke-dasharray": dash || null, "stroke-linejoin": "round", cls: "fd" }, svg);
        F.s("path", { d: d3.line()(pts), fill: "none", stroke: "transparent", "stroke-width": 14, cls: "mk", tip: name + "|" + n0(o.verk) + " verk i " + n0(o.familiar) + " kanalfamiliar|Gini " + F.n(o.gini, 2) + "|dei ti største har " + F.n(o.topp10, 1) + " %" }, svg);
      };
      if (st.vis === "alle") {
        line(d.alle, "var(--fg)", 2.6, null, "alle", "Alle verk med kanalnamn");
        F.s("text", { x: x(0.5), y: y(0.1) - 12, "text-anchor": "middle", text: "Gini " + F.n(d.alle.gini, 2), cls: "b halo" }, svg);
      } else {
        line(d.liste, "var(--fg)", 2.6, null, "liste", "Via tidsskriftlista");
        line(d.andre, "var(--dim)", 2.6, "5 3", "andre", "Andre verk");
        F.s("text", { x: x(0.12), y: y(0.55), text: "via tidsskriftlista", cls: "b halo" }, svg);
        F.s("text", { x: x(0.12), y: y(0.55) + 13, text: "topp ti " + F.n(d.liste.topp10, 1) + " %", cls: "halo" }, svg);
        F.s("text", { x: x(0.5), y: y(0.1) - 14, "text-anchor": "middle", text: "andre verk, topp ti " + F.n(d.andre.topp10, 1) + " %", style: "fill:var(--dim)", cls: "halo" }, svg);
      }
    }
    lor();
    F.d("p", { cls: "sm" }, A).append("Dei ti største kanalfamiliane har ", b(F.p(d.alle.topp10, 1)), " av verka.");
    /* B */
    F.rows(B, { w: B.w }, { rows: d.topp.map((q) => ({ label: q.namn, v: q.n, vtxt: n0(q.n), color: "var(--fg)", tip: q.namn + "|" + n0(q.n) + " verk" })), max: 500, ticks: [0, 250, 500], mark: "bar", rowH: 32, fmt: (v) => n0(v), label: "Dei ti største kanalane" });
    F.d("p", { cls: "sm" }, B).append("FormAkademisk er ", b(F.p(d.topp[0].n / d.alle.verk * 100, 1)), " av verka med kanalnamn.");
    /* C */
    F.d("h4", { text: "Del av verka i dei ti største kanalane, prosent" }, C);
    F.lines(C, C.w, 150, { cats: d.periodar, short, series: [{ name: "topp ti, del av verka", vals: d.per.map((q) => q.topp10), color: "var(--fg)" }], min: 0, max: 100, fmt: (v) => F.n(v, 1) + " %", yfmt: (v) => v + "", n: 2, above: 10, label: "Topp-ti-del per periode" });
    F.d("h4", { text: "Gini", style: "margin-top:18px" }, C);
    F.lines(C, C.w, 130, { cats: d.periodar, short, series: [{ name: "Gini", vals: d.per.map((q) => q.gini), color: "var(--dim)" }], min: 0, max: 1, fmt: (v) => F.n(v, 2), yfmt: (v) => F.n(v, 1), n: 2, above: 10, label: "Gini per periode" });
    F.d("p", { cls: "sm" }, C).append("Før 2000 er det berre ", b(n0(d.per[0].n)), " verk.");
  };

  /* ---------- f11: nordiske kanalar ---------- */
  F.fig.f11 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p21", ["Kanalklasse per periode, del av verka (prosent)", "Nordisk del per land, 2000–2026"]);
    const vals = d.per.map((q) => ({ fa: Math.max(0, q["nordisk kanal"] - q.nord_utan_fa_nordes), an: q.nord_utan_fa_nordes, int: q["internasjonal kanal"], fs: q.forlagsserie, rep: q.repositorium, uk: q.ukjend }));
    const keys = [{ k: "fa", name: "FormAkademisk og Nordes", fill: "var(--fg)", ink: "var(--bg)" }, { k: "an", name: "andre nordiske kanalar", fill: { hatch: "var(--fg)" } }, { k: "int", name: "internasjonal kanal", fill: "var(--t3)", ink: "var(--bg)" }, { k: "fs", name: "forlagsserie", fill: "var(--t2)", ink: "var(--fg)" }, { k: "rep", name: "repositorium", fill: "var(--t1)", ink: "var(--fg)" }, { k: "uk", name: "ukjend", fill: { outline: true } }];
    F.stackCols(A, A.w, ctx.mob ? 300 : 340, { cats: d.periodar.map((p) => ({ label: short(p) })), keys, vals, n: d.per.map((q) => q.n), inside: true, label: "Kanalklasse per periode" });
    F.legend(A, keys.map((k) => ({ c: k.k === "an" ? "repeating-linear-gradient(45deg,var(--fg) 0 2px,transparent 2px 5px)" : (k.k === "uk" ? "transparent" : k.fill), t: k.name, open: k.k === "uk" })));
    const rows = d.land.map((l) => ({ label: F.landNamn[l.k] + " · " + n0(l.n) + " verk", vtxt: F.n(l.nordisk, 1) + " → " + F.n(l.nordisk_andre, 1), mark: "none", dots: [{ v: l.nordisk, color: F.cc(l.k) }, { v: l.nordisk_andre, color: F.cc(l.k), hollow: true }], linkc: F.cc(l.k), tip: F.landNamn[l.k] + "|Alle verk: " + F.n(l.nordisk, 1) + " % i nordiske kanalar|Utan verk via tidsskriftlista: " + F.n(l.nordisk_andre, 1) + " %" }));
    F.rows(B, { w: B.w }, { rows, min: 0, max: 50, ticks: [0, 10, 20, 30, 40, 50], tfmt: (v) => v + "", rowH: 44, label: "Nordisk del per land, med og utan porten" });
    F.legend(B, [{ c: "var(--fg)", t: "alle verk", r: true }, { c: "var(--fg)", t: "utan verk via tidsskriftlista", r: true, open: true }]);
    F.d("p", { cls: "sm" }, B).append(b(n0(d.fa_norsk) + " av " + n0(d.fa_n)), " FormAkademisk-verk har Noreg, og kanalen har ", b(F.p(d.fa_del_av_norske, 1)), " av alle norske verk med kanalnamn.");
  };

  /* ---------- f12: siteringar etter kanal; kanalfamiliar over tid ---------- */
  F.fig.f12 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p12", ["Registrerte siteringar per verk, verk 2005–2022: median og kvartilar", "Kanalfamiliar etter periode, verk per celle"]);
    const cc = { "Design Studies": "Design Studies", "CoDesign": "CoDesign", "Designing Interactive Systems": "DIS", "FormAkademisk": "FormAkademisk", "Proceedings of DRS": "DRS", "Nordes": "Nordes" };
    F.rows(A, { w: A.w }, { rows: d.sit.map((q) => ({ label: (cc[q.namn] || q.namn) + " · n " + n0(q.n), v: q.median, lo: q.p25, hi: q.p75, mark: "range", vtxt: "median " + F.n(q.median, q.median % 1 ? 1 : 0), color: "var(--fg)", tip: q.namn + "|n " + n0(q.n) + " verk|median " + F.n(q.median, 1) + ", kvartilar " + F.n(q.p25, 1) + " til " + F.n(q.p75, 1) + "|usiterte " + F.n(q.usiterte, 1) + " %" })), min: 0, max: 80, ticks: [0, 20, 40, 60, 80], tfmt: (v) => v + "", rowH: 40, valW: 7.2, label: "Siteringar per verk etter kanal" });
    F.d("p", { cls: "sm" }, A).append("Stolpen er første til tredje kvartil, ringen er medianen.");
    /* matrise */
    const rows = d.matrise.slice().sort((a, c) => a.forste - c.forste || c.n - a.n);
    const W = B.w, mob = W < 520, rh = mob ? 7.5 : 9, padR = mob ? 98 : 150, padT = 34, padL = 10;
    const H = padT + rows.length * rh + 4;
    const svg = F.svg(B, W, H, "Kanalfamiliar etter periode");
    const cw = (W - padL - padR) / 4, mx = d3.max(rows, (r) => d3.max(r.per));
    const op = d3.scaleSqrt().domain([0, mx]).range([0.18, 1]);
    d.matrise_per.forEach((p, i) => F.s("text", { x: padL + cw * i + cw / 2, y: 14, "text-anchor": "middle", text: p, cls: mob ? "sm" : "" }, svg));
    const labelled = [];
    rows.forEach((r, ri) => {
      const y = padT + ri * rh, all4 = r.per.every((v) => v > 0);
      const g = F.s("g", { cls: "mk", tip: r.namn + "|" + r.n + " verk, " + r.forste + " til " + r.siste + "|" + d.matrise_per.map((p, i) => p + ": " + r.per[i]).join("  ") }, svg);
      F.s("rect", { x: 0, y, width: W, height: rh, fill: "transparent" }, g);
      if (all4) F.s("rect", { x: 0, y: y + 1, width: 3, height: rh - 2, fill: "var(--fg)" }, g);
      r.per.forEach((v, i) => { if (v > 0) F.s("rect", { x: padL + cw * i + 1, y: y + 0.6, width: cw - 2, height: rh - 1.2, rx: 1, fill: "var(--fg)", opacity: op(v), cls: "fd" }, g); });
      if (r.n >= (mob ? 45 : 35)) labelled.push({ r, y });
    });
    const ny = F.nudge(labelled.map((q) => ({ y: q.y + rh / 2 + 3.5 })), 11.5, padT + 8, H - 6);
    labelled.forEach((q, i) => F.s("text", { x: padL + cw * 4 + 6, y: ny[i], text: F.trunc(chShort(q.r.namn), Math.floor((padR - 8) / 6.3)), cls: "sm fg" }, svg));
    F.d("p", { cls: "sm" }, B).append("Rader sorterte etter første år. Strek til venstre: ", b(d.alle_fire + " familiar"), " har verk i alle fire periodar. ", b(n0(d.nye_2020_24.verk) + " av " + n0(d.nye_2020_24.av)), " verk 2020–24 ligg i familiar frå 2015 eller seinare.");
  };

  /* ---------- f14: skeive siteringar ---------- */
  F.fig.f14 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Lorenz-kurve for mottekne siteringar", "Del usiterte verk, per publiseringsår"]);
    const w = A.w, h = Math.min(w, 330), pl = 32, pb = 26, pt = 10, pr = 8;
    const svg = F.svg(A, w, h, "Lorenz-kurve for mottekne siteringar");
    const x = d3.scaleLinear().domain([0, 1]).range([pl, w - pr]), y = d3.scaleLinear().domain([0, 1]).range([h - pb, pt]);
    F.axisY(svg, y, pl, w - pl - pr, { values: [0, 0.5, 1], fmt: (v) => v * 100 + "" });
    F.axisX(svg, x, h - pb, h - pb - pt, { values: [0, 0.5, 1], fmt: (v) => v * 100 + "" });
    F.s("line", { x1: x(0), y1: y(0), x2: x(1), y2: y(1), cls: "ref" }, svg);
    const pts = d.x.map((v, i) => [x(v), y(d.y[i])]);
    F.s("path", { d: d3.area().x((q) => q[0]).y0(y(0)).y1((q) => q[1])(pts), fill: "var(--fg)", opacity: 0.07 }, svg);
    F.s("path", { d: d3.line()(pts), fill: "none", stroke: "var(--fg)", "stroke-width": 2.6, "stroke-linejoin": "round", cls: "fd" }, svg);
    F.s("text", { x: pl + (w - pl - pr) / 2, y: h - 2, "text-anchor": "middle", text: "del av verka, minst sitert først (prosent)", cls: "sm" }, svg);
    const mark = (xv, yv, txt, dx, dy, anc) => { F.s("circle", { cx: x(xv), cy: y(yv), r: 4.5, fill: "var(--bg)", stroke: "var(--fg)", "stroke-width": 2 }, svg); F.s("text", { x: x(xv) + dx, y: y(yv) + dy, "text-anchor": anc || "end", text: txt, cls: "b halo" }, svg); };
    mark(0.9, 1 - d.topp10_pct / 100, "topp 10 % har " + F.n(d.topp10_pct, 1) + " %", -8, 4);
    mark(0.99, 1 - d.topp1_pct / 100, "topp 1 % har " + F.n(d.topp1_pct, 1) + " %", -8, 4);
    F.s("text", { x: x(0.02), y: y(0.8), text: "Median " + n0(d.median) + ", snitt " + F.n(d.snitt, 1), cls: "b" }, svg);
    F.s("text", { x: x(0.02), y: y(0.8) + 14, text: n0(d.usiterte) + " verk utan sitering (" + F.n(d.usiterte_pct, 1) + " %)" }, svg);
    /* B: del usiterte per år, med gruppesnitt */
    const wb = B.w, hb = Math.min(wb, 330), plb = 34, prb = 4;
    const sb = F.svg(B, wb, hb, "Del usiterte verk per år");
    const xb = d3.scaleBand().domain(d.ar).range([plb, wb - prb]).paddingInner(0.15), yb = d3.scaleLinear().domain([0, 100]).range([hb - 24, 14]);
    F.axisY(sb, yb, plb, wb - plb - prb, { values: [0, 25, 50, 75, 100], fmt: (v) => v + "" });
    d.ar.forEach((a, i) => { F.s("rect", { x: xb(a), y: yb(d.usitert_ar[i]), width: xb.bandwidth(), height: yb(0) - yb(d.usitert_ar[i]), fill: "var(--ref)", cls: "mk gy", tip: a + "|" + F.n(d.usitert_ar[i], 1) + " % usiterte" }, sb); if (a % 5 === 0) F.s("text", { x: xb(a) + xb.bandwidth() / 2, y: hb - 10, "text-anchor": "middle", text: a, cls: "sm" }, sb); });
    const span = [[2000, 2009], [2010, 2014], [2015, 2019], [2020, 2022], [2023, 2025], [2026, 2026]];
    d.grupper.forEach((g, i) => {
      const x0 = xb(span[i][0]), x1 = xb(span[i][1]) + xb.bandwidth(), yy = yb(g.usitert);
      const gg = F.s("g", { cls: "mk", tip: g.namn + "|" + F.n(g.usitert, 1) + " % av " + n0(g.n) + " verk er usiterte" }, sb);
      F.s("rect", { x: x0, y: yy - 8, width: x1 - x0, height: 16, fill: "transparent" }, gg);
      F.s("line", { x1: x0, x2: x1, y1: yy, y2: yy, stroke: "var(--fg)", "stroke-width": 2.6 }, gg);
      F.s("text", { x: i === 5 ? x1 : (x0 + x1) / 2, y: yy - 7, "text-anchor": i === 5 ? "end" : "middle", text: F.n(g.usitert, 1), cls: "b halo sm" }, gg);
    });
    F.d("h4", { text: "Bokkapittel og artiklar frå 2015–19, del usiterte", style: "font:400 11.5px/1.35 var(--mono);color:var(--dim);margin:20px 0 4px" }, B);
    F.rows(B, { w: B.w }, { rows: [{ label: "Bokkapittel · " + d.kapittel_2015_19.n + " verk", v: d.kapittel_2015_19.usitert, color: "var(--fg)" }, { label: "Artiklar · " + d.artikkel_2015_19.n + " verk", v: d.artikkel_2015_19.usitert, color: "var(--t3)" }], max: 60, ticks: [0, 20, 40, 60], tfmt: (v) => v + "", fmt: (v) => F.n(v, 1) + " %", rowH: 38, label: "Bokkapittel mot artiklar" });
  };

  /* ---------- f15: referansetal og -alder ---------- */
  F.fig.f15 = function (m, d, ctx) {
    const W = ctx.w, rows = d.periodar, pl = 4, pr = 4, rh = ctx.mob ? 92 : 96, top = 8, ph = 52;
    const H = top + rows.length * rh + 34;
    const svg = F.svg(m, W, H, "Referanseliste og referansealder per periode");
    const bins = 41, x = d3.scaleBand().domain(d3.range(bins)).range([pl, W - pr]).paddingInner(0.14);
    const shares = rows.map((r) => { const s = d3.sum(r.alder_hist); return r.alder_hist.map((v) => v / s); });
    const mx = d3.max(shares, (s) => d3.max(s.slice(0, 40)));
    const y = d3.scaleLinear().domain([0, mx]).range([ph, 0]);
    rows.forEach((r, ri) => {
      const y0 = top + ri * rh;
      const g = F.s("g", { transform: "translate(0," + y0 + ")" }, svg);
      F.s("text", { x: pl, y: 12, text: r.namn, cls: "b" }, g);
      F.s("text", { x: W - pr, y: 12, "text-anchor": "end", text: n0(r.median_ref) + " ref. · alder " + n0(r.median_alder) + " · ≤5 år " + F.n(r.del_5, 1) + " %" }, g);
      const gy = F.s("g", { transform: "translate(0,26)" }, g);
      F.s("line", { x1: pl, x2: W - pr, y1: ph, y2: ph, stroke: "var(--line)" }, gy);
      shares[ri].forEach((s, i) => {
        const hh = Math.min(ph, ph - y(s)), cap = i === 40;
        F.s("rect", { x: x(i), y: ph - hh, width: x.bandwidth(), height: Math.max(0.6, hh), fill: i <= 5 ? "var(--fg)" : (cap ? "var(--ref)" : "var(--t3)"), opacity: i <= 5 ? 1 : (cap ? 0.8 : 0.55), cls: "mk gy", tip: r.namn + "|" + (cap ? "40 år eller meir" : "Alder " + i + " år") + "|" + F.n(s * 100, 1) + " % av referansane med kjent år" }, gy);
      });
      const mxp = x(Math.min(40, Math.round(r.median_alder))) + x.bandwidth() / 2;
      F.s("line", { x1: mxp, x2: mxp, y1: -2, y2: ph, stroke: "var(--bg)", "stroke-width": 3 }, gy);
      F.s("line", { x1: mxp, x2: mxp, y1: -2, y2: ph, stroke: "var(--fg)", "stroke-width": 1, "stroke-dasharray": "2 2" }, gy);
    });
    [0, 10, 20, 30, 40].forEach((t) => F.s("text", { x: x(t) + x.bandwidth() / 2, y: H - 8, "text-anchor": t === 0 ? "start" : (t === 40 ? "end" : "middle"), text: t === 40 ? "40+" : t }, svg));
    F.s("text", { x: W - pr, y: H + 8, "text-anchor": "end", text: "alder i år frå utgjeving", cls: "sm" }, svg);
    F.d("p", { cls: "sm" }, m).append("Mørke søyler er fem år eller yngre. Stipla strek er medianen. ", b(n0(d.verk)), " av ", b(n0(d.alle_verk)), " verk har referanseliste.");
  };

  /* ---------- f16: kvar referansane går ---------- */
  F.fig.f16 = function (m, d, ctx) {
    const W = ctx.w, svg = F.svg(m, W, 80, "Kvar referansane går");
    const s = (W - 4) / d.sum;
    const segs = [["Til verk i laget", d.til_laget, "var(--fg)"], ["Til utanforverk i tabellen", d.til_utanfor, "var(--t3)"], ["Utanfor tabellen", d.utanfor_tabellen, "var(--hair)"]];
    let acc = 0;
    segs.forEach(([t, v, c], i) => { const wd = v * s; F.s("rect", { x: acc, y: 10, width: Math.max(1.5, wd - 1), height: 26, fill: c, stroke: i === 2 ? "var(--line)" : null, cls: "mk gx", tip: t + "|" + n0(v) + " av " + n0(d.sum) + " referansar (" + F.n(v / d.sum * 100, 1) + " %)" }, svg); acc += wd; });
    F.s("text", { x: 0, y: 52, text: "Til laget " + n0(d.til_laget), cls: "b" }, svg);
    F.s("text", { x: 0, y: 68, text: "Til utanforverk i tabellen " + n0(d.til_utanfor), style: "fill:var(--dim)" }, svg);
    F.s("text", { x: W, y: 52, "text-anchor": "end", text: "Utanfor tabellen " + n0(d.utanfor_tabellen) }, svg);
    F.s("line", { x1: 0, x2: 34, y1: 36, y2: 41, stroke: "var(--ref)" }, svg);
    F.d("h4", { text: "Del til laget, per periode (prosent)", style: "font:400 11.5px/1.35 var(--mono);color:var(--dim);margin:18px 0 6px" }, m);
    F.rows(m, ctx, { rows: d.periodar.map((p, i) => ({ label: p + " · " + n0(d.per_n[i]) + " ref.", v: d.per_del[i], color: "var(--fg)", tip: p + "|" + F.n(d.per_del[i], 1) + " % av " + n0(d.per_n[i]) + " referansar peikar til laget" })), max: 10, ticks: [0, 5, 10], tfmt: (v) => v + "", fmt: (v) => F.n(v, 1) + " %", rowH: 33, label: "Del til laget per periode" });
    F.d("h4", { text: "Referansar per mottakarverk: i laget mot utanfor", style: "font:400 11.5px/1.35 var(--mono);color:var(--dim);margin:18px 0 6px" }, m);
    F.rows(m, ctx, { rows: [
      { label: "Verk i laget", v: d.per_mottakar.laget, vtxt: F.n(d.per_mottakar.laget, 2), color: "var(--fg)", tip: "Referansar per mottakarverk|laget " + F.n(d.per_mottakar.laget, 2) + ", utanfor " + F.n(d.per_mottakar.utanfor, 2) + " (" + F.n(d.per_mottakar.forhald, 1) + " gonger)" },
      { label: "Verk utanfor laget", v: d.per_mottakar.utanfor, vtxt: F.n(d.per_mottakar.utanfor, 2), color: "var(--t3)", tip: "Referansar per mottakarverk utanfor|" + F.n(d.per_mottakar.utanfor, 2) }], max: 2, ticks: [0, 1, 2], tfmt: (v) => v + "", fmt: (v) => F.n(v, 2), mark: "bar", rowH: 32, label: "Referansar per mottakarverk" });
    F.d("h4", { text: "Kven peikar dei på, prosent", style: "font:400 11.5px/1.35 var(--mono);color:var(--dim);margin:18px 0 6px" }, m);
    F.rows(m, ctx, { rows: [
      { label: "Utanforverk refererte frå laget", v: d.utanfor_refererte.pct, vtxt: F.p(d.utanfor_refererte.pct, 1), color: "var(--t3)", tip: "Utanforverk refererte|" + n0(d.utanfor_refererte.n) + " av " + n0(d.utanfor_refererte.av) },
      { label: "Til same kjelde", v: d.same_kjelde_pct, vtxt: F.p(d.same_kjelde_pct, 1), color: "var(--fg)", tip: "Referansar til verk i same kjelde|" + F.n(d.same_kjelde_pct, 1) + " %" },
      { label: "Til verk med delt land", v: d.delt_land_pct, vtxt: F.p(d.delt_land_pct, 1), color: "var(--fg)", tip: "Referansar til verk med minst eitt felles land|" + F.n(d.delt_land_pct, 1) + " %" }], max: 100, ticks: [0, 50, 100], tfmt: (v) => v + "", mark: "bar", rowH: 32, label: "Kven referansane peikar på" });
  };

  /* ---------- f17: siteringssamfunn ---------- */
  F.fig.f17 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Kor samanhengande er koplingsnettverket", "NMI mellom samfunn og kjelde, språk, type, land og periode"]);
    const W = A.w, svg = F.svg(A, W, 96, "Koplingsnettverket");
    const s = (W - 2) / d.verk, rest = d.verk - d.storst - d.isolerte;
    [["I det store nettverket", d.storst, "var(--fg)"], ["Små komponentar", rest, "var(--t3)"], ["Isolerte", d.isolerte, { hatch: "var(--dim)" }]].forEach(([t, v, c], i) => { /* teikn i rekkjefølgje */ });
    let acc = 0;
    const hz = F.hatch(svg, "var(--dim)");
    [["I det store nettverket", d.storst, "var(--fg)"], ["Små komponentar", rest, "var(--t3)"], ["Isolerte", d.isolerte, hz]].forEach(([t, v, c]) => { const wd = v * s; F.s("rect", { x: acc, y: 8, width: Math.max(1, wd - 1), height: 24, fill: c, stroke: c === hz ? "var(--dim)" : null, cls: "mk gx", tip: t + "|" + n0(v) + " av " + n0(d.verk) + " verk" }, svg); acc += wd; });
    F.s("text", { x: 0, y: 50, text: "Det store nettverket " + n0(d.storst) + " (" + F.n(d.storst_pct, 1) + " %)", cls: "b" }, svg);
    F.s("text", { x: W, y: 68, "text-anchor": "end", text: "Isolerte " + n0(d.isolerte) }, svg);
    F.s("text", { x: 0, y: 86, text: n0(d.kantar) + " kantar" }, svg);
    F.d("h4", { text: "Kantar mellom verk med same første land (prosent)", style: "font:400 11.5px/1.35 var(--mono);color:var(--dim);margin:22px 0 6px" }, A);
    F.rows(A, { w: A.w }, { rows: [{ label: "Observert", v: d.same_land.observert, color: "var(--fg)" }, { label: "Venta ved tilfeldige par", v: d.same_land.venta, color: "var(--ref)" }], max: 50, ticks: [0, 25, 50], tfmt: (v) => v + "", fmt: (v) => F.n(v, 1) + " %", rowH: 36, mark: "bar", label: "Same første land, observert mot venta" });
    const nm = { kjelde: "Kjelde", språk: "Språk", type: "Type", land: "Land", periode: "Periode" };
    F.rows(B, { w: B.w }, { rows: d.nmi.map((q) => ({ label: nm[q.namn] || q.namn, lo: q.lo, hi: q.hi, mark: "range", vtxt: q.lo === q.hi ? F.n(q.lo, 2) : F.n(q.lo, 2) + "–" + F.n(q.hi, 2), color: q.namn === "kjelde" ? "var(--fg)" : "var(--t3)", tip: (nm[q.namn] || q.namn) + "|NMI " + F.n(q.lo, 2) + " til " + F.n(q.hi, 2) + " over ti køyringar" })), min: 0, max: 0.2, ticks: [0, 0.05, 0.1, 0.15, 0.2], tfmt: (v) => F.n(v, 2), fmt: (v) => F.n(v, 2), rowH: 38, label: "NMI mellom samfunn og variablar" });
    F.d("p", { cls: "sm" }, B).append("Spenn over ti køyringar. Samfunna er ustabile mellom køyringar, så dei er ikkje fasit.");
  };
})();
