/* Språkmodell i nettlesaren (valfri). Lastar @huggingface/transformers med dynamisk import() og koder spørjinga lokalt.
   Spørjinga forlèt aldri nettlesaren; berre modellfilene vert henta (jsDelivr og huggingface.co).
   Klassisk skript (UMD-hale): window.DTEmbed i nettlesaren, module.exports i node. */
(function () {
  "use strict";

  const DIM = 256;
  const MAX_TOKENS = 128;
  const ALLOWED_LIB_HOSTS = ["cdn.jsdelivr.net"];

  /* Same nøkkel som i query_vectors.json (4.9): trim, ein mellomrom, toLowerCase. */
  function normalizeKey(q) { return String(q == null ? "" : q).trim().replace(/\s+/g, " ").toLowerCase(); }
  function queryPrompt(key) { return "task: search result | query: " + key; }

  /* Matryoshka: dei 256 første dimensjonane, så L2-normalisering. Ingen anna pooling. */
  function postprocess(data) {
    const out = new Float32Array(DIM);
    let s = 0;
    for (let i = 0; i < DIM; i++) { const v = data[i] || 0; out[i] = v; s += v * v; }
    s = Math.sqrt(s) || 1;
    for (let i = 0; i < DIM; i++) out[i] /= s;
    return out;
  }

  function cosine(a, b) {
    let d = 0, na = 0, nb = 0;
    for (let i = 0; i < a.length; i++) { d += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
    return d / (Math.sqrt(na) * Math.sqrt(nb) || 1);
  }

  function libraryAllowed(url) {
    try { const u = new URL(url); return u.protocol === "https:" && ALLOWED_LIB_HOSTS.indexOf(u.host) >= 0; } catch (e) { return false; }
  }

  /* opts: {cfg: meta.browser_model, onState(state, info), onProgress(frac, loaded, total), importer(url) (for testar)} */
  function create(opts) {
    const cfg = opts.cfg || {};
    const importer = opts.importer || ((u) => import(/* webpackIgnore: true */ u));
    let state = "av", lib = null, tokenizer = null, model = null, run = 0, chain = Promise.resolve();
    const files = new Map();

    const set = (s, info) => { state = s; if (opts.onState) opts.onState(s, info || null); };

    function total() {
      let l = 0, t = 0;
      for (const f of files.values()) { l += f.loaded || 0; t += f.total || 0; }
      return { loaded: l, total: t };
    }
    function onProgress(ev) {
      if (!ev || !ev.file) return;
      if (ev.status === "progress" && typeof ev.total === "number") files.set(ev.file, { loaded: ev.loaded || 0, total: ev.total });
      if (ev.status === "done" && files.has(ev.file)) { const f = files.get(ev.file); f.loaded = f.total; }
      if (opts.onProgress) {
        const t = total();
        const expected = Object.keys(cfg.download_files || {}).filter((k) => k.indexOf("huggingface.co") === 0).reduce((a, k) => a + cfg.download_files[k], 0);
        const denom = Math.max(t.total, expected, 1);
        opts.onProgress(Math.min(1, t.loaded / denom), t.loaded, t.total);
      }
    }

    async function load() {
      if (!libraryAllowed(cfg.library_url)) throw new Error("Biblioteksadressa er ikkje tillaten");
      if (typeof WebAssembly === "undefined" && !opts.importer) throw new Error("WebAssembly manglar");
      lib = await importer(cfg.library_url);
      const T = lib.AutoTokenizer, M = lib.AutoModel;
      if (!T || !M) throw new Error("Biblioteket manglar AutoTokenizer eller AutoModel");
      tokenizer = await T.from_pretrained(cfg.model_id, { progress_callback: onProgress });
      model = await M.from_pretrained(cfg.model_id, { dtype: cfg.dtype || "q8", progress_callback: onProgress });
    }

    async function enable() {
      if (state === "lastar" || state === "klar") return state === "klar";
      const my = ++run;
      files.clear();
      set("lastar");
      try {
        await load();
        if (my !== run) return false; // avbrote
        set("klar");
        return true;
      } catch (e) {
        if (my !== run) return false;
        tokenizer = null; model = null;
        set("feil", e && e.message ? e.message : String(e));
        return false;
      }
    }

    function cancel() {
      run++;
      tokenizer = null; model = null;
      set("av");
    }

    /* Er alle modellfilene alt i nettlesarens cache? (ingen nedlasting) */
    async function cached() {
      try {
        if (typeof caches === "undefined") return false;
        const names = Object.keys(cfg.download_files || {});
        const c = await caches.open("transformers-cache");
        const keys = await c.keys();
        const urls = keys.map((k) => k.url);
        const main = names.filter((n) => /model_quantized\.onnx(_data)?$/.test(n)).map((n) => n.split("/").pop());
        if (!main.length) return false;
        return main.every((n) => urls.some((u) => u.indexOf(cfg.model_id) >= 0 && u.slice(-n.length) === n));
      } catch (e) { return false; }
    }

    /* Stille lasting frå cache. Gir false (og rører ikkje tilstanden) om cachen manglar. */
    async function silent() {
      if (!(await cached())) return false;
      return enable();
    }

    function encode(q) {
      const key = normalizeKey(q);
      const my = run;
      const job = chain.then(async () => {
        if (state !== "klar" || !tokenizer || !model) throw new Error("Modellen er ikkje klar");
        const inputs = tokenizer([queryPrompt(key)], { padding: true, truncation: true, max_length: MAX_TOKENS });
        const out = await model(inputs);
        const emb = out.sentence_embedding || out.embeddings;
        if (!emb || !emb.data) throw new Error("Modellen gav ikkje sentence_embedding");
        return postprocess(emb.data);
      });
      chain = job.catch(() => {});
      return job.then((v) => { if (my !== run) throw new Error("avbrote"); return v; });
    }

    return { enable, cancel, silent, cached, encode, get state() { return state; }, get error() { return null; } };
  }

  const API = { DIM, MAX_TOKENS, normalizeKey, queryPrompt, postprocess, cosine, libraryAllowed, create };
  if (typeof module === "object" && module.exports) { module.exports = API; } else { window.DTEmbed = API; }
})();
