import { afterEach, describe, expect, it, vi } from "vitest";
import type { InkopItems } from "./inkop-items";
import "./inkop-items"; // registers <inkop-items>
import { FREQUENT_ENTITY } from "./items";
import type { ListInfo } from "./lists";
import type { HomeAssistant } from "./types";

type CallService = HomeAssistant["callService"];
type Item = { uid: string; summary: string; status?: string };

const LIST_A: ListInfo = {
  entityId: "todo.ica_a",
  offlineId: "A-1",
  title: "Veckan",
  itemCount: 2,
};
const LIST_B: ListInfo = {
  entityId: "todo.ica_b",
  offlineId: "B-2",
  title: "Festen",
  itemCount: 0,
};

interface Options {
  language?: string;
  /** State of the todo entities; "gone" removes the entity. */
  entities?: Record<string, string>;
  quick?: Array<{ name: string; icon?: string; count?: number }>;
  subscribeFails?: boolean;
  noConnection?: boolean;
  callService?: CallService;
}

function defaultCallService(): CallService {
  return vi.fn(async (_domain: string, service: string, data?: Record<string, unknown>) => {
    if (service === "add_item") {
      return {
        context: {},
        response: { added: true, duplicate: false, item: data?.["item"], duplicates: [] },
      };
    }
    return { context: {}, response: {} };
  });
}

function makeEnv(options: Options = {}) {
  const subscribers: Array<{ entityId: string; callback: (message: unknown) => void }> = [];
  const unsubscribe = vi.fn();
  const subscribeMessage = vi.fn(
    async (callback: (m: unknown) => void, message: Record<string, unknown>) => {
      if (options.subscribeFails) throw new Error("subscription refused");
      subscribers.push({ entityId: String(message["entity_id"]), callback });
      return unsubscribe;
    },
  );
  const callService = options.callService ?? defaultCallService();
  const entities = options.entities ?? { [LIST_A.entityId]: "2", [LIST_B.entityId]: "0" };

  const build = (overrides: Partial<Options> = {}): HomeAssistant => {
    const merged = { ...entities, ...(overrides.entities ?? {}) };
    const states: HomeAssistant["states"] = {};
    for (const [id, state] of Object.entries(merged)) {
      if (state !== "gone") states[id] = { state, attributes: {} };
    }
    const quick = overrides.quick ?? options.quick;
    if (quick) {
      states[FREQUENT_ENTITY] = { state: String(quick.length), attributes: { items: quick } };
    }
    return {
      language: overrides.language ?? options.language ?? "sv",
      states,
      callService,
      ...(options.noConnection ? {} : { connection: { subscribeMessage } as never }),
    };
  };

  const push = (items: Item[], entityId = LIST_A.entityId) => {
    for (const sub of subscribers.filter((s) => s.entityId === entityId)) {
      sub.callback({ items: items.map((i) => ({ status: "needs_action", ...i })) });
    }
  };
  return { build, push, subscribeMessage, unsubscribe, callService, subscribers };
}

async function settle(el?: InkopItems): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await el?.updateComplete;
}

async function mount(
  hass: HomeAssistant,
  list: ListInfo | null = LIST_A,
  locked = false,
): Promise<InkopItems> {
  const el = document.createElement("inkop-items") as InkopItems;
  el.hass = hass;
  el.list = list;
  el.locked = locked;
  document.body.appendChild(el);
  await settle(el);
  return el;
}

const root = (el: InkopItems) => el.shadowRoot as ShadowRoot;
const input = (el: InkopItems) => root(el).querySelector<HTMLInputElement>("input[type=text]");
const row = (el: InkopItems, summary: string) =>
  [...root(el).querySelectorAll<HTMLElement>("li.item[data-uid]")].find(
    (li) => li.querySelector(".text")?.textContent?.trim() === summary,
  );
const rowTexts = (el: InkopItems) =>
  [...root(el).querySelectorAll("li.item")].map((li) => {
    const text = li.querySelector(".text")?.textContent?.replace(/\s+/g, " ").trim() ?? "";
    const prefix = li.classList.contains("pending")
      ? "…"
      : li.classList.contains("done")
        ? "x"
        : "-";
    return `${prefix} ${text}`;
  });
const button = (el: InkopItems, action: string) =>
  root(el).querySelector<HTMLButtonElement>(`[data-action="${action}"]`);
const testid = (el: InkopItems, id: string) => root(el).querySelector(`[data-testid="${id}"]`);

async function type(el: InkopItems, value: string): Promise<void> {
  const field = input(el) as HTMLInputElement;
  field.value = value;
  field.dispatchEvent(new Event("input"));
  await el.updateComplete;
}

async function submit(el: InkopItems): Promise<void> {
  root(el)
    .querySelector("form")
    ?.dispatchEvent(new Event("submit", { cancelable: true }));
  await settle(el);
}

async function add(el: InkopItems, text: string): Promise<void> {
  await type(el, text);
  await submit(el);
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

const addedResponse = (item: string) => ({
  context: {},
  response: { added: true, duplicate: false, item, duplicates: [] },
});
const duplicateResponse = (item: string) => ({
  context: {},
  response: { added: false, duplicate: true, item, duplicates: [{ uid: "x", summary: item }] },
});
const callsTo = (callService: CallService, service: string) =>
  (callService as ReturnType<typeof vi.fn>).mock.calls.filter((call) => call[1] === service);

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

describe("live items", () => {
  it("subscribes to the list's todo entity and shows a loading text until items arrive", async () => {
    const env = makeEnv();
    const el = await mount(env.build());

    expect(env.subscribeMessage).toHaveBeenCalledTimes(1);
    expect(env.subscribeMessage.mock.calls[0]?.[1]).toEqual({
      type: "todo/item/subscribe",
      entity_id: "todo.ica_a",
    });
    expect(testid(el, "loading")?.textContent).toContain("Hämtar varor");

    env.push([{ uid: "1", summary: "mjölk" }]);
    await el.updateComplete;
    expect(testid(el, "loading")).toBeNull();
    expect(rowTexts(el)).toEqual(["- mjölk"]);
  });

  it("shows open items first, ticked ones last and struck through", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    env.push([
      { uid: "1", summary: "bröd", status: "completed" },
      { uid: "2", summary: "mjölk" },
      { uid: "3", summary: "smör" },
    ]);
    await el.updateComplete;

    expect(rowTexts(el)).toEqual(["- mjölk", "- smör", "x bröd"]);
  });

  it("separates ticked items from the rest with a labelled divider showing how many", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    env.push([
      { uid: "1", summary: "bröd", status: "completed" },
      { uid: "2", summary: "mjölk" },
      { uid: "3", summary: "ost", status: "completed" },
    ]);
    await el.updateComplete;

    const children = [...root(el).querySelectorAll("ul > li")].map((li) =>
      li.classList.contains("divider")
        ? `| ${li.textContent?.replace(/\s+/g, " ").trim()}`
        : li.querySelector(".text")?.textContent?.trim(),
    );
    expect(children).toEqual(["mjölk", "| Avbockade (2)", "bröd", "ost"]);
    expect(testid(el, "ticked-divider")?.getAttribute("role")).toBe("separator");
  });

  it("shows no divider when nothing is ticked", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    env.push([{ uid: "1", summary: "mjölk" }]);
    await el.updateComplete;

    expect(testid(el, "ticked-divider")).toBeNull();
  });

  it("puts the divider first when everything is ticked, in English too", async () => {
    const env = makeEnv({ language: "en" });
    const el = await mount(env.build());
    env.push([{ uid: "1", summary: "bread", status: "completed" }]);
    await el.updateComplete;

    const first = root(el).querySelector("ul > li");
    expect(first?.classList.contains("divider")).toBe(true);
    expect(first?.textContent?.trim()).toBe("Ticked (1)");
  });

  it("keeps the divider between a pending item and the ticked ones", async () => {
    const gate = deferred<unknown>();
    const callService = vi.fn(() => gate.promise) as unknown as CallService;
    const env = makeEnv({ callService });
    const el = await mount(env.build());
    env.push([{ uid: "1", summary: "bröd", status: "completed" }]);
    await el.updateComplete;

    await add(el, "ägg");

    expect(rowTexts(el)).toEqual(["… ägg lägger till…", "x bröd"]);
    expect(testid(el, "ticked-divider")).not.toBeNull();
    gate.resolve(addedResponse("ägg"));
    await settle(el);
  });

  it("follows later changes", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    env.push([{ uid: "1", summary: "mjölk" }]);
    env.push([
      { uid: "1", summary: "mjölk" },
      { uid: "2", summary: "ägg" },
    ]);
    await el.updateComplete;

    expect(rowTexts(el)).toEqual(["- mjölk", "- ägg"]);
  });

  it("says so when the list is empty", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    env.push([]);
    await el.updateComplete;

    expect(testid(el, "empty")?.textContent).toContain("Listan är tom");
    expect(root(el).querySelector("ul")).toBeNull();
  });

  it("does not subscribe again when only Home Assistant's state object changes", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    el.hass = env.build();
    await settle(el);
    el.hass = env.build();
    await settle(el);

    expect(env.subscribeMessage).toHaveBeenCalledTimes(1);
  });

  it("switches subscription when another list is chosen, stopping the old one", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    env.push([{ uid: "1", summary: "mjölk" }]);
    await el.updateComplete;

    el.list = LIST_B;
    await settle(el);

    expect(env.unsubscribe).toHaveBeenCalledTimes(1);
    expect(env.subscribeMessage).toHaveBeenCalledTimes(2);
    expect(env.subscribeMessage.mock.calls[1]?.[1]).toMatchObject({ entity_id: "todo.ica_b" });
    expect(testid(el, "loading")).not.toBeNull();
    env.push([{ uid: "9", summary: "öl" }], LIST_B.entityId);
    await el.updateComplete;
    expect(rowTexts(el)).toEqual(["- öl"]);
  });

  it("ignores items that arrive late for a list that is no longer shown", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    el.list = LIST_B;
    await settle(el);

    env.push([{ uid: "1", summary: "gammal" }], LIST_A.entityId);
    await el.updateComplete;

    expect(rowTexts(el)).toEqual([]);
  });

  it("stops a subscription that resolves after the list was already switched", async () => {
    const late = deferred<() => void>();
    const stopLate = vi.fn();
    const subscribeMessage = vi
      .fn()
      .mockReturnValueOnce(late.promise)
      .mockResolvedValue(() => undefined);
    const hass: HomeAssistant = {
      language: "sv",
      states: {
        "todo.ica_a": { state: "1", attributes: {} },
        "todo.ica_b": { state: "1", attributes: {} },
      },
      callService: defaultCallService(),
      connection: { subscribeMessage } as never,
    };
    const el = await mount(hass);

    el.list = LIST_B;
    await settle(el);
    late.resolve(stopLate);
    await settle(el);

    expect(stopLate).toHaveBeenCalledTimes(1);
  });

  it("stops listening when removed from the page", async () => {
    const env = makeEnv();
    const el = await mount(env.build());

    el.remove();

    expect(env.unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("subscribes again when put back on the page", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    el.remove();
    document.body.appendChild(el);
    await settle(el);

    expect(env.subscribeMessage).toHaveBeenCalledTimes(2);
  });

  it("waits while the list is unavailable and resubscribes when it is back", async () => {
    const env = makeEnv({ entities: { [LIST_A.entityId]: "unavailable" } });
    const el = await mount(env.build());

    expect(env.subscribeMessage).not.toHaveBeenCalled();
    expect(testid(el, "unavailable")?.textContent).toContain("inte tillgänglig");
    expect(testid(el, "items")).toBeNull();

    el.hass = env.build({ entities: { [LIST_A.entityId]: "2" } });
    await settle(el);
    expect(env.subscribeMessage).toHaveBeenCalledTimes(1);
    expect(testid(el, "unavailable")).toBeNull();
  });

  it("resubscribes after the entity disappeared and came back (ha-ica-todo reload)", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    env.push([{ uid: "1", summary: "mjölk" }]);
    await el.updateComplete;

    el.hass = env.build({ entities: { [LIST_A.entityId]: "gone" } });
    await settle(el);
    expect(env.unsubscribe).toHaveBeenCalledTimes(1);
    expect(testid(el, "unavailable")).not.toBeNull();
    expect(rowTexts(el)).toEqual([]);

    el.hass = env.build();
    await settle(el);
    expect(env.subscribeMessage).toHaveBeenCalledTimes(2);
    env.push([
      { uid: "1", summary: "mjölk" },
      { uid: "2", summary: "ägg" },
    ]);
    await el.updateComplete;
    expect(rowTexts(el)).toEqual(["- mjölk", "- ägg"]);
  });

  it("shows an error when the subscription fails", async () => {
    const el = await mount(makeEnv({ subscribeFails: true }).build());

    expect(testid(el, "load-failed")?.textContent).toContain("subscription refused");
  });

  it("shows an error without a connection to Home Assistant", async () => {
    const el = await mount(makeEnv({ noConnection: true }).build());

    expect(testid(el, "load-failed")?.textContent).toContain("No connection");
  });

  it("renders nothing without a list", async () => {
    const el = await mount(makeEnv().build(), null);

    expect(root(el).querySelector("form")).toBeNull();
  });

  it("renders in English", async () => {
    const env = makeEnv({ language: "en" });
    const el = await mount(env.build());
    env.push([]);
    await el.updateComplete;

    expect(testid(el, "empty")?.textContent).toContain("The list is empty");
    expect(button(el, "add")?.textContent?.trim()).toBe("Add");
  });
});

describe("adding items", () => {
  it("adds on Enter, clears the field and keeps it focused for the next item", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    input(el)?.focus();

    await add(el, "  2 st gurka ");

    expect(env.callService).toHaveBeenCalledWith(
      "inkop",
      "add_item",
      { entity_id: "todo.ica_a", item: "2 st gurka", confirm_duplicate: false },
      undefined,
      false,
      true,
    );
    expect(input(el)?.value).toBe("");
    expect(root(el).activeElement).toBe(input(el));
  });

  it("ignores empty text", async () => {
    const env = makeEnv();
    const el = await mount(env.build());

    await add(el, "   ");

    expect(callsTo(env.callService, "add_item")).toHaveLength(0);
  });

  it("shows the item as 'adding…' until it has been added", async () => {
    const gate = deferred<unknown>();
    const callService = vi.fn(() => gate.promise) as unknown as CallService;
    const env = makeEnv({ callService });
    const el = await mount(env.build());
    env.push([{ uid: "1", summary: "mjölk" }]);
    await el.updateComplete;

    await add(el, "ägg");
    expect(rowTexts(el)).toEqual(["… ägg lägger till…", "- mjölk"]);

    gate.resolve(addedResponse("ägg"));
    await settle(el);
    expect(rowTexts(el)).toEqual(["- mjölk"]);
  });

  it("never disables the field while adding, so the keyboard stays open", async () => {
    const gate = deferred<unknown>();
    const callService = vi.fn(() => gate.promise) as unknown as CallService;
    const el = await mount(makeEnv({ callService }).build());
    input(el)?.focus();

    await add(el, "ägg");

    expect(input(el)?.disabled).toBe(false);
    expect(root(el).activeElement).toBe(input(el));
    gate.resolve(addedResponse("ägg"));
    await settle(el);
  });

  it("queues fast entries and adds them one at a time, in order", async () => {
    const first = deferred<unknown>();
    const callService = vi.fn(async (_d: string, _s: string, data?: Record<string, unknown>) => {
      if (data?.["item"] === "mjölk") return first.promise;
      return addedResponse(String(data?.["item"]));
    }) as unknown as CallService;
    const el = await mount(makeEnv({ callService }).build());

    await add(el, "mjölk");
    await add(el, "ägg");
    expect(callsTo(callService, "add_item")).toHaveLength(1);
    expect(rowTexts(el)).toEqual(["… mjölk lägger till…", "… ägg lägger till…"]);

    first.resolve(addedResponse("mjölk"));
    await settle(el);
    await settle(el);

    expect(
      callsTo(callService, "add_item").map((call) => (call[2] as { item: string }).item),
    ).toEqual(["mjölk", "ägg"]);
    expect(rowTexts(el)).toEqual([]);
  });

  it("sends a queued item to the list it was typed for, even if another list is chosen meanwhile", async () => {
    const first = deferred<unknown>();
    const callService = vi.fn(async (_d: string, _s: string, data?: Record<string, unknown>) => {
      if (data?.["item"] === "mjölk") return first.promise;
      return addedResponse(String(data?.["item"]));
    }) as unknown as CallService;
    const env = makeEnv({ callService });
    const el = await mount(env.build());
    await add(el, "mjölk");
    await add(el, "ägg");

    el.list = LIST_B;
    await settle(el);
    expect(rowTexts(el)).toEqual([]); // pending rows belong to the other list
    first.resolve(addedResponse("mjölk"));
    await settle(el);
    await settle(el);

    const entities = callsTo(callService, "add_item").map(
      (call) => (call[2] as { entity_id: string }).entity_id,
    );
    expect(entities).toEqual(["todo.ica_a", "todo.ica_a"]);
  });

  it("is blocked while a list is being created or deleted", async () => {
    const env = makeEnv();
    const el = await mount(env.build(), LIST_A, true);

    expect(input(el)?.disabled).toBe(true);
    expect(button(el, "add")?.disabled).toBe(true);
    await submit(el);
    expect(callsTo(env.callService, "add_item")).toHaveLength(0);
  });

  it("is blocked while the list is unavailable", async () => {
    const env = makeEnv({ entities: { [LIST_A.entityId]: "unavailable" } });
    const el = await mount(env.build());

    expect(input(el)?.disabled).toBe(true);
    await submit(el);
    expect(callsTo(env.callService, "add_item")).toHaveLength(0);
  });

  it("gives up quietly if Home Assistant goes away mid-queue", async () => {
    const first = deferred<unknown>();
    const callService = vi.fn(async (_d: string, _s: string, data?: Record<string, unknown>) => {
      if (data?.["item"] === "mjölk") return first.promise;
      return addedResponse(String(data?.["item"]));
    }) as unknown as CallService;
    const el = await mount(makeEnv({ callService }).build());
    await add(el, "mjölk");
    await add(el, "ägg");

    el.hass = undefined;
    first.resolve(addedResponse("mjölk"));
    await settle(el);
    await settle(el);

    expect(callsTo(callService, "add_item")).toHaveLength(1);
  });
});

describe("duplicates", () => {
  function duplicateEnv() {
    const callService = vi.fn(async (_d: string, _s: string, data?: Record<string, unknown>) => {
      const item = String(data?.["item"]);
      if (item === "mjölk" && data?.["confirm_duplicate"] !== true) return duplicateResponse(item);
      return addedResponse(item);
    }) as unknown as CallService;
    return { callService, env: makeEnv({ callService }) };
  }

  it("asks before adding an item that is already on the list", async () => {
    const { env, callService } = duplicateEnv();
    const el = await mount(env.build());

    await add(el, "mjölk");

    expect(testid(el, "duplicate")?.textContent).toContain(
      "“mjölk” finns redan – lägga till igen?",
    );
    expect(callsTo(callService, "add_item")).toHaveLength(1);
  });

  it("adds it again when confirmed", async () => {
    const { env, callService } = duplicateEnv();
    const el = await mount(env.build());
    await add(el, "mjölk");

    button(el, "duplicate-add")?.click();
    await settle(el);
    await settle(el);

    const calls = callsTo(callService, "add_item");
    expect(calls).toHaveLength(2);
    expect(calls[1]?.[2]).toMatchObject({ item: "mjölk", confirm_duplicate: true });
    expect(testid(el, "duplicate")).toBeNull();
    expect(rowTexts(el)).toEqual([]);
  });

  it("skips it when declined", async () => {
    const { env, callService } = duplicateEnv();
    const el = await mount(env.build());
    await add(el, "mjölk");

    button(el, "duplicate-skip")?.click();
    await settle(el);

    expect(callsTo(callService, "add_item")).toHaveLength(1);
    expect(testid(el, "duplicate")).toBeNull();
    expect(rowTexts(el)).toEqual([]);
  });

  it("holds the queue until you decide, then carries on", async () => {
    const { env, callService } = duplicateEnv();
    const el = await mount(env.build());

    await add(el, "mjölk");
    await add(el, "ägg");
    expect(callsTo(callService, "add_item")).toHaveLength(1); // "ägg" waits for the answer

    button(el, "duplicate-skip")?.click();
    await settle(el);
    await settle(el);

    expect(callsTo(callService, "add_item").map((c) => (c[2] as { item: string }).item)).toEqual([
      "mjölk",
      "ägg",
    ]);
  });

  it("carries on with the queue after a confirmed duplicate", async () => {
    const { env, callService } = duplicateEnv();
    const el = await mount(env.build());
    await add(el, "mjölk");
    await add(el, "ägg");

    button(el, "duplicate-add")?.click();
    await settle(el);
    await settle(el);
    await settle(el);

    expect(callsTo(callService, "add_item").map((c) => (c[2] as { item: string }).item)).toEqual([
      "mjölk",
      "mjölk",
      "ägg",
    ]);
  });

  it("shows the prompt in English", async () => {
    const callService = vi.fn(async () => duplicateResponse("milk")) as unknown as CallService;
    const el = await mount(makeEnv({ callService, language: "en" }).build());

    await add(el, "milk");

    expect(testid(el, "duplicate")?.textContent).toContain("is already on the list – add again?");
  });
});

describe("when adding fails", () => {
  function failingEnv() {
    let fail = true;
    const callService = vi.fn(async (_d: string, _s: string, data?: Record<string, unknown>) => {
      if (fail && data?.["item"] === "ananas") throw { message: "ICA said no." };
      return addedResponse(String(data?.["item"]));
    }) as unknown as CallService;
    return { env: makeEnv({ callService }), callService, recover: () => (fail = false) };
  }

  it("says what went wrong and lets you retry", async () => {
    const { env, callService, recover } = failingEnv();
    const el = await mount(env.build());

    await add(el, "ananas");
    expect(testid(el, "add-failed")?.textContent).toContain(
      "Kunde inte lägga till “ananas”: ICA said no.",
    );

    recover();
    button(el, "add-retry")?.click();
    await settle(el);
    await settle(el);

    expect(callsTo(callService, "add_item")).toHaveLength(2);
    expect(testid(el, "add-failed")).toBeNull();
    expect(rowTexts(el)).toEqual([]);
  });

  it("can give up on the item and carries on with the rest of the queue", async () => {
    const { env, callService } = failingEnv();
    const el = await mount(env.build());
    await add(el, "ananas");
    await add(el, "ägg");

    button(el, "add-skip")?.click();
    await settle(el);
    await settle(el);

    expect(callsTo(callService, "add_item").map((c) => (c[2] as { item: string }).item)).toEqual([
      "ananas",
      "ägg",
    ]);
    expect(testid(el, "add-failed")).toBeNull();
  });

  it("treats an answer that is neither added nor a duplicate as a failure", async () => {
    const callService = vi.fn(async () => ({
      context: {},
      response: { added: false },
    })) as unknown as CallService;
    const el = await mount(makeEnv({ callService }).build());

    await add(el, "ananas");

    expect(testid(el, "add-failed")?.textContent).toContain("Unknown error");
  });
});

describe("quick-add buttons", () => {
  const QUICK = [
    { name: "mjölk", icon: "mdi:cow", count: 5 },
    { name: "ägg", icon: "mdi:egg", count: 0 },
  ];

  it("shows a button with an icon for each frequent item", async () => {
    const el = await mount(makeEnv({ quick: QUICK }).build());

    const chips = [...root(el).querySelectorAll<HTMLElement>(".chip")];
    expect(chips.map((chip) => chip.dataset["quick"])).toEqual(["mjölk", "ägg"]);
    expect(chips[0]?.querySelector("ha-icon")?.getAttribute("icon")).toBe("mdi:cow");
    expect(chips[0]?.textContent?.trim()).toBe("mjölk");
  });

  it("shows nothing when there are none", async () => {
    const el = await mount(makeEnv().build());

    expect(root(el).querySelector(".chips")).toBeNull();
  });

  it("adds the item when tapped", async () => {
    const env = makeEnv({ quick: QUICK });
    const el = await mount(env.build());

    root(el).querySelector<HTMLButtonElement>('[data-quick="ägg"]')?.click();
    await settle(el);

    expect(env.callService).toHaveBeenCalledWith(
      "inkop",
      "add_item",
      { entity_id: "todo.ica_a", item: "ägg", confirm_duplicate: false },
      undefined,
      false,
      true,
    );
  });

  it("asks about duplicates like typed items do", async () => {
    const callService = vi.fn(async () => duplicateResponse("mjölk")) as unknown as CallService;
    const el = await mount(makeEnv({ quick: QUICK, callService }).build());

    root(el).querySelector<HTMLButtonElement>('[data-quick="mjölk"]')?.click();
    await settle(el);

    expect(testid(el, "duplicate")).not.toBeNull();
  });

  it("is disabled while the list is locked or unavailable", async () => {
    const locked = await mount(makeEnv({ quick: QUICK }).build(), LIST_A, true);
    expect(root(locked).querySelector<HTMLButtonElement>(".chip")?.disabled).toBe(true);

    const env = makeEnv({ quick: QUICK, entities: { [LIST_A.entityId]: "unavailable" } });
    const unavailable = await mount(env.build());
    root(unavailable).querySelector<HTMLButtonElement>(".chip")?.click();
    await settle(unavailable);
    expect(callsTo(env.callService, "add_item")).toHaveLength(0);
  });
});

describe("ticking, removing and clearing", () => {
  async function withItems(options: Options = {}) {
    const env = makeEnv(options);
    const el = await mount(env.build());
    env.push([
      { uid: "u1", summary: "mjölk" },
      { uid: "u2", summary: "bröd", status: "completed" },
      { uid: "u3", summary: "smör" },
    ]);
    await el.updateComplete;
    return { env, el };
  }

  it("ticks an open item by its id", async () => {
    const { env, el } = await withItems();

    row(el, "mjölk")?.querySelector<HTMLButtonElement>('[data-action="tick"]')?.click();
    await settle(el);

    expect(env.callService).toHaveBeenCalledWith(
      "inkop",
      "tick_item",
      { entity_id: "todo.ica_a", item: "u1", ticked: true },
      undefined,
      false,
      false,
    );
  });

  it("unticks a ticked item", async () => {
    const { env, el } = await withItems();

    row(el, "bröd")?.querySelector<HTMLButtonElement>('[data-action="tick"]')?.click();
    await settle(el);

    expect(callsTo(env.callService, "tick_item")[0]?.[2]).toMatchObject({
      item: "u2",
      ticked: false,
    });
  });

  it("labels the buttons for screen readers", async () => {
    const { el } = await withItems();

    const open = row(el, "mjölk")?.querySelector('[data-action="tick"]');
    const done = row(el, "bröd")?.querySelector('[data-action="tick"]');
    expect(open?.getAttribute("aria-label")).toBe("Bocka av mjölk");
    expect(open?.getAttribute("aria-pressed")).toBe("false");
    expect(done?.getAttribute("aria-label")).toBe("Ta bort bocken på bröd");
    expect(done?.getAttribute("aria-pressed")).toBe("true");
    expect(
      row(el, "smör")?.querySelector('[data-action="remove"]')?.getAttribute("aria-label"),
    ).toBe("Ta bort smör");
  });

  it("locks a row while its call runs, so a second tap does nothing", async () => {
    const gate = deferred<unknown>();
    const callService = vi.fn(() => gate.promise) as unknown as CallService;
    const { el } = await withItems({ callService });
    const tick = () => row(el, "mjölk")?.querySelector<HTMLButtonElement>('[data-action="tick"]');

    tick()?.click();
    await el.updateComplete;
    expect(tick()?.disabled).toBe(true);
    expect(
      row(el, "mjölk")?.querySelector<HTMLButtonElement>('[data-action="remove"]')?.disabled,
    ).toBe(true);
    expect(
      row(el, "smör")?.querySelector<HTMLButtonElement>('[data-action="tick"]')?.disabled,
    ).toBe(false);
    tick()?.click();
    await el.updateComplete;
    expect(callsTo(callService, "tick_item")).toHaveLength(1);

    gate.resolve({});
    await settle(el);
    expect(tick()?.disabled).toBe(false);
  });

  it("ignores a second tap in the same instant, before the button shows as locked", async () => {
    const gate = deferred<unknown>();
    const callService = vi.fn(() => gate.promise) as unknown as CallService;
    const { el } = await withItems({ callService });
    const tick = row(el, "mjölk")?.querySelector<HTMLButtonElement>('[data-action="tick"]');

    tick?.click();
    tick?.click(); // no re-render in between, so the button is not disabled yet
    await el.updateComplete;

    expect(callsTo(callService, "tick_item")).toHaveLength(1);
    gate.resolve({});
    await settle(el);
  });

  it("removes an item by its id", async () => {
    const { env, el } = await withItems();

    row(el, "smör")?.querySelector<HTMLButtonElement>('[data-action="remove"]')?.click();
    await settle(el);

    expect(env.callService).toHaveBeenCalledWith(
      "inkop",
      "remove_item",
      { entity_id: "todo.ica_a", item: "u3" },
      undefined,
      false,
      false,
    );
  });

  it("shows an error when a change fails, unlocks the row and lets you dismiss the error", async () => {
    const callService = vi
      .fn()
      .mockRejectedValue({ message: "ICA said no." }) as unknown as CallService;
    const { el } = await withItems({ callService });

    row(el, "mjölk")?.querySelector<HTMLButtonElement>('[data-action="tick"]')?.click();
    await settle(el);

    expect(testid(el, "action-failed")?.textContent).toContain(
      "Kunde inte uppdatera listan: ICA said no.",
    );
    expect(
      row(el, "mjölk")?.querySelector<HTMLButtonElement>('[data-action="tick"]')?.disabled,
    ).toBe(false);
    button(el, "dismiss")?.click();
    await el.updateComplete;
    expect(testid(el, "action-failed")).toBeNull();
  });

  it("offers to clear ticked items only when there are some", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    env.push([{ uid: "u1", summary: "mjölk" }]);
    await el.updateComplete;
    expect(button(el, "clear-ticked")).toBeNull();

    env.push([
      { uid: "u1", summary: "mjölk", status: "completed" },
      { uid: "u2", summary: "bröd", status: "completed" },
    ]);
    await el.updateComplete;
    expect(button(el, "clear-ticked")?.textContent?.trim()).toBe("Rensa avbockade (2)");
  });

  it("clears the ticked items", async () => {
    const { env, el } = await withItems();

    button(el, "clear-ticked")?.click();
    await settle(el);

    expect(env.callService).toHaveBeenCalledWith(
      "inkop",
      "clear_ticked",
      { entity_id: "todo.ica_a" },
      undefined,
      false,
      false,
    );
  });

  it("locks everything while clearing and ignores a second tap", async () => {
    const gate = deferred<unknown>();
    const callService = vi.fn(() => gate.promise) as unknown as CallService;
    const { el } = await withItems({ callService });

    button(el, "clear-ticked")?.click();
    await el.updateComplete;
    expect(button(el, "clear-ticked")?.disabled).toBe(true);
    expect(
      row(el, "mjölk")?.querySelector<HTMLButtonElement>('[data-action="tick"]')?.disabled,
    ).toBe(true);
    button(el, "clear-ticked")?.click();
    await el.updateComplete;
    expect(callsTo(callService, "clear_ticked")).toHaveLength(1);

    gate.resolve({});
    await settle(el);
    expect(button(el, "clear-ticked")?.disabled).toBe(false);
  });

  it("shows an error when clearing fails", async () => {
    const callService = vi.fn().mockRejectedValue(new Error("nope")) as unknown as CallService;
    const { el } = await withItems({ callService });

    button(el, "clear-ticked")?.click();
    await settle(el);

    expect(testid(el, "action-failed")?.textContent).toContain("nope");
    expect(button(el, "clear-ticked")?.disabled).toBe(false);
  });

  it("is locked while a list is being created or deleted", async () => {
    const env = makeEnv();
    const el = await mount(env.build(), LIST_A, true);
    env.push([
      { uid: "u1", summary: "mjölk" },
      { uid: "u2", summary: "bröd", status: "completed" },
    ]);
    await el.updateComplete;

    expect(
      row(el, "mjölk")?.querySelector<HTMLButtonElement>('[data-action="tick"]')?.disabled,
    ).toBe(true);
    expect(
      row(el, "mjölk")?.querySelector<HTMLButtonElement>('[data-action="remove"]')?.disabled,
    ).toBe(true);
    expect(button(el, "clear-ticked")?.disabled).toBe(true);
  });
});
