"""Bina sistem_tahanan.html (Sistem Pengurusan Data Tahanan + Reman 35 + Devin).

Guna:
    python src/build_sistem.py

Output: <repo>/sistem_tahanan.html
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read(name):
    with open(os.path.join(HERE, name), 'r', encoding='utf-8') as f:
        return f.read()


tpl = read('sistem.template.html')
lib = read('sheetjs.min.js')
seed = read('seed.json')
avatar = read('devin_b64.txt').strip()

for tok in ('/*__SHEETJS__*/', '__SEED__', '__DEVIN_AVATAR__'):
    assert tok in tpl, 'token hilang: ' + tok

out = (tpl.replace('/*__SHEETJS__*/', lib)
          .replace('__SEED__', seed)
          .replace('__DEVIN_AVATAR__', avatar))

dst = os.path.join(ROOT, 'sistem_tahanan.html')
with open(dst, 'w', encoding='utf-8') as f:
    f.write(out)
print('built', dst, os.path.getsize(dst), 'bytes')
