# Using Handla on a dashboard

The integration serves the cards itself (see "How the card reaches Home Assistant" in `docs/dev.md`), so there is no Lovelace resource to add. Three things are available.

## 1. The shopping card

The full view: list picker, add field, quick-add buttons, items.

```yaml
type: custom:handla-card
# title: Handla      # optional, defaults to "Handla"
```

Put it on its own dashboard view, for example `/lovelace/handla` (view path `handla`).

## 2. The shortcut card (for the phone dashboard)

A small card with the number of items left to buy and the list name. If you set `navigation_path`, tapping it opens that dashboard path, so it can send you to the shopping view above.

```yaml
type: custom:handla-shortcut
navigation_path: /lovelace/handla   # optional; without it the card is a plain count
# title: Handla                    # optional, defaults to the list name
```

- It shows the list **you** picked on this device (the picker in the full card), otherwise the household's active list.
- The count follows live.
- `navigation_path` must start with `/` (a path inside Home Assistant, not a web address).

## 3. A dashboard badge (alternative)

The count is also a normal sensor, `sensor.handla_items_to_buy` (open items on the household's **active** list, with a cart icon). Use it as a badge in the dashboard header:

```yaml
badges:
  - type: entity
    entity: sensor.handla_items_to_buy
    name: Handla
    show_name: true
    tap_action:
      action: navigate
      navigation_path: /lovelace/handla
```

Note the difference: the badge and `sensor.handla_items_to_buy` always follow the household's active list, while the shortcut card follows the list each person picked on their own device.

## Managing the quick-add buttons

Tap **Hantera** (Manage) after the quick-add buttons. The view lists everything Handla has counted, not only the buttons:

- **Remove:** ✕ forgets an item. If you add it again later it starts counting from 1.
- **Merge:** tick two or more items (for example "Tomat" and "Tomater"), tap **Slå ihop** and choose which name stays (the most used is preselected). The counts are added together, and from then on adding "Tomat" counts toward "Tomater". The merged-away names do not come back as buttons.
- **Add:** type a name and tap **Lägg till** to pin it. Pinned items always come first, even if you have never added them.

Changes are shared by everyone using the same Handla, like the counts themselves.

## Other entities and services

- `sensor.handla_lists`: all lists with item counts. `sensor.handla_status`: idle / creating / deleting / error.
- `sensor.handla_frequent_items`: the quick-add buttons (most added first, topped up with staples).
- `select.handla_active_list`: the household's active list.
- Services (`handla.*`): `add_item`, `tick_item`, `remove_item`, `clear_ticked`, `create_list`, `delete_list`, `set_active_list`, `suggest_list_name`, `get_top_items`, `remove_quick_item`, `add_quick_item`, `merge_quick_items` (`sources`, `target`).
- `sensor.handla_ai`: `off` / `ready` / `unavailable`; `handla.ai_extract_items` exists only while AI is on. See [ai.md](ai.md).
- Event `handla_item_added`: fired for every added item (item, list, who added it).
- Notifications: *Settings → Devices & services → Handla → Configure*.
