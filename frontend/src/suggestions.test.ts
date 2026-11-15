import { describe, expect, it } from "vitest";
import {
  filterSuggestions,
  parseItemSuggestions,
  pickedText,
  splitTyped,
  type ItemSuggestion,
} from "./suggestions";

const s = (name: string, groupId = 10): ItemSuggestion => ({
  name,
  groupId,
  source: "history",
  count: 1,
});

describe("parseItemSuggestions", () => {
  it("reads names, groups, sources and counts in order", () => {
    const result = parseItemSuggestions({
      items: [{ name: " Mjölk ", group_id: 10, source: "history", count: 4 }, { name: "Smör" }],
    });
    expect(result).toEqual([
      { name: "Mjölk", groupId: 10, source: "history", count: 4 },
      { name: "Smör", groupId: 12, source: "", count: 0 },
    ]);
  });

  it("skips entries without a name and ignores a bad answer", () => {
    expect(
      parseItemSuggestions({ items: [null, "x", {}, { name: "" }, { name: 3 }, { name: "Ost" }] }),
    ).toHaveLength(1);
    expect(parseItemSuggestions({})).toEqual([]);
    expect(parseItemSuggestions({ items: "x" })).toEqual([]);
  });
});

describe("splitTyped", () => {
  it.each([
    ["2 st toal", "2 st ", "toal"],
    ["2 toal", "2 ", "toal"],
    ["1,5 kg potatis", "1,5 kg ", "potatis"],
    ["2–3 st gurka", "2–3 st ", "gurka"],
    ["2 ST toal", "2 ST ", "toal"],
    ["2kg mjöl", "2kg ", "mjöl"],
    ["2 lök", "2 ", "lök"],
    ["2", "2 ", ""],
    ["toal", "", "toal"],
    ["  toal", "", "toal"],
    ["", "", ""],
    ["st toal", "", "st toal"],
  ])("splits %j into prefix %j and query %j", (text, prefix, query) => {
    expect(splitTyped(text)).toEqual({ prefix, query });
  });
});

describe("pickedText", () => {
  it("keeps the typed quantity", () => {
    expect(pickedText("2 st ", "Toalettpapper")).toBe("2 st Toalettpapper");
    expect(pickedText("", "Toalettpapper")).toBe("Toalettpapper");
  });
});

describe("filterSuggestions", () => {
  const all = [
    s("Hushållspapper"),
    s("Toalettpapper"),
    s("Gröna ärtor"),
    s("Bakpapper"),
    s("Papper"),
  ];

  it("shows nothing below two characters", () => {
    expect(filterSuggestions(all, "")).toEqual([]);
    expect(filterSuggestions(all, "p")).toEqual([]);
    expect(filterSuggestions(all, " p ")).toEqual([]);
  });

  it("puts names that start with the text first, then a word that starts, then contains", () => {
    const names = filterSuggestions(
      [s("Bakpapper"), s("Hushållspapper"), s("Papper"), s("Wallpaper kräm"), s("Eko papper")],
      "pap",
    ).map((x) => x.name);
    expect(names).toEqual([
      "Papper",
      "Eko papper",
      "Bakpapper",
      "Hushållspapper",
      "Wallpaper kräm",
    ]);
  });

  it("keeps the server order within each group and ignores case", () => {
    const names = filterSuggestions([s("Toa B"), s("toa A")], "TOA").map((x) => x.name);
    expect(names).toEqual(["Toa B", "toa A"]);
  });

  it("limits the answer", () => {
    const many = Array.from({ length: 30 }, (_, i) => s(`Gurka ${i}`));
    expect(filterSuggestions(many, "gu")).toHaveLength(8);
    expect(filterSuggestions(many, "gu", 12)).toHaveLength(12);
  });
});
