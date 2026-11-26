# IKAWAL

**Iringkawal Analyzer + Supervisor Dashboard — BPK 2026**

A monitoring & decision-support dashboard for remand cases (*reman*) / foreign
detainees (*banduan dagang*) at BPK.

## Two front-ends, one data source

| File | Description |
|------|-------------|
| `app.py` + `templates/` | **Python / Flask + SQLite** app. Server-side login & roles, SQLite database, Excel/CSV import (auto-clean), Excel/PDF export, audit log. |
| `app.html` | Single-file dashboard. **Wired to the Flask backend when served by it** (`/app`); falls back to browser `localStorage` when opened directly as a file. |
| `data/iringkawal_bpk2026.xlsx` | The working dataset (2,199 rows). Auto-imported into SQLite on first run. |
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

### Re-import the dataset
The database is created and seeded automatically on first run. To wipe the
records and re-import the bundled Excel file:

```powershell
python app.py import
```

---

## The dataset

`data/iringkawal_bpk2026.xlsx` — 2,199 rows × 15 columns (2,114 valid rows after
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
app.html                       # Single-file dashboard, wired to the API on /app
data/iringkawal_bpk2026.xlsx   # Bundled dataset (auto-imported)
requirements.txt               # Flask, openpyxl, reportlab
.vscode/launch.json            # Run/debug config for VS Code
ikawal.db                      # SQLite database (created on first run, git-ignored)
```

## Features

- **Login & roles** — staff / penyelia / boss with server-side sessions.
- **Dashboard** — KPI cards, alert banner, charts (Chart.js), 2,114 records.
- **Records** — search, filters, sort, add/edit/delete with validation.
- **Supervisor view** — officer workload ranking; click an officer to filter.
- **Auto-clean import** — upload `.xlsx`/`.csv`; headers auto-detected and values
  normalised (gender/age split, bangsa/warganegara split, "thn" removed, dates
  parsed, duplicates on the reman number & empty dates flagged).
- **Reports** — clean Excel export, PDF report by period, print, and a
  "sudah bebas" print list.
- **Audit log** — who did what, kept in SQLite (last 400 entries).

## API (JSON)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/me` | Current session/role |
| GET | `/api/data` | Records + stats + charts (params: `filter, q, officer, sort`) |
| POST | `/api/records` | Create record |
| PUT | `/api/records/<id>` | Update record |
| DELETE | `/api/records/<id>` | Delete record |
| DELETE | `/api/records` | Clear all |
| POST | `/api/sample` | Load 12 demo records |
| POST | `/api/import` | Upload Excel/CSV (form field `file`) |
| GET | `/api/export/xlsx` | Clean Excel download |
| GET | `/api/export/pdf?period=` | PDF report |
| GET/POST/DELETE | `/api/audit` | Audit log |

## How `app.html` is wired

When served from the Flask backend (`/app`), `app.html`:

- calls `GET /api/me` to detect the backend and current role,
- loads records from `GET /api/data`,
- saves through `POST/PUT/DELETE /api/records`, `POST /api/import`, etc.,
- uses the server for Excel/PDF export and the audit log.

If the backend is not reachable (for example, you just double-click the file), it
silently falls back to its original standalone `localStorage` behaviour.
