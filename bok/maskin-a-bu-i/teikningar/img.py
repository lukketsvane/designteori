import argparse, base64, json, mimetypes, os, sys, urllib.error, urllib.request


def sd(pages):
    return [f"sd_p{n}.png" for n in pages.split()]


MODES = {
    "standard": {
        "params": {"model": "gpt-image-2.6-sunburst", "quality": "high"},
        "prompt": "{prompt}",
        "check": [
            "motiv, komposisjon og stil svarar til bestillinga",
            "all tekst er rett stava og leseleg, ingen ekstra tekst, logoar eller vassmerke",
            "ved redigering: berre det etterspurde er endra, referansedetaljar er intakte",
            "ved transparent bakgrunn: fila har faktisk gjennomsiktige pikslar",
        ],
    },
    "speculative-drawing": {
        "params": {"model": "gpt-image-2.6-sunburst", "quality": "max", "complexity": "high",
                   "size": "1440x2032", "background": "opaque"},
        "prompt": "du skal illustrere vedlagt tekst. heile saken del for del. gjer det eksakt i denne stilen "
                  "med topfer speculative drawing. ei side etter den andre til me har dekt det tekstlege innhaldet."
                  "\n\n{prompt}\n\n"
                  "Dei vedlagde bileta er berre stilreferansar: svart tusjstrek på kvit side, handskrivne "
                  "merknader, luftig oppsett. Ikkje kopier motiv, figurar, tekst, namn eller sidetal frå dei. "
                  "Lag éi ståande side. Tekst i biletet: berre det som står i hermeteikn over, ordrett.",
        "refs": {
            "middels": sd("206 153 067 066 269 043"),
            "lite": sd("206 207 153 269 043 067"),
            "mykje": sd("066 067 269 043 014 268"),
        },
        "check": [
            "sida dekkjer akkurat den tekstdelen ho skal, med motiv henta frå teksten",
            "svart strek på kvit side, handskrivne merknader, ingen gråtonar eller fargar",
            "ingenting er kopiert frå referansane: motiv, engelsk tekst, namn, sidetal",
            "all tekst står ordrett som bestilt (æ, ø, å), og ingen annan tekst",
            "éi ståande side, ingenting avkutta",
        ],
    },
}
USD_PER_M = {"text": 5, "image": 8, "out": 30}

p = argparse.ArgumentParser()
p.add_argument("prompt")
p.add_argument("-o", "--out", default="out.png")
p.add_argument("-m", "--mode", default="standard", choices=MODES)
p.add_argument("-r", "--refs")
p.add_argument("-i", "--image", action="append", default=[])
p.add_argument("--mask")
p.add_argument("--markup")
p.add_argument("-p", "--param", action="append", default=[], metavar="KEY=VALUE")
a = p.parse_args()

key = os.environ.get("OPENAI_API_KEY")
base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
headers = {"Content-Type": "application/json"}
if key:
    headers["Authorization"] = f"Bearer {key}"
mode = MODES[a.mode]
stem, ext = os.path.splitext(a.out)
ext = ext.lstrip(".").lower()


def api(path, data=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, data, headers), timeout=540) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {e.headers.get('x-request-id', '')}: {e.read().decode(errors='replace')}")


def ref(x):
    if x.startswith(("http://", "https://", "data:")):
        return x
    mime = mimetypes.guess_type(x)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(x, "rb").read()).decode()


def value(v):
    try:
        return json.loads(v)
    except ValueError:
        return v


body = {**mode["params"], **{k: value(v) for k, v in (x.split("=", 1) for x in a.param)}}
body["prompt"] = mode["prompt"].replace("{prompt}", a.prompt)
body["output_format"] = {"jpg": "jpeg"}.get(ext, ext)
images = list(body.get("images", []))
if "refs" in mode:
    names = mode["refs"][a.refs or next(iter(mode["refs"]))]
    ids = {f["filename"]: f["id"] for f in api("/files?purpose=vision")["data"]}
    missing = [n for n in names if n not in ids]
    if missing:
        sys.exit("manglar i OpenAI Files: " + " ".join(missing))
    images += [{"file_id": ids[n]} for n in names]
images += [{"image_url": ref(x)} for x in a.image]
if images:
    body["images"] = images
for k in ("mask", "markup"):
    if getattr(a, k):
        body[k] = {"image_url": ref(getattr(a, k))}

res = api("/images/edits" if images else "/images/generations", json.dumps(body).encode())

for i, d in enumerate(res["data"]):
    path = a.out if len(res["data"]) == 1 else f"{stem}-{i + 1}.{ext}"
    with open(path, "wb") as f:
        f.write(base64.b64decode(d["b64_json"]))
    print(path)

u = res.get("usage") or {}
t = u.get("input_tokens_details") or {}
usd = (t.get("text_tokens", 0) * USD_PER_M["text"] + t.get("image_tokens", 0) * USD_PER_M["image"]
       + u.get("output_tokens", 0) * USD_PER_M["out"]) / 1e6
print(f"{body['model']} mode={a.mode} tokens={u.get('total_tokens')} ~${usd:.3f}")
for c in mode["check"]:
    print("check:", c)
