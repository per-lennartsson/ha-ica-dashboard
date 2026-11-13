import { describe, expect, it } from "vitest";
import { en, isCardLanguage, localize, pickLanguage, sv, withLanguage } from "./i18n";

describe("pickLanguage", () => {
  it.each([
    ["sv", "sv"],
    ["sv-SE", "sv"],
    ["SV", "sv"],
    ["en", "en"],
    ["en-GB", "en"],
    ["de", "en"],
    ["", "sv"],
    [undefined, "sv"],
  ] as const)("%s -> %s", (input, expected) => {
    expect(pickLanguage(input)).toBe(expected);
  });
});

describe("localize", () => {
  it("returns Swedish and English text", () => {
    expect(localize("sv", "card.title")).toBe("Handla");
    expect(localize("en", "card.title")).toBe("Shopping");
  });

  it("defaults to Swedish when no language is known", () => {
    expect(localize(undefined, "card.title")).toBe("Handla");
  });

  it("fills in parameters", () => {
    expect(localize("sv", "delete.confirm", { title: "Veckan" })).toBe(
      "Ta bort listan “Veckan” från ICA? Det går inte att ångra.",
    );
    expect(localize("en", "error.generic", { message: "boom" })).toBe("Something went wrong: boom");
  });

  it("fills in every occurrence of a parameter", () => {
    const text = localize("sv", "delete.confirm", { title: "A" });
    expect(text).not.toContain("{title}");
  });

  it("leaves unknown placeholders alone", () => {
    expect(localize("sv", "error.generic")).toBe("Något gick fel: {message}");
  });

  it("has the same keys in both languages", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(sv).sort());
  });

  it("uses the same placeholders in both languages", () => {
    const placeholders = (text: string) => text.match(/\{\w+\}/g)?.sort() ?? [];
    for (const key of Object.keys(sv) as Array<keyof typeof sv>) {
      expect(placeholders(en[key])).toEqual(placeholders(sv[key]));
    }
  });
});

describe("isCardLanguage", () => {
  it.each([
    ["sv", true],
    ["en", true],
    ["de", false],
    ["", false],
    [undefined, false],
  ] as const)("%s -> %s", (input, expected) => {
    expect(isCardLanguage(input)).toBe(expected);
  });
});

describe("withLanguage", () => {
  const hass = { language: "en", states: {} };

  it("returns hass itself without an override or when it already matches", () => {
    expect(withLanguage(hass, undefined)).toBe(hass);
    expect(withLanguage(hass, "en")).toBe(hass);
    expect(withLanguage(undefined, "sv")).toBeUndefined();
  });

  it("returns a copy in the chosen language and leaves hass alone", () => {
    const copy = withLanguage(hass, "sv");
    expect(copy?.language).toBe("sv");
    expect(copy?.states).toBe(hass.states);
    expect(hass.language).toBe("en");
  });

  it("returns the same copy for the same hass", () => {
    expect(withLanguage(hass, "sv")).toBe(withLanguage(hass, "sv"));
  });
});
