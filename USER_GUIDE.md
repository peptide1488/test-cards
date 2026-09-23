# Dexmoon card maker: user guide

Two ways to make a **DEX PAID** card: the **Telegram bot** (fastest) or the **web editor** (full control).

---

## Telegram bot: @dexmoonupdaterbot

Open **https://t.me/dexmoonupdaterbot**, press **Start**, and follow the buttons.

1. **How do you want to fill it in?**
   - **🔗 Autofill from a link**: paste a Dexscreener or CoinMarketCap link. The bot finds the name, ticker, chain and X handle, and uses the X profile picture for the little circle.
   - **✍️ Fill in manually**: type the name, ticker, chain and X handle yourself.
2. **Picture:** use the token's picture from the link, keep the moon, or upload your own.
   - **Transparent PNG** (no background, sent as a *File*: 📎 → File): shown big as a cut-out, with the moon behind it.
   - **Any other picture**: shown in a round badge with a glowing ring.
3. **Colours:** pick one of the 12 schemes, tap **🖌 Custom colour** and send a hex code (e.g. `#2f8a5a`), or keep the template colours.
4. **Ref code:** type it, or skip. It goes in the footer ("Save 10% on your update · code …").
5. **Check the summary.** Use the buttons to change colours, ref code, chain or picture, then press **✅ Make it**.
6. You get the card as a photo, plus the **full-quality PNG as a file** (use the file for posting).

Tip: after a card, **🎨 Same card, new colour** remakes it in another colour without re-entering anything.

Commands: `/start` or `/card` makes a card · `/cancel` stops · `/themes` lists colour schemes.

---

## Web editor

Open **https://peptide1488.github.io/test-cards-web/**. It works in any browser, with nothing to install.

- **Fill from link:** paste a Dexscreener / CMC link in *Link* and press **Fill from link**.
- **Hero image:** drop an image on the dashed box (or straight onto the card), or paste it with Ctrl+V.
  - *Mode*: **Auto** picks for you. **Hero** is a big transparent cut-out; **PFP** is a round badge.
- **Edit anything:** click any text or object on the card and its settings open on the left.
  - **Drag** to move.
  - **Drag a corner handle** to resize.
  - **Arrow keys** nudge (Shift = 10 px).
  - **Alt+click** picks the thing *behind* (e.g. the moon behind the hero).
- **Colour scheme:** preset buttons, or the **Custom** colour picker.
- **Reset:** **↺ Reset positions** puts everything back; each element also has its own ↺.
- **Download PNG:** 2400×1350 (sharpest), or 1200×675.

### Saving and sharing a layout (template)
1. Arrange the card the way you like.
2. Under **Saved templates**, type a name and choose:
   - *layout + colours only*: reusable for any coin, **recommended**
   - *everything*: includes the text and images
3. Press **Save + download .json** (or **⬇** next to a saved template).
4. Send the `.dexmoon.json` file to the admin. They forward it to the bot and send `/use <name>`, and from then on every bot card uses that layout.

Templates are also kept in your browser (Load / Update / ✕). **Export all** backs them all up in one file; **Import file** loads them back.

---

## For admins (in the bot chat)

`/admin` lists all admin commands. The main ones:

| command | does |
|---|---|
| send a `.dexmoon.json` file | adds those templates to the bot |
| `/templates` | lists templates (* = active) |
| `/use <name>` | makes that layout the one everyone gets (`/use off` = default) |
| `/lock on` / `/lock off` | on: users pick content, colours and ref code only; the layout stays yours |
| `/access private` / `/access public` | private: only admins + `/adduser @name` users can use the bot |
| `/addadmin @name` | adds another admin |
| `/status` | shows current settings and cards made |
