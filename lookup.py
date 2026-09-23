"""Fill card fields from a Dexscreener or CoinMarketCap link (server side: no CORS limits, so CMC works here too).
    python lookup.py https://dexscreener.com/solana/<pair-or-token>     |   https://coinmarketcap.com/currencies/<slug>/
Returns {token, ticker, chain, handle, logo_url}. Used by bot.py (a "Link:" line or just pasting the link)."""
import json, re, sys, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) dexmoon-card/1.0", "Accept": "application/json"}
CHAINS = {"solana": "Solana", "ethereum": "Ethereum", "base": "Base", "bsc": "BNB Chain", "arbitrum": "Arbitrum", "polygon": "Polygon",
          "avalanche": "Avalanche", "optimism": "Optimism", "sui": "Sui", "ton": "TON", "tron": "Tron", "blast": "Blast",
          "hyperliquid": "Hyperliquid", "hyperevm": "HyperEVM", "abstract": "Abstract", "sonic": "Sonic", "berachain": "Berachain",
          "linea": "Linea", "zksync": "zkSync", "mantle": "Mantle", "aptos": "Aptos", "near": "NEAR", "pulsechain": "PulseChain", "cronos": "Cronos"}

def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r: return json.load(r)

def _handle(socials):
    for s in socials or []:
        u = s.get("url", "") if isinstance(s, dict) else str(s)
        t = (s.get("type", "") if isinstance(s, dict) else "")
        m = re.search(r"(?:twitter\.com|x\.com)/(?:#!/)?@?([A-Za-z0-9_]{1,15})(?:[/?#]|$)", u)
        if m and m.group(1).lower() not in ("i", "home", "search", "intent", "share"): return m.group(1)
        if t == "twitter" and u and not u.startswith("http"): return u.lstrip("@")
    return None

def _from_pair(p):
    info = p.get("info") or {}
    return {"token": p["baseToken"]["name"], "ticker": p["baseToken"]["symbol"],
            "chain": CHAINS.get(p["chainId"], p["chainId"].title()), "handle": _handle(info.get("socials")),
            "logo_url": info.get("imageUrl"), "source": p.get("url")}

def _best(pairs):
    pairs = [p for p in pairs or [] if p.get("baseToken")]
    return max(pairs, key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0)) if pairs else None

def from_dexscreener(url):
    m = re.search(r"dexscreener\.com/([a-z0-9]+)/([A-Za-z0-9]+)", url)
    if not m: raise ValueError("not a dexscreener pair/token link")
    chain, addr = m.group(1), m.group(2)
    d = _get("https://api.dexscreener.com/latest/dex/pairs/%s/%s" % (chain, addr))
    p = d.get("pair") or _best(d.get("pairs"))
    if not p:                                      # link was a token address, not a pair
        p = _best(_get("https://api.dexscreener.com/latest/dex/tokens/%s" % addr).get("pairs"))
    if not p: raise ValueError("dexscreener has no pair for that link")
    return _from_pair(p)

def from_cmc(url):
    m = re.search(r"coinmarketcap\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?(?:currencies|dexscan/[a-z0-9-]+)/([A-Za-z0-9-]+)", url)
    if not m: raise ValueError("not a coinmarketcap coin link")
    slug = m.group(1)
    if "/dexscan/" in url:                          # CMC DexScan pages carry the pair/token address -> ask dexscreener
        return from_dexscreener("https://dexscreener.com/%s/%s" % (re.search(r"dexscan/([a-z0-9-]+)/", url).group(1), slug))
    d = _get("https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail?slug=%s" % slug)["data"]
    tw = d.get("urls", {}).get("twitter") or []
    plats = d.get("platforms") or []
    # CMC lists every chain a token is bridged to, in no useful order (Based Brett: BNB first, Base second).
    # The real home chain = the contract with the most DEX liquidity, so ask Dexscreener about each one.
    best, best_liq = None, -1
    for p in plats[:8]:
        addr = p.get("contractAddress")
        if not addr: continue
        try: pair = _best(_get("https://api.dexscreener.com/latest/dex/tokens/%s" % addr).get("pairs"))
        except Exception: pair = None
        liq = ((pair or {}).get("liquidity") or {}).get("usd") or 0
        if pair and liq > best_liq: best, best_liq = pair, liq
    if best:
        chain = CHAINS.get(best["chainId"], best["chainId"].title())
    else:
        chain = _pretty(plats[0].get("contractPlatform")) if plats else (d.get("name") if d.get("category") == "coin" else None)
    name = best["baseToken"]["name"] if best else re.sub(r"\s*\([^)]*\)\s*$", "", d["name"])   # "Brett (Based)" is CMC's label; the coin is "Brett"
    return {"token": name, "ticker": d["symbol"], "chain": chain, "handle": _handle(tw),
            "logo_url": "https://s2.coinmarketcap.com/static/img/coins/200x200/%d.png" % d["id"], "source": url}

def _pretty(platform):
    """CMC platform labels -> the short names used on the card."""
    if not platform: return platform
    p = platform.lower()
    for key, nice in (("bnb", "BNB Chain"), ("binance", "BNB Chain"), ("ethereum", "Ethereum"), ("solana", "Solana"), ("base", "Base"),
                      ("arbitrum", "Arbitrum"), ("polygon", "Polygon"), ("avalanche", "Avalanche"), ("optimism", "Optimism"), ("sui", "Sui"), ("ton", "TON")):
        if key in p: return nice
    return re.sub(r"\s*\([^)]*\)", "", platform)

def lookup(url):
    url = url.strip()
    if "dexscreener.com" in url: return from_dexscreener(url)
    if "coinmarketcap.com" in url: return from_cmc(url)
    raise ValueError("send a dexscreener.com or coinmarketcap.com link")

def fetch_bytes(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]}), timeout=20) as r:
        return r.read(), r.headers.get_content_type()

if __name__ == "__main__":
    print(json.dumps(lookup(sys.argv[1]), indent=1))
