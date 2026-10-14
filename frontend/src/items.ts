/** Items on a list, quick-add buttons and the live subscription to a todo entity. */

import type { HomeAssistant } from "./types";

export const FREQUENT_ENTITY = "sensor.inkop_frequent_items";

export interface TodoItem {
  uid: string;
  summary: string;
  completed: boolean;
}

export interface QuickItem {
  name: string;
  icon: string;
  count: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Items from a `todo/item/subscribe` message ({ items: [...] }); malformed ones are skipped. */
export function parseItems(message: unknown): TodoItem[] {
  const raw = isRecord(message) ? message["items"] : undefined;
  if (!Array.isArray(raw)) return [];
  const items: TodoItem[] = [];
  for (const entry of raw) {
    if (!isRecord(entry)) continue;
    const { uid, summary, status } = entry;
    if (typeof uid !== "string" || typeof summary !== "string" || uid === "") continue;
    items.push({ uid, summary, completed: status === "completed" });
  }
  return items;
}

/** Items still to buy first, ticked ones last; order within each group is kept. */
export function orderItems(items: TodoItem[]): TodoItem[] {
  return [...items.filter((item) => !item.completed), ...items.filter((item) => item.completed)];
}

/** Quick-add buttons from the integration, most added first. */
export function readQuickItems(hass: HomeAssistant | undefined): QuickItem[] {
  const raw = hass?.states[FREQUENT_ENTITY]?.attributes["items"];
  if (!Array.isArray(raw)) return [];
  const result: QuickItem[] = [];
  for (const entry of raw) {
    if (!isRecord(entry) || typeof entry["name"] !== "string" || entry["name"] === "") continue;
    result.push({
      name: entry["name"],
      icon: typeof entry["icon"] === "string" ? entry["icon"] : "mdi:cart-outline",
      count: typeof entry["count"] === "number" ? entry["count"] : 0,
    });
  }
  return result;
}

/**
 * Whether the list entity can be used right now. While ha-ica-todo reloads (after a
 * list is created or deleted) the entity is "unavailable" or gone for a few seconds.
 */
export type Availability = "ok" | "unavailable" | "gone";

export function availabilityOf(hass: HomeAssistant | undefined, entityId: string): Availability {
  const state = hass?.states[entityId]?.state;
  if (state === undefined) return "gone";
  return state === "unavailable" ? "unavailable" : "ok";
}

/**
 * Live items of a todo entity, the same subscription Home Assistant's own todo card uses.
 * Resolves to a function that stops the subscription.
 */
export async function subscribeItems(
  hass: HomeAssistant,
  entityId: string,
  onItems: (items: TodoItem[]) => void,
): Promise<() => void> {
  if (!hass.connection) throw new Error("No connection to Home Assistant");
  const unsubscribe = await hass.connection.subscribeMessage(
    (message: unknown) => onItems(parseItems(message)),
    { type: "todo/item/subscribe", entity_id: entityId },
  );
  return () => {
    try {
      void Promise.resolve(unsubscribe()).catch(() => undefined);
    } catch {
      // The connection may already be closed; nothing left to stop
    }
  };
}
