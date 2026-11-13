/* FUNN - seksjon 5 til 9: tema, omgrep, kunnskapsformer, teorielement og dei femten spørsmåla (f19 til f26). */
(function () {
  "use strict";
  const F = window.FUNN, n0 = F.n;
  const b = (t) => Object.assign(document.createElement("b"), { textContent: t });
  const cap = (el, t, mt) => F.d("h4", { text: t, style: "font:400 11.5px/1.35 var(--mono);color:var(--dim);margin:" + (mt == null ? 0 : mt) + "px 0 6px" }, el);
  const pc = (v) => F.n(v, 1) + " %";

  /* ---------- f23: kunnskapsformer ---------- */
  F.fig.f23 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Del av 80 lesne tekstar som har forma (vekta), prosent med 95 % intervall", "Samsvar mellom markør og lesing: kappa"]);
    const cap1 = (q) => q.namn.replace(/^./, (c) => c.toUpperCase());
    const rows = d.former.map((q) => {
      const r = { label: cap1(q), v: q.lesing, lo: q.lo, hi: q.hi, mark: "dot", color: "var(--fg)", vtxt: F.n(q.lesing, 1) + (q.lesing === 0 ? " (til " + F.n(q.hi, 1) + ")" : ""), tip: q.namn + "|lesing " + F.n(q.lesing, 1) + " % (" + F.n(q.lo, 1) + " til " + F.n(q.hi, 1) + ")" };
      if (q.kode === "data_collection") { r.dots = [{ v: d.marker.datainnsamling.pct, color: "var(--fg)", hollow: true, r: 4.5 }, { v: d.justert_datainnsamling, color: "var(--dim)", tick: true }]; r.tip += "|markør, alle " + n0(d.marker.datainnsamling.k) + " av " + n0(d.marker.datainnsamling.n) + ": " + F.n(d.marker.datainnsamling.pct, 1) + " %|justert, om lag " + F.n(d.justert_datainnsamling, 1) + " %"; r.link = false; }
      return r;
    });
    F.rows(A, { w: A.w }, { rows, min: 0, max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 38, valW: 7.4, label: "Del av tekstane per kunnskapsform" });
    F.legend(A, [{ c: "var(--fg)", t: "lesing av 80, med intervall", r: true }, { c: "var(--fg)", t: "markør, alle " + n0(d.populasjon) + " (berre datainnsamling)", r: true, open: true }, { c: "var(--dim)", t: "markør justert (strek)" }]);
    const kr = d.former.map((q) => ({ label: cap1(q), v: q.kappa, lo: q.malbar ? d.kappa_data_ci[0] : null, hi: q.malbar ? d.kappa_data_ci[1] : null, mark: "dot", open: !q.malbar, dashci: false, color: q.malbar ? "var(--fg)" : (q.grense || q.ustabil ? "var(--fg)" : "var(--dim)"), vtxt: F.n(q.kappa, 2) + (q.malbar ? " målbar" : (q.ustabil ? " ustabil" : (q.grense ? " grense" : ""))), vcls: q.malbar ? "b" : "", tip: q.namn + "|kappa " + F.n(q.kappa, 2) + (q.malbar ? " (" + F.n(d.kappa_data_ci[0], 2) + " til " + F.n(d.kappa_data_ci[1], 2) + ")|presisjon " + F.n(d.presisjon, 2) + ", gjenfinning " + F.n(d.gjenfinning, 2) : (q.ustabil ? "|berre 3 positive i lesinga, så kappa er ustabil" : (q.grense ? "|grensetilfelle" : ""))) }));
    F.rows(B, { w: B.w }, { rows: kr, min: -0.2, max: 1, ticks: [0, 0.25, 0.5, 0.75, 1], tfmt: (v) => F.n(v, 2), fmt: (v) => F.n(v, 2), rowH: 38, valW: 7.4, label: "Kappa per form" });
    F.legend(B, [{ c: "var(--fg)", t: "fylt: målbar, med 95 % intervall", r: true }, { c: "var(--fg)", t: "ring: ikkje målbar eller ustabil (modellering: 3 positive)", r: true, open: true }]);
    F.d("p", { cls: "sm" }, B).append("Berre datainnsamling er målbar: kappa ", b("0,75"), " (0,52–0,95), presisjon ", b("0,83"), ", gjenfinning ", b("0,95"), ". Argument er eit grensetilfelle.");
    /* matrise */
    const sec = F.d("div", { style: "margin-top:34px;max-width:680px" }, m);
    cap(sec, "Kva former står saman: phi mellom former, " + d.per_tekst.n + " lesne tekstar (uvekta tal på tekstar)");
    const codes = d.kodar.filter((k) => d.phi.some((p) => p.a === k || p.b === k));
    const lab = { argument: "argument", literature: "litteratur", example: "eksempel", case: "case", data_collection: "datainnsamling", design_work: "designarbeid", practice_reflection: "praksisrefleksjon", use_in_practice: "bruk i praksis" };
    const W = Math.min(ctx.w, 680), labW = Math.max.apply(null, codes.map((k) => (lab[k] || k).length)) * 7.4 + 12, cs = Math.min(50, (W - labW - 8) / codes.length), H = cs * codes.length + 8;
    const svg = F.svg(sec, W, H, "Samførekomst mellom kunnskapsformer");
    const idx = {}; codes.forEach((k, i) => (idx[k] = i));
    codes.forEach((k, i) => {
      F.s("text", { x: labW - 8, y: i * cs + cs / 2 + 4, "text-anchor": "end", text: lab[k] || k, cls: "fg" }, svg);
      F.s("line", { x1: labW, x2: labW + (i + 1) * cs, y1: i * cs + cs, y2: i * cs + cs, stroke: "var(--hair)" }, svg);
      F.s("line", { x1: labW + i * cs + cs, x2: labW + i * cs + cs, y1: i * cs, y2: H - 8, stroke: "var(--hair)" }, svg);
    });
    d.phi.forEach((p) => {
      let i = idx[p.a], j = idx[p.b]; if (i < j) { const t = i; i = j; j = t; }
      const cxp = labW + j * cs + cs / 2, cyp = i * cs + cs / 2, r = Math.max(2, Math.sqrt(Math.abs(p.phi)) * cs * 0.46), small = p.n < 5;
      const g = F.s("g", { cls: "mk fd", tip: (lab[p.a] || p.a) + " og " + (lab[p.b] || p.b) + "|phi " + F.n(p.phi, 2) + "|" + p.n + " tekstar har begge" + (small ? "|lite tal, usikkert" : "") }, svg);
      F.s("rect", { x: cxp - cs / 2, y: cyp - cs / 2, width: cs, height: cs, fill: "transparent" }, g);
      F.s("circle", { cx: cxp, cy: cyp, r, fill: p.phi >= 0 ? "var(--fg)" : "var(--bg)", stroke: "var(--fg)", "stroke-width": p.phi >= 0 ? 0 : 1.6, "stroke-dasharray": small ? "2.5 2" : null, opacity: p.phi >= 0 ? 0.25 + Math.abs(p.phi) * 1.4 : 1 }, g);
      if (small) F.s("circle", { cx: cxp, cy: cyp, r: Math.max(r, 3) + 2.5, fill: "none", stroke: "var(--dim)", "stroke-width": 1, "stroke-dasharray": "2 2" }, g);
    });
    /* tala står under diagonalen: strek med verdi for dei sterkaste */
    d.phi.filter((p) => Math.abs(p.phi) >= 0.33).forEach((p) => {
      let i = idx[p.a], j = idx[p.b]; if (i < j) { const t = i; i = j; j = t; }
      F.s("text", { x: labW + j * cs + cs - 2, y: i * cs + cs - 3, "text-anchor": "end", text: F.n(p.phi, 2).replace("−0,", "−.").replace(/^0,/, "."), cls: "sm halo b", "pointer-events": "none" }, svg);
    });
    F.legend(sec, [{ c: "var(--fg)", t: "saman oftare enn tilfeldig", r: true }, { c: "var(--fg)", t: "saman sjeldnare", r: true, open: true }, { c: "var(--dim)", t: "stipla ring: færre enn 5 tekstar har begge", r: true, open: true }]);
    F.d("p", { cls: "sm" }, sec).append(b(d.per_tekst.tre_pluss + " av " + d.per_tekst.n), " tekstar har tre eller fleire former, snitt ", b(F.n(d.per_tekst.snitt, 2)), ". Éin kodar, ukontrollert.");
  };

  /* ---------- f24: datainnsamlingsmarkørar ---------- */
  F.fig.f24 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Over tid og før mot etter 2015", "Etter kjelde, land og endring innan kjelde"]);
    const dot = (q, group, extra) => Object.assign({ label: q.namn + " · n " + n0(q.n), v: q.pct, lo: q.lo, hi: q.hi, mark: "dot", color: "var(--fg)", vtxt: F.n(q.pct, 1), group, tip: q.namn + "|" + n0(q.k) + " av " + n0(q.n) + " tekstar (" + F.n(q.pct, 1) + " %)" + (q.lo != null ? "|95 % intervall " + F.n(q.lo, 1) + " til " + F.n(q.hi, 1) : "") }, extra || {});
    const rowsA = d.periode.map((q, i) => dot(q, i === 0 ? "Periode" : null)).concat(d.for_etter.map((q, i) => dot(q, i === 0 ? "Før og etter 2015" : null, { color: "var(--t3)" })));
    F.rows(A, { w: A.w }, { rows: rowsA, min: 0, max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 36, gH: 26, valW: 7, label: "Datainnsamlingsmarkørar over tid" });
    const rowsB = d.kjelde.map((q, i) => dot(Object.assign({}, q, { namn: q.namn.replace("Nordic design research conference", "Nordes").replace("Proceedings of ", "").replace("Participatory Design Conference", "PDC").replace("Designing Interactive Systems", "DIS") }), i === 0 ? "Kjelde, minst 40 tekstar" : null))
      .concat(d.land.map((q, i) => dot(q, i === 0 ? "Land, verk med eitt land" : null, { color: F.cc({ Danmark: "DK", Finland: "FI", Noreg: "NO", Sverige: "SE" }[q.namn]) })))
      .concat(d.innan_kjelde.map((q, i) => ({ label: q.namn.replace("Nordic design research conference", "Nordes"), vtxt: F.n(q.for, 1) + " → " + F.n(q.etter, 1), mark: "none", dots: [{ v: q.for, color: "var(--fg)", hollow: true }, { v: q.etter, color: "var(--fg)" }], linkc: "var(--ref)", group: i === 0 ? "Endring innan kjelde, før til etter 2015" : null, tip: q.namn + "|før 2015: " + F.n(q.for, 1) + " %|frå 2015: " + F.n(q.etter, 1) + " %" })));
    F.rows(B, { w: B.w }, { rows: rowsB, min: 0, max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 34, gH: 26, valW: 7, label: "Datainnsamlingsmarkørar etter kjelde og land" });
    F.d("p", { cls: "sm" }, B).append("Markør for datainnsamling er ikkje kvalitet: å ha samla inn data er ikkje det same som at ein påstand er støtta av dei.");
  };

  /* ---------- f25: teorielement i pilotane ---------- */
  F.fig.f25 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Profil: del av påstandane, prosent (95 % intervall)", "Pålitelegheit: andre lesing av same tekstar"]);
    const iv = (label, a, group, extra) => Object.assign({ label, v: a[0], lo: a[1], hi: a[2], mark: "dot", color: "var(--fg)", vtxt: F.n(a[0], 0), group, tip: label + "|" + F.n(a[0], 0) + " % (" + F.n(a[1], 0) + " til " + F.n(a[2], 0) + ")" }, extra || {});
    const k = d.kausal, rowsA = [
      iv("Pilot v0.1, " + k.v01[3] + " påstandar", k.v01.slice(0, 3), "Påstanden er «causes or enables»"),
      iv("Pilot v0.3, " + k.v03[3] + " påstandar", k.v03.slice(0, 3), null, { color: "var(--fg)" }),
      { label: "Andre lesing, v0.3", v: k.les2, mark: "dot", open: true, vtxt: F.n(k.les2, 0), color: "var(--dim)", tip: "Andre lesing|" + k.les2 + " %|skilnad " + F.n(k.diff[0], 1) + " poeng (" + k.diff[1] + " til +" + k.diff[2] + ")" },
      iv("I konklusjonen", d.stad.konklusjon, "Kvar påstanden står"),
      { label: "I samandraget", v: d.stad.samandrag, mark: "dot", vtxt: F.n(d.stad.samandrag, 0), color: "var(--fg)" },
      { label: "I innleiinga", v: d.stad.innleiing, mark: "dot", vtxt: F.n(d.stad.innleiing, 0), color: "var(--fg)" },
      iv("Tekstens eigne påstandar, v0.3", d.eigne.v03, "Kjelde og støtte"),
      { label: "Tekstens eigne, v0.1", v: d.eigne.v01, mark: "dot", vtxt: F.n(d.eigne.v01, 0), color: "var(--fg)" },
      iv("Støtte oppgjeve", d.stotte.oppgjeve, null),
      iv("Støtte ikkje oppgjeve", d.stotte.ikkje, null),
      { label: "Omgrep definerte, " + d.omgrep.definerte + " av " + d.omgrep.unike, v: d.omgrep.definerte / d.omgrep.unike * 100, mark: "dot", vtxt: F.n(d.omgrep.definerte / d.omgrep.unike * 100, 1), color: "var(--fg)", group: "Omgrep" },
    ].concat(d.to_omgrep.map((q, i) => ({ label: "To omgrep per påstand, " + q.namn, v: q.pct, mark: "dot", vtxt: F.n(q.pct, 1), color: "var(--fg)", tip: q.namn + "|" + q.k + " av " + q.n + " påstandar" })));
    F.rows(A, { w: A.w }, { rows: rowsA, min: 0, max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 34, gH: 26, valW: 7, label: "Profil for teorielement" });
    const a = d.att, g = d.gjenfinning;
    const bar = (label, k2, n, group, extra) => Object.assign({ label, v: k2 / n * 100, mark: "bar", vtxt: k2 + " av " + n, color: "var(--fg)", group, tip: label + "|" + k2 + " av " + n }, extra || {});
    const rowsB = [bar("Påstandar funne att", a.funne[0], a.funne[1], "Same påstand i lesing 2"), bar("Same samanhengstype", a.type_lik[0], a.type_lik[1], null, { color: "var(--t3)" }), bar("Same støttestatus", a.stotte_lik[0], a.stotte_lik[1], null, { color: "var(--t3)" })]
      .concat(g.map((q, i) => bar("Gjenfinning, " + q.namn, q.k, q.n, i === 0 ? "Gjenfinning etter stad" : null)));
    F.rows(B, { w: B.w }, { rows: rowsB, min: 0, max: 100, ticks: [0, 50, 100], tfmt: (v) => v + "", rowH: 34, gH: 26, label: "Pålitelegheit" });
    F.d("p", { cls: "sm" }, B).append("Kappa for samanhengstype ", b(F.n(a.kappa, 2)), ". Skilnaden i «causes or enables» mellom lesingane er ", b(F.n(k.diff[0], 1) + " poeng"), " (", k.diff[1], " til +", k.diff[2], ").");
    F.d("p", { cls: "sm" }, A).append("v0.1 (", b("31 %"), " av 315) og v0.3 (", b("56 %"), " av 52) kan ikkje samanliknast: skilnaden følgjer både plukkemåte og tekstutval, og dei to kan ikkje skiljast med desse data.");
  };

  /* ---------- f26: femten spørsmål ---------- */
  F.fig.f26 = function (m, d, ctx) {
    const W = ctx.w, mob = W < 760;
    const oname = d.namn;
    /* inngangsbilete: femten flater */
    const ov = F.d("div", { style: "margin:0 0 6px" }, m);
    const lin = ["Eininga", "Skilja", "Tida"];
    const cw = mob ? Math.floor((W - 2) / 5) : 74, rh = 64, left = mob ? 0 : 84;
    const svg0 = F.svg(ov, mob ? W : Math.min(W, left + cw * 5 + 8), 3 * (rh + 14), "Oversyn over femten spørsmål");
    lin.forEach((l, li) => {
      F.s("text", { x: 0, y: li * (rh + 14) + (mob ? 8 : rh / 2 + 4), text: l, cls: "b" }, svg0);
      d.sporsmal.filter((q) => q.linse === l).forEach((q, i) => {
        const x0 = left + i * cw, y0 = li * (rh + 14) + (mob ? 14 : 0);
        const a = F.s("a", { href: "#sp-" + q.id }, svg0);
        const g = F.s("g", { cls: "mk", tip: q.tittel + "|" + oname[q.utfall] }, a);
        const hh = mob ? rh - 16 : rh;
        F.s("rect", { x: x0 + 2, y: y0, width: cw - 6, height: hh, rx: 5, fill: q.utfall === "held" ? "var(--fg)" : "transparent", stroke: "var(--fg)", "stroke-width": q.utfall === "held" ? 0 : 1.4, "stroke-dasharray": q.utfall === "undecided" ? "3 3" : null }, g);
        const nr = q.rader.length, step = (cw - 14) / Math.max(nr, 1);
        q.rader.forEach((r, k) => {
          const cxp = x0 + 8 + step * k + step / 2 - 1, cyp = y0 + hh / 2 - 5, ink = q.utfall === "held" ? "var(--bg)" : "var(--fg)";
          F.s("circle", { cx: cxp, cy: cyp, r: 3.4, fill: r.dom === "treff" ? ink : "none", stroke: ink, "stroke-width": 1.4, "stroke-dasharray": r.dom === "open" ? "2 1.6" : null }, g);
        });
        F.s("text", { x: x0 + cw / 2 - 1, y: y0 + hh - 10, "text-anchor": "middle", text: q.id.split("-")[1], style: "fill:" + (q.utfall === "held" ? "var(--bg)" : "var(--fg)") }, g);
      });
    });
    const legd = F.d("div", { cls: "leg", style: "margin-top:12px" }, ov);
    [["var(--fg)", "heldt", false], ["var(--fg)", "heldt ikkje", true], ["var(--dim)", "uavgjort", true]].forEach(([c, t, o], i) => { const s = F.d("span", null, legd); const ii = F.d("i", { cls: o ? "o" : "" }, s); ii.style.background = c; ii.style.color = c; if (i === 2) ii.style.borderStyle = "dashed"; s.appendChild(document.createTextNode(t)); });
    F.d("p", { cls: "sm", text: "Prikkane er stripene: fylt er treff, open er bom, stipla er ikkje avgjort. I korta er skygga felt det forventa området og svart merke det observerte." }, ov);
    lin.forEach((l) => {
      F.d("div", { cls: "sp-linse", text: l }, m);
      const grid = F.d("div", { cls: "sp-grid" }, m);
      d.sporsmal.filter((q) => q.linse === l).forEach((q) => card(grid, q));
    });
    function card(grid, q) {
      const el = F.d("section", { cls: "sp", id: "sp-" + q.id }, grid);
      const h = F.d("h4", null, el);
      F.d("span", { text: q.tittel }, h);
      F.d("em", { text: oname[q.utfall], cls: q.utfall }, h);
      F.d("p", { cls: "sp-merk", text: q.nemnar }, el);
      const w = Math.floor(el.getBoundingClientRect().width) || (mob ? W : W / 2 - 24);
      const heights = [], lines = [];
      const cpl = Math.floor((w - 40) / 7.1);
      const notes = [], legs = [];
      q.rader.forEach((r) => { const t = r.namn; const l1 = t.length <= cpl ? [t] : wrap(t, cpl); lines.push(l1); const nt = ((r.avleidd ? "Utleidd tal. " : "") + (r.merknad || "")).trim(); const nl = nt ? F.wrap(nt, Math.floor((w - 4) / 7.0), 3) : []; notes.push(nl); const lgt = r.obs.length > 1 ? F.wrap(r.obs.map((o, k) => ["●", "◆", "■", "▲", "✚"][k % 5] + " " + (o.namn || "") + " " + F.n(o.v, Math.abs(o.v) < 1 && o.v % 0.1 ? 2 : (o.v % 1 ? 1 : 0))).join("   "), Math.floor((w - 4) / 7.0), 2) : []; legs.push(lgt); heights.push(l1.length * 14 + 64 + (lgt.length ? lgt.length * 14 + 4 : 0) + (nl.length ? nl.length * 14 + 10 : 0)); });
      const H = heights.reduce((a, c) => a + c, 0) + 4;
      const svg = F.svg(el, w, H, q.tittel);
      let y = 2;
      q.rader.forEach((r, ri) => {
        const L = lines[ri], domC = "var(--fg)";
        const g = F.s("g", { cls: "mk" }, svg);
        const unit = r.eining === "prosent" ? " %" : (r.eining === "del" || r.eining === "forhold" || r.eining === "indeks" || r.eining === "poeng" || r.eining === "rho" || r.eining === "AUC" || r.eining === "tal" || r.eining === "gonger" ? "" : " " + r.eining);
        L.forEach((t, k) => F.s("text", { x: 0, y: y + 11 + k * 14, text: t, cls: "fg", style: "font-size:12px" }, g));
        /* dom */
        const dx = w - 4, dy = y + 7;
        const gl = F.s("g", { tip: (r.dom === "treff" ? "Treff" : (r.dom === "bom" ? "Bom" : "Ikkje avgjort")) + "|" + vtxt(r) }, svg);
        F.s("circle", { cx: dx - 6, cy: dy, r: 6, fill: r.dom === "treff" ? "var(--fg)" : "transparent", stroke: "var(--fg)", "stroke-width": 1.5, "stroke-dasharray": r.dom === "open" ? "2.5 2" : null }, gl);
        /* akse */
        const ty = y + L.length * 14 + 31, px0 = 6, px1 = w - 6;
        const x = d3.scaleLinear().domain(r.akse).range([px0, px1]);
        F.s("line", { x1: px0, x2: px1, y1: ty, y2: ty, stroke: "var(--line)" }, svg);
        const vn = r.venta;
        const lo = vn.lo == null ? r.akse[0] : vn.lo, hi = vn.hi == null ? r.akse[1] : vn.hi;
        if (vn.tilnaerma && vn.lo === vn.hi) {
          F.s("line", { x1: x(vn.lo), x2: x(vn.lo), y1: ty - 11, y2: ty + 11, stroke: "var(--ref)", "stroke-width": 3 }, svg);
          F.s("text", { x: x(vn.lo) + 6, y: ty + 20, text: "om lag", cls: "sm" }, svg);
        } else {
          const gid = "gd" + q.id + ri;
          const defs = svg.querySelector("defs") || svg.insertBefore(F.s("defs"), svg.firstChild);
          if (vn.lo == null || vn.hi == null) {
            const lg = F.s("linearGradient", { id: gid, x1: vn.lo == null ? 1 : 0, x2: vn.lo == null ? 0 : 1, y1: 0, y2: 0 }, defs);
            F.s("stop", { offset: "0", "stop-color": "var(--ref)", "stop-opacity": 0.42 }, lg);
            F.s("stop", { offset: "1", "stop-color": "var(--ref)", "stop-opacity": 0.04 }, lg);
          }
          F.s("rect", { x: x(lo), y: ty - 12, width: Math.max(2, x(hi) - x(lo)), height: 24, rx: 2, fill: (vn.lo == null || vn.hi == null) ? "url(#" + gid + ")" : "var(--ref)", opacity: (vn.lo == null || vn.hi == null) ? 1 : 0.32, cls: "fd" }, svg);
          if (vn.lo != null) F.s("line", { x1: x(lo), x2: x(lo), y1: ty - 12, y2: ty + 12, stroke: "var(--ref)", "stroke-width": 1.4 }, svg);
          if (vn.hi != null) F.s("line", { x1: x(hi), x2: x(hi), y1: ty - 12, y2: ty + 12, stroke: "var(--ref)", "stroke-width": 1.4 }, svg);
        }
        /* observert */
        const shapes = ["circle", "diamond", "square", "tri", "cross"];
        let lastLx = null;
        r.obs.slice().sort((a, c) => a.v - c.v).forEach((o) => {
          const k = r.obs.indexOf(o);
          const xo = x(Math.max(r.akse[0], Math.min(r.akse[1], o.v)));
          if (o.lo != null && o.hi != null && !(o.lo === o.hi)) {
            F.s("line", { x1: x(Math.max(r.akse[0], o.lo)), x2: x(Math.min(r.akse[1], o.hi)), y1: ty, y2: ty, stroke: "var(--fg)", "stroke-width": 2.2 }, svg);
            F.s("line", { x1: x(Math.max(r.akse[0], o.lo)), x2: x(Math.max(r.akse[0], o.lo)), y1: ty - 5, y2: ty + 5, stroke: "var(--fg)", "stroke-width": 1.4 }, svg);
            F.s("line", { x1: x(Math.min(r.akse[1], o.hi)), x2: x(Math.min(r.akse[1], o.hi)), y1: ty - 5, y2: ty + 5, stroke: "var(--fg)", "stroke-width": 1.4 }, svg);
          }
          marker(svg, shapes[k % 5], xo, ty, o.mid ? true : false);
          const txt = F.n(o.v, Math.abs(o.v) < 1 && o.v % 0.1 ? 2 : (o.v % 1 ? 1 : 0));
          const lx = Math.max(14, Math.min(w - 14, xo));
          const close = lastLx != null && Math.abs(lx - lastLx) < 34;
          F.s("text", { x: lx, y: ty - 17 - (close ? 13 : 0), "text-anchor": "middle", text: txt, cls: "b halo" }, svg);
          lastLx = close ? null : lx;
        });
        /* akseendar */
        const fmtA = (v) => F.n(v, v % 1 ? 1 : 0);
        F.s("text", { x: px0, y: ty + 24, text: fmtA(r.akse[0]), cls: "sm" }, svg);
        F.s("text", { x: px1, y: ty + 24, "text-anchor": "end", text: fmtA(r.akse[1]) + unit, cls: "sm" }, svg);
        legs[ri].forEach((t, k) => F.s("text", { x: 0, y: ty + 40 + k * 14, text: t, cls: "sm fg" }, svg));
        /* skyggeforklaring i tips */
        const tip = r.namn + "|forventa " + vtxtV(vn, unit) + "|observert " + r.obs.map((o) => (o.namn ? o.namn + " " : "") + F.n(o.v, 2) + (o.lo != null && o.lo !== o.hi ? " (" + F.n(o.lo, 2) + " til " + F.n(o.hi, 2) + ")" : "") + unit).join(", ") + (r.merknad ? "|" + r.merknad : "") + (r.avleidd ? "|Utleidd tal" : "");
        g.setAttribute("data-tip", tip);
        F.s("rect", { x: 0, y: y, width: w, height: heights[ri], fill: "transparent" }, g);
        notes[ri].forEach((t, k) => F.s("text", { x: 0, y: ty + 40 + (legs[ri].length ? legs[ri].length * 14 + 4 : 0) + k * 14, text: t, cls: "sm" }, svg));
        y += heights[ri];
        F.s("line", { x1: 0, x2: w, y1: y - 6, y2: y - 6, stroke: "var(--hair)" }, svg);
        if (r.merknad) { /* merknad kjem i verktøyhint */ }
      });
    }
    function wrap(t, n) {
      const words = t.split(" "); const out = []; let cur = "";
      words.forEach((w) => { if ((cur + " " + w).trim().length > n) { out.push(cur); cur = w; } else cur = (cur + " " + w).trim(); });
      out.push(cur);
      if (out.length > 2) { out.length = 2; out[1] = F.trunc(out[1] + "…", n); }
      return out;
    }
    function vtxtV(v, unit) { if (v.lo == null) return "høgst " + F.n(v.hi, 2) + unit; if (v.hi == null) return "minst " + F.n(v.lo, 2) + unit; if (v.lo === v.hi) return "om lag " + F.n(v.lo, 2) + unit; return F.n(v.lo, 2) + " til " + F.n(v.hi, 2) + unit; }
    function vtxt(r) { return "forventa " + vtxtV(r.venta, "") + ", observert " + r.obs.map((o) => F.n(o.v, 2)).join(" og "); }
    function marker(svg, s, x, y, hollow) {
      const f = hollow ? "var(--bg)" : "var(--fg)", o = { fill: f, stroke: "var(--fg)", "stroke-width": 2 };
      if (s === "circle") F.s("circle", Object.assign({ cx: x, cy: y, r: 5.5 }, o), svg);
      else if (s === "diamond") F.s("path", Object.assign({ d: "M" + x + "," + (y - 7) + " L" + (x + 7) + "," + y + " L" + x + "," + (y + 7) + " L" + (x - 7) + "," + y + " Z" }, o), svg);
      else if (s === "square") F.s("rect", Object.assign({ x: x - 5, y: y - 5, width: 10, height: 10 }, o), svg);
      else if (s === "tri") F.s("path", Object.assign({ d: "M" + x + "," + (y - 7) + " L" + (x + 7) + "," + (y + 5) + " L" + (x - 7) + "," + (y + 5) + " Z" }, o), svg);
      else F.s("path", { d: "M" + (x - 6) + "," + y + " H" + (x + 6) + " M" + x + "," + (y - 6) + " V" + (y + 6), stroke: "var(--fg)", "stroke-width": 3 }, svg);
    }
  };
})();
