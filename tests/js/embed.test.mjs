import test from "node:test";
import assert from "node:assert/strict";
import { Emb, Search } from "./helpers.mjs";

const CFG = {
  library_url: "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1/dist/transformers.min.js",
  model_id: "onnx-community/embeddinggemma-300m-ONNX", dtype: "q8",
  download_files: { "huggingface.co/onnx/model_quantized.onnx_data": 308890624, "huggingface.co/tokenizer.json": 20323312 },
};

function mockLib(log, opts = {}) {
  return {
    AutoTokenizer: { from_pretrained: async (id, o) => { log.push(["tok", id]); o.progress_callback && o.progress_callback({ status: "progress", file: "tokenizer.json", loaded: 5, total: 10 }); return (texts, topt) => { log.push(["tokenize", texts, topt]); return { texts }; }; } },
    AutoModel: {
      from_pretrained: async (id, o) => {
        log.push(["model", id, o.dtype]);
        if (opts.delay) await new Promise((r) => setTimeout(r, opts.delay));
        return async (inputs) => {
          log.push(["run", inputs.texts[0]]);
          const v = new Float32Array(768);
          for (let i = 0; i < 768; i++) v[i] = i < 256 ? (i % 7) - 3 : 100; // dimensjonar over 256 skal kuttast
          return { sentence_embedding: { data: v, dims: [1, 768] } };
        };
      },
    },
  };
}

test("R11: ingenting vert lasta før enable()", () => {
  let imported = 0;
  Emb.create({ cfg: CFG, importer: async () => { imported++; return mockLib([]); } });
  assert.equal(imported, 0);
});

test("modell: AutoTokenizer + AutoModel med dtype q8, ingen pipeline, tilstandar av -> lastar -> klar", async () => {
  const log = [], states = [], urls = [];
  const m = Emb.create({ cfg: CFG, onState: (s) => states.push(s), importer: async (u) => { urls.push(u); return mockLib(log); } });
  assert.equal(m.state, "av");
  assert.equal(await m.enable(), true);
  assert.deepEqual(states, ["lastar", "klar"]);
  assert.deepEqual(urls, [CFG.library_url]);
  assert.deepEqual(log.filter((e) => e[0] === "model"), [["model", "onnx-community/embeddinggemma-300m-ONNX", "q8"]]);
});

test("koding: prompt, trunkering til 128 token, 256 dimensjonar, L2-normalisert, same nøkkel som query_vectors", async () => {
  const log = [];
  const m = Emb.create({ cfg: CFG, importer: async () => mockLib(log) });
  await m.enable();
  const v = await m.encode("  Service   DESIGN  ");
  assert.equal(log.find((e) => e[0] === "run")[1], "task: search result | query: service design");
  assert.deepEqual(log.find((e) => e[0] === "tokenize")[2], { padding: true, truncation: true, max_length: 128 });
  assert.ok(v instanceof Float32Array);
  assert.equal(v.length, 256);
  let n = 0;
  for (const x of v) n += x * x;
  assert.ok(Math.abs(Math.sqrt(n) - 1) < 1e-5);
  // første 256 dimensjonar, ikkje resten (100-verdiane skal ikkje påverke)
  const raw = Float32Array.from({ length: 256 }, (_, i) => (i % 7) - 3);
  assert.ok(Emb.cosine(v, raw) > 0.99999);
  assert.equal(Emb.normalizeKey("  Service   DESIGN  "), Search.normalizeKey("  Service   DESIGN  "));
  assert.equal(Emb.queryPrompt("a b"), "task: search result | query: a b");
});

test("postprocess: kutt til 256 og normaliser", () => {
  const raw = new Float32Array(768).fill(2);
  const v = Emb.postprocess(raw);
  assert.equal(v.length, 256);
  assert.ok(Math.abs(v[0] - 1 / 16) < 1e-6);
});

test("feil: nettverk, bibliotek og ikkje tillaten adresse gir tilstand feil utan å stoppe søket", async () => {
  const states = [];
  const bad = Emb.create({ cfg: CFG, onState: (s, info) => states.push([s, info]), importer: async () => { throw new Error("nett"); } });
  assert.equal(await bad.enable(), false);
  assert.equal(bad.state, "feil");
  assert.equal(states.at(-1)[1], "nett");
  await assert.rejects(() => bad.encode("x"));
  let called = 0;
  const wrongHost = Emb.create({ cfg: Object.assign({}, CFG, { library_url: "https://evil.example/x.js" }), importer: async () => { called++; return mockLib([]); } });
  assert.equal(await wrongHost.enable(), false);
  assert.equal(called, 0);
  assert.ok(Emb.libraryAllowed(CFG.library_url));
  assert.ok(!Emb.libraryAllowed("http://cdn.jsdelivr.net/x.js"));
  assert.ok(!Emb.libraryAllowed("https://huggingface.co/x.js"));
  const noApi = Emb.create({ cfg: CFG, importer: async () => ({}) });
  assert.equal(await noApi.enable(), false);
});

test("avbryt: tilstand tilbake til av og resultatet vert forkasta", async () => {
  const states = [];
  const m = Emb.create({ cfg: CFG, onState: (s) => states.push(s), importer: async () => mockLib([], { delay: 40 }) });
  const p = m.enable();
  m.cancel();
  assert.equal(await p, false);
  assert.equal(m.state, "av");
  assert.ok(!states.includes("klar"));
});

test("framdrift: samla del frå progress_callback", async () => {
  const fr = [];
  const m = Emb.create({ cfg: CFG, onProgress: (f) => fr.push(f), importer: async () => mockLib([]) });
  await m.enable();
  assert.ok(fr.length >= 1);
  assert.ok(fr.every((f) => f >= 0 && f <= 1));
});

test("koding: éi om gongen i rekkjefølgje", async () => {
  const log = [];
  const m = Emb.create({ cfg: CFG, importer: async () => mockLib(log) });
  await m.enable();
  await Promise.all([m.encode("a"), m.encode("b"), m.encode("c")]);
  assert.deepEqual(log.filter((e) => e[0] === "run").map((e) => e[1].slice(-1)), ["a", "b", "c"]);
  const off = Emb.create({ cfg: CFG, importer: async () => mockLib([]) });
  await assert.rejects(() => off.encode("x"), /ikkje klar/);
});
