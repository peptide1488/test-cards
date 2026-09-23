"""Step-by-step card wizard for the Dexmoon bot (inline buttons). Wired in by bot.py.

/start or /card
  -> How do you want to fill it?   [Autofill from a link] [Fill in manually]
  link:   send link -> shows what was found -> Use the token's picture from the link?  [Yes] [No, keep the moon] [Upload my own]
  manual: name -> ticker -> chain (buttons or type) -> X handle (or Skip) -> picture? [Upload] [Keep the moon]
  -> Colour scheme  (theme buttons, or keep the template colours)
  -> Ref code (type it, or Skip)
  -> card (photo + full-size PNG file) -> [Make another] [Same card, new colour]
"""
import asyncio, base64, re
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as KB
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import lookup

MODE, LINK, PIC, NAME, TICKER, CHAIN, HANDLE, UPLOAD, COLOUR, REF, CONFIRM, HEX = range(12)
CHAINS = ["Solana", "Ethereum", "Base", "BNB Chain", "Robinhood", "Hyperliquid", "Sui", "Arbitrum", "TON"]

def _kb(rows): return KB([[B(t, callback_data=d) for t, d in r] for r in rows])
def _data_url(b, mime): return "data:%s;base64,%s" % (mime, base64.b64encode(b).decode())

async def _say(update, text, kb=None):
    if update.callback_query:
        await update.callback_query.answer()
        return await update.callback_query.message.reply_text(text, reply_markup=kb)
    return await update.message.reply_text(text, reply_markup=kb)

def build(render_and_send, themes, can_use):
    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not can_use(update.effective_user):
            await _say(update, "This bot is private. Ask an admin for access."); return ConversationHandler.END
        ctx.user_data["card"] = {}
        await _say(update, "Let's make a DEX PAID card. How do you want to fill it in?",
                   _kb([[("🔗 Autofill from a link", "m:link")], [("✍️ Fill in manually", "m:manual")]]))
        return MODE

    async def mode(update, ctx):
        if update.callback_query.data == "m:link":
            await _say(update, "Send the Dexscreener or CoinMarketCap link for the token."); return LINK
        await _say(update, "What's the token name? (e.g. Pepe Coin)"); return NAME

    # ---------- link path ----------
    async def got_link(update, ctx):
        url = update.message.text.strip()
        await update.message.reply_text("Looking it up...")
        loop = asyncio.get_running_loop()
        try: got = await loop.run_in_executor(None, lookup.lookup, url)
        except Exception as e:
            await update.message.reply_text("Couldn't read that link (%s). Send another link, or /card to start over." % e); return LINK
        c = ctx.user_data["card"]
        c.update({k: got[k] for k in ("token", "ticker", "chain", "handle") if got.get(k)})
        ctx.user_data["logo_url"] = got.get("logo_url")
        if got.get("handle"):   # small @handle circle: X profile picture, token logo as fallback (fetched now, used unless replaced)
            try:
                b, mt = await loop.run_in_executor(None, lookup.fetch_bytes, "https://unavatar.io/x/%s?fallback=false" % got["handle"])
                c["avatar"] = _data_url(b, mt)
            except Exception: pass
        found = "Found: %s  $%s  on %s%s" % (c.get("token"), str(c.get("ticker", "")).lstrip("$"), c.get("chain"),
                                             ("  ·  @" + c["handle"]) if c.get("handle") else "  ·  (no X handle listed)")
        rows = [[("✅ Yes, use the token's picture", "p:logo")]] if got.get("logo_url") else []
        rows += [[("🌙 No, keep the moon", "p:moon")], [("📎 I'll upload my own", "p:upload")]]
        await update.message.reply_text(found + "\n\nUse the token's picture from the link on the card?", reply_markup=_kb(rows))
        return PIC

    async def pic(update, ctx):
        choice = update.callback_query.data; c = ctx.user_data["card"]
        if choice == "p:upload":
            await _say(update, "Send the picture. Tip: send it as a FILE (📎 → File) to keep a transparent background — "
                               "transparent PNGs are shown big as a cut-out, anything else goes in a round badge."); return UPLOAD
        if choice == "p:moon": c.pop("hero", None); ctx.user_data["hero_is_logo"] = False
        if choice == "p:logo" and ctx.user_data.get("logo_url"):
            ctx.user_data["hero_is_logo"] = True
            try:
                b, mt = await asyncio.get_running_loop().run_in_executor(None, lookup.fetch_bytes, ctx.user_data["logo_url"])
                c["hero"] = _data_url(b, mt); c.setdefault("avatar", c["hero"])
            except Exception:
                await _say(update, "Couldn't download the token picture - keeping the moon.")
        if ctx.user_data.pop("editing", False): return await summary(update, ctx)
        return await ask_colour(update, ctx)

    # ---------- manual path ----------
    async def name(update, ctx):
        ctx.user_data["card"]["token"] = update.message.text.strip()
        await update.message.reply_text("Ticker? (e.g. PEPE)"); return TICKER
    async def ticker(update, ctx):
        ctx.user_data["card"]["ticker"] = update.message.text.strip().lstrip("$").upper()
        rows = [[(n, "c:" + n) for n in CHAINS[i:i + 3]] for i in range(0, len(CHAINS), 3)]
        await update.message.reply_text("Which chain? Tap one or type it.", reply_markup=_kb(rows)); return CHAIN
    async def chain(update, ctx):
        ctx.user_data["card"]["chain"] = update.callback_query.data[2:] if update.callback_query else update.message.text.strip()
        if ctx.user_data.pop("editing", False): return await summary(update, ctx)
        await _say(update, "X / Twitter handle? (e.g. @pepecoin)", _kb([[("Skip", "h:skip")]])); return HANDLE
    async def handle(update, ctx):
        if update.message: ctx.user_data["card"]["handle"] = update.message.text.strip().lstrip("@")
        await _say(update, "Add a picture for the card?", _kb([[("📎 Upload a picture", "p:upload")], [("🌙 Keep the moon", "p:moon")]]))
        return PIC

    async def upload(update, ctx):
        m = update.message; c = ctx.user_data["card"]
        if m.document and (m.document.mime_type or "").startswith("image/"):
            f, mt = await m.document.get_file(), m.document.mime_type
        elif m.photo:
            f, mt = await m.photo[-1].get_file(), "image/jpeg"
        else:
            await m.reply_text("That's not an image - send a picture, or tap /card to start over."); return UPLOAD
        c["hero"] = _data_url(bytes(await f.download_as_bytearray()), mt); ctx.user_data["hero_is_logo"] = False
        if ctx.user_data.pop("editing", False): return await summary(update, ctx)
        return await ask_colour(update, ctx)

    # ---------- colour + ref code ----------
    async def ask_colour(update, ctx):
        rows = [[("🎨 Keep the template colours", "t:keep")], [("🖌 Custom colour (hex code)", "t:hex")]]
        rows += [[(n, "t:" + n) for n in themes[i:i + 3]] for i in range(0, len(themes), 3)]
        await _say(update, "Pick a colour scheme:", _kb(rows)); return COLOUR
    async def colour(update, ctx):
        t = update.callback_query.data[2:]
        if t == "hex":
            await _say(update, "Send a hex colour code, e.g. #2f8a5a or ff6600. It becomes the main accent (badge, pfp ring, glow, moon tint).\n"
                               "Tip: pick one at https://htmlcolorcodes.com/color-picker/"); return HEX
        if t != "keep": ctx.user_data["card"]["theme"] = t
        else: ctx.user_data["card"].pop("theme", None)
        if ctx.user_data.pop("recolour", False) or ctx.user_data.pop("editing", False):
            return await summary(update, ctx)
        await _say(update, "Your ref code for the footer? Type it, or skip.", _kb([[("Skip", "r:skip")]])); return REF
    async def hexcode(update, ctx):
        m = re.fullmatch(r"#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})", update.message.text.strip())
        if not m:
            await update.message.reply_text("That isn't a hex colour. Send 6 characters like #2f8a5a (or 3 like #f60)."); return HEX
        h = m.group(1); h = "".join(ch * 2 for ch in h) if len(h) == 3 else h
        ctx.user_data["card"]["theme"] = "#" + h.lower()
        if ctx.user_data.pop("recolour", False) or ctx.user_data.pop("editing", False): return await summary(update, ctx)
        await update.message.reply_text("Your ref code for the footer? Type it, or skip.", reply_markup=_kb([[("Skip", "r:skip")]])); return REF

    async def ref(update, ctx):
        if update.message: ctx.user_data["card"]["refcode"] = update.message.text.strip()
        else: ctx.user_data["card"].pop("refcode", None)
        ctx.user_data.pop("editing", None)
        return await summary(update, ctx)

    async def summary(update, ctx):
        c = ctx.user_data["card"]
        pic = ("your uploaded picture" if c.get("hero") and not ctx.user_data.get("hero_is_logo") else
               "the token's picture" if c.get("hero") else "the moon")
        lines = ["Here's your card:",
                 "• Token: %s" % c.get("token", "-"), "• Ticker: $%s" % str(c.get("ticker", "-")).lstrip("$"),
                 "• Chain: %s" % c.get("chain", "-"), "• X handle: %s" % ("@" + c["handle"] if c.get("handle") else "none"),
                 "• Picture: %s" % pic, "• Colours: %s" % (c.get("theme") or "template colours"),
                 "• Ref code: %s" % (c.get("refcode") or "none")]
        kb = _kb([[("✅ Make it", "k:go")],
                  [("🎨 Change colours", "k:colour"), ("🏷 Change ref code", "k:ref")],
                  [("⛓ Change chain", "k:chain"), ("🖼 Change picture", "k:pic")], [("🔄 Start over", "k:restart")]])
        await _say(update, "\n".join(lines), kb); return CONFIRM

    async def confirm(update, ctx):
        d = update.callback_query.data
        if d == "k:go":
            await update.callback_query.answer("Making it..."); return await finish(update, ctx)
        if d == "k:colour": ctx.user_data["editing"] = True; return await ask_colour(update, ctx)
        if d == "k:ref":
            ctx.user_data["editing"] = True
            await _say(update, "New ref code? Type it, or skip.", _kb([[("Skip", "r:skip")]])); return REF
        if d == "k:chain":
            ctx.user_data["editing"] = True
            rows = [[(n, "c:" + n) for n in CHAINS[i:i + 3]] for i in range(0, len(CHAINS), 3)]
            await _say(update, "Which chain? Tap one or type it.", _kb(rows)); return CHAIN
        if d == "k:pic":
            ctx.user_data["editing"] = True
            rows = [[("✅ Token's picture", "p:logo")]] if ctx.user_data.get("logo_url") else []
            rows += [[("📎 Upload my own", "p:upload")], [("🌙 Keep the moon", "p:moon")]]
            await _say(update, "Which picture?", _kb(rows)); return PIC
        return await start(update, ctx)

    async def finish(update, ctx):
        chat = update.effective_chat.id
        await render_and_send(ctx.bot, chat, update.effective_user, dict(ctx.user_data["card"]))
        await ctx.bot.send_message(chat, "Want another?", reply_markup=_kb([[("🔁 Make another card", "a:new")], [("🎨 Same card, new colour", "a:recolour")]]))
        return ConversationHandler.END

    async def again(update, ctx):
        if update.callback_query.data == "a:recolour" and ctx.user_data.get("card"):
            ctx.user_data["recolour"] = True; return await ask_colour(update, ctx)   # -> summary -> confirm
        return await start(update, ctx)

    async def cancel(update, ctx):
        await update.message.reply_text("Cancelled. /card to start again."); return ConversationHandler.END

    text = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[CommandHandler(["start", "card"], start), CallbackQueryHandler(again, pattern=r"^a:")],
        states={
            MODE: [CallbackQueryHandler(mode, pattern=r"^m:")],
            LINK: [MessageHandler(text, got_link)],
            PIC: [CallbackQueryHandler(pic, pattern=r"^p:")],
            NAME: [MessageHandler(text, name)],
            TICKER: [MessageHandler(text, ticker)],
            CHAIN: [CallbackQueryHandler(chain, pattern=r"^c:"), MessageHandler(text, chain)],
            HANDLE: [CallbackQueryHandler(handle, pattern=r"^h:"), MessageHandler(text, handle)],
            UPLOAD: [MessageHandler(filters.PHOTO | filters.Document.ALL | text, upload)],
            COLOUR: [CallbackQueryHandler(colour, pattern=r"^t:")],
            REF: [CallbackQueryHandler(ref, pattern=r"^r:"), MessageHandler(text, ref)],
            CONFIRM: [CallbackQueryHandler(confirm, pattern=r"^k:")],
            HEX: [MessageHandler(text, hexcode)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler(["start", "card"], start)],
        allow_reentry=True,
    )
