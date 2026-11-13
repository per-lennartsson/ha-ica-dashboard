import { afterEach, describe, expect, it, vi } from "vitest";
import { AI_ENTITY } from "./ai";
import type { CategoryData } from "./categories";
import type { HandlaCategorize } from "./handla-categorize";
import "./handla-categorize"; // registers <handla-categorize>
import type { ListInfo } from "./lists";
import type { HomeAssistant } from "./types";

type CallService = HomeAssistant["callService"];

const LIST: ListInfo = { entityId: "todo.ica_a", offlineId: "A-1", title: "Veckan", itemCount: 3 };
const DATA: CategoryData = {
  groups: [
    { id: 4, name: "Frukt & Grönt" },
    { id: 10, name: "Mejeri" },
    { id: 12, name: "Ospecificerad" },
  ],
  groupOf: {},
};
const SUGGESTIONS = [
  { uid: "a", name: "havremjölk", current: 12, suggested: 10 },
  { uid: "b", name: "gurka", current: 12, suggested: 4 },
];

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const answer = (response: Record<string, unknown>) => ({ context: {}, response });

function makeHass(callService: CallService, aiState: string | null = "ready"): HomeAssistant {
  const states: HomeAssistant["states"] = {};
  if (aiState !== null) states[AI_ENTITY] = { state: aiState, attributes: {} };
  return { language: "sv", states, callService };
}

/** A service double: suggestions for ai_suggest_categories, everything saved for set_category. */
function service(overrides: Partial<Record<string, () => Promise<unknown>>> = {}): CallService {
  return vi.fn(async (_domain: string, name: string, data?: Record<string, unknown>) => {
    const custom = overrides[name];
    if (custom) return custom();
    if (name === "ai_suggest_categories") {
      return answer({ items: SUGGESTIONS, truncated: false, asked: 2 });
    }
    const items = (data?.["items"] ?? []) as Array<{ uid: string }>;
    return answer({ updated: items.map((entry) => entry.uid), not_found: [] });
  });
}

async function mount(
  hass: HomeAssistant,
  options: { list?: ListInfo | null; data?: CategoryData | null; locked?: boolean } = {},
): Promise<HandlaCategorize> {
  const el = document.createElement("handla-categorize") as HandlaCategorize;
  el.hass = hass;
  el.list = options.list === undefined ? LIST : options.list;
  el.data = options.data === undefined ? DATA : options.data;
  el.locked = options.locked ?? false;
  document.body.appendChild(el);
  await settle(el);
  return el;
}

async function settle(el: HandlaCategorize): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await el.updateComplete;
}

const root = (el: HandlaCategorize) => el.shadowRoot as ShadowRoot;
const button = (el: HandlaCategorize, action: string) =>
  root(el).querySelector<HTMLButtonElement>(`button[data-action="${action}"]`);
const testid = (el: HandlaCategorize, id: string) =>
  root(el).querySelector(`[data-testid="${id}"]`);
const rows = (el: HandlaCategorize) => [...root(el).querySelectorAll<HTMLElement>("li.suggestion")];
const calls = (callService: CallService, name: string) =>
  (callService as ReturnType<typeof vi.fn>).mock.calls.filter((call) => call[1] === name);

async function click(el: HandlaCategorize, action: string): Promise<void> {
  button(el, action)?.click();
  await settle(el);
}

async function suggest(el: HandlaCategorize): Promise<void> {
  await click(el, "suggest");
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("visibility", () => {
  it.each(["off", "unavailable", "unknown"])("shows nothing when AI is %s", async (state) => {
    const el = await mount(makeHass(service(), state));
    expect(root(el).querySelector(":not(style)")).toBeNull();
    expect(button(el, "suggest")).toBeNull();
  });

  it("shows nothing without the AI sensor, or without a list", async () => {
    expect(button(await mount(makeHass(service(), null)), "suggest")).toBeNull();
    expect(button(await mount(makeHass(service()), { list: null }), "suggest")).toBeNull();
  });

  it("shows the button when AI is ready", async () => {
    const el = await mount(makeHass(service()));
    expect(button(el, "suggest")?.textContent?.trim()).toBe("Föreslå kategorier (AI)");
  });

  it("disables the button while a list is created or deleted", async () => {
    const el = await mount(makeHass(service()), { locked: true });
    expect(button(el, "suggest")?.disabled).toBe(true);
  });
});

describe("asking for suggestions", () => {
  it("asks about items without a group by default and shows a review", async () => {
    const callService = service();
    const el = await mount(makeHass(callService));

    await suggest(el);

    expect(calls(callService, "ai_suggest_categories")[0]?.[2]).toEqual({
      entity_id: "todo.ica_a",
      scope: "unspecified",
    });
    expect(rows(el).map((row) => row.querySelector(".name")?.textContent?.trim())).toEqual([
      "havremjölk",
      "gurka",
    ]);
    const selects = rows(el).map((row) => row.querySelector<HTMLSelectElement>("select")?.value);
    expect(selects).toEqual(["10", "4"]);
    expect(rows(el)[0]?.querySelector(".note")?.textContent?.trim()).toBe("nu: Ospecificerad");
  });

  it("asks about every item when the box is ticked", async () => {
    const callService = service();
    const el = await mount(makeHass(callService));
    const box = root(el).querySelector<HTMLInputElement>("[data-action=include-all]");
    box?.click();
    await el.updateComplete;

    await suggest(el);

    expect(calls(callService, "ai_suggest_categories")[0]?.[2]).toMatchObject({ scope: "all" });
  });

  it("locks the form while reading and ignores a second tap", async () => {
    const pending = deferred<unknown>();
    const callService = service({ ai_suggest_categories: () => pending.promise });
    const el = await mount(makeHass(callService));

    button(el, "suggest")?.click();
    await settle(el);
    expect(testid(el, "reading")).not.toBeNull();
    expect(button(el, "suggest")).toBeNull();
    expect(calls(callService, "ai_suggest_categories")).toHaveLength(1);

    pending.resolve(answer({ items: SUGGESTIONS }));
    await settle(el);
    expect(rows(el)).toHaveLength(2);
  });

  it("says so when nothing needs to change", async () => {
    const el = await mount(
      makeHass(service({ ai_suggest_categories: async () => answer({ items: [] }) })),
    );
    await suggest(el);
    expect(testid(el, "review")).toBeNull();
    expect(testid(el, "note")?.textContent).toContain("Inga ändringar");
    expect(button(el, "suggest")).not.toBeNull();
  });

  it("warns when the list was longer than the AI reads", async () => {
    const el = await mount(
      makeHass(
        service({
          ai_suggest_categories: async () =>
            answer({ items: SUGGESTIONS, truncated: true, asked: 60 }),
        }),
      ),
    );
    await suggest(el);
    expect(testid(el, "note")?.textContent).toContain("60");
  });

  it("shows the error and lets the user try again", async () => {
    const callService = service({
      ai_suggest_categories: async () => {
        throw new Error("The AI provider failed: credits");
      },
    });
    const el = await mount(makeHass(callService));

    await suggest(el);

    expect(testid(el, "error")?.textContent).toContain("credits");
    expect(button(el, "suggest")).not.toBeNull();
  });

  it("ignores an answer that arrives after the review was closed", async () => {
    const pending = deferred<unknown>();
    const el = await mount(makeHass(service({ ai_suggest_categories: () => pending.promise })));
    button(el, "suggest")?.click();
    await settle(el);
    // Closing is possible only from the review; simulate a restart by asking again
    (el as unknown as { _close(): void })._close();
    await settle(el);

    pending.resolve(answer({ items: SUGGESTIONS }));
    await settle(el);

    expect(testid(el, "review")).toBeNull();
  });

  it("does nothing without a list or while locked", async () => {
    const callService = service();
    const el = await mount(makeHass(callService), { locked: true });
    await (el as unknown as { _suggest(): Promise<void> })._suggest();
    expect(calls(callService, "ai_suggest_categories")).toHaveLength(0);
  });
});

describe("reviewing and saving", () => {
  async function review(callService: CallService = service()) {
    const el = await mount(makeHass(callService));
    await suggest(el);
    return { el, callService };
  }

  it("saves all suggestions through set_category and closes", async () => {
    const { el, callService } = await review();
    const changed = vi.fn();
    el.addEventListener("categories-changed", changed);

    await click(el, "save");

    expect(calls(callService, "set_category")[0]?.[2]).toEqual({
      entity_id: "todo.ica_a",
      items: [
        { uid: "a", group_id: 10 },
        { uid: "b", group_id: 4 },
      ],
    });
    expect(changed).toHaveBeenCalledTimes(1);
    expect(testid(el, "review")).toBeNull();
    expect(testid(el, "note")?.textContent).toContain("Sparade 2");
  });

  it("saves the group the user picked instead", async () => {
    const { el, callService } = await review();
    const select = rows(el)[0]?.querySelector<HTMLSelectElement>("select") as HTMLSelectElement;
    select.value = "4";
    select.dispatchEvent(new Event("change"));
    await el.updateComplete;

    await click(el, "save");

    expect(calls(callService, "set_category")[0]?.[2]).toMatchObject({
      items: [
        { uid: "a", group_id: 4 },
        { uid: "b", group_id: 4 },
      ],
    });
  });

  it("saves only the ticked rows", async () => {
    const { el, callService } = await review();
    const box = rows(el)[1]?.querySelector<HTMLInputElement>("input[type=checkbox]");
    (box as HTMLInputElement).checked = false;
    box?.dispatchEvent(new Event("change"));
    await el.updateComplete;
    expect(button(el, "save")?.textContent).toContain("(1)");

    await click(el, "save");

    expect(calls(callService, "set_category")[0]?.[2]).toMatchObject({
      items: [{ uid: "a", group_id: 10 }],
    });
  });

  it("cannot save with nothing ticked", async () => {
    const { el, callService } = await review();
    for (const row of rows(el)) {
      const box = row.querySelector<HTMLInputElement>("input[type=checkbox]");
      (box as HTMLInputElement).checked = false;
      box?.dispatchEvent(new Event("change"));
    }
    await el.updateComplete;
    expect(button(el, "save")?.disabled).toBe(true);
    await (el as unknown as { _save(): Promise<void> })._save();
    expect(calls(callService, "set_category")).toHaveLength(0);
  });

  it("keeps rows that were not saved and removes the saved ones", async () => {
    const callService = service({
      set_category: async () => answer({ updated: ["a"], not_found: ["b"] }),
    });
    const { el } = await review(callService);
    const changed = vi.fn();
    el.addEventListener("categories-changed", changed);

    await click(el, "save");

    expect(rows(el).map((row) => row.dataset["uid"])).toEqual(["b"]);
    expect(rows(el)[0]?.querySelector(".note.error")?.textContent).toContain("finns inte längre");
    expect(testid(el, "note")?.textContent).toContain("1 varor kunde inte sparas");
    expect(changed).toHaveBeenCalledTimes(1);
  });

  it("keeps every row with the error when the call fails, and retries", async () => {
    let fail = true;
    const callService = service({
      set_category: async () => {
        if (fail) throw new Error("ICA is down");
        return answer({ updated: ["a", "b"] });
      },
    });
    const { el } = await review(callService);
    const changed = vi.fn();
    el.addEventListener("categories-changed", changed);

    await click(el, "save");
    expect(rows(el)).toHaveLength(2);
    expect(rows(el)[0]?.querySelector(".note.error")?.textContent).toContain("ICA is down");
    expect(changed).not.toHaveBeenCalled();

    fail = false;
    await click(el, "save");
    expect(testid(el, "review")).toBeNull();
    expect(changed).toHaveBeenCalledTimes(1);
  });

  it("locks the review while saving and ignores a second tap", async () => {
    const pending = deferred<unknown>();
    const callService = service({ set_category: () => pending.promise });
    const { el } = await review(callService);

    button(el, "save")?.click();
    await settle(el);
    expect(button(el, "save")?.disabled).toBe(true);
    expect(button(el, "close")?.disabled).toBe(true);
    button(el, "save")?.click();
    await settle(el);
    expect(calls(callService, "set_category")).toHaveLength(1);

    pending.resolve(answer({ updated: ["a", "b"] }));
    await settle(el);
    expect(testid(el, "review")).toBeNull();
  });

  it("closing the review forgets the suggestions without saving", async () => {
    const { el, callService } = await review();
    await click(el, "close");
    expect(testid(el, "review")).toBeNull();
    expect(button(el, "suggest")).not.toBeNull();
    expect(calls(callService, "set_category")).toHaveLength(0);
  });

  it("ignores a save answer that arrives after closing", async () => {
    const pending = deferred<unknown>();
    const { el } = await review(service({ set_category: () => pending.promise }));
    const changed = vi.fn();
    el.addEventListener("categories-changed", changed);
    button(el, "save")?.click();
    await settle(el);
    (el as unknown as { _close(): void })._close();

    pending.resolve(answer({ updated: ["a", "b"] }));
    await settle(el);

    expect(changed).not.toHaveBeenCalled();
  });

  it("shows the group id when the group list is missing", async () => {
    const callService = service();
    const el = await mount(makeHass(callService), { data: null });
    await suggest(el);
    expect(rows(el)[0]?.querySelector(".note")?.textContent?.trim()).toBe("nu: 12");
    expect(rows(el)[0]?.querySelectorAll("option")).toHaveLength(0);
  });
});
