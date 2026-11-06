/* DESIGNTEORI — Unified Research Workbench (Metadata + PDF + Citations + Google Embeddings + Analysis) */
(() => {
  "use strict";

  const PAGE_SIZE = 40;
  const CLUSTER_COLORS = [
    "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
    "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1"
  ];
  const COUNTRY_COLORS = {
    NO: "#2563eb", SE: "#eab308", DK: "#dc2626", FI: "#06b6d4", IS: "#a855f7"
  };

  const state = {
    allWorks: [],
    worksById: new Map(),
    pdfItems: [],
    analysis: null,
    context: null,
    canon: null,
    authors: null,
    institutions: null,
    semMeta: null,
    semVectors: null, // Int8Array (N * dims)
    semRowById: new Map(),
    semMap: null,
    wasmExtractor: null,

    // Corpus tab state
    filtered: [],
    page: 0,
    semanticScores: null, // Map<workId, cosine>
    semanticLabel: "",

    // PDF tab state
    pdfFiltered: [],
    pdfPage: 0,

    // Citations tab state
    citSub: "internal",

    // Map state
    mapClusterFilter: -1,
    mapZoom: 1,
    mapPanX: 0,
    mapPanY: 0,
  };

  const $ = (id) => document.getElementById(id);
  const fmt = (n) => (typeof n === "number" ? n.toLocaleString("nn-NO") : "—");
  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  async function fetchJson(url, fallback = null) {
    try {
      const r = await fetch(url);
      if (!r.ok) return fallback;
      return await r.json();
    } catch {
      return fallback;
    }
  }

  async function boot() {
    bindEvents();
    const [pubs, nordic, theory, analysis, pdfKat] = await Promise.all([
      fetchJson("data/publications.json", []),
      fetchJson("data/nordic_additions.json", []),
      fetchJson("data/theory_additions.json", []),
      fetchJson("data/analysis.json", null),
      fetchJson("data/pdf_katalog.json", { items: [], stats: {} }),
    ]);

    for (const w of pubs) {
      w._layer = "openalex";
      w._search = buildSearchString(w);
      state.allWorks.push(w);
      state.worksById.set(w.id, w);
    }
    for (const w of nordic) {
      w._layer = "nordic";
      w._search = buildSearchString(w);
      state.allWorks.push(w);
      state.worksById.set(w.id, w);
    }
    for (const w of theory) {
      w._layer = "historical";
      w._search = buildSearchString(w);
      state.allWorks.push(w);
      state.worksById.set(w.id, w);
    }

    state.analysis = analysis;
    state.pdfItems = pdfKat.items || [];
    updateKpis();
    applyCorpusFilters();
    applyPdfFilters();
    renderAnalysis();

    // Load Google EmbeddingGemma int8 vectors asynchronously
    loadSemanticIndex();

    // Respect initial URL hash
    const initHash = (location.hash || "").replace("#", "");
    if (["korpus", "pdf", "siteringar", "kart", "analyse"].includes(initHash)) {
      switchTab(initHash);
    }
  }

  function buildSearchString(w) {
    const auth = Array.isArray(w.authors) ? w.authors.join(" ") : (w.authors || "");
    return `${w.title || ""} ${auth} ${w.source || ""} ${w.doi || ""} ${w.topic || ""} ${w.keyword_categories || ""}`.toLowerCase();
  }

  function updateKpis() {
    const ov = state.analysis?.overview || {};
    $("kpiTotal").textContent = fmt(ov.total_searchable_works ?? state.allWorks.length);
    $("kpiIncluded").textContent = fmt(ov.openalex_auto_included ?? 0);
    $("kpiPdfs").textContent = fmt(ov.repo_pdf_files ?? state.allWorks.filter((w) => w.pdf).length);
    $("kpiEmbeddings").textContent = fmt(ov.google_embedded_works ?? 0);
    $("kpiCitations").textContent = fmt(ov.internal_citation_edges ?? 0);
    $("kpiCanon").textContent = fmt(ov.cited_canon_works ?? 0);
  }

  async function loadSemanticIndex() {
    const meta = await fetchJson("data/semantic_index.json", null);
    if (!meta || !meta.ids) {
      $("embeddingStatus").textContent = "Ingen semantisk indeks funnen.";
      return;
    }
    try {
      const resp = await fetch("data/semantic_vectors.bin");
      if (!resp.ok) throw new Error("Bin missing");
      const buf = await resp.arrayBuffer();
      const vecs = new Int8Array(buf);
      if (vecs.length !== meta.ids.length * meta.dimensions) {
        throw new Error("Dim mismatch");
      }
      state.semMeta = meta;
      state.semVectors = vecs;
      meta.ids.forEach((id, idx) => state.semRowById.set(id, idx));
      $("embeddingStatus").textContent = `Google EmbeddingGemma-300M klar (${fmt(meta.ids.length)} vektorar · ${meta.dimensions}d)`;
    } catch {
      $("embeddingStatus").textContent = "Kunne ikkje laste vektorfil.";
    }
  }

  function scoreAgainstFloatVector(qVec) {
    if (!state.semVectors || !state.semMeta) return null;
    const dims = state.semMeta.dimensions;
    const ids = state.semMeta.ids;
    const mat = state.semVectors;
    let qNorm = 0;
    for (let d = 0; d < dims; d++) qNorm += qVec[d] * qVec[d];
    qNorm = Math.sqrt(qNorm) || 1;

    const scores = new Map();
    for (let i = 0, base = 0; i < ids.length; i++, base += dims) {
      let dot = 0;
      let vNormSq = 0;
      for (let d = 0; d < dims; d++) {
        const v = mat[base + d];
        dot += v * qVec[d];
        vNormSq += v * v;
      }
      const denom = Math.sqrt(vNormSq) * qNorm;
      scores.set(ids[i], denom > 0 ? dot / denom : 0);
    }
    return scores;
  }

  function runWorkSimilarity(workId) {
    if (!state.semVectors || !state.semRowById.has(workId)) return;
    const row = state.semRowById.get(workId);
    const dims = state.semMeta.dimensions;
    const slice = new Float32Array(dims);
    for (let d = 0; d < dims; d++) slice[d] = state.semVectors[row * dims + d];
    const target = state.worksById.get(workId);
    state.semanticScores = scoreAgainstFloatVector(slice);
    state.semanticLabel = `Semantisk likskap (Google EmbeddingGemma) til: «${(target?.title || workId).slice(0, 85)}»`;
    $("sortFilter").value = "relevance";
    switchTab("korpus");
    applyCorpusFilters();
  }

  function topSimilarWorks(workId, k = 10) {
    if (!state.semVectors || !state.semRowById.has(workId)) return [];
    const row = state.semRowById.get(workId);
    const dims = state.semMeta.dimensions;
    const slice = new Float32Array(dims);
    for (let d = 0; d < dims; d++) slice[d] = state.semVectors[row * dims + d];
    const scores = scoreAgainstFloatVector(slice);
    const arr = [];
    for (const [id, sc] of scores.entries()) {
      if (id !== workId && state.worksById.has(id)) arr.push([id, sc]);
    }
    arr.sort((a, b) => b[1] - a[1]);
    return arr.slice(0, k).map(([id, sc]) => ({ work: state.worksById.get(id), cosine: sc }));
  }

  async function runLiveBrowserEmbeddingSearch() {
    const query = $("qInput").value.trim();
    if (!query) return;
    if (!state.semVectors || !state.semMeta) return;
    const btn = $("neuralSearchBtn");
    const origText = btn.textContent;
    try {
      btn.disabled = true;
      if (!state.wasmExtractor) {
        btn.textContent = "Lastar Google EmbeddingGemma (WASM)…";
        const { pipeline, env } = await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.4.0");
        env.allowLocalModels = false;
        state.wasmExtractor = await pipeline("feature-extraction", state.semMeta.onnx_web_model || "onnx-community/embeddinggemma-300m-ONNX", {
          dtype: "q8",
        });
      }
      btn.textContent = "Reknar vektor…";
      const out = await state.wasmExtractor(`task: search result | query: ${query}`, {
        pooling: "none",
      });
      // EmbeddingGemma ONNX returns pooled sentence_embedding or token states; slice first `dims`
      const flat = out.data;
      const dims = state.semMeta.dimensions;
      const qVec = new Float32Array(dims);
      for (let d = 0; d < dims; d++) qVec[d] = flat[d] || 0;
      state.semanticScores = scoreAgainstFloatVector(qVec);
      state.semanticLabel = `Google EmbeddingGemma semantisk fritekstsøk: «${query}»`;
      $("sortFilter").value = "relevance";
      applyCorpusFilters();
    } catch (err) {
      $("embeddingStatus").textContent = "Nettlesar-WASM feila — bruk førehandsrekna tema eller «Liknande verk» på alle kort.";
      console.error(err);
    } finally {
      btn.disabled = false;
      btn.textContent = origText;
    }
  }

  function applyCorpusFilters() {
    const q = $("qInput").value.trim().toLowerCase();
    const tokens = q ? q.split(/\s+/).filter(Boolean) : [];
    const layer = $("layerFilter").value;
    const cc = $("countryFilter").value;
    const era = $("eraFilter").value;
    const pdfOnly = $("pdfOnlyToggle").checked;
    const sort = $("sortFilter").value;

    const banner = $("semanticActiveBanner");
    if (state.semanticScores) {
      banner.style.display = "flex";
      $("semanticBannerText").textContent = state.semanticLabel;
    } else {
      banner.style.display = "none";
    }

    const out = [];
    for (const w of state.allWorks) {
      if (layer === "nordic" && w._layer !== "nordic") continue;
      if (layer !== "all" && layer !== "nordic" && w.scope !== layer) continue;
      if (cc) {
        const wCs = w.countries || (w.source_country ? [w.source_country] : []);
        if (!wCs.includes(cc)) continue;
      }
      if (era) {
        const y = w.year;
        if (!y) continue;
        if (era === "pre2000" && y >= 2000) continue;
        if (era === "2000-2009" && (y < 2000 || y > 2009)) continue;
        if (era === "2010-2019" && (y < 2010 || y > 2019)) continue;
        if (era === "2020-2026" && y < 2020) continue;
      }
      if (pdfOnly && !w.pdf) continue;
      // When not in semantic mode, require lexical match for all tokens
      if (!state.semanticScores && tokens.length > 0) {
        let ok = true;
        for (const t of tokens) {
          if (!w._search.includes(t)) {
            ok = false;
            break;
          }
        }
        if (!ok) continue;
      }
      out.push(w);
    }

    if (sort === "citations") {
      out.sort((a, b) => (b.citations || 0) - (a.citations || 0));
    } else if (sort === "year_desc") {
      out.sort((a, b) => (b.year || 0) - (a.year || 0));
    } else if (sort === "year_asc") {
      out.sort((a, b) => (a.year || 9999) - (b.year || 9999));
    } else if (state.semanticScores) {
      out.sort((a, b) => (state.semanticScores.get(b.id) || -1) - (state.semanticScores.get(a.id) || -1));
    } else if (tokens.length > 0) {
      out.sort((a, b) => {
        const aTitle = (a.title || "").toLowerCase();
        const bTitle = (b.title || "").toLowerCase();
        const aHits = tokens.reduce((s, t) => s + (aTitle.includes(t) ? 2 : 0), 0);
        const bHits = tokens.reduce((s, t) => s + (bTitle.includes(t) ? 2 : 0), 0);
        if (bHits !== aHits) return bHits - aHits;
        return (b.citations || 0) - (a.citations || 0);
      });
    } else {
      out.sort((a, b) => {
        if (Boolean(b.pdf) !== Boolean(a.pdf)) return b.pdf ? 1 : -1;
        return (b.citations || 0) - (a.citations || 0);
      });
    }

    state.filtered = out;
    state.page = 0;
    renderCorpusPage();
  }

  function renderCorpusPage() {
    const total = state.filtered.length;
    const maxPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
    state.page = Math.min(Math.max(0, state.page), maxPage);
    const slice = state.filtered.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);

    $("resultsSummary").textContent = `Viser ${fmt(slice.length)} av ${fmt(total)} registreringar`;
    $("pageIndicator").textContent = `${state.page + 1} / ${maxPage + 1}`;
    $("prevPageBtn").disabled = state.page <= 0;
    $("nextPageBtn").disabled = state.page >= maxPage;

    const html = slice.map((w) => renderWorkCard(w)).join("");
    $("corpusList").innerHTML = html || `<div class="box">Ingen treff for gjeldande filter.</div>`;
  }

  function scopeBadge(w) {
    if (w.scope === "automatic-title-inclusion") return `<span class="badge badge-blue">OpenAlex tittelinkludert</span>`;
    if (w.scope === "awaiting-eligibility-review") return `<span class="badge">OpenAlex vurderingskø</span>`;
    if (w._layer === "nordic") return `<span class="badge badge-amber">${esc(w.source || "Nordisk arkiv")}</span>`;
    return `<span class="badge">Historisk referanse</span>`;
  }

  function renderWorkCard(w) {
    const auth = Array.isArray(w.authors) ? w.authors.slice(0, 5).join(", ") : (w.authors || "");
    const cs = (w.countries && w.countries.length ? w.countries : (w.source_country ? [w.source_country] : [])).join(", ");
    const cos = state.semanticScores?.get(w.id);
    const cosHtml = typeof cos === "number" ? `<span class="badge badge-blue">cos ${cos.toFixed(3)}</span>` : "";
    const pdfBtn = w.pdf
      ? `<a class="btn btn-xs btn-pdf" href="${esc(w.pdf)}" target="_blank" rel="noopener">Opne PDF</a>`
      : (w.oa_url ? `<a class="btn btn-xs" href="${esc(w.oa_url)}" target="_blank" rel="noopener">OA-kjelde</a>` : "");
    const simBtn = state.semRowById.has(w.id)
      ? `<button class="btn btn-xs" data-sim="${esc(w.id)}">Liknande verk</button>`
      : "";

    return `
      <article class="work-card">
        <div class="work-top">
          <div>
            <h3 class="work-title" data-open="${esc(w.id)}">${esc(w.title || "(utan tittel)")}</h3>
            <div class="work-sub">
              <strong>${esc(w.year || "ukjent år")}</strong>
              ${auth ? " · " + esc(auth) : ""}
              ${w.source ? " · <em>" + esc(w.source) + "</em>" : ""}
            </div>
          </div>
          <div class="card-actions">
            ${pdfBtn}
            ${simBtn}
            <button class="btn btn-xs" data-open="${esc(w.id)}">Detaljar</button>
          </div>
        </div>
        <div class="badge-row">
          ${scopeBadge(w)}
          ${w.pdf ? `<span class="badge badge-green">PDF i repo (pdf/)</span>` : ""}
          ${cs ? `<span class="badge">${esc(cs)}</span>` : ""}
          ${w.kind ? `<span class="badge">${esc(w.kind)}</span>` : ""}
          ${typeof w.citations === "number" ? `<span class="badge">${fmt(w.citations)} siteringar</span>` : ""}
          ${cosHtml}
        </div>
      </article>
    `;
  }

  /* TAB 2: PDF ARCHIVE */
  function applyPdfFilters() {
    const q = $("pdfSearchInput").value.trim().toLowerCase();
    const mode = $("pdfAccessFilter").value;
    const cc = $("pdfCountryFilter").value;
    const out = state.pdfItems.filter((it) => {
      if (mode === "repo" && !it.pdf_in_repo) return false;
      if (mode === "verified" && !it.verified_oa_pdf) return false;
      if (cc && !(it.country_affiliations || []).includes(cc)) return false;
      if (q) {
        const hay = `${it.title || ""} ${(it.authors || []).join(" ")} ${it.source || ""} ${it.doi || ""} ${it.document_sha256 || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    state.pdfFiltered = out;
    state.pdfPage = 0;
    renderPdfPage();
  }

  function renderPdfPage() {
    const total = state.pdfFiltered.length;
    const maxP = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
    state.pdfPage = Math.min(Math.max(0, state.pdfPage), maxP);
    const slice = state.pdfFiltered.slice(state.pdfPage * PAGE_SIZE, (state.pdfPage + 1) * PAGE_SIZE);
    $("pdfSummary").textContent = `Viser ${fmt(slice.length)} av ${fmt(total)} fulltekstoppføringar`;
    $("pdfPageInd").textContent = `${state.pdfPage + 1} / ${maxP + 1}`;
    $("pdfPrevBtn").disabled = state.pdfPage <= 0;
    $("pdfNextBtn").disabled = state.pdfPage >= maxP;

    $("pdfList").innerHTML = slice.map((it) => {
      const url = it.public_pdf_url || it.oa_location_unverified || "";
      const mb = it.document_bytes ? (it.document_bytes / 1e6).toFixed(2) + " MB" : "";
      const sha = it.document_sha256 ? it.document_sha256.slice(0, 12) + "…" : "";
      return `
        <article class="work-card">
          <div class="work-top">
            <div>
              <h3 class="work-title" data-open="${esc(it.id)}">${esc(it.title)}</h3>
              <div class="work-sub">
                <strong>${esc(it.year || "?")}</strong> · ${esc((it.authors || []).slice(0, 4).join(", "))}
                ${it.source ? " · <em>" + esc(it.source) + "</em>" : ""}
              </div>
            </div>
            <div class="card-actions">
              ${url ? `<a class="btn btn-xs btn-pdf" href="${esc(url)}" target="_blank" rel="noopener">${it.pdf_in_repo ? "Opne PDF (GitHub)" : "Opne OA-PDF"}</a>` : ""}
              <button class="btn btn-xs" data-open="${esc(it.id)}">Detaljar</button>
            </div>
          </div>
          <div class="badge-row">
            ${it.pdf_in_repo ? `<span class="badge badge-green">Lagra i pdf/</span>` : `<span class="badge badge-blue">Ekstern OA-lenkje</span>`}
            ${mb ? `<span class="badge">${esc(mb)}</span>` : ""}
            ${sha ? `<span class="badge" style="font-family:var(--mono);">SHA-256: ${esc(sha)}</span>` : ""}
            ${(it.country_affiliations || []).length ? `<span class="badge">${esc(it.country_affiliations.join(", "))}</span>` : ""}
          </div>
        </article>
      `;
    }).join("") || `<div class="box">Ingen PDF-oppføringar funne.</div>`;
  }

  /* TAB 3: CITATIONS, CANON & ACTORS */
  async function renderCitationsTab() {
    const q = $("citFilterInput").value.trim().toLowerCase();
    const box = $("citationContainer");
    if (state.citSub === "internal") {
      const list = (state.analysis?.citations?.top_internally_cited || []).filter((r) =>
        !q || `${r.title} ${(r.authors || []).join(" ")} ${r.source}`.toLowerCase().includes(q)
      );
      box.innerHTML = `
        <h3>Mest siterte nordiske verk internt i korpuset</h3>
        <p style="color:var(--ink-muted);font-size:0.86rem;">Rangert etter kor mange andre nordiske designpublikasjonar i korpuset som siterer verket.</p>
        <table class="data-table">
          <thead><tr><th>Verk</th><th>År</th><th>Land</th><th>Interne sit.</th><th>Globale sit.</th><th>PDF</th></tr></thead>
          <tbody>
            ${list.map((r) => `
              <tr>
                <td><a href="#" data-open="${esc(r.id)}"><strong>${esc(r.title)}</strong></a><br/><span style="color:var(--ink-muted);font-size:0.8rem;">${esc((r.authors || []).join(", "))} · ${esc(r.source || "")}</span></td>
                <td>${esc(r.year || "")}</td>
                <td>${esc((r.countries || []).join(", "))}</td>
                <td><strong>${fmt(r.internal_citations)}</strong></td>
                <td>${fmt(r.global_citations)}</td>
                <td>${r.pdf ? `<a href="${esc(r.pdf)}" target="_blank" rel="noopener">PDF</a>` : "—"}</td>
              </tr>`).join("")}
          </tbody>
        </table>`;
      return;
    }

    if (state.citSub === "canon") {
      if (!state.canon) {
        box.innerHTML = "Lastar sitert grunnlagskanon…";
        const d = await fetchJson("data/cited_canon.json", { items: [] });
        state.canon = d.items || [];
      }
      const list = state.canon.filter((r) =>
        !q || `${r.title} ${r.authors} ${r.source}`.toLowerCase().includes(q)
      ).slice(0, 200);
      box.innerHTML = `
        <h3>Grunnleggjande sitert kanon i nordisk designforsking (topp 1 000 refererte verk)</h3>
        <p style="color:var(--ink-muted);font-size:0.86rem;">Internasjonale og nordiske referanseverk som oftast blir siterte frå det nordiske designkorpuset.</p>
        <table class="data-table">
          <thead><tr><th>Tittel &amp; Forfattar</th><th>År</th><th>Sitert av nordiske verk</th><th>Globale sit.</th><th>Kjelde</th></tr></thead>
          <tbody>
            ${list.map((r) => `
              <tr>
                <td>${r.in_primary_corpus ? `<a href="#" data-open="${esc(r.id)}"><strong>${esc(r.title)}</strong></a>` : `<strong>${esc(r.title)}</strong>`}<br/><span style="color:var(--ink-muted);font-size:0.8rem;">${esc(r.authors)}</span></td>
                <td>${esc(r.year || "")}</td>
                <td><strong>${fmt(r.nordic_citing_count)}</strong></td>
                <td>${fmt(r.global_citations)}</td>
                <td>${r.doi ? `<a href="${esc(r.doi)}" target="_blank" rel="noopener">DOI</a>` : esc(r.source || "—")}</td>
              </tr>`).join("")}
          </tbody>
        </table>`;
      return;
    }

    if (state.citSub === "authors") {
      if (!state.authors) {
        box.innerHTML = "Lastar forfattarregister…";
        const d = await fetchJson("data/authors.json", { items: [] });
        state.authors = d.items || [];
      }
      const list = state.authors.filter((a) => !q || `${a.name} ${(a.institutions || []).join(" ")}`.toLowerCase().includes(q)).slice(0, 150);
      box.innerHTML = `
        <h3>Nordiske designforskarar</h3>
        <table class="data-table">
          <thead><tr><th>Forfattar</th><th>Land</th><th>Tittelinkluderte</th><th>Totalt</th><th>Siteringssum</th><th>Institusjonar</th></tr></thead>
          <tbody>
            ${list.map((a) => `
              <tr>
                <td><a href="#" data-author-q="${esc(a.name)}"><strong>${esc(a.name)}</strong></a></td>
                <td>${esc((a.countries || []).join(", "))}</td>
                <td><strong>${fmt(a.automatically_title_included)}</strong></td>
                <td>${fmt(a.works)}</td>
                <td>${fmt(a.openalex_citation_sum_on_snapshot_works)}</td>
                <td style="font-size:0.79rem;color:var(--ink-muted);">${esc((a.institutions || []).slice(0, 2).join("; "))}</td>
              </tr>`).join("")}
          </tbody>
        </table>`;
      return;
    }

    if (state.citSub === "institutions") {
      if (!state.institutions) {
        box.innerHTML = "Lastar institusjonsregister…";
        const d = await fetchJson("data/institutions.json", { items: [] });
        state.institutions = d.items || [];
      }
      const list = state.institutions.filter((i) => !q || `${i.name} ${i.country}`.toLowerCase().includes(q)).slice(0, 150);
      box.innerHTML = `
        <h3>Forskingsinstitusjonar</h3>
        <table class="data-table">
          <thead><tr><th>Institusjon</th><th>Land</th><th>Tittelinkluderte verk</th><th>Totalt i korpus</th></tr></thead>
          <tbody>
            ${list.map((i) => `
              <tr>
                <td><strong>${esc(i.name)}</strong></td>
                <td>${esc(i.country)}</td>
                <td><strong>${fmt(i.automatically_title_included)}</strong></td>
                <td>${fmt(i.works)}</td>
              </tr>`).join("")}
          </tbody>
        </table>`;
    }
  }

  /* TAB 4: 2D SEMANTIC MAP */
  async function ensureSemanticMap() {
    if (!state.semMap) {
      state.semMap = await fetchJson("data/semantic_map.json", { clusters: [], points: [] });
      renderMapLegend();
    }
    drawSemanticMap();
  }

  function renderMapLegend() {
    const clusters = state.semMap?.clusters || [];
    $("mapLegend").innerHTML =
      `<div class="legend-item ${state.mapClusterFilter === -1 ? "active" : ""}" data-cluster="-1">
        <span class="swatch" style="background:#94a3b8;"></span>
        <span><strong>Alle klynger (${fmt(state.semMap?.points?.length || 0)} verk)</strong></span>
      </div>` +
      clusters.map((c, idx) => `
        <div class="legend-item ${state.mapClusterFilter === c.id ? "active" : ""}" data-cluster="${c.id}">
          <span class="swatch" style="background:${CLUSTER_COLORS[idx % CLUSTER_COLORS.length]};"></span>
          <div>
            <div style="font-weight:600;">${esc(c.label)}</div>
            <div style="font-size:0.74rem;color:var(--ink-muted);">${esc((c.keywords || []).slice(0, 4).join(", "))}</div>
          </div>
        </div>
      `).join("");
  }

  function drawSemanticMap() {
    const canvas = $("semanticCanvas");
    if (!canvas || !state.semMap) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const W = Math.max(600, rect.width);
    const H = 560;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#0f1522";
    ctx.fillRect(0, 0, W, H);

    const mode = $("mapColorMode").value;
    const pts = state.semMap.points || [];
    const cx = W / 2 + state.mapPanX;
    const cy = H / 2 + state.mapPanY;
    const scale = Math.min(W, H) * 0.34 * state.mapZoom;

    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      if (state.mapClusterFilter !== -1 && p.c !== state.mapClusterFilter) continue;
      const sx = cx + p.x * scale;
      const sy = cy - p.y * scale;
      if (sx < -6 || sx > W + 6 || sy < -6 || sy > H + 6) continue;
      p._sx = sx;
      p._sy = sy;
      if (mode === "country") {
        ctx.fillStyle = COUNTRY_COLORS[p.cc] || "#64748b";
      } else if (mode === "pdf") {
        ctx.fillStyle = p.pdf ? "#22c55e" : "#475569";
      } else {
        ctx.fillStyle = CLUSTER_COLORS[p.c % CLUSTER_COLORS.length];
      }
      ctx.globalAlpha = p.pdf ? 0.92 : 0.62;
      ctx.beginPath();
      ctx.arc(sx, sy, p.pdf ? 3.3 : 2.3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  /* TAB 5: EMPIRICAL ANALYSIS */
  function renderAnalysis() {
    const a = state.analysis;
    if (!a) return;
    const decs = a.decades || [];
    const maxDec = Math.max(1, ...decs.map((d) => d.total + (d.nordic_archives || 0)));
    const countries = a.countries || [];
    const matrix = a.cross_nordic_collaboration?.matrix || {};
    const clusters = a.semantic_clusters || [];
    const venues = (a.top_venues || []).slice(0, 20);

    $("analysisRoot").innerHTML = `
      <div class="grid-2">
        <div class="box">
          <h3>Historisk vekst per tiår (1900–2026)</h3>
          <p style="font-size:0.83rem;color:var(--ink-muted);">Blå = totale registreringar, grøn = nedlasta PDF i <code>pdf/</code>.</p>
          ${decs.map((d) => {
            const sum = d.total + (d.nordic_archives || 0);
            const pct = ((sum / maxDec) * 100).toFixed(1);
            const pdfPct = ((d.pdfs / maxDec) * 100).toFixed(1);
            return `
              <div class="bar-row">
                <strong>${esc(d.decade)}</strong>
                <div class="bar-track">
                  <div class="bar-fill" style="width:${pct}%"></div>
                  <div class="bar-fill-pdf" style="width:${pdfPct}%"></div>
                </div>
                <span style="text-align:right;font-variant-numeric:tabular-nums;">${fmt(sum)} (${fmt(d.pdfs)} PDF)</span>
              </div>`;
          }).join("")}
        </div>

        <div class="box">
          <h3>Nordisk landprofil (NO · SE · DK · FI · IS)</h3>
          <table class="data-table">
            <thead><tr><th>Land</th><th>OpenAlex</th><th>Tittelinkl.</th><th>Nasjonalt arkiv</th><th>PDF i repo</th><th>OA-del</th></tr></thead>
            <tbody>
              ${countries.map((c) => `
                <tr>
                  <td><strong>${esc(c.country)}</strong></td>
                  <td>${fmt(c.openalex_works)}</td>
                  <td>${fmt(c.auto_included)}</td>
                  <td>${fmt(c.nordic_archive_records)}</td>
                  <td><strong>${fmt(c.pdfs)}</strong></td>
                  <td>${((c.oa_share || 0) * 100).toFixed(1)} %</td>
                </tr>`).join("")}
            </tbody>
          </table>

          <h3 style="margin-top:1.2rem;">Nordisk samskrivingsmatrise</h3>
          <table class="data-table">
            <thead><tr><th></th>${["NO", "SE", "DK", "FI", "IS"].map((c) => `<th>${c}</th>`).join("")}</tr></thead>
            <tbody>
              ${["NO", "SE", "DK", "FI", "IS"].map((r) => `
                <tr>
                  <th>${r}</th>
                  ${["NO", "SE", "DK", "FI", "IS"].map((c) => `<td>${fmt(matrix[r]?.[c] ?? 0)}</td>`).join("")}
                </tr>`).join("")}
            </tbody>
          </table>
        </div>
      </div>

      <div class="box">
        <h3>10 Semantiske forskingsklynger (Google EmbeddingGemma-300M)</h3>
        <table class="data-table">
          <thead><tr><th>Forskingsklynge</th><th>Kjerneverk</th><th>PDF i repo</th><th>Nøkkelord</th><th>Landfordeling (NO/SE/DK/FI/IS)</th></tr></thead>
          <tbody>
            ${clusters.map((c) => `
              <tr>
                <td><strong>${esc(c.label)}</strong></td>
                <td>${fmt(c.core_works)}</td>
                <td>${fmt(c.pdfs)}</td>
                <td style="font-size:0.8rem;color:var(--ink-muted);">${esc((c.keywords || []).join(", "))}</td>
                <td style="font-size:0.8rem;">NO:${c.countries?.NO || 0} · SE:${c.countries?.SE || 0} · DK:${c.countries?.DK || 0} · FI:${c.countries?.FI || 0} · IS:${c.countries?.IS || 0}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>

      <div class="grid-2">
        <div class="box">
          <h3>Sentrale publiseringskanalar</h3>
          <table class="data-table">
            <thead><tr><th>Tidsskrift / konferanse</th><th>Tittelinkl.</th><th>PDF</th><th>Siteringar</th></tr></thead>
            <tbody>
              ${venues.map((v) => `
                <tr>
                  <td><strong>${esc(v.venue)}</strong></td>
                  <td>${fmt(v.auto_included)}</td>
                  <td>${fmt(v.pdfs)}</td>
                  <td>${fmt(v.citations)}</td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>

        <div class="box">
          <h3>Metodisk etterprøvbarheit</h3>
          <ul class="mini-list">
            ${(a.methodological_notes || []).map((n) => `<li>${esc(n)}</li>`).join("")}
          </ul>
        </div>
      </div>
    `;
  }

  /* SLIDE-OVER DETAIL DRAWER */
  async function openDrawer(workId) {
    const w = state.worksById.get(workId);
    if (!w) return;
    if (!state.context) {
      state.context = await fetchJson("data/work_context.json", {});
    }
    const ctx = state.context?.[workId] || {};
    $("drawerBadge").textContent = `${w._layer.toUpperCase()} · ${w.id}`;
    $("drawerTitle").textContent = w.title || "(utan tittel)";
    const auth = Array.isArray(w.authors) ? w.authors.join(", ") : (w.authors || "");
    $("drawerMeta").innerHTML = `<strong>${esc(w.year || "?")}</strong> · ${esc(auth)} ${w.source ? " · <em>" + esc(w.source) + "</em>" : ""}`;

    const actions = [];
    if (w.pdf) actions.push(`<a class="btn btn-pdf" href="${esc(w.pdf)}" target="_blank" rel="noopener">Opne PDF (GitHub)</a>`);
    if (w.oa_url && w.oa_url !== w.pdf) actions.push(`<a class="btn" href="${esc(w.oa_url)}" target="_blank" rel="noopener">Original OA-URL</a>`);
    if (w.doi) {
      const doiHref = w.doi.startsWith("http") ? w.doi : `https://doi.org/${w.doi}`;
      actions.push(`<a class="btn" href="${esc(doiHref)}" target="_blank" rel="noopener">DOI</a>`);
    }
    if (state.semRowById.has(workId)) {
      actions.push(`<button class="btn" data-sim="${esc(workId)}">Filtrer på liknande i hovudlista</button>`);
    }
    $("drawerActions").innerHTML = actions.join("");

    // Institutional affiliations
    const affs = ctx.authors || [];
    $("drawerAffiliations").innerHTML = affs.length
      ? `<h4>Forfattarar og institusjonar</h4><ul class="mini-list">${affs.map((a) => `<li><strong>${esc(a.name)}</strong> — ${esc((a.institutions || []).map((i) => `${i.name} (${i.country})`).join("; "))}</li>`).join("")}</ul>`
      : "";

    // Live Google EmbeddingGemma nearest neighbors
    const sims = topSimilarWorks(workId, 8);
    $("drawerSimilar").innerHTML = sims.length
      ? `<h4>Semantisk liknande verk (Google EmbeddingGemma-300M)</h4>
         <ul class="mini-list">${sims.map(({ work, cosine }) => `
           <li>
             <a href="#" data-open="${esc(work.id)}"><strong>${esc(work.title)}</strong></a>
             (${esc(work.year || "?")}) <span class="badge badge-blue">cos ${cosine.toFixed(3)}</span>
             ${work.pdf ? `<a class="badge badge-green" href="${esc(work.pdf)}" target="_blank" rel="noopener">PDF</a>` : ""}
           </li>`).join("")}</ul>`
      : "";

    const citedBy = (ctx.cited_by || []).map((id) => state.worksById.get(id)).filter(Boolean);
    $("drawerCitedBy").innerHTML = citedBy.length
      ? `<h4>Sitert av i nordisk korpus (${citedBy.length})</h4>
         <ul class="mini-list">${citedBy.slice(0, 25).map((cw) => `<li><a href="#" data-open="${esc(cw.id)}">${esc(cw.title)}</a> (${esc(cw.year || "?")})</li>`).join("")}</ul>`
      : "";

    const cites = (ctx.cites || []).map((id) => state.worksById.get(id)).filter(Boolean);
    $("drawerCites").innerHTML = cites.length
      ? `<h4>Refererer til i nordisk korpus (${cites.length})</h4>
         <ul class="mini-list">${cites.slice(0, 25).map((cw) => `<li><a href="#" data-open="${esc(cw.id)}">${esc(cw.title)}</a> (${esc(cw.year || "?")})</li>`).join("")}</ul>`
      : "";

    $("drawerBackdrop").classList.add("open");
    $("workDrawer").classList.add("open");
  }

  function closeDrawer() {
    $("drawerBackdrop").classList.remove("open");
    $("workDrawer").classList.remove("open");
  }

  function switchTab(tab) {
    document.querySelectorAll(".nav-tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${tab}`));
    history.replaceState(null, "", `#${tab}`);
    if (tab === "siteringar") renderCitationsTab();
    if (tab === "kart") ensureSemanticMap();
  }

  function bindEvents() {
    document.querySelectorAll(".nav-tab").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    let debounceTimer = null;
    $("qInput").addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        if (state.semanticScores && $("presetSelect").value === "") {
          state.semanticScores = null;
        }
        applyCorpusFilters();
      }, 140);
    });
    $("qInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.ctrlKey) runLiveBrowserEmbeddingSearch();
    });

    $("neuralSearchBtn").addEventListener("click", runLiveBrowserEmbeddingSearch);
    $("resetSearchBtn").addEventListener("click", () => {
      $("qInput").value = "";
      $("layerFilter").value = "all";
      $("countryFilter").value = "";
      $("eraFilter").value = "";
      $("sortFilter").value = "relevance";
      $("pdfOnlyToggle").checked = false;
      $("presetSelect").value = "";
      state.semanticScores = null;
      applyCorpusFilters();
    });

    for (const id of ["layerFilter", "countryFilter", "eraFilter", "sortFilter", "pdfOnlyToggle"]) {
      $(id).addEventListener("change", applyCorpusFilters);
    }

    $("presetSelect").addEventListener("change", (e) => {
      const key = e.target.value;
      if (!key || !state.semMeta?.presets?.[key]) {
        state.semanticScores = null;
        applyCorpusFilters();
        return;
      }
      const vec = state.semMeta.presets[key];
      const label = e.target.options[e.target.selectedIndex].text;
      state.semanticScores = scoreAgainstFloatVector(vec);
      state.semanticLabel = `Google EmbeddingGemma semantisk temasøk: ${label}`;
      $("sortFilter").value = "relevance";
      applyCorpusFilters();
    });

    $("clearSemanticBtn").addEventListener("click", () => {
      state.semanticScores = null;
      $("presetSelect").value = "";
      applyCorpusFilters();
    });

    $("prevPageBtn").addEventListener("click", () => { state.page--; renderCorpusPage(); window.scrollTo(0, 0); });
    $("nextPageBtn").addEventListener("click", () => { state.page++; renderCorpusPage(); window.scrollTo(0, 0); });

    // PDF tab events
    $("pdfSearchInput").addEventListener("input", applyPdfFilters);
    $("pdfAccessFilter").addEventListener("change", applyPdfFilters);
    $("pdfCountryFilter").addEventListener("change", applyPdfFilters);
    $("pdfPrevBtn").addEventListener("click", () => { state.pdfPage--; renderPdfPage(); window.scrollTo(0, 0); });
    $("pdfNextBtn").addEventListener("click", () => { state.pdfPage++; renderPdfPage(); window.scrollTo(0, 0); });

    // Citations tab events
    document.querySelectorAll(".subview-btn").forEach((b) => {
      b.addEventListener("click", () => {
        document.querySelectorAll(".subview-btn").forEach((x) => x.classList.remove("btn-primary"));
        b.classList.add("btn-primary");
        state.citSub = b.dataset.sub;
        renderCitationsTab();
      });
    });
    $("citFilterInput").addEventListener("input", renderCitationsTab);

    // Map events
    $("mapColorMode").addEventListener("change", drawSemanticMap);
    $("mapResetZoom").addEventListener("click", () => {
      state.mapZoom = 1;
      state.mapPanX = 0;
      state.mapPanY = 0;
      drawSemanticMap();
    });
    $("mapLegend").addEventListener("click", (e) => {
      const item = e.target.closest("[data-cluster]");
      if (!item) return;
      state.mapClusterFilter = parseInt(item.dataset.cluster, 10);
      renderMapLegend();
      drawSemanticMap();
    });

    const canvas = $("semanticCanvas");
    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.18 : 0.85;
      state.mapZoom = Math.min(12, Math.max(0.5, state.mapZoom * factor));
      drawSemanticMap();
    }, { passive: false });

    let dragging = false, lastX = 0, lastY = 0, moved = false;
    canvas.addEventListener("mousedown", (e) => { dragging = true; moved = false; lastX = e.clientX; lastY = e.clientY; });
    window.addEventListener("mouseup", () => { dragging = false; });
    canvas.addEventListener("mousemove", (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      if (dragging) {
        const dx = e.clientX - lastX;
        const dy = e.clientY - lastY;
        if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
        state.mapPanX += dx;
        state.mapPanY += dy;
        lastX = e.clientX;
        lastY = e.clientY;
        drawSemanticMap();
        return;
      }
      const pts = state.semMap?.points || [];
      let best = null, bestD = 81;
      for (const p of pts) {
        if (state.mapClusterFilter !== -1 && p.c !== state.mapClusterFilter) continue;
        if (p._sx === undefined) continue;
        const d2 = (p._sx - mx) ** 2 + (p._sy - my) ** 2;
        if (d2 < bestD) { bestD = d2; best = p; }
      }
      const tip = $("mapTooltip");
      if (best) {
        const w = state.worksById.get(best.id);
        tip.style.display = "block";
        tip.style.left = `${Math.min(rect.width - 280, mx + 12)}px`;
        tip.style.top = `${Math.max(10, my - 28)}px`;
        tip.innerHTML = `<strong>${esc(w?.title || best.id)}</strong><br/>${esc(best.y_pub || "")} · ${esc(best.cc || "")} ${best.pdf ? "· PDF i repo" : ""}`;
      } else {
        tip.style.display = "none";
      }
    });
    canvas.addEventListener("click", (e) => {
      if (moved) return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const pts = state.semMap?.points || [];
      let best = null, bestD = 100;
      for (const p of pts) {
        if (state.mapClusterFilter !== -1 && p.c !== state.mapClusterFilter) continue;
        if (p._sx === undefined) continue;
        const d2 = (p._sx - mx) ** 2 + (p._sy - my) ** 2;
        if (d2 < bestD) { bestD = d2; best = p; }
      }
      if (best) openDrawer(best.id);
    });

    // Global delegated clicks (`data-open`, `data-sim`, `data-author-q`)
    document.body.addEventListener("click", (e) => {
      const openEl = e.target.closest("[data-open]");
      if (openEl) {
        e.preventDefault();
        openDrawer(openEl.dataset.open);
        return;
      }
      const simEl = e.target.closest("[data-sim]");
      if (simEl) {
        e.preventDefault();
        closeDrawer();
        runWorkSimilarity(simEl.dataset.sim);
        return;
      }
      const authEl = e.target.closest("[data-author-q]");
      if (authEl) {
        e.preventDefault();
        $("qInput").value = authEl.dataset.authorQ;
        state.semanticScores = null;
        switchTab("korpus");
        applyCorpusFilters();
      }
    });

    $("closeDrawerBtn").addEventListener("click", closeDrawer);
    $("drawerBackdrop").addEventListener("click", closeDrawer);
    window.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
  }

  boot();
})();

