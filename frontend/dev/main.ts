/** Mock-data preview of the card: run `./scripts/node.sh npm run dev`. */
import "../src/inkop-card";
import type { InkopCard } from "../src/inkop-card";
import type { HomeAssistant } from "../src/types";

const state = { language: "sv", count: "3" as string };

function makeHass(): HomeAssistant {
  return {
    language: state.language,
    states:
      state.count === ""
        ? {}
        : { "sensor.inkop_items_to_buy": { state: state.count, attributes: {} } },
    callService: async () => undefined,
  };
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
addControl("3 varor", () => (state.count = "3"));
addControl("0 varor", () => (state.count = "0"));
addControl("Ingen data", () => (state.count = ""));
addControl("Otillgänglig", () => (state.count = "unavailable"));
refresh();
