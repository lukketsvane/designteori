/* FUNN - hjelparar for søyler, stabla søyler og linjer over periodar. */
(function () {
  "use strict";
  const F = window.FUNN;
  let hid = 0;

  F.hatch = function (svg, color, bg) {
    const id = "ht" + ++hid;
    let defs = svg.querySelector("defs");
    if (!defs) defs = svg.insertBefore(F.s("defs"), svg.firstChild);
    const p = F.s("pattern", { id, width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    F.s("rect", { width: 5, height: 5, fill: bg || "var(--bg)" }, p);
    F.s("line", { x1: 0, y1: 0, x2: 0, y2: 5, stroke: color || "var(--dim)", "stroke-width": 2.2 }, p);
    return "url(#" + id + ")";
  };
  const fillOf = (svg, f) => (f && f.hatch ? F.hatch(svg, f.hatch) : (f && f.outline ? "var(--bg)" : (f && f.fill) || f));
  F.fillOf = fillOf;

  /* søyler (ein eller fleire seriar). items: [{label, vals:[...], tip, color}] */
  F.cols = function (p, w, h, o) {
    const items = o.items, ns = o.series ? o.series.length : 1;
    const hasSub = items.some((q) => q.sub != null);
    const pl = o.pl == null ? 30 : o.pl, pr = 2, pt = 16, pb = o.pb == null ? (hasSub ? 38 : 24) : o.pb;
    const svg = F.svg(p, w, h, o.label);
    const x = d3.scaleBand().domain(items.map((_, i) => i)).range([pl, w - pr]).paddingInner(o.pad == null ? 0.22 : o.pad).paddingOuter(0.05);
    const y = d3.scaleLinear().domain([0, o.max]).range([h - pb, pt]);
    const fm = o.fmt || ((v) => F.n(v, o.d || 0));
    F.axisY(svg, y, pl, w - pl - pr, { n: o.n || 4, fmt: o.yfmt || fm, values: o.ticks });
    (o.refs || []).forEach((rf) => {
      F.s("line", { x1: pl, x2: w - pr, y1: y(rf.v), y2: y(rf.v), cls: "ref" }, svg);
      if (rf.label) F.s("text", { x: w - pr, y: y(rf.v) - 4, "text-anchor": "end", text: rf.label, cls: "sm halo" }, svg);
    });
    const sub = d3.scaleBand().domain(d3.range(ns)).range([0, x.bandwidth()]).padding(ns > 1 ? 0.08 : 0);
    const skip = Math.ceil(36 / x.step());
    items.forEach((it, i) => {
      const g = F.s("g", { cls: "mk", tip: it.tip || (it.label + "|" + it.vals.map((v, k) => (o.series ? o.series[k].name + " " : "") + fm(v)).join("  ")) }, svg);
      F.s("rect", { x: x(i) - 2, y: pt, width: x.bandwidth() + 4, height: h - pb - pt, fill: "transparent" }, g);
      it.vals.forEach((v, k) => {
        if (v == null) return;
        const c = (o.series ? o.series[k].color : (it.color || o.color)) || "var(--fg)";
        const bx = x(i) + sub(k), bw = sub.bandwidth();
        const hz = it.hatch ? F.hatch(svg, c) : null;
        F.s("rect", { x: bx, y: y(v), width: bw, height: Math.max(0.8, h - pb - y(v)), fill: hz || fillOf(svg, c), stroke: hz ? c : (c.outline || null), "stroke-width": hz ? 1 : null, opacity: it.fade ? 0.55 : null, cls: "gy" }, g);
        if (o.vl !== false && (ns === 1 || bw > 20) && (items.length <= (o.vlMax || 9) || x.step() > 26)) {
          if (it.vlIn) F.s("text", { x: bx + bw / 2, y: h - pb - 4, "text-anchor": "middle", text: fm(v), cls: "sm", style: "fill:var(--bg)" }, g);
          else F.s("text", { x: bx + bw / 2, y: y(v) - 4, "text-anchor": "middle", text: fm(v), cls: "sm halo" + (o.vb ? " b" : "") }, g);
        }
      });
      if (!(i % skip) || it.always) F.s("text", { x: x(i) + x.bandwidth() / 2, y: h - pb + 14, "text-anchor": "middle", text: it.label }, svg);
      if (it.sub != null && (!(i % skip) || it.always)) F.s("text", { x: x(i) + x.bandwidth() / 2, y: h - pb + 26, "text-anchor": "middle", text: it.sub, cls: "sm" }, svg);
    });
    return { svg, x, y };
  };

  /* stabla søyler, kvar kategori sum 100 (eller eigen sum). cats: [namn], keys: [{k, name, fill}], vals[i][k] */
  F.stackCols = function (p, w, h, o) {
    const pl = o.pl == null ? 30 : o.pl, pr = 2, pt = 10, pb = 22;
    const svg = F.svg(p, w, h, o.label);
    const x = d3.scaleBand().domain(o.cats.map((_, i) => i)).range([pl, w - pr]).paddingInner(0.16).paddingOuter(0.04);
    const y = d3.scaleLinear().domain([0, o.max || 100]).range([h - pb, pt]);
    F.axisY(svg, y, pl, w - pl - pr, { values: [0, 25, 50, 75, 100], fmt: (v) => v + "" });
    const skip = Math.ceil(40 / x.step());
    o.cats.forEach((c, i) => {
      let acc = 0;
      const g = F.s("g", { cls: "mk" }, svg);
      const lines = [c.label || c];
      o.keys.forEach((kk) => {
        const v = o.vals[i][kk.k] || 0;
        if (v <= 0) return;
        F.s("rect", { x: x(i), y: y(acc + v), width: x.bandwidth(), height: Math.max(0.5, y(acc) - y(acc + v)), fill: fillOf(svg, kk.fill), stroke: kk.fill && kk.fill.outline ? "var(--dim)" : null, "stroke-dasharray": kk.fill && kk.fill.outline ? "3 2" : null, cls: "gy", tip: (c.label || c) + "|" + kk.name + " " + F.n(v, 1) + " %" + (o.n ? "|" + F.n(o.n[i]) + " verk" : "") }, g);
        if (o.inside && !(kk.fill && kk.fill.hatch) && (y(acc) - y(acc + v)) > 13 && x.bandwidth() > 24) F.s("text", { x: x(i) + x.bandwidth() / 2, y: (y(acc) + y(acc + v)) / 2 + 3.5, "text-anchor": "middle", text: F.n(v, 0), cls: "sm", style: "fill:" + (kk.ink || "var(--bg)") }, g);
        acc += v;
      });
      if (!(i % skip)) F.s("text", { x: x(i) + x.bandwidth() / 2, y: h - pb + 14, "text-anchor": "middle", text: c.label || c }, svg);
    });
    return { svg, x, y };
  };

  /* linjer over kategoriar. series: [{name, vals, color, dash, w, end}] */
  F.lines = function (p, w, h, o) {
    const pl = o.pl == null ? 34 : o.pl, pr = o.pr || 6, pt = 12, pb = 24;
    const n = o.cats.length;
    const svg = F.svg(p, w, h, o.label);
    const x = d3.scalePoint().domain(d3.range(n)).range([pl + 6, w - pr - 6]);
    const all = [].concat.apply([], o.series.map((s) => s.vals.filter((v) => v != null)));
    const lo = o.min == null ? 0 : o.min, hi = o.max == null ? d3.max(all) * 1.1 : o.max;
    const y = d3.scaleLinear().domain([lo, hi]).range([h - pb, pt]);
    const fm = o.fmt || ((v) => F.n(v, o.d || 0));
    F.axisY(svg, y, pl, w - pl - pr, { n: o.n || 4, fmt: o.yfmt || fm });
    const skip = Math.ceil(46 / x.step());
    o.cats.forEach((c, i) => { if (!(i % skip)) F.s("text", { x: x(i), y: h - pb + 14, "text-anchor": "middle", text: o.short ? o.short(c) : c }, svg); });
    o.series.forEach((s) => {
      const pts = s.vals.map((v, i) => (v == null ? null : [x(i), y(v)]));
      const ln = d3.line().defined((d) => d).curve(d3.curveLinear);
      F.s("path", { d: ln(pts), fill: "none", stroke: s.color || "var(--fg)", "stroke-width": s.w || 2, "stroke-dasharray": s.dash || null, "stroke-linejoin": "round" }, svg);
      pts.forEach((q) => { if (q) F.s("circle", { cx: q[0], cy: q[1], r: s.r || 3, fill: s.hollow ? "var(--bg)" : (s.color || "var(--fg)"), stroke: s.color || "var(--fg)", "stroke-width": 1.5 }, svg); });
    });
    const ends = o.series.map((s, i) => { let k = s.vals.length - 1; while (k > 0 && s.vals[k] == null) k--; return { y: y(s.vals[k]) + 4, i, k }; });
    const ny = F.nudge(ends, 13, pt + 6, h - pb - 2);
    if (o.labels === true) o.series.forEach((s, i) => {
      const e = ends[i];
      if (s.lab) { /* eigen plassering: {i: punkt, dx, dy, a: anker} */
        F.s("text", { x: x(s.lab.i) + (s.lab.dx || 0), y: y(s.vals[s.lab.i]) + (s.lab.dy || 0), "text-anchor": s.lab.a || "middle", text: s.name, cls: "sm halo", style: "fill:" + (s.color || "var(--fg)") }, svg);
        return;
      }
      F.s("text", { x: x(e.k) - 2, y: ny[i] - (o.above == null ? 9 : o.above), "text-anchor": "end", text: s.name, cls: "sm halo", style: "fill:" + (s.color || "var(--fg)") }, svg);
    });
    F.xhover(svg, { x0: pl, x1: w - pr, y0: pt, y1: h - pb }, n, (i) => x(i), (i) => o.cats[i] + "|" + o.series.map((s) => (s.vals[i] == null ? null : s.name + " " + fm(s.vals[i]))).filter(Boolean).join("|"));
    return { svg, x, y };
  };
})();
