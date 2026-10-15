import { describe, expect, it } from "vitest";
import { AI_ENTITY, isAiReady, parseSuggestions } from "./ai";
import type { HomeAssistant } from "./types";

const hassWith = (state?: string): HomeAssistant =>
  ({
    language: "sv",
    states: state === undefined ? {} : { [AI_ENTITY]: { state, attributes: {} } },
  }) as unknown as HomeAssistant;

describe("isAiReady", () => {
  it("is true only for the ready state", () => {
    expect(isAiReady(hassWith("ready"))).toBe(true);
  });

  it.each(["off", "unavailable", "unknown", "", "on"])("is false for %j", (state) => {
    expect(isAiReady(hassWith(state))).toBe(false);
  });

  it("is false without the sensor or without hass", () => {
    expect(isAiReady(hassWith())).toBe(false);
    expect(isAiReady(undefined)).toBe(false);
  });
});

describe("parseSuggestions", () => {
  it("reads items and starts ones already on the list unticked", () => {
    const result = parseSuggestions([
      { item: "2 l mjölk", on_list: true, existing: "1 l Mjölk", selected: true },
      { item: " ost ", on_list: false, existing: null, selected: true },
      { item: "ägg" },
      { item: "smör", on_list: false, selected: false },
    ]);

    expect(result).toEqual([
      { item: "2 l mjölk", onList: true, existing: "1 l Mjölk", selected: false },
      { item: "ost", onList: false, existing: null, selected: true },
      { item: "ägg", onList: false, existing: null, selected: true },
      { item: "smör", onList: false, existing: null, selected: false },
    ]);
  });

  it.each([undefined, null, "x", 5, {}, [null, 3, "x", { item: 5 }, { item: "  " }]])(
    "gives nothing for %j",
    (raw) => {
      expect(parseSuggestions(raw)).toEqual([]);
    },
  );
});
