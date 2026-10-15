import { describe, expect, it, vi } from "vitest";
import {
  addItem,
  clearTicked,
  createList,
  deleteList,
  errorMessage,
  extractItems,
  removeItem,
  responseOf,
  suggestListName,
  tickItem,
} from "./api";
import type { HomeAssistant } from "./types";

function hassReturning(result: unknown) {
  const callService = vi.fn().mockResolvedValue(result);
  const hass: HomeAssistant = { language: "sv", states: {}, callService };
  return { hass, callService };
}

describe("responseOf", () => {
  it("unwraps the response of a service call", () => {
    expect(responseOf({ context: {}, response: { name: "x" } })).toEqual({ name: "x" });
  });

  it.each([undefined, null, "x", 3, {}, { response: null }, { response: "x" }])(
    "gives an empty object for %j",
    (value) => {
      expect(responseOf(value)).toEqual({});
    },
  );
});

describe("errorMessage", () => {
  it.each([
    [new Error("boom"), "boom"],
    [{ message: "from ha" }, "from ha"],
    ["plain", "plain"],
    [new Error(""), "Unknown error"],
    [{ message: 5 }, "Unknown error"],
    [null, "Unknown error"],
    ["", "Unknown error"],
  ])("%j -> %s", (err, expected) => {
    expect(errorMessage(err)).toBe(expected);
  });
});

describe("suggestListName", () => {
  it("asks the integration and returns the name", async () => {
    const { hass, callService } = hassReturning({ response: { name: "Att handla 14 oktober" } });
    expect(await suggestListName(hass)).toBe("Att handla 14 oktober");
    expect(callService).toHaveBeenCalledWith(
      "handla",
      "suggest_list_name",
      {},
      undefined,
      false,
      true,
    );
  });

  it("returns an empty name when there is no usable answer", async () => {
    expect(await suggestListName(hassReturning({ response: { name: 5 } }).hass)).toBe("");
    expect(await suggestListName(hassReturning(undefined).hass)).toBe("");
  });
});

describe("createList", () => {
  it("creates the list, makes it active and returns its id", async () => {
    const { hass, callService } = hassReturning({ response: { offline_id: "NEW-1" } });
    expect(await createList(hass, "Veckan")).toBe("NEW-1");
    expect(callService).toHaveBeenCalledWith(
      "handla",
      "create_list",
      { title: "Veckan", set_active: true },
      undefined,
      false,
      true,
    );
  });

  it("returns null when the answer has no id", async () => {
    expect(await createList(hassReturning({ response: {} }).hass, "X")).toBeNull();
  });

  it("turns failures into readable errors and keeps the cause", async () => {
    const cause = { message: "Another list operation is still running." };
    const hass: HomeAssistant = {
      language: "sv",
      states: {},
      callService: vi.fn().mockRejectedValue(cause),
    };
    await expect(createList(hass, "X")).rejects.toMatchObject({
      message: "Another list operation is still running.",
      cause,
    });
  });
});

describe("deleteList", () => {
  it("calls delete_list with the entity id", async () => {
    const { hass, callService } = hassReturning(undefined);
    await deleteList(hass, "todo.ica_veckan");
    expect(callService).toHaveBeenCalledWith(
      "handla",
      "delete_list",
      { entity_id: "todo.ica_veckan" },
      undefined,
      false,
      false,
    );
  });
});

describe("addItem", () => {
  it("adds without confirmation by default and parses the answer", async () => {
    const { hass, callService } = hassReturning({
      response: { added: true, duplicate: false, item: "2 st gurka", duplicates: [] },
    });
    expect(await addItem(hass, "todo.a", "2 st gurka")).toEqual({
      added: true,
      duplicate: false,
      item: "2 st gurka",
      duplicates: [],
    });
    expect(callService).toHaveBeenCalledWith(
      "handla",
      "add_item",
      { entity_id: "todo.a", item: "2 st gurka", confirm_duplicate: false },
      undefined,
      false,
      true,
    );
  });

  it("reports a duplicate that was not added", async () => {
    const { hass } = hassReturning({
      response: {
        added: false,
        duplicate: true,
        item: "mjölk",
        duplicates: [{ uid: "u1", summary: "1 l mjölk" }],
      },
    });
    expect(await addItem(hass, "todo.a", "mjölk")).toEqual({
      added: false,
      duplicate: true,
      item: "mjölk",
      duplicates: [{ uid: "u1", summary: "1 l mjölk" }],
    });
  });

  it("passes the confirmation on", async () => {
    const { hass, callService } = hassReturning({ response: { added: true } });
    await addItem(hass, "todo.a", "mjölk", true);
    expect(callService.mock.calls[0]?.[2]).toMatchObject({ confirm_duplicate: true });
  });

  it("copes with a missing or malformed answer", async () => {
    const result = await addItem(hassReturning(undefined).hass, "todo.a", "mjölk");
    expect(result).toEqual({ added: false, duplicate: false, item: "mjölk", duplicates: [] });

    const odd = await addItem(
      hassReturning({
        response: {
          added: "yes",
          item: 5,
          duplicates: [null, "x", { uid: 1 }, { uid: "u", summary: "s" }],
        },
      }).hass,
      "todo.a",
      "x",
    );
    expect(odd).toEqual({
      added: false,
      duplicate: false,
      item: "x",
      duplicates: [{ uid: "u", summary: "s" }],
    });
  });

  it("turns failures into readable errors", async () => {
    const hass: HomeAssistant = {
      language: "sv",
      states: {},
      callService: vi.fn().mockRejectedValue({ message: "list not available" }),
    };
    await expect(addItem(hass, "todo.a", "mjölk")).rejects.toThrow("list not available");
  });
});

describe("tickItem, removeItem and clearTicked", () => {
  it("ticks and unticks by uid", async () => {
    const { hass, callService } = hassReturning(undefined);
    await tickItem(hass, "todo.a", "u1", true);
    await tickItem(hass, "todo.a", "u1", false);
    expect(callService.mock.calls[0]).toEqual([
      "handla",
      "tick_item",
      { entity_id: "todo.a", item: "u1", ticked: true },
      undefined,
      false,
      false,
    ]);
    expect(callService.mock.calls[1]?.[2]).toMatchObject({ ticked: false });
  });

  it("removes by uid", async () => {
    const { hass, callService } = hassReturning(undefined);
    await removeItem(hass, "todo.a", "u1");
    expect(callService).toHaveBeenCalledWith(
      "handla",
      "remove_item",
      { entity_id: "todo.a", item: "u1" },
      undefined,
      false,
      false,
    );
  });

  it("clears the ticked items of a list", async () => {
    const { hass, callService } = hassReturning(undefined);
    await clearTicked(hass, "todo.a");
    expect(callService).toHaveBeenCalledWith(
      "handla",
      "clear_ticked",
      { entity_id: "todo.a" },
      undefined,
      false,
      false,
    );
  });
});

describe("extractItems", () => {
  it("sends the text and list and returns the suggestions", async () => {
    const { hass, callService } = hassReturning({
      context: {},
      response: {
        items: [
          { item: "2 st gurka", on_list: false, existing: null, selected: true },
          { item: "mjölk", on_list: true, existing: "1 l mjölk", selected: false },
        ],
      },
    });

    const result = await extractItems(hass, "todo.ica_a", "Gurksallad och mjölk");

    expect(callService).toHaveBeenCalledWith(
      "handla",
      "ai_extract_items",
      { entity_id: "todo.ica_a", text: "Gurksallad och mjölk" },
      undefined,
      false,
      true,
    );
    expect(result.map((s) => [s.item, s.onList, s.selected])).toEqual([
      ["2 st gurka", false, true],
      ["mjölk", true, false],
    ]);
  });

  it("gives nothing for an answer without items", async () => {
    const { hass } = hassReturning({ context: {}, response: {} });
    expect(await extractItems(hass, "todo.ica_a", "x")).toEqual([]);
  });

  it("turns a failed call into an Error with a readable message", async () => {
    const callService = vi.fn().mockRejectedValue({ message: "The AI provider failed: credits" });
    const hass: HomeAssistant = { language: "sv", states: {}, callService };
    await expect(extractItems(hass, "todo.ica_a", "x")).rejects.toThrow("credits");
  });
});
