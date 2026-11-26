# IKAWAL

**Iringkawal Analyzer + Supervisor Dashboard — BPK 2026**

A monitoring & decision-support dashboard for remand cases (*reman*) / foreign
detainees (*banduan dagang*) at BPK. The project ships in two equivalent forms:

| File | Description |
|------|-------------|
| `app.html` | Single-file, browser-only version. Data is stored in the browser (`localStorage`). Just open it in a browser. |
| `app.py` + `templates/` | **Python version** — a full Flask + SQLite web app with a real database, server-side login/roles, Excel/CSV import (auto-clean), Excel/PDF export, and an audit log. |
| `Ikawal_usecase_pipeline_v3.html` | Use cases & pipeline document (SmartDepot concept). |

Both versions share the same look, features and demo data:
login roles, KPI cards, charts, officer workload, filters/CRUD, auto-clean
import, audit log and Excel/PDF/print reports.

---

## Running the Python (Flask) app in Visual Studio Code

### 1. Open the folder in VS Code
`File → Open Folder…` → select this project.

### 2. Create a virtual environment (recommended)
Open the terminal (`` Ctrl+` ``) and run:

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
Either press **F5** (uses `.vscode/launch.json` → *"Python: Iringkawal (Flask)"*),
or run:

```powershell
python app.py
```

Then open <http://127.0.0.1:5000> in a browser.

### Demo logins

| Role | Password | Access |
|------|----------|--------|
| 🧑‍💼 Staff Iringkawal | `staff2026` | Upload, add, edit, delete, export |
| 👁️ Penyelia | `penyelia2026` | Edit & export only |
| 🧑‍✈️ Boss | `boss2026` | View & export only |

Change the passwords/secret with environment variables:
`IKAWAL_PW_STAFF`, `IKAWAL_PW_PENYELIA`, `IKAWAL_PW_BOSS`, `IKAWAL_SECRET`.

---

## Project structure

```
app.py                         # Flask backend + SQLite + auto-clean + reports
templates/index.html           # Dashboard (calls the JSON API)
templates/login.html           # Server-side login page
requirements.txt               # Flask, openpyxl, reportlab
.vscode/launch.json            # Run/debug config for VS Code
app.html                       # Original single-file browser version
Ikawal_usecase_pipeline_v3.html
ikawal.db                      # SQLite database (created on first run)
```

## Features

- **Login & roles** — staff / penyelia / boss with server-side sessions.
- **Dashboard** — KPI cards, alert banner for reman ending within 3 days, charts (Chart.js).
- **Records** — search, filters, sort, add/edit/delete with validation.
- **Supervisor view** — officer workload ranking; click an officer to filter.
- **Auto-clean import** — upload `.xlsx`/`.csv`; headers are auto-detected and
  values normalised (gender/age split, bangsa/warganegara split, "thn" removed,
  dates parsed, duplicates & empty dates flagged).
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
| GET/DELETE | `/api/audit` | Audit log |

## Notes

- Data persists in `ikawal.db` (SQLite) — back up that file to back up your data.
- The app works without internet; Chart.js is loaded from a CDN, so charts need
  a connection (tables and reports still work offline).
