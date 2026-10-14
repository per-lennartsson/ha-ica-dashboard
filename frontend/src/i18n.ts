/** Texts for the card. Swedish is the source; English must have the same keys. */

export const sv = {
  "card.title": "Inköp",
  "card.invalid_config": "Ogiltig kortkonfiguration.",
  "card.not_running":
    "Inköp körs inte. Kontrollera att ICA-integrationen (ha-ica-todo) är installerad och laddad (Inställningar → System → Reparationer) och att Inköp är tillagt under Enheter och tjänster.",
  "lists.label": "Lista",
  "lists.none": "Det finns inga inköpslistor än. Skapa en för att komma igång.",
  "lists.new": "Ny lista",
  "lists.delete": "Ta bort lista",
  "create.label": "Namn på listan",
  "create.submit": "Skapa lista",
  "create.cancel": "Avbryt",
  "create.name_required": "Ange ett namn på listan.",
  "delete.confirm": "Ta bort listan “{title}” från ICA? Det går inte att ångra.",
  "delete.submit": "Ta bort",
  "delete.cancel": "Avbryt",
  "busy.creating": "Skapar listan… Det kan ta några sekunder.",
  "busy.deleting": "Tar bort listan… Det kan ta några sekunder.",
  "busy.working": "Arbetar…",
  "error.generic": "Något gick fel: {message}",
  "error.last": "Senaste åtgärden misslyckades: {detail}",
  "items.add_label": "Lägg till vara",
  "items.add_placeholder": "t.ex. mjölk eller 2 st gurka",
  "items.add_button": "Lägg till",
  "items.empty": "Listan är tom. Lägg till något ovan.",
  "items.loading": "Hämtar varor…",
  "items.adding": "lägger till…",
  "items.tick": "Bocka av {item}",
  "items.untick": "Ta bort bocken på {item}",
  "items.remove": "Ta bort {item}",
  "items.ticked": "Avbockade ({count})",
  "items.clear": "Rensa avbockade ({count})",
  "items.unavailable":
    "Listan är inte tillgänglig just nu (ICA laddar kanske om). Försök igen om en stund.",
  "items.load_error": "Kunde inte hämta varorna: {message}",
  "duplicate.prompt": "“{item}” finns redan – lägga till igen?",
  "duplicate.add": "Lägg till igen",
  "duplicate.skip": "Hoppa över",
  "add.failed": "Kunde inte lägga till “{item}”: {message}",
  "add.retry": "Försök igen",
  "add.skip": "Hoppa över",
  "action.failed": "Kunde inte uppdatera listan: {message}",
  "quick.label": "Vanliga varor",
  "common.dismiss": "Stäng",
} as const;

export type TranslationKey = keyof typeof sv;

export const en: Record<TranslationKey, string> = {
  "card.title": "Shopping",
  "card.invalid_config": "Invalid card configuration.",
  "card.not_running":
    "Inköp is not running. Check that the ICA integration (ha-ica-todo) is installed and loaded (Settings → System → Repairs) and that Inköp is added under Devices & services.",
  "lists.label": "List",
  "lists.none": "There are no shopping lists yet. Create one to get started.",
  "lists.new": "New list",
  "lists.delete": "Delete list",
  "create.label": "List name",
  "create.submit": "Create list",
  "create.cancel": "Cancel",
  "create.name_required": "Enter a name for the list.",
  "delete.confirm": "Delete the list “{title}” from ICA? This cannot be undone.",
  "delete.submit": "Delete",
  "delete.cancel": "Cancel",
  "busy.creating": "Creating the list… This can take a few seconds.",
  "busy.deleting": "Deleting the list… This can take a few seconds.",
  "busy.working": "Working…",
  "error.generic": "Something went wrong: {message}",
  "error.last": "The last action failed: {detail}",
  "items.add_label": "Add item",
  "items.add_placeholder": "e.g. milk or 2 st cucumber",
  "items.add_button": "Add",
  "items.empty": "The list is empty. Add something above.",
  "items.loading": "Loading items…",
  "items.adding": "adding…",
  "items.tick": "Tick off {item}",
  "items.untick": "Untick {item}",
  "items.remove": "Remove {item}",
  "items.ticked": "Ticked ({count})",
  "items.clear": "Clear ticked ({count})",
  "items.unavailable":
    "The list is not available right now (ICA may be reloading). Try again in a moment.",
  "items.load_error": "Could not load the items: {message}",
  "duplicate.prompt": "“{item}” is already on the list – add again?",
  "duplicate.add": "Add again",
  "duplicate.skip": "Skip",
  "add.failed": "Could not add “{item}”: {message}",
  "add.retry": "Try again",
  "add.skip": "Skip",
  "action.failed": "Could not update the list: {message}",
  "quick.label": "Frequent items",
  "common.dismiss": "Dismiss",
};

/** Swedish for Swedish (and when no language is known), English for everything else. */
export function pickLanguage(language: string | undefined): "sv" | "en" {
  if (!language) return "sv";
  return language.toLowerCase().startsWith("sv") ? "sv" : "en";
}

export function localize(
  language: string | undefined,
  key: TranslationKey,
  params: Record<string, string | number> = {},
): string {
  const table: Record<TranslationKey, string> = pickLanguage(language) === "sv" ? sv : en;
  return Object.entries(params).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
    table[key],
  );
}
