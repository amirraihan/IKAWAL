# Architecture decision

Decision and user outcome:

Build UC-2 (Case Decision Support) inside the scaffolded PCAI app at `smartdepot/`. An authenticated
officer opens the app and sees a live **priority worklist**: every reman case with its countdown
(days left), a 0-100 risk score, a priority label (Kritikal / Tinggi / Sederhana / Rendah) and one
recommended next action. The same facts are available to the chat through bounded read-only tools,
so an officer can ask "which cases are critical today?" and get a sourced answer.

Current code or platform evidence:

- `app/main.py` owns HTTP, settings, size limits and identity. `app/agent.py` owns the bounded
  LiteLLM tool loop. `app/static/` owns the browser UI (no build step, `script-src 'self'`).
- The loader must read `iringkawal_BPK_2026` Sheet1 (14 columns, 2,115 rows). Confirmed with the
  provided dummy file: ` FAIL` has a leading space, `TARIKH TAMAT REMAN` is a single `DD.MM.YYYY-DD.MM.YYYY`
  text cell, 256 blank `NO.REMAN`, two `NO.REMAN` duplicates, many `TINDAKAN` spellings.
- Runtime dependencies are pinned and hash-locked (`requirements.lock.txt`) and the image installs
  with `--require-hashes`. Adding pandas/openpyxl would force a lock regeneration and a heavier image.

Options considered and tradeoff:

1. pandas + openpyxl + pandera (per the design doc's pilot). Strong for cleaning, but it is a new
   runtime dependency that invalidates the hash lock and grows the image for a rule engine that only
   needs to read one sheet.
2. A stdlib `.xlsx` reader (`zipfile` + `xml.etree`) plus a small pure-Python rule engine. No new
   dependency, works inside the existing locked image, and is fully unit-testable with an in-memory
   workbook. Chosen.
3. Push the whole thing into the LLM. Rejected: the doc requires deterministic, explainable scores
   and officer approval; scoring must not depend on a model call.

Chosen interfaces and ownership:

- `app/xlsx.py` — minimal, read-only `.xlsx` reader (shared strings, inline strings, numbers). Owns
  file decoding only.
- `app/reman.py` — pure domain engine. Owns date parsing, tindakan normalisation, countdown,
  risk score, label, recommended action and name masking. No I/O, no model, no FastAPI.
- `app/store.py` — owns locating the workbook and turning rows into `Case` objects, with a small
  mtime-keyed cache.
- `app/main.py` — owns the HTTP boundary and JSON shapes (`/api/uc2/...`).
- `app/agent.py` — owns the model loop; exposes the worklist to the model as bounded read-only tools.
- `app/static/` — owns presentation of the worklist; renders untrusted text with `textContent`.

Main request/data flow:

`GET /api/uc2/cases` -> resolve workbook path -> read Sheet1 -> map rows -> derive countdown ->
score -> label -> recommended action -> sort by score -> JSON. The chat path loads the same cases
once per request and passes them to `execute_tool`, so model answers and the screen agree.

Failure and retry behavior:

- No workbook found -> HTTP 503 with a clear message; the UI shows an actionable hint. No crash.
- Invalid/blank date on a row -> the row is kept as `tidak sah`, excluded from scoring, and listed
  under data-quality issues. Other rows are unaffected.
- Gateway errors keep the existing behaviour; UC-2 endpoints never call the model.

Tenant identity and persistence implications:

UC-2 is read-only over a single shared register and holds no per-user state. Identity stays at
oauth2-proxy; the app reads only `x-forwarded-preferred-username` for display. No new persistence,
so no tenant key is introduced. Names are masked and `CATATAN` is never returned to the browser or
the model (only a boolean repeat flag derived from it).

Validation and remaining assumptions:

- Unit tests cover date parsing, both register shapes, tindakan normalisation, scoring, labels,
  actions, masking and the `.xlsx` reader; API tests cover summary/worklist/case and the missing-file path.
- Assumption: the workbook is reachable at a configured path (env `APP_REMAN_FILE`, else `data/`,
  `app/data/`, `.local/`, or the shared repo `../data/`). By default UC-2 reads the same
  `data/iringkawal_bpk2026.xlsx` the Flask app uses. The deployed image does not yet ship the file;
  an operator supplies it. This is listed as outstanding.
- Assumption: capacity-based `+5` factor stays off until a depot capacity table exists (doc section 2.4).
