import { afterEach, describe, expect, it, vi } from "vitest";
import { HandlaCard } from "./handla-card";
import type { HandlaItems } from "./handla-items";
import { LISTS_ENTITY, STATUS_ENTITY } from "./lists";
import type { HomeAssistant } from "./types";

interface Scenario {
  language?: string;
  /** Omit to simulate Handla not running (no sensors at all). */
  lists?: Array<{ id: string; title: string; count?: number | null }>;
  active?: string | null;
  status?: string;
  detail?: string;
  listsState?: string;
}

const BREAD = { id: "A-1", title: "Bröd", count: 2 };
const MILK = { id: "B-2", title: "Mjölk", count: 0 };

type CallService = HomeAssistant["callService"];

function defaultCallService(): CallService {
  return vi.fn(async (_domain: string, service: string) => {
    if (service === "suggest_list_name") {
      return { context: {}, response: { name: "Att handla 14 oktober" } };
    }
    if (service === "create_list") return { context: {}, response: { offline_id: "NEW-1" } };
    return { context: {}, response: {} };
  });
}

function makeHass(scenario: Scenario = {}, callService: CallService = defaultCallService()) {
  const states: HomeAssistant["states"] = {};
  if (scenario.lists) {
    states[LISTS_ENTITY] = {
      state: scenario.listsState ?? String(scenario.lists.length),
      attributes: {
        lists: scenario.lists.map((item) => ({
          entity_id: `todo.ica_${item.id.toLowerCase()}`,
          offline_id: item.id,
          title: item.title,
          item_count: item.count ?? 0,
        })),
        active_offline_id: scenario.active ?? null,
      },
    };
    states[STATUS_ENTITY] = {
      state: scenario.status ?? "idle",
      attributes: scenario.detail ? { detail: scenario.detail } : {},
    };
  }
  const hass: HomeAssistant = { language: scenario.language ?? "sv", states, callService };
  return { hass, callService };
}

async function settle(card: HandlaCard): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await card.updateComplete;
}

async function mount(hass?: HomeAssistant, config: object = { type: "custom:handla-card" }) {
  const card = document.createElement("handla-card") as HandlaCard;
  card.setConfig(config as never);
  if (hass) card.hass = hass;
  document.body.appendChild(card);
  await card.updateComplete;
  return card;
}

const root = (card: HandlaCard) => card.shadowRoot as ShadowRoot;
const text = (card: HandlaCard) => root(card).querySelector(".card")?.textContent ?? "";
const button = (card: HandlaCard, action: string) =>
  root(card).querySelector<HTMLButtonElement>(`[data-action="${action}"]`);
const select = (card: HandlaCard) => root(card).querySelector<HTMLSelectElement>("select");
const input = (card: HandlaCard) => root(card).querySelector<HTMLInputElement>("input[type=text]");
const optionLabels = (card: HandlaCard) =>
  [...root(card).querySelectorAll("option")].map((option) => option.textContent?.trim());

async function click(card: HandlaCard, action: string): Promise<void> {
  button(card, action)?.click();
  await settle(card);
}

async function typeName(card: HandlaCard, value: string): Promise<void> {
  const field = input(card) as HTMLInputElement;
  field.value = value;
  field.dispatchEvent(new Event("input"));
  await card.updateComplete;
}

async function submit(card: HandlaCard): Promise<void> {
  root(card)
    .querySelector("form")
    ?.dispatchEvent(new Event("submit", { cancelable: true }));
  await settle(card);
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

afterEach(() => {
  document.body.innerHTML = "";
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("basics", () => {
  it("is registered as a custom element and listed for the card picker", () => {
    expect(customElements.get("handla-card")).toBe(HandlaCard);
    expect(window.customCards?.filter((c) => c.type === "handla-card")).toHaveLength(1);
  });

  it("renders nothing until it has a configuration", async () => {
    const card = document.createElement("handla-card") as HandlaCard;
    document.body.appendChild(card);
    await card.updateComplete;
    expect(root(card).querySelector(".card")).toBeNull();
  });

  it("rejects an invalid configuration", () => {
    const card = document.createElement("handla-card") as HandlaCard;
    expect(() => card.setConfig(null as never)).toThrow("Ogiltig kortkonfiguration.");
  });

  it("reports a card size and a stub configuration", () => {
    const card = document.createElement("handla-card") as HandlaCard;
    expect(card.getCardSize()).toBe(2);
    expect(HandlaCard.getStubConfig()).toEqual({});
  });

  it("uses a configured title", async () => {
    const card = await mount(makeHass({ lists: [BREAD] }).hass, {
      type: "custom:handla-card",
      title: "Mat",
    });
    expect(root(card).querySelector("h2")?.textContent).toBe("Mat");
  });

  it("renders in English", async () => {
    const card = await mount(makeHass({ lists: [BREAD], language: "en" }).hass);
    expect(root(card).querySelector("h2")?.textContent).toBe("Shopping");
    expect(button(card, "new-list")?.textContent?.trim()).toBe("New list");
  });
});

describe("when Handla is not running", () => {
  it("explains what to check, including ha-ica-todo", async () => {
    const card = await mount(makeHass().hass);
    expect(text(card)).toContain("ha-ica-todo");
    expect(root(card).querySelector('[data-testid="not-running"]')).not.toBeNull();
    expect(select(card)).toBeNull();
    expect(button(card, "new-list")).toBeNull();
  });

  it("says the same before Home Assistant has handed over its state", async () => {
    const card = await mount();
    expect(text(card)).toContain("ha-ica-todo");
  });

  it("says the same while the lists sensor is unavailable", async () => {
    const card = await mount(makeHass({ lists: [BREAD], listsState: "unavailable" }).hass);
    expect(text(card)).toContain("ha-ica-todo");
  });
});

describe("list picker", () => {
  it("shows every list with its open items and selects the household's active list", async () => {
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }).hass);
    expect(optionLabels(card)).toEqual(["Bröd (2)", "Mjölk (0)"]);
    expect(select(card)?.value).toBe("B-2");
  });

  it("prefers this user's saved choice over the household's active list", async () => {
    window.localStorage.setItem("handla:selected-list", "A-1");
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }).hass);
    expect(select(card)?.value).toBe("A-1");
  });

  it("ignores a saved choice for a list that no longer exists", async () => {
    window.localStorage.setItem("handla:selected-list", "GONE");
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }).hass);
    expect(select(card)?.value).toBe("B-2");
  });

  it("remembers a new choice in this browser only, without calling any service", async () => {
    const { hass, callService } = makeHass({ lists: [BREAD, MILK], active: "B-2" });
    const card = await mount(hass);

    const picker = select(card) as HTMLSelectElement;
    picker.value = "A-1";
    picker.dispatchEvent(new Event("change"));
    await card.updateComplete;

    expect(window.localStorage.getItem("handla:selected-list")).toBe("A-1");
    expect(select(card)?.value).toBe("A-1");
    expect(callService).not.toHaveBeenCalled();
  });

  it("still works when the browser blocks storage", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }).hass);
    const picker = select(card) as HTMLSelectElement;
    picker.value = "A-1";
    picker.dispatchEvent(new Event("change"));
    await card.updateComplete;
    expect(select(card)?.value).toBe("A-1");
  });

  it("follows changes in Home Assistant", async () => {
    const card = await mount(makeHass({ lists: [BREAD] }).hass);
    card.hass = makeHass({ lists: [BREAD, MILK] }).hass;
    await card.updateComplete;
    expect(optionLabels(card)).toEqual(["Bröd (2)", "Mjölk (0)"]);
  });

  it("invites you to create a list when there are none", async () => {
    const card = await mount(makeHass({ lists: [] }).hass);
    expect(root(card).querySelector('[data-testid="no-lists"]')).not.toBeNull();
    expect(select(card)).toBeNull();
    expect(button(card, "new-list")).not.toBeNull();
    expect(button(card, "delete-list")).toBeNull();
  });
});

describe("creating a list", () => {
  it("opens a form with the suggested name and focuses it", async () => {
    const { hass, callService } = makeHass({ lists: [BREAD] });
    const card = await mount(hass);

    await click(card, "new-list");

    expect(input(card)?.value).toBe("Att handla 14 oktober");
    expect(root(card).activeElement).toBe(input(card));
    expect(callService).toHaveBeenCalledWith(
      "handla",
      "suggest_list_name",
      {},
      undefined,
      false,
      true,
    );
    expect(select(card)).toBeNull();
  });

  it("does not overwrite a name the user has already started typing", async () => {
    const suggestion = deferred<unknown>();
    const callService = vi.fn(() => suggestion.promise) as unknown as CallService;
    const card = await mount(makeHass({ lists: [BREAD] }, callService).hass);

    button(card, "new-list")?.click();
    await card.updateComplete;
    await typeName(card, "Mitt namn");
    suggestion.resolve({ response: { name: "Att handla 14 oktober" } });
    await settle(card);

    expect(input(card)?.value).toBe("Mitt namn");
  });

  it("falls back to an empty field when no suggestion can be fetched", async () => {
    const callService = vi.fn().mockRejectedValue(new Error("no")) as unknown as CallService;
    const card = await mount(makeHass({ lists: [BREAD] }, callService).hass);

    await click(card, "new-list");

    expect(input(card)).not.toBeNull();
    expect(input(card)?.value).toBe("");
  });

  it("creates the list with the typed name, makes it this user's list and closes the form", async () => {
    const { hass, callService } = makeHass({ lists: [BREAD], active: "A-1" });
    const card = await mount(hass);
    await click(card, "new-list");
    await typeName(card, "  Fredagsmat ");

    await submit(card);

    expect(callService).toHaveBeenCalledWith(
      "handla",
      "create_list",
      { title: "Fredagsmat", set_active: true },
      undefined,
      false,
      true,
    );
    expect(window.localStorage.getItem("handla:selected-list")).toBe("NEW-1");
    expect(input(card)).toBeNull();
    expect(root(card).querySelector('[data-testid="error"]')).toBeNull();
  });

  it("asks for a name instead of creating a nameless list", async () => {
    const { hass, callService } = makeHass({ lists: [BREAD] });
    const card = await mount(hass);
    await click(card, "new-list");
    await typeName(card, "   ");
    (callService as ReturnType<typeof vi.fn>).mockClear();

    await submit(card);

    expect(root(card).querySelector('[data-testid="error"]')?.textContent).toContain(
      "Ange ett namn",
    );
    expect(callService).not.toHaveBeenCalled();
    expect(input(card)).not.toBeNull();
  });

  it("shows the error and keeps the form when creating fails", async () => {
    const callService = vi.fn(async (_d: string, service: string) => {
      if (service === "create_list") throw { message: "Another list operation is running." };
      return { response: { name: "X" } };
    }) as unknown as CallService;
    const card = await mount(makeHass({ lists: [BREAD] }, callService).hass);
    await click(card, "new-list");

    await submit(card);

    expect(root(card).querySelector('[data-testid="error"]')?.textContent).toContain(
      "Något gick fel: Another list operation is running.",
    );
    expect(input(card)).not.toBeNull();
    expect(button(card, "submit-create")?.disabled).toBe(false);
  });

  it("can be cancelled", async () => {
    const card = await mount(makeHass({ lists: [BREAD] }).hass);
    await click(card, "new-list");
    await typeName(card, "   ");
    await submit(card);
    expect(root(card).querySelector('[data-testid="error"]')).not.toBeNull();

    await click(card, "cancel");

    expect(input(card)).toBeNull();
    expect(select(card)).not.toBeNull();
    expect(root(card).querySelector('[data-testid="error"]')).toBeNull();
  });

  it("locks the controls while the call runs, so a second tap does nothing", async () => {
    const create = deferred<unknown>();
    const callService = vi.fn(async (_d: string, service: string) =>
      service === "create_list" ? create.promise : { response: { name: "X" } },
    ) as unknown as CallService;
    const card = await mount(makeHass({ lists: [BREAD] }, callService).hass);
    await click(card, "new-list");

    await submit(card);
    expect(button(card, "submit-create")?.disabled).toBe(true);
    expect(button(card, "cancel")?.disabled).toBe(true);
    expect(input(card)?.disabled).toBe(true);
    expect(root(card).querySelector('[data-testid="progress"]')?.textContent).toContain("Arbetar");
    await submit(card);
    const createCalls = (callService as ReturnType<typeof vi.fn>).mock.calls.filter(
      (call) => call[1] === "create_list",
    );
    expect(createCalls).toHaveLength(1);

    create.resolve({ response: { offline_id: "NEW-1" } });
    await settle(card);
    expect(root(card).querySelector('[data-testid="progress"]')).toBeNull();
    expect(button(card, "new-list")?.disabled).toBe(false);
  });
});

describe("deleting a list", () => {
  it("asks for confirmation naming the list", async () => {
    const { hass, callService } = makeHass({ lists: [BREAD, MILK], active: "B-2" });
    const card = await mount(hass);

    await click(card, "delete-list");

    expect(root(card).querySelector('[data-testid="confirm"]')?.textContent).toBe(
      "Ta bort listan “Mjölk” från ICA? Det går inte att ångra.",
    );
    expect(callService).not.toHaveBeenCalled();
    expect(select(card)).toBeNull();
  });

  it("deletes the list after confirmation and forgets it if it was this user's choice", async () => {
    window.localStorage.setItem("handla:selected-list", "B-2");
    const { hass, callService } = makeHass({ lists: [BREAD, MILK], active: "A-1" });
    const card = await mount(hass);
    await click(card, "delete-list");

    await click(card, "confirm-delete");

    expect(callService).toHaveBeenCalledWith(
      "handla",
      "delete_list",
      { entity_id: "todo.ica_b-2" },
      undefined,
      false,
      false,
    );
    expect(window.localStorage.getItem("handla:selected-list")).toBeNull();
    expect(root(card).querySelector('[data-testid="confirm"]')).toBeNull();
    expect(select(card)).not.toBeNull();
  });

  it("deletes the fallback list when the saved choice no longer exists, leaving storage alone", async () => {
    window.localStorage.setItem("handla:selected-list", "GONE");
    const { hass, callService } = makeHass({ lists: [BREAD, MILK], active: "B-2" });
    const card = await mount(hass);
    expect(select(card)?.value).toBe("B-2");

    await click(card, "delete-list");
    await click(card, "confirm-delete");

    expect(callService).toHaveBeenCalledWith(
      "handla",
      "delete_list",
      { entity_id: "todo.ica_b-2" },
      undefined,
      false,
      false,
    );
    expect(window.localStorage.getItem("handla:selected-list")).toBe("GONE");
  });

  it("does nothing when cancelled", async () => {
    const { hass, callService } = makeHass({ lists: [BREAD] });
    const card = await mount(hass);
    await click(card, "delete-list");

    await click(card, "cancel");

    expect(callService).not.toHaveBeenCalled();
    expect(root(card).querySelector('[data-testid="confirm"]')).toBeNull();
    expect(select(card)).not.toBeNull();
  });

  it("shows the error and keeps asking when deleting fails", async () => {
    const callService = vi
      .fn()
      .mockRejectedValue(new Error("ICA said no")) as unknown as CallService;
    const card = await mount(makeHass({ lists: [BREAD] }, callService).hass);
    await click(card, "delete-list");

    await click(card, "confirm-delete");

    expect(root(card).querySelector('[data-testid="error"]')?.textContent).toContain(
      "Något gick fel: ICA said no",
    );
    expect(root(card).querySelector('[data-testid="confirm"]')).not.toBeNull();
    expect(button(card, "confirm-delete")?.disabled).toBe(false);
  });

  it("locks the controls while the call runs", async () => {
    const pending = deferred<unknown>();
    const callService = vi.fn(() => pending.promise) as unknown as CallService;
    const card = await mount(makeHass({ lists: [BREAD] }, callService).hass);
    await click(card, "delete-list");

    button(card, "confirm-delete")?.click();
    await card.updateComplete;
    expect(button(card, "confirm-delete")?.disabled).toBe(true);
    button(card, "confirm-delete")?.click();
    await card.updateComplete;
    expect(callService).toHaveBeenCalledTimes(1);

    pending.resolve({});
    await settle(card);
  });

  it("closes the confirmation if the list disappears, and never reopens it by itself", async () => {
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }).hass);
    await click(card, "delete-list");
    expect(root(card).querySelector('[data-testid="confirm"]')).not.toBeNull();

    card.hass = makeHass({ lists: [BREAD], active: "A-1" }).hass;
    await card.updateComplete;
    expect(root(card).querySelector('[data-testid="confirm"]')).toBeNull();

    card.hass = makeHass({ lists: [BREAD, MILK], active: "B-2" }).hass;
    await card.updateComplete;
    expect(root(card).querySelector('[data-testid="confirm"]')).toBeNull();
    expect(select(card)).not.toBeNull();
  });

  it("keeps the confirmation about the same list even if the selection changes elsewhere", async () => {
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }).hass);
    await click(card, "delete-list");

    card.hass = makeHass({ lists: [BREAD, MILK], active: "A-1" }).hass;
    await card.updateComplete;

    expect(root(card).querySelector('[data-testid="confirm"]')?.textContent).toContain("Mjölk");
  });
});

describe("progress and errors from the integration", () => {
  it.each([
    ["creating", "Skapar listan"],
    ["deleting", "Tar bort listan"],
  ])("shows progress and locks everything while %s", async (status, message) => {
    const card = await mount(makeHass({ lists: [BREAD], status }).hass);

    expect(root(card).querySelector('[data-testid="progress"]')?.textContent).toContain(message);
    expect(select(card)?.disabled).toBe(true);
    expect(button(card, "new-list")?.disabled).toBe(true);
    expect(button(card, "delete-list")?.disabled).toBe(true);
  });

  it("unlocks again when the status returns to idle", async () => {
    const card = await mount(makeHass({ lists: [BREAD], status: "creating" }).hass);
    card.hass = makeHass({ lists: [BREAD], status: "idle" }).hass;
    await card.updateComplete;

    expect(root(card).querySelector('[data-testid="progress"]')).toBeNull();
    expect(select(card)?.disabled).toBe(false);
    expect(button(card, "new-list")?.disabled).toBe(false);
  });

  it("shows the progress in English too", async () => {
    const card = await mount(makeHass({ lists: [BREAD], status: "creating", language: "en" }).hass);
    expect(text(card)).toContain("Creating the list");
  });

  it("shows why the last action failed", async () => {
    const card = await mount(makeHass({ lists: [BREAD], status: "error", detail: "boom" }).hass);
    expect(root(card).querySelector('[data-testid="error"]')?.textContent).toBe(
      "Senaste åtgärden misslyckades: boom",
    );
    expect(button(card, "new-list")?.disabled).toBe(false);
  });

  it("still shows an error without detail", async () => {
    const card = await mount(makeHass({ lists: [BREAD], status: "error" }).hass);
    expect(root(card).querySelector('[data-testid="error"]')?.textContent).toContain("?");
  });
});

describe("items view inside the card", () => {
  const itemsView = (card: HandlaCard) =>
    root(card).querySelector("handla-items") as HandlaItems | null;

  it("shows the items of the selected list under the picker", async () => {
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }).hass);

    expect(itemsView(card)?.list?.offlineId).toBe("B-2");
    expect(itemsView(card)?.locked).toBe(false);
  });

  it("follows the user's choice of list", async () => {
    const card = await mount(makeHass({ lists: [BREAD, MILK], active: "B-2" }).hass);

    const picker = select(card) as HTMLSelectElement;
    picker.value = "A-1";
    picker.dispatchEvent(new Event("change"));
    await card.updateComplete;

    expect(itemsView(card)?.list?.offlineId).toBe("A-1");
  });

  it("is not shown when there are no lists or Handla is not running", async () => {
    expect(itemsView(await mount(makeHass({ lists: [] }).hass))).toBeNull();
    expect(itemsView(await mount(makeHass().hass))).toBeNull();
  });

  it("is locked while a list is being created or deleted", async () => {
    const card = await mount(makeHass({ lists: [BREAD], status: "creating" }).hass);
    expect(itemsView(card)?.locked).toBe(true);

    card.hass = makeHass({ lists: [BREAD], status: "idle" }).hass;
    await card.updateComplete;
    expect(itemsView(card)?.locked).toBe(false);
  });

  it("is replaced by the create form and the delete confirmation", async () => {
    const card = await mount(makeHass({ lists: [BREAD] }).hass);

    await click(card, "new-list");
    expect(itemsView(card)).toBeNull();
    await click(card, "cancel");
    expect(itemsView(card)).not.toBeNull();

    await click(card, "delete-list");
    expect(itemsView(card)).toBeNull();
    await click(card, "cancel");
    expect(itemsView(card)).not.toBeNull();
  });
});
