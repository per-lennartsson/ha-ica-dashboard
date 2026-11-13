/** Calls to the Handla services. Errors are thrown as Error with a readable message. */

import { parseSuggestions, type Suggestion } from "./ai";
import {
  parseCategories,
  parseCategorySuggestions,
  type CategoryData,
  type CategorySuggestion,
} from "./categories";
import { localize } from "./i18n";
import { parseQuickItems, type QuickItem } from "./items";
import type { HomeAssistant } from "./types";

const DOMAIN = "handla";

/** `hass.callService(..., returnResponse)` resolves to { context, response }. */
export function responseOf(result: unknown): Record<string, unknown> {
  if (typeof result === "object" && result !== null && "response" in result) {
    const response = (result as { response: unknown }).response;
    if (typeof response === "object" && response !== null) {
      return response as Record<string, unknown>;
    }
  }
  return {};
}

/** A readable message for any thrown value; `language` picks the fallback's language. */
export function errorMessage(err: unknown, language?: string): string {
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === "object" && err !== null && "message" in err) {
    const message = (err as { message: unknown }).message;
    if (typeof message === "string" && message) return message;
  }
  return typeof err === "string" && err ? err : localize(language, "error.unknown");
}

async function call(
  hass: HomeAssistant,
  service: string,
  data: Record<string, unknown>,
  returnResponse = false,
): Promise<Record<string, unknown>> {
  try {
    const result = await hass.callService(DOMAIN, service, data, undefined, false, returnResponse);
    return responseOf(result);
  } catch (err) {
    throw new Error(errorMessage(err), { cause: err });
  }
}

/** The prefilled name for a new list ("Att handla 14 oktober"), or "" if unavailable. */
export async function suggestListName(hass: HomeAssistant): Promise<string> {
  const { name } = await call(hass, "suggest_list_name", {}, true);
  return typeof name === "string" ? name : "";
}

/** Creates a list and makes it the household's active list. Returns its ICA id. */
export async function createList(hass: HomeAssistant, title: string): Promise<string | null> {
  const { offline_id: offlineId } = await call(
    hass,
    "create_list",
    { title, set_active: true },
    true,
  );
  return typeof offlineId === "string" ? offlineId : null;
}

export async function deleteList(hass: HomeAssistant, entityId: string): Promise<void> {
  await call(hass, "delete_list", { entity_id: entityId });
}

export interface AddResult {
  added: boolean;
  /** An open item with the same name was already on the list. */
  duplicate: boolean;
  /** The item text as stored (normalised by the integration). */
  item: string;
  duplicates: Array<{ uid: string; summary: string }>;
}

/**
 * Adds an item. When an open item with the same name exists nothing is added unless
 * `confirmDuplicate` is true; the result then has added=false and duplicate=true.
 */
export async function addItem(
  hass: HomeAssistant,
  entityId: string,
  item: string,
  confirmDuplicate = false,
): Promise<AddResult> {
  const response = await call(
    hass,
    "add_item",
    { entity_id: entityId, item, confirm_duplicate: confirmDuplicate },
    true,
  );
  const raw = Array.isArray(response["duplicates"]) ? response["duplicates"] : [];
  return {
    added: response["added"] === true,
    duplicate: response["duplicate"] === true,
    item: typeof response["item"] === "string" ? response["item"] : item,
    duplicates: raw.flatMap((entry: unknown) => {
      if (typeof entry !== "object" || entry === null) return [];
      const { uid, summary } = entry as Record<string, unknown>;
      return typeof uid === "string" && typeof summary === "string" ? [{ uid, summary }] : [];
    }),
  };
}

export async function tickItem(
  hass: HomeAssistant,
  entityId: string,
  uid: string,
  ticked: boolean,
): Promise<void> {
  await call(hass, "tick_item", { entity_id: entityId, item: uid, ticked });
}

export async function removeItem(
  hass: HomeAssistant,
  entityId: string,
  uid: string,
): Promise<void> {
  await call(hass, "remove_item", { entity_id: entityId, item: uid });
}

export async function clearTicked(hass: HomeAssistant, entityId: string): Promise<void> {
  await call(hass, "clear_ticked", { entity_id: entityId });
}

/**
 * Asks the AI to find shopping items in a pasted text (recipe, meal plan, message).
 * Nothing is added; the items on `entityId` are only compared with the suggestions.
 */
export async function extractItems(
  hass: HomeAssistant,
  entityId: string,
  text: string,
): Promise<Suggestion[]> {
  const response = await call(hass, "ai_extract_items", { entity_id: entityId, text }, true);
  return parseSuggestions(response["items"]);
}

/** Most items the integration tracks; asking for this many returns the whole history. */
const ALL_QUICK_ITEMS = 500;

/** Every tracked quick-add item (not only the buttons shown), pinned first, then most added. */
export async function getQuickItems(hass: HomeAssistant): Promise<QuickItem[]> {
  const response = await call(hass, "get_top_items", { limit: ALL_QUICK_ITEMS }, true);
  return parseQuickItems(response["items"]);
}

export async function removeQuickItem(hass: HomeAssistant, item: string): Promise<void> {
  await call(hass, "remove_quick_item", { item });
}

/** Pins an item to the quick-add buttons, even if it was never added before. */
export async function addQuickItem(hass: HomeAssistant, item: string): Promise<void> {
  await call(hass, "add_quick_item", { item });
}

/** Merges items into one called `target`; the merged names keep counting toward it. */
export async function mergeQuickItems(
  hass: HomeAssistant,
  sources: string[],
  target: string,
): Promise<void> {
  await call(hass, "merge_quick_items", { sources, target });
}

/** The store groups in shopping order and the group of each item on a list. */
export async function getCategories(hass: HomeAssistant, entityId: string): Promise<CategoryData> {
  return parseCategories(await call(hass, "get_categories", { entity_id: entityId }, true));
}

export interface SetCategoryResult {
  updated: string[];
  notFound: string[];
}

function textList(raw: unknown): string[] {
  return Array.isArray(raw)
    ? raw.filter((entry): entry is string => typeof entry === "string")
    : [];
}

/** Moves items to other groups; ICA remembers the choice for later items with the same name. */
export async function setCategory(
  hass: HomeAssistant,
  entityId: string,
  changes: Array<{ uid: string; groupId: number }>,
): Promise<SetCategoryResult> {
  const response = await call(
    hass,
    "set_category",
    {
      entity_id: entityId,
      items: changes.map(({ uid, groupId }) => ({ uid, group_id: groupId })),
    },
    true,
  );
  return { updated: textList(response["updated"]), notFound: textList(response["not_found"]) };
}

export interface CategorySuggestions {
  items: CategorySuggestion[];
  /** The list was longer than the AI reads in one go. */
  truncated: boolean;
  /** How many items the AI was asked about. */
  asked: number;
}

/** Asks the AI to suggest groups. Nothing is changed; saving goes through `setCategory`. */
export async function suggestCategories(
  hass: HomeAssistant,
  entityId: string,
  includeAll: boolean,
): Promise<CategorySuggestions> {
  const response = await call(
    hass,
    "ai_suggest_categories",
    { entity_id: entityId, scope: includeAll ? "all" : "unspecified" },
    true,
  );
  return {
    items: parseCategorySuggestions(response["items"]),
    truncated: response["truncated"] === true,
    asked: typeof response["asked"] === "number" ? response["asked"] : 0,
  };
}
