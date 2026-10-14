/** Calls to the Inköp services. Errors are thrown as Error with a readable message. */

import type { HomeAssistant } from "./types";

const DOMAIN = "inkop";

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
