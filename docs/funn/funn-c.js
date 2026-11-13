/* FUNN - seksjon 5 til 9: tema, omgrep, kunnskapsformer, teorielement og dei femten spørsmåla (f19 til f26). */
(function () {
  "use strict";
  const F = window.FUNN, n0 = F.n;
  const b = (t) => Object.assign(document.createElement("b"), { textContent: t });
  const cap = (el, t, mt) => F.d("h4", { text: t, style: "font:400 11.5px/1.35 var(--mono);color:var(--dim);margin:" + (mt == null ? 0 : mt) + "px 0 6px" }, el);
  const pc = (v) => F.n(v, 1) + " %";

  /* ---------- f19: svak struktur ---------- */
  F.fig.f19 = function (m, d, ctx) {
    const [L, R] = F.pans(m, 2, "p2", ["", ""]);

    cap(L, "Silhuett: observert mot tilfeldig datasky");
    F.rows(L, { w: L.w }, { rows: [{ label: "Observert, ti klynger", v: d.silhuett.observert, color: "var(--fg)" }, { label: "Tilfeldig datasky", v: d.silhuett.tilfeldig, color: "var(--ref)" }], max: 0.1, ticks: [0, 0.05, 0.1], tfmt: (v) => F.n(v, 2), fmt: (v) => F.n(v, 4), mark: "bar", rowH: 36, label: "Silhuett" });
    F.d("p", { cls: "sm" }, L).append(b(F.p(d.midt_mellom, 1)), " av verka ligg nesten midt mellom to klyngesenter.");
    cap(L, "Justert R², prosent av variasjonen i tekstvektorane", 22);
    const nm = (s) => s.replace("kanal (12)", "kanal (12 kanalar)").replace(/^./, (c) => c.toUpperCase());
    F.rows(L, { w: L.w }, { rows: d.r2.map((q, i) => Object.assign({ label: nm(q.namn), v: q.pct, color: i === 0 ? "var(--fg)" : "var(--t3)", group: i === 0 ? "Alle med fulltekst" : null })).concat(d.r2_same.map((q, i) => ({ label: nm(q.namn), v: q.pct, color: "var(--t3)", group: i === 0 ? "Same 1 435 verk" : null }))), max: 16, ticks: [0, 4, 8, 12, 16], tfmt: (v) => v + "", fmt: (v) => F.n(v, 2) + " %", mark: "bar", rowH: 32, gH: 26, label: "Justert R2" });
    F.d("p", { cls: "sm" }, L).append("Kanal er ikkje årsak.");
    cap(R, "Klynge 8 er språk: del med nordisk språk, prosent");
    F.rows(R, { w: R.w }, { rows: [{ label: "I klynge 8, " + d.klynge8.n + " verk", v: d.klynge8.nordisk, color: "var(--fg)" }, { label: "Alle verk med fulltekst", v: d.klynge8.alle, color: "var(--ref)" }], max: 100, ticks: [0, 50, 100], tfmt: (v) => v + "", fmt: pc, mark: "bar", rowH: 36, label: "Nordisk språk" });
    cap(R, "Kva fulltekstutvalet dekkjer: del av verka med fulltekst, prosent", 24);
    const e = (t, v, g) => ({ label: t, v, color: "var(--fg)", group: g });
    F.rows(R, { w: R.w }, { rows: d.utval_periode.map((q, i) => e(q[0], q[1], i === 0 ? "Periode" : null)).concat(d.utval_sprak.map((q, i) => e(q[0].replace(/^./, (c) => c.toUpperCase()) + "språklege", q[1], i === 0 ? "Språk" : null)), d.utval_type.map((q, i) => e(q[0].replace(/^./, (c) => c.toUpperCase()), q[1], i === 0 ? "Slag" : null))), max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", fmt: pc, rowH: 32, gH: 26, label: "Kva fulltekstutvalet dekkjer" });
  };

  /* ---------- f20: emne og klynger ---------- */
  F.fig.f20 = function (m, d, ctx) {
    const [L, R] = F.pans(m, 2, "p2", ["", ""]);

    cap(L, "OpenAlex-emne, dei åtte største, del av " + n0(d.emne_n) + " verk med emne");
    F.rows(L, { w: L.w }, { rows: d.topp.map((q) => ({ label: q.namn, v: q.pct, vtxt: pc(q.pct), color: "var(--fg)", tip: q.namn + "|" + n0(q.n) + " verk (" + pc(q.pct) + ")" })), max: 40, ticks: [0, 10, 20, 30, 40], tfmt: (v) => v + "", fmt: pc, mark: "bar", rowH: 34, label: "Dei åtte største emna" });
    F.d("p", { cls: "sm" }, L).append(b(n0(d.ulike_emne)), " ulike emne. Dei fem største har ", b(pc(d.topp5_pct)), ". ", b(n0(d.mekanisk[0])), " av dei ", n0(d.mekanisk[1]), " i det største emnet ligg under Mechanical Engineering, og domenet Physical Sciences har ", b(pc(d.domene.fysiske[1])), " (", n0(d.domene.fysiske[0]), " verk).");
    cap(L, "Del per femårsperiode, emne med minst 30 verk (mørke: del som endrar seg)", 26);
    F.spark(L, { w: L.w }, { rows: d.emne.map((q) => ({ label: q.namn, vals: q.del, flag: !!q.endrar, tip: q.namn + "|" + d.periodar.map((p, i) => p + ": " + F.n(q.del[i], 1) + " %").join("|") })), kind: "bars", perRow: true, periods: d.periodar, max: 50, rowH: 27, labelW: 200, vw: 84, label: "Emne over tid" });
    F.d("p", { cls: "sm" }, L).append("Eit utval på 300 verk har ", b(F.n(d.rikdom_300[0], 1)), " ulike emne i 2005–09 og ", b(F.n(d.rikdom_300[3], 1)), " i 2020–24.");
    cap(R, "Klyngeandelar i fulltekstutvalet, 2005–09 til 2020–24, prosent av verka");
    const order = ["veks", "fell", "ingen"], gname = { veks: "Veks", fell: "Fell", ingen: "Ingen lineær trend" };
    const rows = [];
    order.forEach((g) => d.klynger.filter((k) => k.retning === g).forEach((k, i) => rows.push({ label: k.namn.replace(/^./, (c) => c.toUpperCase()), vals: k.del, flag: g === "veks", dash: g === "fell", group: i === 0 ? gname[g] : null, tip: k.namn + "|" + d.klyngeperiodar.map((p, j) => p + ": " + F.n(k.del[j], 1) + " %").join("|") + "|" + n0(k.n) + " verk i klynga" })));
    F.spark(R, { w: R.w }, { rows, kind: "line", periods: d.klyngeperiodar, max: 27, rowH: 34, labelW: 190, vw: 92, label: "Klyngeandelar over tid" });
    F.d("p", { cls: "sm" }, R).append("Klyngenamna er våre, ikkje fagfolk sine. Heiltrukke linje veks, stipla fell.");
  };

  /* ---------- f21: breidde og ankerdel ---------- */
  F.fig.f21 = function (m, d, ctx) {
    const W = ctx.w, mob = W < 520, h = mob ? 330 : 390, pl = 34, pr = 14, pt = 22, pb = 34;
    const svg = F.svg(m, W, h, "Breidde og ankerdel for omgrep");
    const x = d3.scaleLinear().domain([0, 80]).range([pl, W - pr]), y = d3.scaleLinear().domain([0, 60]).range([h - pb, pt]);
    F.axisX(svg, x, h - pb, h - pb - pt, { values: [0, 20, 40, 60, 80], fmt: (v) => v + "" });
    F.axisY(svg, y, pl, W - pl - pr, { values: [0, 20, 40, 60], fmt: (v) => v + "" });
    F.s("text", { x: pl + (W - pl - pr) / 2, y: h - 2, "text-anchor": "middle", text: "breidde: % av engelske fulltekstar 2020–25", cls: "sm" }, svg);
    F.s("text", { x: 0, y: 6, text: "anker: % av brukartekstane som siterer same anker", cls: "sm" }, svg);
    F.s("text", { x: W - pr - 4, y: pt + 14, "text-anchor": "end", text: "ankerdelen er eit golv", cls: "sm" }, svg);
    const place = { "design process": ["end", 0, 20], "design research": ["start", 9, 4], "wicked problem": ["start", 9, -7], "speculative design": ["start", 0, 17] };
    d.begge.forEach((q) => {
      const pos = place[q.namn] || ["start", 9, 4];
      const range = q.x_lo != null;
      const g = F.s("g", { cls: "mk fd", tip: q.namn + "|breidde " + (range ? "3 til 10 %" : F.n(q.x, 1) + " %") + "|ankerdel " + F.n(q.y, 1) + " %" + (d.anker_tittel[q.namn] ? "|" + d.anker_tittel[q.namn] : "") }, svg);
      if (range) {
        F.s("line", { x1: x(q.x_lo), x2: x(q.x_hi), y1: y(q.y), y2: y(q.y), stroke: "var(--fg)", "stroke-width": 3 }, g);
        F.s("line", { x1: x(q.x_lo), x2: x(q.x_lo), y1: y(q.y) - 5, y2: y(q.y) + 5, stroke: "var(--fg)", "stroke-width": 1.5 }, g);
        F.s("line", { x1: x(q.x_hi), x2: x(q.x_hi), y1: y(q.y) - 5, y2: y(q.y) + 5, stroke: "var(--fg)", "stroke-width": 1.5 }, g);
        F.s("text", { x: x(q.x_lo), y: y(q.y) + pos[2], text: q.namn, cls: "b halo" }, g);
      } else {
        F.s("circle", { cx: x(q.x), cy: y(q.y), r: 6, fill: "var(--fg)" }, g);
        F.s("text", { x: x(q.x) + (pos[0] === "end" ? 4 : 9), y: y(q.y) + pos[2], "text-anchor": pos[0], text: q.namn, cls: "b halo" }, g);
      }
    });
    F.s("text", { x: x(10) + 8, y: y(44.9) + 4, text: "3–10 %", cls: "sm" }, svg);
    const wrap = F.d("div", { cls: "pans p2", style: "margin-top:20px" }, m);
    const a = F.d("div", { cls: "pan" }, wrap), c = F.d("div", { cls: "pan" }, wrap);
    cap(a, "Berre breidde kontrollert, prosent");
    const sp = (q) => (q.x_lo != null ? { lo: q.x_lo, hi: q.x_hi, mark: "range", vtxt: "3–10", tip: q.namn + "|breidde 3 til 10 %" } : { v: q.x, mark: "dot", vtxt: F.n(q.x, 1), tip: q.namn + "|breidde " + F.n(q.x, 1) + " %" });
    const aw = Math.floor(a.getBoundingClientRect().width);
    F.rows(a, { w: aw }, { rows: d.berre_breidde.map((q) => Object.assign({ label: q.namn, color: "var(--fg)", r: 4.5 }, sp(q))), min: 0, max: 80, ticks: [0, 20, 40, 60, 80], tfmt: (v) => v + "", rowH: 32, label: "Berre breidde" });
    cap(c, "Berre ankerdel kontrollert, prosent");
    F.rows(c, { w: Math.floor(c.getBoundingClientRect().width) }, { rows: d.berre_anker.map((q) => ({ label: q.namn, v: q.y, mark: "dot", vtxt: F.n(q.y, 1), color: "var(--fg)", r: 4.5, tip: q.namn + "|ankerdel " + F.n(q.y, 1) + " %" })), min: 0, max: 60, ticks: [0, 20, 40, 60], tfmt: (v) => v + "", rowH: 32, label: "Berre ankerdel" });
  };

  /* ---------- f22: stig og fall ---------- */
  F.fig.f22 = function (m, d, ctx) {
    const W = ctx.w;
    cap(m, "Uttrykk som stig og fell mellom periodar (tal på uttrykk)");
    const rows = d.overgangar.map((o) => ({ t: o.namn, up: [o.opp], dn: [o.ned] })).concat([{ t: d.lang_bogen.namn, up: d.lang_bogen.opp, dn: d.lang_bogen.ned, lang: true }]);
    const rh = 50, H = rows.length * rh + 6, svg = F.svg(m, W, H, "Stigande og fallande uttrykk");
    const cx = W / 2, sc = d3.scaleLinear().domain([0, 48]).range([0, W / 2 - 30]);
    rows.forEach((r, i) => {
      const y0 = i * rh + 4;
      F.s("text", { x: 0, y: y0 + 8, text: r.t, cls: "fg" }, svg);
      const g = F.s("g", { cls: "mk fd", tip: r.t + "|stig: " + r.up.join(" til ") + "|fell: " + r.dn.join(" til ") }, svg);
      const by = y0 + 18, bh = 16;
      F.s("rect", { x: cx, y: by, width: Math.max(r.up[0] ? 2 : 0, sc(r.up[0])), height: bh, fill: "var(--fg)", cls: "gx" }, g);
      if (r.lang) F.s("rect", { x: cx + sc(r.up[0]), y: by, width: sc(r.up[1]) - sc(r.up[0]), height: bh, fill: F.hatch(svg, "var(--fg)") , stroke: "var(--fg)", "stroke-width": 1 }, g);
      F.s("rect", { x: cx - Math.max(r.dn[0] ? 2 : 0, sc(r.dn[0])), y: by, width: Math.max(r.dn[0] ? 2 : 0, sc(r.dn[0])), height: bh, fill: "var(--ref)", cls: "gx" }, g);
      if (r.lang) F.s("rect", { x: cx - sc(r.dn[1]), y: by, width: sc(r.dn[1]) - sc(r.dn[0]), height: bh, fill: F.hatch(svg, "var(--ref)"), stroke: "var(--ref)", "stroke-width": 1 }, g);
      F.s("text", { x: cx + sc(r.up[r.up.length - 1]) + 6, y: by + 12, text: r.lang ? r.up[0] + "–" + r.up[1] : r.up[0], cls: "b" }, g);
      F.s("text", { x: cx - sc(r.dn[r.dn.length - 1]) - 6, y: by + 12, "text-anchor": "end", text: r.lang ? r.dn[0] + "–" + r.dn[1] : r.dn[0], cls: "b" }, g);
      F.s("line", { x1: cx, x2: cx, y1: by - 3, y2: by + bh + 3, stroke: "var(--fg)" }, svg);
    });
    F.legend(m, [{ c: "var(--fg)", t: "stig" }, { c: "var(--ref)", t: "fell" }]);
    cap(m, "Tre døme: verk med uttrykket i engelsk samandrag", 18);
    F.rows(m, ctx, { rows: d.dome.map((q) => ({ label: q.namn + (q.fra_pct ? " (" + F.n(q.fra_pct, 1) + " % → " + F.n(q.til_pct, 1) + " %)" : ""), vtxt: q.fra + " → " + q.til, mark: "none", dots: [{ v: q.fra, color: "var(--fg)", hollow: true }, { v: q.til, color: "var(--fg)" }], linkc: "var(--ref)", tip: q.namn + "|frå " + q.fra + (q.fra_n ? " av om lag " + n0(q.fra_n) : "") + " verk|til " + q.til + (q.til_n ? " av " + n0(q.til_n) : "") + " verk" })), min: 0, max: 160, ticks: [0, 40, 80, 120, 160], tfmt: (v) => v + "", rowH: 44, label: "Tre døme" });
    F.legend(m, [{ c: "var(--fg)", t: "tidleg", r: true, open: true }, { c: "var(--fg)", t: "seint", r: true }]);
    cap(m, "Første framtreding i data: del av fleirordsuttrykka, prosent", 22);
    const f = d.forste;
    F.cols(m, W, 170, { items: f.periodar.map((p, i) => ({ label: p, vals: [f.termar_pct[i]], tip: p + "|" + f.termar_pct[i] + " % av fleirordsuttrykka syner seg første gong|" + (i === 0 ? "21" : (i === 1 ? "om lag 1 000" : "om lag 2 430")) + " verk med engelsk samandrag" })), max: 100, color: "var(--fg)", fmt: (v) => v + " %", ticks: [0, 50, 100], yfmt: (v) => v + "", label: "Første framtreding", always: true });
    F.d("p", { cls: "sm" }, m).append("Verk med engelsk samandrag: ", b("21"), " (1995–99), ", b("om lag 1 000"), " (2000–14), ", b("om lag 2 430"), " (2015–25). Det er dekning, ikkje første bruk. Døme: design research ", b(d.forste_dome[0].ar), ", participatory design ", b(d.forste_dome[1].ar), ".");
  };

  /* ---------- f23: kunnskapsformer ---------- */
  F.fig.f23 = function (m, d, ctx) {
    const [A, B] = F.pans(m, 2, "p2", ["Del av 80 lesne tekstar som har forma, prosent (95 % intervall)", "Samsvar mellom markør og lesing: kappa"]);
    const rows = d.former.map((q) => {
      const r = { label: q.namn.replace(/^./, (c) => c.toUpperCase()), v: q.lesing, lo: q.lo, hi: q.hi, mark: "dot", color: "var(--fg)", vtxt: F.n(q.lesing, 1) + (q.lesing === 0 ? " (til " + F.n(q.hi, 1) + ")" : ""), tip: q.namn + "|lesing " + F.n(q.lesing, 1) + " % (" + F.n(q.lo, 1) + " til " + F.n(q.hi, 1) + ")" };
      if (q.kode === "data_collection") { r.dots = [{ v: d.marker.datainnsamling.pct, color: "var(--fg)", hollow: true, r: 4.5 }, { v: d.justert_datainnsamling, color: "var(--dim)", tick: true }]; r.tip += "|markør, alle " + n0(d.marker.datainnsamling.k) + " av " + n0(d.marker.datainnsamling.n) + ": " + F.n(d.marker.datainnsamling.pct, 1) + " %|justert, om lag " + F.n(d.justert_datainnsamling, 1) + " %"; r.link = false; }
      return r;
    });
    F.rows(A, { w: A.w }, { rows, min: 0, max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", rowH: 38, valW: 7.2, label: "Del av tekstane per kunnskapsform" });
    F.legend(A, [{ c: "var(--fg)", t: "lesing av 80", r: true }, { c: "var(--fg)", t: "markør, alle " + n0(d.populasjon), r: true, open: true }, { c: "var(--dim)", t: "justert" }]);
    const kr = d.former.map((q) => ({ label: q.namn.replace(/^./, (c) => c.toUpperCase()), v: q.kappa, lo: q.malbar ? d.kappa_data_ci[0] : null, hi: q.malbar ? d.kappa_data_ci[1] : null, mark: "dot", open: !q.malbar, color: q.malbar ? "var(--fg)" : (q.grense ? "var(--fg)" : "var(--dim)"), vtxt: F.n(q.kappa, 2) + (q.malbar ? " målbar" : (q.grense ? " grense" : "")), vcls: q.malbar ? "b" : "", tip: q.namn + "|kappa " + F.n(q.kappa, 2) + (q.malbar ? " (" + F.n(d.kappa_data_ci[0], 2) + " til " + F.n(d.kappa_data_ci[1], 2) + ")|presisjon " + F.n(d.presisjon, 2) + ", gjenfinning " + F.n(d.gjenfinning, 2) : (q.grense ? "|grensetilfelle" : "")) }));
    F.rows(B, { w: B.w }, { rows: kr, min: -0.2, max: 1, ticks: [0, 0.25, 0.5, 0.75, 1], tfmt: (v) => F.n(v, 2), fmt: (v) => F.n(v, 2), rowH: 38, valW: 7.2, label: "Kappa per form" });
    F.d("p", { cls: "sm" }, B).append("Berre datainnsamling er målbar: kappa ", b("0,75"), " (0,52–0,95), presisjon ", b("0,83"), ", gjenfinning ", b("0,95"), ". Argument er eit grensetilfelle.");
    /* matrise */
    const sec = F.d("div", { style: "margin-top:34px;max-width:640px" }, m);
    cap(sec, "Kva former står saman: phi mellom former, " + d.per_tekst.n + " lesne tekstar");
    const codes = d.kodar.filter((k) => d.phi.some((p) => p.a === k || p.b === k));
    const lab = { argument: "argument", literature: "litteratur", example: "eksempel", case: "case", data_collection: "datainnsamling", design_work: "designarbeid", practice_reflection: "praksisrefleksjon", use_in_practice: "bruk i praksis" };
    const W = Math.min(ctx.w, 640), labW = ctx.mob ? 122 : 136, cs = Math.min(46, (W - labW - 8) / codes.length), H = cs * codes.length + 6;
    const svg = F.svg(sec, W, H, "Samførekomst mellom kunnskapsformer");
    const idx = {}; codes.forEach((k, i) => (idx[k] = i));
    codes.forEach((k, i) => {
      F.s("text", { x: labW - 6, y: i * cs + cs / 2 + 4, "text-anchor": "end", text: lab[k] || k, cls: "fg" }, svg);
      F.s("line", { x1: labW, x2: labW + (i + 1) * cs, y1: i * cs + cs, y2: i * cs + cs, stroke: "var(--hair)" }, svg);
      F.s("line", { x1: labW + i * cs + cs, x2: labW + i * cs + cs, y1: i * cs, y2: H - 6, stroke: "var(--hair)" }, svg);
    });
    d.phi.forEach((p) => {
      let i = idx[p.a], j = idx[p.b]; if (i < j) { const t = i; i = j; j = t; }
      const cxp = labW + j * cs + cs / 2, cyp = i * cs + cs / 2, r = Math.max(2, Math.sqrt(Math.abs(p.phi)) * cs * 0.58);
      const g = F.s("g", { cls: "mk fd", tip: (lab[p.a] || p.a) + " og " + (lab[p.b] || p.b) + "|phi " + F.n(p.phi, 2) + "|" + p.n + " tekstar har begge" }, svg);
      F.s("rect", { x: cxp - cs / 2, y: cyp - cs / 2, width: cs, height: cs, fill: "transparent" }, g);
      F.s("circle", { cx: cxp, cy: cyp, r, fill: p.phi >= 0 ? "var(--fg)" : "var(--bg)", stroke: "var(--fg)", "stroke-width": p.phi >= 0 ? 0 : 1.6, opacity: p.phi >= 0 ? 0.25 + Math.abs(p.phi) * 1.4 : 1 }, g);
      if (Math.abs(p.phi) >= 0.33) F.s("text", { x: cxp, y: cyp + 3.5, "text-anchor": "middle", text: F.n(p.phi, 2).replace("−0,", "−.").replace(/^0,/, "."), cls: "sm", style: "fill:" + (p.phi >= 0 ? "var(--bg)" : "var(--fg)") }, g);
    });
    F.legend(sec, [{ c: "var(--fg)", t: "saman oftare enn tilfeldig", r: true }, { c: "var(--fg)", t: "saman sjeldnare", r: true, open: true }]);
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
      const w = Math.floor(el.getBoundingClientRect().width) || (mob ? W : W / 2 - 24);
      const heights = [], lines = [];
      const cpl = Math.floor((w - 72) / 6.4);
      q.rader.forEach((r) => { const t = r.namn; const l1 = t.length <= cpl ? [t] : wrap(t, cpl); lines.push(l1); heights.push(l1.length * 14 + 64); });
      const H = heights.reduce((a, c) => a + c, 0) + 4;
      const svg = F.svg(el, w, H, q.tittel);
      let y = 2;
      q.rader.forEach((r, ri) => {
        const L = lines[ri], domC = "var(--fg)";
        const g = F.s("g", { cls: "mk" }, svg);
        const unit = r.eining === "prosent" ? " %" : (r.eining === "del" || r.eining === "forhold" || r.eining === "indeks" || r.eining === "poeng" || r.eining === "rho" || r.eining === "AUC" || r.eining === "tal" || r.eining === "gonger" ? "" : " " + r.eining);
        L.forEach((t, k) => F.s("text", { x: 0, y: y + 11 + k * 14, text: t, cls: "fg", style: "font-size:11.5px" }, g));
        /* dom */
        const dx = w - 4, dy = y + 7;
        const gl = F.s("g", { tip: (r.dom === "treff" ? "Treff" : (r.dom === "bom" ? "Bom" : "Ikkje avgjort")) + "|" + vtxt(r) }, svg);
        const lbl = r.dom === "treff" ? "treff" : (r.dom === "bom" ? "bom" : "open");
        F.s("rect", { x: dx - 40, y: dy - 9, width: 40, height: 17, rx: 8.5, fill: r.dom === "treff" ? "var(--fg)" : "transparent", stroke: "var(--fg)", "stroke-width": 1.2, "stroke-dasharray": r.dom === "open" ? "2.5 2" : null }, gl);
        F.s("text", { x: dx - 20, y: dy + 3, "text-anchor": "middle", text: lbl, style: "fill:" + (r.dom === "treff" ? "var(--bg)" : "var(--fg)") + ";font-size:10.5px" }, gl);
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
        r.obs.forEach((o, k) => {
          const xo = x(Math.max(r.akse[0], Math.min(r.akse[1], o.v)));
          if (o.lo != null && o.hi != null && !(o.lo === o.hi)) {
            F.s("line", { x1: x(Math.max(r.akse[0], o.lo)), x2: x(Math.min(r.akse[1], o.hi)), y1: ty, y2: ty, stroke: "var(--fg)", "stroke-width": 2.2 }, svg);
            F.s("line", { x1: x(Math.max(r.akse[0], o.lo)), x2: x(Math.max(r.akse[0], o.lo)), y1: ty - 5, y2: ty + 5, stroke: "var(--fg)", "stroke-width": 1.4 }, svg);
            F.s("line", { x1: x(Math.min(r.akse[1], o.hi)), x2: x(Math.min(r.akse[1], o.hi)), y1: ty - 5, y2: ty + 5, stroke: "var(--fg)", "stroke-width": 1.4 }, svg);
          }
          marker(svg, shapes[k % 5], xo, ty, o.mid ? true : false);
          const txt = F.n(o.v, Math.abs(o.v) < 1 && o.v % 0.1 ? 2 : (o.v % 1 ? 1 : 0));
          F.s("text", { x: Math.max(14, Math.min(w - 14, xo)), y: ty - 17 + (k % 2 ? 0 : 0), "text-anchor": "middle", text: txt, cls: "b halo" }, svg);
        });
        /* akseendar */
        const fmtA = (v) => F.n(v, v % 1 ? 1 : 0);
        F.s("text", { x: px0, y: ty + 24, text: fmtA(r.akse[0]), cls: "sm" }, svg);
        F.s("text", { x: px1, y: ty + 24, "text-anchor": "end", text: fmtA(r.akse[1]) + unit, cls: "sm" }, svg);
        if (r.obs.length > 1) {
          const lg = r.obs.map((o, k) => ["●", "◆", "■", "▲", "✚"][k % 5] + " " + (o.namn || "") + " " + F.n(o.v, o.v % 1 ? 1 : 0)).join("   ");
          F.s("text", { x: w / 2, y: ty + 24, "text-anchor": "middle", text: F.trunc(lg, cpl + 6), cls: "sm" }, svg);
        }
        /* skyggeforklaring i tips */
        const tip = r.namn + "|forventa " + vtxtV(vn, unit) + "|observert " + r.obs.map((o) => (o.namn ? o.namn + " " : "") + F.n(o.v, 2) + (o.lo != null && o.lo !== o.hi ? " (" + F.n(o.lo, 2) + " til " + F.n(o.hi, 2) + ")" : "") + unit).join(", ") + (r.merknad ? "|" + r.merknad : "") + (r.avleidd ? "|Utleidd tal" : "");
        g.setAttribute("data-tip", tip);
        F.s("rect", { x: 0, y: y, width: w, height: heights[ri], fill: "transparent" }, g);
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
