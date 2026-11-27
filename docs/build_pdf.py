# -*- coding: utf-8 -*-
"""
build_pdf.py  —  tukar docs/TDD_IKAWAL.md kepada docs/TDD_IKAWAL.pdf

Diagram Mermaid dirender menjadi imej (mermaid.ink, fallback kroki.io),
markdown -> HTML -> PDF (xhtml2pdf).

Guna:
    python docs/build_pdf.py
"""
import os, re, base64, zlib, urllib.request
import markdown
from xhtml2pdf import pisa

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "TDD_IKAWAL.md")
PDF = os.path.join(HERE, "TDD_IKAWAL.pdf")
IMG_DIR = os.path.join(HERE, "_diagrams")
os.makedirs(IMG_DIR, exist_ok=True)

src = open(MD, encoding="utf-8").read()

diagrams = {}
_counter = [0]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=45).read()


def render_mermaid(code):
    # 1) mermaid.ink
    try:
        u = "https://mermaid.ink/img/" + base64.urlsafe_b64encode(code.encode("utf-8")).decode()
        return fetch(u)
    except Exception as e1:
        # 2) kroki.io (deflate + base64url)
        try:
            comp = zlib.compress(code.encode("utf-8"), 9)
            u = "https://kroki.io/mermaid/png/" + base64.urlsafe_b64encode(comp).decode()
            return fetch(u)
        except Exception as e2:
            raise RuntimeError("mermaid.ink: %r | kroki: %r" % (e1, e2))


def repl(m):
    code = m.group(1).strip()
    idx = _counter[0]
    _counter[0] += 1
    key = "MMD%d" % idx
    try:
        data = render_mermaid(code)
        path = os.path.join(IMG_DIR, key + ("k.png" if data[:4] == b"\x89PNG" else ".jpg"))
        with open(path, "wb") as fh:
            fh.write(data)
        diagrams[key] = path
        print("  %s OK %d bytes  [%s...]" % (key, len(data), code.splitlines()[0][:40]))
        return "\n\n<!--%s-->\n\n" % key
    except Exception as e:
        print("  %s GAGAL %s" % (key, repr(e)[:140]))
        return m.group(0)  # kekalkan sebagai blok kod


src2 = re.sub(r"```mermaid\s*\n(.*?)```", repl, src, flags=re.S)
print("Jumlah blok mermaid:", _counter[0], "| berjaya:", len(diagrams))

body = markdown.markdown(src2, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])

for key, path in diagrams.items():
    p = path.replace("\\", "/")
    img = '<div class="diagram"><img src="%s"/></div>' % p
    body = body.replace("<!--%s-->" % key, img)
    body = body.replace("<p><!--%s--></p>" % key, img)

# resolve imej + set saiz eksplisit (cm) supaya xhtml2pdf render betul
try:
    from PIL import Image as _PILImage
except Exception:
    _PILImage = None


def _img_tag(m):
    tag = m.group(0)
    sm = re.search(r'src="([^"]+)"', tag)
    if not sm:
        return tag
    src = sm.group(1)
    if src.startswith(("http://", "https://", "data:")):
        return tag
    cand = src if os.path.isabs(src) else os.path.join(HERE, src)
    if not os.path.exists(cand):
        return tag
    cand = cand.replace("\\", "/")
    aspect = 1.6
    try:
        if _PILImage:
            w, h = _PILImage.open(cand).size
            aspect = (w / h) if h else 1.6
    except Exception:
        pass
    width_cm = 17.4
    height_cm = round(width_cm / aspect, 2)
    return '<img src="%s" style="width:%scm;height:%scm;"/>' % (cand, width_cm, height_cm)


body = re.sub(r"<img[^>]*>", _img_tag, body)

# aksara yang tak ada dalam font terbina (Helvetica/Courier) -> ASCII untuk PDF
REPL = [
    ("\u2192", "->"), ("\u2705", "Ya"), ("\u274c", "Tidak"), ("\u2610", "[ ]"),
    ("\u2605", "*"), ("\u2265", ">="), ("\u2264", "<="),
    ("\u201c", '"'), ("\u201d", '"'), ("\u2018", "'"), ("\u2019", "'"),
    ("\u251c\u2500", "|-- "), ("\u2514\u2500", "`-- "), ("\u2502", "|"), ("\u2500", "-"),
    ("\u00b7", "-"), ("\u2013", "-"), ("\u2014", "--"),
]
for a, b in REPL:
    body = body.replace(a, b)

CSS = """
@page { size: a4; margin: 1.6cm 1.5cm 1.8cm 1.5cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 9.7pt; color:#1c2b3a; line-height:1.45; }
h1 { font-size: 17pt; color:#0B2C4A; border-bottom:2px solid #F2B705; padding-bottom:4px; margin:0 0 8px 0; }
h2 { font-size: 13pt; color:#0B2C4A; margin:14px 0 5px 0; border-bottom:1px solid #DCE5F0; padding-bottom:2px; page-break-after: avoid; }
h3 { font-size: 11pt; color:#163E63; margin:10px 0 4px 0; }
p { margin: 4px 0; }
code { font-family: Courier, monospace; font-size: 8.6pt; background:#F1F5FA; }
pre { font-family: Courier, monospace; font-size: 8.2pt; background:#F4F6FA; border:1px solid #DCE5F0; padding:6px; white-space: pre-wrap; }
table { width:100%; margin:6px 0; }
th, td { border:1px solid #cfd9e5; padding:4px 6px; font-size:8.8pt; vertical-align: top; }
th { background:#EEF2F7; color:#0B2C4A; text-align:left; }
blockquote { background:#FFFBF0; border-left:4px solid #F2B705; margin:0 0 8px 0; padding:8px 10px; color:#5F7389; }
hr { border:0; border-top:1px solid #DCE5F0; }
a { color:#1E5AA8; }
img { width:100%; }
.diagram { text-align:center; margin:8px 0; page-break-inside: avoid; }
ul, ol { margin:4px 0; }
"""

full = '<!doctype html><html><head><meta charset="utf-8"><style>%s</style></head><body>%s</body></html>' % (CSS, body)


def link_callback(uri, rel):
    return uri


with open(PDF, "wb") as f:
    result = pisa.CreatePDF(full, dest=f, link_callback=link_callback)

print("err:", result.err)
print("PDF:", PDF, os.path.getsize(PDF), "bytes")
