"""Headless Dexmoon card renderer - the SAME index.html the client edits in the browser, driven by Playwright (one source of truth).
    python render.py --token "Pepe Coin" --ticker PEPE --chain Solana --handle pepe --refcode MOON10 [--hero img.png] [--avatar a.png] [--headline "DEX PAID"] [--updated "..."] [--preset p.json] -o out.png
    from render import CardRenderer; r = CardRenderer(); png_bytes = r.render({...}); r.close()
"""
import argparse, base64, json, mimetypes, pathlib
from playwright.sync_api import sync_playwright
PAGE = (pathlib.Path(__file__).parent / "index.html").resolve().as_uri()

def data_url(path):
    if not path: return None
    b = pathlib.Path(path).read_bytes(); mt = mimetypes.guess_type(str(path))[0] or "image/png"
    return "data:%s;base64,%s" % (mt, base64.b64encode(b).decode())

class CardRenderer:
    def __init__(self):
        self._p = sync_playwright().start(); self._b = self._p.chromium.launch(); self._pg = self._b.new_page()
        self._pg.goto(PAGE); self._pg.wait_for_function("window.dexReady===true", timeout=20000)
    def render(self, fields):
        url = self._pg.evaluate("o => window.dexCard(o)", fields)
        return base64.b64decode(url.split(",", 1)[1])
    def close(self): self._b.close(); self._p.stop()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for k in ("theme", "scale", "token", "headline", "ticker", "chain", "updated", "handle", "refcode", "site", "promo", "hero", "avatar", "preset"): ap.add_argument("--" + k)
    ap.add_argument("-o", "--out", default="card.png"); a = vars(ap.parse_args())
    f = {k: v for k, v in a.items() if v is not None and k not in ("out", "hero", "avatar", "preset")}
    if "scale" in f: f["scale"] = int(f["scale"])
    if a["hero"]: f["hero"] = data_url(a["hero"])
    if a["avatar"]: f["avatar"] = data_url(a["avatar"])
    if a["preset"]: f["preset"] = json.load(open(a["preset"], encoding="utf-8"))
    r = CardRenderer(); pathlib.Path(a["out"]).write_bytes(r.render(f)); r.close(); print(a["out"])
