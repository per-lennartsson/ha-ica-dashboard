# Plan: categories in Handla

Group the items on a list by ICA article group (category), let people change an item's category, and (optional AI) suggest categories for the items ICA could not place.

All matching and all writes to ICA live in ha-ica-todo (branch `article-group-categories`, v0.12.0). Handla only reads categories, shows them, and asks ha-ica-todo to change them. This follows the rules in `CLAUDE.md`: ICA only through `ica.*` services, service calls only in `*_api.py`, pure logic in `domain/`, a thin card.

## What ha-ica-todo v0.12.0 provides

| Service | Fields | Response |
|---|---|---|
| `ica.get_article_groups` | none | `{"article_groups": [{"id": 10, "name": "Mejeri"}, ...]}`. Falls back to a built-in list when ICA can't be reached |
| `ica.get_shopping_list_items` | `entity_id` (entity service) | `{entity_id: {"items": [{uid, product_name, quantity, unit, completed, article_group: {id, name}, article_group_extended_id, offer_id, product_ean, latest_change}]}}`. Read from ha-ica-todo's cache, no ICA call |
| `ica.set_item_article_group` | `entity_id`, `items: [{uid, article_group_id}]`, `remember` (default true) | `{entity_id: {"updated": [uid], "not_found": [uid]}}`. Writes to ICA. `remember` makes later items with the same name get that group |

- The groups: 3 Bröd, kex och bageri, 4 Frukt & Grönt, 5 Djupfryst, 6 Färskvaror, 7 Hälsa & Skönhet, 8 Kassa, 9 Skafferivaror, 10 Mejeri, 11 Hem & Fritid, 12 Ospecificerad (none).
- Option *Categorize items automatically* (on by default): open items in 12 get a group on the next update when their name matches an ICA article or an earlier choice. So most items arrive with a group already; AI is only for what is left.
- A category change shows up in `ica_list_items_changed` as a `changed` row with `changed_props: ["articleGroupId", ...]`.
- `todo/item/subscribe` does **not** carry the category. The card has to fetch it separately (see below).

## Milestone 0: prerequisites (in ha-ica-todo, done by the maintainer)

1. Merge `article-group-categories` and release v0.12.0.
2. Check in Home Assistant that ICA keeps a category change: `ica.set_item_article_group` on one item, then look in the ICA app.
3. Here: set `MIN_ICA_VERSION = "0.12.0"` in `const.py`, update `docs/ica-contract.md` (services, option, the event note above) and add an entry in `docs/ica-change-requests.md`.

## Milestone 1: show items grouped by category

Backend:
1. `ica_api.py`: `async_get_article_groups(hass)` and `async_get_list_items(hass, entity_id)`. Errors become `failure(...)` with translation keys, like the existing calls.
2. `domain/categories.py` (pure, tested):
   - `ArticleGroup(id, name)` and `CategorizedItem(uid, name, group_id, completed)`, with defensive parsing of the responses (unknown or missing group → 12).
   - `STORE_ORDER`: the order of a typical walk through the store: 4 Frukt & Grönt, 3 Bröd, 6 Färskvaror, 10 Mejeri, 5 Djupfryst, 9 Skafferivaror, 7 Hälsa & Skönhet, 11 Hem & Fritid, 8 Kassa, 12 Ospecificerad. Unknown ids go just before 12.
   - `group_items(items) -> list[Section]`: open items per group in `STORE_ORDER`, empty groups left out; ticked items stay in their own section at the bottom, as today.
3. Service `handla.get_categories` (list, response only): `{"groups": [{id, name}], "items": {uid: group_id}}`. Only reads.

Card:
1. `api.ts`: `getCategories(hass, list)`.
2. `categories.ts` (pure, tested): merge the subscription's items with the `uid → group` map into sections. An item missing from the map (just added) goes to *Ospecificerad* until the next fetch.
3. `handla-items.ts`: after each subscription message, fetch the categories (debounced about 300 ms; ignore answers older than the latest request, as the existing `_generation` does). Render a heading per section.
4. A per-user switch "Gruppera efter kategori" (group by category), stored in browser storage (`storage.ts`), on by default. Off means today's flat list.
5. i18n: group names in sv and en, keyed by group id, falling back to ICA's name for an unknown id.

## Milestone 2: change an item's category by hand

1. `ica_api.py`: `async_set_article_groups(hass, entity_id, items, remember=True)`.
2. Service `handla.set_category` (list, `items: [{uid, group_id}]`): validates ids against the known groups, calls ha-ica-todo, returns `updated` / `not_found`. Used both by this menu and by the AI review.
3. Card: a "Byt kategori" (change category) action per item opens a picker with the groups. Update optimistically, roll back with an error message if the call fails.
4. Check that `item_announcer` / notifications ignore category-only changes (they react to adds through Handla only, so this should already hold; add a test).

## Milestone 3: AI suggests categories (optional, off by default)

Same pattern as the recipe feature (`domain/extraction.py`, `ai.py`, `handla-ai.ts`).

Backend:
1. `domain/categorize.py` (pure, tested):
   - The prompt as a Swedish constant: put each item in exactly one of the given groups, answer with ids only.
   - `STRUCTURE`: `{"items": [{"uid": str, "group_id": int}]}`.
   - `build_categorize_instructions(items, groups)`: only uid and name per item, plus the group list. No quantities, nothing else from the list.
   - `clean_category_suggestions(raw, items, groups)`: drop unknown uids or ids, duplicates and suggestions equal to the current group.
   - `MAX_CATEGORIZE_ITEMS` (for example 60), so the answer fits the provider's token limit (see `docs/ai.md`).
2. `ai.py`: `async_suggest_categories(hass, entry, list, scope)` with `scope` `unspecified` (default, only group 12) or `all`. Uses `_ask_provider` and `AiMonitor`, so failures are reported like the recipe feature's.
3. Service `handla.ai_suggest_categories` (list, scope, response only): `[{uid, name, current, suggested}]`. Registered through `async_sync_ai_services`, so it does not exist when AI is off. Writes nothing; saving goes through `handla.set_category`.

Card:
1. A "Föreslå kategorier" (suggest categories) button, only when `isAiReady(hass)`.
2. `handla-categorize.ts`: a review with one row per suggestion: name, current → suggested, a checkbox (on), and a dropdown to pick another group. "Spara" (save) sends the ticked rows to `handla.set_category`. Rows that failed stay in the view for retrying; saved ones disappear.
3. Because ha-ica-todo remembers saved choices, the same items are placed automatically next time without AI.

## Tests

- Python: `domain/categories.py` and `domain/categorize.py` as plain unit tests. The services with a mocked `ica.*` (registered fake services) in `pytest-homeassistant-custom-component`, including errors and AI off.
- Frontend: Vitest for `categories.ts`, the API wrappers, grouped rendering, the picker and the AI review (shown only when ready, failed rows kept).

## Docs

- README (en and sv): grouping, changing a category, the AI button.
- `docs/ai.md`: the categorise feature, what is sent to the provider (item names only), the item limit.
- `docs/usage.md`: the new services.

## Open questions

- Is the fixed `STORE_ORDER` good enough, or should the order be configurable per household (options flow) later? Following the store layout of the list's `sortingStore` would be better, but there is no known API for it.
- Should items in *Ospecificerad* come first instead of last, as a reminder to sort them?
