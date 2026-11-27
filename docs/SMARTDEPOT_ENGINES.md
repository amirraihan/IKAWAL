# SmartDepot Engines — UC-2 / UC-3 / UC-4 on the real dataset

The Flask app (`app.py`) provides the web UI, storage, import/export and audit.
This package (`smartdepot/`) adds the **AI core** from the use-case document:
the automated reman engine, risk scoring, decision support, depot forecasting
and the monthly report generator.

It reads the **real register** `data/iringkawal_bpk2026.xlsx` directly.

## Data alignment

`smartdepot/constants.py` maps the register's columns to internal fields and keeps
the code lists (dropdowns) and risk weights in one place.

| Excel column | Internal field | Handling |
|--------------|----------------|----------|
| `TARIKH MASUK` | `tarikh_masuk` → `tarikh_reman_mula` | dd.mm.yyyy |
| `TARIKH TAMAT REMAN` | `tarikh_reman_tamat` | dd.mm.yyyy (single date) |
| `NAMA` | `nama` | masked for non-cleared roles |
| `JANTINA` | `jantina` | LELAKI / PEREMPUAN |
| `UMUR (THN)` | `umur_thn` | integer → age band |
| `BANGSA` | `bangsa` | spelling variants unified (VISAYA/BISAYA) |
| `WARGANEGARA` | `warganegara` | trimmed; ethnic names → nationality |
| `NO.REMAN` | `no_reman` | primary key; duplicates rejected |
| `DOKUMEN` | `dokumen` | |
| `NAMA PEGAWAI` | `nama_pegawai` | |
| `FAIL` (leading space) | `fail` | header whitespace trimmed |
| `DEPOT` | `depot` | DIKK / DIP (display: Kota Kinabalu / Papar) |
| `CATATAN` | `catatan` | masked; repeat-flag keywords read |
| `TINDAKAN` | `tindakan_kod` | USIR / +BLI / +RAI / BATAL PAS / BEBAS / BELUM MUKTAMAD |
| `KESALAHAN` | `akta` + `seksyen` | regex → Act group + clean section (e.g. `SEK 411 KK` → Kanun Keseksaan 411) |

Both the new layout (two single-date columns) and the legacy combined
`DD.MM.YYYY-DD.MM.YYYY` cell are supported.

## Merged into the Flask app

The two lines of work are now one system: the engines read the Flask app's
`records` table (SQLite `ikawal.db`) via `smartdepot/bridge.py`, and
`smartdepot/flask_api.py` registers a blueprint that `app.py` loads (guarded, so
the app still runs without the engine deps).

Start the app (`python app.py`) and open **<http://127.0.0.1:5000/engine>**.

| Endpoint | Purpose |
|----------|---------|
| `GET /engine` | small HTML page: KPIs, alerts, priority worklist, forecast |
| `GET /api/engine/summary` | KPIs + counts by risk / status |
| `GET /api/engine/alerts` | cases raising an alert (E5) |
| `GET /api/engine/worklist` | priority-ranked cases (E6/E7) |
| `GET /api/engine/forecast` | weekly intake forecast per depot (E8) |
| `POST /api/engine/decision` | log an officer accept/override (writes the app's audit log) |
| `GET /api/engine/report` | generate the monthly report (E9) |

The bridge maps the app's field names to the engine schema
(`nombor_reman`→`no_reman`, `pegawai`→`nama_pegawai`, `jenis_kesalahan`→`kesalahan`,
`umur`→`umur_thn`, `nombor_fail`→`fail`) and its depot display names back to codes
(Papar→DIP, Kota Kinabalu→DIKK).

### Surfaced inside the main dashboard

`/api/data` now attaches per-record engine fields (`risk_score`, `risk_label`,
`alert_tier`, `recommended_action`, `hari_berbaki`, …) and an `engine` panel
payload. Both front-ends use it:

- **Records table** — three new columns: **Risiko**, **Amaran**, **Cadangan (E7)**.
- **Engine panel** — a KPI tile row (Kritikal / Tinggi / Sederhana / Amaran) plus
  the top alerts, shown above the table on `templates/index.html` and `app.html`.
- **Forecast panel (UC-3)** — a weekly per-depot intake chart, fetched from
  `/api/engine/forecast` and rendered above the table.

The engines are optional: if the import fails, `/api/data` still returns records
and the panels stay hidden. The engine endpoints require a logged-in session
(`before_request` guard on the blueprint).

## Run it

```bash
pip install -r requirements.txt -r requirements-engines.txt

# rebuild the engine DB and load the real register through the cleaning pipeline
python scripts/cli.py ingest "data/iringkawal_bpk2026.xlsx"

# UC-2 alerts + UC-3 forecast
python scripts/run_daily.py

# UC-4 monthly report (XLSX / DOCX / HTML, + PDF if reportlab is installed)
python scripts/run_monthly.py --year 2026 --month 11

# UC-1 dashboard (Streamlit)
streamlit run app/streamlit_app.py
```

`python scripts/cli.py stats` prints case counts by depot, status and risk.

## What the engines do

- **E5 Reman engine** — `hari_berbaki` countdown, alert tiers (overdue / due today /
  1 day / 3 days), and pre-filled extension/outcome drafts (`reporting/drafts.py`).
- **E6 Risk scoring** — 0–100 with the weights in `constants.RISK_WEIGHTS`; labels
  Kritikal / Tinggi / Sederhana / Rendah with reasons. **Nationality and ethnicity
  are never scoring inputs.**
- **E7 Decision support** — one recommended action per case; officer accept/override,
  every override logged.
- **E8 Forecaster** — weekly new-reman intake per depot; moving-average baseline,
  plus SARIMA (`statsmodels`) and gradient boosting (`scikit-learn`) when available,
  chosen per depot by back-test MAPE.
- **E9 Reporting** — KPIs + narrative generated only from computed numbers (no
  names, no CATATAN), then XLSX / DOCX / HTML (+ PDF).

## Notes

- Storage is stdlib `sqlite3` (`data/smartdepot.db`); `app.py` uses `ikawal.db` —
  the two are independent and can be pointed at the same file via `SMARTDEPOT_DB`.
- `.local-backup/` holds the earlier local `README.md`, `requirements.txt` and
  `.gitignore` that were replaced when the repo was fetched.
