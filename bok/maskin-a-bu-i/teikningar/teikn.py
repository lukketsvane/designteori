#!/usr/bin/env python3
"""Lagar teikningane til «MASKINA Å BU I» side for side (speculative drawing, kvadratisk 1:1).

Bruk:   python teikn.py 1            (berre side 1)
        python teikn.py 2-46 -j 4    (side 2 til 46, fire om gongen)
Sider som alt finst (side-NN.png), vert hoppa over. Logg og kostnad: logg.txt.
Krev OPENAI_API_KEY i miljøet (eller som brukarvariabel på Windows).
"""
import argparse
import os
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sider import SIDER

HER = Path(__file__).resolve().parent
STORLEIK = "1920x1920"          # 1:1, største storleik utan eksperimentell modus
LÅS = threading.Lock()


def prompt(k: int, n: int, s: dict) -> str:
    linjer = [f"Side {k} av {n}. Illustrer berre denne teksten:", f"«{s['tekst']}»",
              "Teksten i «» er berre til lesing; han skal ikkje skrivast i biletet.", "",
              "Teikningar, ovanfrå og ned:"]
    linjer += [f"{i}. {t}" for i, t in enumerate(s["teikningar"], 1)]
    linjer += ["", "Handskrivne merknader, ordrett, i store bokstavar:"]
    linjer += [f"\"{m}\"" for m in s["merknader"]]
    if s.get("tittel"):
        linjer += ["", f"Handskriven sidetittel øvst til venstre: \"{s['tittel']}\""]
    linjer += ["", "Format: sida er kvadratisk (1:1), ikkje ståande. Bruk heile den kvadratiske flata, "
               "luftig men utan store tomme parti. Inga sidetal."]
    return "\n".join(linjer)


def lag(k: int, n: int, s: dict) -> str:
    ut = HER / f"side-{k:02d}.png"
    if ut.exists():
        return f"side {k}: finst alt"
    env = dict(os.environ)
    if not env.get("OPENAI_API_KEY") and sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as nøkkel:
            env["OPENAI_API_KEY"] = winreg.QueryValueEx(nøkkel, "OPENAI_API_KEY")[0]
    r = subprocess.run(
        [sys.executable, str(HER / "img.py"), prompt(k, n, s), "-o", str(ut), "-m", "speculative-drawing",
         "-r", s.get("ref", "middels"), "-p", f"size={STORLEIK}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    kost = re.search(r"~\$([\d.]+)", r.stdout)
    melding = (f"side {k}: {'ok' if ut.exists() else 'FEIL'}"
               f"{' ~$' + kost.group(1) if kost else ''} {r.stderr.strip()[-400:] if not ut.exists() else ''}")
    with LÅS:
        with open(HER / "logg.txt", "a", encoding="utf-8") as f:
            f.write(melding + "\n")
        print(melding, flush=True)
    return melding


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sider", help="t.d. 1 eller 2-46")
    p.add_argument("-j", type=int, default=1)
    a = p.parse_args()
    fra, _, til = a.sider.partition("-")
    nr = range(int(fra), int(til or fra) + 1)
    n = len(SIDER)
    with ThreadPoolExecutor(a.j) as ex:
        list(ex.map(lambda k: lag(k, n, SIDER[k - 1]), nr))


if __name__ == "__main__":
    main()
