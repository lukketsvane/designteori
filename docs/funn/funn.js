/* FUNN - kjerne: lasting, lat teikning, verktøyhint, hjelparar, felles radteikning. Berre vanleg JavaScript (d3 7.9.0 for skalaer). */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const F = (window.FUNN = { fig: {}, del: {}, st: {}, cache: {}, rendered: new Map(), land: ["DK", "FI", "IS", "NO", "SE"],
    landNamn: { DK: "Danmark", FI: "Finland", IS: "Island", NO: "Noreg", SE: "Sverige" } });

  /* ---------- tal og tekst ---------- */
  const nf = {};
  F.n = function (v, d) {
    d = d || 0;
    if (v == null || Number.isNaN(v)) return "";
    const k = "d" + d;
    nf[k] = nf[k] || new Intl.NumberFormat("nb-NO", { minimumFractionDigits: d, maximumFractionDigits: d });
    return nf[k].format(v).replace("−", "−");
  };
  F.p = (v, d) => F.n(v, d == null ? 1 : d) + " %";
  F.trunc = (s, n) => (s.length > n ? s.slice(0, Math.max(1, n - 1)).trimEnd() + "…" : s);
  /* bryt ein merkelapp over inntil to linjer (aldri avkorta midt i eit ord utan at tredje linje trengst) */
  F.wrap = function (t, n, maxl) {
    maxl = maxl || 2;
    if (t.length <= n) return [t];
    const out = []; let cur = "";
    t.split(" ").forEach((w) => { if (cur && (cur + " " + w).length > n) { out.push(cur); cur = w; } else cur = cur ? cur + " " + w : w; });
    out.push(cur);
    if (out.length > maxl) { const keep = out.slice(0, maxl - 1); keep.push(F.trunc(out.slice(maxl - 1).join(" "), n)); return keep; }
    return out;
  };
  F.ramp = function (p, from, to, lo, hi, txt) {
    const l = F.d("div", { cls: "leg" }, p);
    F.d("span", { text: lo + " " }, l);
    const i = F.d("i", null, l); i.style.cssText = "width:70px;height:10px;border-radius:2px;background:linear-gradient(90deg," + from + "," + to + ")";
    F.d("span", { text: hi + (txt ? "  " + txt : "") }, l);
    return l;
  };

  /* ---------- DOM ---------- */
  F.s = function (tag, a, p) {
    const e = document.createElementNS(NS, tag);
    if (a) for (const k in a) {
      const v = a[k];
      if (v == null || v === false) continue;
      if (k === "text") e.textContent = v;
      else if (k === "cls") e.setAttribute("class", v);
      else if (k === "tip") e.setAttribute("data-tip", v);
      else if ((k === "fill" || k === "stroke" || k === "opacity") && typeof v === "string" && v.indexOf("var(") === 0) e.style[k] = v;
      else e.setAttribute(k, v);
    }
    if (p) p.appendChild(e);
    return e;
  };
  F.d = function (tag, a, p) {
    const e = document.createElement(tag);
    if (a) for (const k in a) {
      const v = a[k];
      if (v == null || v === false) continue;
      if (k === "text") e.textContent = v;
      else if (k === "cls") e.className = v;
      else if (k === "tip") e.setAttribute("data-tip", v);
      else e.setAttribute(k, v);
    }
    if (p) p.appendChild(e);
    return e;
  };
  F.svg = (p, w, h, label) => F.s("svg", { width: w, height: h, viewBox: "0 0 " + w + " " + h, role: "img", "aria-label": label || "" }, p);
  F.css = (el, name) => getComputedStyle(el).getPropertyValue(name).trim();
  F.cc = (c) => (F.land.indexOf(c) >= 0 ? "var(--" + c + ")" : "var(--ANNA)");

  /* ---------- kontrollar ---------- */
  F.seg = function (p, opts, cur, cb, label) {
    const g = F.d("div", { cls: "seg", role: "group", "aria-label": label || "" }, p);
    opts.forEach((o) => {
      const b = F.d("button", { type: "button", text: o.t, "aria-pressed": String(o.k === cur) }, g);
      b.addEventListener("click", () => {
        if (b.getAttribute("aria-pressed") === "true") return;
        g.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", "false"));
        b.setAttribute("aria-pressed", "true");
        cb(o.k);
      });
    });
    return g;
  };
  F.legend = function (p, items) {
    const l = F.d("div", { cls: "leg" }, p);
    items.forEach((it) => {
      const s = F.d("span", null, l);
      const i = F.d("i", { cls: it.open ? "o" : "" }, s);
      if (it.ln) { i.style.cssText = "width:20px;height:0;border-radius:0;border-top:2.5px " + it.ln + " " + it.c + ";background:none"; }
      else { i.style.background = it.c; i.style.color = it.open && it.c === "transparent" ? "var(--dim)" : it.c; }
      if (it.r) i.style.borderRadius = "50%";
      s.appendChild(document.createTextNode(it.t));
    });
    return l;
  };

  /* ---------- verktøyhint ---------- */
  const tip = document.createElement("div");
  tip.id = "tip";
  tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);
  let cur = null, tipTouch = false;
  function setTip(txt) {
    tip.textContent = "";
    String(txt).split("|").forEach((p, i) => { const e = document.createElement(i ? "span" : "b"); e.textContent = p; tip.appendChild(e); });
  }
  function place(x, y, touch) {
    const r = tip.getBoundingClientRect();
    let tx = x + 14, ty = y + 16;
    if (touch) ty = y - r.height - 24;
    if (tx + r.width > innerWidth - 8) tx = innerWidth - 8 - r.width;
    if (tx < 8) tx = 8;
    if (ty + r.height > innerHeight - 8) ty = y - r.height - 12;
    if (ty < 8) ty = 8;
    tip.style.left = tx + "px"; tip.style.top = ty + "px";
  }
  F.tipAt = function (x, y, txt, touch) { setTip(txt); tip.classList.add("on"); place(x, y, touch); cur = tip; };
  F.tipHide = function () { tip.classList.remove("on"); cur = null; };
  function onPoint(e) {
    if (e.target.closest && e.target.closest("#tip")) return;
    const t = e.target.closest ? e.target.closest("[data-tip]") : null;
    if (t) { cur = t; tipTouch = e.pointerType === "touch"; setTip(t.getAttribute("data-tip")); tip.classList.add("on"); place(e.clientX, e.clientY, tipTouch); }
    else if (e.type !== "pointermove" && !e.target.closest("canvas[data-tipc]")) F.tipHide();
  }
  document.addEventListener("pointerover", onPoint, { passive: true });
  document.addEventListener("pointerdown", onPoint, { passive: true });
  document.addEventListener("pointermove", (e) => {
    if (cur && cur !== tip && e.pointerType !== "touch" && tip.classList.contains("on")) {
      const t = e.target.closest ? e.target.closest("[data-tip]") : null;
      if (t === cur) place(e.clientX, e.clientY, false);
    }
  }, { passive: true });
  document.addEventListener("scroll", () => { if (tipTouch) F.tipHide(); }, { passive: true });
  document.documentElement.addEventListener("pointerleave", F.tipHide);

  /* ---------- aksar ---------- */
  F.axisX = function (g, x, y0, h, o) {
    o = o || {};
    const ticks = o.values || x.ticks(o.n || Math.max(2, Math.floor(Math.abs(x.range()[1] - x.range()[0]) / 80)));
    const gr = F.s("g", { cls: "grid" }, g);
    const ax = F.s("g", null, g);
    ticks.forEach((t) => {
      const px = x(t);
      if (o.grid !== false) F.s("line", { x1: px, x2: px, y1: y0 - h, y2: y0, stroke: "var(--hair)" }, gr);
      F.s("text", { x: px, y: y0 + 14, "text-anchor": "middle", text: o.fmt ? o.fmt(t) : F.n(t) }, ax);
    });
  };
  F.axisY = function (g, y, x0, w, o) {
    o = o || {};
    const ticks = o.values || y.ticks(o.n || 4);
    const gr = F.s("g", { cls: "grid" }, g);
    ticks.forEach((t) => {
      const py = y(t);
      F.s("line", { x1: x0, x2: x0 + w, y1: py, y2: py, stroke: "var(--hair)" }, gr);
      F.s("text", { x: x0 - 6, y: py + 3.5, "text-anchor": "end", text: o.fmt ? o.fmt(t) : F.n(t) }, g);
    });
  };

  /* ---------- felles radteikning: knott, punkt med intervall, spenn, stolpe ---------- */
  F.rows = function (p, ctx, o) {
    const W = ctx.w, pl = 10, pr = 10;
    const x = d3.scaleLinear().domain([o.min == null ? 0 : o.min, o.max]).range([pl, W - pr]).clamp(true);
    const rowH = o.rowH || 38, gH = o.gH || 30, top = 20, lh = 13;
    const vw = o.valW || 7.3;
    const fm = o.fmt || ((v) => F.n(v, o.d || 0));
    /* førstegangsrunde: merkelappar, verditekst og rad-høgder */
    let last = null, H = top + 6;
    const info = o.rows.map((r) => {
      const vtxt = r.vtxt != null ? r.vtxt : (r.v != null ? fm(r.v) : (r.lo != null ? fm(r.lo) + "–" + fm(r.hi) : ""));
      const maxc = Math.max(8, Math.floor((W - vtxt.length * vw - 14) / 7.0));
      const lines = r.nowrap ? [F.trunc(r.label, maxc)] : F.wrap(r.label, maxc, 2);
      const h = rowH + (lines.length > 1 ? lh : 0);
      let gh = 0;
      if (r.group && r.group !== last) { last = r.group; gh = gH; }
      H += h + gh;
      return { vtxt, lines, h, gh };
    });
    const svg = F.svg(p, W, H, o.label);
    const ticks = o.ticks || x.ticks(Math.max(2, Math.floor(W / 90)));
    const gr = F.s("g", { cls: "grid" }, svg);
    ticks.forEach((t) => {
      F.s("line", { x1: x(t), x2: x(t), y1: 12, y2: H - 4, stroke: "var(--hair)" }, gr);
      F.s("text", { x: Math.min(Math.max(x(t), 8), W - 8), y: 8, "text-anchor": x(t) < 8 ? "start" : (x(t) > W - 8 ? "end" : "middle"), text: (o.tfmt || fm)(t) }, svg);
    });
    (o.refs || []).forEach((rf) => {
      F.s("line", { x1: x(rf.v), x2: x(rf.v), y1: 12, y2: H - 4, cls: "ref" }, svg);
      if (rf.label) F.s("text", { x: x(rf.v) + (rf.left ? -4 : 4), y: H - 8, "text-anchor": rf.left ? "end" : "start", text: rf.label, cls: "sm halo" }, svg);
    });
    let y = top; last = null;
    o.rows.forEach((r, ri) => {
      const inf = info[ri];
      if (r.group && r.group !== last) {
        last = r.group;
        F.s("text", { x: 0, y: y + 16, text: r.group.toUpperCase(), cls: "sm", "letter-spacing": ".06em" }, svg);
        y += gH;
      }
      const vtxt = inf.vtxt, ex = inf.lines.length > 1 ? lh : 0;
      const g = F.s("g", { cls: "mk fd", tip: r.tip || (r.label + "|" + (r.tiptxt || vtxt)), opacity: r.fade ? 0.55 : null }, svg);
      F.s("rect", { x: 0, y: y, width: W, height: inf.h - 2, fill: "transparent" }, g);
      inf.lines.forEach((t, k) => F.s("text", { x: 0, y: y + 12 + k * lh, text: t, cls: "fg", style: "font-size:12px" }, g));
      F.s("text", { x: W, y: y + 12, "text-anchor": "end", text: vtxt, cls: r.vcls || "b" }, g);
      const ty = y + 25 + ex, col = r.color || "var(--fg)";
      F.s("line", { x1: pl, x2: W - pr, y1: ty, y2: ty, stroke: "var(--hair)" }, g);
      const mk = r.mark || o.mark || "knob";
      if (mk === "knob") {
        F.s("line", { x1: x(x.domain()[0]), x2: x(r.v), y1: ty, y2: ty, stroke: col, "stroke-width": 3, cls: "gx" }, g);
        F.s("circle", { cx: x(r.v), cy: ty, r: r.r || 5.5, fill: col, cls: "fd" }, g);
      } else if (mk === "dot") {
        if (r.lo != null) {
          F.s("line", { x1: x(r.lo), x2: x(r.hi), y1: ty, y2: ty, stroke: col, "stroke-width": 2.5, "stroke-dasharray": r.dashci ? "3 2" : null, cls: "gx" }, g);
          F.s("line", { x1: x(r.lo), x2: x(r.lo), y1: ty - 4, y2: ty + 4, stroke: col, "stroke-width": 1.5 }, g);
          F.s("line", { x1: x(r.hi), x2: x(r.hi), y1: ty - 4, y2: ty + 4, stroke: col, "stroke-width": 1.5 }, g);
        }
        F.s("circle", { cx: x(r.v), cy: ty, r: r.r || 5.5, fill: r.open ? "var(--bg)" : col, stroke: col, "stroke-width": 2, cls: "fd" }, g);
      } else if (mk === "range") {
        F.s("rect", { x: x(r.lo), y: ty - 4.5, width: Math.max(2, x(r.hi) - x(r.lo)), height: 9, rx: 2, fill: col, cls: "gx" }, g);
        if (r.v != null) F.s("circle", { cx: x(r.v), cy: ty, r: 3.2, fill: "var(--bg)", stroke: col, "stroke-width": 1.5 }, g);
      } else if (mk === "bar") {
        F.s("rect", { x: x(x.domain()[0]), y: ty - 4.5, width: Math.max(1.5, x(r.v) - x(x.domain()[0])), height: 9, rx: 1.5, fill: col, cls: "gx" }, g);
      }
      if (r.dots) {
        const vs = r.dots.map((q) => q.v);
        if (r.dots.length > 1 && r.link !== false) F.s("line", { x1: x(Math.min.apply(null, vs)), x2: x(Math.max.apply(null, vs)), y1: ty, y2: ty, stroke: r.linkc || "var(--dim)", "stroke-width": 2, cls: "gx" }, g);
        r.dots.forEach((q) => {
          if (q.tick) F.s("line", { x1: x(q.v), x2: x(q.v), y1: ty - 8, y2: ty + 8, stroke: q.color || "var(--fg)", "stroke-width": 2 }, g);
          else F.s("circle", { cx: x(q.v), cy: ty, r: q.r || 5.5, fill: q.hollow ? "var(--bg)" : (q.color || "var(--fg)"), stroke: q.color || "var(--fg)", "stroke-width": 2, cls: "fd" }, g);
        });
      }
      y += inf.h;
    });
    return { svg, x, H };
  };

  /* ---------- paneler, hover langs x, nudging av merkelappar, små linjer ---------- */
  F.pans = function (p, n, cls, titles) {
    const g = F.d("div", { cls: "pans " + (cls || "") }, p);
    const out = [];
    for (let i = 0; i < n; i++) {
      const el = F.d("div", { cls: "pan" }, g);
      if (titles && titles[i]) F.d("h4", { text: titles[i] }, el);
      out.push(el);
    }
    out.forEach((el) => { el.w = Math.floor(el.getBoundingClientRect().width); });
    return out;
  };
  F.nudge = function (ys, gap, lo, hi) {
    /* ys: [{y, i}], returnerer ny y utan overlapp */
    const a = ys.map((o, i) => ({ y: o.y, i })).sort((p, q) => p.y - q.y);
    for (let k = 1; k < a.length; k++) if (a[k].y < a[k - 1].y + gap) a[k].y = a[k - 1].y + gap;
    const over = a.length ? a[a.length - 1].y - hi : 0;
    if (over > 0) { a[a.length - 1].y = hi; for (let k = a.length - 2; k >= 0; k--) if (a[k].y > a[k + 1].y - gap) a[k].y = a[k + 1].y - gap; }
    if (a.length && a[0].y < lo) { a[0].y = lo; for (let k = 1; k < a.length; k++) if (a[k].y < a[k - 1].y + gap) a[k].y = a[k - 1].y + gap; }
    const out = [];
    a.forEach((o) => { out[o.i] = o.y; });
    return out;
  };
  F.xhover = function (svg, box, n, xAt, txt) {
    const line = F.s("line", { y1: box.y0, y2: box.y1, stroke: "var(--fg)", "stroke-width": 1, opacity: 0, "pointer-events": "none" }, svg);
    const r = F.s("rect", { x: box.x0, y: box.y0, width: box.x1 - box.x0, height: box.y1 - box.y0, fill: "transparent", style: "touch-action:pan-y" }, svg);
    const at = (e) => {
      const b = r.getBoundingClientRect();
      const px = e.clientX - b.left + box.x0;
      let best = 0, bd = 1e9;
      for (let i = 0; i < n; i++) { const d = Math.abs(xAt(i) - px); if (d < bd) { bd = d; best = i; } }
      line.setAttribute("x1", xAt(best)); line.setAttribute("x2", xAt(best)); line.style.opacity = 0.55;
      F.tipAt(e.clientX, e.clientY, txt(best), e.pointerType === "touch");
    };
    r.addEventListener("pointermove", at);
    r.addEventListener("pointerdown", at);
    r.addEventListener("pointerleave", () => { line.style.opacity = 0; F.tipHide(); });
    return r;
  };
  /* rader med små linjer eller søyler: {label, vals, flag, vtxt} */
  F.spark = function (p, ctx, o) {
    const W = ctx.w, rowH = o.rowH || 30, gH = 26, top = 4;
    let H = top + o.rows.length * rowH, last = null, gs = 0;
    o.rows.forEach((r) => { if (r.group && r.group !== last) { gs++; last = r.group; } });
    H += gs * gH;
    const svg = F.svg(p, W, H, o.label);
    const nl = Math.min(Math.floor(W * 0.5), o.labelW || 190), vw = o.vw || 92;
    const x0 = nl + 6, x1 = W - vw;
    const vals = [].concat.apply([], o.rows.map((r) => r.vals));
    const mx = o.max || d3.max(vals);
    const m = o.vals ? o.vals : null;
    const n = o.rows[0].vals.length;
    let y = top; last = null;
    o.rows.forEach((r) => {
      if (r.group && r.group !== last) { last = r.group; F.s("text", { x: 0, y: y + 17, text: r.group.toUpperCase(), cls: "sm", "letter-spacing": ".06em" }, svg); y += gH; }
      const g = F.s("g", { cls: "mk fd", tip: r.tip || (r.label + "|" + r.vals.map((v, i) => (o.periods ? o.periods[i] + ": " : "") + F.n(v, 1) + " %").join("  ")) }, svg);
      F.s("rect", { x: 0, y: y, width: W, height: rowH - 2, fill: "transparent" }, g);
      const bx = r.badge ? 26 : 0;
      if (r.badge) { F.s("rect", { x: 0, y: y + rowH / 2 - 10, width: 20, height: 20, rx: 4, fill: "none", stroke: "var(--dim)", "stroke-width": 1.5 }, g); F.s("text", { x: 10, y: y + rowH / 2 + 4, "text-anchor": "middle", text: r.badge, cls: "fg", style: "font-weight:500;font-size:11.5px" }, g); }
      const ll = F.wrap(r.label, Math.floor((nl - bx) / 7.0), 2);
      ll.forEach((t, k) => F.s("text", { x: bx, y: y + rowH / 2 + 3 + (k - (ll.length - 1) / 2) * 13, text: t, cls: r.flag ? "b" : "fg", style: "font-size:12px" }, g));
      const sx = d3.scaleLinear().domain([0, n - 1]).range([x0 + 4, x1 - 4]);
      const sy = d3.scaleLinear().domain([0, o.perRow ? d3.max(r.vals) * 1.05 || 1 : mx]).range([y + rowH - 5, y + 4]);
      const col = r.flag ? "var(--fg)" : "var(--dim)";
      if (o.kind === "bars") {
        const bw = Math.max(3, (x1 - x0) / n - 4);
        r.vals.forEach((v, i) => F.s("rect", { x: sx(i) - bw / 2, y: sy(v), width: bw, height: Math.max(1, y + rowH - 5 - sy(v)), fill: col, opacity: r.flag ? 1 : .6, cls: "gy" }, g));
      } else {
        F.s("path", { d: d3.line()(r.vals.map((v, i) => [sx(i), sy(v)])), fill: "none", stroke: col, "stroke-width": r.flag ? 2 : 1.4, "stroke-dasharray": r.dash ? "4 3" : null }, g);
        r.vals.forEach((v, i) => { if (i === 0 || i === n - 1) F.s("circle", { cx: sx(i), cy: sy(v), r: 2.8, fill: col }, g); });
      }
      F.s("text", { x: W, y: y + rowH / 2 + 3, "text-anchor": "end", text: r.vtxt || (F.n(r.vals[0], 1) + " → " + F.n(r.vals[n - 1], 1)), cls: r.flag ? "b" : "" }, g);
      F.s("line", { x1: 0, x2: W, y1: y + rowH - 1, y2: y + rowH - 1, stroke: "var(--hair)" }, g);
      y += rowH;
    });
    return { svg, H };
  };

  /* ---------- lasting ---------- */
  function load(file, opt) {
    if (!F.cache[file]) F.cache[file] = fetch(file, opt || { cache: "force-cache" }).then((r) => { if (!r.ok) throw new Error(file + " " + r.status); return r.json(); });
    return F.cache[file];
  }
  /* manifestet hentast alltid på nytt; datafilene får sjekksummen i adressa og kan då bufrast for godt */
  F.manifest = () => load("../data/meta/manifest.json", { cache: "no-cache" });
  F.load = (f) => (f === "manifest.json" ? F.manifest() : F.manifest().then((m) => load("../data/meta/" + f + "?v=" + ((m.filer[f] || {}).sha256 || "").slice(0, 12))));
  F.figData = async function (id) {
    const m = await F.manifest();
    const e = m.figurar.find((f) => f.id === id);
    const d = await F.load(e.fil);
    return { d: d.figurar[id], m: e };
  };

  /* ---------- lat teikning ---------- */
  /* venta høgd per figur (mobil, brei), målt frå ferdig teikna figurar: held sida stabil medan ho blir teikna */
  F.HOYDE = {f01: [1531, 1097], f02: [1208, 956], f03: [1005, 839], f04: [686, 633], f05: [2811, 1332], f06: [791, 883], f07: [1400, 519], f08: [903, 1018], f09: [1127, 577], f10: [757, 665], f11: [1198, 778], f12: [739, 383], f13: [1270, 626], f14: [771, 660], f15: [858, 766], f16: [1789, 1142], f17: [1246, 747], f18: [6830, 4203]};
  function expH(id) {
    const e = F.HOYDE[id]; if (!e) return 0;
    return innerWidth < 700 ? e[0] : e[1];
  }
  async function render(el, first) {
    const id = el.dataset.fig, mount = el.querySelector(".mount");
    const fn = F.fig[id];
    if (!fn) return;
    const w = Math.floor(mount.getBoundingClientRect().width);
    if (!w) return;
    try {
      const { d, m } = await F.figData(id);
      /* ei figur med fleire delar har ei nemnarlinje under kvar del (teikna av samansettinga), ikkje under heile figuren */
      const nem = el.querySelector(".nem");
      if (nem && (m.delar || []).length > 1) nem.hidden = true;
      else if (nem && !nem.textContent) nem.textContent = m.nemnar;
      const st = F.st[id] || (F.st[id] = {});
      const ctx = { id, w, mob: w < 520, st, el: mount, fig: el, m, rerender: () => render(el), dark: matchMedia("(prefers-color-scheme: dark)").matches || document.documentElement.dataset.theme === "dark" };
      const hold = mount.offsetHeight;
      mount.style.minHeight = hold + "px";
      mount.textContent = "";
      mount.classList.remove("vent");
      await fn(mount, d, ctx);
      mount.style.minHeight = "";
      mount.dataset.w = w;
      F.rendered.set(id, el);
      spy();
    } catch (e) {
      console.error(id, e);
      mount.textContent = "";
      const p = document.createElement("p");
      p.className = "tx"; p.textContent = "Biletet kunne ikkje teiknast.";
      mount.appendChild(p);
    }
  }
  F.render = render;

  let links = [], secs = [];
  function spy() {
    const line = Math.min(innerHeight * 0.35, 260);
    let cur = null;
    secs.forEach((sc) => { if (sc.getBoundingClientRect().top <= line) cur = sc; });
    links.forEach((a) => {
      if (cur && a.getAttribute("href") === "#" + cur.id) {
        if (a.getAttribute("aria-current") !== "true") { a.setAttribute("aria-current", "true"); a.parentNode.scrollTo({ left: a.offsetLeft - 40, behavior: "smooth" }); }
      } else a.removeAttribute("aria-current");
    });
  }

  function init() {
    const els = Array.from(document.querySelectorAll("[data-fig]"));
    els.forEach((e) => {
      const mt = e.querySelector(".mount");
      mt.classList.add("vent");
      const h = expH(e.dataset.fig);
      if (h) mt.style.minHeight = h + "px";
    });
    /* hent manifest og alle seksjonsfiler straks sida er i ro, så teikninga ikkje ventar på nettet */
    const pre = () => F.manifest().then((m) => Object.keys(m.filer).forEach((f) => F.load(f))).catch(() => {});
    if (window.requestIdleCallback) requestIdleCallback(pre, { timeout: 1200 }); else setTimeout(pre, 300);
    F.manifest().catch(() => {});
    /* alle figurar blir teikna i rekkjefølgje så snart sida er i ro (ei om gongen), og dei som ligg nær skjermen først.
       Ein figur som ikkje er teikna held plassen sin med målt høgd, så sida skal ikkje hoppe. */
    const state = new Map();
    const draw1 = (el) => {
      if (!state.has(el)) state.set(el, render(el, true).then(() => watch(el)));
      return state.get(el);
    };
    F.ensure = (target) => {
      /* teikn alle figurar frå toppen og ned til og med målet, så ein hoppar til ein ferdig side */
      const upto = els.indexOf(target.closest ? (target.closest("[data-fig]") || target) : target);
      const need = upto >= 0 ? els.slice(0, upto + 1) : els.filter((e) => target.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_PRECEDING);
      return Promise.all(need.map(draw1));
    };
    const io = new IntersectionObserver((es) => { es.forEach((en) => { if (en.isIntersecting) { io.unobserve(en.target); draw1(en.target); } }); }, { rootMargin: "900px 0px" });
    els.forEach((e) => io.observe(e));
    const rest = () => { const nxt = els.find((e) => !state.has(e)); if (!nxt) return; draw1(nxt).then(() => setTimeout(rest, 30)); };
    if (window.requestIdleCallback) requestIdleCallback(rest, { timeout: 1500 }); else setTimeout(rest, 400);
    /* hopp frå meny, figurlenkjer og rutenett: teikn først, rull deretter, så ein landar nøyaktig */
    const jump = async (hash, push) => {
      let t = null; try { t = hash.length > 1 ? document.getElementById(decodeURIComponent(hash.slice(1))) : null; } catch (e) { t = null; }
      if (!t) return false;
      await F.ensure(t);
      t.dispatchEvent(new CustomEvent("opna"));
      t.scrollIntoView({ block: "start", behavior: "instant" });
      if (push) history.pushState(null, "", hash);
      if (t.classList.contains("sp")) { t.classList.remove("fokus"); void t.offsetWidth; t.classList.add("fokus"); }
      spy();
      return true;
    };
    F.jump = jump;
    document.addEventListener("click", (e) => {
      const a = e.target.closest && e.target.closest("a[href^='#']");
      if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || a.getAttribute("href") === "#") return;
      const h = a.getAttribute("href");
      if (!document.getElementById(decodeURIComponent(h.slice(1)))) return;
      e.preventDefault();
      jump(h, true);
    });
    addEventListener("popstate", () => { if (location.hash) jump(location.hash, false); });
    if (location.hash) setTimeout(() => jump(location.hash, false), 0);

    function watch(el) {
      const mount = el.querySelector(".mount");
      let t = 0;
      new ResizeObserver(() => {
        clearTimeout(t);
        t = setTimeout(() => { const w = Math.floor(mount.getBoundingClientRect().width); if (w && Math.abs(w - (+mount.dataset.w || 0)) > 6) render(el); }, 180);
      }).observe(mount);
    }
    const redo = () => F.rendered.forEach((el) => render(el));
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redo);
    new MutationObserver(redo).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    /* seksjonsmeny: les posisjonen ved kvar rulling og etter kvar teikning, så han følgjer med etter hopp */
    links = Array.from(document.querySelectorAll(".topp a"));
    secs = Array.from(document.querySelectorAll("[data-sek]"));
    addEventListener("scroll", spy, { passive: true });
    addEventListener("resize", spy);
    spy();
    hero();
    heroTal();
  }

  /* hero: tal på funn kjem frå manifestet, så sida og dataa seier det same */
  async function heroTal() {
    const li = document.querySelector("[data-funn]");
    if (!li) return;
    try {
      const f = (await F.manifest()).funn;
      if (!f) return;
      li.querySelector("b").textContent = F.n(f.kontrollerte);
      li.querySelector("span").textContent = "kontrollerte funn i to rundar (" + F.n(f.stadfesta) + " stadfesta, " + F.n(f.retta) + " retta); " + F.n(f.teikna) + " av dei er teikna, pluss " + F.n(f.sporsmal) + " spørsmål";
    } catch (e) { /* den statiske teksten står att */ }
  }

  /* ---------- inngangsbilete: kartet som bakgrunn ---------- */
  /* klyngefargar: ein farge har éi tyding på sida. Landa har blå, rosa, gul, oransje og grøn; laga har indigo og karmin.
     Klyngene bruker berre dei fargane som er att (gulgrøn, grøn, fiolett, purpur) pluss kvitt, sand og stålgrått,
     og har alltid nummer eller bokstav ved sida av. */
  const PAL = ["#b8ec4a", "#a974ff", "#8de35f", "#f2f2f2", "#d46bff", "#c8b98f", "#9fb2c4", "#6fdc8a"];
  F.PAL = PAL;
  F.GPAL = ["#b8ec4a", "#a974ff", "#8de35f", "#f2f2f2", "#d46bff", "#c8b98f", "#9fb2c4"];
  async function hero() {
    const cv = document.getElementById("hero-kart");
    if (!cv) return;
    let d;
    try { d = (await F.figData("f11")).d.d18; } catch (e) { return; }
    const draw = () => {
      const r = cv.parentNode.getBoundingClientRect();
      const dpr = Math.min(devicePixelRatio || 1, 2);
      cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr);
      const c = cv.getContext("2d");
      c.scale(dpr, dpr);
      c.fillStyle = "#000"; c.fillRect(0, 0, r.width, r.height);
      const side = Math.max(r.height * 1.12, Math.min(r.width, r.height * 1.6));
      const ox = r.width > 760 ? r.width - side * 0.95 : (r.width - side) / 2, oy = (r.height - side) / 2;
      c.globalCompositeOperation = "lighter";
      const kl = d.klynger.map((k) => PAL[k.farge]);
      for (let i = 0; i < d.x.length; i++) {
        c.fillStyle = kl[d.k[i]];
        c.globalAlpha = 0.78;
        c.beginPath();
        c.arc(ox + (d.x[i] / d.skala) * side, oy + (d.y[i] / d.skala) * side, r.width < 600 ? 1.35 : 1.8, 0, 6.283);
        c.fill();
      }
    };
    draw();
    let t = 0, lw = innerWidth;
    addEventListener("resize", () => { if (innerWidth === lw) return; lw = innerWidth; clearTimeout(t); t = setTimeout(draw, 200); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
