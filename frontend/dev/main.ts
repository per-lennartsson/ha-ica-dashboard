/**
 * Mock-data preview of the card: run `DOCKER_FLAGS="-p 5173:5173" ./scripts/node.sh npm run dev`.
 * It imitates the integration: create/delete take a few seconds and change the status
 * sensor while they run, items change live through a mock websocket subscription, and a
 * second list operation during that time is refused.
 */
import "../src/index";
import type { InkopCard } from "../src/inkop-card";
import type { InkopShortcut } from "../src/inkop-shortcut";
import type { HomeAssistant } from "../src/types";

interface MockItem {
  uid: string;
  summary: string;
  completed: boolean;
}
interface MockList {
  id: string;
  title: string;
}

const MONTHS = [
  "januari",
  "februari",
  "mars",
  "april",
  "maj",
  "juni",
  "juli",
  "augusti",
  "september",
  "oktober",
  "november",
  "december",
];
const STAPLES: ReadonlyArray<readonly [string, string]> = [
  ["mjölk", "mdi:cow"],
  ["bröd", "mdi:bread-slice"],
  ["ägg", "mdi:egg"],
  ["smör", "mdi:cow"],
  ["ost", "mdi:cheese"],
  ["kaffe", "mdi:coffee"],
  ["bananer", "mdi:food-apple"],
  ["tomater", "mdi:fruit-grapes"],
];
const EMOJI: Record<string, string> = {
  "mdi:cow": "🐄",
  "mdi:bread-slice": "🍞",
  "mdi:egg": "🥚",
  "mdi:cheese": "🧀",
  "mdi:coffee": "☕",
  "mdi:food-apple": "🍎",
  "mdi:fruit-grapes": "🍅",
  "mdi:cart-outline": "🛒",
};

// Stand-in for Home Assistant's own <ha-icon>, which the preview does not have
class HaIconStub extends HTMLElement {
  static observedAttributes = ["icon"];
  attributeChangedCallback(): void {
    this.textContent = EMOJI[this.getAttribute("icon") ?? ""] ?? "•";
  }
}
if (!customElements.get("ha-icon")) customElements.define("ha-icon", HaIconStub);

const initialLists = (): MockList[] => [
  { id: "A-1", title: "Veckans mat" },
  { id: "B-2", title: "Fest på lördag" },
];
const initialItems = (): Record<string, MockItem[]> => ({
  "A-1": [
    { uid: "u1", summary: "1 l mjölk", completed: false },
    { uid: "u2", summary: "2 st gurka", completed: false },
    { uid: "u3", summary: "bröd", completed: true },
    { uid: "u4", summary: "smör", completed: false },
  ],
  "B-2": [],
});

const state = {
  language: "sv",
  running: true,
  lists: initialLists(),
  items: initialItems(),
  usage: new Map<string, { name: string; count: number }>(),
  active: "A-1" as string | null,
  status: "idle",
  detail: "",
  failNext: false,
  unavailableItems: false,
  counter: 0,
  uid: 100,
};

const entityOf = (id: string) => `todo.ica_${id.toLowerCase()}`;
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const open = (list: MockItem[]) => list.filter((item) => !item.completed);
const nameOf = (text: string) =>
  text
    .toLowerCase()
    .replace(/^\s*\d+([.,]\d+)?\s*(st|förp|kg|hg|g|l|dl|cl|ml|msk|tsk|krm)?\s+/, "")
    .trim();

function suggestion(): string {
  const now = new Date();
  const base = `Att handla ${now.getDate()} ${MONTHS[now.getMonth()]}`;
  const taken = new Set(state.lists.map((item) => item.title.toLowerCase()));
  let name = base;
  for (let n = 2; taken.has(name.toLowerCase()); n += 1) name = `${base} (${n})`;
  return name;
}

// --- mock websocket subscriptions (todo/item/subscribe) ---------------------
const subscribers = new Set<{ entityId: string; callback: (message: unknown) => void }>();

function push(): void {
  for (const sub of subscribers) {
    const list = state.lists.find((item) => entityOf(item.id) === sub.entityId);
    if (list) {
      sub.callback({
        items: (state.items[list.id] ?? []).map((item) => ({
          uid: item.uid,
          summary: item.summary,
          status: item.completed ? "completed" : "needs_action",
        })),
      });
    }
  }
}

function makeHass(): HomeAssistant {
  const states: HomeAssistant["states"] = {};
  if (state.running) {
    states["sensor.inkop_lists"] = {
      state: String(state.lists.length),
      attributes: {
        lists: state.lists.map((item) => ({
          entity_id: entityOf(item.id),
          offline_id: item.id,
          title: item.title,
          item_count: open(state.items[item.id] ?? []).length,
        })),
        active_offline_id: state.active,
      },
    };
    states["sensor.inkop_status"] = {
      state: state.status,
      attributes: state.detail ? { detail: state.detail } : {},
    };
    const real = [...state.usage.values()].sort((a, b) => b.count - a.count).slice(0, 12);
    const shown = real.map((u) => ({ name: u.name, count: u.count, icon: iconFor(u.name) }));
    for (const [name, icon] of STAPLES) {
      if (shown.length >= 8) break;
      if (!shown.some((s) => s.name.toLowerCase() === name)) shown.push({ name, count: 0, icon });
    }
    states["sensor.inkop_frequent_items"] = {
      state: String(state.usage.size),
      attributes: { items: shown },
    };
    for (const list of state.lists) {
      states[entityOf(list.id)] = {
        state:
          state.unavailableItems && list.id === state.active
            ? "unavailable"
            : String(open(state.items[list.id] ?? []).length),
        attributes: {},
      };
    }
  }
  return {
    language: state.language,
    states,
    callService: async (_domain, service, data) => handle(service, data ?? {}),
    connection: {
      subscribeMessage: async <T>(
        callback: (message: T) => void,
        message: Record<string, unknown>,
      ) => {
        const sub = {
          entityId: String(message["entity_id"]),
          callback: callback as (m: unknown) => void,
        };
        subscribers.add(sub);
        setTimeout(push, 150);
        return () => subscribers.delete(sub);
      },
    },
  };
}

function iconFor(name: string): string {
  return STAPLES.find(([n]) => name.toLowerCase().includes(n))?.[1] ?? "mdi:cart-outline";
}

function listOf(entityId: unknown): MockList {
  const list = state.lists.find((item) => entityOf(item.id) === entityId);
  if (!list) throw { message: `Unknown list ${String(entityId)}` };
  return list;
}

async function handle(service: string, data: Record<string, unknown>): Promise<unknown> {
  if (service === "suggest_list_name") return { context: {}, response: { name: suggestion() } };
  const failing = state.failNext;
  if (["add_item", "tick_item", "remove_item", "clear_ticked"].includes(service)) {
    await sleep(400);
    if (failing) {
      state.failNext = false;
      throw { message: "ICA said no." };
    }
    return handleItem(service, data);
  }
  if (state.status === "creating" || state.status === "deleting") {
    throw { message: "Another list operation is still running. Wait for it to finish." };
  }
  state.failNext = false;
  state.detail = "";
  if (service === "create_list") {
    state.status = "creating";
    refresh();
    await sleep(2500);
    if (failing) return fail("The list was created, but did not appear in time.");
    state.counter += 1;
    const id = `NEW-${state.counter}`;
    state.lists.push({ id, title: String(data["title"]) });
    state.items[id] = [];
    state.active = id;
    state.status = "idle";
    refresh();
    return { context: {}, response: { offline_id: id } };
  }
  if (service === "delete_list") {
    state.status = "deleting";
    refresh();
    await sleep(2500);
    if (failing) return fail("Could not delete the list: ICA said no.");
    const doomed = listOf(data["entity_id"]);
    state.lists = state.lists.filter((item) => item !== doomed);
    if (state.active === doomed.id) state.active = state.lists[0]?.id ?? null;
    state.status = "idle";
    refresh();
    return { context: {}, response: {} };
  }
  throw { message: `Unknown service ${service}` };
}

function handleItem(service: string, data: Record<string, unknown>): unknown {
  const list = listOf(data["entity_id"]);
  const items = (state.items[list.id] ??= []);
  if (service === "add_item") {
    const text = String(data["item"]).trim();
    const duplicates = open(items).filter((item) => nameOf(item.summary) === nameOf(text));
    if (duplicates.length > 0 && data["confirm_duplicate"] !== true) {
      return {
        context: {},
        response: {
          added: false,
          duplicate: true,
          item: text,
          duplicates: duplicates.map((d) => ({ uid: d.uid, summary: d.summary })),
        },
      };
    }
    state.uid += 1;
    items.push({ uid: `u${state.uid}`, summary: text, completed: false });
    const key = nameOf(text);
    const entry = state.usage.get(key) ?? { name: key, count: 0 };
    state.usage.set(key, { name: key, count: entry.count + 1 });
    push();
    refresh();
    return {
      context: {},
      response: { added: true, duplicate: duplicates.length > 0, item: text, duplicates: [] },
    };
  }
  if (service === "clear_ticked") {
    state.items[list.id] = items.filter((item) => !item.completed);
  } else {
    const item = items.find((entry) => entry.uid === data["item"]);
    if (!item) throw { message: `No item matching “${String(data["item"])}” on the list.` };
    if (service === "tick_item") item.completed = data["ticked"] !== false;
    if (service === "remove_item") state.items[list.id] = items.filter((entry) => entry !== item);
  }
  push();
  refresh();
  return { context: {}, response: {} };
}

function fail(message: string): never {
  state.status = "error";
  state.detail = message;
  refresh();
  throw { message };
}

// The phone shortcut: a tap navigates (here the preview just reports where it would go)
const shortcut = document.createElement("inkop-shortcut") as InkopShortcut;
shortcut.setConfig({ type: "custom:inkop-shortcut", navigation_path: "/lovelace/inkop" });
const where = document.createElement("p");
where.id = "where";
where.style.cssText = "margin: 4px 0 16px; font-size: 0.85rem; color: #555";
window.addEventListener("location-changed", () => {
  where.textContent = `Genvägen öppnar: ${window.location.pathname}`;
  window.history.replaceState(null, "", "/");
});
document.getElementById("host")?.append(shortcut, where);

const card = document.createElement("inkop-card") as InkopCard;
card.setConfig({ type: "custom:inkop-card" });
document.getElementById("host")?.appendChild(card);

function refresh(): void {
  card.hass = makeHass();
  shortcut.hass = makeHass();
}

function addControl(label: string, onClick: () => void): void {
  const button = document.createElement("button");
  button.textContent = label;
  button.addEventListener("click", () => {
    onClick();
    refresh();
    push();
  });
  document.getElementById("controls")?.appendChild(button);
}

addControl("Svenska", () => (state.language = "sv"));
addControl("English", () => (state.language = "en"));
addControl("Inköp körs inte", () => (state.running = !state.running));
addControl("Nästa åtgärd misslyckas", () => (state.failNext = true));
addControl("Listan otillgänglig", () => (state.unavailableItems = !state.unavailableItems));
addControl("Återställ", () => {
  state.lists = initialLists();
  state.items = initialItems();
  state.usage = new Map();
  state.active = "A-1";
  state.status = "idle";
  state.detail = "";
  state.running = true;
  state.failNext = false;
  state.unavailableItems = false;
});
refresh();
