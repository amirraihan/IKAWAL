"""Bina app.html (IRINGKAWAL BPK 2026) daripada templat + SheetJS + data + avatar Devin.

Guna:
    python src/build_app.py

Output: <repo>/app.html
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read(name):
    with open(os.path.join(HERE, name), 'r', encoding='utf-8') as f:
        return f.read()


tpl = read('app.template.html')
lib = read('sheetjs.min.js')
data = read('data.json')
avatar = read('devin_b64.txt').strip()

for tok in ('/*__SHEETJS__*/', '/*__DEFAULT_DATA__*/[]', '__DEVIN_AVATAR__'):
    assert tok in tpl, 'token hilang: ' + tok

out = (tpl.replace('/*__SHEETJS__*/', lib)
          .replace('/*__DEFAULT_DATA__*/[]', data)
          .replace('__DEVIN_AVATAR__', avatar))

dst = os.path.join(ROOT, 'app.html')
with open(dst, 'w', encoding='utf-8') as f:
    f.write(out)
print('built', dst, os.path.getsize(dst), 'bytes')
