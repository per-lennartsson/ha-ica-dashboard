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
