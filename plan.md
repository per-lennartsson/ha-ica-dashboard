# Implementation plan: Inköp

Tracking file. Development and automated verification need **no running Home Assistant**: Python tests use `pytest-homeassistant-custom-component` (in-process HA core) with mocked ICA/AI, and card tests use Vitest + jsdom plus a mock-data dev page. A real HA (the maintainer's own HA OS, installed via HACS, throwaway lists only) is used only for steps marked **Manual (real HA)**.

 Tick `[x]` when a step is done **and** its verification has passed. One step = one feature branch/PR. Do not start a step before the previous one is verified. Nothing is implemented until the maintainer approves this plan.

Legend: **Verify** = how we know the step is done. Effort: S (<½ day), M (~1 day), L (2–3 days).

---

## Phase 0: Foundation

### 0.1 Confirm the ha-ica-todo contract (S)
- [x] Read the `per-lennartsson/ha-ica-todo` repo: current version, `manifest.json`, services (fields and responses), entity naming, events, install via HACS.
- [x] Write findings to `docs/ica-contract.md` (versions, service signatures, entity ID patterns, known limits).
- [x] List any needed changes to ha-ica-todo as ready-to-use prompts for the maintainer to implement (we never patch that repo).
- **Verify:** the contract doc matches the repo; every ICA call planned later appears in it.

### 0.2 Repo skeleton and tooling (M)
- [x] `custom_components/inkop/` with `manifest.json` (declares `ha-ica-todo`), `__init__.py`, `const.py`; `hacs.json`; `.env.example`; `requirements_dev.txt`.
- [x] Ruff, mypy, pytest (`pytest-homeassistant-custom-component`) configured, with shared fixtures: fake ICA `todo` entities and mocked `ica.*` services.
- [x] Update CLAUDE.md `Setup`/`Test` TODOs with real commands.
- **Verify:** `ruff check . && mypy custom_components && pytest tests/ -v` run green (with one smoke test).

### 0.3 CI (S)
- [x] GitHub Actions (`.github/workflows/ci.yaml`): lint, mypy, pytest, hassfest, HACS validation. Workflow written and YAML-checked locally; **a green run on a PR is still to be confirmed** (see Verify).
- **Verify:** workflow is green on a PR; a deliberately broken lint fails it.

### 0.4 Manual test setup on the maintainer's own HA (S)
- [x] `docs/dev.md`: how to install a branch/release of `inkop` via HACS custom repository on the own HA OS, ha-ica-todo already installed, rules for throwaway ICA lists and cleanup. (Optional: Docker HA instance, not required.)
- [x] Update CLAUDE.md `Run` section.
- [x] Minimal config flow (single instance, creates the entry; `strings.json`, sv/en translations, tests) so `inkop` can be added from the UI without editing YAML. Dependency checks stay in step 1.2.
- [x] **Verify:** `inkop` installs on the real HA, is added via *Add integration → Inköp* and works (confirmed by the maintainer).

---

## Phase 1: Core (no AI)

### 1.1 Pure domain logic (M)
- [x] `domain/` package: item text parsing and formatting (quantity, unit, name per the ICA rules), case-insensitive duplicate detection, default list name ("Att handla <dag> <månad>", "(2)", "(3)").
- [x] Unit tests including: comma decimals, ranges "2–3", whole-word units, Swedish month/day names, name collisions.
- **Verify (done):** 78 tests pass; `domain/` coverage 100% (`pytest --cov=custom_components/inkop/domain`); an AST test checks that `domain/` never imports Home Assistant. Parser checked against ha-ica-todo's regex on 27 inputs: identical except bare `12` / `1,5`, which ha-ica-todo splits into quantity 1 + name `2` / `,5` (bug; inkop keeps them as plain names).
- Decisions: a duplicate is a same normalized name (case and whitespace-insensitive), quantity and unit ignored, no plural matching. Default list name is "Att handla <dagens datum> <månad>", e.g. "Att handla 14 oktober" (day of month, not weekday).

### 1.2 Config flow and dependency check (M)
- [x] Config flow: single instance; aborts with clear Swedish/English message if `ha-ica-todo` is missing, not set up, not loaded, or below the minimum version (`v0.10.0`, see `docs/ica-contract.md`). Pure version comparison in `domain/versions.py`, I/O check in `dependency.py`.
- [x] Setup re-checks the dependency; if unusable it raises a repair issue and retries (`ConfigEntryNotReady`); the issue clears when ICA is usable again or the entry is removed. **Not monitored while running** on purpose: ha-ica-todo reloads on every list create/delete, which must not look like a problem (step 1.3 handles that as a busy state).
- **Verify (automated, done):** 126 tests pass, 100% coverage of `custom_components/inkop`; tests cover missing, too old (incl. unparseable version), not configured, not loaded, OK, repair issue create/update/clear, recovery on retry, and translation keys/placeholders (sv/en/strings.json checked consistent).
- **Verify (Manual, real HA, not yet done):** add the integration with ha-ica-todo present (works), and with it disabled or removed (clear message in Swedish/English; repair issue after restart).

### 1.3 Coordinator and list management services (L)
- [x] Coordinator reading ICA `todo` entities.
- [x] Services: `inkop.set_active_list`, `inkop.create_list` (prefilled name, wraps `ica.create_shopping_list`), `inkop.delete_list` (wraps `ica.delete_shopping_list`).
- [x] Handle the 4–5 s integration reload: busy state until the `ica_lists_changed` event (v0.10.0), with a timeout as a safety net. A missing entity in the event means failure. Use the `offline_id` entity attribute, not registry parsing. Use events/coordinator, not templates.
- [x] Entities: active-list select, item-count sensor, busy/status sensor.
- **Verify (automated, done):** 184 tests pass, 100% coverage of `custom_components/inkop`. Covered: create/delete success, default and numbered names, event arriving before or after the service returns, lower/upper-case ids, timeout, event without entity (failed reload), ICA error, ICA not loaded, busy refusal, status transitions, active list default/persistence/fallback, favourites ignored, list kept while ICA reloads, translations consistent.
- **Verify (Manual, real HA, the main risk check, not yet done):** follow "Manual check: lists" in `docs/dev.md` with throwaway lists, record the reload time, clean up.
- Decisions: (1) the active list is shared by the household and lives in the integration (select + `inkop.set_active_list`, saved across restarts); a user's own choice in the card stays in the browser (1.8). (2) With several ICA accounts the first loaded one is used. (3) Wait for `ica_lists_changed` at most 30 s (`LISTS_CHANGED_TIMEOUT`); a missing entity in the event counts as failure. (4) One create/delete at a time; a second call is refused (`busy`). (5) Entities: `select` active list, `sensor` items to buy (open items on the active list), `sensor` status (idle/creating/deleting/error). (6) Service schemas use `probatio` when available (Home Assistant 2026.10+) and fall back to `voluptuous`.

### 1.4 Add, duplicate check, remove, clear (L)
- [ ] Services: `inkop.add_item` (returns duplicate info instead of adding when `confirm_duplicate` is false), `inkop.remove_item`, `inkop.tick_item`, `inkop.clear_ticked`.
- [ ] Text goes in service data (never state; 255-char limit).
- **Verify:** tests for add, duplicate flow (case-insensitive), remove, tick, clear; manual round-trip against the throwaway list in the ICA app.

### 1.5 Usage statistics and quick-add (M)
- [ ] Persist per-item add counts (HA `Store`); service/sensor exposes the top N items.
- **Verify:** tests for counting and ranking; a test reloads the entry and counts persist; Manual (real HA): counts survive an HA restart.

### 1.6 Notifications (M)
- [ ] Options flow: choose users/notify targets.
- [ ] Use HA service call context (user ID) to know who added items; notify the others only. No heuristics.
- [ ] Optionally also react to `ica_list_items_changed` for changes made outside HA (e.g. in the ICA app), without notifying twice for changes `inkop` made itself. The event carries no user.
- [ ] Fire an `inkop_item_added` event with the user ID.
- **Verify:** tests with mocked context for own vs. others' additions; Manual (real HA): two HA users.

### 1.7 Frontend card scaffold (M)
- [ ] `frontend/` with Lit, TypeScript, Vite, Vitest, ESLint/Prettier; build output served as a Lovelace resource; CI builds and tests it.
- [ ] i18n setup (sv default, en).
- **Verify:** `npm test` and `npm run build` pass; a "hello" card renders in the mock-data dev page (Vite) in a browser; Manual (real HA): it loads as a Lovelace resource.

### 1.8 Card: list picker, create, delete (M)
- [ ] Select the active list, create (prefilled name), delete with confirmation, progress indicator and disabled buttons during busy state.
- [ ] Per-user UI state in browser storage, not helpers.
- [ ] Clear message when ha-ica-todo is missing.
- **Verify:** component tests; mock-data dev page for visual checks; Manual (real HA): on the phone/companion app: no double taps possible during reload.

### 1.9 Card: items view (L)
- [ ] Free-text input (Enter adds and keeps focus), item list with tick/remove, clear ticked, duplicate prompt "finns redan – lägga till igen?", quick-add buttons with icons.
- **Verify:** component tests for each interaction; manual on a phone including keyboard behaviour.

### 1.10 Mobile shortcut (S)
- [ ] Compact card/badge on the mobile dashboard showing the item count and opening the shopping view.
- **Verify:** works on a phone in the companion app; count updates live.

### 1.11 Core release (M)
- [ ] README (sv/en): install via HACS (both ha-ica-todo and inkop), configuration, screenshots.
- [ ] Release workflow: tag, build card, attach assets, version bump.
- **Verify:** install from the tagged release via HACS custom repository on the own HA (HACS custom repository); run the core feature checklist (features 1–6) end-to-end.

**Phase 1 done when:** features 1–6 work on a phone with only HA + ha-ica-todo, CI is green, a tagged release installs via HACS, and no AI code or UI is present.

---

## Phase 2: Optional AI module

### 2.1 Enable switch and provider selection (M)
- [ ] Add a mocked `ai_task` entity fixture to `tests/conftest.py` (dev environment now has HA 2026.10.1, which includes `ai_task`).
- [ ] Options flow: AI off by default; when on, choose an `ai_task` entity; validate it exists.
- [ ] Expose AI-enabled state so the card can hide all AI UI when off.
- **Verify:** tests for off (no services registered, no UI) and on; Manual (real HA): toggle in the options flow.

### 2.2 Extraction service (L)
- [ ] `inkop.ai_extract_items`: pasted text in service data → structured output (short Swedish names, quantity first, merged duplicates, staples skipped).
- [ ] Prompt and JSON schema in version control; set `max_tokens` explicitly so long lists aren't truncated (note: Anthropic-specific).
- [ ] Mark items already on the list.
- **Verify:** tests with mocked `ai_task` against fixture inputs (recipe, meal plan, message, very long text); prompt reviewed with real provider on a few samples.

### 2.3 Card: paste, review, add (L)
- [ ] Paste box, review list (edit, untick, already-on-list marked and unticked), add selected; failed items stay for retry.
- [ ] Hidden entirely when AI is off or no provider.
- **Verify:** component tests incl. partial failure and retry; manual with a real provider.

### 2.4 Provider monitoring (M)
- [ ] Push notification on provider failure (e.g. credits exhausted), de-duplicated.
- [ ] Optional daily health check (tiny `ai_task` call) toggled in the options flow.
- **Verify:** tests simulating provider errors; manual by pointing at an invalid key or disabled entity.

### 2.5 AI release (S)
- [ ] Docs for AI setup (any provider, Anthropic notes: `max_tokens`, no balance API).
- **Verify:** clean install with AI off shows no AI UI; with AI on, features 7–10 work end-to-end; tagged release.

**Phase 2 done when:** features 7–10 work, AI off equals Phase 1 behaviour exactly, CI is green, release tagged.

---

## Definition of done (every step)
- Code, tests and docs merged via PR from a feature branch; CI green.
- Verification listed for the step has been run and recorded (note result under the step).
- No secrets in git; no changes made directly to ha-ica-todo.
- CLAUDE.md and this plan updated if conventions or scope changed.

## Risks and open questions
- ICA API or ha-ica-todo changes may break services: pin a minimum version, test against mocks, keep `docs/ica-contract.md` current.
- Integration reload after create/delete may race with follow-up calls: mitigated by the `ica_lists_changed` event (v0.10.0), but still needs a busy state and timeout (1.3). New ha-ica-todo code (events, attributes) has only helper-level tests so far; first real check is 1.3 on the own HA.
- Quantity/unit edge cases around renaming (ICA ignores a null unit): document as limitation.
- Dev environment runs Home Assistant 2026.10.1 while production is 2026.9.x (e.g. service schemas moved from `voluptuous` to `probatio`; handled with a fallback). Consider pinning the dev environment to the production version, or testing both.
- Open: confirm Vitest as frontend test tool; decide whether to commit `frontend/dist` for HACS or attach it to releases; final usage-statistics source (own counts only, or also ICA history).

## Progress log
| Date | Step | Result |
|------|------|--------|
| 2026-10-13 | 0.1 (update) | ha-ica-todo changes made on branch `list-events-and-metadata` (`c2fe1f1`, v0.10.0): `ica_lists_changed`, `ica_list_items_changed`, list entity attributes, fork metadata. Contract and plan updated; minimum version now `>= v0.10.0`. Review notes: event fires also on reload failure; item-change event has no user; removed fields not reported. |
| 2026-10-13 | env | Upgraded dev env to Python 3.14.8 (Homebrew) and HA 2026.10.1 / pytest-homeassistant-custom-component 0.13.372. Checks green. `ai_task` is now testable. |
| 2026-10-14 | 1.3 | Lists implemented: coordinator, `inkop.create_list` / `delete_list` / `set_active_list`, select + 2 sensors; 184 tests, 100% coverage. Manual check on the real HA (reload time!) pending. |
| 2026-10-14 | 1.2 | Dependency check implemented (flow + setup + repair issue), 126 tests green. Manual check on the real HA pending. |
| 2026-10-14 | 1.1 | Domain logic done: `domain/items.py`, `duplicates.py`, `naming.py`; 78 tests, 100% coverage of `domain/`. |
| 2026-10-14 | 0.4 | Manual verification on the real HA: `inkop` installed and worked. Docs and minimal config flow merged (`7a33bf1`). |
| 2026-10-13 | 0.2 | Skeleton + tooling done. ruff, mypy and 2 smoke tests green. Dev env: Python 3.13.1 resolves HA 2025.4.4 (not 2026.9); `ai_task` (2025.8+) cannot be tested until Python/HA is upgraded. Node only via Docker. |
| 2026-10-13 | 0.1 | Contract written from ha-ica-todo `main` @ `6c45aa7` (v0.9.0). Brief confirmed except: `create_shopping_list` needs `integration`; no item-change event; create/delete return before reload completes. Possible ha-ica-todo changes identified, none blocking. |
