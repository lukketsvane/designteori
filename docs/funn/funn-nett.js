/* FUNN - tette bilete på svart: nettverk (f09), samsiteringsnett (f13) og kartet (f18). Canvas, med nærmaste-prikk for verktøyhint. */
(function () {
  "use strict";
  const F = window.FUNN, n0 = F.n;
  const TAU = Math.PI * 2;

  function canvas(host, w, h, label) {
    const wrap = F.d("div", { style: "position:relative;width:" + w + "px;height:" + h + "px" }, host);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const mk = (z) => { const cv = F.d("canvas", { style: "position:absolute;left:0;top:0;width:" + w + "px;height:" + h + "px;z-index:" + z }, wrap); cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); const c = cv.getContext("2d"); c.scale(dpr, dpr); return { cv, c }; };
    const base = mk(1), top = mk(2);
    top.cv.setAttribute("data-tipc", "1");
    top.cv.setAttribute("role", "img");
    top.cv.setAttribute("aria-label", label || "Nettverksbilete");
    top.cv.style.touchAction = "pan-y";
    return { wrap, base, top, w, h };
  }
  /* finn nærmaste punkt med kvadtre og koble til verktøyhint */
  function pick(cv, pts, rad, onHit, onMiss) {
    const qt = d3.quadtree().x((p) => p.px).y((p) => p.py).addAll(pts);
    let lastIdx = -1;
    const at = (e) => {
      const b = cv.getBoundingClientRect();
      const x = e.clientX - b.left, y = e.clientY - b.top;
      const p = qt.find(x, y, rad);
      if (p) { if (p !== lastIdx) { lastIdx = p; } onHit(p, e); } else if (lastIdx) { lastIdx = null; onMiss(e); }
    };
    cv.addEventListener("pointermove", (e) => { if (e.pointerType !== "touch") at(e); });
    cv.addEventListener("pointerdown", at);
    cv.addEventListener("pointerleave", () => { lastIdx = null; onMiss(); });
  }

  /* ---------- f09: tre nettverk ---------- */
  F.fig.f09 = function (m, d, ctx) {
    const mob = ctx.w < 700;
    const titles = ["Forfattarar", "Institusjonar", "Land"];
    const [A, B, C] = F.pans(m, 3, "p3", titles);
    const col = (n) => F.css(m, n);
    const white = "#f4f4f4", grey = "#7a7a7a";
    const names = { GB: "Storbritannia", US: "USA", NL: "Nederland", DK: "Danmark", FI: "Finland", IS: "Island", NO: "Noreg", SE: "Sverige" };

    function net(host, spec) {
      const w = host.w, h = w;
      const cvs = canvas(host, w, h, spec.label);
      const pad = 8, sc = (v) => pad + (v / 10000) * (w - 2 * pad);
      const N = spec.x.length, pts = new Array(N);
      for (let i = 0; i < N; i++) pts[i] = { i, px: sc(spec.x[i]), py: sc(spec.y[i]) };
      const c = cvs.base.c;
      c.lineCap = "round";
      /* kantar */
      c.beginPath();
      const k = spec.kant, three = spec.three;
      const stp = three ? 3 : 2;
      for (let e = 0; e < k.length; e += stp) { const a = pts[k[e]], b = pts[k[e + 1]]; c.moveTo(a.px, a.py); c.lineTo(b.px, b.py); }
      c.strokeStyle = "rgba(255,255,255," + spec.ea + ")"; c.lineWidth = spec.ew; c.stroke();
      if (spec.heavy) {
        spec.heavy.forEach((q) => { c.beginPath(); c.moveTo(pts[q[0]].px, pts[q[0]].py); c.lineTo(pts[q[1]].px, pts[q[1]].py); c.strokeStyle = "rgba(255,255,255," + q[3] + ")"; c.lineWidth = q[2]; c.stroke(); });
      }
      /* prikkar */
      for (let i = 0; i < N; i++) { c.fillStyle = spec.col(i); c.globalAlpha = spec.alpha ? spec.alpha(i) : 1; c.beginPath(); c.arc(pts[i].px, pts[i].py, spec.r(i), 0, TAU); c.fill(); }
      c.globalAlpha = 1;
      if (spec.labels) spec.labels.forEach((q) => { c.font = "500 11px 'IBM Plex Mono', monospace"; c.textAlign = "center"; c.lineWidth = 3.5; c.strokeStyle = "#000"; c.strokeText(q.t, pts[q.i].px, pts[q.i].py - spec.r(q.i) - 4); c.fillStyle = "#fff"; c.fillText(q.t, pts[q.i].px, pts[q.i].py - spec.r(q.i) - 4); });
      const t = cvs.top.c;
      pick(cvs.top.cv, pts, 14, (p, e) => {
        t.clearRect(0, 0, w, h);
        t.beginPath(); t.arc(p.px, p.py, spec.r(p.i) + 3.5, 0, TAU); t.strokeStyle = "#fff"; t.lineWidth = 1.5; t.stroke();
        F.tipAt(e.clientX, e.clientY, spec.tip(p.i), e.pointerType === "touch");
      }, () => { t.clearRect(0, 0, w, h); F.tipHide(); });
    }

    /* A: forfattarar, største komponent lyst */
    const fa = d.forfattar, nF = fa.x.length;
    const par = new Int32Array(nF); for (let i = 0; i < nF; i++) par[i] = i;
    const find = (x) => { while (par[x] !== x) { par[x] = par[par[x]]; x = par[x]; } return x; };
    for (let e = 0; e < fa.kant.length; e += 2) { const a = find(fa.kant[e]), b = find(fa.kant[e + 1]); if (a !== b) par[a] = b; }
    const size = new Map(); for (let i = 0; i < nF; i++) { const r = find(i); size.set(r, (size.get(r) || 0) + 1); }
    let big = -1, bs = 0; size.forEach((v, r) => { if (v > bs) { bs = v; big = r; } });
    net(A, { label: "Medforfattarnettverk for 6 033 forfattarar", x: fa.x, y: fa.y, kant: fa.kant, ea: mob ? 0.11 : 0.12, ew: 0.5, col: (i) => (find(i) === big ? white : grey), r: (i) => 0.8 + Math.min(fa.n[i], 6) * 0.17, alpha: (i) => (find(i) === big ? 0.95 : 0.8),
      tip: (i) => "Forfattar|" + fa.n[i] + (fa.n[i] === 1 ? " verk" : " verk") + (fa.n[i] >= 9 ? " eller fleire" : "") + " i laget|" + (find(i) === big ? "i største komponent" : "utanfor største komponent") });
    F.d("p", { cls: "sm" }, A).append(Object.assign(document.createElement("b"), { textContent: F.p(d.stor_pct.forfattar, 1) }), " i største komponent, mot " + F.p(d.null_forfattar_pct, 1) + " i nullmodellen. " + n0(fa.komponentar) + " komponentar, " + n0(fa.aleine) + " aleine. " + F.p(fa.par_fleire_pct, 1) + " av medforfattarpar skriv saman fleire gonger (nullmodell " + F.p(d.par_null_pct, 1) + ").");

    /* B: institusjonar */
    const ins = d.institusjon, lc = (i) => (ins.land[i] < 5 ? F.css(m, "--" + F.land[ins.land[i]]) : grey);
    net(B, { label: "Nettverk av 1 090 institusjonar", x: ins.x, y: ins.y, kant: ins.kant, ea: 0.07, ew: 0.45, col: lc, r: (i) => 1 + Math.sqrt(ins.n[i]) * 0.32, alpha: () => 0.9,
      tip: (i) => "Institusjon|" + ins.n[i] + (ins.n[i] >= 99 ? " eller fleire" : "") + " verk|" + (ins.land[i] < 5 ? F.landNamn[F.land[ins.land[i]]] : "anna land") });
    F.d("p", { cls: "sm" }, B).append(Object.assign(document.createElement("b"), { textContent: F.p(d.stor_pct.institusjon, 1) }), " i største komponent. " + n0(ins.noder) + " institusjonar. Fargen er landet.");

    /* C: land */
    const ld = d.land, nL = ld.k.length;
    const idx = {}; ld.k.forEach((k, i) => (idx[k] = i));
    const heavy = [], ed = [];
    for (let e = 0; e < ld.kant.length; e++) { const q = ld.kant[e]; ed.push(q[0], q[1], q[2]); }
    const lcol = (i) => (F.land.indexOf(ld.k[i]) >= 0 ? F.css(m, "--" + ld.k[i]) : grey);
    const top = ld.n.map((v, i) => [v, i]).sort((a, b) => b[0] - a[0]).slice(0, 9).map((q) => q[1]);
    const labs = []; const seen = new Set(top.concat(F.land.map((k) => idx[k]).filter((v) => v != null)));
    seen.forEach((i) => labs.push({ i, t: ld.k[i] }));
    const wC = C.w, cvC = canvas(C, wC, wC, "Nettverk av 86 land");
    (function () {
      const w = wC, pad = 14, sc = (v) => pad + (v / 10000) * (w - 2 * pad), c = cvC.base.c;
      const pts = ld.k.map((k, i) => ({ i, px: sc(ld.x[i]), py: sc(ld.y[i]) }));
      ld.kant.forEach((q) => { c.beginPath(); c.moveTo(pts[q[0]].px, pts[q[0]].py); c.lineTo(pts[q[1]].px, pts[q[1]].py); c.strokeStyle = "rgba(255,255,255," + Math.min(0.5, 0.05 + Math.log10(q[2] + 1) * 0.12) + ")"; c.lineWidth = 0.4 + Math.log10(q[2] + 1) * 0.9; c.stroke(); });
      const rr = (i) => 1.6 + Math.sqrt(ld.n[i]) * 0.24;
      pts.forEach((p) => { c.fillStyle = lcol(p.i); c.beginPath(); c.arc(p.px, p.py, rr(p.i), 0, TAU); c.fill(); });
      const lb = [];
      labs.forEach((q) => { const p = pts[q.i]; const wd = q.t.length * 7 + 4; const box = [p.px - wd / 2, p.py - rr(q.i) - 16, wd, 13]; if (lb.some((b) => box[0] < b[0] + b[2] && box[0] + box[2] > b[0] && box[1] < b[1] + b[3] && box[1] + box[3] > b[1])) return; lb.push(box); c.font = "500 11px 'IBM Plex Mono', monospace"; c.textAlign = "center"; c.lineWidth = 3.5; c.strokeStyle = "#000"; c.strokeText(q.t, p.px, p.py - rr(q.i) - 5); c.fillStyle = "#fff"; c.fillText(q.t, p.px, p.py - rr(q.i) - 5); });
      const t = cvC.top.c;
      pick(cvC.top.cv, pts, 16, (p, e) => { t.clearRect(0, 0, w, w); t.beginPath(); t.arc(p.px, p.py, rr(p.i) + 3.5, 0, TAU); t.strokeStyle = "#fff"; t.lineWidth = 1.5; t.stroke(); F.tipAt(e.clientX, e.clientY, (names[ld.k[p.i]] || ld.k[p.i]) + "|" + n0(ld.n[p.i]) + " verk", e.pointerType === "touch"); }, () => { t.clearRect(0, 0, w, w); F.tipHide(); });
    })();
    F.d("p", { cls: "sm" }, C).append(Object.assign(document.createElement("b"), { textContent: n0(ld.stor) + " av " + n0(ld.noder) }), " land i same komponent. Danmark og Sverige delar " + n0(ld.dk_se) + " verk, Island og Finland " + n0(ld.is_fi) + ".");
  };

  /* ---------- f13: samsiteringsnett ---------- */
  F.fig.f13 = function (m, d, ctx) {
    const mob = ctx.w < 760, gcol = [0, 1, 2, 3, 4, 6, 7].map((i) => F.PAL[i]);
    const [A, B] = F.pans(m, 2, mob ? "" : "p21", ["", "Del av alle referansar"]);

    const w = A.w, h = mob ? Math.round(w * 1.05) : Math.min(660, Math.round(w * 0.86));
    const cvs = canvas(A, w, h, "Samsiteringsnett for dei 150 mest siterte elementa"), c = cvs.base.c, t = cvs.top.c;
    const pad = 22, scx = (v) => pad + (v / 10000) * (w - 2 * pad), scy = (v) => pad + (v / 10000) * (h - 2 * pad);
    const nodes = d.noder.map((q, i) => Object.assign({ i, px: scx(q.x), py: scy(q.y) }, q));
    const rr = (q) => (mob ? 2.5 : 3.2) + Math.sqrt(q.n) * (mob ? 0.34 : 0.46);
    let sel = null, hi = null;
    function draw() {
      c.clearRect(0, 0, w, h);
      d.kantar.forEach((e) => { const a = nodes[e[0]], b = nodes[e[1]]; const on = hi == null || (a.gr === hi && b.gr === hi); c.beginPath(); c.moveTo(a.px, a.py); c.lineTo(b.px, b.py); c.strokeStyle = "rgba(255,255,255," + (on ? 0.07 + e[3] * 0.22 : 0.02) + ")"; c.lineWidth = 0.5 + Math.min(e[2], 40) / 25; c.stroke(); });
      nodes.slice().sort((a, b) => b.n - a.n).forEach((q) => {
        c.globalAlpha = hi == null || q.gr === hi ? 0.95 : 0.2;
        c.fillStyle = gcol[q.gr]; c.beginPath(); c.arc(q.px, q.py, rr(q), 0, TAU); c.fill();
        if (q.inne) { c.globalAlpha = hi == null || q.gr === hi ? 1 : 0.3; c.lineWidth = 1.6; c.strokeStyle = "#fff"; c.beginPath(); c.arc(q.px, q.py, rr(q) + 2.6, 0, TAU); c.stroke(); }
      });
      c.globalAlpha = 1;
      const box = [];
      nodes.slice().sort((a, b) => b.n - a.n).slice(0, mob ? 11 : 20).forEach((q) => {
        if (hi != null && q.gr !== hi) return;
        c.font = "500 " + (mob ? 10.5 : 11) + "px 'IBM Plex Mono', monospace";
        const wd = c.measureText(q.namn).width + 4, bx = [q.px - wd / 2, q.py - rr(q) - 17, wd, 13];
        if (bx[0] < 0 || bx[0] + wd > w) return;
        if (box.some((b) => bx[0] < b[0] + b[2] && bx[0] + bx[2] > b[0] && bx[1] < b[1] + b[3] && bx[1] + bx[3] > b[1])) return;
        box.push(bx); c.textAlign = "center"; c.lineWidth = 3.5; c.strokeStyle = "#000"; c.strokeText(q.namn, q.px, q.py - rr(q) - 6); c.fillStyle = "#fff"; c.fillText(q.namn, q.px, q.py - rr(q) - 6);
      });
    }
    draw();
    const card = F.d("div", { style: "min-height:5.4em;margin-top:12px;font-size:.92rem;line-height:1.45" }, A);
    function show(q) {
      card.textContent = "";
      if (!q) { card.style.color = "var(--dim)"; card.textContent = "Trykk på ein prikk."; return; }
      card.style.color = "";
      const b = F.d("b", { text: q.namn }, card); b.style.fontWeight = 500;
      card.appendChild(document.createTextNode(" · sitert " + n0(q.n) + " gonger av dei 3 554 verka" + (q.ar ? " · " + q.ar : "")));
      F.d("div", { text: q.tittel, style: "color:var(--dim);font-style:italic" }, card);
      if (q.inne && q.id) { const a = F.d("a", { href: "../index.html#verk/" + encodeURIComponent(q.id), text: "Opne verket i katalogen" }, card); a.style.fontSize = ".86rem"; }
      else if (q.inne) card.appendChild(document.createTextNode(" Verk i laget."));
    }
    show(null);
    const ring = (q) => { t.clearRect(0, 0, w, h); if (q) { t.beginPath(); t.arc(q.px, q.py, rr(q) + 5.5, 0, TAU); t.strokeStyle = "#fff"; t.lineWidth = 1.2; t.stroke(); } };
    pick(cvs.top.cv, nodes, 18, (p, e) => { ring(p); F.tipAt(e.clientX, e.clientY, p.namn + (p.ar ? " (" + p.ar + ")" : "") + "|Sitert " + n0(p.n) + " gonger" + (p.inne ? "|Verk i laget" : ""), e.pointerType === "touch"); }, () => { ring(sel); F.tipHide(); });
    cvs.top.cv.addEventListener("click", (e) => { const b = cvs.top.cv.getBoundingClientRect(); const q = d3.least(nodes, (p) => Math.hypot(p.px - (e.clientX - b.left), p.py - (e.clientY - b.top))); const dd = q && Math.hypot(q.px - (e.clientX - b.left), q.py - (e.clientY - b.top)); if (q && dd < 20) { sel = q; show(q); ring(q); } });
    const lg = F.d("div", { cls: "leg", style: "margin-top:12px" }, A);
    d.grupper.forEach((g, i) => {
      const s = F.d("span", { style: "cursor:pointer;min-height:28px", tabindex: 0 }, lg);
      const ic = F.d("i", { style: "background:" + gcol[i] + ";border-radius:50%" }, s);
      s.appendChild(document.createTextNode(g.namn + " "));
      F.d("b", { text: g.n, style: "color:var(--fg);font-weight:500" }, s);
      const on = () => { hi = i; draw(); }, off = () => { hi = null; draw(); };
      s.addEventListener("pointerenter", on); s.addEventListener("pointerleave", off); s.addEventListener("focus", on); s.addEventListener("blur", off);
    });
    const ringleg = F.d("div", { cls: "leg" }, A);
    const rs = F.d("span", null, ringleg); const ri = F.d("i", { cls: "o", style: "border-color:#fff;border-radius:50%;color:#fff" }, rs); rs.appendChild(document.createTextNode("er òg verk i laget (" + d.topp100_inne + " av dei 100 mest siterte)"));
    /* delar av referansane */
    const rows = [
      { label: "Dei 100 mest siterte", v: d.del_referansar.topp100, color: "var(--fg)", tip: "Dei 100 mest siterte elementa|" + F.n(d.del_referansar.topp100, 1) + " % av " + n0(d.referansar) + " referansar" },
      { label: "Det øvste prosentet, " + n0(d.topp1_n) + " element", v: d.del_referansar.topp1, color: "var(--fg)", tip: "Det øvste prosentet av elementa|" + n0(d.topp1_n) + " av " + n0(d.elementa) + " element har " + F.n(d.del_referansar.topp1, 1) + " % av referansane" },
      { label: "Sitert éin gong, " + n0(d.ein_gong_n) + " element", v: d.del_referansar.ein_gong, color: "var(--dim)", tip: "Element sitert éin gong|" + n0(d.ein_gong_n) + " av " + n0(d.elementa) + " element, " + F.n(d.del_referansar.ein_gong, 1) + " % av referansane" }];
    F.rows(B, { w: B.w }, { rows, max: 50, ticks: [0, 25, 50], tfmt: (v) => v + "", fmt: (v) => F.n(v, 1) + " %", rowH: 46, valW: 7.2, label: "Del av alle referansar", mark: "bar" });
  };

  /* ---------- f18: kartet ---------- */
  F.fig.f18 = function (m, d, ctx) {
    const st = ctx.st; st.mode = st.mode || "klynge";
    const mob = ctx.w < 760;
    const ctl = F.d("div", { cls: "ctl" }, m);
    const [A, B] = F.pans(m, 2, mob ? "" : "p21", ["", ""]);

    const w = A.w, h = mob ? w : Math.min(680, w);
    const cvs = canvas(A, w, h, "Kart over alle 6 432 verk, fargelagt etter klynge"), c = cvs.base.c;
    const pad = 12, sc = (v, s) => pad + (v / d.skala) * (s - 2 * pad);
    const N = d.x.length, px = new Float32Array(N), py = new Float32Array(N);
    for (let i = 0; i < N; i++) { px[i] = sc(d.x[i], w); py[i] = sc(d.y[i], h); }
    const kc = d.klynger.map((k) => F.PAL[k.farge]);
    let hi = null;
    function draw() {
      c.clearRect(0, 0, w, h);
      const mode = st.mode, r = mob ? 1.35 : 1.6;
      for (let pass = 0; pass < 2; pass++) {
        for (let i = 0; i < N; i++) {
          const k = d.k[i], f = d.f[i];
          let on, col, al;
          if (mode === "klynge") { on = hi == null || hi === k; col = kc[k]; al = on ? 0.85 : 0.12; }
          else if (mode === "sprak") { on = (f & 4) !== 0; col = on ? "#ffffff" : "#8a8a8a"; al = on ? 0.95 : 0.2; }
          else { on = (f & 1) !== 0; col = on ? "#ffffff" : "#8a8a8a"; al = on ? 0.95 : 0.2; }
          if ((pass === 0) === on) continue;
          c.globalAlpha = al; c.fillStyle = col; c.beginPath(); c.arc(px[i], py[i], on && mode !== "klynge" ? r + 0.3 : r, 0, TAU); c.fill();
        }
      }
      c.globalAlpha = 1;
    }
    draw();
    /* merkelappar som ekte lenkjer */
    const ov = F.s("svg", { width: w, height: h, viewBox: "0 0 " + w + " " + h, style: "position:absolute;left:0;top:0;z-index:3;pointer-events:none", "aria-label": "Klyngemerke" }, cvs.wrap);
    d.klynger.forEach((k) => {
      const a = F.s("a", { href: d.lenkje + k.id, style: "pointer-events:auto", "aria-label": "Opne klynge " + (k.id + 1) + " i kartfana" }, ov);
      const g = F.s("g", { cls: "mk", tip: (k.id + 1) + " " + k.namn + "|" + n0(k.n) + " verk" }, a);
      const x = sc(k.lx, w), y = sc(k.ly, h);
      F.s("circle", { cx: x, cy: y, r: 11, fill: "#000", stroke: kc[k.id], "stroke-width": 2 }, g);
      F.s("text", { x, y: y + 4, "text-anchor": "middle", text: k.id + 1, style: "fill:#fff;font-weight:500;font-size:12px" }, g);
    });
    const t = cvs.top.c;
    const pts = []; for (let i = 0; i < N; i += 1) pts.push({ i, px: px[i], py: py[i] });
    pick(cvs.top.cv, pts, 6, (p, e) => {
      t.clearRect(0, 0, w, h); t.beginPath(); t.arc(p.px, p.py, 4, 0, TAU); t.strokeStyle = "#fff"; t.lineWidth = 1.3; t.stroke();
      const k = d.klynger[d.k[p.i]]; const fl = d.f[p.i];
      F.tipAt(e.clientX, e.clientY, "Verk i klynge " + (k.id + 1) + "|" + k.namn + "|" + ((fl & 4) ? "nordisk språk" : "engelsk") + ((fl & 1) ? " · nær klyngegrensa" : ""), e.pointerType === "touch");
    }, () => { t.clearRect(0, 0, w, h); F.tipHide(); });
    cvs.wrap.addEventListener("pointerleave", () => { t.clearRect(0, 0, w, h); F.tipHide(); });
    F.seg(ctl, [{ k: "klynge", t: "Klynger" }, { k: "sprak", t: "Nordisk språk" }, { k: "grense", t: "Nær grensa" }], st.mode, (k) => { st.mode = k; draw(); note(); }, "Fargelegg etter");
    const nt = F.d("p", { cls: "sm", style: "margin-top:8px;min-height:3em" }, A);
    function note() {
      nt.textContent = "";
      const b = (tx) => Object.assign(document.createElement("b"), { textContent: tx });
      if (st.mode === "klynge") nt.append(b("Silhuett " + F.n(d.silhuett, 3)), " mot " + F.n(d.silhuett_null, 3) + " i ein tilfeldig datasky: klyngene er svakt skilde.");
      else if (st.mode === "sprak") nt.append(b(F.p(d.nordisk_sprak_del_alle * 100, 1)), " av verka er på nordisk språk. Dei samlar seg i éi klynge.");
      else nt.append(b(F.p(d.grense_del * 100, 1)), " av verka ligg nær grensa mellom to klynger.");
    }
    note();
    /* liste over klyngene */
    F.d("h4", { text: "Klynger", style: "font:400 11.5px/1.35 var(--mono);color:var(--dim);margin:0 0 6px" }, B);
    const ul = F.d("ol", { style: "list-style:none;margin:0;padding:0" }, B);
    d.klynger.forEach((k) => {
      const li = F.d("li", { style: "border-top:1px solid var(--hair);padding:9px 0;display:grid;grid-template-columns:26px 1fr;gap:2px 8px;align-items:start;cursor:default" }, ul);
      const chip = F.d("span", { text: k.id + 1, style: "width:22px;height:22px;border-radius:50%;border:2px solid " + kc[k.id] + ";display:inline-flex;align-items:center;justify-content:center;font:500 11.5px var(--mono);color:var(--fg)" }, li);
      const body = F.d("div", { style: "font-size:.9rem;line-height:1.35" }, li);
      const a = F.d("a", { href: d.lenkje + k.id, text: k.namn }, body);
      F.d("div", { text: n0(k.n) + " verk · " + F.n(k.nordisk_sprak, 1) + " % på nordisk språk", style: "font:11.5px/1.4 var(--mono);color:var(--dim);margin-top:2px" }, body);
      const on = () => { if (st.mode === "klynge") { hi = k.id; draw(); } }, off = () => { hi = null; draw(); };
      li.addEventListener("pointerenter", on); li.addEventListener("pointerleave", off); a.addEventListener("focus", on); a.addEventListener("blur", off);
    });
  };
})();
