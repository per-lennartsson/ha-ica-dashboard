# Plan: åtgärda arkitekturgranskningen (version 2)

**Läge:** steg 1–6 är genomförda och mergade till `main` (tester, `options.py`, översatta notistexter, I/O-lager, slimmad koordinator, `event_filter` och dokumentation). Kvar är steg 7 (frontend). Koordinatorn blev 200 rader (målet var ca 150), och `usage`, `notifier` och `ai_monitor` ägs fortfarande av koordinatorn.

Bygger på [architecture-review.md](architecture-review.md), uppdaterad mot `main` 96ae4e8. Godkänd av maintainern i första versionen. Ändringarna jämfört med den finns längst ned.

## Ramar

- Varje steg är en egen feature-branch och en egen merge till `main`. Aldrig direkt på `main`.
- Inga ändringar av tjänstenamn, händelsenamn eller entitets-ID:n.
- Inget installeras och inga beroenden läggs till. Python-verktygen finns i `.venv`, Node körs via `./scripts/node.sh`.
- Efter varje steg: `ruff check . && ruff format --check .`, `mypy custom_components`, `pytest tests/ -v`. Frontendsteg kör även `format:check`, `lint` och `test:coverage`.
- Befintliga tester ska gå gröna utan att ändras i sak. Ändrar jag ett test för att det ska passa, säger jag det.

## Beslut (antagna enligt förslagen, säg till om du vill ändra)

1. Standardnamnet "Att handla <dag> <månad>" förblir svenskt och dokumenteras som undantag i CLAUDE.md.
2. AI-prompten och hälsokontrollens text förblir versionshanterade svenska konstanter, dokumenterade som undantag.
3. Misslyckade notiser: logg räcker. Det lades redan till per-grupp-felhantering i `444f7c5`, så jag lägger inte till något attribut på statussensorn.
4. De breda `except Exception` i `coordinator.py:212` och `notify.py:85` stannar kvar. De är medvetna (de hindrar dubbletter och tappade notiser) och dokumenteras som undantag.

## Steg

### Steg 1 – Direkta tester (klart)

Branch `test-events-and-todo-api`, två commits, 483 tester gröna. Väntar på merge.

### Steg 2 – Gemensam konfigurationsmodul och bryt cirkeln (litet)

- Ny `options.py` med `get_ai_config`, `get_health_check` och `get_recipients` (flyttas från `ai.py` och `notify.py`). `TYPE_CHECKING`-importen i `ai.py:29` försvinner och `ai_monitor.py:12` importerar från `options.py`.
- `event_data` flyttas från `notify.py:107` till `domain/notify.py`.
- Inga beteendeförändringar. Tester flyttas med funktionerna.

### Steg 3 – Översätt notistexter (litet–medel)

- Flytta texterna i `domain/notify.py:build_message` och `domain/ai_health.py:build_failure_message` till `strings.json` och `translations/{sv,en}.json`.
- I/O-lagret hämtar mallarna med `async_get_translations`. Domänfunktionerna tar emot färdiga mallar och formaterar bara, så domänen förblir fri från HA.
- Risk: hassfest kan avvisa egna nycklar. Jag kontrollerar först vilken kategori som är tillåten (troligen `exceptions`). Faller det, behåller jag en liten sv/en-tabell i `const.py` och dokumenterar det.
- Okända språk faller tillbaka på engelska, som idag.
- Tester: sv, en och okänt språk för båda meddelandena.

### Steg 4 – I/O-lager för `ica.*` och `ai_task.*` (medel)

- Ny `ica_api.py` med `async_create_list` och `async_delete_list` (flyttas från `coordinator.py:349-398`, inklusive felmappningen till `create_failed`/`delete_failed`).
- Ny `ai_api.py` med en gemensam `async_generate_data(...)`. `ai._ask_provider` (`ai.py:79`) och `ai_monitor.async_health_check` (`ai_monitor.py:73`) använder den, så felmappningen finns på ett ställe.
- `notify.async_notify_users` bedöms när jag ser koden: flyttas till `notify_api.py` om det blir renare, annars blir den kvar.
- Tester: enhetstester per I/O-modul med mockade tjänster. Koordinator- och AI-testerna kan förenklas.
- Gör klart: inga `hass.services.async_call` för `ica` och `ai_task` utanför I/O-modulerna.

### Steg 5 – Slimma koordinatorn (medel, mindre än tidigare plan)

`services.py` och `add_item`-orkestreringen är redan åtgärdade, så steget är mindre än planerat. Kvar:

- `lists_registry.py`: `_read_lists`/`_compute`, aktiv lista och dess `Store` (`coordinator.py:124-160`, `:257`).
- Ersätt de två kopierade flödena `async_create_list` (`:316`) och `async_delete_list` (`:370`) med ett gemensamt `_run_list_operation(status, anrop, matchning)`. Flytta dem, tillsammans med statusmaskinen (`_begin`, `_set_status`), till `list_operations.py` ovanpå `ica_api` och `ListsChangedWaiter`.
- Flytta `async_add_item`, `async_item_added` och `_announce_item` (`:186-240`) till en liten `ItemAnnouncer`, så koordinatorn inte äger statistik, event och notis. `usage`, `notifier` och `ai_monitor` ägs då av entryn (`__init__.py`) och inte av listkoordinatorn.
- Den publika ytan (`resolve_list`, `usage`, `status`, `suggest_list_name`) hålls oförändrad så sensorer och tjänster rörs minimalt.
- Gör klart: `coordinator.py` under ca 150 rader, ingen funktion över ca 30 rader, alla gamla tester gröna.

### Steg 6 – Lyssnare och dokumentation (litet)

- `coordinator.py:113`: `event_filter` på `state_changed` (som `sensor.py:149`) så att bara `todo.*` når callbacken.
- Dokumentera i CLAUDE.md och `docs/`: dubblettkontrollen är inte atomär, de breda `except Exception` är medvetna undantag, och texterna i beslut 1–2.

### Steg 7 – Frontend: ta bort dubbla regler (medel, oberoende)

- `ai.ts:43`: backend avgör `selected`. Kortet litar på svaret men bevarar användarens eget val. Verifiera mot `suggestions_payload` att fältet alltid sätts.
- `lists.ts:67` och `handla-card.ts:252`: samla ID-jämförelsen i en enda hjälpfunktion (en kopia i frontend är oundviklig).
- Dela upp `handla-items.ts` (637 rader): bryt ut tilläggskön (`_queue`, `handla-items.ts:304-340`) till en ren kontrollerklass med egna tester. Ingen UI-ändring.

## Ordning

```
Steg 1 (klart) ─> merge
Steg 2 ─> Steg 3
Steg 2 ─> Steg 4 ─> Steg 5 ─> Steg 6
Steg 7 (oberoende, frontend)
```

## Skillnad mot första planen

| Område | Första planen | Nu | Varför |
|---|---|---|---|
| Delning av `services.py` | Del av stora koordinatorsteget | **Struken** | Redan gjord i `444f7c5` (`ServiceSpec`-tabell, handlers på modulnivå). |
| Orkestrering av `add_item` | Flytta ut ur `services.py` | **Struken** i services, **flyttad** till steg 5 | Den ligger nu i `coordinator.async_add_item`, men koordinatorn ska ändå inte äga den. |
| Felhantering (steg 5 förut) | Notisfel, `card.py`, tom `catch` | **Struken**, ersatt av dokumentation av undantag | `card.py`, `notify.async_flush`, `usage.async_flush`, `_set_preferred`, `handla-card.ts` och `api.ts` är åtgärdade i `444f7c5`. |
| Beslut 3 (notisfel-attribut) | Logg plus `last_notify_error` | **Bara logg** | Per-grupp-felhantering finns redan. |
| Steg-numrering | 1 texter, 2 options, 3 I/O, 4 koordinator, 5 fel, 6 tester, 7 frontend | 1 tester (klart), 2 options, 3 texter, 4 I/O, 5 koordinator, 6 lyssnare/dok, 7 frontend | Testerna är klara, och texter hanteras efter `options.py` som de delvis beror på. |
| Koordinatorsteget | Stort, delas i tre | **Mindre**: `lists_registry`, gemensam create/delete och `ItemAnnouncer` | Mindre kvar efter `444f7c5`, men koordinatorn har växt från 370 till 406 rader. |
| Radhänvisningar | Gamla | Uppdaterade till `main` 96ae4e8 | Filerna ändrades av `444f7c5` och `7c8181b`. |
| Nytt | – | Dokumentation av medvetna `except Exception` | De uppstod i `444f7c5` och strider mot ordalydelsen i CLAUDE.md. |
