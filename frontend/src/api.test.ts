import { describe, expect, it, vi } from "vitest";
import { createList, deleteList, errorMessage, responseOf, suggestListName } from "./api";
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
      "inkop",
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
      "inkop",
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
      "inkop",
      "delete_list",
      { entity_id: "todo.ica_veckan" },
      undefined,
      false,
      false,
    );
  });
});
