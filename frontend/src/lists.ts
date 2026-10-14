/** Reading the lists and status that the integration exposes as sensors. */

import type { HomeAssistant } from "./types";

export const LISTS_ENTITY = "sensor.handla_lists";
export const STATUS_ENTITY = "sensor.handla_status";

export interface ListInfo {
  entityId: string;
  offlineId: string;
  title: string;
  itemCount: number | null;
}

export interface ListsState {
  lists: ListInfo[];
  /** The household's active list (shared by all users). */
  activeOfflineId: string | null;
}

export type Status = "idle" | "creating" | "deleting" | "error";

export interface StatusState {
  status: Status;
  detail: string | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseList(raw: unknown): ListInfo | null {
  if (!isRecord(raw)) return null;
  const { entity_id: entityId, offline_id: offlineId, title, item_count: count } = raw;
  if (typeof entityId !== "string" || typeof offlineId !== "string" || typeof title !== "string") {
    return null;
  }
  return {
    entityId,
    offlineId,
    title,
    itemCount: typeof count === "number" ? count : null,
  };
}

/** The lists, or null when Handla is not running (sensor missing or unavailable). */
export function readLists(hass: HomeAssistant | undefined): ListsState | null {
  const entity = hass?.states[LISTS_ENTITY];
  if (!entity || entity.state === "unavailable" || entity.state === "unknown") return null;
  const raw = entity.attributes["lists"];
  const lists = Array.isArray(raw)
    ? raw.map(parseList).filter((item): item is ListInfo => item !== null)
    : [];
  const active = entity.attributes["active_offline_id"];
  return { lists, activeOfflineId: typeof active === "string" ? active : null };
}

export function readStatus(hass: HomeAssistant | undefined): StatusState {
  const entity = hass?.states[STATUS_ENTITY];
  const state = entity?.state;
  const status: Status =
    state === "creating" || state === "deleting" || state === "error" ? state : "idle";
  const detail = entity?.attributes["detail"];
  return { status, detail: typeof detail === "string" && detail !== "" ? detail : null };
}

const same = (a: string | null | undefined, b: string | null | undefined): boolean =>
  a != null && b != null && a.toLowerCase() === b.toLowerCase();

/**
 * The list this user is looking at: their own saved choice, else the household's
 * active list, else the first list.
 */
export function resolveSelected(
  lists: ListInfo[],
  stored: string | null,
  active: string | null,
): ListInfo | null {
  for (const wanted of [stored, active]) {
    const found = lists.find((item) => same(item.offlineId, wanted));
    if (found) return found;
  }
  return lists[0] ?? null;
}

export function listLabel(list: ListInfo): string {
  return list.itemCount === null ? list.title : `${list.title} (${list.itemCount})`;
}
