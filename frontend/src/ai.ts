/** The optional AI module: whether it is usable, and the suggestions it returns. */

import type { HomeAssistant } from "./types";

export const AI_ENTITY = "sensor.handla_ai";

/** Longest text the integration accepts (MAX_TEXT_LENGTH in the integration). */
export const MAX_TEXT_LENGTH = 20000;

/**
 * AI UI is shown only when the integration reports `ready`. Off, unavailable, a missing
 * sensor (AI code not present) and anything unknown all mean: show nothing.
 */
export function isAiReady(hass: HomeAssistant | undefined): boolean {
  return hass?.states[AI_ENTITY]?.state === "ready";
}

export interface Suggestion {
  /** The item text, "<quantity> <unit> <name>". */
  item: string;
  /** An open item with the same name is already on the list. */
  onList: boolean;
  /** That existing item's text. */
  existing: string | null;
  /** Whether the item starts ticked in the review. */
  selected: boolean;
}

/** Suggestions from the service answer; malformed entries are skipped. */
export function parseSuggestions(raw: unknown): Suggestion[] {
  if (!Array.isArray(raw)) return [];
  const result: Suggestion[] = [];
  for (const entry of raw) {
    if (typeof entry !== "object" || entry === null) continue;
    const { item, on_list: onList, existing, selected } = entry as Record<string, unknown>;
    if (typeof item !== "string" || item.trim() === "") continue;
    const isOnList = onList === true;
    result.push({
      item: item.trim(),
      onList: isOnList,
      existing: typeof existing === "string" ? existing : null,
      // Items already on the list start unticked, whatever the answer says
      selected: !isOnList && selected !== false,
    });
  }
  return result;
}
