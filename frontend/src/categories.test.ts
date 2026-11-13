import { describe, expect, it } from "vitest";
import {
  buildSections,
  groupLabel,
  parseCategories,
  parseCategorySuggestions,
  type CategoryData,
} from "./categories";
import type { TodoItem } from "./items";

const item = (uid: string, summary = uid): TodoItem => ({ uid, summary, completed: false });

const DATA: CategoryData = {
  groups: [
    { id: 4, name: "Frukt & Grönt" },
    { id: 10, name: "Mejeri" },
    { id: 12, name: "Ospecificerad" },
  ],
  groupOf: { milk: 10, apple: 4, odd: 99, other: 12 },
};

describe("parseCategories", () => {
  it("reads groups and item groups, skipping malformed entries", () => {
    const data = parseCategories({
      groups: [{ id: 4, name: "Frukt" }, { id: "x", name: "bad" }, { id: 5 }, "junk", null],
      items: { a: 4, b: "x", c: 10 },
    });
    expect(data).toEqual({ groups: [{ id: 4, name: "Frukt" }], groupOf: { a: 4, c: 10 } });
  });

  it("gives empty data for an empty answer", () => {
    expect(parseCategories({})).toEqual({ groups: [], groupOf: {} });
    expect(parseCategories({ groups: "x", items: [1] })).toEqual({ groups: [], groupOf: {} });
  });
});

describe("groupLabel", () => {
  const group = { id: 10, name: "Mejeri (ICA)" };
  it("uses our own text in the user's language", () => {
    expect(groupLabel("sv", group)).toBe("Mejeri");
    expect(groupLabel("en", group)).toBe("Dairy");
  });
  it("falls back to ICA's name for a group we have no text for", () => {
    expect(groupLabel("sv", { id: 99, name: "Nytt" })).toBe("Nytt");
  });
});

describe("buildSections", () => {
  it("puts open items in store order and leaves empty groups out", () => {
    const sections = buildSections([item("milk"), item("apple"), item("other")], DATA);
    expect(sections.map((s) => [s.group.id, s.items.map((i) => i.uid)])).toEqual([
      [4, ["apple"]],
      [10, ["milk"]],
      [12, ["other"]],
    ]);
  });

  it("puts new and unknown-group items in the unspecified group", () => {
    const sections = buildSections([item("new"), item("odd")], DATA);
    expect(sections).toHaveLength(1);
    expect(sections[0]?.group.id).toBe(12);
    expect(sections[0]?.items.map((i) => i.uid)).toEqual(["new", "odd"]);
  });

  it("makes an unspecified section even if the integration sent no such group", () => {
    const sections = buildSections([item("x")], { groups: [{ id: 4, name: "F" }], groupOf: {} });
    expect(sections.map((s) => s.group.id)).toEqual([12]);
  });

  it("gives nothing for no items", () => {
    expect(buildSections([], DATA)).toEqual([]);
  });
});

describe("parseCategorySuggestions", () => {
  it("keeps valid suggestions only", () => {
    expect(
      parseCategorySuggestions([
        { uid: "a", name: "mjölk", current: 12, suggested: 10 },
        { uid: "", name: "x", current: 12, suggested: 10 },
        { uid: "b", name: "x", current: "12", suggested: 10 },
        "junk",
      ]),
    ).toEqual([{ uid: "a", name: "mjölk", current: 12, suggested: 10 }]);
  });
  it("gives nothing for a non-list", () => {
    expect(parseCategorySuggestions(undefined)).toEqual([]);
  });
});
