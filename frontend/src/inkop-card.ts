import { LitElement, css, html, nothing } from "lit";
import { localize } from "./i18n";
import type { HomeAssistant, InkopCardConfig } from "./types";

/** Entity with the number of items still to buy on the active list. */
export const ITEMS_ENTITY = "sensor.inkop_items_to_buy";

export class InkopCard extends LitElement {
  static override properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  static override styles = css`
    ha-card,
    .card {
      display: block;
      padding: 16px;
      background: var(--ha-card-background, var(--card-background-color, white));
      color: var(--primary-text-color, #212121);
      border-radius: var(--ha-card-border-radius, 12px);
    }
    h2 {
      margin: 0 0 8px;
      font-size: 1.25rem;
      font-weight: 500;
    }
    p {
      margin: 4px 0;
    }
    .muted {
      color: var(--secondary-text-color, #727272);
    }
  `;

  declare hass?: HomeAssistant;
  declare _config?: InkopCardConfig;

  static getStubConfig(): Partial<InkopCardConfig> {
    return {};
  }

  setConfig(config: InkopCardConfig): void {
    if (typeof config !== "object" || config === null) {
      throw new Error(localize(this.hass?.language, "card.invalid_config"));
    }
    this._config = config;
  }

  getCardSize(): number {
    return 2;
  }

  override render() {
    if (!this._config) return nothing;
    const language = this.hass?.language;
    const count = this.hass?.states[ITEMS_ENTITY]?.state;
    const title = this._config.title ?? localize(language, "card.title");
    return html`
      <div class="card">
        <h2>${title}</h2>
        <p>${localize(language, "card.loaded")}</p>
        <p class="muted">
          ${
            count !== undefined && count !== "unavailable" && count !== "unknown"
              ? localize(language, "card.items", { count })
              : localize(language, "card.no_data")
          }
        </p>
        <p class="muted">v${__INKOP_VERSION__}</p>
      </div>
    `;
  }
}

if (!customElements.get("inkop-card")) {
  customElements.define("inkop-card", InkopCard);
}

window.customCards = window.customCards ?? [];
if (!window.customCards.some((card) => card.type === "inkop-card")) {
  window.customCards.push({
    type: "inkop-card",
    name: "Inköp",
    description: "Shopping lists on top of ICA",
  });
}
