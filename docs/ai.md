# AI: add items from pasted text (optional)

Paste a recipe, a meal plan or a message, and Handla suggests the shopping items. You review them (untick, edit) before anything is added. This is **off by default**: with it off, no AI interface is shown, no AI service exists and nothing is sent to any provider.

## Set it up

1. **Add an AI provider to Home Assistant** that offers an *AI Task* entity (*Settings → Voice assistants / Devices & services*). Handla works with any provider; it does not need Anthropic. You can check that you have one under *Settings → Devices & services → Entities*, filter `ai_task.`.
2. *Settings → Devices & services → Handla → Configure → **AI (optional)***:
   - **Use AI:** on.
   - **AI Task entity:** the provider that should read the texts. Required when AI is on.
   - **Daily health check:** optional, see [Monitoring](#monitoring).
3. Reload the dashboard. A button **Lägg till från text (AI)** / *Add from text (AI)* appears above the add field.

`sensor.handla_ai` shows the state: `off`, `ready`, or `unavailable` (AI is on, but the chosen entity is missing or unavailable). The card shows the button only when it is `ready`.

## Using it

1. Tap the button, paste the text, tap **Hitta varor** / *Find items*. This takes a few seconds.
2. Review the suggestions. Items **already on the list** are marked ("finns redan: …") and start unticked. Untick what you do not want; edit the text if needed (`2 st gurka`, `500 g nötfärs`).
3. Tap **Lägg till valda**. Items that fail to add stay in the review with the error, so you can try again.

What the AI is asked to do: short Swedish names, quantity first, the same item mentioned twice merged into one line, and things you always have at home (salt, pepper, water) skipped. The prompt and the output format are in [`domain/extraction.py`](../custom_components/handla/domain/extraction.py). Nothing is added to the list until you confirm.

Limits: at most 20 000 characters of text, and at most 100 suggested items.

## What is sent where

The pasted text is sent to **the AI provider you chose** (and nothing else: no list contents, no names). Check the provider's own terms if the texts are private. The text is not stored by Handla.

## Monitoring

If a call to the provider fails (for example credits ran out, an invalid key or the service is down), Handla sends one push to the people chosen under *Configure → Notifications*, with the error. While the provider keeps failing you are not told again until it has worked once, or after 24 hours. Nobody chosen? Then the error is only written to the Home Assistant log.

The optional **daily health check** sends one tiny request (a few tokens) to the provider every 24 hours, so you find out about a problem before someone pastes a recipe. It uses the same notification.

There is no way to ask a provider how much credit is left, so Handla only detects failures when a call fails.

## Anthropic (Claude) notes

- The result is a list of short lines, but a long text gives a long answer. Home Assistant's `ai_task.generate_data` has **no `max_tokens` field**, so Handla cannot set it per request. The limit belongs to the provider's configuration: for Anthropic, the **Maximum tokens** setting of the AI Task entry (*Devices & services → Anthropic → the AI Task entry → ⚙*). If long lists end abruptly or items are missing, raise it. Handla cannot detect a cut-off answer, so a too-low limit shows up as a short list, not as an error.
- Anthropic has no API for the remaining credit, so a failure is only seen when a call fails (the daily check makes that happen earlier).
- Use a small, fast model for the AI Task entry; reading a recipe does not need a large one.

## Services and entities

- `sensor.handla_ai`: `off` / `ready` / `unavailable`, with the chosen entity in the attribute `provider`.
- `handla.ai_extract_items` (only while AI is on): `text` (required) and optional `entity_id` (the list to compare with; default the active list). Returns `items` (each with `item`, `on_list`, `existing`, `selected`, `quantity`, `unit`) and `count`. It adds nothing; add the chosen ones with `handla.add_item`.

## Troubleshooting

- **No button on the card:** *Configure → AI (optional)* must be on with an entity chosen, and `sensor.handla_ai` must say `ready`. Reload the dashboard.
- **`unavailable`:** the chosen AI Task entity is missing or unavailable; check the provider integration.
- **"The AI provider failed: …":** the message comes from the provider (key, credits, rate limit). Fix it there.
- **"answered in an unexpected way":** try again; if it keeps happening, try another model.
- **Items missing from a long text:** see the Anthropic notes above (token limit), or paste the text in parts.
