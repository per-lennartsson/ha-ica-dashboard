import { LitElement, css, html, nothing } from "lit";
import { localize, type TranslationKey } from "./i18n";
import { readLists, resolveSelected } from "./lists";
import { isDashboardPath, navigate } from "./navigate";
import { loadSelectedList } from "./storage";
import type { HomeAssistant, HandlaShortcutConfig } from "./types";

/**
 * A small card for the phone dashboard: how many items are left to buy, and (if a
 * navigation_path is configured) a tap opens the shopping view.
 */
export class HandlaShortcut extends LitElement {
  static override properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  static override styles = css`
    .card {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 12px 16px;
      min-height: 64px;
      box-sizing: border-box;
      background: var(--ha-card-background, var(--card-background-color, white));
      color: var(--primary-text-color, #212121);
      border-radius: var(--ha-card-border-radius, 12px);
    }
    .card.tappable {
      cursor: pointer;
    }
    .card.tappable:focus-visible {
      outline: 2px solid var(--primary-color, #03a9f4);
      outline-offset: 2px;
    }
    .count {
      min-width: 2ch;
      font-size: 2rem;
      font-weight: 500;
      line-height: 1;
      text-align: center;
      color: var(--primary-color, #03a9f4);
    }
    .text {
      display: flex;
      flex-direction: column;
      min-width: 0;
    }
    .label {
      font-size: 1rem;
    }
    .list {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 0.85rem;
      color: var(--secondary-text-color, #727272);
    }
    .muted {
      color: var(--secondary-text-color, #727272);
    }
    .chevron {
      margin-left: auto;
      font-size: 1.5rem;
      color: var(--secondary-text-color, #727272);
    }
  `;

  declare hass?: HomeAssistant;
  declare _config?: HandlaShortcutConfig;

  static getStubConfig(): Partial<HandlaShortcutConfig> {
    return {};
  }

  setConfig(config: HandlaShortcutConfig): void {
    if (typeof config !== "object" || config === null) {
      throw new Error(localize(this.hass?.language, "card.invalid_config"));
    }
    if (config.navigation_path !== undefined && !isDashboardPath(config.navigation_path)) {
      throw new Error(localize(this.hass?.language, "shortcut.invalid_path"));
    }
    this._config = config;
  }

  getCardSize(): number {
    return 1;
  }

  private _t(key: TranslationKey, params: Record<string, string | number> = {}): string {
    return localize(this.hass?.language, key, params);
  }

  private _open(): void {
    const path = this._config?.navigation_path;
    if (path) navigate(path);
  }

  private _onKey(event: KeyboardEvent): void {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      this._open();
    }
  }

  override render() {
    if (!this._config) return nothing;
    const path = this._config.navigation_path;
    const state = readLists(this.hass);
    const list = state
      ? resolveSelected(state.lists, loadSelectedList(), state.activeOfflineId)
      : null;
    const count = list?.itemCount ?? null;
    const title = this._config.title ?? list?.title ?? this._t("shortcut.no_list");

    let body;
    if (state === null) {
      body = html`<div class="text">
        <span class="label muted">${this._t("shortcut.not_running")}</span>
      </div>`;
    } else {
      body = html`
        <span class="count" data-testid="count">${count ?? "–"}</span>
        <div class="text">
          <span class="label"
            >${count === null ? this._t("shortcut.unknown") : this._t("shortcut.to_buy")}</span
          >
          <span class="list" data-testid="list">${title}</span>
        </div>
      `;
    }

    const label =
      count === null
        ? nothing
        : this._t(path ? "shortcut.aria_open" : "shortcut.aria", { count, title });
    return html`
      <div
        class="card ${path ? "tappable" : ""}"
        role=${path ? "button" : nothing}
        tabindex=${path ? "0" : nothing}
        aria-label=${label}
        @click=${() => this._open()}
        @keydown=${(event: KeyboardEvent) => (path ? this._onKey(event) : undefined)}
      >
        ${body}
        ${path && state !== null ? html`<span class="chevron" aria-hidden="true">›</span>` : nothing}
      </div>
    `;
  }
}

if (!customElements.get("handla-shortcut")) {
  customElements.define("handla-shortcut", HandlaShortcut);
}

window.customCards = window.customCards ?? [];
if (!window.customCards.some((card) => card.type === "handla-shortcut")) {
  window.customCards.push({
    type: "handla-shortcut",
    name: "Handla: genväg",
    description: "Items left to buy, with a tap to open the shopping view",
  });
}
