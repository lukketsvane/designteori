/* DESIGNTEORI - arbeidsbenk for nordisk designteori og designforsking.
   Katalog med ordsøk, ordliste, valfri språkmodell, samandrag, liknande verk, eksport og leseliste. */
(() => {
  "use strict";

  const U = window.DTUi, Search = window.DTSearch, Exp = window.DTExport, Emb = window.DTEmbed, Om = window.DTOm;
  const { esc, fmt } = U;

  const STEP = 50;
  const COUNTRY_NAMES = { NO: "Noreg", SE: "Sverige", DK: "Danmark", FI: "Finland", IS: "Island", FO: "Færøyane", GL: "Grønland" };
  const NORDIC_CC = new Set(["NO", "SE", "DK", "FI", "IS", "FO", "GL"]);
  const LS = { model: "designteori.modell", start: "designteori.start", list: "designteori.leseliste.v1" };
  const ISO = { e: "en", b: "nb", n: "nn", d: "da", s: "sv", f: "fi", o: "", u: "" };
  const LANGMAP = { en: "e", da: "d", sv: "s", fi: "f", nn: "n", no: "b" };
  const TABS = U.TABS;

  const S = {
    works: [], byId: new Map(), pos: new Map(), analysis: null,
    meta: null, metaOK: false, degraded: false, noAbs: false, counts: null,
    config: null, engine: null, corpus: null, qf: null, access: null,
    vectors: null, sim: null, qvs: null, qvCache: new Map(), modelQV: new Map(),
    shards: new Map(), ctx: null, insts: null, instSets: new Map(), instName: new Map(), glossary: null, about: null, quality: null,
    t1: false, loading: new Map(),
    st: U.emptyState(), lastHash: null, seq: 0, shown: STEP, result: null, hl: { terms: new Set() },
    expandedId: null, openAbs: new Set(), reading: [], peopleAll: false, startOpen: true, filterOpen: false,
    embed: null, modelState: "av", modelMsg: "", modelProgress: 0, modelPanelOpen: false, encTimer: null, encKey: "", encPending: false,
    canon: null, authors: null, citSub: "internal", teLoaded: false,
  };

  const $ = (id) => document.getElementById(id);
  const saveData = () => !!(navigator.connection && navigator.connection.saveData);
  /* Tilgangsadressene kjem aldri når fila feila, eller når saveData held bakgrunnslastinga tilbake */
  const accessGone = () => !S.access && (!!S.accessFailed || (saveData() && !S.t1));
  const accInfo = (i, w) => U.accessInfo(S.meta.acc[i], w, S.access ? S.access[w.id] : null, { unavailable: accessGone() });
  const narrow = () => { const w = window.innerWidth; return w > 0 && w < 600; };
  const lowMem = () => typeof navigator.deviceMemory === "number" && navigator.deviceMemory < 4;
  const tally = (s) => { const o = {}; for (const c of s) o[c] = (o[c] || 0) + 1; return o; };

  /* ---------- lagring (alltid try/catch) ---------- */
  const mem = {};
  const store = {
    get(k) { try { const v = window.localStorage.getItem(k); return v == null ? (mem[k] ?? null) : v; } catch { return mem[k] ?? null; } },
    set(k, v) { mem[k] = v; try { window.localStorage.setItem(k, v); } catch { /* utan lagring */ } },
    del(k) { delete mem[k]; try { window.localStorage.removeItem(k); } catch { /* utan lagring */ } },
  };

  /* ---------- henting ---------- */
  async function jget(u, fb = null) {
    try { const r = await fetch(u); return r.ok ? await r.json() : fb; } catch { return fb; }
  }
  const sUrl = (f) => `data/search/${f}?v=${encodeURIComponent(S.meta && S.meta.build_id ? S.meta.build_id : "0")}`;
  const sget = (f, fb = null) => jget(sUrl(f), fb);
  async function sbin(f) {
    try { const r = await fetch(sUrl(f)); return r.ok ? await r.arrayBuffer() : null; } catch { return null; }
  }
  /* Kvar fil vert hentt éin gong; feil slår av funksjonen utan å stoppe sida */
  function once(key, fn) {
    if (!S.loading.has(key)) S.loading.set(key, Promise.resolve().then(fn).catch(() => null));
    return S.loading.get(key);
  }

  const toastEl = document.createElement("div");
  toastEl.className = "toast"; toastEl.setAttribute("role", "status"); toastEl.hidden = true;
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(toastEl));
  let toastTmr = null;
  function toast(msg) {
    if (!toastEl.isConnected) document.body.appendChild(toastEl);
    toastEl.textContent = msg; toastEl.hidden = false;
    clearTimeout(toastTmr); toastTmr = setTimeout(() => { toastEl.hidden = true; }, 2600);
  }
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch { /* prøv alternativ */ }
    try {
      const ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.cssText = "position:fixed;top:0;left:0;opacity:0";
      document.body.appendChild(ta); ta.select();
      const ok = document.execCommand("copy"); ta.remove(); return ok;
    } catch { return false; }
  }

  /* ---------- start ---------- */
  async function init() {
    bind();
    S.reading = loadReading();
    const metaP = jget(`data/search/meta.json?v=${Math.round(Date.now() / 3600e3)}`, null);
    const [pubs, nordic, ana, meta] = await Promise.all([
      jget("data/publications.json", []), jget("data/nordic_additions.json", []), jget("data/analysis.json", null), metaP,
    ]);
    for (const w of pubs) { w._layer = "openalex"; S.works.push(w); }
    for (const w of nordic) { w._layer = "nordic"; S.works.push(w); }
    S.works.forEach((w, i) => { w._i = i; S.byId.set(w.id, w); S.pos.set(w.id, i); });
    S.analysis = ana;
    validateMeta(meta);
    S.corpus = Search.createCorpus(S.works, S.meta, Search.FOLD_MAP);
    S.counts = S.metaOK && S.meta.counts ? S.meta.counts : deriveCounts();

    const ov = ana && ana.overview ? ana.overview : {};
    $("stWorks").textContent = fmt(ov.total_searchable_works ?? S.works.length);
    if (S.metaOK) $("stPdfs").textContent = fmt(S.counts.pdf_verified_total ?? ((S.counts.acc || {}).h + (S.counts.acc || {}).v));
    else { $("stPdfs").textContent = fmt(ov.repo_pdf_files ?? S.works.filter((w) => w.pdf).length); document.querySelector("#metricPdfBtn .label").textContent = "Fulltekst-PDF i arkivet"; }

    const stored = store.get(LS.start);
    S.startOpen = stored === "skjult" ? false : stored === "open" ? true : !narrow();
    S.filterOpen = !narrow();

    S.st = U.parseHash(location.hash);
    S.lastHash = location.hash;
    applyStateToUi();
    showTab(S.st.tab, true);
    runSearch();
    renderModelUi();
    scheduleT1();
    if (S.st.q.trim()) startT1(true);
    window.addEventListener("hashchange", onHash);
    if (/debug=1/.test(location.hash) || /debug=1/.test(location.search)) installDebug();
  }

  function validateMeta(meta) {
    const n = S.works.length;
    let ok = !!meta && meta.schema === 1 && meta.n === n && Array.isArray(meta.ids) && meta.ids.length === n;
    if (ok) for (let i = 0; i < n; i++) if (meta.ids[i] !== S.works[i].id) { ok = false; break; }
    if (ok) for (const k of ["lang", "abs", "acc", "flag"]) if (typeof meta[k] !== "string" || meta[k].length !== n) { ok = false; break; }
    S.metaOK = ok;
    if (ok) { S.meta = meta; return; }
    S.degraded = true; S.noAbs = true;
    S.meta = deriveMeta();
    const msg = $("loadMsg");
    msg.textContent = meta ? "Søkedata passar ikkje til katalogen. Gammal søkemodus er på." : "Søkedata kunne ikkje lastast. Gammal søkemodus er på.";
    msg.hidden = false;
  }

  /* Utleidd meta når søkedata manglar: berre det som finst i katalogen */
  function deriveMeta() {
    const a = [], ab = [], l = [], f = [];
    for (const w of S.works) {
      const addr = w.oa_url || w.source_url || "";
      const isDoi = addr && (addr === w.doi || addr.startsWith("https://doi.org/"));
      a.push(w.pdf ? "h" : addr && !isDoi ? "u" : (w.doi || isDoi) ? "d" : "0");
      ab.push("0");
      l.push(LANGMAP[w.language] || "u");
      f.push(w.duplicate_status === "possible-duplicate" ? "d" : "0");
    }
    return { schema: 0, build_id: "0", acc: a.join(""), abs: ab.join(""), lang: l.join(""), flag: f.join(""), similar: null, vectors: null, query_vectors: null, abstracts: null };
  }
  function deriveCounts() {
    const m = S.meta;
    const oa = S.works.filter((w) => w._layer === "openalex").length;
    return { acc: tally(m.acc), abs: tally(m.abs), lang: tally(m.lang), flag: tally(m.flag), layers: { openalex: oa, nordic: S.works.length - oa }, year_range: [], sources: [], pdf_verified_total: 0 };
  }

  /* T1: ordsøk-indeks. Startar ved fokus, eller etter første teikning (requestIdleCallback eller setTimeout). */
  function scheduleT1() {
    if (!S.metaOK) return;
    const go = () => startT1(false);
    if (typeof window.requestIdleCallback === "function") setTimeout(() => window.requestIdleCallback(go, { timeout: 3000 }), 1000);
    else setTimeout(go, 1500);
    loadConfigEarly();
  }
  async function loadConfigEarly() {
    if (saveData()) return renderStart();
    await ensureConfig();
    renderStart();
  }
  function ensureConfig() {
    return once("config", async () => {
      const c = await sget(S.meta.config ? S.meta.config.file : "search_config.json", null);
      if (c && c.schema === 1) S.config = c;
      return c;
    });
  }
  function startT1(force) {
    if (!S.metaOK || S.t1) return;
    if (saveData() && !force) return;
    S.t1 = true;
    Promise.all([ensureConfig(), once("lex", () => sget(S.meta.lex ? S.meta.lex.file : "lex.json", null))]).then(([cfg, lex]) => {
      if (cfg && lex && lex.schema === 1 && lex.n === S.works.length) {
        S.engine = Search.createEngine(cfg, lex);
        if (!S.st.sim) runSearch();
      } else {
        S.t1failed = true;
        $("loadMsg").textContent = "Søkeindeksen kunne ikkje lastast. Søket brukar tittel, forfattar og tidsskrift.";
        $("loadMsg").hidden = false;
        if (S.result) renderAll();
      }
      renderStart();
    });
    once("access", () => sget(S.meta.access ? S.meta.access.file : "access.json", null)).then((a) => {
      if (a && a.items) { S.access = a.items; if (S.result) renderList(); }
      else { S.accessFailed = true; if (S.result) renderList(); }
    });
  }

  /* ---------- støttefiler ved bruk ---------- */
  function ensureSim() {
    if (!S.metaOK || !S.meta.similar) return Promise.resolve(null);
    return once("sim", async () => {
      const buf = await sbin(S.meta.similar.file);
      const k = S.meta.similar.k, n = S.works.length;
      if (!buf || buf.byteLength !== n * k * 3) return null;
      S.sim = { nbr: new Uint16Array(buf, 0, n * k), sim: new Uint8Array(buf, n * k * 2, n * k), k };
      return S.sim;
    }).then((v) => { if (!v) S.simFailed = true; return v; });
  }
  function ensureVectors() {
    if (!S.metaOK || !S.meta.vectors) return Promise.resolve(null);
    return once("vectors", async () => {
      const buf = await sbin(S.meta.vectors.file);
      const n = S.works.length, dim = S.meta.vectors.dim;
      if (!buf || buf.byteLength !== n * dim) return null;
      S.vectors = new Int8Array(buf);
      return S.vectors;
    });
  }
  function ensureQV() {
    if (!S.metaOK || !S.meta.query_vectors) return Promise.resolve(null);
    return once("qv", async () => {
      const q = await sget(S.meta.query_vectors.file, null);
      if (q && q.queries) S.qvs = q.queries;
      return S.qvs;
    });
  }
  function ensureContext() { return once("ctx", async () => { S.ctx = await jget("data/work_context.json", {}); return S.ctx; }); }
  function ensureInst() {
    return once("inst", async () => {
      const d = await jget("data/institutions.json", null);
      if (!d || !d.items) return null;
      S.insts = d.items;
      for (const it of d.items) { S.instSets.set(it.id, new Set(it.work_ids || [])); S.instName.set(it.id, it.name); }
      return S.insts;
    });
  }
  function ensureGlossary() {
    if (!S.metaOK) return Promise.resolve(null);
    return once("glossary", async () => { S.glossary = await sget(S.meta.glossary ? S.meta.glossary.file : "glossary.json", null); return S.glossary; });
  }
  function shardOf(i) { return Math.floor(i / ((S.meta.abstracts && S.meta.abstracts.shard_size) || 128)); }
  function ensureShard(k) {
    if (S.noAbs || !S.meta.abstracts) return Promise.resolve(null);
    if (S.shards.has(k)) return Promise.resolve(S.shards.get(k));
    const name = String(k).padStart(3, "0");
    return once("shard" + k, async () => {
      const d = await sget(`${S.meta.abstracts.dir}/${S.meta.abstracts.pattern.replace("{NNN}", name)}`, null);
      S.shards.set(k, d || false);
      return d;
    });
  }
  /* undefined = ikkje lasta, null = lasta men inga oppføring */
  function shardEntry(i) {
    const sh = S.shards.get(shardOf(i));
    if (sh === undefined) return undefined;
    return sh && sh[S.works[i].id] ? sh[S.works[i].id] : null;
  }

  /* ---------- språkmodell ---------- */
  function modelCfg() { return S.metaOK && S.meta.browser_model ? S.meta.browser_model : null; }
  function setupEmbedder() {
    if (S.embed || !modelCfg()) return S.embed;
    S.embed = Emb.create({
      cfg: modelCfg(),
      importer: S.debugImporter || undefined,
      onState(st, info) {
        S.modelState = st;
        S.modelMsg = st === "feil" ? "Språkmodellen kunne ikkje lastast. Søket brukar ord og ordliste i staden." : "";
        if (st === "klar") { store.set(LS.model, "pa"); ensureVectors().then(() => runSearch()); }
        if (st === "feil") store.del(LS.model);
        renderModelUi();
        if (st === "klar") scheduleEncode();
      },
      onProgress(frac) { S.modelProgress = frac; const p = $("modelProg"); if (p) p.value = frac; const t = $("modelProgTxt"); if (t) t.textContent = Math.round(frac * 100) + " %"; },
    });
    return S.embed;
  }
  function modelSizeText() {
    const c = modelCfg();
    const mb = c ? (c.download_mb_rounded || Math.round((c.download_bytes || 350e6) / 1e6 / 5) * 5) : 350;
    return `ca. ${mb} MB`;
  }
  function renderModelUi() {
    const btn = $("modelBtn"), panel = $("modelPanel"), st = S.modelState;
    if (!modelCfg()) { btn.hidden = true; panel.hidden = true; return; }
    btn.hidden = false;
    btn.textContent = st === "klar" ? "Språkmodell: på" : st === "lastar" ? "Språkmodell lastar…" : "Slå på språkmodell";
    btn.setAttribute("aria-expanded", String(S.modelPanelOpen));
    $("modelState").textContent = st === "feil" ? S.modelMsg : "";
    panel.hidden = !S.modelPanelOpen;
    if (!S.modelPanelOpen) return;
    const warn = narrow() || lowMem() ? " Stor nedlasting; best på skrivebord." : "";
    if (st === "lastar") {
      panel.innerHTML = `<p>Lastar språkmodellen. Dette kan ta fleire minutt første gong.</p><p><progress id="modelProg" max="1" value="${esc(S.modelProgress)}"></progress> <span id="modelProgTxt">${Math.round(S.modelProgress * 100)} %</span></p><button type="button" class="act act-block" data-model="cancel">Avbryt</button>`;
    } else if (st === "klar") {
      panel.innerHTML = `<p>Språkmodellen er på. Søk gir treff etter ord og etter meining, òg på tvers av språk. Kvart søk kan ta nokre sekund.</p><button type="button" class="act act-block" data-model="off">Slå av</button> <button type="button" class="act act-block" data-model="close">Lukk</button>`;
    } else {
      panel.innerHTML = `<h3>Språkmodell i nettlesaren</h3>
        <p>Finn verk etter meining, òg på tvers av språk: ei norsk spørjing finn engelske verk.</p>
        <ul class="plain">
          <li>Nedlasting: ${esc(modelSizeText())}, éin gong. Modellen vert hugsa i nettlesaren.${esc(warn)}</li>
          <li>Spørjinga vert rekna ut i nettlesaren og vert ikkje sendt nokon stad. Berre modellfilene vert henta, frå jsDelivr og huggingface.co.</li>
          <li>Passar best på nett utan datakvote og på skrivebord. Utan modell fungerer søket med ord og ordliste.</li>
        </ul>
        ${S.modelMsg ? `<p class="warn">${esc(S.modelMsg)}</p>` : ""}
        <button type="button" class="act act-block" data-model="on">Last ned og slå på</button> <button type="button" class="act act-block" data-model="close">Lukk</button>`;
    }
  }
  function onModelAction(a) {
    const emb = setupEmbedder();
    if (a === "on" && emb) { S.modelProgress = 0; emb.enable(); renderModelUi(); }
    else if (a === "cancel" && emb) { emb.cancel(); store.del(LS.model); }
    else if (a === "off" && emb) { emb.cancel(); store.del(LS.model); S.modelQV.clear(); runSearch(); }
    else if (a === "close") { S.modelPanelOpen = false; renderModelUi(); }
  }
  /* Slå på stille frå cache når søkefeltet får fokus (berre om brukaren slo på modellen før) */
  async function silentModel() {
    if (store.get(LS.model) !== "pa" || S.modelState !== "av" || !modelCfg()) return;
    const emb = setupEmbedder();
    const ok = await emb.silent();
    if (!ok && emb.state === "av") store.del(LS.model);
  }
  function scheduleEncode() {
    const q = S.st.q.trim();
    if (!q || S.modelState !== "klar" || S.st.sim) return;
    const key = Search.normalizeKey(q);
    if (S.modelQV.has(key)) return;
    clearTimeout(S.encTimer);
    S.encPending = true;
    S.encKey = key;
    S.encTimer = setTimeout(async () => {
      try {
        const v = await S.embed.encode(key);
        if (key !== Search.normalizeKey(S.st.q)) return; // utdatert
        S.modelQV.set(key, v);
        await ensureVectors();
        S.encPending = false;
        runSearch();
      } catch (e) {
        S.encPending = false;
        renderStatus();
      }
    }, 400);
    renderStatus();
  }
  function installDebug() {
    window.__dtDebug = {
      embed: async (q) => { const emb = setupEmbedder(); if (emb.state !== "klar") await emb.enable(); return emb.encode(q); },
      stored: (q) => (S.qvs && S.qvs[Search.normalizeKey(q)] ? Search.decodeQV(S.qvs[Search.normalizeKey(q)]) : null),
      state: S,
      setImporter: (fn) => { S.debugImporter = fn; S.embed = null; },
    };
  }

  /* ---------- tilstand og adresse ---------- */
  function filtersOf(st) {
    return { yr: st.yr, cc: st.cc, kind: st.kind, lang: st.lang, tilg: st.tilg, inst: st.inst && S.instSets.has(st.inst) ? S.instSets.get(st.inst) : null, au: st.au, dup: st.dup };
  }
  function stateFiltersActive(st) { return U.filterCount(st) > 0; }

  function applyStateToUi() {
    const st = S.st;
    $("qInput").value = st.sim ? "" : st.q;
    $("yrFrom").value = st.yr && st.yr[0] ? st.yr[0] : "";
    $("yrTo").value = st.yr && st.yr[1] ? st.yr[1] : "";
    $("kindSel").value = st.kind; $("langSel").value = st.lang; $("ccSel").value = st.cc; $("tilgSel").value = st.tilg;
    $("dupChk").checked = !st.dup;
    $("sortSel").value = effSort();
  }
  function effSort() {
    const q = S.st.q.trim();
    const s = S.st.sort;
    if (!q && (s === "rel" || s === "first" || !s)) return "cited";
    return s || (q ? "rel" : "cited");
  }
  function writeHash(push) {
    const h = U.buildHash(S.st);
    if (h === location.hash) return;
    S.lastHash = h;
    if (push) location.hash = h; else history.replaceState(null, "", h);
  }
  /* Navigering i katalogen: set felt, nullstill verk/liste/liknande om ikkje oppgitt */
  function go(patch, opts = {}) {
    S.st = Object.assign(S.st, { tab: "korpus", sim: "", work: "", list: null, anchor: "" }, patch);
    if (S.st.sort === (S.st.q.trim() ? "rel" : "cited")) S.st.sort = "";
    S.shown = STEP;
    S.expandedId = S.st.work || null;
    if (!opts.keepTab) showTab("korpus", true);
    applyStateToUi();
    writeHash(opts.push !== false);
    runSearch();
    if (S.st.sim) S.scrollSim = opts.scroll !== false;
    else if (opts.scroll !== false) scrollToList();
  }
  function onHash() {
    if (location.hash === S.lastHash) return;
    S.lastHash = location.hash;
    S.st = U.parseHash(location.hash);
    S.shown = STEP;
    S.expandedId = S.st.work || null;
    applyStateToUi();
    showTab(S.st.tab, true);
    runSearch();
    if (S.st.anchor) setTimeout(() => { const el = $(S.st.anchor); if (el) el.scrollIntoView(); }, 50);
  }
  function scrollToList() {
    const el = S.st.sim ? $("simBanner") : document.querySelector(".resultline");
    if (el) { el.scrollIntoView({ block: "start" }); if (S.st.sim) { el.setAttribute("tabindex", "-1"); el.focus({ preventScroll: true }); } }
  }

  /* ---------- søk ---------- */
  async function runSearch() {
    const seq = ++S.seq;
    const st = S.st;
    const q = st.q.trim();

    if (st.inst && !S.instSets.has(st.inst)) {
      $("loadMsg").textContent = "Lastar filter..."; $("loadMsg").hidden = false;
      const ok = await ensureInst();
      if (seq !== S.seq) return;
      if (!ok || !S.instSets.has(st.inst)) {
        $("loadMsg").textContent = "Filteret for institusjon kunne ikkje lastast og er fjerna.";
        S.st.inst = ""; writeHash(false);
      } else if (!S.degraded) { $("loadMsg").hidden = true; }
    }

    if (st.sim) { buildSimResult(seq); return; }

    const mask = S.corpus.mask(filtersOf(st));
    const sort = effSort();
    const res = { q, sort, list: [], total: 0, cap: 0, capped: false, hasQuery: !!q, mode: "ord", rel: [], terms: new Set(), core: [], legacy: false, info: null, simPct: null, pinned: null };

    if (q) {
      if (!S.engine) {
        res.legacy = true;
        if (!S.qf) S.qf = S.works.map((w) => Search.fold(`${w.title || ""} ${(w.authors || []).join(" ")} ${w.source || ""} ${w.venue || ""} ${w.doi || ""} ${w.topic || ""}`));
        const pos = Search.legacySearch(S.qf, q, Search.FOLD_MAP, mask, 0);
        const toks = Search.tokenize(q);
        const score = (i) => { const t = Search.fold(S.works[i].title || ""); return toks.reduce((s, x) => s + (t.indexOf(x) >= 0 ? 1 : 0), 0); };
        pos.sort((a, b) => (score(b) - score(a)) || ((S.works[b].citations || 0) - (S.works[a].citations || 0)) || (a - b));
        res.rel = pos.slice(0, 300);
        res.core = toks;
        res.list = sort === "rel" || sort === "first" ? res.rel : S.corpus.sortList(pos.slice(0, 2000), sort);
        res.total = res.list.length;
        for (const t of toks) res.terms.add(t);
        if (S.metaOK) { ensureQV(); ensureSim(); }
      } else {
        const key = Search.normalizeKey(q);
        let qv = null, src = "";
        if (S.modelQV.has(key)) { qv = S.modelQV.get(key); src = "modell"; }
        else if (S.qvs && S.qvs[key]) {
          if (!S.qvCache.has(key)) S.qvCache.set(key, Search.decodeQV(S.qvs[key], S.meta.vectors ? S.meta.vectors.scale : 127));
          qv = S.qvCache.get(key); src = "lagra";
          if (!S.vectors) { ensureVectors().then((v) => { if (v && seq === S.seq) runSearch(); }); }
        }
        if (S.metaOK && !S.qvs && S.meta.query_vectors) ensureQV().then((v) => { if (v && seq === S.seq && v[key]) runSearch(); });
        if (S.metaOK && !S.sim && S.meta.similar) ensureSim().then((v) => { if (v && seq === S.seq) runSearch(); });
        const out = Search.run(S.engine, q, { mask, n: S.works.length, qv: qv && S.vectors ? qv : null, vectors: S.vectors, dim: S.meta.vectors ? S.meta.vectors.dim : 256, sim: S.sim, titles: S.corpus.titleKeys() });
        res.mode = out.mode === "sem" ? src : "ord";
        res.rel = out.hits.map((h) => h.d);
        res.cap = out.cap; res.capped = out.capped;
        res.core = out.lex.core; res.info = out.lex;
        for (const t of out.lex.terms) res.terms.add(t);
        for (const t of out.lex.core) res.terms.add(t);
        if (sort === "rel") res.list = res.rel;
        else if (sort === "first") {
          const scores = new Map(out.fused.map((e) => [e.d, e.rrf]));
          res.list = S.corpus.sortList(Search.sortPool(out), "first", { scores, max: out.fused.length ? out.fused[0].rrf : 1 });
        } else {
          res.list = S.corpus.sortList(Search.sortPool(out), sort);
        }
        res.total = res.list.length;
        if (S.modelState === "klar" && !S.modelQV.has(key)) scheduleEncode();
      }
    } else {
      const all = [];
      for (let i = 0; i < S.works.length; i++) if (!mask || mask[i]) all.push(i);
      res.list = S.corpus.sortList(all, sort);
      res.total = res.list.length;
    }
    if (st.work && S.pos.has(st.work)) {
      const p = S.pos.get(st.work);
      res.pinned = p;
      res.list = res.list.filter((i) => i !== p);
    }
    S.result = res;
    S.hl = { terms: res.terms };
    if (!$("loadMsg").textContent.startsWith("Søkedata") && !$("loadMsg").textContent.startsWith("Søkeindeksen")) $("loadMsg").hidden = true;
    renderAll();
  }

  function buildSimResult(seq) {
    const id = S.st.sim;
    const i = S.pos.get(id);
    ensureSim().then(() => {
      if (seq !== S.seq) return;
      if (i === undefined || !S.sim) {
        S.result = { q: "", sort: "sim", list: [], total: 0, sim: true, simPct: new Map(), terms: new Set(), rel: [], core: [], failed: true, pinned: i === undefined ? null : i };
        S.hl = { terms: new Set() };
        renderAll(); return;
      }
      const k = S.sim.k, pct = new Map(), list = [];
      for (let e = 0; e < k; e++) { const d = S.sim.nbr[i * k + e]; list.push(d); pct.set(d, U.simPercent(S.sim.sim[i * k + e])); }
      S.result = { q: "", sort: "sim", list, total: list.length, sim: true, simPct: pct, terms: new Set(), rel: [], core: [], pinned: i };
      S.hl = { terms: new Set() };
      renderAll();
      if (S.scrollSim) { S.scrollSim = false; scrollToList(); }
    });
  }

  /* ---------- teikning ---------- */
  function renderAll() {
    renderFilterUi();
    renderStatus();
    renderChips();
    renderBanner();
    renderCounter();
    renderList();
    renderStart();
    renderZero();
    renderPeople();
    renderReading();
    renderExportMenu();
    if (S.result && S.result.hasQuery && !saveData()) loadTeasers();
  }

  function renderFilterUi() {
    const st = S.st, n = U.filterCount(st);
    $("filterToggle").textContent = n ? `Filter (${n} aktive)` : "Filter";
    $("filterToggle").setAttribute("aria-expanded", String(S.filterOpen));
    $("filterPanel").classList.toggle("open", S.filterOpen);
    $("resetBtn").hidden = !(n || st.q || st.sim || st.work || st.sort);
    $("metricPdfBtn").classList.toggle("active-metric", st.tilg === "open");
    $("metricAllBtn").classList.toggle("active-metric", st.tilg !== "open");
    const hasQ = !!st.q.trim();
    for (const o of $("sortSel").options) { if (o.value === "rel" || o.value === "first") o.disabled = !hasQ; }
    $("sortSel").value = effSort();
    const d = (S.counts.flag || {}).d;
    $("dupLbl").textContent = "Skjul moglege dublettar" + (typeof d === "number" && !S.degraded ? ` (${fmt(d)} skjulte)` : "");
  }

  function renderStatus() {
    const el = $("statusLine"), r = S.result, st = S.st;
    if (!r || !st.q.trim() || st.sim) { el.textContent = ""; return; }
    if (r.legacy) { el.textContent = S.degraded ? "Søker i tittel, forfattar og tidsskrift." : "Søker i tittel, forfattar og tidsskrift. Samandrag kjem med om eit lite augneblikk."; return; }
    const mode = r.mode === "modell" ? "Ord og meining (språkmodell)" : r.mode === "lagra" ? "Ord og meining (lagra spørjing)" : "Ord og ordliste";
    const parts = [mode, `${fmt(r.total)} treff`, "søker i tittel, forfattar, tidsskrift, tilknyting og samandrag"];
    if (S.encPending && S.modelState === "klar") parts.push("Reknar ut meining...");
    el.textContent = parts.join(" · ");
  }

  function renderChips() {
    const st = S.st, c = [];
    const chip = (key, text) => c.push(`<button type="button" class="chip" data-clear="${esc(key)}" aria-label="Fjern: ${esc(text)}">${esc(text)} <span aria-hidden="true">×</span></button>`);
    if (st.yr && (st.yr[0] || st.yr[1])) chip("yr", `År: ${st.yr[0] || "…"}–${st.yr[1] || "…"}`);
    if (st.kind) chip("kind", "Type: " + $("kindSel").querySelector(`option[value="${st.kind}"]`).textContent);
    if (st.lang) chip("lang", "Språk: " + $("langSel").querySelector(`option[value="${st.lang}"]`).textContent);
    if (st.cc) chip("cc", "Land: " + ($("ccSel").querySelector(`option[value="${st.cc}"]`) || { textContent: st.cc }).textContent);
    if (st.tilg) chip("tilg", "Tilgang: " + $("tilgSel").querySelector(`option[value="${st.tilg}"]`).textContent);
    if (st.inst) chip("inst", "Institusjon: " + (S.instName.get(st.inst) || st.inst));
    if (st.au) chip("au", "Forfattar: " + st.au);
    if (st.dup) chip("dup", "Dublettar er synlege");
    $("chips").innerHTML = c.join("");
  }

  function renderBanner() {
    const b = $("simBanner"), st = S.st;
    if (!st.sim) { b.hidden = true; b.innerHTML = ""; return; }
    const w = S.byId.get(st.sim);
    b.hidden = false;
    const i = S.pos.get(st.sim);
    const note = i !== undefined && S.meta.abs[i] === "0" && !S.noAbs ? `<p class="subline">Likskapen bygger berre på tittelen for dette verket.</p>` : "";
    b.innerHTML = `<div class="sim-head"><strong>Liknande: ${esc(w ? w.title : st.sim)}</strong>${note}</div><button type="button" class="act act-block" data-simback="1">Tilbake til førre liste</button>`;
  }

  function renderCounter() {
    const r = S.result, el = $("hitCount");
    if (!r) { el.textContent = "Lastar…"; return; }
    const N = S.works.length;
    let t;
    if (r.sim) t = r.failed ? "Liknande verk er ikkje tilgjengelege no." : `${fmt(r.total)} liknande verk`;
    else {
      t = `${fmt(r.total + (r.pinned != null ? 1 : 0))} av ${fmt(N)} verk`;
      if (r.hasQuery && r.sort === "rel" && r.capped) t += ` · viser dei ${fmt(r.total)} mest relevante`;
      if (!S.st.dup && !S.degraded && (S.counts.flag || {}).d) {
        /* Talet gjeld heile korpuset; det vert berre vist når lista ikkje er smalna inn av søk eller filter */
        const narrowed = !!(S.st.q.trim() || U.filterCount(S.st));
        t += narrowed ? " · moglege dublettar er skjulte" : ` · ${fmt(S.counts.flag.d)} moglege dublettar skjulte`;
      }
    }
    el.textContent = t;
    const has = r.list.length > 0 || r.pinned != null;
    $("copyLinkBtn").hidden = !has;
    $("exportBtn").hidden = !has || S.degraded || r.sim;
    $("listBtn").textContent = `Leseliste (${S.reading.length})`;
    $("listBtn").setAttribute("aria-expanded", String(!$("readingPanel").hidden));
  }

  function authorsText(w, n = 4) {
    const a = w.authors || [];
    return a.slice(0, n).join(", ") + (a.length > n ? " mfl." : "");
  }

  function rowHtml(i, o = {}) {
    const w = S.works[i], id = w.id;
    const code = S.meta.acc[i];
    const item = S.access ? S.access[id] : null;
    const info = accInfo(i, w);
    const detail = S.expandedId === id;
    const absOpen = !S.noAbs && (detail || S.openAbs.has(id));
    const inList = S.reading.includes(id);
    const cc = (w.countries && w.countries.length ? w.countries : (w.source_country ? [w.source_country] : [])).join(", ");
    const sub = [];
    const au = authorsText(w);
    if (au) sub.push(au);
    if (w.venue || w.source) sub.push(w.venue || w.source);
    if (typeof w.citations === "number" && w.citations > 0) sub.push(`${fmt(w.citations)} sit.`);
    if (o.pct != null) sub.push(`likskap ${o.pct} %`);
    let primary = U.accessLinkHtml(info);
    if (!primary && code === "0") {
      const pl = U.publisherLink(w, item);
      if (pl) primary = `<a class="act act-link acc-0" href="${esc(pl.href)}" target="_blank" rel="noopener noreferrer">${esc(pl.label)}</a>`;
    }
    const fl = U.flagInfo(S.meta.flag[i]);
    const tags = [U.accessTagHtml(info), fl ? `<span class="tag tag-flag" title="${esc(fl.help)}">${esc(fl.label)}</span>` : ""].filter(Boolean).join(" ");
    const teaser = !absOpen && o.teaser && !S.noAbs ? `<p class="teaser" data-teaser="${esc(id)}">${teaserHtml(i)}</p>` : "";
    const sims = S.metaOK && S.meta.similar && !o.pinned && !detail ? `<button type="button" class="act" data-sim="${esc(id)}">Liknande</button>` : "";
    const absBtn = S.noAbs ? "" : `<button type="button" class="act" data-abs="${esc(id)}" aria-expanded="${absOpen}">Samandrag</button>`;
    return `<article class="item${o.pinned ? " item-pinned" : ""}" data-id="${esc(id)}">
      <div class="meta-col">${esc(w.year || "")}${cc ? `<br>${esc(cc)}` : ""}</div>
      <div class="main">
        <h3 class="title"><button class="title-btn" type="button" data-toggle="${esc(id)}" aria-expanded="${detail}">${esc(w.title || "(utan tittel)")}</button></h3>
        ${sub.length ? `<p class="subline">${esc(sub.join(" · "))}</p>` : ""}
        ${tags ? `<p class="tags">${tags}</p>` : ""}
        ${teaser}
      </div>
      <div class="actions">${primary}${absBtn}${sims}<button type="button" class="act" data-rl="${esc(id)}" aria-pressed="${inList}">${inList ? "✓ I lista" : "+ Leseliste"}</button><button type="button" class="act" data-copyref="${esc(id)}">Kopier som referanse</button></div>
      ${absOpen && !detail ? `<div class="slot">${absBlockHtml(i)}</div>` : ""}
      ${detail ? detailHtml(i) : ""}
    </article>`;
  }

  function teaserHtml(i) {
    const e = shardEntry(i);
    if (!e) return "";
    const t = e.t.length > 280 ? e.t.slice(0, 280).replace(/\s+\S*$/, "") + "…" : e.t;
    return U.highlight(t, S.hl.terms, Search.FOLD_MAP);
  }

  function absBlockHtml(i) {
    const w = S.works[i];
    const item = S.access ? S.access[w.id] : null;
    if (S.meta.abs[i] === "0") return U.noAbstractHtml(w, item);
    const e = shardEntry(i);
    if (e === undefined) { ensureShard(shardOf(i)).then(() => refreshRow(w.id)); return U.abstractStateHtml("loading"); }
    if (!e) return S.shards.get(shardOf(i)) === false ? U.abstractStateHtml("error") : U.noAbstractHtml(w, item);
    return U.abstractHtml(e, { terms: S.hl.terms, fm: Search.FOLD_MAP });
  }

  function neighborsOf(i, k) {
    if (!S.sim) return null;
    const out = [], K = S.sim.k;
    for (let e = 0; e < Math.min(k, K); e++) out.push({ d: S.sim.nbr[i * K + e], pct: U.simPercent(S.sim.sim[i * K + e]) });
    return out;
  }

  function detailHtml(i) {
    const w = S.works[i], id = w.id;
    const code = S.meta.acc[i];
    const item = S.access ? S.access[id] : null;
    const info = accInfo(i, w);
    const links = [];
    const doi = U.doiHref(w);
    if (doi && code !== "d" && code !== "0") links.push(`<a class="act act-block" href="${esc(doi)}" target="_blank" rel="noopener noreferrer">Utgjevarside</a>`);
    const src = U.safeHref(w.source_url);
    if (src && src !== info.href) links.push(`<a class="act act-block" href="${esc(src)}" target="_blank" rel="noopener noreferrer">Kjelde i arkivet</a>`);
    const buttons = `<button type="button" class="act act-block" data-copylink="${esc(id)}">Kopier lenkje til verket</button>`;

    let simBox = "";
    if (S.metaOK && S.meta.similar) {
      const nb = neighborsOf(i, 6);
      if (S.simFailed) simBox = `<p class="subline">Liknande verk er ikkje tilgjengelege no.</p>`;
      else if (!nb) { ensureSim().then(() => refreshRow(id)); simBox = `<p class="subline">Lastar liknande verk…</p>`; }
      else simBox = `<ul class="plain detail-list">${nb.map(({ d, pct }) => { const sw = S.works[d]; return `<li><a href="#verk/${esc(encodeURIComponent(sw.id))}" data-jump="${esc(sw.id)}">${esc(sw.year ? sw.year + " · " : "")}${esc(sw.title)}</a> <span class="score">${pct} %</span></li>`; }).join("")}</ul><button type="button" class="act act-block" data-sim="${esc(id)}">Vis alle 20</button><p class="subline">${esc(U.SIM_NOTE)}.</p>`;
    }

    let cit = "";
    if (!S.ctx) { ensureContext().then(() => refreshRow(id)); cit = `<p class="subline">Lastar siteringar…</p>`; }
    else {
      const ctx = S.ctx[id] || {};
      const citedBy = (ctx.cited_by || []).map((x) => S.byId.get(x)).filter(Boolean).slice(0, 6);
      const cites = (ctx.cites || []).map((x) => S.byId.get(x)).filter(Boolean).slice(0, 6);
      const li = (cw) => `<li><a href="#verk/${esc(encodeURIComponent(cw.id))}" data-jump="${esc(cw.id)}">${esc(cw.year ? cw.year + " · " : "")}${esc(cw.title)}</a></li>`;
      const grp = (lbl, arr) => (arr.length ? `<p class="subline">${lbl}</p><ul class="plain detail-list">${arr.map((c) => li(c)).join("")}</ul>` : "");
      cit = `<h4>Siteringar i korpuset (${(ctx.cited_by || []).length} inn, ${(ctx.cites || []).length} ut)</h4>` +
        (citedBy.length || cites.length ? grp("Sitert av", citedBy) + grp("Siterer", cites) : `<p class="subline">Ingen siteringar i korpuset.</p>`);
    }

    return `<div class="inline-detail">
      ${S.noAbs ? "" : `<div class="detail-sec">${absBlockHtml(i)}</div>`}
      <div class="detail-sec detail-links">${links.join("")}${buttons}</div>
      ${S.metaOK && S.meta.similar ? `<div class="detail-sec"><h4>Liknande verk</h4>${simBox}</div>` : ""}
      <div class="detail-sec">${cit}</div>
      <div class="detail-sec"><p class="subline">Ikkje kontrollert av eit menneske. <a href="#om" data-tab="om">Les om kva det betyr</a>.</p></div>
    </div>`;
  }

  function refreshRow(id) {
    const el = Array.from(document.querySelectorAll("#corpusList article.item")).find((a) => a.dataset.id === id);
    if (!el) return;
    const i = S.pos.get(id);
    const r = S.result;
    const rank = r ? r.list.indexOf(i) : -1;
    const wrap = document.createElement("div");
    wrap.innerHTML = rowHtml(i, { teaser: r && r.hasQuery && rank >= 0 && rank < 5, pct: r && r.simPct ? r.simPct.get(i) : null, pinned: r && r.pinned === i });
    el.replaceWith(wrap.firstElementChild);
  }

  function renderList() {
    const r = S.result;
    if (!r) return;
    const box = $("corpusList");
    const rows = r.list.slice(0, S.shown);
    let html = "";
    if (r.pinned != null) html += rowHtml(r.pinned, { pinned: true });
    html += rows.map((i, rank) => rowHtml(i, { teaser: r.hasQuery && rank < 5, pct: r.simPct ? r.simPct.get(i) : null })).join("");
    if (r.sim && r.list.length) html += `<p class="subline foot-note">${esc(U.SIM_NOTE)}.</p>`;
    box.innerHTML = html;
    $("moreCorpusBtn").hidden = rows.length >= r.list.length;
    const more = r.list.length - rows.length;
    $("moreCorpusBtn").textContent = `Vis ${Math.min(STEP, more)} fleire`;
  }

  async function loadTeasers() {
    const r = S.result;
    if (!r || !r.hasQuery || S.noAbs) return;
    const top = r.list.slice(0, 5);
    const need = [...new Set(top.filter((i) => S.meta.abs[i] !== "0").map(shardOf))];
    if (!need.length) return;
    await Promise.all(need.map(ensureShard));
    if (r !== S.result) return;
    for (const el of document.querySelectorAll("[data-teaser]")) {
      const i = S.pos.get(el.dataset.teaser);
      if (i !== undefined && !el.innerHTML) el.innerHTML = teaserHtml(i);
    }
  }

  /* ---------- startpanel ---------- */
  function renderStart() {
    const st = S.st, panel = $("startPanel"), openBtn = $("startOpenBtn");
    const idle = S.result && !st.q.trim() && !st.sim && !st.work && !st.list && !U.filterCount(Object.assign({}, st, { dup: false }));
    const show = idle && S.startOpen;
    panel.hidden = !show;
    openBtn.hidden = !(idle && !S.startOpen);
    if (!show) return;
    const exs = (S.config && S.config.examples ? S.config.examples.map((e) => e.q) : Om.DEFAULT_EXAMPLES);
    $("startChips").innerHTML = exs.map((q) => `<button type="button" class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join("");
    $("startLines").innerHTML = Om.startLines(S.counts).map((l) => `<li>${l}</li>`).join("");
    $("startLang").textContent = Om.langNote(S.counts);
    const terms = ["research through design", "infrastructuring", "taus kunnskap", "deltakande design", "tenestedesign", "samdesign"];
    $("startTerms").innerHTML = "Ordforklaring: " + terms.map((t) => `<button type="button" class="chip chip-term" data-gloss="${esc(t)}" title="${esc(glossHint(t))}">${esc(t)}</button>`).join(" ");
    if (!S.glossary && S.metaOK && !saveData()) ensureGlossary().then((g) => { if (g) renderStart(); });
  }
  function glossHint(t) {
    const g = S.glossary && S.glossary.terms ? S.glossary.terms.find((x) => x.term.toLowerCase() === t || (x.q || "").toLowerCase() === t) : null;
    return g ? g.nn : "Forklaring i ordlista";
  }

  /* ---------- null treff ---------- */
  function renderZero() {
    const box = $("zeroBox"), r = S.result;
    const waiting = r && r.legacy && S.metaOK && !S.engine && !S.t1failed; // ordsøk-indeksen lastar enno
    const zero = r && !waiting && r.total === 0 && r.pinned == null && !r.sim && (r.hasQuery || U.filterCount(S.st));
    box.hidden = !zero;
    if (!zero) { box.innerHTML = ""; return; }
    const toks = r.core && r.core.length ? r.core.join(", ") : "";
    const sugg = suggestions(r.core || []);
    box.innerHTML = `<h3>Ingen treff</h3>
      ${r.hasQuery ? `<p>Søkte etter: <strong>${esc(toks || S.st.q)}</strong> (etter folding og fjerning av småord).</p><p>Prøv eitt eller to nøkkelord, engelsk eller norsk.</p>` : `<p>Ingen verk stemmer med filtera. Fjern eit filter eller trykk «Nullstill».</p>`}
      ${sugg.length ? `<p>Forslag:</p><div class="chips">${sugg.map((q) => `<button type="button" class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div>` : ""}
      ${S.modelState !== "klar" && modelCfg() ? `<button type="button" class="act act-block" data-model="open">Slå på språkmodell</button>` : ""}`;
    if (!S.glossary && S.metaOK) ensureGlossary().then((g) => { if (g && S.result === r) renderZero(); });
  }
  function suggestions(core) {
    const out = [];
    const terms = S.glossary && S.glossary.terms ? S.glossary.terms : [];
    const pre = core.filter((t) => t.length >= 3).map((t) => t.slice(0, Math.min(5, t.length)));
    for (const g of terms) {
      const hay = Search.fold([g.term, ...(g.en || []), ...(g.no || [])].join(" "));
      if (pre.some((p) => hay.indexOf(p) >= 0) && out.indexOf(g.q || g.term) < 0) out.push(g.q || g.term);
      if (out.length >= 3) break;
    }
    if (out.length < 3) {
      const ex = S.config && S.config.examples ? S.config.examples.map((e) => e.q) : Om.DEFAULT_EXAMPLES;
      for (const q of ex) { if (out.length >= 3) break; if (out.indexOf(q) < 0) out.push(q); }
    }
    return out.slice(0, 3);
  }

  /* ---------- personar og miljø (F13) ---------- */
  async function renderPeople() {
    const box = $("peoplePanel"), r = S.result;
    const ok = r && r.hasQuery && !r.sim && r.rel.length >= 5 && !S.degraded;
    if (!ok) { box.hidden = true; return; }
    if (!S.ctx) {
      if (saveData()) {
        box.hidden = false;
        box.innerHTML = `<h3>Personar og miljø for dette søket</h3><button type="button" class="act act-block" data-people="load">Vis personar og miljø</button>`;
        return;
      }
      box.hidden = false;
      box.innerHTML = `<h3>Personar og miljø for dette søket</h3><p class="subline">Lastar…</p>`;
      await ensureContext();
      if (r !== S.result) return;
    }
    const top = r.rel.slice(0, 100);
    const all = S.peopleAll;
    const ok2 = (c) => all || NORDIC_CC.has(c);
    const authors = new Map(), insts = new Map();
    for (const i of top) {
      const c = S.ctx[S.works[i].id];
      if (!c || !c.authors) continue;
      const seenInst = new Set();
      for (const a of c.authors) {
        const ii = (a.institutions || []).filter((x) => ok2(x.country));
        if (!ii.length) continue;
        const rec = authors.get(a.id) || { name: a.name, n: 0, inst: new Map() };
        rec.n++;
        for (const x of ii) rec.inst.set(x.id, { x, n: ((rec.inst.get(x.id) || { n: 0 }).n) + 1 });
        authors.set(a.id, rec);
        for (const x of ii) if (!seenInst.has(x.id)) { seenInst.add(x.id); const o = insts.get(x.id) || { x, n: 0 }; o.n++; insts.set(x.id, o); }
      }
    }
    const A = Array.from(authors.values()).sort((a, b) => (b.n - a.n) || a.name.localeCompare(b.name)).slice(0, 8);
    const I = Array.from(insts.values()).sort((a, b) => (b.n - a.n) || a.x.name.localeCompare(b.x.name)).slice(0, 6);
    box.hidden = false;
    if (!A.length) {
      box.innerHTML = `<h3>Personar og miljø for dette søket</h3><p class="subline">Ingen forfattarar med kjend tilknyting blant dei øvste treffa.</p>`;
      return;
    }
    const aRows = A.map((a) => {
      const best = Array.from(a.inst.values()).sort((x, y) => y.n - x.n)[0];
      return `<li><button type="button" class="link-row" data-au="${esc(a.name)}">${esc(a.name)}</button> <span class="subline">${a.n} ${U.plural(a.n, "verk", "verk")} · ${esc(best ? best.x.name : "")}${best && best.x.country ? ", " + esc(best.x.country) : ""}</span></li>`;
    }).join("");
    const iRows = I.map((o) => `<li><button type="button" class="link-row" data-inst="${esc(o.x.id)}">${esc(o.x.name)}</button> <span class="subline">${o.n} verk${o.x.country ? " · " + esc(o.x.country) : ""}</span></li>`).join("");
    box.innerHTML = `<h3>Personar og miljø for dette søket</h3>
      <h4>Forfattarar</h4><ul class="plain people">${aRows}</ul>
      <h4>Institusjonar</h4><ul class="plain people">${iRows}</ul>
      <p class="subline">Tel berre verk frå OpenAlex, der tilknytinga er kjend. Arkivverk manglar tilknyting. Rekna frå dei ${top.length} øvste treffa.</p>
      <button type="button" class="act act-block" data-people="toggle">${all ? "Berre Norden" : "Vis alle land"}</button>`;
  }

  /* ---------- leseliste (F12) ---------- */
  function loadReading() {
    try { const a = JSON.parse(store.get(LS.list) || "[]"); return Array.isArray(a) ? a.filter((x) => typeof x === "string").slice(0, 500) : []; } catch { return []; }
  }
  function saveReading() { store.set(LS.list, JSON.stringify(S.reading.slice(0, 500))); }
  function toggleReading(id) {
    const k = S.reading.indexOf(id);
    if (k >= 0) S.reading.splice(k, 1);
    else if (S.reading.length >= 500) { toast("Leseliste: høgst 500 verk."); return; }
    else S.reading.push(id);
    saveReading();
    document.querySelectorAll(`[data-rl]`).forEach((b) => {
      if (b.dataset.rl !== id) return;
      const on = S.reading.includes(id);
      b.setAttribute("aria-pressed", String(on));
      b.textContent = on ? "✓ I lista" : "+ Leseliste";
    });
    $("listBtn").textContent = `Leseliste (${S.reading.length})`;
    renderReading();
  }
  function shareUrl(ids) { return location.origin + location.pathname + "#liste=" + ids.slice(0, 60).map(encodeURIComponent).join("~"); }

  function exportItems(positions) {
    return positions.map((i) => {
      const w = S.works[i], code = S.meta.acc[i], it = S.access ? S.access[w.id] : null;
      const doi = U.doiHref(w);
      return { w, acc: code, pdfUrl: it && (code === "h" || code === "v" || code === "u") ? it[1] : "", url: it ? it[1] : (w.oa_url || w.source_url || ""), landing: doi || U.safeHref(w.source_url) || "", lang: ISO[S.meta.lang[i]] || "", flag: S.meta.flag[i] === "0" ? "" : S.meta.flag[i] };
    });
  }
  function download(kind, which, positions) {
    const items = exportItems(positions.slice(0, Exp.LIMIT));
    const text = Exp.build(kind, items);
    const blob = new Blob([text], { type: Exp.MIME[kind] });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = Exp.filename(kind, which); document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
  function exportButtons(which) {
    return `<span class="btn-row"><button type="button" class="act act-block" data-export="bibtex" data-which="${which}">BibTeX</button><button type="button" class="act act-block" data-export="ris" data-which="${which}">RIS</button><button type="button" class="act act-block" data-export="csv" data-which="${which}">CSV</button></span>`;
  }
  function renderExportMenu() {
    const box = $("exportMenu"), r = S.result;
    if (box.hidden || !r) return;
    const all = (r.pinned != null ? [r.pinned] : []).concat(r.list);
    const n = all.length;
    box.innerHTML = `<p>Eksporter ${fmt(Math.min(n, Exp.LIMIT))} verk (berre metadata, ingen samandrag).${n > Exp.LIMIT ? ` Treffa er ${fmt(n)}; dei ${fmt(Exp.LIMIT)} første er med.` : ""}</p>${exportButtons("treff")}`;
  }

  function renderReading() {
    const box = $("readingPanel");
    if (S.st.list && box.hidden) box.hidden = false;
    if (box.hidden) { $("listBtn").textContent = `Leseliste (${S.reading.length})`; return; }
    const shared = S.st.list;
    const ids = shared ? shared : S.reading;
    const pos = ids.map((id) => S.pos.get(id)).filter((p) => p !== undefined);
    if (!pos.length) {
      box.innerHTML = `<h3>${shared ? "Delt leseliste" : "Leseliste"}</h3><p>${shared ? "Ingen av verka i lenkja finst i korpuset." : "Leselista er tom. Trykk «+ Leseliste» på eit verk. Lista vert lagra i denne nettlesaren."}</p>`;
      return;
    }
    const rows = pos.map((i) => {
      const w = S.works[i], info = accInfo(i, w);
      return `<li class="rl-row"><div><button type="button" class="link-row" data-jump="${esc(w.id)}">${esc(w.title)}</button><div class="subline">${esc([w.year, authorsText(w, 3), info.tag].filter(Boolean).join(" · "))}</div></div>${shared ? "" : `<button type="button" class="act" data-rl="${esc(w.id)}" aria-label="Fjern frå leseliste">Fjern</button>`}</li>`;
    }).join("");
    const tooMany = ids.length > 60;
    box.innerHTML = `<h3>${shared ? `Delt leseliste (${pos.length} verk)` : `Leseliste (${pos.length})`}</h3>
      ${shared ? `<button type="button" class="act act-block" data-rlsave="1">Lagre i leselista mi</button>` : ""}
      <ul class="plain rl">${rows}</ul>
      <div class="btn-row">${exportButtons("leseliste")}<button type="button" class="act act-block" data-rlrefs="1">Kopier alle som referansar</button>${shared ? "" : `<button type="button" class="act act-block" data-rlshare="1">Del lista</button><button type="button" class="act act-block" data-rlclear="1">Tøm lista</button>`}</div>
      ${tooMany && !shared ? `<p class="subline">Ei delt liste tek høgst 60 verk; dei 60 første er med.</p>` : ""}`;
  }

  /* ---------- faner ---------- */
  function showTab(t, noHash) {
    if (TABS.indexOf(t) < 0) t = "korpus";
    const changed = S.tabNow !== t;
    S.tabNow = t;
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === t));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${t}`));
    S.st.tab = t;
    if (!noHash) { const h = U.buildHash(S.st); S.lastHash = h; history.replaceState(null, "", h); }
    if (t === "siteringar") renderCitations();
    if (t === "analyse") renderAnalysis();
    if (t === "om") loadAbout();
    if (t === "teorielement") loadTeIntro();
    if (changed) window.scrollTo(0, 0);
  }
  function setTab(t) {
    if (t === "korpus") { go({ q: S.st.q, sort: S.st.sort }, { scroll: false, keepTab: false }); return; }
    S.st = Object.assign(S.st, { work: "", list: null });
    showTab(t);
  }

  async function loadTeIntro() {
    if (S.teLoaded) return;
    S.teLoaded = true;
    const d = await jget("data/teorielement/rader.json", null);
    const n = d && d.stats && d.stats.texts;
    if (typeof n === "number") $("teTexts").textContent = String(n);
  }

  async function loadAbout() {
    const root = $("omRoot");
    const render = () => { root.innerHTML = Om.aboutHtml(S.counts, S.about, S.quality, S.glossary, { built: S.meta && S.meta.built }); };
    render();
    if (!S.metaOK) return;
    const [a, q, g] = await Promise.all([
      once("about", async () => (S.about = await sget(S.meta.about ? S.meta.about.file : "about.json", null))),
      once("quality", async () => (S.quality = await sget(S.meta.quality ? S.meta.quality.file : "search_quality.json", null))),
      ensureGlossary(),
    ]);
    render();
    if (S.st.anchor) { const el = $(S.st.anchor); if (el) el.scrollIntoView(); }
  }

  /* ---------- kanon ---------- */
  async function renderCitations() {
    const q = Search.fold($("citQ").value.trim());
    const box = $("citBox");
    const match = (s) => !q || Search.fold(s).includes(q);

    if (S.citSub === "internal") {
      const rows = (S.analysis?.citations?.top_internally_cited || []).filter((r) => match(`${r.title} ${(r.authors || []).join(" ")}`));
      box.innerHTML = `<p class="subline">Tal: sitat frå Norden av sitat totalt.</p>` + rows.map((r) => {
        const sub = [(r.authors || []).join(", "), `${fmt(r.internal_citations)} av ${fmt(r.global_citations)}`].filter(Boolean).join(" · ");
        return `
          <article class="item">
            <div class="meta-col">${esc(r.year || "")}${(r.countries || []).length ? `<br>${esc(r.countries.join(", "))}` : ""}</div>
            <div class="main">
              <h3 class="title"><button class="title-btn" type="button" data-jump="${esc(r.id)}">${esc(r.title)}</button></h3>
              <p class="subline">${esc(sub)}</p>
            </div>
            <div class="actions">${r.pdf ? `<a class="act act-link acc-h" href="${esc(r.pdf)}" target="_blank" rel="noopener noreferrer">PDF</a>` : ""}</div>
          </article>`;
      }).join("");
      return;
    }

    if (S.citSub === "canon") {
      if (!S.canon) S.canon = (await jget("data/cited_canon.json", { items: [] })).items || [];
      const rows = S.canon.filter((r) => match(`${r.title} ${r.authors}`)).slice(0, 150);
      box.innerHTML = `<p class="subline">Tal: sitat frå Norden av sitat totalt.</p>` + rows.map((r) => {
        const sub = [r.authors, `${fmt(r.nordic_citing_count)} av ${fmt(r.global_citations)}`].filter(Boolean).join(" · ");
        const doiHref = U.doiHref({ doi: r.doi });
        return `
          <article class="item">
            <div class="meta-col">${esc(r.year || "")}</div>
            <div class="main">
              <h3 class="title">${esc(r.title)}</h3>
              <p class="subline">${esc(sub)}</p>
            </div>
            <div class="actions">${doiHref ? `<a class="act act-link acc-d" href="${esc(doiHref)}" target="_blank" rel="noopener noreferrer">Utgjevarside</a>` : ""}</div>
          </article>`;
      }).join("");
      return;
    }

    if (S.citSub === "authors") {
      if (!S.authors) S.authors = (await jget("data/authors.json", { items: [] })).items || [];
      const rows = S.authors.filter((a) => match(`${a.name} ${(a.institutions || []).join(" ")}`)).slice(0, 120);
      box.innerHTML = rows.map((a) => {
        const sub = [(a.institutions || []).slice(0, 2).join(", "), `${fmt(a.works)} verk`, `${fmt(a.openalex_citation_sum_on_snapshot_works)} sit.`].filter(Boolean).join(" · ");
        return `
          <article class="item">
            <div class="meta-col">${esc((a.countries || []).join(", "))}</div>
            <div class="main">
              <h3 class="title"><button class="title-btn" type="button" data-au="${esc(a.name)}">${esc(a.name)}</button></h3>
              <p class="subline">${esc(sub)}</p>
            </div>
          </article>`;
      }).join("");
      return;
    }

    if (S.citSub === "institutions") {
      if (!S.insts) await ensureInst();
      const rows = (S.insts || []).filter((i) => match(`${i.name} ${i.country}`)).slice(0, 120);
      box.innerHTML = `<p class="subline">Trykk på ein institusjon for å sjå verka i katalogen.</p>` + rows.map((i) => `
        <article class="item">
          <div class="meta-col">${esc(i.country || "")}</div>
          <div class="main">
            <h3 class="title"><button class="title-btn" type="button" data-inst="${esc(i.id)}">${esc(i.name)}</button></h3>
            <p class="subline">${fmt(i.works)} verk</p>
          </div>
        </article>`).join("");
    }
  }

  /* ---------- analyse ---------- */
  /* Klyngene i analysen er dei same åtte som på kartet: namn og tal frå kart.json, PDF-ane talde i katalogen. */
  async function kartClusters() {
    const d = await jget(`data/klynger/kart.json?v=${Math.round(Date.now() / 3600e3)}`, null);
    if (!d || !Array.isArray(d.klynger) || !Array.isArray(d.ids) || !Array.isArray(d.k)) return [];
    const pdf = new Map();
    d.ids.forEach((id, i) => { const w = S.byId.get(id); if (w && w.pdf) pdf.set(d.k[i], (pdf.get(d.k[i]) || 0) + 1); });
    return d.klynger.map((c) => ({ name: c.namn, n: c.n, pdfs: pdf.get(c.id) || 0 })).sort((a, b) => b.n - a.n);
  }
  async function renderAnalysis() {
    const a = S.analysis;
    if (!a) return;
    const decs = a.decades || [];
    const maxD = Math.max(1, ...decs.map((d) => d.total + (d.nordic_archives || 0)));
    const cs = a.countries || [];
    const cls = await kartClusters();
    const vens = (a.top_venues || []).slice(0, 15);
    $("anaRoot").innerHTML = `
      <div class="ana-grid">
        <div class="ana-sec">
          <h3>Verk per tiår</h3>
          <p class="subline">I parentes: verk med PDF i arkivet.</p>
          ${decs.map((d) => {
            const tot = d.total + (d.nordic_archives || 0);
            return `<div class="bar-line"><span>${esc(d.decade)}</span><div class="bar-bg"><div class="bar-a" style="width:${((tot / maxD) * 100).toFixed(1)}%"></div><div class="bar-b" style="width:${((d.pdfs / maxD) * 100).toFixed(1)}%"></div></div><span class="r">${fmt(tot)} (${fmt(d.pdfs)})</span></div>`;
          }).join("")}
        </div>
        <div class="ana-sec">
          <h3>Land</h3>
          <p class="subline">Open: del av OpenAlex-verka med open tilgang.</p>
          <div class="table-wrap">
            <table class="tbl-clean">
              <thead><tr><th>Land</th><th class="r">OpenAlex</th><th class="r">Arkiv</th><th class="r">PDF</th><th class="r">Open</th></tr></thead>
              <tbody>${cs.map((c) => `<tr><td><strong>${esc(COUNTRY_NAMES[c.country] || c.country)}</strong></td><td class="r">${fmt(c.openalex_works)}</td><td class="r">${fmt(c.nordic_archive_records)}</td><td class="r"><strong>${fmt(c.pdfs)}</strong></td><td class="r">${((c.oa_share || 0) * 100).toFixed(0)} %</td></tr>`).join("")}</tbody>
            </table>
          </div>
        </div>
        ${cls.length ? `<div class="ana-sec">
          <h3>Klynger</h3>
          <div class="table-wrap">
            <table class="tbl-clean">
              <thead><tr><th>Klynge</th><th class="r">Verk</th><th class="r">PDF</th></tr></thead>
              <tbody>${cls.map((c) => `<tr><td><strong>${esc(c.name)}</strong></td><td class="r">${fmt(c.n)}</td><td class="r">${fmt(c.pdfs)}</td></tr>`).join("")}</tbody>
            </table>
          </div>
        </div>` : ""}
        <div class="ana-sec">
          <h3>Tidsskrift og konferansar</h3>
          <div class="table-wrap">
            <table class="tbl-clean">
              <thead><tr><th>Kanal</th><th class="r">Verk</th><th class="r">PDF</th><th class="r">Sitat</th></tr></thead>
              <tbody>${vens.map((v) => `<tr><td><strong>${esc(v.venue)}</strong></td><td class="r">${fmt(v.auto_included)}</td><td class="r">${fmt(v.pdfs)}</td><td class="r">${fmt(v.citations)}</td></tr>`).join("")}</tbody>
            </table>
          </div>
        </div>
      </div>`;
  }

  /* ---------- hendingar ---------- */
  function readFilterUi() {
    const a = parseInt($("yrFrom").value, 10) || 0, b = parseInt($("yrTo").value, 10) || 0;
    return { yr: a || b ? [a, b] : null, kind: $("kindSel").value, lang: $("langSel").value, cc: $("ccSel").value, tilg: $("tilgSel").value, dup: !$("dupChk").checked };
  }

  function bind() {
    document.querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", (e) => {
      e.preventDefault();
      if (b.classList.contains("brand")) { S.st = U.emptyState(); S.expandedId = null; S.shown = STEP; showTab("korpus", true); applyStateToUi(); writeHash(true); runSearch(); window.scrollTo(0, 0); return; }
      setTab(b.dataset.tab);
    }));

    const hdr = document.querySelector("header");
    const stick = () => hdr.classList.toggle("stuck", window.scrollY > 2);
    window.addEventListener("scroll", stick, { passive: true });
    stick();

    $("metricAllBtn").addEventListener("click", () => go({ tilg: "" }, { scroll: false }));
    $("metricPdfBtn").addEventListener("click", () => go({ tilg: S.st.tilg === "open" ? "" : "open" }));

    let tmr = null, hashTmr = null;
    const qi = $("qInput");
    qi.addEventListener("focus", () => { startT1(false); silentModel(); });
    qi.addEventListener("input", () => {
      startT1(true);
      S.st.q = qi.value; S.st.sim = ""; S.st.work = ""; S.st.list = null; S.expandedId = null; S.shown = STEP;
      clearTimeout(tmr); clearTimeout(hashTmr);
      tmr = setTimeout(() => { applySortDefault(); runSearch(); }, 120);
      hashTmr = setTimeout(() => writeHash(false), 400);
    });
    qi.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { qi.blur(); clearTimeout(tmr); applySortDefault(); runSearch(); writeHash(false); }
    });

    $("resetBtn").addEventListener("click", () => {
      S.st = U.emptyState();
      S.expandedId = null;
      applyStateToUi(); writeHash(true); runSearch();
    });

    for (const id of ["yrFrom", "yrTo", "kindSel", "langSel", "ccSel", "tilgSel", "dupChk"]) {
      $(id).addEventListener("change", () => go(readFilterUi(), { scroll: true }));
    }
    $("sortSel").addEventListener("change", () => go({ sort: $("sortSel").value }, { scroll: false }));
    $("filterToggle").addEventListener("click", () => { S.filterOpen = !S.filterOpen; renderFilterUi(); });
    $("modelBtn").addEventListener("click", () => { S.modelPanelOpen = !S.modelPanelOpen; renderModelUi(); });
    $("startHideBtn").addEventListener("click", () => { S.startOpen = false; store.set(LS.start, "skjult"); renderStart(); });
    $("startOpenBtn").addEventListener("click", () => { S.startOpen = true; store.set(LS.start, "open"); renderStart(); });
    $("moreCorpusBtn").addEventListener("click", () => { S.shown += STEP; renderList(); if (S.result && S.result.hasQuery) loadTeasers(); });
    $("copyLinkBtn").addEventListener("click", async () => { writeHash(false); toast((await copyText(location.href)) ? "Lenkja er kopiert." : "Kunne ikkje kopiere lenkja."); });
    $("exportBtn").addEventListener("click", () => { const m = $("exportMenu"); m.hidden = !m.hidden; $("exportBtn").setAttribute("aria-expanded", String(!m.hidden)); renderExportMenu(); });
    $("listBtn").addEventListener("click", () => {
      const p = $("readingPanel"); p.hidden = !p.hidden;
      $("listBtn").setAttribute("aria-expanded", String(!p.hidden));
      renderReading();
      if (!p.hidden) p.scrollIntoView({ block: "nearest" });
    });

    document.querySelectorAll(".sub-pill").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll(".sub-pill").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      S.citSub = b.dataset.sub;
      renderCitations();
    }));
    $("citQ").addEventListener("input", renderCitations);

    document.body.addEventListener("click", onBodyClick);
  }

  function applySortDefault() {
    /* ny spørjing: standard er relevans; utan spørjing: mest siterte */
    if (!S.st.q.trim() && (S.st.sort === "rel" || S.st.sort === "first")) S.st.sort = "";
  }

  function onBodyClick(e) {
    const t = e.target;
    const el = (sel) => t.closest(sel);
    let b;
    if ((b = el("[data-model]"))) {
      e.preventDefault();
      if (b.dataset.model === "open") { S.modelPanelOpen = true; renderModelUi(); $("modelPanel").scrollIntoView({ block: "center" }); return; }
      onModelAction(b.dataset.model); return;
    }
    if ((b = el("[data-clear]"))) {
      const k = b.dataset.clear;
      const patch = k === "yr" ? { yr: null } : k === "dup" ? { dup: false } : { [k]: "" };
      if (k === "sim") { simBack(); return; }
      go(patch, { scroll: false }); return;
    }
    if ((b = el("[data-simback]"))) { simBack(); return; }
    if ((b = el("[data-sim]"))) { e.preventDefault(); go({ sim: b.dataset.sim }); return; }
    if ((b = el("[data-q]"))) {
      e.preventDefault();
      if (S.metaOK) startT1(true);
      go({ q: b.dataset.q, sort: "" }); return;
    }
    if ((b = el("[data-gloss]"))) { e.preventDefault(); location.hash = "#ordliste"; return; }
    if ((b = el(".gl-search"))) { go({ q: b.dataset.q }); return; }
    if ((b = el("[data-jump]"))) { e.preventDefault(); openWork(b.dataset.jump); return; }
    if ((b = el("[data-au]"))) { e.preventDefault(); go(b.closest("#peoplePanel") ? { au: b.dataset.au } : Object.assign(U.emptyState(), { au: b.dataset.au })); return; }
    if ((b = el("[data-inst]"))) { e.preventDefault(); go(b.closest("#peoplePanel") ? { inst: b.dataset.inst } : Object.assign(U.emptyState(), { inst: b.dataset.inst })); return; }
    if ((b = el("[data-people]"))) {
      if (b.dataset.people === "toggle") { S.peopleAll = !S.peopleAll; renderPeople(); }
      else { ensureContext().then(() => renderPeople()); }
      return;
    }
    if ((b = el("[data-toggle]"))) {
      const id = b.dataset.toggle;
      S.expandedId = S.expandedId === id ? null : id;
      refreshAllRows(); return;
    }
    if ((b = el("[data-abs]"))) {
      const id = b.dataset.abs;
      if (S.openAbs.has(id)) S.openAbs.delete(id); else S.openAbs.add(id);
      if (S.expandedId === id) S.expandedId = null;
      refreshRow(id);
      return;
    }
    if ((b = el("[data-rl]"))) { toggleReading(b.dataset.rl); return; }
    if ((b = el("[data-copyref]"))) { const i = S.pos.get(b.dataset.copyref); copyText(Exp.reference(exportItems([i])[0])).then((ok) => toast(ok ? "Referansen er kopiert." : "Kunne ikkje kopiere.")); return; }
    if ((b = el("[data-copylink]"))) { copyText(location.origin + location.pathname + "#verk/" + encodeURIComponent(b.dataset.copylink)).then((ok) => toast(ok ? "Lenkja er kopiert." : "Kunne ikkje kopiere.")); return; }
    if ((b = el("[data-export]"))) {
      const which = b.dataset.which;
      let pos;
      if (which === "leseliste") pos = (S.st.list || S.reading).map((id) => S.pos.get(id)).filter((p) => p !== undefined);
      else pos = (S.result.pinned != null ? [S.result.pinned] : []).concat(S.result.list);
      download(b.dataset.export, which, pos); return;
    }
    if ((b = el("[data-rlrefs]"))) {
      const pos = (S.st.list || S.reading).map((id) => S.pos.get(id)).filter((p) => p !== undefined);
      copyText(exportItems(pos).map((it) => Exp.reference(it)).join("\n")).then((ok) => toast(ok ? "Referansane er kopierte." : "Kunne ikkje kopiere.")); return;
    }
    if ((b = el("[data-rlshare]"))) {
      if (!S.reading.length) return;
      copyText(shareUrl(S.reading)).then((ok) => toast(ok ? (S.reading.length > 60 ? "Lenkja er kopiert. Ho tek med dei 60 første verka." : "Lenkja er kopiert.") : "Kunne ikkje kopiere."));
      return;
    }
    if ((b = el("[data-rlclear]"))) { if (S.reading.length && window.confirm("Tøm leselista?")) { S.reading = []; saveReading(); refreshAllRows(); renderReading(); $("listBtn").textContent = "Leseliste (0)"; } return; }
    if ((b = el("[data-rlsave]"))) {
      let added = 0;
      for (const id of S.st.list || []) if (S.pos.has(id) && !S.reading.includes(id) && S.reading.length < 500) { S.reading.push(id); added++; }
      saveReading(); toast(`${added} verk lagra i leselista di.`); S.st.list = null; writeHash(true); renderReading(); renderAll(); return;
    }
    if ((b = el("a[data-tab]"))) { e.preventDefault(); setTab(b.dataset.tab); return; }
  }

  function simBack() {
    const h = U.buildHash(Object.assign({}, S.st, { sim: "" }));
    S.st.sim = "";
    S.shown = STEP;
    S.lastHash = h; location.hash = h;
    applyStateToUi(); runSearch(); scrollToList();
  }

  function openWork(id) {
    if (!S.pos.has(id)) return;
    S.st = Object.assign(U.emptyState(), { work: id });
    S.expandedId = id;
    showTab("korpus", true);
    applyStateToUi();
    const h = U.buildHash(S.st);
    S.lastHash = h; location.hash = h;
    runSearch();
    window.scrollTo(0, 0);
  }

  function refreshAllRows() {
    document.querySelectorAll("#corpusList article.item").forEach((a) => refreshRow(a.dataset.id));
  }

  init();
})();
