"""Dexmoon DEX PAID card - Telegram bot.
    set DEXMOON_BOT_TOKEN=<token from @BotFather>      (or put it in dexmoon_card/bot_token.txt)
    python bot.py
Chat usage:
    Fastest: paste a dexscreener.com or coinmarketcap.com link (+ 'Code: XYZ') -> name, ticker, chain, X handle and the token
    logo (as hero) fill automatically; any typed line overrides it. 'Logo: no' keeps the moon.
    /card   -> the bot replies with the fill-in template
    Send the filled lines as a message. For a hero image, attach it: as a FILE (keeps PNG transparency - best) or as a photo,
    with the lines in the caption.
        Token: Pepe Coin
        Ticker: PEPE
        Chain: Solana
        Handle: pepecoin
        Code: MOON10
        Theme: Emerald          (optional: Dexmoon Midnight Ocean Emerald Gold Sunset Crimson Rose Mono Neon Toxic Ice, or #hex)
        Size: 120               (optional: hero size in %, 100 = moon size)
        Mode: hero | pfp        (optional: hero = transparent cut-out shown large, pfp = any picture in a round badge; default = auto)
        Headline: DEX PAID      (optional)   Updated: ...  (optional, default = now UTC)
    /themes -> list of colour schemes     /layouts -> saved layouts (from the web tool's Export, dropped in presets/); use with 'Layout: name'
Reply: the card as a photo (preview) + the lossless 2400x1350 PNG as a file.
Rendering = render.py -> the same index.html the browser editor uses (one source of truth)."""
import asyncio, base64, io, os, re, pathlib, logging
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from render import CardRenderer
import lookup, wizard

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)   # httpx logs full request URLs, which contain the bot token
HERE = pathlib.Path(__file__).parent
THEMES = ["Dexmoon", "Midnight", "Ocean", "Emerald", "Gold", "Sunset", "Crimson", "Rose", "Mono", "Neon", "Toxic", "Ice"]
KEYS = {"token": "token", "name": "token", "ticker": "ticker", "chain": "chain", "handle": "handle", "code": "refcode",
        "refcode": "refcode", "ref": "refcode", "headline": "headline", "updated": "updated", "site": "site",
        "theme": "theme", "color": "theme", "colour": "theme", "size": "heroSize", "herosize": "heroSize", "link": "link", "logo": "logo", "layout": "layout", "template": "layout", "mode": "mode"}
TEMPLATE = "Link: \nCode: \nTheme: Dexmoon\nSize: 100\n\n(instead of Link you can type: Token / Ticker / Chain / Handle)"
POOL = ThreadPoolExecutor(1); _R = None          # one headless Chromium, reused; renders are serialized on one thread

def load_layout(name):
    """A template exported from the web tool (dexmoon_templates.json, or a single saved template) placed in presets/."""
    import json
    for f in sorted((HERE / "presets").glob("*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        items = j.get("templates", {}) if j.get("dexmoonTemplates") else {f.stem: j}
        for k, t in items.items():
            if k.lower() == name.lower() or f.stem.lower() == name.lower() and len(items) == 1:
                return t.get("config", t)
    return None

def layouts():
    import json; out = []
    for f in sorted((HERE / "presets").glob("*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        out += [k for k in (j.get("templates", {}) if j.get("dexmoonTemplates") else {f.stem: 1}) if k != "(current card)"]
    return out

# ---------------- admin config (bot_config.json) ----------------
import json
CFG_PATH = HERE / "bot_config.json"
DEFAULT_CFG = {"admins": ["dogenerate"], "admin_ids": [], "active_layout": None, "allowed_layouts": [],
               "lock_design": True, "access": "public", "allowed_users": [], "stats": {"cards": 0}}
def cfg():
    try: c = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except Exception: c = {}
    return {**DEFAULT_CFG, **c}
def save_cfg(c): CFG_PATH.write_text(json.dumps(c, indent=1), encoding="utf-8")
def is_admin(user):
    c = cfg(); u = (user.username or "").lower()
    if user.id in c["admin_ids"]: return True
    if u and u in [a.lower().lstrip("@") for a in c["admins"]]:
        c["admin_ids"] = sorted(set(c["admin_ids"] + [user.id])); save_cfg(c); return True    # pin the admin's numeric id on first contact
    return False
def can_use(user):
    c = cfg()
    if c["access"] == "public" or is_admin(user): return True
    return (user.username or "").lower() in [x.lower().lstrip("@") for x in c["allowed_users"]] or user.id in c["allowed_users"]

def _render(fields):
    global _R
    if _R is None: _R = CardRenderer()
    return _R.render(fields)

def parse(text):
    f = {}
    for line in (text or "").splitlines():
        m = re.match(r"\s*([A-Za-z]+)\s*[:=]\s*(.*?)\s*$", line)
        if m and m.group(1).lower() in KEYS and m.group(2): f[KEYS[m.group(1).lower()]] = m.group(2)
    if "theme" in f:
        t = f["theme"]; hit = [n for n in THEMES if n.lower() == t.lower()]
        f["theme"] = hit[0] if hit else (t if re.fullmatch(r"#?[0-9a-fA-F]{6}", t) and t.startswith("#") else ("#" + t if re.fullmatch(r"[0-9a-fA-F]{6}", t) else "Dexmoon"))
    if "heroSize" in f:
        try: f["heroSize"] = max(20.0, min(250.0, float(f["heroSize"].rstrip("%"))))
        except ValueError: f.pop("heroSize")
    return f

async def card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Fill this in and send it back. For a hero image attach it (as a FILE to keep transparency) and put the lines in the caption.\n\n"
        + TEMPLATE + "\n\nThemes: " + ", ".join(THEMES) + " or any #hex colour. Size = hero size in %.")

async def layouts_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ls = layouts()
    await update.message.reply_text(("Saved layouts: " + ", ".join(ls) + ". Use one with a line like  Layout: " + ls[0]) if ls else
        "No saved layouts yet. In the web tool: save a template, Export, and put the file in the bot's presets folder.")

# ---------------- admin commands ----------------
ADMIN_HELP = ("Admin commands:\n"
  "/templates - list saved templates (* = active)\n"
  "/use <name> - make that template the one everyone gets\n"
  "/use off - back to the default Dexmoon look\n"
  "/allowtemplate <name> / /denytemplate <name> - templates users may pick with 'Layout:' while the design is locked\n"
  "/lock on|off - on: users only send content (link, code, image); the look comes from your template\n"
  "/access public|private - private: only admins + /adduser users can make cards\n"
  "/adduser @name  /removeuser @name  /users\n"
  "/addadmin @name  /removeadmin @name\n"
  "/status - current settings + cards made\n"
  "Upload templates: in the web tool Save -> Export all, then send the dexmoon_templates.json file to this bot.")

async def admin_only(update):
    if is_admin(update.effective_user): return True
    await update.message.reply_text("Admins only."); return False

async def a_help(update, ctx):
    if await admin_only(update): await update.message.reply_text(ADMIN_HELP)
async def a_templates(update, ctx):
    if not await admin_only(update): return
    c = cfg(); ls = layouts()
    await update.message.reply_text("Templates:\n" + "\n".join(("* " if n == c["active_layout"] else "- ") + n + ("  (users may pick)" if n in c["allowed_layouts"] else "") for n in ls) if ls else
                                    "No templates yet. Export them from the web tool and send the .json file here.")
async def a_use(update, ctx):
    if not await admin_only(update): return
    name = " ".join(ctx.args).strip(); c = cfg()
    if name.lower() in ("off", "none", "default", ""):
        c["active_layout"] = None; save_cfg(c); return await update.message.reply_text("Active template: default Dexmoon look.")
    hit = [n for n in layouts() if n.lower() == name.lower()]
    if not hit: return await update.message.reply_text("No template called '%s'. /templates lists them." % name)
    c["active_layout"] = hit[0]; save_cfg(c); await update.message.reply_text("Active template: %s - every card now uses it." % hit[0])
async def a_allowtpl(update, ctx, allow=True):
    if not await admin_only(update): return
    name = " ".join(ctx.args).strip(); c = cfg(); hit = [n for n in layouts() if n.lower() == name.lower()]
    if not hit: return await update.message.reply_text("No template called '%s'." % name)
    s_ = set(c["allowed_layouts"]); (s_.add if allow else s_.discard)(hit[0]); c["allowed_layouts"] = sorted(s_); save_cfg(c)
    await update.message.reply_text("Users may pick: " + (", ".join(c["allowed_layouts"]) or "(none - everyone gets the active template)"))
async def a_denytpl(update, ctx): await a_allowtpl(update, ctx, allow=False)
async def a_lock(update, ctx):
    if not await admin_only(update): return
    v = (ctx.args[0].lower() if ctx.args else ""); c = cfg()
    if v in ("on", "off"): c["lock_design"] = v == "on"; save_cfg(c)
    await update.message.reply_text("Design lock is %s." % ("ON - users only send content" if cfg()["lock_design"] else "OFF - users may set Theme/Size/Mode/Layout"))
async def a_access(update, ctx):
    if not await admin_only(update): return
    v = (ctx.args[0].lower() if ctx.args else ""); c = cfg()
    if v in ("public", "private"): c["access"] = v; save_cfg(c)
    await update.message.reply_text("Access: %s" % cfg()["access"])
async def a_user(update, ctx, key, add):
    if not await admin_only(update): return
    names = [a.lstrip("@").lower() for a in ctx.args if a.strip()]
    if not names: return await update.message.reply_text("Give a @username.")
    c = cfg(); s_ = set(x.lower() for x in c[key]); [(s_.add if add else s_.discard)(n) for n in names]
    if key == "admins" and not s_: return await update.message.reply_text("Can't remove the last admin.")
    c[key] = sorted(s_); save_cfg(c); await update.message.reply_text("%s: %s" % ("Admins" if key == "admins" else "Allowed users", ", ".join("@" + x for x in c[key]) or "(none)"))
async def a_adduser(u, c): await a_user(u, c, "allowed_users", True)
async def a_removeuser(u, c): await a_user(u, c, "allowed_users", False)
async def a_addadmin(u, c): await a_user(u, c, "admins", True)
async def a_removeadmin(u, c):
    await a_user(u, c, "admins", False)
    cc = cfg(); cc["admin_ids"] = []; save_cfg(cc)          # re-pinned on next admin message
async def a_users(update, ctx):
    if await admin_only(update): c = cfg(); await update.message.reply_text("Access %s. Allowed users: %s" % (c["access"], ", ".join("@" + x for x in c["allowed_users"]) or "(none)"))
async def a_status(update, ctx):
    if not await admin_only(update): return
    c = cfg()
    await update.message.reply_text("Active template: %s\nUsers may pick: %s\nDesign lock: %s\nAccess: %s\nAdmins: %s\nCards made: %d" % (
        c["active_layout"] or "default Dexmoon", ", ".join(c["allowed_layouts"]) or "-", "on" if c["lock_design"] else "off", c["access"],
        ", ".join("@" + a for a in c["admins"]), c["stats"].get("cards", 0)))
async def a_upload(update, ctx):
    """Admin sends the web tool's exported dexmoon_templates.json -> merged into presets/."""
    doc = update.message.document
    if not is_admin(update.effective_user): return await update.message.reply_text("Only admins can upload templates.")
    b = bytes(await (await doc.get_file()).download_as_bytearray())
    try: j = json.loads(b.decode("utf-8"))
    except Exception: return await update.message.reply_text("That isn't a template file.")
    target = HERE / "presets" / "dexmoon_templates.json"; target.parent.mkdir(exist_ok=True)
    cur = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"dexmoonTemplates": 1, "templates": {}}
    new = j.get("templates", {}) if j.get("dexmoonTemplates") else {pathlib.Path(doc.file_name or "template").stem: j}
    new = {k: v for k, v in new.items() if k != "(current card)"}
    cur["templates"].update(new); target.write_text(json.dumps(cur, indent=1), encoding="utf-8")
    await update.message.reply_text("Saved %d template(s): %s\nMake one active with /use <name>." % (len(new), ", ".join(new)))

async def themes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Colour schemes: " + ", ".join(THEMES) + "\nOr any hex colour, e.g. Theme: #2f8a5a")

async def fill(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.caption if (msg.photo or msg.document) else msg.text
    f = parse(text)
    url = f.pop("link", None) or next(iter(re.findall(r"https?://\S*(?:dexscreener\.com|coinmarketcap\.com)\S*", text or "")), None)
    logo = None
    if url:   # dexscreener / coinmarketcap link -> token, ticker, chain, X handle (+ logo as hero); typed lines still win
        loop = asyncio.get_running_loop()
        try: got = await loop.run_in_executor(None, lookup.lookup, url)
        except Exception as e: return await msg.reply_text("Couldn't read that link: %s" % e)
        for k in ("token", "ticker", "chain", "handle"):
            if got.get(k) and k not in f: f[k] = got[k]
        if got.get("logo_url") and str(f.get("logo", "yes")).lower() not in ("no", "off", "false", "0"):
            try: logo = await loop.run_in_executor(None, lookup.fetch_bytes, got["logo_url"])
            except Exception: logo = None
        pfp = None                              # small @handle circle: the X profile picture, else the token logo
        if got.get("handle"):
            try: pfp = await loop.run_in_executor(None, lookup.fetch_bytes, "https://unavatar.io/x/%s?fallback=false" % got["handle"])
            except Exception: pfp = None
        pfp = pfp or logo
        if pfp: f["avatar"] = "data:%s;base64,%s" % (pfp[1], base64.b64encode(pfp[0]).decode())
    f.pop("logo", None)
    if not can_use(update.effective_user):
        return await msg.reply_text("This bot is private. Ask an admin for access.")
    c = cfg(); admin = is_admin(update.effective_user)
    if c["lock_design"] and not admin:          # regular users only supply content; the admin's template decides the look
        for k in ("heroSize", "mode", "headline"): f.pop(k, None)
        if "layout" in f and f["layout"] not in c["allowed_layouts"]: f.pop("layout")
    if "layout" not in f and c["active_layout"]: f["layout"] = c["active_layout"]
    if "layout" in f:
        lay = load_layout(f.pop("layout"))
        if lay is None: return await msg.reply_text("No saved layout with that name. /layouts lists them.")
        f["preset"] = lay
    if not {"token", "ticker", "chain"} <= f.keys():
        return await msg.reply_text("Need at least Token, Ticker and Chain. Send /card for the template.")
    tgfile, mime = None, "image/png"
    if msg.document and (msg.document.mime_type or "").startswith("image/"):
        tgfile, mime = await msg.document.get_file(), msg.document.mime_type
    elif msg.photo:
        tgfile, mime = await msg.photo[-1].get_file(), "image/jpeg"
    if tgfile:
        b = await tgfile.download_as_bytearray()
        f["hero"] = "data:%s;base64,%s" % (mime, base64.b64encode(bytes(b)).decode())
    elif logo:
        f["hero"] = "data:%s;base64,%s" % (logo[1], base64.b64encode(logo[0]).decode())
    await ctx.bot.send_chat_action(msg.chat_id, "upload_photo")
    try:
        png = await asyncio.get_running_loop().run_in_executor(POOL, _render, f)
    except Exception as e:
        logging.exception("render failed"); return await msg.reply_text("Render failed: %s" % e)
    name = re.sub(r"[^\w$-]+", "_", f["token"]) + "_dexmoon.png"
    await msg.reply_photo(io.BytesIO(png), caption="%s - DEX PAID" % f["token"])
    await msg.reply_document(io.BytesIO(png), filename=name)
    c = cfg(); c["stats"]["cards"] = c["stats"].get("cards", 0) + 1; save_cfg(c)

async def render_and_send(bot_, chat_id, user, f):
    """Apply the admin's template/lock, render, send photo + lossless PNG."""
    c = cfg(); admin = is_admin(user)
    if c["lock_design"] and not admin:
        for k in ("heroSize", "mode", "headline"): f.pop(k, None)
    if "layout" not in f and c["active_layout"]: f["layout"] = c["active_layout"]
    if "layout" in f:
        lay = load_layout(f.pop("layout"))
        if lay is not None: f["preset"] = lay
    await bot_.send_chat_action(chat_id, "upload_photo")
    try: png = await asyncio.get_running_loop().run_in_executor(POOL, _render, f)
    except Exception as e:
        logging.exception("render failed"); return await bot_.send_message(chat_id, "Render failed: %s" % e)
    name = re.sub(r"[^\w$-]+", "_", f.get("token", "card")) + "_dexmoon.png"
    await bot_.send_photo(chat_id, io.BytesIO(png), caption="%s - DEX PAID" % f.get("token", ""))
    await bot_.send_document(chat_id, io.BytesIO(png), filename=name)
    c = cfg(); c["stats"]["cards"] = c["stats"].get("cards", 0) + 1; save_cfg(c)

def main():
    tok = os.environ.get("DEXMOON_BOT_TOKEN") or ((HERE / "bot_token.txt").read_text().strip() if (HERE / "bot_token.txt").exists() else "")
    if not tok: raise SystemExit("No bot token: set DEXMOON_BOT_TOKEN or create bot_token.txt next to bot.py (get one from @BotFather).")
    app = Application.builder().token(tok).build()
    app.add_handler(wizard.build(render_and_send, THEMES, can_use))
    app.add_handler(CommandHandler("help", card))
    app.add_handler(CommandHandler("themes", themes))
    app.add_handler(CommandHandler("layouts", layouts_cmd))
    for name, fn in (("admin", a_help), ("templates", a_templates), ("use", a_use), ("allowtemplate", a_allowtpl), ("denytemplate", a_denytpl),
                     ("lock", a_lock), ("access", a_access), ("adduser", a_adduser), ("removeuser", a_removeuser), ("users", a_users),
                     ("addadmin", a_addadmin), ("removeadmin", a_removeadmin), ("status", a_status)):
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(MessageHandler(filters.Document.FileExtension("json"), a_upload))
    app.add_handler(MessageHandler((filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.Document.IMAGE, fill))
    logging.info("Dexmoon bot running"); app.run_polling()

if __name__ == "__main__":
    main()
