import { afterEach, describe, expect, it, vi } from "vitest";
import {
  loadGroupByCategory,
  loadSelectedList,
  saveGroupByCategory,
  saveSelectedList,
} from "./storage";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("selected list storage", () => {
  it("returns null when nothing is saved", () => {
    expect(loadSelectedList()).toBeNull();
  });

  it("saves, loads and clears the choice", () => {
    saveSelectedList("ABC-1");
    expect(loadSelectedList()).toBe("ABC-1");
    saveSelectedList(null);
    expect(loadSelectedList()).toBeNull();
  });

  it("keeps the choice in this browser's localStorage under a namespaced key", () => {
    saveSelectedList("ABC-1");
    expect(window.localStorage.getItem("handla:selected-list")).toBe("ABC-1");
  });

  it("survives blocked storage when reading", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(loadSelectedList()).toBeNull();
  });

  it("survives blocked storage when writing and clearing", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => saveSelectedList("ABC-1")).not.toThrow();
    expect(() => saveSelectedList(null)).not.toThrow();
  });
});

describe("group by category storage", () => {
  it("is on by default", () => {
    expect(loadGroupByCategory()).toBe(true);
  });

  it("remembers off and on", () => {
    saveGroupByCategory(false);
    expect(loadGroupByCategory()).toBe(false);
    expect(window.localStorage.getItem("handla:group-by-category")).toBe("off");
    saveGroupByCategory(true);
    expect(loadGroupByCategory()).toBe(true);
  });

  it("survives blocked storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(loadGroupByCategory()).toBe(true);
    expect(() => saveGroupByCategory(false)).not.toThrow();
  });
});
