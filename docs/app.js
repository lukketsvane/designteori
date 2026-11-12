/* DESIGNTEORI - Minimal, Native-Feel Nordic Design Theory Interface */
(() => {
  "use strict";

  const STEP = 50;
  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1"];
  const CC_COLORS = { NO: "#3b82f6", SE: "#eab308", DK: "#ef4444", FI: "#06b6d4", IS: "#a855f7" };

  const S = {
    works: [],
    byId: new Map(),
    analysis: null,
    context: null,
    canon: null,
    authors: null,
    insts: null,
    semMeta: null,
    semVecs: null,
    semIdx: new Map(),
    semVocab: null,
    semVocabVecs: null,
    semVocabMap: new Map(),
    semMap: null,

    pdfOnly: false,
    filtered: [],
    shown: STEP,
    expandedId: null,
    semScores: null,
    semLabel: "",
    citSub: "internal",

    clusterFilter: -1,
    zoom: 1,
    panX: 0,
    panY: 0,
  };

  const $ = (id) => document.getElementById(id);
  const fmt = (n) => (typeof n === "number" ? n.toLocaleString("nn-NO") : "");
  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  async function jget(u, fb = null) {
    try { const r = await fetch(u); return r.ok ? await r.json() : fb; } catch { return fb; }
  }

  async function init() {
    bind();
    const [pubs, nordic, ana] = await Promise.all([
      jget("data/publications.json", []),
      jget("data/nordic_additions.json", []),
      jget("data/analysis.json", null),
    ]);

    for (const w of pubs) {
      w._layer = "openalex";
      w._q = `${w.title || ""} ${(w.authors || []).join(" ")} ${w.source || ""} ${w.doi || ""} ${w.topic || ""}`.toLowerCase();
      S.works.push(w);
      S.byId.set(w.id, w);
    }
    for (const w of nordic) {
      w._layer = "nordic";
      w._q = `${w.title || ""} ${(w.authors || []).join(" ")} ${w.source || ""} ${w.venue || ""} ${w.doi || ""}`.toLowerCase();
      S.works.push(w);
      S.byId.set(w.id, w);
    }

    S.analysis = ana;
    const ov = ana?.overview || {};
    const repoPdfCnt = ov.repo_pdf_files ?? S.works.filter((w) => w.pdf).length;
    $("stWorks").textContent = fmt(ov.total_searchable_works ?? S.works.length);
    $("stPdfs").textContent = fmt(repoPdfCnt);

    const h = (location.hash || "").replace("#", "");
    if (h === "pdf") S.pdfOnly = true;

    filterCorpus();
    renderAnalysis();
    loadVectors();

    if (["korpus", "siteringar", "kart", "analyse", "teorielement"].includes(h)) {
      setTab(h);
    }
  }

  async function loadVectors() {
    const [m, vocab] = await Promise.all([
      jget("data/semantic_index.json", null),
      jget("data/semantic_vocab.json", null),
    ]);
    if (!m?.ids) return;
    try {
      const r = await fetch("data/semantic_vectors.bin");
      if (!r.ok) return;
      const v = new Int8Array(await r.arrayBuffer());
      if (v.length !== m.ids.length * m.dimensions) return;
      S.semMeta = m;
      S.semVecs = v;
      m.ids.forEach((id, i) => S.semIdx.set(id, i));
      if (vocab?.words && vocab?.vectors_b64) {
        const bin = atob(vocab.vectors_b64);
        const vv = new Int8Array(bin.length);
        for (let i = 0; i < bin.length; i++) {
          const c = bin.charCodeAt(i);
          vv[i] = c > 127 ? c - 256 : c;
        }
        if (vv.length === vocab.words.length * vocab.dimensions) {
          S.semVocab = vocab.words;
          S.semVocabVecs = vv;
          vocab.words.forEach((w, idx) => S.semVocabMap.set(w, idx));
        }
      }
      if ($("qInput").value.trim() || S.expandedId) filterCorpus();
    } catch {}
  }

  function cosineAll(qVec) {
    if (!S.semVecs || !S.semMeta) return null;
    const D = S.semMeta.dimensions, ids = S.semMeta.ids, M = S.semVecs;
    let qn = 0;
    for (let d = 0; d < D; d++) qn += qVec[d] * qVec[d];
    qn = Math.sqrt(qn) || 1;
    const map = new Map();
    for (let i = 0, b = 0; i < ids.length; i++, b += D) {
      let dot = 0, vn = 0;
      for (let d = 0; d < D; d++) { const x = M[b + d]; dot += x * qVec[d]; vn += x * x; }
      map.set(ids[i], vn > 0 ? dot / (Math.sqrt(vn) * qn) : 0);
    }
    return map;
  }

  function querySemanticVector(tokens) {
    if (!S.semVocabVecs || !S.semMeta || !tokens.length) return null;
    const D = S.semMeta.dimensions;
    const acc = new Float32Array(D);
    let matched = 0;
    for (const raw of tokens) {
      const tok = raw.replace(/[^a-zæøåäöüþð0-9-]/gi, "").toLowerCase();
      if (tok.length < 3) continue;
      let idx = S.semVocabMap.get(tok);
      if (idx === undefined && tok.length >= 4 && S.semVocab) {
        for (let i = 0; i < S.semVocab.length; i++) {
          const vw = S.semVocab[i];
          if (vw.startsWith(tok) || (tok.length >= 5 && tok.startsWith(vw))) {
            idx = i;
            break;
          }
        }
      }
      if (idx !== undefined) {
        const base = idx * D;
        for (let d = 0; d < D; d++) acc[d] += S.semVocabVecs[base + d];
        matched++;
      }
    }
    return matched > 0 ? acc : null;
  }

  function topNeighbors(wid, k = 6) {
    if (!S.semVecs || !S.semIdx.has(wid)) return [];
    const D = S.semMeta.dimensions, row = S.semIdx.get(wid);
    const q = new Float32Array(D);
    for (let d = 0; d < D; d++) q[d] = S.semVecs[row * D + d];
    const sc = cosineAll(q);
    const arr = [];
    for (const [id, c] of sc) if (id !== wid && S.byId.has(id)) arr.push([id, c]);
    arr.sort((a, b) => b[1] - a[1]);
    return arr.slice(0, k).map(([id, c]) => ({ w: S.byId.get(id), c }));
  }

  function triggerSimilar(wid) {
    if (!S.semVecs || !S.semIdx.has(wid)) return;
    const D = S.semMeta.dimensions, row = S.semIdx.get(wid);
    const q = new Float32Array(D);
    for (let d = 0; d < D; d++) q[d] = S.semVecs[row * D + d];
    S.semScores = cosineAll(q);
    S.semLabel = `Liknande: «${(S.byId.get(wid)?.title || wid).slice(0, 64)}»`;
    $("sortSel").value = "relevance";
    setTab("korpus");
    filterCorpus();
  }

  function hasActiveFilters() {
    return Boolean(
      $("qInput").value.trim() ||
      S.pdfOnly ||
      $("ccSel").value ||
      $("presetSel").value ||
      $("eraSel").value ||
      S.semScores
    );
  }

  function filterCorpus() {
    const q = $("qInput").value.trim().toLowerCase();
    const toks = q ? q.split(/\s+/).filter(Boolean) : [];
    const cc = $("ccSel").value;
    const era = $("eraSel").value;
    const sort = $("sortSel").value;

    $("metricPdfBtn").classList.toggle("active-metric", S.pdfOnly);
    $("metricAllBtn").classList.toggle("active-metric", !S.pdfOnly);
    $("resetBtn").hidden = !hasActiveFilters();
    $("semBanner").hidden = !S.semScores;
    if (S.semScores) $("semBannerTxt").textContent = S.semLabel;

    let queryCos = null;
    if (!S.semScores && toks.length) {
      const qv = querySemanticVector(toks);
      if (qv) queryCos = cosineAll(qv);
    }

    const baseCandidates = [];
    for (const w of S.works) {
      if (S.pdfOnly && !w.pdf) continue;
      if (cc && !(w.countries || []).includes(cc) && w.source_country !== cc) continue;
      if (era) {
        const y = w.year;
        if (!y) continue;
        if (era === "pre2000" && y >= 2000) continue;
        if (era === "2000-2009" && (y < 2000 || y > 2009)) continue;
        if (era === "2010-2019" && (y < 2010 || y > 2019)) continue;
        if (era === "2020-2026" && y < 2020) continue;
      }
      baseCandidates.push(w);
    }

    let out = [];
    if (!S.semScores && toks.length) {
      const lexical = [];
      const semFallback = [];
      for (const w of baseCandidates) {
        let ok = true;
        for (const t of toks) if (!w._q.includes(t)) { ok = false; break; }
        if (ok) {
          lexical.push(w);
        } else if (queryCos && (queryCos.get(w.id) || 0) >= 0.64) {
          semFallback.push(w);
        }
      }
      out = lexical.length > 0 ? lexical.concat(semFallback.slice(0, 60)) : semFallback;
    } else {
      out = baseCandidates;
    }

    if (sort === "citations") out.sort((a, b) => (b.citations || 0) - (a.citations || 0));
    else if (sort === "year_desc") out.sort((a, b) => (b.year || 0) - (a.year || 0));
    else if (sort === "year_asc") out.sort((a, b) => (a.year || 9999) - (b.year || 9999));
    else if (S.semScores) out.sort((a, b) => (S.semScores.get(b.id) || -1) - (S.semScores.get(a.id) || -1));
    else if (toks.length) {
      out.sort((a, b) => {
        const at = (a.title || "").toLowerCase(), bt = (b.title || "").toLowerCase();
        const aExact = toks.every((t) => a._q.includes(t)) ? 1 : 0;
        const bExact = toks.every((t) => b._q.includes(t)) ? 1 : 0;
        if (bExact !== aExact) return bExact - aExact;
        const ah = toks.reduce((s, t) => s + (at.includes(t) ? 1 : 0), 0) + (queryCos ? (queryCos.get(a.id) || 0) * 0.8 : 0);
        const bh = toks.reduce((s, t) => s + (bt.includes(t) ? 1 : 0), 0) + (queryCos ? (queryCos.get(b.id) || 0) * 0.8 : 0);
        return Math.abs(bh - ah) > 0.05 ? bh - ah : (Boolean(b.pdf) !== Boolean(a.pdf) ? (b.pdf ? 1 : -1) : (b.citations || 0) - (a.citations || 0));
      });
    } else {
      out.sort((a, b) => (Boolean(b.pdf) !== Boolean(a.pdf) ? (b.pdf ? 1 : -1) : (b.citations || 0) - (a.citations || 0)));
    }

    S.filtered = out;
    S.shown = STEP;
    renderCorpus();
  }

  async function renderCorpus() {
    const N = S.filtered.length;
    const rows = S.filtered.slice(0, S.shown);
    $("hitCount").textContent = N === S.works.length ? `${fmt(N)} publikasjonar` : `${fmt(N)} treff`;
    $("moreCorpusBtn").hidden = rows.length >= N;

    if (S.expandedId && !S.context) {
      S.context = await jget("data/work_context.json", {});
    }

    $("corpusList").innerHTML = rows.map((w) => {
      const isExp = S.expandedId === w.id;
      const auth = (w.authors || []).slice(0, 4).join(", ");
      const cc = (w.countries && w.countries.length ? w.countries : (w.source_country ? [w.source_country] : [])).join(", ");
      const cos = S.semScores?.get(w.id);
      const doiHref = w.doi ? (w.doi.startsWith("http") ? w.doi : `https://doi.org/${w.doi}`) : "";

      const subParts = [];
      if (auth) subParts.push(auth);
      if (w.venue || w.source) subParts.push(w.venue || w.source);
      if (typeof w.citations === "number" && w.citations > 0) subParts.push(`${fmt(w.citations)} sit.`);
      if (typeof cos === "number") subParts.push(`likskap ${cos.toFixed(2)}`);

      return `
        <article class="item">
          <div class="meta-col">${esc(w.year || "")}${cc ? `<br>${esc(cc)}` : ""}</div>
          <div>
            <h3 class="title"><button class="title-btn" type="button" data-toggle="${esc(w.id)}">${esc(w.title || "(utan tittel)")}</button></h3>
            ${subParts.length ? `<p class="subline">${esc(subParts.join(" · "))}</p>` : ""}
          </div>
          <div class="actions">
            ${w.pdf ? `<a class="act-pdf" href="${esc(w.pdf)}" target="_blank" rel="noopener">PDF</a>` : (w.oa_url ? `<a href="${esc(w.oa_url)}" target="_blank" rel="noopener">Kjelde</a>` : "")}
            ${doiHref ? `<a href="${esc(doiHref)}" target="_blank" rel="noopener">DOI</a>` : ""}
            ${S.semIdx.has(w.id) ? `<button type="button" data-sim="${esc(w.id)}">Liknande</button>` : ""}
          </div>
          ${isExp ? renderInlineDetail(w) : ""}
        </article>`;
    }).join("") || `<p style="padding:24px 0;color:var(--dim);">Ingen treff.</p>`;
  }

  function renderInlineDetail(w) {
    const ctx = S.context?.[w.id] || {};
    const sims = topNeighbors(w.id, 6);
    const citedBy = (ctx.cited_by || []).map((id) => S.byId.get(id)).filter(Boolean).slice(0, 6);
    const cites = (ctx.cites || []).map((id) => S.byId.get(id)).filter(Boolean).slice(0, 6);

    return `
      <div class="inline-detail">
        <div class="detail-cols">
          <div class="detail-sec">
            <h4>Næraste verk i vektorrommet</h4>
            ${sims.map(({ w: sw, c }) => `
              <div class="detail-row">
                <span>
                  <a href="#" data-jump="${esc(sw.id)}">${esc(sw.year ? sw.year + " · " : "")}${esc(sw.title)}</a>
                  ${sw.pdf ? ` · <a class="act-pdf" href="${esc(sw.pdf)}" target="_blank" rel="noopener">PDF</a>` : ""}
                </span>
                <span class="score">${c.toFixed(2)}</span>
              </div>`).join("") || `<div class="detail-row" style="color:var(--dim);">Lastar vektorindeks…</div>`}
          </div>
          <div class="detail-sec">
            <h4>Siteringskoplingar i korpuset (${(ctx.cited_by || []).length} inn, ${(ctx.cites || []).length} ut)</h4>
            ${citedBy.map((cw) => `<div class="detail-row"><span>Sitert av: <a href="#" data-jump="${esc(cw.id)}">${esc(cw.year ? cw.year + " · " : "")}${esc(cw.title)}</a></span></div>`).join("")}
            ${cites.map((cw) => `<div class="detail-row"><span>Siterer: <a href="#" data-jump="${esc(cw.id)}">${esc(cw.year ? cw.year + " · " : "")}${esc(cw.title)}</a></span></div>`).join("")}
            ${!citedBy.length && !cites.length ? `<div class="detail-row" style="color:var(--dim);">${esc(w.id)} · ${esc(w.source || "")}</div>` : ""}
          </div>
        </div>
      </div>`;
  }

  /* KANON */
  async function renderCitations() {
    const q = $("citQ").value.trim().toLowerCase();
    const box = $("citBox");

    if (S.citSub === "internal") {
      const rows = (S.analysis?.citations?.top_internally_cited || []).filter((r) => !q || `${r.title} ${(r.authors || []).join(" ")}`.toLowerCase().includes(q));
      box.innerHTML = rows.map((r) => {
        const sub = [(r.authors || []).join(", "), `${fmt(r.internal_citations)} nordiske sit.`, `${fmt(r.global_citations)} globalt`].filter(Boolean).join(" · ");
        return `
          <article class="item">
            <div class="meta-col">${esc(r.year || "")}${(r.countries || []).length ? `<br>${esc(r.countries.join(", "))}` : ""}</div>
            <div>
              <h3 class="title"><button class="title-btn" type="button" data-jump="${esc(r.id)}">${esc(r.title)}</button></h3>
              <p class="subline">${esc(sub)}</p>
            </div>
            <div class="actions">${r.pdf ? `<a class="act-pdf" href="${esc(r.pdf)}" target="_blank" rel="noopener">PDF</a>` : ""}</div>
          </article>`;
      }).join("");
      return;
    }

    if (S.citSub === "canon") {
      if (!S.canon) S.canon = (await jget("data/cited_canon.json", { items: [] })).items || [];
      const rows = S.canon.filter((r) => !q || `${r.title} ${r.authors}`.toLowerCase().includes(q)).slice(0, 150);
      box.innerHTML = rows.map((r) => {
        const sub = [r.authors, `Sitert ${fmt(r.nordic_citing_count)} gonger frå Norden`, `${fmt(r.global_citations)} globalt`].filter(Boolean).join(" · ");
        const doiHref = r.doi ? (r.doi.startsWith("http") ? r.doi : `https://doi.org/${r.doi}`) : "";
        return `
          <article class="item">
            <div class="meta-col">${esc(r.year || "")}</div>
            <div>
              <h3 class="title">${esc(r.title)}</h3>
              <p class="subline">${esc(sub)}</p>
            </div>
            <div class="actions">${doiHref ? `<a href="${esc(doiHref)}" target="_blank" rel="noopener">DOI</a>` : ""}</div>
          </article>`;
      }).join("");
      return;
    }

    if (S.citSub === "authors") {
      if (!S.authors) S.authors = (await jget("data/authors.json", { items: [] })).items || [];
      const rows = S.authors.filter((a) => !q || `${a.name} ${(a.institutions || []).join(" ")}`.toLowerCase().includes(q)).slice(0, 120);
      box.innerHTML = rows.map((a) => {
        const sub = [(a.institutions || []).slice(0, 2).join(", "), `${fmt(a.works)} verk`, `${fmt(a.openalex_citation_sum_on_snapshot_works)} sit.`].filter(Boolean).join(" · ");
        return `
          <article class="item">
            <div class="meta-col">${esc((a.countries || []).join(", "))}</div>
            <div>
              <h3 class="title"><button class="title-btn" type="button" data-author="${esc(a.name)}">${esc(a.name)}</button></h3>
              <p class="subline">${esc(sub)}</p>
            </div>
            <div class="actions"></div>
          </article>`;
      }).join("");
      return;
    }

    if (S.citSub === "institutions") {
      if (!S.insts) S.insts = (await jget("data/institutions.json", { items: [] })).items || [];
      const rows = S.insts.filter((i) => !q || `${i.name} ${i.country}`.toLowerCase().includes(q)).slice(0, 120);
      box.innerHTML = rows.map((i) => `
        <article class="item">
          <div class="meta-col">${esc(i.country || "")}</div>
          <div>
            <h3 class="title">${esc(i.name)}</h3>
            <p class="subline">${fmt(i.works)} designteoretiske verk</p>
          </div>
          <div class="actions"></div>
        </article>`).join("");
    }
  }

  /* SEMANTISK KART */
  async function ensureMap() {
    if (!S.semMap) {
      S.semMap = await jget("data/semantic_map.json", { clusters: [], points: [] });
      renderLegend();
    }
    requestAnimationFrame(drawMap);
  }

  function renderLegend() {
    const cs = S.semMap?.clusters || [];
    const total = S.semMap?.points?.length || 0;
    $("mapLegend").innerHTML =
      `<div class="cluster-row ${S.clusterFilter === -1 ? "active" : ""}" data-cl="-1"><span><span class="swatch" style="background:var(--dim);"></span>Alle klynger</span><span>${fmt(total)}</span></div>` +
      cs.map((c, i) => `<div class="cluster-row ${S.clusterFilter === c.id ? "active" : ""}" data-cl="${c.id}"><span><span class="swatch" style="background:${COLORS[i % COLORS.length]};"></span>${esc(c.label)}</span><span>${fmt(c.size || "")}</span></div>`).join("");
  }

  function drawMap() {
    const cv = $("semCanvas");
    if (!cv || !S.semMap) return;
    cv.style.touchAction = S.zoom > 1.05 ? "none" : "pan-y pinch-zoom";
    const dpr = window.devicePixelRatio || 1;
    const rect = cv.getBoundingClientRect();
    const W = Math.max(280, rect.width), H = rect.height || 340;
    cv.width = W * dpr; cv.height = H * dpr;
    const ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    const css = getComputedStyle(document.documentElement);
    const bg = css.getPropertyValue("--bg").trim() || "#fff";
    const dim = css.getPropertyValue("--dim").trim() || "#767676";
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    const mode = $("mapMode").value;
    const pts = S.semMap.points || [];
    const cx = W / 2 + S.panX, cy = H / 2 + S.panY, sc = Math.min(W, H) * 0.36 * S.zoom;
    for (const p of pts) {
      if (S.clusterFilter !== -1 && p.c !== S.clusterFilter) continue;
      const sx = cx + p.x * sc, sy = cy - p.y * sc;
      p._sx = sx; p._sy = sy;
      if (sx < -4 || sx > W + 4 || sy < -4 || sy > H + 4) continue;
      ctx.fillStyle = mode === "country" ? (CC_COLORS[p.cc] || dim) : mode === "pdf" ? (p.pdf ? css.getPropertyValue("--fg").trim() : dim) : COLORS[p.c % COLORS.length];
      ctx.globalAlpha = p.pdf ? 0.92 : 0.65;
      ctx.beginPath();
      ctx.arc(sx, sy, p.pdf ? 2.9 : 2.1, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function pickPoint(mx, my) {
    let best = null, bd = 196;
    for (const p of S.semMap?.points || []) {
      if (S.clusterFilter !== -1 && p.c !== S.clusterFilter) continue;
      const d2 = (p._sx - mx) ** 2 + (p._sy - my) ** 2;
      if (d2 < bd) { bd = d2; best = p; }
    }
    if (best) {
      const w = S.byId.get(best.id);
      const yr = w?.year ? `${w.year} · ` : "";
      const au = (w?.authors || []).slice(0, 3).join(", ");
      $("mapSelectedBar").innerHTML = `<strong>${esc(yr)}${esc(w?.title || best.id)}</strong>${au ? ` · ${esc(au)}` : ""} · <a href="#" data-jump="${esc(best.id)}">Opne i katalog</a>${w?.pdf ? ` · <a class="act-pdf" href="${esc(w.pdf)}" target="_blank" rel="noopener">PDF</a>` : ""}`;
    }
  }

  /* ANALYSE */
  function renderAnalysis() {
    const a = S.analysis;
    if (!a) return;
    const decs = a.decades || [];
    const maxD = Math.max(1, ...decs.map((d) => d.total + (d.nordic_archives || 0)));
    const cs = a.countries || [];
    const cls = a.semantic_clusters || [];
    const vens = (a.top_venues || []).slice(0, 15);

    $("anaRoot").innerHTML = `
      <div class="ana-grid">
        <div class="ana-sec">
          <h3>Publikasjonar og PDF per tiår</h3>
          ${decs.map((d) => {
            const tot = d.total + (d.nordic_archives || 0);
            return `<div class="bar-line"><span>${esc(d.decade)}</span><div class="bar-bg"><div class="bar-a" style="width:${((tot / maxD) * 100).toFixed(1)}%"></div><div class="bar-b" style="width:${((d.pdfs / maxD) * 100).toFixed(1)}%"></div></div><span class="r">${fmt(tot)} (${fmt(d.pdfs)})</span></div>`;
          }).join("")}
        </div>
        <div class="ana-sec">
          <h3>Landfordeling</h3>
          <div class="table-wrap">
            <table class="tbl-clean">
              <thead><tr><th>Land</th><th class="r">OpenAlex</th><th class="r">Arkiv</th><th class="r">PDF</th><th class="r">OA</th></tr></thead>
              <tbody>${cs.map((c) => `<tr><td><strong>${esc(c.country)}</strong></td><td class="r">${fmt(c.openalex_works)}</td><td class="r">${fmt(c.nordic_archive_records)}</td><td class="r"><strong>${fmt(c.pdfs)}</strong></td><td class="r">${((c.oa_share || 0) * 100).toFixed(0)}%</td></tr>`).join("")}</tbody>
            </table>
          </div>
        </div>
        <div class="ana-sec">
          <h3>Tematiske klynger</h3>
          <div class="table-wrap">
            <table class="tbl-clean">
              <thead><tr><th>Klynge</th><th class="r">Verk</th><th class="r">PDF</th></tr></thead>
              <tbody>${cls.map((c) => `<tr><td><strong>${esc(c.label)}</strong><div style="font-size:11.5px;color:var(--dim);">${esc((c.keywords || []).slice(0, 5).join(", "))}</div></td><td class="r">${fmt(c.core_works)}</td><td class="r">${fmt(c.pdfs)}</td></tr>`).join("")}</tbody>
            </table>
          </div>
        </div>
        <div class="ana-sec">
          <h3>Tidsskrift og konferansar</h3>
          <div class="table-wrap">
            <table class="tbl-clean">
              <thead><tr><th>Kanal</th><th class="r">Verk</th><th class="r">PDF</th><th class="r">Sit.</th></tr></thead>
              <tbody>${vens.map((v) => `<tr><td><strong>${esc(v.venue)}</strong></td><td class="r">${fmt(v.auto_included)}</td><td class="r">${fmt(v.pdfs)}</td><td class="r">${fmt(v.citations)}</td></tr>`).join("")}</tbody>
            </table>
          </div>
        </div>
      </div>`;
  }

  function setTab(t) {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === t));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${t}`));
    history.replaceState(null, "", `#${t}`);
    if (t === "siteringar") renderCitations();
    if (t === "kart") ensureMap();
  }

  function jumpToWorkInline(wid) {
    const w = S.byId.get(wid);
    if (!w) return;
    $("qInput").value = w.title || wid;
    S.pdfOnly = false;
    $("ccSel").value = "";
    $("eraSel").value = "";
    $("presetSel").value = "";
    S.semScores = null;
    S.expandedId = wid;
    setTab("korpus");
    filterCorpus();
  }

  function bind() {
    document.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", (e) => {
      e.preventDefault();
      setTab(b.dataset.tab);
    }));

    const hdr = document.querySelector("header");
    const stick = () => hdr.classList.toggle("stuck", window.scrollY > 2);
    window.addEventListener("scroll", stick, { passive: true });
    stick();

    $("metricAllBtn").addEventListener("click", () => { S.pdfOnly = false; filterCorpus(); });
    $("metricPdfBtn").addEventListener("click", () => { S.pdfOnly = !S.pdfOnly; filterCorpus(); });

    let tmr = null;
    $("qInput").addEventListener("input", () => {
      clearTimeout(tmr);
      tmr = setTimeout(() => {
        if (S.semScores && $("presetSel").value === "") S.semScores = null;
        filterCorpus();
      }, 90);
    });
    $("qInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        $("qInput").blur();
        filterCorpus();
      }
    });

    $("resetBtn").addEventListener("click", () => {
      $("qInput").value = ""; S.pdfOnly = false; $("presetSel").value = "";
      $("ccSel").value = ""; $("eraSel").value = "";
      $("sortSel").value = "relevance"; S.semScores = null; S.expandedId = null;
      filterCorpus();
    });

    for (const id of ["ccSel", "eraSel", "sortSel"]) $(id).addEventListener("change", filterCorpus);

    $("presetSel").addEventListener("change", (e) => {
      const k = e.target.value;
      if (!k || !S.semMeta?.presets?.[k]) { S.semScores = null; filterCorpus(); return; }
      S.semScores = cosineAll(S.semMeta.presets[k]);
      S.semLabel = `Tema: ${e.target.options[e.target.selectedIndex].text}`;
      $("sortSel").value = "relevance";
      filterCorpus();
    });
    $("clearSemBtn").addEventListener("click", () => { S.semScores = null; $("presetSel").value = ""; filterCorpus(); });

    $("moreCorpusBtn").addEventListener("click", () => { S.shown += STEP; renderCorpus(); });

    document.querySelectorAll(".sub-pill").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll(".sub-pill").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      S.citSub = b.dataset.sub;
      renderCitations();
    }));
    $("citQ").addEventListener("input", renderCitations);

    $("mapMode").addEventListener("change", drawMap);
    $("mapReset").addEventListener("click", () => { S.zoom = 1; S.panX = 0; S.panY = 0; drawMap(); });
    $("mapLegend").addEventListener("click", (e) => {
      const el = e.target.closest("[data-cl]");
      if (!el) return;
      S.clusterFilter = parseInt(el.dataset.cl, 10);
      renderLegend();
      drawMap();
    });

    const cv = $("semCanvas");
    window.addEventListener("resize", () => { if ($("view-kart").classList.contains("active")) drawMap(); });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if ($("view-kart").classList.contains("active")) drawMap(); });
    cv.addEventListener("wheel", (e) => {
      e.preventDefault();
      S.zoom = Math.min(12, Math.max(0.8, S.zoom * (e.deltaY < 0 ? 1.18 : 0.85)));
      drawMap();
    }, { passive: false });

    let drag = false, lx = 0, ly = 0, moved = false, pinchDist = 0;
    cv.addEventListener("mousedown", (e) => { drag = true; moved = false; lx = e.clientX; ly = e.clientY; });
    window.addEventListener("mouseup", () => { drag = false; });
    cv.addEventListener("mousemove", (e) => {
      if (!drag) return;
      const dx = e.clientX - lx, dy = e.clientY - ly;
      if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      S.panX += dx; S.panY += dy; lx = e.clientX; ly = e.clientY; drawMap();
    });
    cv.addEventListener("click", (e) => {
      if (moved) return;
      const r = cv.getBoundingClientRect();
      pickPoint(e.clientX - r.left, e.clientY - r.top);
    });

    cv.addEventListener("touchstart", (e) => {
      if (e.touches.length === 1) {
        moved = false;
        lx = e.touches[0].clientX;
        ly = e.touches[0].clientY;
        drag = S.zoom > 1.05;
      } else if (e.touches.length === 2) {
        drag = false;
        moved = true;
        pinchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      }
    }, { passive: true });
    cv.addEventListener("touchmove", (e) => {
      if (e.touches.length === 2 && pinchDist > 0) {
        e.preventDefault();
        const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
        S.zoom = Math.min(12, Math.max(0.8, S.zoom * (d / pinchDist)));
        pinchDist = d;
        drawMap();
      } else if (e.touches.length === 1) {
        const dx = e.touches[0].clientX - lx, dy = e.touches[0].clientY - ly;
        if (Math.abs(dx) + Math.abs(dy) > 6) moved = true;
        if (drag && S.zoom > 1.05) {
          e.preventDefault();
          S.panX += dx; S.panY += dy; lx = e.touches[0].clientX; ly = e.touches[0].clientY;
          drawMap();
        }
      }
    }, { passive: false });
    cv.addEventListener("touchend", (e) => {
      if (!moved && e.changedTouches.length === 1 && e.touches.length === 0) {
        const r = cv.getBoundingClientRect();
        pickPoint(e.changedTouches[0].clientX - r.left, e.changedTouches[0].clientY - r.top);
      }
      drag = false; pinchDist = 0;
    });

    document.body.addEventListener("click", (e) => {
      const sim = e.target.closest("[data-sim]");
      if (sim) { e.preventDefault(); triggerSimilar(sim.dataset.sim); return; }
      const jmp = e.target.closest("[data-jump]");
      if (jmp) { e.preventDefault(); jumpToWorkInline(jmp.dataset.jump); return; }
      const aut = e.target.closest("[data-author]");
      if (aut) { e.preventDefault(); $("qInput").value = aut.dataset.author; S.semScores = null; setTab("korpus"); filterCorpus(); return; }
      const tog = e.target.closest("[data-toggle]");
      if (tog) {
        const id = tog.dataset.toggle;
        S.expandedId = S.expandedId === id ? null : id;
        renderCorpus();
      }
    });
  }

  init();
})();
