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

## Manual check: frequent items (plan step 1.5)

1. Add a few items with `inkop.add_item` (for example `mjölk` three times with `confirm_duplicate: true`, `ägg` once). Run `inkop.get_top_items`: `mjölk` first with count 3 and a milk icon, then `ägg`. Items added directly in the ICA app are **not** counted (known limit).
2. In *Developer tools → States* check `sensor.inkop_frequent_items`: the state is the number of different items, and the attribute `items` lists name, count and icon.
3. Restart Home Assistant. The counts are still there.
4. Look at the icons for your most common groceries. Tell me which look wrong or are missing (the mapping is a small keyword list in `domain/icons.py`). The names are unverified against the Material Design Icons set until the card shows them (step 1.9).

## Manual check: notifications (plan step 1.6)

Needs two Home Assistant users, each with the companion app on their phone (so `notify.mobile_app_<phone>` services exist).

1. **Options:** *Settings → Devices & services → Inköp → Configure*. Choose both users, then pick each user's `mobile_app_...` service. Saving should end without errors.
2. **Other user is told:** as user A (for example in the Home Assistant app), run `inkop.add_item` with `item: mjölk`. About 20 seconds later user B's phone shows "A lade till mjölk i <lista>". User A gets nothing.
3. **Batching:** as user A add `ägg`, `smör` and `bröd` quickly. User B gets **one** message listing all three.
4. **Both ways:** repeat as user B; user A is told, B is not.
5. **Event:** in *Developer tools → Events*, listen to `inkop_item_added` and add an item: the event shows the item, list and who added it.
6. **Automation:** run `inkop.add_item` from *Developer tools → Actions* while logged in, and from an automation. Check who gets told in each case (an automation has no user, so everyone is told).
7. **Off:** configure again with nobody selected. Adding items sends nothing.

Notes for the check: the message follows the Home Assistant language (Swedish → "Embla lade till ..."). Tapping a notification does not open the shopping view yet; that comes with the card (steps 1.9 and 1.10).

## Manual check: list picker (plan step 1.8)

Build the card and install as described under "How the card reaches Home Assistant". Add the card to a dashboard (`type: custom:inkop-card`). Use a throwaway list; check on a **phone in the companion app** as well as on a computer.

1. **Picker:** the card lists your ICA lists with their open-item counts, and shows the household's active list. Pick another list: nothing is sent to ICA, and the choice is still there after you reload the page. A second user (other browser or phone) keeps their own choice.
2. **Create:** tap "Ny lista". The name is prefilled ("Att handla <dag> <månad>", numbered if taken) and the field is focused with the keyboard open. Create it. While it works (4–5 s, or longer) you see "Skapar listan…" and **nothing can be tapped**; afterwards the new list is selected. Try tapping "Skapa lista" twice quickly: only one list is created.
3. **Other devices:** while one device is creating, the other device's card also shows the progress and is locked.
4. **Delete:** tap "Ta bort lista": the confirmation names the list. "Avbryt" does nothing. "Ta bort" shows "Tar bort listan…" and then the list is gone from the card and from the ICA app.
5. **Errors:** with ICA disabled, try to create a list: the card shows a clear error and unlocks again.
6. **Not running:** disable the Inköp integration entry (or stop `ha-ica-todo`): the card shows the "Inköp körs inte … ha-ica-todo" message.
7. **Phone:** no sideways scrolling, buttons easy to hit, and the keyboard does not make the page zoom.

## Manual check: items view (plan step 1.9)

Use a throwaway list as the card's selected list, and check on a **phone in the companion app** as well as on a computer.

1. **Add with Enter:** type `2 st gurka` and press Enter/Send on the keyboard. The field empties, **stays focused and the keyboard stays open**, and the item shows as "lägger till…" and then as a normal row. Check in the ICA app that ICA read it as quantity 2, unit st, name gurka. Type several items quickly: all arrive, in order.
2. **Duplicate:** add `gurka` again. The card asks "“gurka” finns redan – lägga till igen?". "Hoppa över" drops it; "Lägg till igen" adds it. If you typed more items meanwhile, they wait for your answer.
3. **Quick-add buttons:** with no history you see staples (mjölk, bröd, ...) with icons. Tap one: it is added (and asks if it is already on the list). After a while the buttons you use most come first. **Look at the icons** and tell me which ones are wrong or show as empty squares (the icon names are unverified until now).
4. **Tick and remove:** tap the box to tick (the item is struck through and moves to the bottom), tap again to untick, tap × to remove. Check in the ICA app. A row is locked while its call runs.
5. **Clear ticked:** with ticked items, "Rensa avbockade (N)" appears and removes only those.
6. **Live:** add or tick an item in the ICA app (or on a second device): the card updates by itself within a few seconds.
7. **List reload:** create or delete another list: while ha-ica-todo reloads, the card shows "Listan är inte tillgänglig just nu…", typing is blocked, and afterwards the items come back **without reloading the page**.
8. **Views:** switch to another dashboard view and back: the items still update live.
9. **Phone:** no sideways scrolling, easy to hit the boxes and ×, the page does not zoom when the field is focused, and the keyboard does not cover the field.

## Rules for testing against the real ICA account

- Automated tests never use a real ICA account. Mocks only.
- Manual checks use **throwaway lists only**. Name them `TEST inkop <date>` so they are easy to spot. Never touch your real shopping lists.
- Clean up when done: delete the throwaway lists with `ica.delete_shopping_list` (Developer tools → Actions) or in the ICA app. Check the ICA app afterwards that none are left.
- Remember that creating or deleting a list reloads the ICA integration (about 4–5 s); entities are briefly unavailable.
- Do not paste tokens, PINs or personal IDs into issues, chat or files. Long-lived tokens never go in the repo.

## Frontend tooling (Docker)

Node is not installed on the host. Every Node command runs in a container through the wrapper `scripts/node.sh` (image `node:22-alpine`, the repository mounted at `/repo`, working directory `frontend/`, running as your user). Nothing is installed on the host; packages end up in `frontend/node_modules` (git-ignored).

```bash
./scripts/node.sh npm ci                 # install exactly what package-lock.json says
./scripts/node.sh npm run format         # prettier --write
./scripts/node.sh npm run lint           # eslint
./scripts/node.sh npm run typecheck      # tsc --noEmit
./scripts/node.sh npm run test           # vitest
./scripts/node.sh npm run test:coverage  # vitest with coverage
./scripts/node.sh npm run build          # builds custom_components/inkop/www/inkop-card.js
```

**Preview with mock data** (language and item-count buttons, no Home Assistant needed):

```bash
DOCKER_FLAGS="-p 5173:5173" ./scripts/node.sh npm run dev
# then open http://localhost:5173 and stop with Ctrl+C
```

If Prettier or another tool reports a bizarre syntax error right after a file was saved, run the command again: Docker's shared folder can show a half-written file for a moment.

Adding or updating a package is an install: ask the maintainer first, then run for example `./scripts/node.sh npm install <package>` and commit `package.json` and `package-lock.json`.

### How the card reaches Home Assistant

`npm run build` writes `custom_components/inkop/www/inkop-card.js` (git-ignored for now; whether to commit it or attach it to releases is decided in plan step 1.11). When Inköp starts, `card.py` serves that file at `/inkop/inkop-card.js` and tells the frontend to load it in every dashboard, so **no Lovelace resource has to be added by hand**. If the file is missing, Inköp logs a warning and everything else keeps working.

## Manual check: card loads (plan step 1.7)

1. Build the card (above), then install `inkop` on your Home Assistant by copying `custom_components/inkop/` **including the `www/` folder** (see "Installing"), and restart.
2. Open any dashboard in the browser and, in the developer tools, check that `/inkop/inkop-card.js?v=0.1.0` was loaded (status 200).
3. Edit a dashboard → *Add card* → search for "Inköp": the card is listed. Add it (or use `type: custom:inkop-card`). It shows "Inköp", "Inköpskortet är laddat.", the number of items from `sensor.inkop_items_to_buy`, and the version.
4. Switch your user profile language between Svenska and English: the card text follows.
5. Check it on the phone in the companion app (it may need a refresh the first time: pull to refresh, or *Settings → Companion app → Troubleshooting → Reset frontend cache*).

## Python checks (local)

```bash
source .venv/bin/activate
ruff check . && ruff format --check .
mypy custom_components
pytest tests/ -v
```
