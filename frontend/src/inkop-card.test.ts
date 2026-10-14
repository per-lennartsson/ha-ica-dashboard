import { afterEach, describe, expect, it } from "vitest";
import { InkopCard, ITEMS_ENTITY } from "./inkop-card";
import type { HomeAssistant } from "./types";

function makeHass(language: string, count?: string): HomeAssistant {
  return {
    language,
    states: count === undefined ? {} : { [ITEMS_ENTITY]: { state: count, attributes: {} } },
    callService: async () => undefined,
  };
}

async function mount(hass?: HomeAssistant, config: object = { type: "custom:inkop-card" }) {
  const card = document.createElement("inkop-card") as InkopCard;
  card.setConfig(config as never);
  if (hass) card.hass = hass;
  document.body.appendChild(card);
  await card.updateComplete;
  return card;
}

const text = (card: InkopCard) => card.shadowRoot?.querySelector(".card")?.textContent ?? "";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("inkop-card", () => {
  it("is registered as a custom element and listed for the card picker", () => {
    expect(customElements.get("inkop-card")).toBe(InkopCard);
    expect(window.customCards?.filter((c) => c.type === "inkop-card")).toHaveLength(1);
  });

  it("renders in Swedish with the item count", async () => {
    const card = await mount(makeHass("sv", "3"));
    expect(card.shadowRoot?.querySelector("h2")?.textContent).toBe("Inköp");
    expect(text(card)).toContain("Inköpskortet är laddat.");
    expect(text(card)).toContain("3 varor att handla");
  });

  it("renders in English", async () => {
    const card = await mount(makeHass("en", "0"));
    expect(card.shadowRoot?.querySelector("h2")?.textContent).toBe("Shopping");
    expect(text(card)).toContain("0 items to buy");
  });

  it("uses a configured title", async () => {
    const card = await mount(makeHass("sv", "1"), { type: "custom:inkop-card", title: "Mat" });
    expect(card.shadowRoot?.querySelector("h2")?.textContent).toBe("Mat");
  });

  it.each([undefined, "unavailable", "unknown"])("says there is no data for %s", async (count) => {
    const card = await mount(makeHass("sv", count));
    expect(text(card)).toContain("Ingen data ännu");
  });

  it("works before Home Assistant has handed over its state", async () => {
    const card = await mount();
    expect(text(card)).toContain("Ingen data ännu");
  });

  it("updates when the state changes", async () => {
    const card = await mount(makeHass("sv", "3"));
    card.hass = makeHass("sv", "4");
    await card.updateComplete;
    expect(text(card)).toContain("4 varor att handla");
  });

  it("shows the build version", async () => {
    const card = await mount(makeHass("sv", "1"));
    expect(text(card)).toContain(`v${__INKOP_VERSION__}`);
  });

  it("renders nothing until it has a configuration", async () => {
    const card = document.createElement("inkop-card") as InkopCard;
    document.body.appendChild(card);
    await card.updateComplete;
    expect(card.shadowRoot?.querySelector(".card")).toBeNull();
  });

  it("rejects an invalid configuration", () => {
    const card = document.createElement("inkop-card") as InkopCard;
    expect(() => card.setConfig(null as never)).toThrow("Ogiltig kortkonfiguration.");
  });

  it("reports a card size and a stub configuration", () => {
    const card = document.createElement("inkop-card") as InkopCard;
    expect(card.getCardSize()).toBe(2);
    expect(InkopCard.getStubConfig()).toEqual({});
  });
});
