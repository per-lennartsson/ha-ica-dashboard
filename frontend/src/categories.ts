/** Store groups (ICA article groups): reading the integration's answers and building sections. */

import { localizeOptional } from "./i18n";
import type { TodoItem } from "./items";

/** ICA's group for "not specified": items without a better group end up here. */
export const UNSPECIFIED_GROUP = 12;

export interface CategoryGroup {
  id: number;
  name: string;
}

export interface CategoryData {
  /** In the order of a walk through the store (the integration decides the order). */
  groups: CategoryGroup[];
  /** Group id by item uid. */
  groupOf: Record<string, number>;
}

export interface Section {
  group: CategoryGroup;
  items: TodoItem[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Groups and item groups from `handla.get_categories`; malformed entries are skipped. */
export function parseCategories(response: Record<string, unknown>): CategoryData {
  const groups: CategoryGroup[] = [];
  if (Array.isArray(response["groups"])) {
    for (const entry of response["groups"]) {
      if (!isRecord(entry)) continue;
      const { id, name } = entry;
      if (typeof id === "number" && typeof name === "string") groups.push({ id, name });
    }
  }
  const groupOf: Record<string, number> = {};
  const items = response["items"];
  if (isRecord(items)) {
    for (const [uid, id] of Object.entries(items)) {
      if (typeof id === "number") groupOf[uid] = id;
    }
  }
  return { groups, groupOf };
}

/** The group's name in the user's language, or ICA's own name for a group we have no text for. */
export function groupLabel(language: string | undefined, group: CategoryGroup): string {
  return localizeOptional(language, `category.${group.id}`) ?? group.name;
}

/**
 * Open items per group in store order; empty groups are left out. An item the integration
 * has not told us about yet (just added) or one in an unknown group goes to "unspecified".
 */
export function buildSections(items: TodoItem[], data: CategoryData): Section[] {
  const groups = data.groups.some((group) => group.id === UNSPECIFIED_GROUP)
    ? data.groups
    : [...data.groups, { id: UNSPECIFIED_GROUP, name: "Ospecificerad" }];
  const known = new Set(groups.map((group) => group.id));
  const bucket = (item: TodoItem): number => {
    const id = data.groupOf[item.uid];
    return id !== undefined && known.has(id) ? id : UNSPECIFIED_GROUP;
  };
  return groups
    .map((group) => ({ group, items: items.filter((item) => bucket(item) === group.id) }))
    .filter((section) => section.items.length > 0);
}

export interface CategorySuggestion {
  uid: string;
  name: string;
  current: number;
  suggested: number;
}

/** Suggestions from the service answer; malformed entries are skipped. */
export function parseCategorySuggestions(raw: unknown): CategorySuggestion[] {
  if (!Array.isArray(raw)) return [];
  const result: CategorySuggestion[] = [];
  for (const entry of raw) {
    if (!isRecord(entry)) continue;
    const { uid, name, current, suggested } = entry;
    if (
      typeof uid === "string" &&
      uid !== "" &&
      typeof name === "string" &&
      typeof current === "number" &&
      typeof suggested === "number"
    ) {
      result.push({ uid, name, current, suggested });
    }
  }
  return result;
}
