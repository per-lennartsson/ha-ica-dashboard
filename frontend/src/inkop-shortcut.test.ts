import { afterEach, describe, expect, it, vi } from "vitest";
import { InkopShortcut } from "./inkop-shortcut";
import { LISTS_ENTITY } from "./lists";
import type { HomeAssistant } from "./types";

interface Scenario {
  language?: string;
  lists?: Array<{ id: string; title: string; count: number | null }>;
  active?: string | null;
  listsState?: string;
}

const BREAD = { id: "A-1", title: "Bröd", count: 2 };
const MILK = { id: "B-2", title: "Mjölk", count: 7 };

function makeHass(scenario: Scenario = {}): HomeAssistant {
  const states: HomeAssistant["states"] = {};
  if (scenario.lists) {
    states[LISTS_ENTITY] = {
      state: scenario.listsState ?? String(scenario.lists.length),
      attributes: {
        lists: scenario.lists.map((item) => ({
          entity_id: `todo.ica_${item.id.toLowerCase()}`,
          offline_id: item.id,
          title: item.title,
          item_count: item.count,
        })),
        active_offline_id: scenario.active ?? null,
      },
    };
  }
  return { language: scenario.language ?? "sv", states, callService: async () => undefined };
}

async function mount(
  hass?: HomeAssistant,
  config: object = { type: "custom:inkop-shortcut" },
): Promise<InkopShortcut> {
  const card = document.createElement("inkop-shortcut") as InkopShortcut;
  card.setConfig(config as never);
  if (hass) card.hass = hass;
  document.body.appendChild(card);
  await card.updateComplete;
  return card;
}

const root = (card: InkopShortcut) => card.shadowRoot as ShadowRoot;
const surface = (card: InkopShortcut) => root(card).querySelector(".card") as HTMLElement;
const count = (card: InkopShortcut) =>
  root(card).querySelector('[data-testid="count"]')?.textContent;
const listName = (card: InkopShortcut) =>
  root(card).querySelector('[data-testid="list"]')?.textContent;

afterEach(() => {
  document.body.innerHTML = "";
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
  vi.restoreAllMocks();
});

describe("what it shows", () => {
  it("shows the open items and name of the household's active list", async () => {
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }));

    expect(count(card)).toBe("7");
    expect(listName(card)).toBe("Mjölk");
    expect(root(card).textContent).toContain("att handla");
  });

  it("prefers this user's own choice of list", async () => {
    window.localStorage.setItem("inkop:selected-list", "A-1");
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }));

    expect(count(card)).toBe("2");
    expect(listName(card)).toBe("Bröd");
  });

  it("shows 0 when everything is bought", async () => {
    const card = await mount(
      makeHass({ lists: [{ id: "A-1", title: "Bröd", count: 0 }], active: "A-1" }),
    );

    expect(count(card)).toBe("0");
  });

  it("says the count is unknown while the list is unavailable", async () => {
    const card = await mount(
      makeHass({ lists: [{ id: "A-1", title: "Bröd", count: null }], active: "A-1" }),
    );

    expect(count(card)).toBe("–");
    expect(root(card).textContent).toContain("Okänt antal");
  });

  it("uses a configured title instead of the list name", async () => {
    const card = await mount(makeHass({ lists: [BREAD], active: "A-1" }), {
      type: "custom:inkop-shortcut",
      title: "Handla",
    });

    expect(listName(card)).toBe("Handla");
  });

  it("copes with there being no lists", async () => {
    const card = await mount(makeHass({ lists: [] }));

    expect(count(card)).toBe("–");
    expect(listName(card)).toBe("Ingen lista");
  });

  it.each([undefined, { lists: [BREAD], listsState: "unavailable" }])(
    "says Inköp is not running without data (%#)",
    async (scenario) => {
      const card = await mount(scenario ? makeHass(scenario) : undefined);

      expect(root(card).textContent).toContain("Inköp körs inte");
      expect(count(card)).toBeUndefined();
    },
  );

  it("renders in English", async () => {
    const card = await mount(makeHass({ lists: [MILK], active: "B-2", language: "en" }));

    expect(root(card).textContent).toContain("to buy");
  });

  it("follows live changes", async () => {
    const card = await mount(makeHass({ lists: [BREAD], active: "A-1" }));
    card.hass = makeHass({ lists: [{ ...BREAD, count: 9 }], active: "A-1" });
    await card.updateComplete;

    expect(count(card)).toBe("9");
  });

  it("renders nothing until it has a configuration", async () => {
    const card = document.createElement("inkop-shortcut") as InkopShortcut;
    document.body.appendChild(card);
    await card.updateComplete;

    expect(root(card).querySelector(".card")).toBeNull();
  });
});

describe("opening the shopping view", () => {
  const withPath = { type: "custom:inkop-shortcut", navigation_path: "/lovelace/inkop" };
  const hass = () => makeHass({ lists: [BREAD], active: "A-1" });

  it("navigates on tap", async () => {
    const events: Event[] = [];
    window.addEventListener("location-changed", (event) => events.push(event), { once: true });
    const card = await mount(hass(), withPath);

    surface(card).click();

    expect(window.location.pathname).toBe("/lovelace/inkop");
    expect(events).toHaveLength(1);
  });

  it.each(["Enter", " "])(
    "navigates on the %j key, so it works without a touch screen",
    async (key) => {
      const card = await mount(hass(), withPath);

      surface(card).dispatchEvent(new KeyboardEvent("keydown", { key, cancelable: true }));

      expect(window.location.pathname).toBe("/lovelace/inkop");
    },
  );

  it("ignores other keys", async () => {
    const card = await mount(hass(), withPath);

    surface(card).dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));

    expect(window.location.pathname).toBe("/");
  });

  it("is announced as a button that can be focused", async () => {
    const card = await mount(hass(), withPath);

    expect(surface(card).getAttribute("role")).toBe("button");
    expect(surface(card).getAttribute("tabindex")).toBe("0");
    expect(surface(card).getAttribute("aria-label")).toBe(
      "2 att handla på Bröd. Öppna inköpslistan.",
    );
    expect(surface(card).classList.contains("tappable")).toBe(true);
    expect(root(card).querySelector(".chevron")).not.toBeNull();
  });

  it("is a plain count without a navigation path", async () => {
    const card = await mount(hass());

    surface(card).click();
    surface(card).dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));

    expect(window.location.pathname).toBe("/");
    expect(surface(card).getAttribute("role")).toBeNull();
    expect(surface(card).getAttribute("tabindex")).toBeNull();
    expect(surface(card).getAttribute("aria-label")).toBe("2 att handla på Bröd");
    expect(root(card).querySelector(".chevron")).toBeNull();
  });

  it("has no chevron when Inköp is not running", async () => {
    const card = await mount(makeHass(), withPath);

    expect(root(card).querySelector(".chevron")).toBeNull();
  });
});

describe("configuration", () => {
  it("rejects a configuration that is not an object", () => {
    const card = document.createElement("inkop-shortcut") as InkopShortcut;
    expect(() => card.setConfig(null as never)).toThrow("Ogiltig kortkonfiguration.");
  });

  it.each(["lovelace/inkop", "//evil.example", "https://example.com", 5])(
    "rejects the navigation path %j",
    (path) => {
      const card = document.createElement("inkop-shortcut") as InkopShortcut;
      expect(() =>
        card.setConfig({ type: "custom:inkop-shortcut", navigation_path: path } as never),
      ).toThrow("navigation_path måste börja med /");
    },
  );

  it("reports a card size and a stub configuration", () => {
    const card = document.createElement("inkop-shortcut") as InkopShortcut;
    expect(card.getCardSize()).toBe(1);
    expect(InkopShortcut.getStubConfig()).toEqual({});
  });

  it("is listed once for the card picker", () => {
    expect(customElements.get("inkop-shortcut")).toBe(InkopShortcut);
    expect(window.customCards?.filter((c) => c.type === "inkop-shortcut")).toHaveLength(1);
  });
});
