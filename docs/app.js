/* DESIGNTEORI — Nordic Typographic Workbench (Zero Popups, Load-More, Google Embeddings) */
(() => {
  "use strict";

  const STEP = 50;
  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1"];
  const CC_COLORS = { NO: "#3b82f6", SE: "#eab308", DK: "#ef4444", FI: "#06b6d4", IS: "#a855f7" };

  const HERO_COPY = {
    korpus: [
      "Open forsking / Nordisk designteori 1900–2026",
      "Designteori.",
      "Søkbar database for nordisk designteori og designforsking på tvers av Noreg, Sverige, Danmark, Finland og Island — med fulltekst-PDF, siteringsnettverk og Google-embeddingar.",
    ],
    pdf: [
      "Open forsking / Dokumenttilgang",
      "Fulltekst.",
      "SHA-256-verifiserte Open Access fulltekst-PDF-ar lagra direkte i repoet under pdf/, med direkte lenkjer til opne originalkjelder.",
    ],
    siteringar: [
      "Open forsking / Siteringsnettverk & Kanon",
      "Kanon.",
      "Dei mest siterte nordiske designpublikasjonane, den internasjonale grunnlagskanonen sitert frå Norden, samt sentrale forfattarar og institusjonar.",
    ],
    kart: [
      "Open forsking / Google EmbeddingGemma-300M",
      "Semantisk kart.",
      "To-dimensjonal projeksjon av heile det nordiske korpuset bygd frå Google EmbeddingGemma-300M-vektorar og delt inn i ti tematiske klynger.",
    ],
    analyse: [
      "Open forsking / Bibliometri & Historikk",
      "Analyse.",
      "Historisk utvikling frå 1900 til 2026, landfordeling, tematisk struktur og dei viktigaste nordiske og internasjonale publiseringskanalane.",
    ],
  };

  const S = {
    works: [],
    byId: new Map(),
    pdfs: [],
    analysis: null,
    context: null,
    canon: null,
    authors: null,
    insts: null,
    semMeta: null,
    semVecs: null,
    semIdx: new Map(),
    semMap: null,
    wasm: null,

    filtered: [],
    shown: STEP,
    expandedId: null,
    semScores: null,
    semLabel: "",

    pdfFiltered: [],
    pdfShown: STEP,
    citSub: "internal",

    clusterFilter: -1,
    zoom: 1,
    panX: 0,
    panY: 0,
  };

  const $ = (id) => document.getElementById(id);
  const fmt = (n) => (typeof n === "number" ? n.toLocaleString("nn-NO") : "—");
  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  async function jget(u, fb = null) {
    try { const r = await fetch(u); return r.ok ? await r.json() : fb; } catch { return fb; }
  }

  async function init() {
    bind();
    const [pubs, nordic, ana, pkat] = await Promise.all([
      jget("data/publications.json", []),
      jget("data/nordic_additions.json", []),
      jget("data/analysis.json", null),
      jget("data/pdf_katalog.json", { items: [], stats: {} }),
    ]);

    for (const w of pubs) {
      w._layer = "openalex";
      w._q = `${w.title || ""} ${(w.authors || []).join(" ")} ${w.source || ""} ${w.doi || ""} ${w.topic || ""}`.toLowerCase();
      S.works.push(w);
      S.byId.set(w.id, w);
    }
    for (const w of nordic) {
      w._layer = "nordic";
      w._q = `${w.title || ""} ${(w.authors || []).join(" ")} ${w.source || ""} ${w.doi || ""}`.toLowerCase();
      S.works.push(w);
      S.byId.set(w.id, w);
    }

    S.analysis = ana;
    S.pdfs = pkat.items || [];
    const ov = ana?.overview || {};
    const repoPdfCnt = ov.repo_pdf_files ?? S.works.filter((w) => w.pdf).length;
    const totalW = ov.total_searchable_works ?? S.works.length;
    $("stWorks").textContent = fmt(totalW);
    $("stPdfs").textContent = fmt(repoPdfCnt);
    $("stEmb").textContent = fmt(ov.google_embedded_works || totalW);
    $("stInc").textContent = fmt(ov.openalex_auto_included ?? S.works.filter((w) => w.scope === "automatic-title-inclusion").length);

    filterCorpus();
    filterPdfs();
    renderAnalysis();
    loadVectors();

    const h = (location.hash || "").replace("#", "");
    if (HERO_COPY[h]) setTab(h);
  }

  async function loadVectors() {
    const m = await jget("data/semantic_index.json", null);
    if (!m?.ids) return;
    try {
      const r = await fetch("data/semantic_vectors.bin");
      if (!r.ok) return;
      const v = new Int8Array(await r.arrayBuffer());
      if (v.length !== m.ids.length * m.dimensions) return;
      S.semMeta = m;
      S.semVecs = v;
      m.ids.forEach((id, i) => S.semIdx.set(id, i));
      if (m.ids.length) $("stEmb").textContent = fmt(m.ids.length);
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
    S.semLabel = `Semantisk liknande til «${(S.byId.get(wid)?.title || wid).slice(0, 75)}»`;
    $("sortSel").value = "relevance";
    setTab("korpus");
    filterCorpus();
  }

  async function runWasmQuery() {
    const q = $("qInput").value.trim();
    if (!q || !S.semVecs) return;
    const btn = $("wasmBtn");
    const orig = btn.textContent;
    try {
      btn.disabled = true;
      if (!S.wasm) {
        btn.textContent = "Lastar modell …";
        const { pipeline, env } = await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.4.0");
        env.allowLocalModels = false;
        S.wasm = await pipeline("feature-extraction", S.semMeta.onnx_web_model || "onnx-community/embeddinggemma-300m-ONNX", { dtype: "q8" });
      }
      btn.textContent = "Søkjer …";
      const out = await S.wasm(`task: search result | query: ${q}`, { pooling: "none" });
      const D = S.semMeta.dimensions, qv = new Float32Array(D);
      for (let d = 0; d < D; d++) qv[d] = out.data[d] || 0;
      S.semScores = cosineAll(qv);
      S.semLabel = `Google EmbeddingGemma-søk: «${q}»`;
      $("sortSel").value = "relevance";
      filterCorpus();
    } catch (e) {
      console.error(e);
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  }

  function filterCorpus() {
    const q = $("qInput").value.trim().toLowerCase();
    const toks = q ? q.split(/\s+/).filter(Boolean) : [];
    const acc = $("accessSel").value;
    const layer = $("layerSel").value;
    const cc = $("ccSel").value;
    const era = $("eraSel").value;
    const sort = $("sortSel").value;

    $("semBanner").hidden = !S.semScores;
    if (S.semScores) $("semBannerTxt").textContent = S.semLabel;

    const out = [];
    for (const w of S.works) {
      if (acc === "repo" && !w.pdf) continue;
      if (acc === "oa" && !w.pdf && !w.oa_url) continue;
      if (layer === "nordic" && w._layer !== "nordic") continue;
      if (layer !== "all" && layer !== "nordic" && w.scope !== layer) continue;
      if (cc && !(w.countries || []).includes(cc) && w.source_country !== cc) continue;
      if (era) {
        const y = w.year;
        if (!y) continue;
        if (era === "pre2000" && y >= 2000) continue;
        if (era === "2000-2009" && (y < 2000 || y > 2009)) continue;
        if (era === "2010-2019" && (y < 2010 || y > 2019)) continue;
        if (era === "2020-2026" && y < 2020) continue;
      }
      if (!S.semScores && toks.length) {
        let ok = true;
        for (const t of toks) if (!w._q.includes(t)) { ok = false; break; }
        if (!ok) continue;
      }
      out.push(w);
    }

    if (sort === "citations") out.sort((a, b) => (b.citations || 0) - (a.citations || 0));
    else if (sort === "year_desc") out.sort((a, b) => (b.year || 0) - (a.year || 0));
    else if (sort === "year_asc") out.sort((a, b) => (a.year || 9999) - (b.year || 9999));
    else if (S.semScores) out.sort((a, b) => (S.semScores.get(b.id) || -1) - (S.semScores.get(a.id) || -1));
    else if (toks.length) {
      out.sort((a, b) => {
        const at = (a.title || "").toLowerCase(), bt = (b.title || "").toLowerCase();
        const ah = toks.reduce((s, t) => s + (at.includes(t) ? 1 : 0), 0);
        const bh = toks.reduce((s, t) => s + (bt.includes(t) ? 1 : 0), 0);
        return bh !== ah ? bh - ah : (b.citations || 0) - (a.citations || 0);
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
    $("hitCount").textContent = `Viser ${fmt(rows.length)} av ${fmt(N)} publikasjonar`;
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

      const tags = [];
      if (w.pdf) tags.push(`<span class="tag checked">PDF i repo</span>`);
      if (typeof cos === "number") tags.push(`<span class="tag checked">Likskap ${cos.toFixed(2)}</span>`);
      if (cc) tags.push(`<span class="tag">${esc(cc)}</span>`);
      if (typeof w.citations === "number" && w.citations > 0) tags.push(`<span class="tag">${fmt(w.citations)} sit.</span>`);

      return `
        <article class="item">
          <div class="year">${esc(w.year || "—")}</div>
          <div>
            <h3 class="title"><button class="title-btn" type="button" data-toggle="${esc(w.id)}">${esc(w.title || "(utan tittel)")}</button></h3>
            ${auth ? `<p class="byline">${esc(auth)}</p>` : ""}
            ${w.source ? `<p class="source">${esc(w.source)}</p>` : ""}
            <div class="tags">${tags.join("")}</div>
          </div>
          <div class="links">
            ${w.pdf ? `<a href="${esc(w.pdf)}" target="_blank" rel="noopener"><strong>Opne PDF</strong></a>` : (w.oa_url ? `<a href="${esc(w.oa_url)}" target="_blank" rel="noopener">Originalkjelde</a>` : "")}
            ${doiHref ? `<a href="${esc(doiHref)}" target="_blank" rel="noopener">DOI</a>` : ""}
            ${S.semIdx.has(w.id) ? `<button type="button" data-sim="${esc(w.id)}">Liknande verk</button>` : ""}
          </div>
          ${isExp ? renderInlineDetail(w) : ""}
        </article>`;
    }).join("") || `<p style="padding:28px 0;color:var(--muted);">Ingen publikasjonar trefte filteret.</p>`;
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
            <h3>Semantisk næraste verk (Google EmbeddingGemma)</h3>
            ${sims.map(({ w: sw, c }) => `
              <div class="detail-row">
                <span class="tag">${c.toFixed(2)}</span>
                <a href="#" data-jump="${esc(sw.id)}">${esc(sw.year || "")} · ${esc(sw.title)}</a>
                ${sw.pdf ? ` — <a href="${esc(sw.pdf)}" target="_blank" rel="noopener"><strong>PDF</strong></a>` : ""}
              </div>`).join("") || `<div class="detail-row" style="color:var(--muted);">Vektorindeks lastar …</div>`}
          </div>
          <div class="detail-sec">
            <h3>Siteringskoplingar i Norden (${(ctx.cited_by || []).length} inn / ${(ctx.cites || []).length} ut)</h3>
            ${citedBy.map((cw) => `<div class="detail-row">← Sitert av: <a href="#" data-jump="${esc(cw.id)}">${esc(cw.year || "")} · ${esc(cw.title)}</a></div>`).join("")}
            ${cites.map((cw) => `<div class="detail-row">→ Siterer: <a href="#" data-jump="${esc(cw.id)}">${esc(cw.year || "")} · ${esc(cw.title)}</a></div>`).join("")}
            ${!citedBy.length && !cites.length ? `<div class="detail-row" style="color:var(--muted);">ID: ${esc(w.id)} · Lag: ${esc(w.scope || w._layer)}${w.kind ? " · Type: " + esc(w.kind) : ""}</div>` : ""}
          </div>
        </div>
      </div>`;
  }

  /* FULLTEKST / PDF */
  function filterPdfs() {
    const q = $("pdfQ").value.trim().toLowerCase();
    const mode = $("pdfMode").value;
    const cc = $("pdfCc").value;
    S.pdfFiltered = S.pdfs.filter((it) => {
      if (mode === "repo" && !it.pdf_in_repo) return false;
      if (cc && !(it.country_affiliations || []).includes(cc)) return false;
      if (q && !`${it.title} ${(it.authors || []).join(" ")} ${it.source} ${it.doi} ${it.document_sha256}`.toLowerCase().includes(q)) return false;
      return true;
    });
    S.pdfShown = STEP;
    renderPdfs();
  }

  function renderPdfs() {
    const N = S.pdfFiltered.length;
    const slice = S.pdfFiltered.slice(0, S.pdfShown);
    $("pdfCount").textContent = `Viser ${fmt(slice.length)} av ${fmt(N)} dokument`;
    $("morePdfBtn").hidden = slice.length >= N;

    $("pdfList").innerHTML = slice.map((it) => {
      const u = it.public_pdf_url || it.oa_location_unverified || "";
      const mb = it.document_bytes ? (it.document_bytes / 1e6).toFixed(1) + " MB" : "";
      const cc = (it.country_affiliations || []).join(", ");
      return `
        <article class="item">
          <div class="year">${esc(it.year || "—")}</div>
          <div>
            <h3 class="title"><a href="${esc(u || "#")}" ${u ? `target="_blank" rel="noopener"` : ""}>${esc(it.title)}</a></h3>
            <p class="byline">${esc((it.authors || []).slice(0, 4).join(", "))}</p>
            ${it.source ? `<p class="source">${esc(it.source)}</p>` : ""}
            <div class="tags">
              ${it.pdf_in_repo ? `<span class="tag checked">PDF i repo</span>` : `<span class="tag">OA-kjelde</span>`}
              ${mb ? `<span class="tag">${esc(mb)}</span>` : ""}
              ${cc ? `<span class="tag">${esc(cc)}</span>` : ""}
            </div>
          </div>
          <div class="links">
            ${u ? `<a href="${esc(u)}" target="_blank" rel="noopener"><strong>${it.pdf_in_repo ? "Opne PDF" : "Originalkjelde"}</strong></a>` : ""}
            <button type="button" data-jump="${esc(it.id)}">Vis i katalog</button>
          </div>
        </article>`;
    }).join("") || `<p style="padding:28px 0;color:var(--muted);">Ingen dokument trefte filteret.</p>`;
  }

  /* KANON & SITERINGAR */
  async function renderCitations() {
    const q = $("citQ").value.trim().toLowerCase();
    const box = $("citBox");

    if (S.citSub === "internal") {
      const rows = (S.analysis?.citations?.top_internally_cited || []).filter((r) => !q || `${r.title} ${(r.authors || []).join(" ")}`.toLowerCase().includes(q));
      box.innerHTML = rows.map((r) => `
        <article class="item">
          <div class="year">${esc(r.year || "—")}</div>
          <div>
            <h3 class="title"><button class="title-btn" type="button" data-jump="${esc(r.id)}">${esc(r.title)}</button></h3>
            <p class="byline">${esc((r.authors || []).join(", "))}</p>
            <div class="tags">
              <span class="tag checked">${fmt(r.internal_citations)} nordiske siteringar</span>
              <span class="tag">${fmt(r.global_citations)} globalt</span>
              ${(r.countries || []).length ? `<span class="tag">${esc(r.countries.join(", "))}</span>` : ""}
            </div>
          </div>
          <div class="links">
            ${r.pdf ? `<a href="${esc(r.pdf)}" target="_blank" rel="noopener"><strong>Opne PDF</strong></a>` : ""}
            <button type="button" data-jump="${esc(r.id)}">Vis i katalog</button>
          </div>
        </article>`).join("");
      return;
    }

    if (S.citSub === "canon") {
      if (!S.canon) S.canon = (await jget("data/cited_canon.json", { items: [] })).items || [];
      const rows = S.canon.filter((r) => !q || `${r.title} ${r.authors}`.toLowerCase().includes(q)).slice(0, 150);
      box.innerHTML = rows.map((r) => `
        <article class="item">
          <div class="year">${esc(r.year || "—")}</div>
          <div>
            <h3 class="title">${esc(r.title)}</h3>
            <p class="byline">${esc(r.authors || "")}</p>
            <div class="tags">
              <span class="tag checked">Sitert ${fmt(r.nordic_citing_count)}× frå Norden</span>
              <span class="tag">${fmt(r.global_citations)} globalt</span>
            </div>
          </div>
          <div class="links">
            ${r.doi ? `<a href="${esc(r.doi)}" target="_blank" rel="noopener">DOI</a>` : ""}
          </div>
        </article>`).join("");
      return;
    }

    if (S.citSub === "authors") {
      if (!S.authors) S.authors = (await jget("data/authors.json", { items: [] })).items || [];
      const rows = S.authors.filter((a) => !q || `${a.name} ${(a.institutions || []).join(" ")}`.toLowerCase().includes(q)).slice(0, 120);
      box.innerHTML = rows.map((a) => `
        <article class="item">
          <div class="year">${esc((a.countries || []).join(",") || "—")}</div>
          <div>
            <h3 class="title"><button class="title-btn" type="button" data-author="${esc(a.name)}">${esc(a.name)}</button></h3>
            <p class="byline">${esc((a.institutions || []).slice(0, 3).join(" · "))}</p>
            <div class="tags">
              <span class="tag checked">${fmt(a.automatically_title_included)} tittelinkluderte</span>
              <span class="tag">${fmt(a.works)} verk</span>
              <span class="tag">${fmt(a.openalex_citation_sum_on_snapshot_works)} sit.</span>
            </div>
          </div>
          <div class="links"><button type="button" data-author="${esc(a.name)}">Filtrer katalog</button></div>
        </article>`).join("");
      return;
    }

    if (S.citSub === "institutions") {
      if (!S.insts) S.insts = (await jget("data/institutions.json", { items: [] })).items || [];
      const rows = S.insts.filter((i) => !q || `${i.name} ${i.country}`.toLowerCase().includes(q)).slice(0, 120);
      box.innerHTML = rows.map((i) => `
        <article class="item">
          <div class="year">${esc(i.country || "—")}</div>
          <div>
            <h3 class="title">${esc(i.name)}</h3>
            <div class="tags">
              <span class="tag checked">${fmt(i.automatically_title_included)} tittelinkluderte</span>
              <span class="tag">${fmt(i.works)} verk totalt</span>
            </div>
          </div>
          <div class="links"></div>
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
      `<div class="cluster-row ${S.clusterFilter === -1 ? "active" : ""}" data-cl="-1"><span><span class="swatch" style="background:#888;"></span>Alle klynger</span><span>${fmt(total)}</span></div>` +
      cs.map((c, i) => `<div class="cluster-row ${S.clusterFilter === c.id ? "active" : ""}" data-cl="${c.id}"><span><span class="swatch" style="background:${COLORS[i % COLORS.length]};"></span>${esc(c.label)}</span><span>${fmt(c.size || "")}</span></div>`).join("");
  }

  function drawMap() {
    const cv = $("semCanvas");
    if (!cv || !S.semMap) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = cv.getBoundingClientRect();
    const W = Math.max(300, rect.width), H = rect.height || 360;
    cv.width = W * dpr; cv.height = H * dpr;
    const ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#141413";
    ctx.fillRect(0, 0, W, H);

    const mode = $("mapMode").value;
    const pts = S.semMap.points || [];
    const cx = W / 2 + S.panX, cy = H / 2 + S.panY, sc = Math.min(W, H) * 0.36 * S.zoom;
    for (const p of pts) {
      if (S.clusterFilter !== -1 && p.c !== S.clusterFilter) continue;
      const sx = cx + p.x * sc, sy = cy - p.y * sc;
      p._sx = sx; p._sy = sy;
      if (sx < -4 || sx > W + 4 || sy < -4 || sy > H + 4) continue;
      ctx.fillStyle = mode === "country" ? (CC_COLORS[p.cc] || "#888") : mode === "pdf" ? (p.pdf ? "#10b981" : "#52524e") : COLORS[p.c % COLORS.length];
      ctx.globalAlpha = p.pdf ? 0.92 : 0.62;
      ctx.beginPath();
      ctx.arc(sx, sy, p.pdf ? 2.8 : 2.0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function pickPoint(mx, my) {
    let best = null, bd = 144;
    for (const p of S.semMap?.points || []) {
      if (S.clusterFilter !== -1 && p.c !== S.clusterFilter) continue;
      const d2 = (p._sx - mx) ** 2 + (p._sy - my) ** 2;
      if (d2 < bd) { bd = d2; best = p; }
    }
    if (best) {
      const w = S.byId.get(best.id);
      $("mapSelectedBar").innerHTML = `<strong>${esc(w?.year || "")} · ${esc(w?.title || best.id)}</strong> — ${esc((w?.authors || []).slice(0, 3).join(", "))} · <a href="#" data-jump="${esc(best.id)}">Vis i katalog</a> ${w?.pdf ? `· <a href="${esc(w.pdf)}" target="_blank" rel="noopener"><strong>Opne PDF</strong></a>` : ""}`;
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
          <h3>Publikasjonar og PDF per tiår (1900–2026)</h3>
          ${decs.map((d) => {
            const tot = d.total + (d.nordic_archives || 0);
            return `<div class="bar-line"><span>${esc(d.decade)}</span><div class="bar-bg"><div class="bar-a" style="width:${((tot / maxD) * 100).toFixed(1)}%"></div><div class="bar-b" style="width:${((d.pdfs / maxD) * 100).toFixed(1)}%"></div></div><span class="r">${fmt(tot)} (${fmt(d.pdfs)})</span></div>`;
          }).join("")}
        </div>
        <div class="ana-sec">
          <h3>Nordiske land</h3>
          <table class="tbl-clean">
            <thead><tr><th>Land</th><th class="r">OpenAlex</th><th class="r">Arkiv</th><th class="r">PDF</th><th class="r">OA</th></tr></thead>
            <tbody>${cs.map((c) => `<tr><td><strong>${esc(c.country)}</strong></td><td class="r">${fmt(c.openalex_works)}</td><td class="r">${fmt(c.nordic_archive_records)}</td><td class="r"><strong>${fmt(c.pdfs)}</strong></td><td class="r">${((c.oa_share || 0) * 100).toFixed(0)}%</td></tr>`).join("")}</tbody>
          </table>
        </div>
        <div class="ana-sec">
          <h3>Google EmbeddingGemma forskingsklynger</h3>
          <table class="tbl-clean">
            <thead><tr><th>Klynge</th><th class="r">Verk</th><th class="r">PDF</th></tr></thead>
            <tbody>${cls.map((c) => `<tr><td><strong>${esc(c.label)}</strong><div style="font-size:11.5px;color:var(--muted);">${esc((c.keywords || []).slice(0, 5).join(", "))}</div></td><td class="r">${fmt(c.core_works)}</td><td class="r">${fmt(c.pdfs)}</td></tr>`).join("")}</tbody>
          </table>
        </div>
        <div class="ana-sec">
          <h3>Sentrale tidsskrift og konferansar</h3>
          <table class="tbl-clean">
            <thead><tr><th>Kanal</th><th class="r">Verk</th><th class="r">PDF</th><th class="r">Sit.</th></tr></thead>
            <tbody>${vens.map((v) => `<tr><td><strong>${esc(v.venue)}</strong></td><td class="r">${fmt(v.auto_included)}</td><td class="r">${fmt(v.pdfs)}</td><td class="r">${fmt(v.citations)}</td></tr>`).join("")}</tbody>
          </table>
        </div>
      </div>`;
  }

  function setTab(t) {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === t));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${t}`));
    const copy = HERO_COPY[t] || HERO_COPY.korpus;
    $("heroEyebrow").textContent = copy[0];
    $("heroTitle").textContent = copy[1];
    $("heroLead").textContent = copy[2];
    history.replaceState(null, "", `#${t}`);
    if (t === "siteringar") renderCitations();
    if (t === "kart") ensureMap();
  }

  function jumpToWorkInline(wid) {
    const w = S.byId.get(wid);
    if (!w) return;
    $("qInput").value = w.title || wid;
    $("accessSel").value = "";
    $("layerSel").value = "all";
    $("ccSel").value = "";
    $("eraSel").value = "";
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

    let tmr = null;
    $("qInput").addEventListener("input", () => {
      clearTimeout(tmr);
      tmr = setTimeout(() => {
        if (S.semScores && $("presetSel").value === "") S.semScores = null;
        filterCorpus();
      }, 110);
    });
    $("wasmBtn").addEventListener("click", runWasmQuery);

    $("resetBtn").addEventListener("click", () => {
      $("qInput").value = ""; $("accessSel").value = ""; $("presetSel").value = "";
      $("layerSel").value = "all"; $("ccSel").value = ""; $("eraSel").value = "";
      $("sortSel").value = "relevance"; S.semScores = null; S.expandedId = null;
      filterCorpus();
    });

    for (const id of ["accessSel", "layerSel", "ccSel", "eraSel", "sortSel"]) $(id).addEventListener("change", filterCorpus);

    $("presetSel").addEventListener("change", (e) => {
      const k = e.target.value;
      if (!k || !S.semMeta?.presets?.[k]) { S.semScores = null; filterCorpus(); return; }
      S.semScores = cosineAll(S.semMeta.presets[k]);
      S.semLabel = `Google EmbeddingGemma-tema: ${e.target.options[e.target.selectedIndex].text}`;
      $("sortSel").value = "relevance";
      filterCorpus();
    });
    $("clearSemBtn").addEventListener("click", () => { S.semScores = null; $("presetSel").value = ""; filterCorpus(); });

    $("moreCorpusBtn").addEventListener("click", () => { S.shown += STEP; renderCorpus(); });
    $("morePdfBtn").addEventListener("click", () => { S.pdfShown += STEP; renderPdfs(); });

    $("pdfQ").addEventListener("input", filterPdfs);
    $("pdfMode").addEventListener("change", filterPdfs);
    $("pdfCc").addEventListener("change", filterPdfs);

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

    /* Mouse + iPhone Touch Pan & Pinch Zoom on Semantic Map */
    const cv = $("semCanvas");
    window.addEventListener("resize", () => { if ($("view-kart").classList.contains("active")) drawMap(); });
    cv.addEventListener("wheel", (e) => {
      e.preventDefault();
      S.zoom = Math.min(12, Math.max(0.5, S.zoom * (e.deltaY < 0 ? 1.18 : 0.85)));
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
        drag = true; moved = false; lx = e.touches[0].clientX; ly = e.touches[0].clientY;
      } else if (e.touches.length === 2) {
        drag = false;
        pinchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      }
    }, { passive: true });
    cv.addEventListener("touchmove", (e) => {
      e.preventDefault();
      if (e.touches.length === 1 && drag) {
        const dx = e.touches[0].clientX - lx, dy = e.touches[0].clientY - ly;
        if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
        S.panX += dx; S.panY += dy; lx = e.touches[0].clientX; ly = e.touches[0].clientY;
        drawMap();
      } else if (e.touches.length === 2 && pinchDist > 0) {
        const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
        S.zoom = Math.min(12, Math.max(0.5, S.zoom * (d / pinchDist)));
        pinchDist = d;
        drawMap();
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
