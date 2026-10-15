# Implementation plan: Handla (formerly Inköp)

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
- [x] `custom_components/handla/` with `manifest.json` (declares `ha-ica-todo`), `__init__.py`, `const.py`; `hacs.json`; `.env.example`; `requirements_dev.txt`.
- [x] Ruff, mypy, pytest (`pytest-homeassistant-custom-component`) configured, with shared fixtures: fake ICA `todo` entities and mocked `ica.*` services.
- [x] Update CLAUDE.md `Setup`/`Test` TODOs with real commands.
- **Verify:** `ruff check . && mypy custom_components && pytest tests/ -v` run green (with one smoke test).

### 0.3 CI (S)
- [x] GitHub Actions (`.github/workflows/ci.yaml`): lint, mypy, pytest, hassfest, HACS validation. Workflow written and YAML-checked locally; **a green run on a PR is still to be confirmed** (see Verify).
- **Verify:** workflow is green on a PR; a deliberately broken lint fails it.

### 0.4 Manual test setup on the maintainer's own HA (S)
- [x] `docs/dev.md`: how to install a branch/release of `handla` via HACS custom repository on the own HA OS, ha-ica-todo already installed, rules for throwaway ICA lists and cleanup. (Optional: Docker HA instance, not required.)
- [x] Update CLAUDE.md `Run` section.
- [x] Minimal config flow (single instance, creates the entry; `strings.json`, sv/en translations, tests) so `handla` can be added from the UI without editing YAML. Dependency checks stay in step 1.2.
- [x] **Verify:** `handla` installs on the real HA, is added via *Add integration → Handla* and works (confirmed by the maintainer).

---

## Phase 1: Core (no AI)

### 1.1 Pure domain logic (M)
- [x] `domain/` package: item text parsing and formatting (quantity, unit, name per the ICA rules), case-insensitive duplicate detection, default list name ("Att handla <dag> <månad>", "(2)", "(3)").
- [x] Unit tests including: comma decimals, ranges "2–3", whole-word units, Swedish month/day names, name collisions.
- **Verify (done):** 78 tests pass; `domain/` coverage 100% (`pytest --cov=custom_components/handla/domain`); an AST test checks that `domain/` never imports Home Assistant. Parser checked against ha-ica-todo's regex on 27 inputs: identical except bare `12` / `1,5`, which ha-ica-todo splits into quantity 1 + name `2` / `,5` (bug; handla keeps them as plain names).
- Decisions: a duplicate is a same normalized name (case and whitespace-insensitive), quantity and unit ignored, no plural matching. Default list name is "Att handla <dagens datum> <månad>", e.g. "Att handla 14 oktober" (day of month, not weekday).

### 1.2 Config flow and dependency check (M)
- [x] Config flow: single instance; aborts with clear Swedish/English message if `ha-ica-todo` is missing, not set up, not loaded, or below the minimum version (`v0.10.0`, see `docs/ica-contract.md`). Pure version comparison in `domain/versions.py`, I/O check in `dependency.py`.
- [x] Setup re-checks the dependency; if unusable it raises a repair issue and retries (`ConfigEntryNotReady`); the issue clears when ICA is usable again or the entry is removed. **Not monitored while running** on purpose: ha-ica-todo reloads on every list create/delete, which must not look like a problem (step 1.3 handles that as a busy state).
- **Verify (automated, done):** 126 tests pass, 100% coverage of `custom_components/handla`; tests cover missing, too old (incl. unparseable version), not configured, not loaded, OK, repair issue create/update/clear, recovery on retry, and translation keys/placeholders (sv/en/strings.json checked consistent).
- **Verify (Manual, real HA, done):** add the integration with ha-ica-todo present (works), and with it disabled or removed (clear message in Swedish/English; repair issue after restart).

### 1.3 Coordinator and list management services (L)
- [x] Coordinator reading ICA `todo` entities.
- [x] Services: `handla.set_active_list`, `handla.create_list` (prefilled name, wraps `ica.create_shopping_list`), `handla.delete_list` (wraps `ica.delete_shopping_list`).
- [x] Handle the 4–5 s integration reload: busy state until the `ica_lists_changed` event (v0.10.0), with a timeout as a safety net. A missing entity in the event means failure. Use the `offline_id` entity attribute, not registry parsing. Use events/coordinator, not templates.
- [x] Entities: active-list select, item-count sensor, busy/status sensor.
- **Verify (automated, done):** 184 tests pass, 100% coverage of `custom_components/handla`. Covered: create/delete success, default and numbered names, event arriving before or after the service returns, lower/upper-case ids, timeout, event without entity (failed reload), ICA error, ICA not loaded, busy refusal, status transitions, active list default/persistence/fallback, favourites ignored, list kept while ICA reloads, translations consistent.
- **Verify (Manual, real HA, the main risk check, done):** follow "Manual check: lists" in `docs/dev.md` with throwaway lists, record the reload time, clean up.
- Decisions: (1) the active list is shared by the household and lives in the integration (select + `handla.set_active_list`, saved across restarts); a user's own choice in the card stays in the browser (1.8). (2) With several ICA accounts the first loaded one is used. (3) Wait for `ica_lists_changed` at most 30 s (`LISTS_CHANGED_TIMEOUT`); a missing entity in the event counts as failure. (4) One create/delete at a time; a second call is refused (`busy`). (5) Entities: `select` active list, `sensor` items to buy (open items on the active list), `sensor` status (idle/creating/deleting/error). (6) Service schemas use `probatio` when available (Home Assistant 2026.10+) and fall back to `voluptuous`.

### 1.4 Add, duplicate check, remove, clear (L)
- [x] Services: `handla.add_item` (returns duplicate info instead of adding when `confirm_duplicate` is false), `handla.remove_item`, `handla.tick_item`, `handla.clear_ticked`.
- [x] Text goes in service data (never state; 255-char limit).
- **Verify (automated, done):** 221 tests pass, 100% coverage of `custom_components/handla`; two deliberate breakages (ticked items counted as duplicates; confirmation ignored) were caught by the tests. Covered: add to active or explicit list, text normalisation, duplicates (case-insensitive, quantity ignored, ticked items ignored), confirm, empty text, no list, unknown list, list unavailable, failures from `todo.*`, tick/untick by uid or text (prefers the open item), ambiguity, identical entries, remove, clear.
- **Verify (Manual, real HA, done):** follow "Manual check: items" in `docs/dev.md` against a throwaway list in the ICA app.
- Decisions: (1) only **open** items count as duplicates; something already bought may be wanted again. (2) A duplicate is the same name, ignoring case, spaces, quantity and unit. (3) `handla.add_item` answers `added: false` + `duplicates` (no error) so the card can ask "finns redan – lägga till igen?" and call again with `confirm_duplicate: true`. (4) Items are found by uid, then exact text, then same name; ambiguous matches are refused with the candidates listed (the card uses uids). (5) All writes go through Home Assistant's `todo.*` services, never the ICA API. (6) Who added an item (for notifications) is added in 1.6 from the service-call context.

### 1.5 Usage statistics and quick-add (M)
- [x] Persist per-item add counts (HA `Store`); service/sensor exposes the top N items.
- **Verify (automated, done):** 266 tests pass, 100% coverage; a deliberate breakage (adds not counted) made 5 tests fail. Covered: counting by name (case, quantity and unit ignored, latest spelling kept), blank names, cap at 500 entries (least used dropped), ranking by count then recency then name, limit, JSON round trip and skipping of malformed stored data, unconfirmed duplicates / failed adds / ticks / removals are not counted, sensor state and attribute follow the counts, only the top 12 on the sensor, counts saved on unload and restored, corrupt storage starts empty, service limit validation.
- **Verify (Manual, real HA, done):** follow "Manual check: frequent items" in `docs/dev.md`; counts must survive a Home Assistant restart.
- Decisions: (1) Only adds through `handla.add_item` are counted (quick-add and the card use it). Items added in the ICA app or the todo card are not: the `ica_list_items_changed` event could cover them but also fires for our own adds and has no user, so it would double count. (2) "What we buy most" is approximated by what is added most, not ticked. (3) Counts are per name, ignoring quantity and unit; the quick-add button adds the plain name. (4) Exposed as `sensor.handla_frequent_items` (state = number of different items, attribute `items` = top 12 with name, count, icon; not stored in the recorder) and `handla.get_top_items`. (5) Icons come from a Swedish keyword list matched inside words (`havremjölk` gets the milk icon); icon names are unverified until the card shows them (1.9). (6) With no history yet the list was empty; decided in 1.9: default staples fill the quick-add row (see 1.9).

### 1.6 Notifications (M)
- [x] Options flow: choose users/notify targets.
- [x] Use HA service call context (user ID) to know who added items; notify the others only. No heuristics.
- [ ] *Deferred (optional):* react to `ica_list_items_changed` for changes made outside Handla (e.g. in the ICA app). The event carries no user and also fires for our own adds, so it needs de-duplication and would notify the adder too. Revisit after real-world use.
- [x] Fire an `handla_item_added` event with the user ID.
- **Verify (automated, done):** 309 tests pass, 100% coverage. Two deliberate breakages were caught (adder notified too: 3 tests fail; extra timers: 1 test fails). Covered: the other user is told and the adder is not, quick adds combined into one message (repeats skipped, cut off after 5 items), separate messages per adder, a later add starts a new message, add without a user or with an unknown user id tells everyone, Swedish/English text, a failing phone does not block others or the add (warning logged), unconfirmed duplicates send nothing, no recipients / malformed options send nothing, event payload with user and context, pending messages sent on unload, options flow (users, service per user, defaults, off, system/inactive users hidden, aborts).
- **Verify (Manual, real HA, done):** follow "Manual check: notifications" in `docs/dev.md` with two users and two phones.
- Decisions: (1) Delivery through `notify.mobile_app_*` services (falls back to other notify services if none); the options flow maps each chosen user to one service. (2) The adder comes from the service-call context; the adder is never notified, and with no user (automation) everyone is. (3) Adds by the same person to the same list within 20 s become one message; at most 5 items are listed. (4) Message language follows the Home Assistant language (Swedish and English; other languages get English). (5) The event `handla_item_added` (`entity_id`, `list_title`, `item`, `user_id`, `user_name`) is fired for every item actually added; its name and fields are now a public contract. (6) Notification failures are logged, not raised: the add must succeed even if a phone is offline. (7) Tapping a notification does not open the shopping view yet (needs the card, 1.9/1.10).

### 1.7 Frontend card scaffold (M)
- [x] `frontend/` with Lit, TypeScript, Vite, Vitest, ESLint/Prettier; build output served as a Lovelace resource; CI builds and tests it.
- [x] i18n setup (sv default, en).
- **Verify (automated, done):** `npm run format:check`, `lint`, `typecheck`, `test:coverage` (27 tests, 100% line coverage) and `build` (21.6 kB, 7.4 kB gzipped) pass inside Docker; the Python side (`card.py`: serving, once only, missing build, no web server) is tested (315 Python tests, 100% coverage); CI has a new `frontend` job. The "hello" card was checked in a browser on the mock-data page (Swedish, English, with and without data).
- **Verify (Manual, real HA, done):** follow "Manual check: card loads" in `docs/dev.md`.
- Decisions: (1) Tooling: Node 22 in Docker (`scripts/node.sh`), npm, Vite (library build to one ES module), Vitest + jsdom, ESLint + typescript-eslint, Prettier, TypeScript (strict). Lit without decorators (`static properties`, `declare` fields). Current majors resolved by npm (TypeScript 6, Vite 8, Vitest 5, ESLint 10, Lit 3.3), pinned by `package-lock.json`. (2) The integration serves the built file itself and loads it in every dashboard (`add_extra_js_url`), so users never add a resource by hand; `frontend` and `http` are soft (`after_dependencies`) so tests and headless setups work. (3) Card language: Swedish for `sv*` (and when unknown), English for everything else, same rule as the notifications. (4) Still open: commit `custom_components/handla/www/handla-card.js` or build it in the release workflow (decide in 1.11; until then installing from `main` via HACS has no card, a folder copy of a local build does).

### 1.8 Card: list picker, create, delete (M)
- [x] Select the active list, create (prefilled name), delete with confirmation, progress indicator and disabled buttons during busy state.
- [x] Per-user UI state in browser storage, not helpers.
- [x] Clear message when ha-ica-todo is missing.
- **Verify (automated, done):** frontend: 100 tests (lists, api, storage, i18n, card), 100% line coverage, lint/type check/build pass (bundle 33.5 kB, 10.6 kB gzipped); two deliberate breakages (no double-tap guard; confirmation outliving its list) were caught. Backend: 322 tests, 100% coverage (new `sensor.handla_lists`, `handla.suggest_list_name`). Browser check on the mock-data page: picker, create (prefilled name, focus, progress with locked controls, new list selected and remembered), delete (confirmation naming the list), failure (error shown, retry possible), and iPhone width (375 px: no horizontal scroll, 44 px controls, 16 px fields).
- **Verify (Manual, real HA, done):** follow "Manual check: list picker" in `docs/dev.md` on a phone in the companion app: no double taps possible during the reload.
- Decisions: (1) The card reads `sensor.handla_lists` (all lists with entity id, title, open items, plus the household's active list) and `sensor.handla_status`; it contains no list logic. The prefilled name comes from the new service `handla.suggest_list_name` so the date can never be stale. (2) Each user's choice of list is kept in this browser's `localStorage` (`handla:selected-list`, ICA offline id), never in helpers; it falls back to the household's active list, then the first list. Picking a list in the card does not change the household's active list; creating one does (`set_active: true`), and that list also becomes the creator's choice. (3) Delete confirmation is inline (no dialog dependency) and is bound to one list, so it can never pop up for another. (4) Controls lock from the click (local `pending`) and while the status sensor says `creating`/`deleting` (so other devices are locked too); errors from the call are shown in the card, and the status sensor's last error is shown when idle. (5) When the lists sensor is missing or unavailable the card says Handla is not running and points to `ha-ica-todo` and Repairs. (6) Native `<select>`/`<input>`/`<button>` styled with Home Assistant theme variables (16 px fields, 44 px targets).

### 1.9 Card: items view (L)
- [x] Free-text input (Enter adds and keeps focus), item list with tick/remove, clear ticked, duplicate prompt "finns redan – lägga till igen?", quick-add buttons with icons.
- **Verify (automated, done):** frontend 186 tests (items helpers, API, subscription lifecycle, add queue, duplicates, failures, quick-add, tick/remove/clear, card integration), 100% line coverage, lint/type check/build pass (bundle 51 kB, 14 kB gzipped); backend 328 tests, 100% coverage. Deliberate breakages caught (duplicates silently confirmed, field disabled while adding, per-row double-tap guard). The tests found one real bug: the live subscription was not restarted when the card was detached and re-attached (switching dashboard views); fixed. Browser check on the mock-data page (desktop and 375 px): add by Enter with focus kept, queue, duplicate prompt, confirm, tick (row locks), clear ticked, remove, quick-add, failed tick/add with retry, unavailable list and recovery, no horizontal overflow, 44 px targets, 16 px field.
- **Verify (Manual, real HA, done):** follow "Manual check: items view" in `docs/dev.md` on a phone: keyboard stays open after Enter, live updates, reload of ha-ica-todo, and the icon names.
- Decisions: (1) Items come from the same websocket subscription Home Assistant's own todo card uses (`todo/item/subscribe`), so changes made elsewhere appear live; the card resubscribes when the list entity disappears and comes back (ha-ica-todo reload), when another list is chosen, and when it is re-attached. (2) Entered items go into a queue and are added one at a time; the field is never disabled while adding (a disabled field loses focus and closes the phone keyboard); each queued item is sent to the list it was typed for. (3) Duplicate = same name among **open** items (backend rule from 1.4); the card asks "finns redan – lägga till igen?" and holds the rest of the queue until you answer. (4) A failed add shows the error with "Försök igen" / "Hoppa över"; a failed tick/remove/clear shows a dismissable error. (5) Quick-add: backend now tops real favourites up with 8 default Swedish staples (count 0) so a new install has buttons from day one (`quick_add_payload`, minimum 8 shown, never more than 12, never repeating a real item). (6) The items view is its own element `<handla-items>` embedded by the card (card file stays small); icons use Home Assistant's `<ha-icon>`, and the preview page stubs it with emoji. (8) Ticked items are separated from the open ones by a labelled divider with a count ("AVBOCKADE (n)"), added after the first look at the card on a real screen. (7) Tapping a quick-add button moves focus off the text field (the keyboard closes); acceptable, can be revisited after the phone check.

### 1.10 Mobile shortcut (S)
- [x] Compact card/badge on the mobile dashboard showing the item count and opening the shopping view.
- **Verify (automated, done):** frontend 226 tests (shortcut card: counts, own list vs household list, unknown/0/not running, tap and keyboard navigation, plain count without path, config validation; navigation helper), 100% line coverage, lint/type check/build pass (one 56 kB file, 15 kB gzipped); backend 329 tests (cart icon on the count sensor), 100% coverage. Deliberate breakages caught (tap does not navigate; `//evil.example` paths accepted). Browser check on the mock-data page at 375 px: 64 px tall card, count followed a live add from 3 to 4, tap navigated to the configured path.
- **Verify (Manual, real HA, done):** follow "Manual check: mobile shortcut" in `docs/dev.md` on a phone in the companion app.
- Decisions: (1) Both options were built, as chosen: a compact card `<handla-shortcut>` (shown with a chevron and as a button when `navigation_path` is set) and documentation for using `sensor.handla_items_to_buy` as an entity badge (`docs/usage.md`). (2) The shortcut shows the same list the full card shows: this user's own choice on this device, else the household's active list; the badge/sensor always follows the household's active list. (3) Navigation uses a configured dashboard path and Home Assistant's own mechanism (`history.pushState` + `location-changed`); paths must start with a single `/` (no web addresses, no `//host`). (4) Both cards ship in the same `handla-card.js` (entry `src/index.ts`), so there is still one file to serve.

### 1.11 Core release (M)
- [x] README (sv/en): install via HACS (both ha-ica-todo and handla), configuration, screenshots.
- [x] Release workflow: tag, build card, attach assets, version bump.
- **Verify (automated, done):** the packaging script was run for real (`scripts/package-release.sh`, tested in a temporary tree: zip layout, version stamped only in the packaged manifest, no caches, bad tags / missing card / wrong card version refused) and a dry run with the real build gave a 50 KB `handla.zip` with the integration and `www/handla-card.js`; configuration consistency tests (hacs.json ↔ workflows ↔ script, tag only via environment, matching versions); CI has a new *Release package builds* job. Python 347 tests, frontend 226 tests, all green; lint/types/build clean.
- **Verify (Manual, done by the maintainer):** (1) publish `ha-ica-todo` v0.10.0 as a GitHub release; (2) publish a GitHub release `v0.1.0` of this repository (as a pre-release) and check the *Release* workflow attaches `handla.zip`; (3) install it through HACS (custom repository) on the own HA; (4) run the manual checks for steps 1.2–1.10 in `docs/dev.md` plus the core feature checklist (features 1–6) end-to-end on a phone. See `docs/release.md`.
- Decisions: (1) The built card is **not committed**: the release workflow builds it and ships it inside `handla.zip` (`hacs.json`: `zip_release`, `filename: handla.zip`), so git history stays clean. Consequence: HACS can only install published releases; unreleased work is installed by copying the folder (`docs/dev.md`). (2) The workflow stamps the tag's version into the packaged manifest and the card; repository versions are placeholders. (3) The release workflow uses only first-party actions and passes the tag through an environment variable (no expressions in shell code); ha-ica-todo's own release workflow uses a third-party action by branch name (`@main`), worth pinning. (4) `hacs.json` declares `homeassistant: 2026.9.0` (the maintainer's version; development and tests ran on 2026.10, so 2026.9 is **untested**) and `country: SE`. (5) README in English with a Swedish twin (`README.sv.md`); screenshots are from the preview page with sample data and should be replaced with real ones. (6) Still needed before a public release, from the maintainer: a license, repository description and topics (HACS validation).

**Phase 1 done when:** features 1–6 work on a phone with only HA + ha-ica-todo, CI is green, a tagged release installs via HACS, and no AI code or UI is present.

---

## Phase 2: Optional AI module

### 2.1 Enable switch and provider selection (M)
- [x] Add a mocked `ai_task` entity fixture to `tests/conftest.py` (`fake_ai`; dev environment has HA 2026.10.1, which includes `ai_task`).
- [x] Options flow: AI off by default; when on, choose an `ai_task` entity; validate it exists.
- [x] Expose AI-enabled state so the card can hide all AI UI when off (`sensor.handla_ai`: `off` / `ready` / `unavailable`).
- **Verify (automated, done):** 379 Python tests, 100% coverage, ruff/mypy clean. Off by default; malformed options count as off; on needs an existing entity; turning off never fails; the status follows the provider (unavailable, back, removed) and ignores other entities; no AI services are registered. A deliberate breakage (default on) was caught by 3 tests.
- **Verify (Manual, real HA, not yet done):** toggle AI in the options flow (Handla settings, menu: Notifications / AI), pick a real AI Task entity, check `sensor.handla_ai` shows `ready`, then turn it off.
- Decisions: (1) The options flow now opens with a menu (Notifications / AI); the old first step is `notifications`, so existing saved options are unaffected. (2) The status sensor, not an options attribute, is what the card reads. (3) No AI services exist yet; from 2.2 they must be registered only while AI is on.

### 2.2 Extraction service (L)
- [x] `handla.ai_extract_items`: pasted text in service data → structured output (short Swedish names, quantity first, merged duplicates, staples skipped). Registered only while AI is on.
- [x] Prompt and output structure in version control (`domain/extraction.py`). **`max_tokens` cannot be set per call**: `ai_task.generate_data` has no such field (HA 2026.10). The limit belongs to the provider's own configuration (Anthropic: "Maximum tokens" on the conversation/AI Task subentry), so it is documented in 2.5 instead. Mitigations here: compact output (one short text per item), input capped at 20 000 characters, answer capped at 100 items.
- [x] Mark items already on the list (`on_list`, `existing`; they start with `selected: false`).
- **Verify (automated, done):** 411 Python tests, 100% coverage, ruff/mypy clean; mocked `ai_task` with fixtures for cleaning (bullets, staples, merged quantities, malformed answers), provider failure, empty/too long text, unavailable provider, and the service appearing and disappearing with the AI switch. Deliberate breakages (staples not skipped; existing items pre-selected) were each caught by 2 tests.
- **Verify (Manual, real HA, not yet done):** prompt reviewed with the real provider on a few samples (recipe, meal plan, chat message, very long text); call `handla.ai_extract_items` from Developer tools → Actions.
- Decisions: (1) The model returns one list of plain texts ("2 st gurka"), because that is what ha-ica-todo parses; the answer is cleaned and merged again in Python. (2) The service only suggests; nothing is added to the list (2.3 adds the selected ones through `handla.add_item`). (3) Truncated answers by a low provider token limit cannot be detected reliably, so a long list may be cut short silently; see 2.5 docs.

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
- Decided: Vitest for the card; the built card is attached to releases, not committed (1.11). Open: final usage-statistics source (own counts only, or also ICA history); license, description and topics for HACS validation; Home Assistant 2026.9 compatibility is untested (development ran on 2026.10).

## Progress log
| Date | Step | Result |
|------|------|--------|
| 2026-10-15 | 2.2 | Extraction service done: `handla.ai_extract_items` (only while AI is on), `domain/extraction.py` (prompt, structure, cleaning, marking), mocked `ai_task` in tests; 411 tests, 100% coverage. `max_tokens` is not a service field (documented for 2.5). Manual check with a real provider pending. |
| 2026-10-14 | 2.1 | AI switch done: options menu with AI step (on/off, `ai_task` entity, validated), `sensor.handla_ai`, `domain/ai.py`, `fake_ai` fixture; 379 tests, 100% coverage. Manual check on the real HA pending. |
| 2026-10-14 | Phase 1 | Maintainer reports all manual checks for 1.x done on the real HA (steps 1.2–1.11). Phase 1 complete; Phase 2 awaits plan approval. |
| 2026-10-13 | 0.1 (update) | ha-ica-todo changes made on branch `list-events-and-metadata` (`c2fe1f1`, v0.10.0): `ica_lists_changed`, `ica_list_items_changed`, list entity attributes, fork metadata. Contract and plan updated; minimum version now `>= v0.10.0`. Review notes: event fires also on reload failure; item-change event has no user; removed fields not reported. |
| 2026-10-13 | env | Upgraded dev env to Python 3.14.8 (Homebrew) and HA 2026.10.1 / pytest-homeassistant-custom-component 0.13.372. Checks green. `ai_task` is now testable. |
| 2026-10-14 | card delivery | Real HA showed "Custom element doesn't exist: handla-card" (script from `add_extra_js_url` not defined in time; adding `/handla/handla-card.js` as a dashboard resource fixed it). The card is now registered as a Lovelace resource (storage mode; refreshed on version change, kept if added by hand, removed with the integration), with `add_extra_js_url` only as the YAML-mode fallback; pure decisions in `domain/resources.py`, `lovelace` added to `after_dependencies`. 360 Python tests, 100% coverage. Manual check on the real HA pending (remove your hand-made resource first and restart). |
| 2026-10-14 | rename | Renamed Inköp / `inkop` to **Handla** / `handla` before the first release (folder, domain, entity ids, services, event, card elements, storage keys, `handla.zip`, texts, docs, tests, workflows). HACS title and integration name: "Handla – Shared shopping lists for ICA"; device and cards are just "Handla" so entity ids stay short. Repository stays `ha-ica-dashboard`. 347 Python + 226 frontend tests green; package dry run clean. An old install must be cleaned up by hand (see `docs/dev.md`). |
| 2026-10-14 | 1.11 | Release machinery done: packaging script, release workflow (builds card, stamps version, attaches `handla.zip`), `hacs.json` zip release, CI package job, bilingual README with screenshots, `docs/release.md`; 347 Python + 226 frontend tests. Publishing the releases and the HACS install check need the maintainer. |
| 2026-10-14 | 1.10 | Mobile shortcut done: `<handla-shortcut>` card, entity-badge docs (`docs/usage.md`), cart icon on the count sensor; 226 frontend + 329 backend tests; checked in a browser at phone width. Manual check on the real HA pending. |
| 2026-10-14 | 1.9 (follow-up) | Divider between open and ticked items ("Avbockade (n)"); 190 frontend tests. |
| 2026-10-14 | 1.9 | Items view done: `<handla-items>` (live subscription, add queue, duplicate prompt, tick/remove/clear, quick-add), backend staples fallback; 186 frontend + 328 backend tests; checked in a browser incl. phone width; one real bug found by tests and fixed. Manual check on the real HA (keyboard!, icons) pending. |
| 2026-10-14 | 1.8 | List picker done: card (picker, create with prefilled name, delete with confirmation, progress, errors, per-user choice in localStorage), `sensor.handla_lists`, `handla.suggest_list_name`; 100 frontend + 322 backend tests; checked in a browser incl. phone width. Manual check on the real HA pending. |
| 2026-10-14 | 1.7 | Card scaffold done: `frontend/` (Lit, TypeScript, Vite, Vitest, ESLint, Prettier in Docker), hello card, i18n sv/en, mock-data preview checked in a browser, `card.py` serves the build, CI `frontend` job. Manual check on the real HA pending. |
| 2026-10-14 | 1.6 | Notifications done: `notify.py`, `domain/notify.py`, options flow, `handla_item_added` event, `schema.py`; 309 tests, 100% coverage. Item-change event from the ICA app deferred. Manual check with two users pending. |
| 2026-10-14 | 1.5 | Usage statistics done: `domain/usage.py`, `domain/icons.py`, `usage.py`, frequent-items sensor, `handla.get_top_items`; 266 tests, 100% coverage. Manual check on the real HA pending. |
| 2026-10-14 | 1.4 | Items implemented: `handla.add_item` / `tick_item` / `remove_item` / `clear_ticked`, pure `domain/todo_items.py`, `todo_api.py`, `shopping.py`; 221 tests, 100% coverage. Manual check on the real HA pending. |
| 2026-10-14 | 1.3 | Lists implemented: coordinator, `handla.create_list` / `delete_list` / `set_active_list`, select + 2 sensors; 184 tests, 100% coverage. Manual check on the real HA (reload time!) pending. |
| 2026-10-14 | 1.2 | Dependency check implemented (flow + setup + repair issue), 126 tests green. Manual check on the real HA pending. |
| 2026-10-14 | 1.1 | Domain logic done: `domain/items.py`, `duplicates.py`, `naming.py`; 78 tests, 100% coverage of `domain/`. |
| 2026-10-14 | 0.4 | Manual verification on the real HA: `handla` installed and worked. Docs and minimal config flow merged (`7a33bf1`). |
| 2026-10-13 | 0.2 | Skeleton + tooling done. ruff, mypy and 2 smoke tests green. Dev env: Python 3.13.1 resolves HA 2025.4.4 (not 2026.9); `ai_task` (2025.8+) cannot be tested until Python/HA is upgraded. Node only via Docker. |
| 2026-10-13 | 0.1 | Contract written from ha-ica-todo `main` @ `6c45aa7` (v0.9.0). Brief confirmed except: `create_shopping_list` needs `integration`; no item-change event; create/delete return before reload completes. Possible ha-ica-todo changes identified, none blocking. |
