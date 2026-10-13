# ha-ica-todo contract

What `inkop` may rely on from [ha-ica-todo](https://github.com/per-lennartsson/ha-ica-todo). Source of truth is the code; this file is a reviewed snapshot. Re-verify when raising the minimum version.

- Snapshot: local clone at `main`, commit `6c45aa7` ("bump version to v0.9.0")
- Domain: `ica`, `iot_class: cloud_polling`, `config_flow: true`, no HA `dependencies`
- Version: `manifest.json` has `"version": "v0.9.0"` (note the leading `v`; strip it before comparing versions). The release workflow writes the real version into `manifest.json` and attaches `ica.zip`.
- Install: HACS custom repository, type *Integration*, `hacs.json` has `zip_release: true`, `filename: ica.zip`. Config via UI (personal ID, PIN, number of random recipes, JSON-in-description toggle). Polling default 5 min.
- Mismatch to fix in the repo: README, `manifest.json` (`codeowners`, `documentation`, `issue_tracker`) and the blueprint still point to `lazytarget/ha-ica-todo`, not the fork. See `docs/ica-change-requests.md`.

## Entities

| Entity | Unique ID | Notes |
|---|---|---|
| One `todo` entity per tracked list | `{config_entry_id}-{list_offline_id}` | Name is `ICA <list title>`, so entity ID is typically `todo.ica_<slug>`. Icon `mdi:cart`. |
| Favourites | `{config_entry_id}-baseitems` | `todo.ica_favorite_articles`. Exclude it when listing shopping lists. |

- Features: create, update and delete items; item description only if the "JSON data in description" option is on.
- `TodoItem.uid` = ICA row `offlineId`. `status` = `completed` if `isStrikedOver`, else `needs_action`. `due` = valid-to date of the linked offer, if any.
- `TodoItem.summary` = `"<quantity> <unit> <name>"`, e.g. `2 st Gurka`, `1,5 l mjölk` (Swedish decimal comma; quantity omitted if none).
- The list's offline ID is **not exposed as an attribute**. The only way to get it is the entity registry `unique_id` (strip `"{config_entry_id}-"`), which is what the integration's own delete service does.
- The ICA list comment is not exposed.

## Item text parsing (verified in `coordinator.py`)

`<quantity> [<unit>] <name>`, case-insensitive, regex `_SUMMARY_RE`:
- Units, whole word only: `st, förp, kg, hg, g, l, dl, cl, ml, msk, tsk, krm`; stored lower-case.
- Quantity accepts `.` or `,`, sent to ICA as a number, must be > 0.
- Range `2–3` or `2-3`: the higher number is kept.
- Text without a leading number is kept as-is as the name.
- Ticking or renaming an item parses the summary back. Quantity and unit are always sent, **but a missing unit is sent as null and ICA ignores it**, so a rename cannot remove a unit.
- Article group is assigned automatically from the product name.

## Services (domain `ica`)

Confirmed against `services.yaml` / `services.py`. Differences from the project brief are in **bold**.

| Service | Fields | Response |
|---|---|---|
| `ica.create_shopping_list` | **`integration` (config entry ID, required)**, `title` (required), `comment` (optional), `track` (default true) | optional: `{success, offline_id, title, tracked, data}`. If tracked, **the integration reload is only scheduled**; the call returns before the new entity exists. `offline_id` is the ID we sent, ICA may store it upper case. |
| `ica.delete_shopping_list` | `entity_id` (an ICA list entity, not favourites) | optional: `{success, entity_id, offline_id}`. Deletes in ICA, untracks (case-insensitive), removes the entity from the registry, schedules reload. |
| `ica.refresh_all` | none | optional: `{updated_integrations}`. Errors if an entry is not loaded. |
| `ica.upsert_shopping_list` | `entity_id`, `rows` (text or JSON, multiple), `conflict_mode` (`APPEND` default, `MERGE`, `IGNORE`) | entity service |
| `ica.add_offers_to_shopping_list` | `entity_id`, `offer_ids` (multiple), `conflict_mode` | entity service |
| `ica.get_baseitems` | `integration` | response only: `{success, data: [...]}` |
| `ica.add_baseitem` | `integration`, `identifier` (name or barcode) | optional: `{success, data}` |
| `ica.lookup_product` | `identifier` (EAN) | response only |
| `ica.get_recipe` | `recipe_id` | response only |

- Errors: not-loaded entry raises `HomeAssistantError` (`not_loaded`); unknown entity raises `ServiceValidationError`.
- `MERGE` sums quantities with unit conversion (kg/g, l/dl/cl/ml, count units `st` and `förp` are separate groups); `IGNORE` leaves the existing row. `inkop` still needs its own case-insensitive duplicate prompt, since these modes decide silently.

## Events

- Only `ica_new_offers` (new offers in favourite stores). **No event is fired when items or lists change.** Item changes must be observed through `todo` entity state or the coordinator; "who added" must come from the HA service-call context of `todo.add_item` / `ica.upsert_shopping_list`.

## Behaviour `inkop` must handle

1. **Reload after create/delete (about 4–5 s):** entities vanish and reappear. Wait for the new entity in the entity registry/state machine (event-based), with a timeout; keep the UI in a busy state meanwhile.
2. List IDs are upper case from ICA: compare case-insensitively.
3. A tracked list deleted in the ICA app is silently untracked on next load; the entity disappears.
4. Entity availability may flicker during reload and token refresh (auth refresh on expiry or HTTP 401).
5. The fork's behaviour is only guaranteed from the minimum version we declare. Set it after the change requests below are released.

## Minimum version

Proposed: `>= v0.9.0` (first version with create/delete and the parsing fixes). Raise it if a change request is released and needed.
