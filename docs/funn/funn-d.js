/* FUNN - seksjon 5 og 6: svak struktur, emne og klynger, omgrep (f19 til f22). */
(function () {
  "use strict";
  const F = window.FUNN, n0 = F.n;
  const b = (t) => Object.assign(document.createElement("b"), { textContent: t });
  const cap = (el, t, mt) => F.d("h4", { text: t, style: "font:400 12px/1.35 var(--mono);color:var(--dim);margin:" + (mt == null ? 0 : mt) + "px 0 6px" }, el);
  const pc = (v) => F.n(v, 1) + " %";
  /* metastudiens ti klynger har bokstavane A til J, aldri kartets nummer 1 til 8 eller kartfargane */
  const LET = "ABCDEFGHIJ";
  /* overskrift med firkanta bokstavmerke: metastudiens klynger A–J, aldri kartets runde tal 1–8 */
  const capT = (el, chip, t, mt) => { const h = cap(el, "", mt); const c = F.d("span", { cls: "bokst", text: chip, style: "width:auto;min-width:20px;padding:0 5px;margin-right:8px;vertical-align:1px" }, h); h.appendChild(document.createTextNode(t)); return h; };

  /* ---------- f19: svak struktur ---------- */
  F.fig.f19 = function (m, d, ctx) {
    const [L, R] = F.pans(m, 2, "p2", ["", ""]);

    capT(L, "A–J", "Tekstklynger: silhuett mot tilfeldig datasky");
    F.rows(L, { w: L.w }, { rows: [{ label: "Observert, ti klynger", v: d.silhuett.observert, color: "var(--fg)" }, { label: "Tilfeldig datasky", v: d.silhuett.tilfeldig, color: "var(--ref)" }], max: 0.1, ticks: [0, 0.05, 0.1], tfmt: (v) => F.n(v, 2), fmt: (v) => F.n(v, 4), mark: "bar", rowH: 36, label: "Silhuett" });
    F.d("p", { cls: "sm" }, L).append(b(F.p(d.midt_mellom, 1)), " av verka ligg nesten midt mellom to klyngesenter.");
    cap(L, "Justert R², prosent av variasjonen i tekstvektorane", 22);
    const nm = (s) => s.replace("ti klynger", "ti klynger (A–J)").replace("kanal (12)", "kanal (12 kanalar)").replace(/^./, (c) => c.toUpperCase());
    F.rows(L, { w: L.w }, { rows: d.r2.map((q, i) => ({ label: nm(q.namn), v: q.pct, color: i === 0 ? "var(--fg)" : "var(--t3)", group: i === 0 ? "Alle med fulltekst, n " + n0(d.verk) : null })).concat(d.r2_same.map((q, i) => ({ label: nm(q.namn), v: q.pct, color: "var(--t3)", group: i === 0 ? "Same verk, n 1 435" : null }))), max: 16, ticks: [0, 4, 8, 12, 16], tfmt: (v) => v + "", fmt: (v) => F.n(v, 2) + " %", mark: "bar", rowH: 32, gH: 26, label: "Justert R2" });
    F.d("p", { cls: "sm" }, L).append("Kanal forklarer meir enn land eller periode, men er ikkje årsak.");
    capT(R, "I", "Den norskspråklege tekstklynga: del med nordisk språk, prosent");
    F.rows(R, { w: R.w }, { rows: [{ label: "I klynge I, n " + d.klynge8.n, v: d.klynge8.nordisk, color: "var(--fg)" }, { label: "Alle verk med fulltekst, n " + n0(d.verk), v: d.klynge8.alle, color: "var(--ref)" }], max: 100, ticks: [0, 50, 100], tfmt: (v) => v + "", fmt: pc, mark: "bar", rowH: 36, label: "Nordisk språk" });
    cap(R, "Kva fulltekstutvalet dekkjer: del av verka med fulltekst, prosent", 24);
    const e = (t, v, g) => ({ label: t, v, color: "var(--fg)", group: g });
    F.rows(R, { w: R.w }, { rows: d.utval_periode.map((q, i) => e(q[0], q[1], i === 0 ? "Periode" : null)).concat(d.utval_sprak.map((q, i) => e(q[0].replace(/^./, (c) => c.toUpperCase()) + "språklege", q[1], i === 0 ? "Språk" : null)), d.utval_type.map((q, i) => e(q[0].replace(/^./, (c) => c.toUpperCase()), q[1], i === 0 ? "Slag" : null))), max: 100, ticks: [0, 25, 50, 75, 100], tfmt: (v) => v + "", fmt: pc, rowH: 32, gH: 26, label: "Kva fulltekstutvalet dekkjer" });
  };

  /* ---------- f20: emne og klynger ---------- */
  F.fig.f20 = function (m, d, ctx) {
    const [L, R] = F.pans(m, 2, "p2", ["", ""]);

    const heile = {}; d.topp.forEach((q) => { heile[q.namn] = q.pct; });
    cap(L, "OpenAlex-emne (engelske namn frå OpenAlex), 13 med minst 30 verk. Søyler: del per femårsperiode, mørke endrar seg. Tal: del av alle " + n0(d.emne_n) + " verk med emne", 0);
    F.spark(L, { w: L.w }, { rows: d.emne.map((q) => ({ label: q.namn, vals: q.del, flag: !!q.endrar, vtxt: heile[q.namn] != null ? F.n(heile[q.namn], 1) + " %" : " ", tip: q.namn + "|" + d.periodar.map((p, i) => p + ": " + F.n(q.del[i], 1) + " %").join("|") + (heile[q.namn] != null ? "|" + F.n(heile[q.namn], 1) + " % av alle verk med emne" : "") })), kind: "bars", perRow: true, periods: d.periodar, max: 50, rowH: 34, labelW: 210, vw: 84, label: "Emne over tid" });
    F.d("p", { cls: "sm" }, L).append(b(n0(d.ulike_emne)), " ulike emne. ", b(n0(d.mekanisk[0])), " av dei ", n0(d.mekanisk[1]), " i det største emnet ligg under Mechanical Engineering, og domenet Physical Sciences har ", b(pc(d.domene.fysiske[1])), " (", n0(d.domene.fysiske[0]), " verk).");
    F.d("p", { cls: "sm" }, L).append("Eit utval på 300 verk har ", b(F.n(d.rikdom_300[0], 1)), " ulike emne i 2005–09 og ", b(F.n(d.rikdom_300[3], 1)), " i 2020–24.");
    capT(R, "A–J", "Tekstklynger: del av verka i fulltekstutvalet, 2005–09 til 2020–24, prosent");
    const order = ["veks", "fell", "ingen"], gname = { veks: "Veks", fell: "Fell", ingen: "Ingen lineær trend" };
    const rows = [];
    order.forEach((g) => d.klynger.filter((k) => k.retning === g).forEach((k, i) => rows.push({ label: k.namn.replace(/^./, (c) => c.toUpperCase()), badge: LET[k.id], vals: k.del, flag: g === "veks", dash: g === "fell", group: i === 0 ? gname[g] : null, tip: LET[k.id] + " " + k.namn + "|" + d.klyngeperiodar.map((p, j) => p + ": " + F.n(k.del[j], 1) + " %").join("|") + "|" + n0(k.n) + " verk i klynga" })));
    F.spark(R, { w: R.w }, { rows, kind: "line", periods: d.klyngeperiodar, max: 27, rowH: 38, labelW: 210, vw: 92, label: "Klyngeandelar over tid" });
    F.d("p", { cls: "sm" }, R).append("Heiltrukke linje veks, stipla fell.");
  };

  /* ---------- f21: breidde og ankerdel, alle omgrep i éin figur ---------- */
  F.fig.f21 = function (m, d, ctx) {
    const W = ctx.w, mob = W < 520;
    const all = {};
    const mid = (q) => (q.x_lo != null ? (q.x_lo + q.x_hi) / 2 : q.x);
    d.begge.concat(d.berre_breidde, d.berre_anker).forEach((q) => { all[q.namn] = Object.assign(all[q.namn] || {}, q); });
    const rows = Object.keys(all).map((k) => all[k]).sort((a, c) => (mid(c) == null ? -1 : mid(c)) - (mid(a) == null ? -1 : mid(a)) || (c.y || 0) - (a.y || 0));
    const labW = mob ? 116 : 190, gap = 18, aw = Math.floor((W - labW - gap - 10) / 2), rh = 32, top = 44;
    const H = top + rows.length * rh + 6;
    const svg = F.svg(m, W, H, "Breidde og ankerdel for omgrep");
    const x1 = d3.scaleLinear().domain([0, 80]).range([labW, labW + aw]), x2 = d3.scaleLinear().domain([0, 60]).range([labW + aw + gap, labW + aw * 2 + gap]);
    F.s("text", { x: labW, y: 12, text: "breidde, %", cls: "fg" }, svg);
    F.s("text", { x: labW + aw + gap, y: 12, text: "ankerdel, %", cls: "fg" }, svg);
    [[x1, [0, 40, 80]], [x2, [0, 30, 60]]].forEach(([xs, tk]) => tk.forEach((t) => { F.s("line", { x1: xs(t), x2: xs(t), y1: top - 8, y2: H - 4, stroke: "var(--hair)" }, svg); F.s("text", { x: xs(t), y: top - 12, "text-anchor": t === 0 ? "start" : (t === tk[2] ? "end" : "middle"), text: t, cls: "sm" }, svg); }));
    rows.forEach((q, i) => {
      const y = top + i * rh, cy = y + rh / 2;
      const tip = q.namn + "|breidde " + (q.x_lo != null ? "3 til 10 %" : (q.x != null ? F.n(q.x, 1) + " %" : "ikkje kontrollert")) + "|ankerdel " + (q.y != null ? F.n(q.y, 1) + " %" : "ikkje kontrollert") + (d.anker_tittel[q.namn] ? "|" + d.anker_tittel[q.namn] : "");
      const g = F.s("g", { cls: "mk fd", tip }, svg);
      F.s("rect", { x: 0, y, width: W, height: rh - 2, fill: "transparent" }, g);
      F.wrap(q.namn, Math.floor((labW - 8) / 7.0), 2).forEach((t, k, arr) => F.s("text", { x: 0, y: cy + 4 + (k - (arr.length - 1) / 2) * 13, text: t, cls: "fg" }, g));
      F.s("line", { x1: labW, x2: W - 10, y1: y + rh - 1, y2: y + rh - 1, stroke: "var(--hair)" }, g);
      if (q.x_lo != null) {
        F.s("line", { x1: x1(q.x_lo), x2: x1(q.x_hi), y1: cy, y2: cy, stroke: "var(--fg)", "stroke-width": 2, "stroke-dasharray": "3 2" }, g);
        [q.x_lo, q.x_hi].forEach((v) => F.s("line", { x1: x1(v), x2: x1(v), y1: cy - 5, y2: cy + 5, stroke: "var(--fg)", "stroke-width": 1.5 }, g));
        F.s("text", { x: x1(q.x_hi) + 7, y: cy + 4, text: "spenn 3–10", cls: "sm" }, g);
      } else if (q.x != null) { const fl1 = x1(q.x) > labW + aw - 46; F.s("circle", { cx: x1(q.x), cy, r: 5.5, fill: "var(--fg)" }, g); F.s("text", { x: x1(q.x) + (fl1 ? -9 : 9), y: cy + 4, "text-anchor": fl1 ? "end" : "start", text: F.n(q.x, 1), cls: "b sm halo" }, g); }
      else F.s("text", { x: labW + 4, y: cy + 4, text: "–", cls: "sm" }, g);
      if (q.y != null) { const flip = x2(q.y) > labW + aw * 2 + gap - 44; F.s("circle", { cx: x2(q.y), cy, r: 5.5, fill: "var(--fg)" }, g); F.s("text", { x: x2(q.y) + (flip ? -9 : 9), y: cy + 4, "text-anchor": flip ? "end" : "start", text: F.n(q.y, 1), cls: "b sm halo" }, g); }
      else F.s("text", { x: labW + aw + gap + 4, y: cy + 4, text: "–", cls: "sm" }, g);
    });
    F.legend(m, [{ c: "var(--fg)", t: "punkt: kontrollert tal", r: true }, { c: "var(--fg)", ln: "dashed", t: "spenn, ikkje punkt" }]);
    F.d("p", { cls: "sm" }, m).append("– betyr ikkje kontrollert. Omgrepa er engelske uttrykk slik dei står i tekstane. Breidda for participatory design og more-than-human er frå skriptutskrifta og står ikkje i funnteksten.");
  };

  /* ---------- f22: stig og fall ---------- */
  F.fig.f22 = function (m, d, ctx) {
    const W = ctx.w;
    cap(m, "Uttrykk (frå engelske samandrag) som stig og fell frå ein periode til neste, tal på uttrykk");
    const rows = d.overgangar.map((o) => ({ t: o.namn, up: o.opp, dn: o.ned }));
    const rh = 52, H = rows.length * rh + 4, svg = F.svg(m, W, H, "Stigande og fallande uttrykk per periodesteg");
    const cx = W / 2, sc = d3.scaleLinear().domain([0, 12]).range([0, W / 2 - 36]);
    rows.forEach((r, i) => {
      const y0 = i * rh + 4;
      const lite = r.up + r.dn <= 2;
      F.s("text", { x: 0, y: y0 + 10, text: r.t + (lite ? " · få uttrykk" : ""), cls: lite ? "" : "fg" }, svg);
      const g = F.s("g", { cls: "mk fd", tip: r.t + "|stig " + r.up + "|fell " + r.dn + (lite ? "|svært få uttrykk, les med varsemd" : ""), opacity: lite ? 0.6 : null }, svg);
      const by = y0 + 20, bh = 18;
      F.s("rect", { x: cx, y: by, width: Math.max(r.up ? 2 : 0, sc(r.up)), height: bh, fill: "var(--fg)", cls: "gx" }, g);
      F.s("rect", { x: cx - Math.max(r.dn ? 2 : 0, sc(r.dn)), y: by, width: Math.max(r.dn ? 2 : 0, sc(r.dn)), height: bh, fill: "var(--ref)", cls: "gx" }, g);
      F.s("text", { x: cx + sc(r.up) + 6, y: by + 13, text: r.up, cls: "b" }, g);
      F.s("text", { x: cx - sc(r.dn) - 6, y: by + 13, "text-anchor": "end", text: r.dn, cls: "b" }, g);
      F.s("line", { x1: cx, x2: cx, y1: by - 3, y2: by + bh + 3, stroke: "var(--fg)" }, svg);
    });
    F.legend(m, [{ c: "var(--ref)", t: "fell" }, { c: "var(--fg)", t: "stig" }]);
    const lb = d.lang_bogen;
    F.d("p", { cls: "sm" }, m).append("Heile bogen " + lb.namn + ": ", b(lb.opp[0] + " til " + lb.opp[1] + " stig"), " og ", b(lb.ned[0] + " til " + lb.ned[1] + " fall"), " (to terskelval).");
    cap(m, "Tre døme (engelske uttrykk): verk med uttrykket i engelsk samandrag", 18);
    F.rows(m, ctx, { rows: d.dome.map((q) => ({ label: q.namn + (q.fra_pct ? " (" + F.n(q.fra_pct, 1) + " % → " + F.n(q.til_pct, 1) + " %)" : ""), vtxt: "tidleg " + q.fra + " / seint " + q.til, mark: "none", dots: [{ v: q.fra, color: "var(--fg)", hollow: true }, { v: q.til, color: "var(--fg)" }], linkc: "var(--ref)", tip: q.namn + "|frå " + q.fra + (q.fra_n ? " av om lag " + n0(q.fra_n) : "") + " verk|til " + q.til + (q.til_n ? " av " + n0(q.til_n) : "") + " verk" })), min: 0, max: 160, ticks: [0, 40, 80, 120, 160], tfmt: (v) => v + "", rowH: 44, label: "Tre døme" });
    F.legend(m, [{ c: "var(--fg)", t: "tidleg", r: true, open: true }, { c: "var(--fg)", t: "seint", r: true }]);
    cap(m, "Første framtreding i data: del av fleirordsuttrykka, prosent", 22);
    const f = d.forste;
    F.cols(m, W, 170, { items: f.periodar.map((p, i) => ({ label: p, vals: [f.termar_pct[i]], tip: p + "|" + f.termar_pct[i] + " % av fleirordsuttrykka syner seg første gong|" + (i === 0 ? "21" : (i === 1 ? "om lag 1 000" : "om lag 2 430")) + " verk med engelsk samandrag" })), max: 100, color: "var(--fg)", fmt: (v) => v + " %", ticks: [0, 50, 100], yfmt: (v) => v + "", label: "Første framtreding", always: true });
    F.d("p", { cls: "sm" }, m).append("Verk med engelsk samandrag: ", b("21"), " (1995–99), ", b("om lag 1 000"), " (2000–14), ", b("om lag 2 430"), " (2015–25). Det er dekning, ikkje første bruk. Døme: design research ", b(d.forste_dome[0].ar), ", participatory design ", b(d.forste_dome[1].ar), ".");
  };
})();
