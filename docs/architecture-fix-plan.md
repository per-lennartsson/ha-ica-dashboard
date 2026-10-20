# Plan: åtgärda arkitekturgranskningen

Bygger på [architecture-review.md](architecture-review.md). Väntar på godkännande innan något implementeras (CLAUDE.md).

## Ramar

- Varje steg är en egen feature-branch och en egen merge till `main`. Aldrig direkt på `main`.
- Inga ändringar av tjänstenamn, händelsenamn eller entitets-ID:n. Alla steg är interna omstruktureringar utom steg 1, som ändrar var texter hämtas ifrån.
- Inga nya beroenden och inget installeras. Python-verktygen finns redan i `.venv`, Node körs via `./scripts/node.sh`.
- Efter varje steg: `ruff check . && ruff format --check .`, `mypy custom_components`, `pytest tests/ -v`. Frontendsteg kör även `format:check`, `lint` och `test:coverage`.
- Tester skrivs i samma steg som koden. Befintliga tester ska fortsätta gå gröna utan att ändras i sak. Ändrar jag ett befintligt test för att det ska passa, säger jag det.

## Beslut jag behöver från dig

1. **Standardnamnet på nya listor** ("Att handla 20 oktober"): ska det alltid vara svenskt (som idag och som specen säger), eller följa HA:s språk? Förslag: behåll svenskt och dokumentera det som ett medvetet undantag i CLAUDE.md.
2. **AI-prompten och hälsokontrollens text** är svensk i koden. Förslag: behåll som versionshanterade konstanter och dokumentera undantaget, eftersom prompten är en del av logiken och inte UI-text.
3. **Misslyckade notiser** (`notify.py:46`): bara logg räcker, eller ska de synas? Förslag: logg plus en räknare/attribut `last_notify_error` på statussensorn. Ingen reparationsruta, för det blir bruskänsligt.

## Steg

### Steg 1 – Översätt notistexter (prio 1, litet)

- Flytta texterna i `domain/notify.py:build_message` och `domain/ai_health.py:build_failure_message` till `strings.json` och `translations/{sv,en}.json`.
- Hämta dem i I/O-lagret med `async_get_translations` och skicka färdiga mallar till de rena domänfunktionerna, så domänen förblir fri från HA. Domänfunktionerna tar emot mallsträngar och formaterar bara.
- Risk: custom-nycklar utanför HA:s standardkategorier kan stoppas av hassfest. Jag kontrollerar först vilken kategori som är tillåten (troligen `exceptions`) och stämmer av i CI-flödet. Faller det, behåller jag en liten sv/en-tabell i `const.py` och dokumenterar det.
- Fallback för okända språk: engelska, som idag.
- Tester: sv, en och okänt språk för båda meddelandena. Pass-through av tomma namn.
- Gör klart: inga svenska strängar kvar i `domain/notify.py` och `domain/ai_health.py`.

### Steg 2 – Gemensam konfigurationsmodul och bryt cirkeln (prio 4, litet)

- Ny `options.py` med `get_ai_config`, `get_health_check` och `get_recipients` (flyttas från `ai.py` och `notify.py`). `ai.py` och `ai_monitor.py` importerar därifrån, och `TYPE_CHECKING`-importen i `ai.py:29` försvinner.
- Flytta `event_data` från `notify.py:102` till `domain/notify.py`.
- Tester flyttas med funktionerna. Inga beteendeförändringar.

### Steg 3 – I/O-lager för `ica.*` och `ai_task.*` (prio 2, medel)

- Ny `ica_api.py` med `async_create_list` och `async_delete_list` (flyttat från `coordinator.py:313-360`, inklusive felmappningen till `create_failed`/`delete_failed`).
- Ny `ai_api.py` med en enda `async_generate_data(hass, entity_id, task_name, instructions, structure=None, context=None)`. `ai._ask_provider` och `ai_monitor.async_health_check` använder den, så felmappningen finns på ett ställe.
- `notify.async_notify_users` flyttas till ett litet `notify_api.py` (eller blir kvar om den bedöms redan vara ett tunt lager – jag avgör när jag ser koden).
- Tester: nya enhetstester per I/O-modul med mockade tjänster. Koordinator- och AI-tester förenklas till att fejka I/O-modulen.
- Gör klart: inga `hass.services.async_call` för `ica`, `ai_task` eller `notify` utanför I/O-modulerna.

### Steg 4 – Dela upp koordinatorn (prio 3, störst)

Görs efter steg 3, eftersom I/O då redan är utflyttad.

- `lists_registry.py` (eller klass i `lists.py`): härledning ur registret (`_read_lists`, `_compute`), aktiv lista och dess `Store`.
- `list_operations.py`: statusmaskinen och skapa/ta bort, byggd på `ica_api` och `ListsChangedWaiter`. `async_create_list` delas i små steg (förbered, anropa, vänta, aktivera) så den inte behöver kommentarer.
- `item_events.py` (eller metod på en egen klass): "vara tillagd"-flödet (`async_item_added`: användning, event, notis). `services.add_item` anropar den i stället för coordinatorn.
- `HandlaCoordinator` behåller bara `data`, lyssnare och komposition av delarna. Den publika ytan (`resolve_list`, `usage`, `status`, `suggest_list_name` …) hålls oförändrad så sensorer och tjänster inte rörs mer än nödvändigt.
- `services.async_register_services` delas i `_register_item_services`, `_register_list_services`, `_register_quick_services`. Ingen ändring av tjänstenamn eller scheman.
- Gör klart: `coordinator.py` under ca 150 rader, ingen funktion över ca 30 rader, alla gamla tester gröna.

### Steg 5 – Felhantering och lyssnare (prio 5–6, litet)

- `coordinator.py:112`: `event_filter` på `state_changed` (som `sensor.py:149`) så att bara `todo.*` når callbacken.
- Notisfel: enligt beslut 3.
- `card.py`: om resursregistreringen misslyckas, logga som idag men exponera även en flagga som docs/dev.md nämner, så felsökning går att göra utan loggar.
- `frontend/src/handla-card.ts:213`: logga felet med `console.warn` i stället för tom `catch`. Behåll beteendet (användaren skriver namn själv).
- Dokumentera i CLAUDE.md/docs att dubblettkontrollen inte är atomär (två samtidiga adderingar kan båda passera). Ingen kodändring, eftersom ICA saknar atomär operation.

### Steg 6 – Direkta tester (prio 7, litet)

- `tests/test_events.py` för `ListsChangedWaiter`: händelse före `wait_for`, händelse efter, flera händelser, timeout, avregistrering vid utträde.
- `tests/test_todo_api.py`: felmappning, tomma svar, skräprader.
- Kan göras tidigt, parallellt med steg 1–2, eftersom det inte rör produktionskoden.

### Steg 7 – Frontend: ta bort dubbla regler (prio 8, litet)

- `ai.ts:43`: backend avgör redan `selected`. Kortet litar på svaret men bevarar användarens eget val. Verifiera mot `suggestions_payload` att kontraktet verkligen alltid sätter fältet.
- `lists.ts:67` och `handla-card.ts:251`: samla ID-jämförelsen i en enda hjälpfunktion i `lists.ts` (en kopia i frontend är oundviklig eftersom kortet jämför lokalt, så målet är en kopia och inte noll).
- Dela upp `handla-items.ts` (636 rader): bryt ut tilläggskön (`_queue`, `handla-items.ts:303-340`) till en liten ren kontrollerklass med egna tester. Ingen UI-ändring.

## Ordning och beroenden

```
Steg 6 ─┐
Steg 1 ─┼─> Steg 3 ─> Steg 4 ─> Steg 5
Steg 2 ─┘
Steg 7 (oberoende, frontend)
```

Steg 1, 2, 6 och 7 kan göras oberoende av varandra. Steg 3 bör komma efter steg 2, och steg 4 kräver steg 3. Steg 5 rör filer som steg 4 flyttar, så det görs sist.

## Uppskattad omfattning

| Steg | Ungefärlig storlek | Risk |
|---|---|---|
| 1 | liten | medel (hassfest/översättningskategori) |
| 2 | liten | låg |
| 3 | medel | låg–medel |
| 4 | stor | medel (flest rörliga delar) |
| 5 | liten | låg |
| 6 | liten | låg |
| 7 | medel | låg |

## Definition of done

- Alla rader i "Brott mot principerna" i arkitekturgranskningen är antingen åtgärdade eller har ett dokumenterat undantag i CLAUDE.md.
- `ruff`, `mypy`, `pytest`, `eslint`, `prettier` och `vitest` är gröna, och CI är grönt på varje PR.
- Inga tjänstenamn, händelsenamn eller entitets-ID:n har ändrats.
- Efter merge görs en manuell kontroll på din HA enligt `docs/dev.md`: skapa och ta bort en throwaway-lista, lägg till en vara, kontrollera notisen, och kontrollera AI-flödet om modulen är på.
