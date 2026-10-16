import { describe, expect, it, vi } from "vitest";
import {
  FREQUENT_ENTITY,
  availabilityOf,
  orderItems,
  parseItems,
  readQuickItems,
  subscribeItems,
  type TodoItem,
} from "./items";
import type { HomeAssistant } from "./types";

const hassWith = (
  states: HomeAssistant["states"],
  connection?: HomeAssistant["connection"],
): HomeAssistant => ({
  language: "sv",
  states,
  callService: async () => undefined,
  ...(connection ? { connection } : {}),
});

describe("parseItems", () => {
  it("reads the items of a subscription message", () => {
    expect(
      parseItems({
        items: [
          { uid: "1", summary: "mjölk", status: "needs_action" },
          { uid: "2", summary: "bröd", status: "completed", due: "2026-10-14" },
        ],
      }),
    ).toEqual([
      { uid: "1", summary: "mjölk", completed: false },
      { uid: "2", summary: "bröd", completed: true },
    ]);
  });

  it.each([undefined, null, "x", 3, [], {}, { items: "no" }, { items: null }])(
    "gives nothing for %j",
    (message) => {
      expect(parseItems(message)).toEqual([]);
    },
  );

  it("skips malformed entries but keeps the good ones", () => {
    expect(
      parseItems({
        items: [
          null,
          "x",
          { summary: "no uid" },
          { uid: 5, summary: "numeric uid" },
          { uid: "", summary: "empty uid" },
          { uid: "3" },
          { uid: "4", summary: "ok" },
        ],
      }),
    ).toEqual([{ uid: "4", summary: "ok", completed: false }]);
  });
});

describe("orderItems", () => {
  const item = (uid: string, completed: boolean): TodoItem => ({ uid, summary: uid, completed });

  it("puts open items first and keeps the order inside each group", () => {
    const ordered = orderItems([
      item("a", true),
      item("b", false),
      item("c", true),
      item("d", false),
    ]);
    expect(ordered.map((i) => i.uid)).toEqual(["b", "d", "a", "c"]);
  });

  it("does not change its input", () => {
    const input = [item("a", true), item("b", false)];
    orderItems(input);
    expect(input.map((i) => i.uid)).toEqual(["a", "b"]);
  });
});

describe("readQuickItems", () => {
  it("reads name, icon and count", () => {
    const hass = hassWith({
      [FREQUENT_ENTITY]: {
        state: "2",
        attributes: {
          items: [
            { name: "mjölk", icon: "mdi:cow", count: 5 },
            { name: "ägg", icon: "mdi:egg", count: 0 },
          ],
        },
      },
    });
    expect(readQuickItems(hass)).toEqual([
      { name: "mjölk", icon: "mdi:cow", count: 5, pinned: false },
      { name: "ägg", icon: "mdi:egg", count: 0, pinned: false },
    ]);
  });

  it("reads the pinned flag", () => {
    const hass = hassWith({
      [FREQUENT_ENTITY]: { state: "1", attributes: { items: [{ name: "x", pinned: true }] } },
    });
    expect(readQuickItems(hass)[0]?.pinned).toBe(true);
  });

  it("falls back to a cart icon and count 0, and skips nameless entries", () => {
    const hass = hassWith({
      [FREQUENT_ENTITY]: {
        state: "1",
        attributes: { items: [{ name: "x" }, { name: "" }, { icon: "mdi:cow" }, null, 7] },
      },
    });
    expect(readQuickItems(hass)).toEqual([
      { name: "x", icon: "mdi:cart-outline", count: 0, pinned: false },
    ]);
  });

  it.each([
    undefined,
    hassWith({}),
    hassWith({ [FREQUENT_ENTITY]: { state: "0", attributes: {} } }),
  ])("is empty without data (%#)", (hass) => {
    expect(readQuickItems(hass)).toEqual([]);
  });
});

describe("availabilityOf", () => {
  it("tells ok, unavailable and gone apart", () => {
    const hass = hassWith({
      "todo.a": { state: "3", attributes: {} },
      "todo.b": { state: "unavailable", attributes: {} },
    });
    expect(availabilityOf(hass, "todo.a")).toBe("ok");
    expect(availabilityOf(hass, "todo.b")).toBe("unavailable");
    expect(availabilityOf(hass, "todo.c")).toBe("gone");
    expect(availabilityOf(undefined, "todo.a")).toBe("gone");
  });

  it("treats 0 open items as available", () => {
    expect(availabilityOf(hassWith({ "todo.a": { state: "0", attributes: {} } }), "todo.a")).toBe(
      "ok",
    );
  });
});

describe("subscribeItems", () => {
  it("subscribes like Home Assistant's own todo card and forwards parsed items", async () => {
    let deliver: (message: unknown) => void = () => undefined;
    const unsubscribe = vi.fn();
    const subscribeMessage = vi.fn(async (callback: (m: unknown) => void) => {
      deliver = callback;
      return unsubscribe;
    });
    const received: TodoItem[][] = [];

    const stop = await subscribeItems(
      hassWith({}, { subscribeMessage } as never),
      "todo.a",
      (items) => received.push(items),
    );
    deliver({ items: [{ uid: "1", summary: "mjölk", status: "needs_action" }] });

    expect(subscribeMessage).toHaveBeenCalledWith(expect.any(Function), {
      type: "todo/item/subscribe",
      entity_id: "todo.a",
    });
    expect(received).toEqual([[{ uid: "1", summary: "mjölk", completed: false }]]);
    stop();
    expect(unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("rejects without a connection", async () => {
    await expect(subscribeItems(hassWith({}), "todo.a", () => undefined)).rejects.toThrow(
      "No connection",
    );
  });

  it("never throws when stopping a connection that is already closed", async () => {
    const throwing = vi.fn(() => {
      throw new Error("closed");
    });
    const rejecting = vi.fn(async () => {
      throw new Error("closed");
    });
    for (const unsubscribe of [throwing, rejecting]) {
      const subscribeMessage = vi.fn(async () => unsubscribe);
      const stop = await subscribeItems(
        hassWith({}, { subscribeMessage } as never),
        "todo.a",
        () => undefined,
      );
      expect(() => stop()).not.toThrow();
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
});
