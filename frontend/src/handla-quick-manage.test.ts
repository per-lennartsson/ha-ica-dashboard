import { afterEach, describe, expect, it, vi } from "vitest";
import type { HandlaQuickManage } from "./handla-quick-manage";
import "./handla-quick-manage"; // registers <handla-quick-manage>
import type { HomeAssistant } from "./types";

type Entry = { name: string; icon?: string; count: number; pinned?: boolean };

const ITEMS: Entry[] = [
  { name: "Toalettpapper", icon: "mdi:paper-roll", count: 1, pinned: true },
  { name: "Tomater", icon: "mdi:fruit-cherries", count: 5 },
  { name: "Tomat", icon: "mdi:fruit-cherries", count: 2 },
  { name: "Mjölk", icon: "mdi:cow", count: 9 },
];

function makeHass(options: { items?: Entry[]; fail?: string; language?: string } = {}) {
  let items = options.items ?? ITEMS;
  const callService = vi.fn(async (_d: string, service: string, data?: Record<string, unknown>) => {
    if (options.fail && service !== "get_top_items") throw new Error(options.fail);
    if (service === "remove_quick_item") items = items.filter((i) => i.name !== data?.["item"]);
    if (service === "get_top_items") {
      if (options.fail === "load") throw new Error("load refused");
      return { context: {}, response: { items } };
    }
    return { context: {}, response: {} };
  });
  const hass = {
    states: {},
    language: options.language ?? "sv",
    callService,
  } as unknown as HomeAssistant;
  return { hass, callService };
}

async function settle(el: HandlaQuickManage): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await el.updateComplete;
}

async function mount(hass: HomeAssistant): Promise<HandlaQuickManage> {
  const el = document.createElement("handla-quick-manage") as HandlaQuickManage;
  el.hass = hass;
  document.body.appendChild(el);
  await settle(el);
  return el;
}

const root = (el: HandlaQuickManage) => el.shadowRoot as ShadowRoot;
const calls = (fn: ReturnType<typeof vi.fn>, service: string) =>
  fn.mock.calls.filter((call) => call[1] === service);

function check(el: HandlaQuickManage, name: string): void {
  const box = root(el).querySelector<HTMLInputElement>(`li[data-name="${name}"] input`);
  if (!box) throw new Error(`no row for ${name}`);
  box.checked = true;
  box.dispatchEvent(new Event("change"));
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("<handla-quick-manage>", () => {
  it("loads and lists every tracked item with counts and pins", async () => {
    const { hass, callService } = makeHass();
    const el = await mount(hass);

    expect(callService).toHaveBeenCalledWith(
      "handla",
      "get_top_items",
      { limit: 500 },
      undefined,
      false,
      true,
    );
    const rows = [...root(el).querySelectorAll<HTMLElement>("li")];
    expect(rows.map((row) => row.dataset["name"])).toEqual([
      "Toalettpapper",
      "Tomater",
      "Tomat",
      "Mjölk",
    ]);
    expect(rows[0]?.textContent).toContain("fäst");
    expect(rows[1]?.textContent).toContain("5×");
  });

  it("shows English when the user's language is not Swedish", async () => {
    const el = await mount(makeHass({ language: "en" }).hass);
    expect(root(el).textContent).toContain("Manage frequent items");
  });

  it("shows an error when loading fails, and an empty message for no items", async () => {
    const failing = await mount(makeHass({ fail: "load" }).hass);
    expect(root(failing).querySelector('[data-testid="load-error"]')?.textContent).toContain(
      "load refused",
    );
    document.body.innerHTML = "";
    const empty = await mount(makeHass({ items: [] }).hass);
    expect(root(empty).textContent).toContain("Inga vanliga varor");
  });

  it("removes an item and reloads", async () => {
    const { hass, callService } = makeHass();
    const el = await mount(hass);

    root(el)
      .querySelector<HTMLButtonElement>('li[data-name="Mjölk"] [data-action="remove"]')
      ?.click();
    await settle(el);

    expect(calls(callService, "remove_quick_item")[0]?.[2]).toEqual({ item: "Mjölk" });
    expect(root(el).querySelector('li[data-name="Mjölk"]')).toBeNull();
  });

  it("pins a new item from the field", async () => {
    const { hass, callService } = makeHass();
    const el = await mount(hass);
    const input = root(el).querySelector<HTMLInputElement>('input[type="text"]');
    const add = root(el).querySelector<HTMLButtonElement>('[data-action="new"]');
    expect(add?.disabled).toBe(true);

    if (input) {
      input.value = "  Diskmedel ";
      input.dispatchEvent(new Event("input"));
    }
    await el.updateComplete;
    root(el)
      .querySelector("form")
      ?.dispatchEvent(new Event("submit", { cancelable: true }));
    await settle(el);

    expect(calls(callService, "add_quick_item")[0]?.[2]).toEqual({ item: "Diskmedel" });
    expect(root(el).querySelector<HTMLInputElement>('input[type="text"]')?.value).toBe("");
  });

  it("ignores a blank new item", async () => {
    const { hass, callService } = makeHass();
    const el = await mount(hass);
    root(el)
      .querySelector("form")
      ?.dispatchEvent(new Event("submit", { cancelable: true }));
    await settle(el);
    expect(calls(callService, "add_quick_item")).toHaveLength(0);
  });

  it("merges two or more selected items into the name you pick", async () => {
    const { hass, callService } = makeHass();
    const el = await mount(hass);
    expect(root(el).querySelector('[data-action="merge"]')).toBeNull();

    check(el, "Tomat");
    await el.updateComplete;
    expect(root(el).querySelector('[data-action="merge"]')).toBeNull();
    check(el, "Tomater");
    await el.updateComplete;
    root(el).querySelector<HTMLButtonElement>('[data-action="merge"]')?.click();
    await el.updateComplete;

    const radios = [...root(el).querySelectorAll<HTMLInputElement>('input[type="radio"]')];
    expect(radios.map((r) => r.value)).toEqual(["Tomater", "Tomat"]); // most used first
    expect(radios[0]?.checked).toBe(true);

    radios[1]?.dispatchEvent(new Event("change"));
    await el.updateComplete;
    root(el).querySelector<HTMLButtonElement>('[data-action="merge-submit"]')?.click();
    await settle(el);

    expect(calls(callService, "merge_quick_items")[0]?.[2]).toEqual({
      sources: ["Tomater", "Tomat"],
      target: "Tomat",
    });
    expect(root(el).querySelector('[data-testid="merge"]')).toBeNull();
  });

  it("can cancel a merge and unselect an item", async () => {
    const el = await mount(makeHass().hass);
    check(el, "Tomat");
    check(el, "Mjölk");
    await el.updateComplete;
    root(el).querySelector<HTMLButtonElement>('[data-action="merge"]')?.click();
    await el.updateComplete;
    root(el).querySelector<HTMLButtonElement>('[data-action="merge-cancel"]')?.click();
    await el.updateComplete;
    expect(root(el).querySelector('[data-testid="merge"]')).toBeNull();

    const box = root(el).querySelector<HTMLInputElement>('li[data-name="Tomat"] input');
    if (box) {
      box.checked = false;
      box.dispatchEvent(new Event("change"));
    }
    await el.updateComplete;
    expect(root(el).querySelector('[data-action="merge"]')).toBeNull();
  });

  it("shows the error when a change fails and keeps the merge dialog open", async () => {
    const { hass } = makeHass({ fail: "Varan finns inte" });
    const el = await mount(hass);
    check(el, "Tomat");
    check(el, "Mjölk");
    await el.updateComplete;
    root(el).querySelector<HTMLButtonElement>('[data-action="merge"]')?.click();
    await el.updateComplete;
    root(el).querySelector<HTMLButtonElement>('[data-action="merge-submit"]')?.click();
    await settle(el);

    expect(root(el).querySelector('[data-testid="error"]')?.textContent).toContain(
      "Varan finns inte",
    );
    expect(root(el).querySelector('[data-testid="merge"]')).not.toBeNull();
  });

  it("fires close when done", async () => {
    const el = await mount(makeHass().hass);
    const onClose = vi.fn();
    el.addEventListener("close", onClose);
    root(el).querySelector<HTMLButtonElement>('[data-action="done"]')?.click();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does nothing without a hass object", async () => {
    const el = document.createElement("handla-quick-manage") as HandlaQuickManage;
    document.body.appendChild(el);
    await settle(el);
    expect(root(el).textContent).toContain("Hämtar");
  });
});
