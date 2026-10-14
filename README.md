# Inköp

Shared shopping lists for Home Assistant, on top of your ICA lists. Everyone in the household sees the same list, adds items in a second, and gets a notification when someone else adds something.

[Svenska](README.sv.md)

<p>
  <img src="docs/images/overview.png" alt="The Inköp card: list picker, add field, quick-add buttons, items and ticked items" width="300">
  <img src="docs/images/duplicate.png" alt="Asking before adding an item that is already on the list" width="300">
</p>

*Screenshots are a preview with sample data.*

## What it does

- **Shared ICA lists:** choose, create and delete lists. A new list gets a name like "Att handla 14 oktober".
- **Fast adding:** type an item and press Enter; the field stays ready for the next one. Quantities work: `2 st gurka`, `1,5 l mjölk`, `500 g nötfärs`.
- **Quick-add buttons:** with icons, based on what you actually add most.
- **Duplicate check:** "finns redan – lägga till igen?" before adding something that is already on the list.
- **Tick off, remove, clear ticked:** changes show up live on every device, also when made in the ICA app.
- **Notifications:** a push to the people you choose when someone *else* adds items (several quick adds become one message).
- **Phone shortcut:** a small card (or a badge) with the number of items left, that opens the shopping view.
- **Swedish and English.**

## Requirements

- Home Assistant 2026.9 or newer, with [HACS](https://hacs.xyz/).
- An ICA account, connected through [ha-ica-todo](https://github.com/per-lennartsson/ha-ica-todo) **v0.10.0 or newer** (a maintained fork of the ICA integration). Inköp checks this and tells you if it is missing.

## Installation

1. **Install ha-ica-todo** and set it up with your ICA account:
   HACS → ⋮ → *Custom repositories* → add `https://github.com/per-lennartsson/ha-ica-todo` as type *Integration* → download → restart Home Assistant → *Settings → Devices & services → Add integration → ICA*.
2. **Install Inköp** the same way: add `https://github.com/per-lennartsson/ha-ica-dashboard` as a custom repository (type *Integration*), download the latest release and restart Home Assistant.
3. *Settings → Devices & services → Add integration → **Inköp**.* That is all; no dashboard resource has to be added by hand.
4. *(Optional)* **Notifications:** *Devices & services → Inköp → Configure*. Choose who is told, and which `mobile_app_...` service reaches their phone.

## Dashboard

Add the card to a dashboard (for example a view with the path `inkop`):

```yaml
type: custom:inkop-card
```

For the phone dashboard, a small shortcut that shows how many items are left and opens that view when tapped:

```yaml
type: custom:inkop-shortcut
navigation_path: /lovelace/inkop
```

Everything about the cards, the badge option, entities, services and events is in [docs/usage.md](docs/usage.md).

## Good to know

- Creating or deleting a list makes the ICA integration reload, which takes a few seconds. The card shows progress and locks itself meanwhile, so nobody taps twice.
- The quick-add buttons are based on items added **through Inköp**. Items added directly in the ICA app are not counted (they do show up in the list).
- Notifications are sent for items added through Inköp, not for items added in the ICA app, and tapping a notification does not open the card yet.
- ICA ignores an empty unit, so renaming an item cannot remove its unit.
- Icons are Material Design Icons picked by a small list of Swedish grocery words; unknown items get a cart.

## Troubleshooting

- **The card says "Inköp körs inte":** check that ha-ica-todo (v0.10.0+) is installed and loaded, and look under *Settings → System → Repairs*.
- **The card does not show up:** restart Home Assistant after installing, then reload the page (in the phone app: *Settings → Companion app → Troubleshooting → Reset frontend cache*).
- **Something looks wrong after an update:** hard-refresh the browser. The card file is versioned, but browsers can be stubborn.

## Development

See [docs/dev.md](docs/dev.md) (tests need no running Home Assistant; Node tooling runs in Docker) and [plan.md](plan.md) for status.
