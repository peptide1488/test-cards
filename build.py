"""Builds the self-contained index.html (fonts + both logos inlined) from src.html.  Run after editing src.html:  python build.py"""
import base64
s = open("src.html", encoding="utf-8").read().replace("/*__FONTS__*/", open("fonts/fonts_inline.css", encoding="utf-8").read())
for name in ("logo_icon.png", "logo_lockup.png"):
    s = s.replace("'%s'" % name, "'data:image/png;base64,%s'" % base64.b64encode(open(name, "rb").read()).decode())
open("index.html", "w", encoding="utf-8").write(s); print("index.html", len(s) // 1024, "KB")
