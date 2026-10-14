import { describe, expect, it } from "vitest";
import { en, localize, pickLanguage, sv } from "./i18n";

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
    expect(localize("sv", "card.title")).toBe("Inköp");
    expect(localize("en", "card.title")).toBe("Shopping");
  });

  it("defaults to Swedish when no language is known", () => {
    expect(localize(undefined, "card.title")).toBe("Inköp");
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
