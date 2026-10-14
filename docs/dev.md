# Development and manual testing

Day-to-day development needs **no running Home Assistant**. Automated tests use an in-process HA core and mocks (`pytest tests/`). A real Home Assistant is used only for steps marked **Manual (real HA)** in `plan.md`, on the maintainer's own HA OS.

## Prerequisites on the real HA

- Home Assistant OS with HACS.
- `ha-ica-todo` **v0.10.0 or later** installed and configured (HACS custom repository `https://github.com/per-lennartsson/ha-ica-todo`, type *Integration*). It uses `zip_release`, so a published GitHub release with `ica.zip` is required for HACS to install it. Check *Settings → Devices & services → ICA* and that the integration's list entities exist.
- Access to the HA config folder for the manual install option (Samba, SSH or File editor add-on).

## Installing `inkop` for a manual check

Choose one.

### Option A: HACS custom repository (preferred, tests the real install path)

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/per-lennartsson/ha-ica-dashboard`, type *Integration*.
2. Open *Inköp* in HACS → *Download*. With no release published, HACS installs the default branch (`main`) and shows a commit hash as the version. Once releases exist it offers them. Unmerged feature branches are not reliably installable through HACS: use option B for those.
3. Restart Home Assistant.

To update after new commits: HACS → *Inköp* → *Redownload*, then restart.

### Option B: copy the folder (fast, any branch)

1. On the dev machine, check out the branch to test.
2. Copy `custom_components/inkop/` into the HA config folder `config/custom_components/inkop/` (Samba share, SSH `scp`, or File editor).
3. Restart Home Assistant.

To update: copy again and restart (or reload if only Python files in a loaded entry changed).

Do not install both options at once. Remove the folder, or the HACS install, before switching.

## Checking that it loaded

1. *Settings → Devices & services → Add integration → Inköp*, confirm. It is a single-instance integration, so a second attempt is refused. If `ha-ica-todo` is missing, older than v0.10.0, not set up or not loaded, the dialog stops with a message saying which (Swedish or English, depending on your language).
2. The entry should show as loaded with no errors. In *Settings → System → Logs* there is a normal warning that `inkop` is a custom integration, and **no errors** mentioning `inkop`.
3. To clean up: remove the Inköp entry from *Devices & services*.

4. To see the dependency check fail on purpose, disable the ICA integration (*Devices & services → ICA → ⋮ → Disable*) and try to add Inköp. Re-enable ICA afterwards. If Inköp is already added and ICA is not usable at startup, Inköp waits and retries, and *Settings → System → Repairs* shows an issue until ICA is back.

## Manual check: lists (plan step 1.3)

Needs `ha-ica-todo` v0.10.0 or later. Use *Developer tools → Actions*. Use a throwaway list name and clean up afterwards (see the rules below).

1. **Create:** run `inkop.create_list` with `title: TEST inkop <date>`. Within a few seconds the sensor *Inköp Status* goes `creating` → `idle`, the response shows the new `entity_id`, the list appears in the ICA app, and *Inköp Active list* switches to it. Note how many seconds it took.
2. **Default name:** run `inkop.create_list` with no title. The name should be "Att handla <dag> <månad>" (add `(2)` if you run it twice on the same day). Delete it afterwards.
3. **No double taps:** run `inkop.create_list` and, right away, once more. The second call is refused with "another list operation is still running".
4. **Item count:** add an item to the test list (todo card or ICA app). *Inköp Items to buy* changes while that list is active.
5. **Switch:** run `inkop.set_active_list` for another list, or use the select. Restart Home Assistant: the choice is kept.
6. **Delete:** run `inkop.delete_list` for the test list. Status goes `deleting` → `idle`, the list is gone from the ICA app, and the active list moves to another one.
7. **Failure message (optional):** disable the ICA integration and run `inkop.create_list`. You should get a clear error and the status sensor should show `error` until the next successful operation. Re-enable ICA afterwards.

Record the results (and the reload time in step 1) in `plan.md`.

## Manual check: items (plan step 1.4)

Use a throwaway list that is the active list (see the list check above). Run the services from *Developer tools → Actions*, with "Perform action" and look at the response.

1. **Add:** `inkop.add_item` with `item: 2 st gurka`. The item shows in the ICA app as quantity 2 st, name "gurka" (check that the quantity and unit were understood by ICA, not left in the name).
2. **Duplicate:** `inkop.add_item` with `item: Gurka`. The response says `added: false`, `duplicate: true` and lists the existing item; nothing is added. Run it again with `confirm_duplicate: true`: the item is added.
3. **Decimal/unit text:** add `1,5 l mjölk` and `500g nötfärs`; check quantity and unit in the ICA app.
4. **Tick:** `inkop.tick_item` with the item text (`gurka`), then with `ticked: false`. The item is struck over in the ICA app and back. Then with an item id from the response.
5. **Remove:** `inkop.remove_item` with an item text. It disappears from the ICA app.
6. **Clear:** tick two items, run `inkop.clear_ticked`. Only the ticked ones are removed; the response lists them.
7. **Ambiguous:** with two different open items containing "mjölk" (for example `1 l mjölk` and `2 st mjölk`), `inkop.remove_item` with `mjölk` should be refused and list both.
8. **During a reload:** run `inkop.create_list` and, while the status is `creating`, try `inkop.add_item` on the list being reloaded. Expect a clear "not available right now" message, not a crash.

Record anything surprising (especially how ICA treats the text) in `plan.md`.

## Rules for testing against the real ICA account

- Automated tests never use a real ICA account. Mocks only.
- Manual checks use **throwaway lists only**. Name them `TEST inkop <date>` so they are easy to spot. Never touch your real shopping lists.
- Clean up when done: delete the throwaway lists with `ica.delete_shopping_list` (Developer tools → Actions) or in the ICA app. Check the ICA app afterwards that none are left.
- Remember that creating or deleting a list reloads the ICA integration (about 4–5 s); entities are briefly unavailable.
- Do not paste tokens, PINs or personal IDs into issues, chat or files. Long-lived tokens never go in the repo.

## Frontend tooling (Docker)

Node is not installed on the host. All Node tooling runs in a Docker container. The exact `docker run` commands are added in plan step 1.7.

## Python checks (local)

```bash
source .venv/bin/activate
ruff check . && ruff format --check .
mypy custom_components
pytest tests/ -v
```
