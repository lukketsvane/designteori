// Liten statisk server for docs/ (node, ingen avhengigheiter). Ikkje ein test: filnamnet sluttar ikkje på .test.mjs.
// Bruk: node tests/js/serve.mjs [--port 8765] [--search-dir <mappe>]
// --search-dir byter ut /data/search/ med ei anna mappe (t.d. fixturar), elles vert docs/data/search/ brukt.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const docs = path.resolve(here, "..", "..", "docs");
const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : def; };
const port = +opt("--port", "8765");
const searchDir = opt("--search-dir", "");

const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".csv": "text/csv; charset=utf-8",
  ".bin": "application/octet-stream", ".i8": "application/octet-stream", ".pdf": "application/pdf", ".svg": "image/svg+xml",
  ".png": "image/png", ".ico": "image/x-icon",
};

const server = http.createServer((req, res) => {
  let p;
  try { p = decodeURIComponent(new URL(req.url, "http://x").pathname); } catch { res.writeHead(400); res.end("bad"); return; }
  let file;
  if (searchDir && p.startsWith("/data/search/")) file = path.join(path.resolve(searchDir), p.slice("/data/search/".length));
  else file = path.join(docs, p);
  const root = searchDir && p.startsWith("/data/search/") ? path.resolve(searchDir) : docs;
  if (!path.resolve(file).startsWith(root)) { res.writeHead(403); res.end("forbidden"); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, "index.html");
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404, { "Content-Type": "text/plain" }); res.end("404"); return; }
    res.writeHead(200, { "Content-Type": MIME[path.extname(file).toLowerCase()] || "application/octet-stream", "Cache-Control": "no-store" });
    res.end(buf);
  });
});
server.listen(port, "127.0.0.1", () => console.log(`docs/ på http://127.0.0.1:${port}/` + (searchDir ? ` (search: ${searchDir})` : "")));
