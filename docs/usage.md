# Using Inköp on a dashboard

The integration serves the cards itself (see "How the card reaches Home Assistant" in `docs/dev.md`), so there is no Lovelace resource to add. Three things are available.

## 1. The shopping card

The full view: list picker, add field, quick-add buttons, items.

```yaml
type: custom:inkop-card
# title: Handla      # optional, defaults to "Inköp"
```

Put it on its own dashboard view, for example `/lovelace/inkop` (view path `inkop`).

## 2. The shortcut card (for the phone dashboard)

A small card with the number of items left to buy and the list name. If you set `navigation_path`, tapping it opens that dashboard path, so it can send you to the shopping view above.

```yaml
type: custom:inkop-shortcut
navigation_path: /lovelace/inkop   # optional; without it the card is a plain count
# title: Handla                    # optional, defaults to the list name
```

- It shows the list **you** picked on this device (the picker in the full card), otherwise the household's active list.
- The count follows live.
- `navigation_path` must start with `/` (a path inside Home Assistant, not a web address).

## 3. A dashboard badge (alternative)

The count is also a normal sensor, `sensor.inkop_items_to_buy` (open items on the household's **active** list, with a cart icon). Use it as a badge in the dashboard header:

```yaml
badges:
  - type: entity
    entity: sensor.inkop_items_to_buy
    name: Inköp
    show_name: true
    tap_action:
      action: navigate
      navigation_path: /lovelace/inkop
```

Note the difference: the badge and `sensor.inkop_items_to_buy` always follow the household's active list, while the shortcut card follows the list each person picked on their own device.

## Other entities and services

- `sensor.inkop_lists`: all lists with item counts. `sensor.inkop_status`: idle / creating / deleting / error.
- `sensor.inkop_frequent_items`: the quick-add buttons (most added first, topped up with staples).
- `select.inkop_active_list`: the household's active list.
- Services (`inkop.*`): `add_item`, `tick_item`, `remove_item`, `clear_ticked`, `create_list`, `delete_list`, `set_active_list`, `suggest_list_name`, `get_top_items`.
- Event `inkop_item_added`: fired for every added item (item, list, who added it).
- Notifications: *Settings → Devices & services → Inköp → Configure*.
