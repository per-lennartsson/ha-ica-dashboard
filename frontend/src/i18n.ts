/** Texts for the card. Swedish is the source; English must have the same keys. */

export const sv = {
  "card.title": "Inköp",
  "card.loaded": "Inköpskortet är laddat.",
  "card.items": "{count} varor att handla",
  "card.no_data": "Ingen data ännu. Är Inköp installerat och konfigurerat?",
  "card.invalid_config": "Ogiltig kortkonfiguration.",
} as const;

export type TranslationKey = keyof typeof sv;

export const en: Record<TranslationKey, string> = {
  "card.title": "Shopping",
  "card.loaded": "The shopping card is loaded.",
  "card.items": "{count} items to buy",
  "card.no_data": "No data yet. Is Inköp installed and set up?",
  "card.invalid_config": "Invalid card configuration.",
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
