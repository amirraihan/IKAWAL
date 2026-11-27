# src/ — Sumber binaan (build sources)

Folder ini mengandungi **sumber** untuk menjana fail HTML berdiri sendiri di akar repo.
Fail HTML itu (`app.html`, `sistem_tahanan.html`, `reman35_contoh.html`) adalah hasil
(output) — jangan edit terus kalau boleh; edit templat di sini dan bina semula.

## Kandungan

| Fail | Guna |
|------|------|
| `app.template.html` | Templat app IRINGKAWAL BPK 2026 (token `/*__SHEETJS__*/`, `/*__DEFAULT_DATA__*/[]`, `__DEVIN_AVATAR__`) |
| `sistem.template.html` | Templat Sistem Pengurusan Data Tahanan + Reman 35 (token `/*__SHEETJS__*/`, `__SEED__`, `__DEVIN_AVATAR__`) |
| `sheetjs.min.js` | Pustaka SheetJS (import/eksport Excel), dibenam ke dalam HTML |
| `data.json` | Data IRINGKAWAL (2115 baris, 15 kolum) untuk `app.html` |
| `seed.json` | Data sistem tahanan (2115 rekod) untuk `sistem_tahanan.html` |
| `devin_b64.txt` | Avatar Devin (data URI JPEG base64) |
| `build_app.py` | Bina `<repo>/app.html` |
| `build_sistem.py` | Bina `<repo>/sistem_tahanan.html` |
| `make_sample.py` | Bina `<repo>/reman35_contoh.html` (contoh borang) |

## Cara bina

Dari akar repo:

```bash
python src/build_app.py       # -> app.html
python src/build_sistem.py    # -> sistem_tahanan.html
python src/make_sample.py     # -> reman35_contoh.html  (jalankan selepas build_sistem)
```

Setiap output ialah satu fail HTML yang berdiri sendiri (data + SheetJS + avatar di-embed),
boleh dibuka terus dalam pelayar tanpa pelayan.
