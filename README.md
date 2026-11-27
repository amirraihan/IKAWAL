# IKAWAL

**Iringkawal Analyzer + Supervisor Dashboard — BPK 2026**

A monitoring & decision-support dashboard for remand cases (*reman*) / foreign
detainees (*banduan dagang*) at BPK.

## Two front-ends, one data source

| File | Description |
|------|-------------|
| `app.py` + `templates/` | **Python / Flask + SQLite** app. Server-side login & roles, SQLite database, Excel/CSV import (auto-clean), PDF export, audit log. Served at `/` and `/login`. |
| `app.html` | **IRINGKAWAL BPK 2026** — standalone single-file app: 3-role login (Admin / Penyelia / Pegawai), bundled 2,115-row dataset, add / edit / delete, Excel upload, custom *Laporan PDF*, and the local **Devin** assistant. Open the file directly — no server needed. |
| `sistem_tahanan.html` | **Sistem Pengurusan Data Tahanan + Auto Cetak Reman 35** — daily data entry, list / filter / import, and the Section 35 notice print (A4, 100% English), plus the **Devin** assistant. Standalone. |
| `reman35_contoh.html` | Sample preview of the Reman 35 print form. |
| `devin.png` | Devin assistant avatar. |
| `data/iringkawal_bpk2026.xlsx` | Bundled dataset (2,115 rows). Load it with `python app.py import`, or upload your own Excel/CSV. |
| `Ikawal_usecase_pipeline_v3.html` | Use cases & pipeline document (SmartDepot concept). |

---

## Running the Python (Flask) app in Visual Studio Code

### 1. Open the folder in VS Code
`File → Open Folder…` → select this project.

### 2. Create a virtual environment (recommended)
Open the terminal (`` Ctrl+` ``):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # PowerShell
# macOS / Linux: source .venv/bin/activate
```

### 3. Install dependencies
```powershell
python -m pip install -r requirements.txt
```

### 4. Run the app
Press **F5** (uses `.vscode/launch.json` → *"Python: Iringkawal (Flask)"*), or:

```powershell
python app.py
```

| Page | URL | Notes |
|------|-----|-------|
| Flask dashboard | <http://127.0.0.1:5000/> | Server-rendered UI (`templates/index.html`) |
| **app.html wired to the backend** | <http://127.0.0.1:5000/app> | The single-file dashboard, reading/writing the SQLite data |
| Login | <http://127.0.0.1:5000/login> | |

### Demo logins

| Role | Password | Access |
|------|----------|--------|
| 🧑‍💼 Staff Iringkawal | `staff2026` | Upload, add, edit, delete, export |
| 👁️ Penyelia | `penyelia2026` | Edit & export only |
| 🧑‍✈️ Boss | `boss2026` | View & export only |

Change the passwords/secret with environment variables:
`IKAWAL_PW_STAFF`, `IKAWAL_PW_PENYELIA`, `IKAWAL_PW_BOSS`, `IKAWAL_SECRET`.

### Loading data
The database starts **empty** — the dashboard shows *"Sila Upload Excel"* until a
file is uploaded with **Upload Excel / CSV**. To load the bundled dataset instead
(or to wipe and re-import it):

```powershell
python app.py import
```

---

## The dataset

`data/iringkawal_bpk2026.xlsx` — 2,115 rows × 15 columns (2,114 valid rows after
the auto-clean drops blank rows). Original columns and how they map:

| Excel column | App field | Notes |
|--------------|-----------|-------|
| TARIKH MASUK | `tarikh_masuk` | `dd.mm.yyyy` → ISO |
| TARIKH TAMAT REMAN | `tarikh_tamat_reman` | `dd.mm.yyyy` → ISO |
| NAMA | `nama` | |
| JANTINA | `jantina` | LELAKI/PEREMPUAN → Lelaki/Perempuan |
| UMUR (THN) | `umur` | |
| BANGSA | `bangsa` | |
| WARGANEGARA | `warganegara` | |
| NO.REMAN | `nombor_reman` | used as the duplicate-detection key |
| DOKUMEN | `dokumen` | |
| NAMA PEGAWAI | `pegawai` | |
| FAIL | `nombor_fail` | a repeating batch number, not unique |
| DEPOT | `depot` | **DIP → Papar**, **DIKK → Kota Kinabalu** |
| CATATAN | `catatan` | |
| TINDAKAN | `tindakan` | USIR → "Usir", BEBAS → "Bebas", … |
| KESALAHAN | `jenis_kesalahan` | |

The header row is detected automatically (within the first 12 rows) and columns
are matched by keyword, so slightly different headings still import correctly.

> **Note on "Reman Tamat < 3 Hari":** this counts records whose reman end date is
> within 3 days **or already in the past**. Because the dataset runs Jan–Dec 2026
> and the current date is late 2026, most rows show as past/ending, so that KPI
> is high. It is driven by the real dates, not a bug.

---

## Project structure

```
app.py                         # Flask backend + SQLite + auto-clean + reports
templates/index.html           # Server dashboard (calls the JSON API)
templates/login.html           # Server login page
app.html                       # IRINGKAWAL BPK 2026 (standalone; login + AI + Devin)
sistem_tahanan.html            # Data tahanan + Reman 35 print (standalone)
reman35_contoh.html            # Sample Reman 35 print preview
devin.png                      # Devin assistant avatar
src/                           # Build sources for the standalone HTML apps
src/build_app.py               #   -> app.html
src/build_sistem.py            #   -> sistem_tahanan.html
src/make_sample.py             #   -> reman35_contoh.html
data/iringkawal_bpk2026.xlsx   # Bundled dataset (manual import)
requirements.txt               # Flask, openpyxl, reportlab
.vscode/launch.json            # Run/debug config for VS Code
ikawal.db                      # SQLite database (created on first run, git-ignored)
```

## Features

- **Login & roles** — staff / penyelia / boss with server-side sessions.
- **Dashboard** — starts empty; after an upload it shows the KPI cards, alert
  banner, charts (Chart.js), records table and officer workload.
- **Records** — search, filters, sort, add/edit/delete with validation.
- **Supervisor view** — officer workload ranking; click an officer to filter.
- **Auto-clean import** — upload `.xlsx`/`.csv`; headers auto-detected and values
  normalised (gender/age split, bangsa/warganegara split, "thn" removed, dates
  parsed, duplicates on the reman number & empty dates flagged).
- **Reports** — PDF report by period and a "sudah bebas" print list.
- **Laporan PDF (custom report)** — available to **all roles** (Staff, Penyelia,
  Boss). Pick any combination of Depot, Warganegara, Jenis Kesalahan, Jantina,
  Bangsa, Pegawai, Tarikh Masuk (month range) and Status; the count, summary
  tables (by Warganegara & Jenis Kesalahan) and mini charts update live, then
  **Pratonton Laporan** or **Cetak / Simpan PDF** produce a report containing
  only the filtered rows.
- **Audit log** — who did what, kept in SQLite (last 400 entries).

## API (JSON)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/me` | Current session/role |
| GET | `/api/data` | Records + stats + charts (params: `filter, q, officer, sort`) |
| GET | `/api/options` | Distinct filter options for the custom report |
| POST | `/api/records` | Create record |
| PUT | `/api/records/<id>` | Update record |
| DELETE | `/api/records/<id>` | Delete record |
| DELETE | `/api/records` | Clear all |
| POST | `/api/import` | Upload Excel/CSV (form field `file`) |
| GET | `/api/export/pdf?period=` | PDF report |
| GET | `/api/export/pdf/custom` | PDF report by custom filters (all roles) |
| GET/POST/DELETE | `/api/audit` | Audit log |

## The single-file apps (no server needed)

`app.html` and `sistem_tahanan.html` are **fully standalone**: open them directly in a
browser (double-click) — no Flask required. Each embeds its own dataset, the SheetJS
Excel engine and the Devin avatar, and saves changes in the browser (`localStorage`).

Rebuild them from source after editing a template:

```powershell
python src/build_app.py       # -> app.html
python src/build_sistem.py    # -> sistem_tahanan.html
python src/make_sample.py     # -> reman35_contoh.html
```

## Flask backend

`app.py` + `templates/` still provide the server-rendered dashboard (`/`), login
(`/login`), the JSON API (`/api/...`) and the SQLite store. It is independent of the
standalone HTML apps above.
