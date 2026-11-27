# Feature brief

User and problem:

A reman (remand) officer / depot head / investigating officer must decide, every day, which foreign
detainee cases need action first. Today reman end dates are watched by eye in a long Excel sheet and
there is no consistent priority. UC-2 gives each case an automated countdown, a risk score with
reasons, and one recommended next action.

User action and expected result:

Open the app and view the **Priority worklist**: cases sorted by risk score, each showing days left,
status (aktif / tamat hari ini / tertunggak / selesai), priority label (Kritikal / Tinggi / Sederhana /
Rendah), the reasons for the score, and a recommended action. Filter by label, depot or officer.
Optionally ask the chat "Which cases are critical today?" and get the same list with tool trace.

Inputs, outputs and saved data:

- Input: the reman register workbook (`iringkawal_BPK_2026`, Sheet1, 14 columns), located by
  `APP_REMAN_FILE` or a search path. Read-only.
- Derived: `tarikh_reman_mula/tamat`, `tempoh_reman`, `hari_berbaki`, `status_reman`, normalised
  `tindakan_kod`, age band, repeat flag, risk `score`, `label`, `action`, `reasons`.
- Output: JSON from `/api/uc2/summary`, `/api/uc2/cases`, `/api/uc2/case/{no_reman}` and the on-screen
  worklist. Nothing is saved or written back.

Identity and access boundaries:

No change to login: oauth2-proxy still owns identity; the app stays private behind NetworkPolicy.
The app only reads the display name header. `NAMA` is masked and `CATATAN` is never returned.

Model and tool capabilities required:

Two read-only tools for tool-capable models (DeepSeek, Qwen2.5): `reman_summary` and
`list_priority_cases`, plus `get_case`. They return masked, bounded results. Models without tool
support simply do not see them. No tool can mutate data or run commands.

Acceptance example:

`GET /api/uc2/cases?label=Kritikal` returns cases with `score >= 60`, a non-final `tindakan`, and an
`action` of "Act today...". `GET /api/uc2/summary` reports counts by label and the overdue / due-today
tallies. With no workbook configured, both return 503 with a hint to set `APP_REMAN_FILE`.

Out of scope:

UC-1 dashboard pages, UC-3 forecasting, UC-4 reports, persistence/database, scheduled jobs, alerts,
paperwork generation, and ML scoring (v2). Decision support here is rule-based v1 only.
