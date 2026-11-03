# Polish findings (2026-11-02)

The assignment's review prompt, run against the whole code base. Earlier reviews (`code-quality-review.md`, `security-review.md`) had already led to most of the error handling work, so the remaining list is short.

| # | Category | Where | Finding | Action | Status |
|---|---|---|---|---|---|
| 1 | Missing error handling | `.github/workflows/release.yaml` | A release could be built and published without the Python tests having run (only card tests ran) | Add a `test` job (ruff, mypy, pytest) that the release job `needs` | Fixed |
| 2 | Edge case | `.github/workflows/release.yaml` | Any tag, also on a side branch, would publish a release | Check that the tagged commit is an ancestor of `origin/main`, else fail with a clear message | Fixed |
| 3 | Unclear error message | `frontend/src/items.ts:86` | Swedish users saw the English text "No connection to Home Assistant" | Translate it through `i18n.ts` (`error.no_connection`, sv and en) and update the tests | Fixed |
| 4 | Documentation | `README.md`, `README.sv.md` | No architecture, stack, limitations or license sections, no CI badge | Follow the course README template | Fixed |
| 5 | Documentation | repository root | No `LICENSE`; HACS validation requires one | Add MIT license | Fixed |
| 6 | Hard-coded values | `const.py` (`LISTS_CHANGED_TIMEOUT`, `USAGE_SAVE_DELAY`, `QUICK_ADD_LIMIT`) | Named constants, but not configurable by users | Left as is on purpose: they are tuning values and each option adds UI and tests | Open |
| 7 | Missing error handling | `frontend/src/items.ts` (unsubscribe) | Errors on closing the subscription are ignored | Left as is: the connection is already closed, documented in the code | Open |

Checked and found fine: service schemas cap the length of every text field, the AI input is capped (`MAX_TEXT_LENGTH`), all `entries[0]`/`services[0]` accesses are guarded, no bare `except`. Secrets: see [secrets-check.md](secrets-check.md).
