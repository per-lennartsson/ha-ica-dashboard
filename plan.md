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
- [ ] GitHub Actions: lint, mypy, pytest, hassfest, HACS validation.
- **Verify:** workflow is green on a PR; a deliberately broken lint fails it.

### 0.4 Manual test setup on the maintainer's own HA (S)
- [ ] `docs/dev.md`: how to install a branch/release of `inkop` via HACS custom repository on the own HA OS, ha-ica-todo already installed, rules for throwaway ICA lists and cleanup. (Optional: Docker HA instance, not required.)
- [ ] Update CLAUDE.md `Run` section.
- **Verify:** `inkop` installs from a branch via HACS on the real HA, appears as an integration, and no errors show in the log.

---

## Phase 1: Core (no AI)

### 1.1 Pure domain logic (M)
- [ ] `domain/` package: item text parsing and formatting (quantity, unit, name per the ICA rules), case-insensitive duplicate detection, default list name ("Att handla <dag> <månad>", "(2)", "(3)").
- [ ] Unit tests including: comma decimals, ranges "2–3", whole-word units, Swedish month/day names, name collisions.
- **Verify:** unit tests pass with no HA dependency; coverage of `domain/` ≥ 90%.

### 1.2 Config flow and dependency check (M)
- [ ] Config flow: single instance; aborts with clear Swedish/English message if `ha-ica-todo` is missing, not loaded, or below the minimum version.
- [ ] Setup re-checks the dependency and raises a repair issue if it disappears.
- **Verify:** flow tests for missing, too old, and OK; Manual (real HA): add the integration with ha-ica-todo present, and (if practical) with it disabled.

### 1.3 Coordinator and list management services (L)
- [ ] Coordinator reading ICA `todo` entities.
- [ ] Services: `inkop.set_active_list`, `inkop.create_list` (prefilled name, wraps `ica.create_shopping_list`), `inkop.delete_list` (wraps `ica.delete_shopping_list`).
- [ ] Handle the 4–5 s integration reload: busy state, retry/wait on entity availability (use events/coordinator, not templates).
- [ ] Entities: active-list select, item-count sensor, busy/status sensor.
- **Verify:** tests with mocked ICA services; Manual (real HA, the main risk check): create and delete a throwaway list and see the busy state clear. Throwaway lists cleaned up.

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
- Integration reload after create/delete may race with follow-up calls: needs a robust busy/wait design (1.3).
- Quantity/unit edge cases around renaming (ICA ignores a null unit): document as limitation.
- Open: confirm Vitest as frontend test tool; decide whether to commit `frontend/dist` for HACS or attach it to releases; final usage-statistics source (own counts only, or also ICA history).

## Progress log
| Date | Step | Result |
|------|------|--------|
| 2026-10-13 | env | Upgraded dev env to Python 3.14.8 (Homebrew) and HA 2026.10.1 / pytest-homeassistant-custom-component 0.13.372. Checks green. `ai_task` is now testable. |
| 2026-10-13 | 0.2 | Skeleton + tooling done. ruff, mypy and 2 smoke tests green. Dev env: Python 3.13.1 resolves HA 2025.4.4 (not 2026.9); `ai_task` (2025.8+) cannot be tested until Python/HA is upgraded. Node only via Docker. |
| 2026-10-13 | 0.1 | Contract written from ha-ica-todo `main` @ `6c45aa7` (v0.9.0). Brief confirmed except: `create_shopping_list` needs `integration`; no item-change event; create/delete return before reload completes. Possible ha-ica-todo changes identified, none blocking. |
