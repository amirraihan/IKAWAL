# Release record

Release name / namespace / authorized context:

`smartdepot` UC-2 (Case Decision Support) — local development build. No cluster release was created
or changed. Target namespace and Keycloak client are still to be confirmed by the platform owner.

Image tag and digest / chart version:

Not built. Chart is the scaffold default (`deploy/chart`, version 0.1.0).

Operator / date:

OpenCode agent session, 2026-11-26.

| Check | Evidence and result |
|---|---|
| App and tool tests | `python -m pytest tests` → 28 passed. The one failure (`test_workshop.py`) is pre-existing and environmental: masked secret input needs a real console, which this shell is not. UC-2 is covered by `tests/test_reman.py` (15 tests). |
| Chart validation and rendered route | Not run this pass: `scripts/validate.py` needs Helm 3 and `requirements-dev.txt` (jsonschema, PyYAML). Chart files unchanged. |
| Registry pull and pod rollout | Not attempted. |
| Anonymous login redirect | Not attempted (needs the deployed gateway). |
| Allowed group access | Not attempted. |
| Denied group access | Not attempted. |
| Private backend network boundary | Chart unchanged; NetworkPolicy still routes only via the auth service. |
| Real LiteLLM answer and report tools | Not exercised: no LiteLLM key was configured. UC-2 endpoints and the worklist were verified locally in the browser (Chromium) with no console errors. Chat tools verified with a mock gateway in `tests/test_app.py`. |
| Downloaded Markdown contents | Chat download unchanged; not re-verified against a live model. |
| Local UC-2 user flow | Browser against the shared dataset `data/iringkawal_bpk2026.xlsx`: worklist rendered 4 open cases (all Tinggi), label filter narrowed the set, depot filter options populated, case detail masked, 404/422 handled, `/api/uc2/*` all 200, no console errors. |
| Upgrade/rollback | Not attempted. |

Secret or Keycloak changes outside Helm:

None. No key was printed, stored or embedded. `.local/` was not modified.

Known gaps / owner / next action:

- UC-2 reads the same register as the Flask app (`data/iringkawal_bpk2026.xlsx`, 2,199 rows x 15 cols).
  The deployed PCAI image copies only `app/` and `certs/`, so an operator must supply the file at
  runtime (`APP_REMAN_FILE` or a mounted `data/` volume). Owner: platform operator + BPK data owner.
  Next action: decide the runtime data path and whether the workbook is baked into the image or mounted.
- Risk weights, labels and the action list are section 5.2/5.3 proposals awaiting sign-off by the
  depot head and legal unit (document open questions 3 and 4).
- Capacity-based `+5` factor is inactive until a depot capacity table exists (document section 2.4).
