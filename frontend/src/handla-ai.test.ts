import { afterEach, describe, expect, it, vi } from "vitest";
import { AI_ENTITY } from "./ai";
import type { HandlaAi } from "./handla-ai";
import "./handla-ai"; // registers <handla-ai>
import type { ListInfo } from "./lists";
import type { HomeAssistant } from "./types";

type CallService = HomeAssistant["callService"];
type Suggested = { item: string; on_list?: boolean; existing?: string | null; selected?: boolean };

const LIST: ListInfo = { entityId: "todo.ica_a", offlineId: "A-1", title: "Veckan", itemCount: 2 };

interface Options {
  aiState?: string | null;
  suggestions?: Suggested[];
  /** Items whose add_item call fails with this message. */
  failing?: Record<string, string>;
  extractError?: string;
  language?: string;
  listState?: string;
  callService?: CallService;
}

function makeEnv(options: Options = {}) {
  const callService: CallService =
    options.callService ??
    vi.fn(async (_domain: string, service: string, data?: Record<string, unknown>) => {
      if (service === "ai_extract_items") {
        if (options.extractError) throw new Error(options.extractError);
        return { context: {}, response: { items: options.suggestions ?? [] } };
      }
      if (service === "add_item") {
        const item = String(data?.["item"]);
        const failure = options.failing?.[item];
        if (failure) throw new Error(failure);
        return { context: {}, response: { added: true, duplicate: false, item, duplicates: [] } };
      }
      return { context: {}, response: {} };
    });
  const build = (overrides: Partial<Options> = {}): HomeAssistant => {
    const aiState = overrides.aiState === undefined ? options.aiState : overrides.aiState;
    const states: HomeAssistant["states"] = {
      [LIST.entityId]: { state: overrides.listState ?? options.listState ?? "2", attributes: {} },
    };
    if (aiState !== null) {
      states[AI_ENTITY] = { state: aiState ?? "ready", attributes: {} };
    }
    return { language: options.language ?? "sv", states, callService };
  };
  return { build, callService };
}

async function settle(el: HandlaAi): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await el.updateComplete;
}

async function mount(hass: HomeAssistant, locked = false): Promise<HandlaAi> {
  const el = document.createElement("handla-ai") as HandlaAi;
  el.hass = hass;
  el.list = LIST;
  el.locked = locked;
  document.body.appendChild(el);
  await settle(el);
  return el;
}

const root = (el: HandlaAi) => el.shadowRoot as ShadowRoot;
/** What the user could see: the shadow root minus the element's own <style>. */
const rendered = (el: HandlaAi) =>
  [...root(el).children].filter((child) => child.tagName !== "STYLE");
const button = (el: HandlaAi, action: string) =>
  root(el).querySelector<HTMLButtonElement>(`[data-action="${action}"]`);
const testid = (el: HandlaAi, id: string) => root(el).querySelector(`[data-testid="${id}"]`);
const rows = (el: HandlaAi) => [...root(el).querySelectorAll<HTMLElement>("li.suggestion")];
const textOf = (row: HTMLElement) =>
  row.querySelector<HTMLInputElement>("input[type=text]")?.value ?? "";
const checked = (row: HTMLElement) =>
  row.querySelector<HTMLInputElement>("input[type=checkbox]")?.checked ?? false;

async function click(el: HandlaAi, action: string): Promise<void> {
  button(el, action)?.click();
  await settle(el);
}

async function openAndRead(el: HandlaAi, text = "Pannkakor"): Promise<void> {
  await click(el, "ai-open");
  const area = root(el).querySelector("textarea") as HTMLTextAreaElement;
  area.value = text;
  area.dispatchEvent(new Event("input"));
  await el.updateComplete;
  await click(el, "ai-find");
}

async function edit(el: HandlaAi, row: HTMLElement, value: string): Promise<void> {
  const field = row.querySelector<HTMLInputElement>("input[type=text]") as HTMLInputElement;
  field.value = value;
  field.dispatchEvent(new Event("input"));
  await el.updateComplete;
}

async function toggle(el: HandlaAi, row: HTMLElement): Promise<void> {
  const box = row.querySelector<HTMLInputElement>("input[type=checkbox]") as HTMLInputElement;
  box.checked = !box.checked;
  box.dispatchEvent(new Event("change"));
  await el.updateComplete;
}

const callsTo = (callService: CallService, service: string) =>
  (callService as ReturnType<typeof vi.fn>).mock.calls.filter((call) => call[1] === service);

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

const SUGGESTIONS: Suggested[] = [
  { item: "2 st gurka", on_list: false, existing: null, selected: true },
  { item: "1 l mjölk", on_list: true, existing: "mjölk", selected: false },
  { item: "ost", on_list: false, existing: null, selected: true },
];

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

describe("visibility", () => {
  it.each(["off", "unavailable", "unknown"])("renders nothing when AI is %s", async (aiState) => {
    const el = await mount(makeEnv({ aiState }).build());
    expect(rendered(el)).toHaveLength(0);
  });

  it("renders nothing without the AI sensor", async () => {
    const el = await mount(makeEnv({ aiState: null }).build());
    expect(rendered(el)).toHaveLength(0);
  });

  it("shows only the open button when AI is ready", async () => {
    const el = await mount(makeEnv().build());
    expect(button(el, "ai-open")?.textContent?.trim()).toBe("Lägg till från text (AI)");
    expect(root(el).querySelector("textarea")).toBeNull();
  });

  it("hides again when AI is turned off while it is open", async () => {
    const env = makeEnv();
    const el = await mount(env.build());
    await click(el, "ai-open");

    el.hass = env.build({ aiState: "off" });
    await settle(el);

    expect(rendered(el)).toHaveLength(0);
  });

  it("renders nothing without a list", async () => {
    const el = await mount(makeEnv().build());
    el.list = null;
    await settle(el);
    expect(rendered(el)).toHaveLength(0);
  });

  it("disables the button while the list is locked or unavailable", async () => {
    const locked = await mount(makeEnv().build(), true);
    expect(button(locked, "ai-open")?.disabled).toBe(true);
    const unavailable = await mount(makeEnv({ listState: "unavailable" }).build());
    expect(button(unavailable, "ai-open")?.disabled).toBe(true);
  });

  it("speaks English for an English user", async () => {
    const el = await mount(makeEnv({ language: "en" }).build());
    expect(button(el, "ai-open")?.textContent?.trim()).toBe("Add from text (AI)");
  });
});

describe("paste and read", () => {
  it("needs some text before it can read", async () => {
    const el = await mount(makeEnv().build());
    await click(el, "ai-open");
    expect(button(el, "ai-find")?.disabled).toBe(true);
  });

  it("sends the text for the current list and shows the suggestions", async () => {
    const env = makeEnv({ suggestions: SUGGESTIONS });
    const el = await mount(env.build());
    await openAndRead(el, "  Gurksallad  ");

    expect(callsTo(env.callService, "ai_extract_items")[0]).toEqual([
      "handla",
      "ai_extract_items",
      { entity_id: "todo.ica_a", text: "Gurksallad" },
      undefined,
      false,
      true,
    ]);
    expect(rows(el).map(textOf)).toEqual(["2 st gurka", "1 l mjölk", "ost"]);
  });

  it("marks items already on the list and leaves them unticked", async () => {
    const el = await mount(makeEnv({ suggestions: SUGGESTIONS }).build());
    await openAndRead(el);

    expect(rows(el).map(checked)).toEqual([true, false, true]);
    expect(rows(el)[1]?.querySelector("[data-note=on-list]")?.textContent).toContain(
      "finns redan: mjölk",
    );
    expect(rows(el)[0]?.querySelector("[data-note=on-list]")).toBeNull();
    expect(button(el, "ai-add")?.textContent?.trim()).toBe("Lägg till valda (2)");
  });

  it("locks the form while reading, and ignores a second tap", async () => {
    const gate = deferred<unknown>();
    const callService = vi.fn(() => gate.promise) as unknown as CallService;
    const el = await mount(makeEnv({ callService }).build());
    await openAndRead(el);

    expect(testid(el, "ai-reading")?.textContent).toContain("Läser texten");
    expect(button(el, "ai-find")?.disabled).toBe(true);
    expect(root(el).querySelector("textarea")?.disabled).toBe(true);
    button(el, "ai-find")?.click();
    expect(callService).toHaveBeenCalledTimes(1);

    gate.resolve({ context: {}, response: { items: SUGGESTIONS } });
    await settle(el);
    expect(rows(el)).toHaveLength(3);
  });

  it("says so when nothing was found and keeps the text", async () => {
    const el = await mount(makeEnv({ suggestions: [] }).build());
    await openAndRead(el, "Hej!");

    expect(testid(el, "ai-none")?.textContent).toContain("Hittade inga varor");
    expect(root(el).querySelector("textarea")?.value).toBe("Hej!");
    expect(testid(el, "ai-review")).toBeNull();
  });

  it("shows a failure from the AI provider and keeps the text for another try", async () => {
    const el = await mount(makeEnv({ extractError: "credit balance too low" }).build());
    await openAndRead(el, "Pannkakor");

    expect(testid(el, "ai-error")?.textContent).toContain("credit balance too low");
    expect(root(el).querySelector("textarea")?.value).toBe("Pannkakor");
    expect(button(el, "ai-find")?.disabled).toBe(false);
  });

  it("can be closed, and the text is kept for next time", async () => {
    const el = await mount(makeEnv().build());
    await openAndRead(el, "Pannkakor");
    await click(el, "ai-close");
    expect(root(el).querySelector("textarea")).toBeNull();

    await click(el, "ai-open");
    expect(root(el).querySelector("textarea")?.value).toBe("Pannkakor");
  });
});

describe("review and add", () => {
  it("adds the chosen items, with edits, and closes", async () => {
    const env = makeEnv({ suggestions: SUGGESTIONS });
    const el = await mount(env.build());
    await openAndRead(el);
    await edit(el, rows(el)[0] as HTMLElement, "3 st gurka");
    await toggle(el, rows(el)[2] as HTMLElement); // untick ost
    await toggle(el, rows(el)[1] as HTMLElement); // tick mjölk, already on the list
    expect(button(el, "ai-add")?.textContent?.trim()).toBe("Lägg till valda (2)");

    await click(el, "ai-add");

    const adds = callsTo(env.callService, "add_item").map((call) => call[2]);
    expect(adds).toEqual([
      { entity_id: "todo.ica_a", item: "3 st gurka", confirm_duplicate: true },
      { entity_id: "todo.ica_a", item: "1 l mjölk", confirm_duplicate: true },
    ]);
    expect(testid(el, "ai-review")).toBeNull();
    expect(testid(el, "ai-done")?.textContent).toContain("Lade till 2 varor");
    expect(button(el, "ai-open")).not.toBeNull();
  });

  it("clears the text after a successful add", async () => {
    const el = await mount(makeEnv({ suggestions: SUGGESTIONS }).build());
    await openAndRead(el, "Pannkakor");
    await click(el, "ai-add");
    await click(el, "ai-open");
    expect(root(el).querySelector("textarea")?.value).toBe("");
  });

  it("adds nothing when nothing is chosen", async () => {
    const env = makeEnv({ suggestions: SUGGESTIONS });
    const el = await mount(env.build());
    await openAndRead(el);
    await toggle(el, rows(el)[0] as HTMLElement);
    await toggle(el, rows(el)[2] as HTMLElement);

    expect(button(el, "ai-add")?.disabled).toBe(true);
    button(el, "ai-add")?.click();
    expect(callsTo(env.callService, "add_item")).toHaveLength(0);
  });

  it("does not add an item whose text was emptied", async () => {
    const env = makeEnv({ suggestions: SUGGESTIONS });
    const el = await mount(env.build());
    await openAndRead(el);
    await edit(el, rows(el)[0] as HTMLElement, "   ");

    expect(button(el, "ai-add")?.textContent?.trim()).toBe("Lägg till valda (1)");
    await click(el, "ai-add");
    expect(callsTo(env.callService, "add_item").map((call) => call[2]?.["item"])).toEqual(["ost"]);
  });

  it("keeps failed items for a retry and removes the ones that were added", async () => {
    const failing = { "2 st gurka": "ICA is reloading" };
    const env = makeEnv({ suggestions: SUGGESTIONS, failing });
    const el = await mount(env.build());
    await openAndRead(el);

    await click(el, "ai-add");

    expect(rows(el).map(textOf)).toEqual(["2 st gurka", "1 l mjölk"]);
    expect(rows(el)[0]?.querySelector("[data-note=failed]")?.textContent).toContain(
      "ICA is reloading",
    );
    expect(testid(el, "ai-retry")?.textContent).toContain("1 varor kunde inte läggas till");
    expect(checked(rows(el)[0] as HTMLElement)).toBe(true);
    expect(checked(rows(el)[1] as HTMLElement)).toBe(false); // still not wanted
    expect(button(el, "ai-add")?.textContent?.trim()).toBe("Lägg till valda (1)");
    expect(testid(el, "ai-done")).toBeNull();
  });

  it("retries only the failed items, and finishes when they go through", async () => {
    const failing: Record<string, string> = { "2 st gurka": "ICA is reloading" };
    const env = makeEnv({ suggestions: SUGGESTIONS, failing });
    const el = await mount(env.build());
    await openAndRead(el);
    await click(el, "ai-add");

    delete failing["2 st gurka"];
    await click(el, "ai-add");

    const added = callsTo(env.callService, "add_item").map((call) => call[2]?.["item"]);
    expect(added).toEqual(["2 st gurka", "ost", "2 st gurka"]);
    expect(testid(el, "ai-review")).toBeNull();
    expect(testid(el, "ai-done")?.textContent).toContain("Lade till 1 varor");
  });

  it("treats a refused add as a failure", async () => {
    const callService = vi.fn(async (_d: string, service: string) =>
      service === "ai_extract_items"
        ? { context: {}, response: { items: [{ item: "ost", selected: true }] } }
        : { context: {}, response: { added: false, duplicate: false } },
    ) as unknown as CallService;
    const el = await mount(makeEnv({ callService }).build());
    await openAndRead(el);

    await click(el, "ai-add");

    expect(rows(el)).toHaveLength(1);
    expect(rows(el)[0]?.querySelector("[data-note=failed]")).not.toBeNull();
  });

  it("locks the review while adding, so nothing is added twice", async () => {
    const gate = deferred<unknown>();
    const callService = vi.fn(async (_d: string, service: string) => {
      if (service === "ai_extract_items") {
        return { context: {}, response: { items: [{ item: "ost", selected: true }] } };
      }
      return gate.promise;
    }) as unknown as CallService;
    const el = await mount(makeEnv({ callService }).build());
    await openAndRead(el);

    await click(el, "ai-add");
    expect(button(el, "ai-add")?.disabled).toBe(true);
    expect(button(el, "ai-add")?.textContent?.trim()).toBe("Lägger till…");
    expect(button(el, "ai-back")?.disabled).toBe(true);
    expect(button(el, "ai-close")?.disabled).toBe(true);
    button(el, "ai-add")?.click();
    button(el, "ai-close")?.click();
    expect(callsTo(callService, "add_item")).toHaveLength(1);

    gate.resolve({ context: {}, response: { added: true, duplicate: false, item: "ost" } });
    await settle(el);
    expect(testid(el, "ai-done")).not.toBeNull();
  });

  it("does not add while the list is locked", async () => {
    const env = makeEnv({ suggestions: SUGGESTIONS });
    const el = await mount(env.build());
    await openAndRead(el);
    el.locked = true;
    await settle(el);

    expect(button(el, "ai-add")?.disabled).toBe(true);
    (el as unknown as { _addChosen(): Promise<void> })._addChosen();
    expect(callsTo(env.callService, "add_item")).toHaveLength(0);
  });

  it("can be closed from the review", async () => {
    const el = await mount(makeEnv({ suggestions: SUGGESTIONS }).build());
    await openAndRead(el);

    await click(el, "ai-close");

    expect(testid(el, "ai-review")).toBeNull();
    expect(button(el, "ai-open")).not.toBeNull();
  });

  it("goes back to the text and keeps it", async () => {
    const el = await mount(makeEnv({ suggestions: SUGGESTIONS }).build());
    await openAndRead(el, "Pannkakor");

    await click(el, "ai-back");

    expect(testid(el, "ai-review")).toBeNull();
    expect(root(el).querySelector("textarea")?.value).toBe("Pannkakor");
  });
});
