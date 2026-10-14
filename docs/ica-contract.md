# ha-ica-todo contract

What `handla` may rely on from [ha-ica-todo](https://github.com/per-lennartsson/ha-ica-todo). Source of truth is the code; this file is a reviewed snapshot. Re-verify when raising the minimum version.

- Snapshot: branch `list-events-and-metadata`, commit `c2fe1f1` (v0.10.0). Re-check against the merged/released code before relying on it.
- Domain: `ica`, `iot_class: cloud_polling`, `config_flow: true`, no HA `dependencies`
- Version: `manifest.json` has `"version": "v0.10.0"` (note the leading `v`; strip it before comparing versions). The release workflow writes the real version into `manifest.json` and attaches `ica.zip`.
- Install: HACS custom repository, type *Integration*, `hacs.json` has `zip_release: true`, `filename: ica.zip`. Config via UI (personal ID, PIN, number of random recipes, JSON-in-description toggle). Polling default 5 min.
- Repo metadata (README, manifest, blueprint) points to the fork since v0.10.0, with credit to upstream kept.

## Entities

| Entity | Unique ID | Notes |
|---|---|---|
| One `todo` entity per tracked list | `{config_entry_id}-{list_offline_id}` | Name is `ICA <list title>`, so entity ID is typically `todo.ica_<slug>`. Icon `mdi:cart`. |
| Favourites | `{config_entry_id}-baseitems` | `todo.ica_favorite_articles`. Exclude it when listing shopping lists. |

- Features: create, update and delete items; item description only if the "JSON data in description" option is on.
- `TodoItem.uid` = ICA row `offlineId`. `status` = `completed` if `isStrikedOver`, else `needs_action`. `due` = valid-to date of the linked offer, if any.
- `TodoItem.summary` = `"<quantity> <unit> <name>"`, e.g. `2 st Gurka`, `1,5 l mjölk` (Swedish decimal comma; quantity omitted if none).
- Since v0.10.0 each list entity has the state attributes `offline_id` (ICA offline ID), `config_entry_id` and `comment` (ICA list comment or `null`). The favourites entity has none of them. Use these instead of parsing the registry `unique_id`.

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
| `ica.create_shopping_list` | **`integration` (config entry ID, required)**, `title` (required), `comment` (optional), `track` (default true) | optional: `{success, offline_id, title, tracked, data}`. If tracked, **the integration reload runs in the background**; the call returns before the new entity exists. Wait for the `ica_lists_changed` event. `offline_id` is the ID we sent, ICA may store it upper case. |
| `ica.delete_shopping_list` | `entity_id` (an ICA list entity, not favourites) | optional: `{success, entity_id, offline_id}`. Deletes in ICA, untracks (case-insensitive), removes the entity from the registry, reloads in the background and then fires `ica_lists_changed`. |
| `ica.refresh_all` | none | optional: `{updated_integrations}`. Errors if an entry is not loaded. |
| `ica.upsert_shopping_list` | `entity_id`, `rows` (text or JSON, multiple), `conflict_mode` (`APPEND` default, `MERGE`, `IGNORE`) | entity service |
| `ica.add_offers_to_shopping_list` | `entity_id`, `offer_ids` (multiple), `conflict_mode` | entity service |
| `ica.get_baseitems` | `integration` | response only: `{success, data: [...]}` |
| `ica.add_baseitem` | `integration`, `identifier` (name or barcode) | optional: `{success, data}` |
| `ica.lookup_product` | `identifier` (EAN) | response only |
| `ica.get_recipe` | `recipe_id` | response only |

- Errors: not-loaded entry raises `HomeAssistantError` (`not_loaded`); unknown entity raises `ServiceValidationError`.
- `MERGE` sums quantities with unit conversion (kg/g, l/dl/cl/ml, count units `st` and `förp` are separate groups); `IGNORE` leaves the existing row. `handla` still needs its own case-insensitive duplicate prompt, since these modes decide silently.

## Events

| Event | When | Payload |
|---|---|---|
| `ica_new_offers` | New offers found in favourite stores | offer data |
| `ica_lists_changed` | After `create_shopping_list` (with `track`) or `delete_shopping_list` has reloaded the entry. Also fired immediately for an untracked create. | `{config_entry_id, created: [offline_id], deleted: [offline_id], entities: {offline_id: entity_id}}` |
| `ica_list_items_changed` | A refresh finds added, removed or changed rows compared with the previous data. Not fired on the first load of a list. | `{entity_id, offline_id, added: [{uid, summary}], removed: [uid], changed: [{uid, summary, changed_props}]}` |

- `ica_lists_changed` is **also fired if the reload fails**, then with an empty or partial `entities`. Treat a missing entity as failure, not as "keep waiting". `created` holds the ID we sent; ICA may store it upper case, so match case-insensitively.
- `ica_list_items_changed` is fired for changes made through HA as well as in the ICA app, and carries **no user or context**. It cannot tell who changed an item. "Who added" must come from the HA service-call context of `todo.add_item` / `ica.upsert_shopping_list`. Use the event for changes made outside HA, and avoid notifying twice for changes `handla` made itself.
- `changed` only reports fields present in the new row. An item that loses its quantity or unit is not reported as changed.

## Behaviour `handla` must handle

1. **Reload after create/delete (about 4–5 s):** entities vanish and reappear. Keep the UI in a busy state until `ica_lists_changed` arrives, with a timeout as a safety net (the event fires after the reload even on failure, but not if HA restarts).
2. List IDs are upper case from ICA: compare case-insensitively.
3. A tracked list deleted in the ICA app is silently untracked on next load; the entity disappears.
4. Entity availability may flicker during reload and token refresh (auth refresh on expiry or HTTP 401).
5. The fork's behaviour is only guaranteed from the minimum version we declare (below).

## Minimum version

`>= v0.10.0` (first version with `ica_lists_changed`, `ica_list_items_changed` and the list attributes). v0.9.0 had create/delete and the parsing fixes but none of these, so it is not supported. The constant `MIN_ICA_VERSION` in `custom_components/handla/const.py` matches this. Raise this again only if a later ha-ica-todo change is released and needed.
