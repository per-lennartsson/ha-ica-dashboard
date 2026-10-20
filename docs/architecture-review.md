# Arkitekturgranskning mot CLAUDE.md

Datum: 2026-10-20. Granskad: `custom_components/handla/` (≈3 100 rader Python), `frontend/src/` och `tests/`.
Metod: läsning av koden för arkitekturprinciperna i CLAUDE.md ("Architecture", "Code conventions", "Rules"). Inga tester eller linters kördes, så resultatet gäller struktur och inte körbarhet. Radhänvisningarna är kontrollerade mot koden vid skrivtillfället, men några avser spann och kan glida när filerna ändras.

## Sammanfattning

Grundarkitekturen följer principerna. Domänlogiken är ren Python, all kommunikation med ICA går via `ica.*`- och `todo.*`-tjänster, AI-modulen är avstängd som standard och kortet är tunt. De tydligaste avvikelserna är:

1. Användarsynliga texter ligger hårdkodade i logiken, trots att "all user-visible strings go through translations".
2. `ica.*`- och `ai_task.*`-anrop ligger utspridda i stället för i ett separat I/O-lager.
3. `HandlaCoordinator` har för många ansvar.
4. Några felhanteringar loggar eller sväljer fel i stället för att visa dem för användaren.

## I linje med principerna

| Princip | Hur koden följer den | Var |
|---|---|---|
| Ren domänlogik utan HA | Inga `homeassistant`-importer i `domain/` (kontrollerat med grep). Modulerna är små och rena: parsning, dubblettregler, namn, listor, användning. | `custom_components/handla/domain/*.py`, `domain/__init__.py:1` |
| Domänlogiken testbar utan HA | En testfil per domänmodul. | `tests/test_domain_*.py` |
| Aldrig anropa ICA direkt | Bara `ica.create_shopping_list` / `ica.delete_shopping_list` och HA:s `todo.*`. Inga ICA-uppgifter eller tokens hanteras. Kortet anropar bara `handla.*`. | `coordinator.py:313`, `coordinator.py:334`, `todo_api.py:30` |
| Tunt I/O-lager för todo | `todo_api.py` är ett litet lager med ett enda felmappande anropsställe (`_call`) som översätter fel till `todo_failed`. | `todo_api.py:23-43` |
| AI valfritt och av som standard | `get_ai_config` kräver `is True`, så felaktiga värden räknas som av. AI-tjänsten registreras bara när modulen är på och tas bort när den stängs av. Kortet visar AI-UI bara när sensorn är `ready`. | `ai.py:33`, `services.py:200-225`, `__init__.py` (`async_setup_entry`), `frontend/src/ai.ts` (`isAiReady`) |
| Failure-detection via fel, inte saldo | `AiMonitor` räknar fel, meddelar en gång per avbrott och återställer vid första lyckade anrop. | `ai_monitor.py:61-97`, `domain/ai_health.py` |
| Push i stället för polling | `update_interval=None`. Coordinatorn lyssnar på registry-, state- och `ica_lists_changed`-händelser. | `coordinator.py` (`async_start`, rad 112) |
| Missad händelse tolereras | `ListsChangedWaiter` prenumererar *innan* ICA-anropet görs, så en snabb händelse missas inte. | `events.py:14-40`, `coordinator.py:280-311` |
| Skydd mot dubbelklick | `_begin` vägrar starta en andra skapa/ta bort-operation och statussensorn visar framsteg. | `coordinator.py:261-267` |
| Användar-ID från HA-kontext | Avsändaren hämtas från `call.context.user_id` och inte genom gissning. Notiser går aldrig till den som lade till. | `services.py:101-111`, `coordinator.py:185-210`, `domain/notify.py` |
| Lång text som servicedata | Inklistrad text går som tjänsteparameter. Storleken begränsas med `MAX_TEXT_LENGTH`. Stora attribut utesluts från historiken med `_unrecorded_attributes`. | `ai.py:111-125`, `sensor.py:91`, `sensor.py:111` |
| UI-tillstånd per användare i kortet | Vald lista och liknande lagras i webbläsaren, inte i helpers. Hushållets aktiva lista lagras i en `Store` hos integrationen. | `frontend/src/storage.ts`, `coordinator.py:225` |
| Felöversättning | Fel är `HomeAssistantError` / `ServiceValidationError` med `translation_key`. Inga rå-strängar i undantagen. | `coordinator.py` (`_failure`), `shopping.py:38`, `ai.py:59` |
| Stabilt kontrakt mot ha-ica-todo | Beroendekontrollen körs bara i `async_setup_entry`, så att ICA:s omladdning inte rapporteras som fel. Versionsminimum finns i domänen. | `__init__.py` (`async_setup_entry`), `dependency.py`, `domain/versions.py` |
| Kort utan affärslogik (i huvudsak) | `api.ts` är ett tunt anrop mot `handla.*`. Dubblettkontrollen görs i backend (`shopping.py:56-71`), och kortet frågar bara användaren. Parsning av servicesvar är defensiv. | `frontend/src/api.ts`, `frontend/src/handla-items.ts:325-340` |
| Tester skrivs tillsammans med koden | Pytest-filer finns för varje modul (utom de som nämns nedan) och Vitest-filer för varje frontendmodul. | `tests/`, `frontend/src/*.test.ts` |

## Brott mot principerna

### 1. Hårdkodade användarsynliga texter i logiken (hög)

CLAUDE.md: "All user-visible strings go through translations. Never hard-code Swedish text in logic." Följande texter ligger i koden:

- `domain/notify.py:36-55` – `build_message` har en egen `_swedish()`-gren med "Nytt på …" och en engelsk gren. Texterna är användarsynliga pushnotiser som inte går via `strings.json`/`translations/`. Språk utöver sv/en faller tyst till engelska.
- `domain/ai_health.py:40-55` – `build_failure_message` gör samma sak för felnotisen ("Lägg till från text är inte tillgängligt …").
- `domain/naming.py:21-36` (+ `SWEDISH_MONTHS`) – standardnamnet "Att handla <dag> <månad>" är fast på svenska. Det är specat så, men namnet visas för användaren oavsett HA-språk.
- `ai_monitor.py:20` – `HEALTH_INSTRUCTIONS = "Svara med ordet OK."` och `HEALTH_TASK_NAME` är hårdkodade. Det är inte användarsynligt, men det är svensk text i logiken.
- `domain/extraction.py:41-56` – hela AI-prompten är på svenska i koden. Det är avsiktligt ("prompt lives in version control") och inte ett brott i sig, men prompten är en användarpåverkande sträng som inte går att byta språk på.

Förslag: lägg notistexterna i `translations/*.json` (HA stöder `async_get_translations`) eller i en tabell i `const.py` med tydlig koppling till språkfiler. Prompten kan vara kvar som version-kontrollerad konstant, men dokumentera undantaget i CLAUDE.md.

### 2. I/O ligger inte i ett separat lager (medel–hög)

CLAUDE.md: "All I/O (HA service calls, AI Task calls) lives in a separate layer."

- `todo_api.py` följer regeln för `todo.*`, men det finns inget motsvarande lager för `ica.*` eller `ai_task.*`.
- `coordinator.py:_call_create` (`coordinator.py:313-332`) och `async_delete_list` (`coordinator.py:334-360`) anropar `hass.services.async_call(ICA_DOMAIN, …)` direkt. Samma modul innehåller tillståndsmaskin, händelselyssning och orkestrering.
- `ai.py:_ask_provider` (`ai.py:79-108`) och `ai_monitor.py:async_health_check` (`ai_monitor.py:73-97`) gör var sin `ai_task.generate_data`-anrop med samma felbehandling. Det är två nästan identiska I/O-anrop på olika ställen.
- `notify.py:async_notify_users` (`notify.py:34-48`) anropar `notify.*` direkt i samma modul som batch-logiken (`AddNotifier`).
- `card.py` blandar I/O mot Lovelace-resurser med registreringslogik, men det är ett naturligt undantag.

Förslag: en `ica_api.py` (create/delete) och en `ai_api.py` (`generate_data`) analogt med `todo_api.py`. Då får felmappningen ett enda ställe och koordinatorn kan testas med enklare fakes.

### 3. `HandlaCoordinator` gör för mycket (medel)

CLAUDE.md: "Functions do one thing."

`coordinator.py` (370 rader) ansvarar för:
- att härleda listor ur entitetsregistret (`_compute`, `_read_lists`, `coordinator.py:123-165`),
- aktiv lista och dess lagring (`async_set_active*`, `_set_preferred`),
- statusmaskin för skapa/ta bort (`_begin`, `_set_status`),
- själva ICA-orkestreringen (`async_create_list`, `async_delete_list`),
- användningsstatistik, notis och eventutskick vid tillagd vara (`async_item_added`, `coordinator.py:185-210`),
- ägandet av `UsageTracker`, `AddNotifier` och `AiMonitor` (`coordinator.py` (`__init__`)).

Konkreta fall:
- `async_create_list` (`coordinator.py:280-311`) gör sju saker: statusbyte, hitta ICA-entry, namnval, väntan på händelse, felklassificering, aktivering och resultatbygge. Den kräver fortfarande kommentarer för att följas.
- `async_item_added` skriver användning, uppdaterar lyssnare, hämtar användare, avfyrar händelse och köar notis. Den bör bo i en egen komponent som `services.add_item` anropar, eftersom `add_item`-handlern i `services.py:101-111` redan själv sammanför `shopping.async_add_item` och `coordinator.async_item_added`.
- `services.async_register_services` (`services.py:87-198`) är en ~120 raders funktion med nästlade handlers och tre registreringsloopar. Schemadefinitionerna (`services.py:17-62`) är rimliga, men registreringen är svår att överblicka.

Förslag: bryt ut `ListRegistry` (härledning + aktiv lista) och `ListOperations` (skapa/ta bort + status). Låt coordinatorn bara äga `data` och lyssnare.

### 4. Felhantering som loggar eller sväljer i stället för att visa (medel)

CLAUDE.md: "Never swallow exceptions, and surface failures to the user with a clear message."

- `notify.py:46` – om ett `notify.*`-anrop misslyckas loggas bara en varning. Ingen annan får veta det. För ett push-flöde är det rimligt, men det strider mot ordalydelsen och bör vara ett medvetet, dokumenterat undantag (eller lyftas som reparationsärende / statusattribut).
- `card.py:54`, `card.py:68` – misslyckad registrering av dashboard-resurs loggas bara; kortet kan då saknas utan att användaren ser något.
- `frontend/src/handla-card.ts:213-215` – `suggestListName` fångar *alla* fel med tom `catch`. Kommentaren förklarar det, men felet loggas inte ens.
- `frontend/src/items.ts:93-95` – tom `catch` vid avprenumeration (motiverad i kommentar, lågt värde).
- `ai_monitor.py:61-71` – om ingen mottagare är konfigurerad loggas AI-felet bara. Det är dokumenterat beteende men betyder att ett AI-avbrott kan förbli osynligt tills någon anropar tjänsten.
- `events.py:57-60` – `TimeoutError` blir `None`. Anroparna översätter det till `create_timeout`/`delete_timeout`, så det är ett korrekt mönster.

### 5. Cirkulärt beroende och felplacerad konfiguration (låg–medel)

- `ai.py` importerar `AiMonitor` bara under `TYPE_CHECKING` (`ai.py:29-30`) medan `ai_monitor.py` importerar `get_ai_config`/`get_health_check` från `ai.py` (`ai_monitor.py:12`). Beroendet går i en ring och hålls uppe av ett `TYPE_CHECKING`-trick.
- `ai.py` har docstringen "The optional AI module's switch and provider, read from the config entry" men innehåller även orkestreringen `async_extract_items`, providerlogik och statusbedömning. Konfigurationsläsning (`get_ai_config`, `get_health_check`) hör hemma i en liten modul som både `ai.py` och `ai_monitor.py` kan importera. Samma sak gäller `get_recipients` i `notify.py` som `ai_monitor.py` importerar.
- `notify.py:event_data` (`notify.py:102-116`) bygger payloaden för `handla_item_added` och är ren logik som borde ligga i `domain/notify.py`.

### 6. Stark koppling till ha-ica-todos interna konventioner (låg)

- `coordinator.py:_read_lists` (`coordinator.py:130-165`) identifierar ICA-listor via registrets `platform`, ett `-baseitems`-suffix på `unique_id` och fallback `unique_id.partition("-")[2]`. Primärt används attributet `offline_id`, i linje med `docs/ica-contract.md:21`, men fallbacken och suffixet är en tyst koppling till ha-ica-todos interna format.
- Detta är i praktiken oundvikligt eftersom inget API finns, men det borde samlas på ett ställe tillsammans med kontraktet i `docs/ica-contract.md`.

### 7. Prestanda- och korrekthetsdetaljer som bryter mot andan i "event-driven" (låg)

- `coordinator.py:112` lyssnar på *alla* `state_changed`-händelser i hela HA och filtrerar sedan i callbacken. `sensor.py:149` använder `event_filter` för samma sak och är bättre. `coordinator.py:_read_lists` itererar dessutom hela entitetsregistret vid varje relevant ändring.
- `shopping.py:async_add_item` (`shopping.py:56-76`) gör läs-kontrollera-skriv i tre steg utan lås. Två användare som lägger till samma vara samtidigt kan båda passera dubblettkontrollen. ICA har ingen atomär operation, så det är en känd begränsning – men den är inte dokumenterad.
- `services.py:_coordinator` (`services.py:65-71`) antar exakt en config entry (`entries[0]`). Det är rimligt för en integration med `single_instance_allowed`, men antagandet bör vara explicit.

### 8. Tillstånd och "inget globalt tillstånd" (låg)

CLAUDE.md: "No global state. Pass configuration as arguments."

- `card.py:82` använder `hass.data[DOMAIN]["card_registered"]` som flagga. Det är HA:s vanliga mönster, men flaggan lever utanför `runtime_data` och återställs inte vid `async_unload_entry`. Efter en omladdning registreras kortet inte om (avsiktligt, eftersom statiska sökvägar inte kan avregistreras), men det är värt en kommentar.
- Tjänsterna registreras i `async_setup` (global registrering) men agerar på en entry (`services.py:65-71`). Det är konventionellt i HA och ger tydligt felmeddelande `not_set_up`.

### 9. Frontend: viss logik som egentligen hör hemma i backend (låg)

CLAUDE.md: "The card stays thin and contains no business logic."

- `frontend/src/ai.ts:43` – regeln "varor som redan finns på listan börjar avmarkerade" är upprepad i kortet (`selected: !isOnList && selected !== false`). Samma regel finns i `suggestions_payload` i backend; kortet säkerställer den en gång till.
- `frontend/src/lists.ts:67-68` (`same`) och `frontend/src/handla-card.ts:251` – skiftlägesokänslig jämförelse av list-ID duplicerar `same_id` i `domain/lists.py`.
- `frontend/src/handla-items.ts` (636 rader) bär en egen kö (`_queue`, `handla-items.ts:312-340`) som lägger till varor en i taget och stannar vid dubblett eller fel. Det är UI-orkestrering, men den är stor nog att motivera en liten kontrollerklass, och en backend-tjänst för att lägga till flera varor skulle förenkla kortet.
- Filstorlek: `handla-items.ts` (636), `handla-card.ts` (454), `handla-ai.ts` (428) och `handla-quick-manage.ts` (370) är stora för "tunna" komponenter.

### 10. Testluckor (låg)

- `events.py` (`ListsChangedWaiter`) och `todo_api.py` har inga egna testfiler. De täcks indirekt via `test_coordinator.py` och `test_item_services.py`, men väntelogiken (race-skyddet som CLAUDE.md pekar ut som en känd fallgrop) borde ha ett direkt enhetstest: händelse före `wait_for`, händelse efter, och timeout.
- Ingen test hittades för tillståndet "dubbla samtidiga add_item" (se punkt 7).

## Prioriterad åtgärdslista

| Prio | Åtgärd | Berörda filer |
|---|---|---|
| 1 | Flytta notis- och felnotistexter till översättningsfiler | `domain/notify.py`, `domain/ai_health.py`, `translations/`, `strings.json` |
| 2 | Inför `ica_api.py` och `ai_api.py` i samma stil som `todo_api.py` | `coordinator.py`, `ai.py`, `ai_monitor.py` |
| 3 | Dela upp `HandlaCoordinator` (listhärledning, operationer, "item added"-flöde) | `coordinator.py`, `services.py` |
| 4 | Bryt ut AI-konfiguration och `get_recipients` till en gemensam modul, och ta bort `TYPE_CHECKING`-ringen | `ai.py`, `ai_monitor.py`, `notify.py` |
| 5 | Bestäm och dokumentera hur misslyckade notiser och kortregistrering ska synas (reparationsärende eller sensorattribut) | `notify.py`, `card.py` |
| 6 | Lägg till `event_filter` på `state_changed` i koordinatorn | `coordinator.py:112` |
| 7 | Direkta tester för `ListsChangedWaiter` och `todo_api` | `tests/` |
| 8 | Flytta sista kvarvarande regler (`selected`, ID-jämförelse) till backend eller ta bort dubbletterna | `frontend/src/ai.ts`, `frontend/src/lists.ts` |
