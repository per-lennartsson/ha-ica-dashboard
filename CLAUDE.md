# CLAUDE.md

## Project

"Handla": a shopping-list solution for Home Assistant, built on ICA shopping lists. A custom integration (`handla`, Python) owns the domain logic and a thin custom card (TypeScript/Lit) provides the UI. Designed for multiple users sharing the same shopping list, each on their own device via the Home Assistant companion app. The UI is in Swedish. The project is HACS-ready so others can reuse it.

Naming: the product is **Handla** (Home Assistant domain `handla`; it was called Inköp / `inkop` before its first release). The HACS title and the integration name are "Handla – Shared shopping lists for ICA"; the device and the cards are just "Handla", which keeps entity ids short (`sensor.handla_items_to_buy`). The GitHub repository is still `ha-ica-dashboard`.

Environment: Home Assistant OS (core 2026.9.x) with HACS.

**Required dependency:** [ha-ica-todo](https://github.com/per-lennartsson/ha-ica-todo), a maintained fork of `lazytarget/ha-ica-todo`. It is installed separately (HACS custom repository). `handla` declares it as a dependency, checks the minimum version at setup, and shows a clear message in the UI when it is missing or not loaded. Check the repo for the current version, services and entities before relying on them. The ICA entities and services (all under the `ica` domain):
* Each tracked ICA shopping list is a `todo` entity, plus a favourites list.
* Services: `ica.create_shopping_list` (title, optional comment, track), `ica.delete_shopping_list`, `ica.refresh_all`, `ica.get_baseitems`, `ica.add_baseitem`, `ica.upsert_shopping_list`, `ica.add_offers_to_shopping_list`, `ica.lookup_product`, `ica.get_recipe`.
* Item text is parsed as "quantity unit name". Units count only as whole words: st, förp, kg, hg, g, l, dl, cl, ml, msk, tsk, krm. Quantity is a number (comma decimals allowed), and ranges like "2–3" keep the higher number. Ticking or renaming an item parses the text back.
* List IDs are matched case-insensitively (ICA returns upper case). A tracked list that returns 404 is untracked.
* Known limits: renaming an item cannot remove its unit (ICA ignores a null unit). Creating or deleting a list reloads the integration (about 4–5 s), and its entities are briefly unavailable. The UI must handle this.

**Features**

Core (works with only HA and ha-ica-todo):
1. Lists: choose the active list; create a list (name prefilled "Att handla <dag> <månad>", with "(2)", "(3)" if taken); delete with confirmation; clear progress feedback so nobody taps twice.
2. Adding items: free text (Enter adds and keeps focus); quick-add buttons with icons, based on what is bought most.
3. Duplicates: case-insensitive check, ask "finns redan – lägga till igen?" before adding.
4. Removing items: remove or tick off, and clear ticked items.
5. Notifications: push to chosen users when someone else adds items.
6. Mobile: a shortcut on the mobile dashboard showing the item count and opening the shopping view.

Optional AI module (opt-in, **off by default**; when off or no provider is available, no AI UI is shown and everything else works):
7. Paste any text (recipe, meal plan, message).
8. AI extracts items: short Swedish names, quantity first, duplicates merged, staples like salt, pepper and water skipped.
9. Review and edit suggestions; items already on the list are marked and unticked; failed items stay in the view for retry.
10. Monitoring: push when the AI provider fails (e.g. Anthropic credits run out); optional daily health check.

## Tech stack

* Home Assistant custom integration `handla` (Python 3.14, developed against Home Assistant 2026.10), declaring `ha-ica-todo` as a dependency
* Frontend: custom card in TypeScript with Lit, Swedish UI with i18n (sv, en)
* AI: HA's provider-neutral `ai_task` platform; the user picks any configured AI Task entity (Anthropic or another). Claude/Anthropic is **not** assumed installed
* Tests: `pytest` with `pytest-homeassistant-custom-component` (mocked ICA and AI services); frontend tests with Vitest + jsdom
* Lint/typing: Ruff, mypy (Python); ESLint, Prettier, `tsc` (TypeScript)
* CI: GitHub Actions (lint, type check, tests, HACS/hassfest validation, tagged releases)
* Distribution: HACS custom repository; versioned GitHub releases carry `handla.zip` (integration + built card), built by the release workflow. The built card is not committed

## Code conventions

* Python: Ruff for lint and format, type hints on all functions, docstrings on modules and public functions.
* Naming: `snake_case` for Python functions and variables, `PascalCase` for classes; `camelCase` in TypeScript, `kebab-case` for custom element names.
* Follow Home Assistant integration conventions (config flow, options flow, `DataUpdateCoordinator`, `strings.json` and translations).
* All user-visible strings go through translations. Never hard-code Swedish text in logic.
* Commit messages: short, imperative.

## Architecture

* `handla` owns the domain logic: lists, duplicate rules, quantity rules, usage statistics, notifications and the optional AI module. It exposes services, entities and events. The card stays thin and contains no business logic.
* All calls to ICA go through `ha-ica-todo` services and `todo` entities. Never call the ICA API directly or handle ICA credentials/tokens.
* All I/O (HA service calls, AI Task calls) lives in a separate layer. Pure domain logic (parsing, duplicate detection, name generation) is plain Python and unit-testable without HA.
* The AI module is optional. Toggle it via the integration's options flow, and choose the AI Task entity there. Off by default. No AI code path may run, and no AI UI may render, when disabled.
* Functions do one thing. If a function needs a comment to explain what it does, split it.
* No global state. Pass configuration as arguments.
* All external calls need explicit error handling. Never swallow exceptions, and surface failures to the user with a clear message.
* Tests are written alongside implementation, not after.

**Known Home Assistant pitfalls to design around**
* Helpers (`input_text` etc.) are global across users and devices. Do not use them for UI state. Keep per-user UI state in the card (e.g. browser storage).
* Entity state is capped at 255 characters. Pass long pasted text as service data, never as state.
* Templates using `integration_entities()` create no listeners, so `wait_template` and template sensors will not update. Do not rely on them; use events or coordinators.
* Returning JSON from a template where a card expects a list can break cards. Return native lists.
* Notifications must know who made a change using HA context (user ID), not heuristics.
* `ai_task` default `max_tokens` (300 in some providers) can truncate structured output on long lists, and `ai_task.generate_data` has no field to set it per call. It is the provider's own setting (Anthropic: "Maximum tokens" on the AI Task entry): document it (`docs/ai.md`), keep answers compact, and cap input and output sizes.
* There is no API for the remaining Anthropic credit balance. Detect failure by errors, not by balance.

## Rules

* **Never change `ha-ica-todo` directly** (no local patches, no pushes to that repo). If a change is needed, write a ready-to-use prompt/issue text for the maintainer, who implements and pushes it themselves in the `per-lennartsson/ha-ica-todo` fork, with a versioned release. Then bump the minimum version here.
* Never store long-lived tokens or secrets in files, docs or git. Use HA's secret handling and environment variables, documented in `.env.example`.
* Configuration lives in version control (the repo), not pushed ad hoc through the HA API.
* Tests against a real ICA account must use throwaway lists and clean them up afterwards. Default tests use mocks.
* Do not add or swap dependencies without asking.
* **Never install anything** (pip/npm packages, tools, system software, virtual environments) without explicit permission from the maintainer. Ask first and say what and why.
* Node/npm is not installed on the host. Run all Node tooling (frontend build, Vitest, ESLint) inside a Docker container, never directly on the host. Document the exact `docker run` commands in `docs/dev.md`.
* Do not change service names, event names or entity IDs once released. It breaks existing dashboards and automations.
* Never commit directly to main. Work in feature branches.
* Do not start implementing a phase without the maintainer's approval of the plan.

## Project structure

```
/
├── CLAUDE.md, plan.md, README.md, README.sv.md
├── custom_components/handla/
│   ├── manifest.json, strings.json, translations/   # sv + en
│   ├── __init__.py          # setup, services registration
│   ├── config_flow.py       # setup flow (ICA dependency check) + options flow (who is notified)
│   ├── dependency.py        # checks ha-ica-todo (installed, version, loaded), repair issue
│   ├── coordinator.py       # event-driven: ICA lists, active list, create/delete flows
│   ├── events.py            # collects ica_lists_changed events
│   ├── services.py, services.yaml   # set_active_list, create/delete_list, suggest_list_name, items, get_top_items
│   ├── shopping.py          # add / tick / remove / clear items on a list
│   ├── usage.py             # persistent add counts (quick-add data)
│   ├── ai.py, ai_monitor.py # optional AI: switch, extraction service, failure push + daily check
│   ├── notify.py            # batched "someone added items" notifications, handla_item_added event
│   ├── schema.py            # probatio (HA 2026.10+) or voluptuous
│   ├── card.py              # serves the built card and loads it in every dashboard
│   ├── www/                 # built card (git-ignored): handla-card.js
│   ├── todo_api.py          # thin wrappers around Home Assistant's todo.* services
│   ├── entity.py, select.py, sensor.py
│   ├── const.py
│   └── domain/              # pure logic, no Home Assistant imports
│       ├── items.py, duplicates.py, naming.py, lists.py, todo_items.py, usage.py, icons.py, notify.py, versions.py
│       ├── ai.py, extraction.py, ai_health.py   # AI status, prompt and cleaning, failure de-duplication
├── tests/                   # pytest, mocked ICA and AI (conftest.py has FakeIca)
├── docs/                    # ica-contract.md, dev.md, usage.md, ai.md (cards, shortcut, badge), release.md, images/
├── .github/workflows/       # ci.yaml, release.yaml (builds card + handla.zip on a published release)
├── hacs.json, pyproject.toml, requirements_dev.txt, .env.example
├── frontend/                # Lit card: src/ (index, handla-card, handla-items, handla-shortcut, handla-ai, ai, lists, items, api, navigate, storage, i18n), dev/ (mock-data preview), tests next to sources
├── scripts/node.sh          # runs Node commands in Docker
└── scripts/package-release.sh  # builds dist/handla.zip for a release (docs/release.md)
```


## Setup

Python runs locally, with libraries kept in `.venv` (git-ignored). Ask the maintainer before installing anything.

```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements_dev.txt
cp .env.example .env   # only needed for manual checks against a real HA
# Never put long-lived tokens in files that are committed
```

Node is not installed on the host. All frontend commands run in Docker through `./scripts/node.sh` (see `docs/dev.md`), for example `./scripts/node.sh npm ci`. Installing or adding packages needs the maintainer's permission.

Requires `ha-ica-todo` installed and configured in Home Assistant (HACS custom repository `per-lennartsson/ha-ica-todo`) for manual checks.

## Run

Development needs no running Home Assistant: tests use an in-process HA core and mocks.
Manual checks run on the maintainer's own HA with `ha-ica-todo >= v0.10.0`. How to install a branch or release, how to check that it loaded, and the rules for throwaway ICA lists are in `docs/dev.md`.
Card preview with mock data: `DOCKER_FLAGS="-p 5173:5173" ./scripts/node.sh npm run dev`, then open http://localhost:5173.

## Test

```bash
source .venv/bin/activate
ruff check . && ruff format --check .
mypy custom_components
pytest tests/ -v
```

Frontend (Docker):

```bash
./scripts/node.sh npm run format:check
./scripts/node.sh npm run lint
./scripts/node.sh npm run test:coverage
./scripts/node.sh npm run build   # writes custom_components/handla/www/handla-card.js
```

## Plan and open questions

Phased plan (needs the maintainer's approval before implementation):
* Phase 1: core without AI (lists, add, duplicates, remove/clear, notifications, mobile shortcut).
* Phase 2: optional AI module (paste, extract, review, monitoring).

TODO: record the approved milestones, effort estimates and definition of done here once agreed.
