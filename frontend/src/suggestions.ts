/** Item name suggestions while typing: reading the answer, splitting what is typed, filtering. */

import { UNSPECIFIED_GROUP } from "./categories";

export interface ItemSuggestion {
  name: string;
  /** The category an item with this name gets (12 means none). */
  groupId: number;
  /** "history", "favorite" or "article". */
  source: string;
  count: number;
}

/** Nothing is suggested for fewer characters than this. */
export const MIN_QUERY_LENGTH = 2;

/** The longest dropdown, in the narrow and the wide layout. */
export const MAX_SUGGESTIONS_NARROW = 8;
export const MAX_SUGGESTIONS_WIDE = 12;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Suggestions from `handla.get_item_suggestions`; entries without a name are skipped. */
export function parseItemSuggestions(response: Record<string, unknown>): ItemSuggestion[] {
  const raw = response["items"];
  if (!Array.isArray(raw)) return [];
  const result: ItemSuggestion[] = [];
  for (const entry of raw) {
    if (!isRecord(entry) || typeof entry["name"] !== "string" || entry["name"].trim() === "") {
      continue;
    }
    result.push({
      name: entry["name"].trim(),
      groupId: typeof entry["group_id"] === "number" ? entry["group_id"] : UNSPECIFIED_GROUP,
      source: typeof entry["source"] === "string" ? entry["source"] : "",
      count: typeof entry["count"] === "number" ? entry["count"] : 0,
    });
  }
  return result;
}

// The quantity and unit the item parser understands ("2", "1,5 kg", "2–3 st"). A unit counts
// only as a whole word, so "2 lök" is quantity 2 and the name "lök", not 2 l + "ök".
const LEADING_QUANTITY =
  /^(\d+(?:[.,]\d+)?(?:\s*[–-]\s*\d+(?:[.,]\d+)?)?(?:\s*(?:st|förp|kg|hg|g|l|dl|cl|ml|msk|tsk|krm)(?=\s|$))?)\s*/i;

export interface TypedText {
  /** The quantity and unit typed so far, with a trailing space ("2 st "), or "". */
  prefix: string;
  /** What is left to search for ("toal"). */
  query: string;
}

/** Splits a leading quantity and unit from the text to search for: "2 st toal" → "2 st ", "toal". */
export function splitTyped(text: string): TypedText {
  const trimmed = text.trimStart();
  const match = LEADING_QUANTITY.exec(trimmed);
  if (!match) return { prefix: "", query: trimmed };
  const quantity = match[1] ?? "";
  return { prefix: `${quantity} `, query: trimmed.slice(match[0].length) };
}

/** The text to add when a suggestion is picked: the typed quantity is kept. */
export function pickedText(prefix: string, name: string): string {
  return `${prefix}${name}`;
}

function startsAWord(name: string, query: string): boolean {
  return name.split(/[^\p{L}\p{N}]+/u).some((word) => word.startsWith(query));
}

/**
 * Names that start with the text first, then names with a word that starts with it, then names
 * that contain it. The server's order (most used first) is kept within each group.
 */
export function filterSuggestions(
  all: readonly ItemSuggestion[],
  query: string,
  max = MAX_SUGGESTIONS_NARROW,
): ItemSuggestion[] {
  const needle = query.trim().toLowerCase();
  if (needle.length < MIN_QUERY_LENGTH) return [];
  const starts: ItemSuggestion[] = [];
  const words: ItemSuggestion[] = [];
  const contains: ItemSuggestion[] = [];
  for (const suggestion of all) {
    const name = suggestion.name.toLowerCase();
    if (name.startsWith(needle)) starts.push(suggestion);
    else if (startsAWord(name, needle)) words.push(suggestion);
    else if (name.includes(needle)) contains.push(suggestion);
  }
  return [...starts, ...words, ...contains].slice(0, max);
}
