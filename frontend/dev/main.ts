/**
 * Mock-data preview of the card: run `DOCKER_FLAGS="-p 5173:5173" ./scripts/node.sh npm run dev`.
 * It imitates the integration: create/delete take a few seconds and change the status
 * sensor while they run, and a second call during that time is refused.
 */
import "../src/inkop-card";
import type { InkopCard } from "../src/inkop-card";
import type { HomeAssistant } from "../src/types";

interface MockList {
  id: string;
  title: string;
  count: number;
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

const initial = (): MockList[] => [
  { id: "A-1", title: "Veckans mat", count: 4 },
  { id: "B-2", title: "Fest på lördag", count: 0 },
];

const state = {
  language: "sv",
  running: true,
  lists: initial(),
  active: "A-1" as string | null,
  status: "idle",
  detail: "",
  failNext: false,
  counter: 0,
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function suggestion(): string {
  const now = new Date();
  const base = `Att handla ${now.getDate()} ${MONTHS[now.getMonth()]}`;
  const taken = new Set(state.lists.map((item) => item.title.toLowerCase()));
  let name = base;
  for (let n = 2; taken.has(name.toLowerCase()); n += 1) name = `${base} (${n})`;
  return name;
}

function makeHass(): HomeAssistant {
  const states: HomeAssistant["states"] = {};
  if (state.running) {
    states["sensor.inkop_lists"] = {
      state: String(state.lists.length),
      attributes: {
        lists: state.lists.map((item) => ({
          entity_id: `todo.ica_${item.id.toLowerCase()}`,
          offline_id: item.id,
          title: item.title,
          item_count: item.count,
        })),
        active_offline_id: state.active,
      },
    };
    states["sensor.inkop_status"] = {
      state: state.status,
      attributes: state.detail ? { detail: state.detail } : {},
    };
  }
  return {
    language: state.language,
    states,
    callService: async (_domain, service, data) => handle(service, data ?? {}),
  };
}

async function handle(service: string, data: Record<string, unknown>): Promise<unknown> {
  if (service === "suggest_list_name") return { context: {}, response: { name: suggestion() } };
  if (state.status === "creating" || state.status === "deleting") {
    throw { message: "Another list operation is still running. Wait for it to finish." };
  }
  const failing = state.failNext;
  state.failNext = false;
  state.detail = "";
  if (service === "create_list") {
    state.status = "creating";
    refresh();
    await sleep(2500);
    if (failing) return fail("The list was created, but did not appear in time.");
    state.counter += 1;
    const id = `NEW-${state.counter}`;
    state.lists.push({ id, title: String(data["title"]), count: 0 });
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
    const doomed = state.lists.find(
      (item) => `todo.ica_${item.id.toLowerCase()}` === data["entity_id"],
    );
    state.lists = state.lists.filter((item) => item !== doomed);
    if (doomed && state.active === doomed.id) state.active = state.lists[0]?.id ?? null;
    state.status = "idle";
    refresh();
    return { context: {}, response: {} };
  }
  throw { message: `Unknown service ${service}` };
}

function fail(message: string): never {
  state.status = "error";
  state.detail = message;
  refresh();
  throw { message };
}

const card = document.createElement("inkop-card") as InkopCard;
card.setConfig({ type: "custom:inkop-card" });
document.getElementById("host")?.appendChild(card);

function refresh(): void {
  card.hass = makeHass();
}

function addControl(label: string, onClick: () => void): void {
  const button = document.createElement("button");
  button.textContent = label;
  button.addEventListener("click", () => {
    onClick();
    refresh();
  });
  document.getElementById("controls")?.appendChild(button);
}

addControl("Svenska", () => (state.language = "sv"));
addControl("English", () => (state.language = "en"));
addControl("Inköp körs inte", () => (state.running = !state.running));
addControl("Nästa åtgärd misslyckas", () => (state.failNext = true));
addControl("Inga listor", () => {
  state.lists = [];
  state.active = null;
});
addControl("Återställ", () => {
  state.lists = initial();
  state.active = "A-1";
  state.status = "idle";
  state.detail = "";
  state.running = true;
  state.failNext = false;
});
refresh();
