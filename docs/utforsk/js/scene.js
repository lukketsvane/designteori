// Canvas scene shared by Kart, Nett, Verda and the Siteringar map: base and overlay
// canvas with dpr, d3.zoom, pointer and touch rules, tooltip and pinned card,
// lasso, keyboard pan/zoom, focus-ring cycling, zoom buttons.
import { tooltip, kort, rorsle, annonserMerke, esc, KL } from "./hjelp.js?v=28";

const DPR = () => Math.min(window.devicePixelRatio || 1, 2);

export function lagScene(flate, o) {
  const d3 = window.d3;
  flate.classList.add("scene");
  flate.insertAdjacentHTML("beforeend", `
    <canvas class="lag-base" aria-hidden="true"></canvas>
    <canvas class="lag-over" tabindex="0" role="application" aria-roledescription="${esc(o.rolle || "interaktivt kart")}"></canvas>
    <div class="zoomknappar" role="group" aria-label="Zoom">
      <button type="button" class="knapp ikon" data-zoom="inn" aria-label="Zoom inn">+</button>
      <button type="button" class="knapp ikon" data-zoom="ut" aria-label="Zoom ut">−</button>
      <button type="button" class="knapp ikon" data-zoom="null" aria-label="Nullstill zoom" title="Nullstill zoom">⟲</button>
    </div>`);
  const base = flate.querySelector(".lag-base"), over = flate.querySelector(".lag-over");
  const cb = base.getContext("2d"), co = over.getContext("2d");
  const [VW, VH] = o.verd;
  const sc = { rf: 1, w: 1, h: 1, dpr: 1, s0: 1, ox: 0, oy: 0, t: d3.zoomIdentity, K: 1, TX: 0, TY: 0, k: 1, fokusId: null, hoverId: null };
  const teiknTider = [];

  function oppdaterSc() {
    const t = sc.t;
    sc.k = t.k;
    sc.K = sc.s0 * t.k;
    sc.TX = t.k * sc.ox + t.x;
    sc.TY = t.k * sc.oy + t.y;
  }
  sc.tilSkjerm = (x, y) => [x * sc.K + sc.TX, y * sc.K + sc.TY];
  sc.tilVerd = (px, py) => [(px - sc.TX) / sc.K, (py - sc.TY) / sc.K];
  sc.synleg = (x, y, m = 0) => { const [px, py] = sc.tilSkjerm(x, y); return px >= -m && px <= sc.w + m && py >= -m && py <= sc.h + m; };
  sc.verdBoks = () => { const [x0, y0] = sc.tilVerd(0, 0), [x1, y1] = sc.tilVerd(sc.w, sc.h); return [x0, y0, x1, y1]; };
  sc.setVerd = (ctx) => ctx.setTransform(sc.dpr * sc.K, 0, 0, sc.dpr * sc.K, sc.dpr * sc.TX, sc.dpr * sc.TY);
  sc.setSkjerm = (ctx) => ctx.setTransform(sc.dpr, 0, 0, sc.dpr, 0, 0);

  // ---------- drawing ----------
  let ventBase = false, ventOver = false, raf = 0;
  function teiknNo() {
    raf = 0;
    const t0 = performance.now();
    try {
      if (ventBase) {
        ventBase = false;
        cb.setTransform(1, 0, 0, 1, 0, 0);
        cb.clearRect(0, 0, base.width, base.height);
        o.teiknBase(cb, sc);
      }
      if (ventOver) {
        ventOver = false;
        co.setTransform(1, 0, 0, 1, 0, 0);
        co.clearRect(0, 0, over.width, over.height);
        o.teiknOverlay(co, sc);
        if (lasso && lasso.pkt.length > 1) teiknLasso();
      }
    } catch (e) {
      if (o.feil) o.feil(e); else console.error(e);
    }
    teiknTider.push(performance.now() - t0);
    if (teiknTider.length > 400) teiknTider.splice(0, 200);
  }
  const teikn = () => { ventBase = ventOver = true; tipsKey = null; if (!raf) raf = requestAnimationFrame(teiknNo); };
  const teiknOverlay = () => { ventOver = true; if (!raf) raf = requestAnimationFrame(teiknNo); };

  // ---------- size ----------
  // Boxes of the controls that float over the drawing (legend, side panel, toolbars), in
  // canvas px. Labels avoid them, and the home view is fitted to the space they leave.
  let dekkaTid = 0;
  function malDekka() {
    const r = flate.getBoundingClientRect();
    const ut = [];
    const els = [...flate.querySelectorAll(":scope > .teikn-wrap, :scope > .sidepanel:not([hidden]), :scope > .verktoy, :scope > .zoomknappar, :scope > .invitasjon:not([hidden])")];
    // panels that float over this drawing from outside its own box (Siteringar's ranked list)
    if (o.dekkaEkstra) for (const e of o.dekkaEkstra()) if (e && !e.hidden) els.push(e);
    for (const e of els) {
      const b = e.getBoundingClientRect();
      if (b.right <= r.left || b.left >= r.right || b.bottom <= r.top || b.top >= r.bottom) continue;
      if (!b.width || !b.height) continue;
      ut.push({ x0: b.left - r.left - 4, y0: b.top - r.top - 4, x1: b.right - r.left + 4, y1: b.bottom - r.top + 4, kind: e.classList.contains("teikn-wrap") ? "teikn" : e.classList.contains("sidepanel") ? "panel" : "verktoy" });
    }
    sc.dekka = ut;
    dekkaTid = performance.now();
    return ut;
  }
  sc.dekka = [];
  sc.dekkaNo = () => (performance.now() - dekkaTid > 400 ? malDekka() : sc.dekka);

  function storleik() {
    const r = flate.getBoundingClientRect();
    // a hidden view (display:none) reports 0 x 0: keep the last size and transform
    if (!r.width || !r.height) return;
    const w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
    // keep the reader's zoom; the home view (identity) refits to the new size and panels
    const heime = Math.abs(sc.t.k - 1) < 1e-3 && Math.abs(sc.t.x) < 0.5 && Math.abs(sc.t.y) < 0.5;
    const z = sc.w > 1 && !heime ? zNo() : null;
    const dpr = DPR();
    // reallocate the canvases only when the size changed (a filter change must not pay for it)
    if (w !== sc.w || h !== sc.h || dpr !== sc.dpr) {
      sc.w = w; sc.h = h; sc.dpr = dpr;
      for (const c of [base, over]) {
        c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
        c.style.width = `${w}px`; c.style.height = `${h}px`;
      }
    }
    // mark sizes are tuned for a drawing about 860 px across; smaller drawings get smaller marks
    sc.rf = Math.max(0.5, Math.min(1, Math.min(w, h) / 860));
    const m = o.marg != null ? o.marg : 0.04;
    // the home view fits o.heim() (a box in world units) or the whole world
    const hb = o.heim ? o.heim() : [0, 0, VW, VH];
    const bw = Math.max(1, hb[2] - hb[0]), bh = Math.max(1, hb[3] - hb[1]);
    // The home view is fitted to the free area: a side panel on the right takes its width,
    // and the floating legend (lower left) takes either its width or its height, whichever
    // leaves the larger drawing. The zoom buttons and toolbars are small and are not counted.
    const dk = malDekka();
    // a tall panel on the right takes width; a box resting on the bottom (the legend, or a
    // ranked list docked at the bottom on a phone) takes height; the legend may take width
    const hogre = dk.filter((b) => b.kind === "panel" && b.x0 > w * 0.4 && b.y1 - b.y0 > h * 0.3);
    const botn = dk.filter((b) => b.kind !== "verktoy" && b.y1 >= h - 30 && !hogre.includes(b));
    const forkl = dk.filter((b) => b.kind === "teikn");
    const padR = Math.max(0, ...hogre.map((b) => w - b.x0 + 8));
    const padL = Math.max(0, ...forkl.map((b) => b.x1 + 8));
    const padB = Math.max(0, ...botn.map((b) => h - b.y0 + 4));
    const padT = Math.max(0, ...dk.filter((b) => b.kind === "verktoy" && b.x0 < w * 0.5).map((b) => b.y1 + 4));
    const val = [];
    const prov = (l, rr, t, bt) => { const fw = w - l - rr, fh = h - t - bt; if (fw > 80 && fh > 80) val.push({ l, rr, t, bt, s: Math.min(fw / bw, fh / bh) }); };
    prov(padL, padR, 0, 0);
    prov(0, padR, 0, padB);
    prov(0, padR, padT, padB);
    prov(0, padR, 0, 0);
    prov(0, 0, 0, 0);
    // prefer a fit that leaves every control clear, unless it costs more than 45 % of the scale
    const best = val.reduce((a, b) => (b.s > a.s ? b : a), val[val.length - 1]);
    const klar = val.slice(0, 3).filter((v) => v.s >= best.s * 0.55).sort((a, b) => b.s - a.s)[0] || best;
    const fw = w - klar.l - klar.rr, fh = h - klar.t - klar.bt;
    sc.s0 = Math.min(fw / bw, fh / bh) * (1 - 2 * m);
    sc.ox = klar.l + (fw - bw * sc.s0) / 2 - hb[0] * sc.s0; sc.oy = klar.t + (fh - bh * sc.s0) / 2 - hb[1] * sc.s0;
    zoom.extent([[0, 0], [w, h]]).translateExtent(o.fri ? [[-Infinity, -Infinity], [Infinity, Infinity]] : [[-w * 2, -h * 2], [w * 3, h * 3]]);
    if (z) settZ(z, 0, true); else { oppdaterSc(); }
    teikn();
  }

  // ---------- zoom ----------
  let lassoModus = false, suspendert = false;
  const zoom = d3.zoom().scaleExtent(o.skala).clickDistance(4).tapDistance(10)
    .filter((ev) => {
      if (ev.type === "wheel") return !lasso;
      if (lasso) return false;
      if (o.lasso && (ev.shiftKey || (lassoModus && !suspendert))) return false;
      return (!ev.ctrlKey || ev.type === "wheel") && !ev.button;
    })
    .on("zoom", (ev) => {
      sc.t = ev.transform;
      oppdaterSc();
      if (o.vedZoomRask) o.vedZoomRask(sc);
      teikn();
      if (!stilleZoom && o.vedZoom) { const t = ev.transform; o.vedZoom(Math.abs(t.k - 1) < 1e-3 && Math.abs(t.x) < 0.5 && Math.abs(t.y) < 0.5 ? null : zNo()); }
    });
  let stilleZoom = false;
  const sel = d3.select(over);
  sel.call(zoom).on("dblclick.zoom", null);

  function zNo() {
    const t = sc.t;
    const cx = ((sc.w / 2 - t.x) / t.k - sc.ox) / sc.s0, cy = ((sc.h / 2 - t.y) / t.k - sc.oy) / sc.s0;
    return [t.k, cx, cy];
  }
  function tFor([k, cx, cy], yMidt = sc.h / 2) {
    k = Math.max(o.skala[0], Math.min(o.skala[1], k));
    return d3.zoomIdentity.translate(sc.w / 2 - k * (sc.s0 * cx + sc.ox), yMidt - k * (sc.s0 * cy + sc.oy)).scale(k);
  }
  function brukT(t, ms, stille) {
    stilleZoom = !!stille;
    if (!ms || rorsle.redusert) { sel.call(zoom.transform, t); stilleZoom = false; return; }
    sel.transition().duration(ms).call(zoom.transform, t).on("end interrupt", () => { stilleZoom = false; });
  }
  function settZ(z, ms = 0, stille = true) {
    if (!z) { brukT(d3.zoomIdentity, ms, stille); return; }
    brukT(tFor(z), ms, stille);
  }
  const zoomBy = (f) => { stilleZoom = false; if (rorsle.redusert) sel.call(zoom.scaleBy, f); else sel.transition().duration(200).call(zoom.scaleBy, f); };
  flate.querySelector(".zoomknappar").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-zoom]");
    if (!b) return;
    if (b.dataset.zoom === "inn") zoomBy(1.5);
    else if (b.dataset.zoom === "ut") zoomBy(1 / 1.5);
    else brukT(d3.zoomIdentity, 300, false);
  });

  // ---------- pointer ----------
  let sistePeikar = "mouse";
  let hoverEv = null, hoverRaf = 0, tipsKey = null;
  const peikarar = new Set();
  const lokal = (ev) => { const r = over.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top]; };
  function hoverNo() {
    hoverRaf = 0;
    const ev = hoverEv;
    if (!ev) return;
    const [px, py] = lokal(ev);
    const hit = o.finn(px, py, "mouse");
    const id = hit ? hit.id : null;
    if (id !== sc.hoverId) {
      sc.hoverId = id;
      if (o.hoverEndra) o.hoverEndra(hit);
      teiknOverlay();
    }
    if (hit && !kort.ope) {
      // the tooltip text is built once per mark (and per redraw), then only moved
      const key = `${id}|${hit.fleire || 0}`;
      if (key !== tipsKey || !tooltip.synleg) {
        tipsKey = key;
        const html = o.tips(hit);
        if (html) tooltip.vis(html, ev.clientX, ev.clientY); else { tooltip.skjul(); tipsKey = null; }
      } else tooltip.flytt(ev.clientX, ev.clientY);
    } else { tooltip.skjul(); tipsKey = null; }
    over.style.cursor = hit ? "pointer" : (o.peikarFor ? o.peikarFor(px, py) : "") || "";
  }
  over.addEventListener("pointermove", (ev) => {
    if (lasso) { lassoFlytt(ev); return; }
    if (ev.pointerType !== "mouse" || ev.buttons) { if (ev.buttons && tooltip.synleg) tooltip.skjul(); return; }
    hoverEv = ev;
    if (!hoverRaf) hoverRaf = requestAnimationFrame(hoverNo);
  });
  over.addEventListener("pointerleave", () => {
    hoverEv = null;
    tooltip.skjul();
    if (sc.hoverId != null) { sc.hoverId = null; if (o.hoverEndra) o.hoverEndra(null); teiknOverlay(); }
  });
  over.addEventListener("pointerdown", (ev) => {
    sistePeikar = ev.pointerType || "mouse";
    // a primary pointer means no other pointer is down: forget ids whose release we never saw
    // (a mouse button released outside the canvas), so later touches are not "second fingers"
    if (ev.isPrimary) { peikarar.clear(); suspendert = false; }
    peikarar.add(ev.pointerId);
    if (o.stopp) o.stopp();
    if (lasso && peikarar.size > 1) { avbrytLasso(); suspendert = true; return; }
    if (o.lasso && ev.isPrimary && ((lassoModus && !suspendert) || (ev.shiftKey && ev.pointerType === "mouse"))) startLasso(ev);
  });
  const opp = (ev) => {
    peikarar.delete(ev.pointerId);
    if (lasso && ev.pointerId === lasso.id) ferdigLasso(ev);
    if (!peikarar.size) suspendert = false;
  };
  over.addEventListener("pointerup", opp);
  // releases outside the canvas (the mouse is not captured) still end the press
  window.addEventListener("pointerup", (ev) => { if (peikarar.has(ev.pointerId) && ev.target !== over) opp(ev); });
  over.addEventListener("lostpointercapture", (ev) => { if (lasso && ev.pointerId === lasso.id) avbrytLasso(); peikarar.delete(ev.pointerId); if (!peikarar.size) suspendert = false; });
  over.addEventListener("pointercancel", (ev) => { peikarar.delete(ev.pointerId); if (lasso && ev.pointerId === lasso.id) avbrytLasso(); if (!peikarar.size) suspendert = false; });
  over.addEventListener("click", (ev) => {
    if (lassoNettoFerdig) { lassoNettoFerdig = false; return; }
    const type = ev.pointerType || sistePeikar;
    const [px, py] = lokal(ev);
    const hit = o.finn(px, py, type === "mouse" ? "mouse" : "touch");
    if (type === "mouse") {
      if (hit) o.klikk(hit, ev);
      else { if (kort.ope) kort.lukk(); if (o.tomKlikk) o.tomKlikk(px, py, ev); }
      return;
    }
    // touch and pen: first tap inspects, second acts
    tooltip.skjul();
    if (!hit) {
      if (kort.ope) kort.lukk();
      else if (o.tomKlikk) o.tomKlikk(px, py, ev);
      sc.hoverId = null; teiknOverlay();
      return;
    }
    if (kort.ope && kort.id === hit.id) { kort.lukk(); o.tapHandling(hit, ev); return; }
    const k = o.kort(hit);
    sc.hoverId = hit.id;
    if (o.hoverEndra) o.hoverEndra(hit);
    teiknOverlay();
    kort.opne({ id: hit.id, html: k.html, knappar: k.knappar, x: ev.clientX, y: ev.clientY });
  });

  // ---------- lasso ----------
  let lasso = null, lassoNettoFerdig = false;
  function startLasso(ev) {
    ev.preventDefault();
    try { over.setPointerCapture(ev.pointerId); } catch (e) { /* pointer already gone */ }
    lasso = { id: ev.pointerId, pkt: [lokal(ev)] };
    tooltip.skjul();
  }
  function lassoFlytt(ev) {
    if (ev.pointerId !== lasso.id) return;
    const p = lokal(ev), q = lasso.pkt[lasso.pkt.length - 1];
    if (Math.hypot(p[0] - q[0], p[1] - q[1]) > 3) { lasso.pkt.push(p); teiknOverlay(); }
  }
  function teiknLasso() {
    sc.setSkjerm(co);
    co.beginPath();
    lasso.pkt.forEach(([x, y], i) => (i ? co.lineTo(x, y) : co.moveTo(x, y)));
    co.closePath();
    co.fillStyle = KL.lassoFyll;
    co.fill();
    co.strokeStyle = KL.ring;
    co.lineWidth = 1;
    co.stroke();
  }
  function ferdigLasso() {
    const pkt = lasso.pkt;
    lasso = null;
    lassoNettoFerdig = pkt.length > 2;
    setTimeout(() => { lassoNettoFerdig = false; }, 400);
    teiknOverlay();
    const siste = pkt[pkt.length - 1];
    if (pkt.length < 3) { if (pkt.length > 1) lassoHint(siste); return; }
    let verd = pkt.map(([x, y]) => sc.tilVerd(x, y));
    const [x0, y0, x1, y1] = sc.verdBoks();
    const tol = Math.hypot(x1 - x0, y1 - y0) * 0.015;
    verd = forenkle(verd, tol);
    while (verd.length > 24) verd = forenkle(verd, tolAuke(verd));
    if (verd.length < 3 || areal(verd) < VW * VH * 0.0001) {
      // a drag with little area: use the box it spans when that is a real box, else say how
      const xs = pkt.map((p) => p[0]), ys = pkt.map((p) => p[1]);
      const bx0 = Math.min(...xs), bx1 = Math.max(...xs), by0 = Math.min(...ys), by1 = Math.max(...ys);
      if (bx1 - bx0 < 16 || by1 - by0 < 16) { lassoHint(siste); return; }
      verd = [[bx0, by0], [bx1, by0], [bx1, by1], [bx0, by1]].map(([x, y]) => sc.tilVerd(x, y));
    }
    o.lasso.ferdig(verd.map(([x, y]) => [Math.round(x), Math.round(y)]), sistePeikar);
  }
  let hintTid = 0;
  function lassoHint([x, y]) {
    const r = over.getBoundingClientRect();
    tooltip.vis(`<div class="tt-tittel">Teikn ein ring rundt verka</div><div class="tt-meta">Ei rett line har ikkje noko område. Dra rundt punkta, eller dra på skrå for ein firkant.</div>`, r.left + x, r.top + y);
    clearTimeout(hintTid);
    hintTid = setTimeout(() => tooltip.skjul(), 2600);
  }
  function avbrytLasso() {
    if (!lasso) return false;
    lasso = null;
    teiknOverlay();
    return true;
  }

  // ---------- keyboard ----------
  let fokusIdx = -1;
  over.addEventListener("keydown", (ev) => {
    // leave browser shortcuts alone (Ctrl/Cmd + plus, minus, 0 zoom the page; Alt+Left goes back)
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const k = ev.key;
    const steg = 0.1;
    if (k === "ArrowLeft" || k === "ArrowRight" || k === "ArrowUp" || k === "ArrowDown") {
      const dx = k === "ArrowLeft" ? sc.w * steg : k === "ArrowRight" ? -sc.w * steg : 0;
      const dy = k === "ArrowUp" ? sc.h * steg : k === "ArrowDown" ? -sc.h * steg : 0;
      sel.call(zoom.translateBy, dx / sc.t.k, dy / sc.t.k);
    } else if (k === "+" || k === "=") zoomBy(1.5);
    else if (k === "-" || k === "_") zoomBy(1 / 1.5);
    else if (k === "0") brukT(d3.zoomIdentity, 300, false);
    else if ((k === "n" || k === "N") && o.fokusListe) {
      const l = o.fokusListe();
      if (!l.length) return;
      fokusIdx = (fokusIdx + (k === "n" ? 1 : l.length - 1) + (fokusIdx < 0 && k === "N" ? 1 : 0)) % l.length;
      const f = l[fokusIdx];
      sc.fokusId = f.id;
      const [px, py] = sc.tilSkjerm(f.x, f.y);
      if (px < 0 || px > sc.w || py < 0 || py > sc.h) brukT(tFor([sc.t.k, f.x, f.y]), 250, false);
      const r = over.getBoundingClientRect();
      const hit = o.finnId(f.id);
      const html = hit ? o.tips(hit) : "";
      if (html) {
        const [qx, qy] = sc.tilSkjerm(f.x, f.y);
        tooltip.vis(html, r.left + qx, r.top + qy);
        const tmp = document.createElement("div");
        tmp.innerHTML = html;
        annonserMerke(tmp.textContent.replace(/\s+/g, " ").trim());
      }
      if (o.hoverEndra) { sc.hoverId = f.id; o.hoverEndra(hit); }
      teiknOverlay();
    } else if (k === "Enter" && sc.fokusId != null && o.fokusHandling) o.fokusHandling(sc.fokusId, ev);
    else return;
    ev.preventDefault();
  });
  over.addEventListener("blur", () => { if (sc.fokusId != null) { fokusUt(); } });
  function fokusUt() {
    if (sc.fokusId == null) return false;
    sc.fokusId = null; fokusIdx = -1; sc.hoverId = null;
    tooltip.skjul();
    if (o.hoverEndra) o.hoverEndra(null);
    teiknOverlay();
    return true;
  }

  const ro = new ResizeObserver(() => storleik());
  ro.observe(flate);
  flate.addEventListener("utforsk:teikn", () => storleik());

  return {
    sc, base, over, teikn, teiknOverlay, storleik, zNo,
    tvingTeikn() { if (raf) { cancelAnimationFrame(raf); teiknNo(); } },
    settZ,
    zoomTilBoks(b, ms = 300, yPad = 0) {
      const [x0, y0, x1, y1] = b;
      const bw = Math.max(1, x1 - x0) * sc.s0, bh = Math.max(1, y1 - y0) * sc.s0;
      const k = Math.min(o.skala[1], Math.max(o.skala[0], 0.9 * Math.min(sc.w / bw, (sc.h - yPad) / bh)));
      brukT(tFor([k, (x0 + x1) / 2, (y0 + y1) / 2], (sc.h - yPad) / 2), ms, false);
    },
    sentrer(x, y, botnPad = 0, ms = 250) { brukT(tFor([sc.t.k, x, y], (sc.h - botnPad) / 2), ms, false); },
    panTilOmUte(x, y, ms = 250) { if (!sc.synleg(x, y, -20)) brukT(tFor([sc.t.k, x, y]), ms, false); },
    zoomBy,
    settLassoModus(v) { lassoModus = v; over.classList.toggle("lassomodus", v); },
    lassoModus: () => lassoModus,
    avbrytLasso,
    lassoAktiv: () => !!lasso,
    fokusUt,
    settLabel(t) { over.setAttribute("aria-label", t); },
    teiknTider,
    zoomBehaviour: zoom,
    sel,
  };
}

// Douglas-Peucker on a closed polygon (treated as an open polyline).
function forenkle(p, tol) {
  if (p.length < 4) return p;
  const behald = new Uint8Array(p.length);
  behald[0] = behald[p.length - 1] = 1;
  const stabel = [[0, p.length - 1]];
  while (stabel.length) {
    const [a, b] = stabel.pop();
    let mx = 0, mi = -1;
    const [ax, ay] = p[a], [bx, by] = p[b];
    const L = Math.hypot(bx - ax, by - ay) || 1;
    for (let i = a + 1; i < b; i++) {
      const d = Math.abs((bx - ax) * (ay - p[i][1]) - (ax - p[i][0]) * (by - ay)) / L;
      if (d > mx) { mx = d; mi = i; }
    }
    if (mx > tol && mi > 0) { behald[mi] = 1; stabel.push([a, mi], [mi, b]); }
  }
  return p.filter((_, i) => behald[i]);
}
function tolAuke(p) {
  let mn = Infinity;
  for (let i = 1; i < p.length; i++) mn = Math.min(mn, Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]));
  return Math.max(mn, 1) * 1.5;
}
function areal(p) {
  let a = 0;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) a += (p[j][0] + p[i][0]) * (p[j][1] - p[i][1]);
  return Math.abs(a / 2);
}

// Simple quadtree helpers on world points.
export function lagIndeks(n, xf, yf) {
  const d3 = window.d3;
  const idx = Array.from({ length: n }, (_, i) => i);
  return d3.quadtree(idx, xf, yf);
}
// All items within r (world units) of (x, y).
export function innanfor(qt, x, y, r, xf, yf) {
  const ut = [];
  qt.visit((node, x0, y0, x1, y1) => {
    if (x0 > x + r || x1 < x - r || y0 > y + r || y1 < y - r) return true;
    if (!node.length) {
      let d = node;
      do { const i = d.data; const dx = xf(i) - x, dy = yf(i) - y; if (dx * dx + dy * dy <= r * r) ut.push(i); d = d.next; } while (d);
    }
    return false;
  });
  return ut;
}
