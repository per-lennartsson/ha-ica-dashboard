/** Calls to the Handla services. Errors are thrown as Error with a readable message. */

import { parseSuggestions, type Suggestion } from "./ai";
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

export function errorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === "object" && err !== null && "message" in err) {
    const message = (err as { message: unknown }).message;
    if (typeof message === "string" && message) return message;
  }
  return typeof err === "string" && err ? err : "Unknown error";
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
