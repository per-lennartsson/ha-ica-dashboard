# Plan: suggestions while typing

Show names to pick from while typing in the add field. Each suggestion shows the category the item will get. The data and the category logic live in ha-ica-todo (v0.13.0, branch `item-history-suggestions`). Handla only fetches, filters and shows them. Same rules as `docs/categories-plan.md`: ICA only through `ica.*` services, service calls only in `*_api.py`, pure logic in `domain/`, a thin card.

## What ha-ica-todo v0.13.0 provides

| Service | Fields | Response |
|---|---|---|
| `ica.get_item_suggestions` | `entity_id` (any ICA list of the account), optional `query`, optional `limit` | `{entity_id: {"items": [{"name", "source", "count"?, "article_group": {"id", "name"}}]}}` |

- **Order:** names from the item history (most used first), then favourite items (`source: "favorite"`), then ICA's articles (`source: "article"`). Each name appears once (plural and case ignored). `count` is only set for history names.
- **`article_group`:** the category an item with that name gets when it is added now. The order is a saved choice, then the most used category from the history, then ICA's articles.
- **With `query`:** names containing the text, the ones starting with it first, then the ones with a word starting with it.
- **Without `query`:** the full list, a few thousand names and about 100–200 KB. ha-ica-todo builds it in under 20 ms.
- **The history** counts items added from anywhere (Handla, the ICA app, the website) and the category they ended up in. Picking a suggestion adds the item by name as today, and ha-ica-todo sets the category itself. Handla does not send one.

## Milestone 0: prerequisites

1. In ha-ica-todo: merge `item-history-suggestions` and release v0.13.0.
2. Here: `MIN_ICA_VERSION = "0.13.0"`, update `docs/ica-contract.md` (the service, the new matching step) and add an entry in `docs/ica-change-requests.md`.

## Milestone 1: backend

1. `ica_api.py`: `async_get_item_suggestions(hass, entity_id, query=None, limit=None)`. Errors become `failure(...)` with translation keys, like the existing calls.
2. `domain/suggestions.py` (pure, tested):
   - `ItemSuggestion(name, group_id, source, count)`, with defensive parsing: skip entries without a name, and treat an unknown or missing group as 12.
   - `merge_with_usage(suggestions, usage_entries)`: Handla's own usage counts (`domain/usage.py`) only re-rank names already in the list. They do not add names. Keep it simple; if the ranking from ha-ica-todo is good enough, drop this step.
3. Service `handla.get_item_suggestions` (list, response only): `{"items": [{name, group_id, source, count}]}`. Only reads.

## Milestone 2: card

1. `api.ts`: `getItemSuggestions(hass, list)`.
2. `suggestions.ts` (pure, tested):
   - `splitTyped(text)`: split a leading quantity and unit ("2 st toal" → prefix "2 st ", query "toal"), using the same units as the item parser (st, förp, kg, hg, g, l, dl, cl, ml, msk, tsk, krm).
   - `filterSuggestions(all, query, max = 8)`: starts with > a word starts with > contains, keeping the server order within each, case-insensitive. Nothing for a query shorter than 2 characters.
   - Picking returns `prefix + name`, so the quantity typed is kept.
3. `handla-items.ts`:
   - Fetch the full list once, and again after about 10 minutes or when the card reconnects. The list is the same for every list of the account, so switching lists (also in the wide layout's sidebar) does not refetch. Keep it in memory, not in browser storage, because it is large and changes as items are added.
   - Show a dropdown under the add field with the name and a category chip (group names from i18n, as in the grouped view).
   - Keyboard: ↑/↓ moves, Enter picks the highlighted suggestion (or adds the text as typed when none is highlighted), Esc closes. Tapping picks. The dropdown closes on blur and after adding.
   - A pick goes through the existing add path, so the duplicate check ("finns redan") still applies.
   - Accessibility: `role="combobox"`, `aria-expanded`, `aria-activedescendant`, and a `listbox` with options.
4. Both layouts (`layout.ts`, panel view, from PR 7):
   - Build the dropdown inside `_renderAddForm()`, which both the narrow and the wide template use, so it works in both without changes to `_renderItems` or the side column.
   - `WideLayout` renders a different template when the width crosses 760 px, so the input element is recreated. Keep the dropdown state (open, highlighted index) in component properties, as `_text` already is, not in the DOM, so a resize or rotation does not lose it. Also put the focus back in the field if it was there.
   - In the wide layout, the dropdown is positioned under the field and is as wide as the main column. It must not overlap the side column and must not be clipped by the `.columns` grid.
   - The panel view is mostly used with a keyboard (tablet on the wall, computer), so the keyboard handling above matters more there. More height is available, so show up to 12 suggestions when wide and 8 when narrow.
5. A per-user switch "Visa förslag" (show suggestions) in `storage.ts`, on by default.
6. i18n: texts in sv and en.

## Later / open questions

- **Quick-add buttons.** These come from Handla's usage tracker today, which only sees adds through Handla. ha-ica-todo's history sees every add. Should the chips use `source: "history"` from the suggestions instead, and the usage tracker go? The wide layout's side column has room for a longer "Vanliga varor" (common items) list, built from the same history.
- **Offline or failed fetch.** Show no dropdown and add as typed, never block adding.
- **"Saknar kategori" (no category) hint:** show the chip in grey for group 12 so people can set the category right after adding.

## Tests

- Python: `domain/suggestions.py` as plain unit tests. The service with a mocked `ica.get_item_suggestions`, including errors and an old ha-ica-todo.
- Frontend (Vitest): `splitTyped`, `filterSuggestions`, keyboard handling, picking keeps the quantity, duplicate check on pick, the switch off means no dropdown, a failed fetch still allows adding. Both layouts: with `setWidth(800)` the dropdown is inside `[data-testid="wide"] .main`, and the text, the open dropdown and the highlighted row survive a switch between the layouts. Switching lists does not refetch.

## Docs

- README (en and sv): suggestions while typing.
- `docs/usage.md`: the new service.
