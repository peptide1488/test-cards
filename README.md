# Dexmoon DEX PAID card bot

Telegram bot that makes Dexmoon "DEX PAID" cards. Users walk through a button wizard
(autofill from a Dexscreener / CoinMarketCap link, or manual), pick colours, ref code, confirm,
and get the card as a photo + full-size 2400x1350 PNG.

The card is rendered by `index.html` - the same page as the web editor
(https://peptide1488.github.io/test-cards-web/) - driven headlessly by Playwright/Chromium,
so the bot and the web tool always look identical.

User guide: [USER_GUIDE.md](USER_GUIDE.md)

## Run it

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium     # --with-deps on Linux servers
cp bot_config.example.json bot_config.json            # admins, active template, lock, access
echo "<token from @BotFather>" > bot_token.txt        # or: export DEXMOON_BOT_TOKEN=...
python bot.py
```

Keep it running on a server (systemd / pm2 / docker). Example systemd unit:

```ini
[Unit]
Description=Dexmoon card bot
After=network-online.target

[Service]
WorkingDirectory=/opt/dexmoon-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
Environment=DEXMOON_BOT_TOKEN=xxxxx

[Install]
WantedBy=multi-user.target
```

Resources: ~300-400 MB RAM (headless Chromium), ~1-2 s per card. Only ONE instance may poll a bot token at a time.

## Files

| file | what |
|---|---|
| `bot.py` | Telegram bot: admin commands, template lock, rendering + sending |
| `wizard.py` | the step-by-step button wizard (/start, /card) |
| `lookup.py` | Dexscreener + CoinMarketCap lookup (name, ticker, chain by top liquidity, X handle, logo) |
| `render.py` | headless renderer: `CardRenderer().render({...})` -> PNG bytes; also a CLI |
| `index.html` | the card editor/renderer (built file - do not edit by hand) |
| `src.html` + `build.py` | source of index.html; edit src.html, then `python build.py` (inlines fonts + logos) |
| `presets/dexmoon_templates.json` | saved layouts (exported from the web tool's "Save + download .json") |
| `bot_config.example.json` | settings template -> copy to bot_config.json |

## Admin (in Telegram)

`/admin` lists everything. Main ones: `/use <template>` (the layout everyone gets), `/lock on|off`,
`/access public|private`, `/adduser @x`, `/addadmin @x`, `/templates`, `/status`.
Upload new templates by sending the exported `.dexmoon.json` file to the bot.
Colours (12 schemes or any hex) and ref codes are always chosen by the user; the template locks the layout.

## Render without Telegram

```bash
python render.py --token "Pepe" --ticker PEPE --chain Ethereum --handle pepecoineth --refcode MOON10 --theme Emerald -o card.png
```
