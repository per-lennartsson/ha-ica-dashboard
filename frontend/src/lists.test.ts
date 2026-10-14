import { describe, expect, it } from "vitest";
import {
  LISTS_ENTITY,
  STATUS_ENTITY,
  listLabel,
  readLists,
  readStatus,
  resolveSelected,
  type ListInfo,
} from "./lists";
import type { HomeAssistant } from "./types";

function hassWith(states: HomeAssistant["states"]): HomeAssistant {
  return { language: "sv", states, callService: async () => undefined };
}

const list = (offlineId: string, title: string, itemCount: number | null = 0): ListInfo => ({
  entityId: `todo.${offlineId.toLowerCase()}`,
  offlineId,
  title,
  itemCount,
});

describe("readLists", () => {
  it("parses the lists and the active one", () => {
    const hass = hassWith({
      [LISTS_ENTITY]: {
        state: "2",
        attributes: {
          lists: [
            { entity_id: "todo.a", offline_id: "A-1", title: "Bröd", item_count: 2 },
            { entity_id: "todo.b", offline_id: "B-2", title: "Mjölk", item_count: null },
          ],
          active_offline_id: "B-2",
        },
      },
    });
    expect(readLists(hass)).toEqual({
      lists: [
        { entityId: "todo.a", offlineId: "A-1", title: "Bröd", itemCount: 2 },
        { entityId: "todo.b", offlineId: "B-2", title: "Mjölk", itemCount: null },
      ],
      activeOfflineId: "B-2",
    });
  });

  it.each([undefined, {}, { [LISTS_ENTITY]: { state: "unavailable", attributes: {} } }])(
    "is null when Inköp is not running (%#)",
    (states) => {
      const hass = states === undefined ? undefined : hassWith(states as HomeAssistant["states"]);
      expect(readLists(hass)).toBeNull();
    },
  );

  it("is null while the sensor is unknown", () => {
    expect(
      readLists(hassWith({ [LISTS_ENTITY]: { state: "unknown", attributes: {} } })),
    ).toBeNull();
  });

  it("skips malformed lists and tolerates missing attributes", () => {
    const hass = hassWith({
      [LISTS_ENTITY]: {
        state: "1",
        attributes: {
          lists: [
            null,
            "x",
            { entity_id: "todo.a" },
            { entity_id: "todo.b", offline_id: "B", title: "Ok", item_count: "3" },
          ],
        },
      },
    });
    expect(readLists(hass)).toEqual({
      lists: [{ entityId: "todo.b", offlineId: "B", title: "Ok", itemCount: null }],
      activeOfflineId: null,
    });
  });

  it("treats a non-array lists attribute as empty", () => {
    const hass = hassWith({
      [LISTS_ENTITY]: { state: "0", attributes: { lists: "nope", active_offline_id: 5 } },
    });
    expect(readLists(hass)).toEqual({ lists: [], activeOfflineId: null });
  });
});

describe("readStatus", () => {
  it.each(["creating", "deleting", "error"] as const)("reads %s", (status) => {
    const hass = hassWith({ [STATUS_ENTITY]: { state: status, attributes: {} } });
    expect(readStatus(hass).status).toBe(status);
  });

  it.each([undefined, "idle", "unavailable", "weird"])("treats %s as idle", (state) => {
    const hass = hassWith(state ? { [STATUS_ENTITY]: { state, attributes: {} } } : {});
    expect(readStatus(hass)).toEqual({ status: "idle", detail: null });
  });

  it("reads the error detail", () => {
    const hass = hassWith({
      [STATUS_ENTITY]: { state: "error", attributes: { detail: "boom" } },
    });
    expect(readStatus(hass)).toEqual({ status: "error", detail: "boom" });
  });

  it("ignores empty or non-text details and a missing hass", () => {
    expect(
      readStatus(hassWith({ [STATUS_ENTITY]: { state: "error", attributes: { detail: "" } } }))
        .detail,
    ).toBeNull();
    expect(readStatus(undefined)).toEqual({ status: "idle", detail: null });
  });
});

describe("resolveSelected", () => {
  const lists = [list("A-1", "Bröd"), list("B-2", "Mjölk"), list("C-3", "Ägg")];

  it("prefers the user's own choice", () => {
    expect(resolveSelected(lists, "C-3", "B-2")?.offlineId).toBe("C-3");
  });

  it("compares ids case-insensitively", () => {
    expect(resolveSelected(lists, "c-3", null)?.offlineId).toBe("C-3");
  });

  it("falls back to the household's active list", () => {
    expect(resolveSelected(lists, "GONE", "B-2")?.offlineId).toBe("B-2");
    expect(resolveSelected(lists, null, "B-2")?.offlineId).toBe("B-2");
  });

  it("falls back to the first list, then to nothing", () => {
    expect(resolveSelected(lists, null, null)?.offlineId).toBe("A-1");
    expect(resolveSelected(lists, "GONE", "ALSO-GONE")?.offlineId).toBe("A-1");
    expect(resolveSelected([], "A-1", "A-1")).toBeNull();
  });
});

describe("listLabel", () => {
  it("shows the number of open items when known", () => {
    expect(listLabel(list("A", "Bröd", 3))).toBe("Bröd (3)");
    expect(listLabel(list("A", "Bröd", 0))).toBe("Bröd (0)");
    expect(listLabel(list("A", "Bröd", null))).toBe("Bröd");
  });
});
