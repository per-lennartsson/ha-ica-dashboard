import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import "./handla-ai";
import "./handla-items";
import { createList, deleteList, errorMessage, suggestListName } from "./api";
import { localize, type TranslationKey } from "./i18n";
import {
  listLabel,
  readLists,
  readStatus,
  resolveSelected,
  type ListInfo,
  type Status,
} from "./lists";
import { loadSelectedList, saveSelectedList } from "./storage";
import type { HomeAssistant, HandlaCardConfig } from "./types";

type Mode = "list" | "create" | "delete";

export class HandlaCard extends LitElement {
  static override properties = {
    hass: { attribute: false },
    _config: { state: true },
    _mode: { state: true },
    _name: { state: true },
    _pending: { state: true },
    _error: { state: true },
    _selected: { state: true },
    _deleteTarget: { state: true },
  };

  static override styles = css`
    .card {
      display: block;
      padding: 16px;
      background: var(--ha-card-background, var(--card-background-color, white));
      color: var(--primary-text-color, #212121);
      border-radius: var(--ha-card-border-radius, 12px);
    }
    h2 {
      margin: 0 0 12px;
      font-size: 1.25rem;
      font-weight: 500;
    }
    p {
      margin: 8px 0;
    }
    .muted {
      color: var(--secondary-text-color, #727272);
    }
    .row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: stretch;
    }
    label {
      display: block;
      margin-bottom: 4px;
      font-size: 0.875rem;
      color: var(--secondary-text-color, #727272);
    }
    select,
    input[type="text"] {
      flex: 1 1 200px;
      min-width: 0;
      min-height: 44px;
      padding: 0 12px;
      box-sizing: border-box;
      /* 16px stops iOS from zooming in when the field gets focus */
      font-size: 16px;
      color: inherit;
      background: var(--secondary-background-color, #f4f4f5);
      border: 1px solid var(--divider-color, #cfcfcf);
      border-radius: 8px;
    }
    button {
      min-height: 44px;
      padding: 0 16px;
      font-size: 0.95rem;
      font-family: inherit;
      color: var(--primary-text-color, #212121);
      background: var(--secondary-background-color, #f4f4f5);
      border: 1px solid var(--divider-color, #cfcfcf);
      border-radius: 8px;
      cursor: pointer;
    }
    button.primary {
      color: var(--text-primary-color, white);
      background: var(--primary-color, #03a9f4);
      border-color: transparent;
    }
    button.danger {
      color: var(--text-primary-color, white);
      background: var(--error-color, #db4437);
      border-color: transparent;
    }
    button:disabled,
    select:disabled,
    input:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .progress {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 12px;
    }
    .spinner {
      width: 18px;
      height: 18px;
      border: 3px solid var(--divider-color, #cfcfcf);
      border-top-color: var(--primary-color, #03a9f4);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
    .error {
      margin: 0 0 12px;
      padding: 8px 12px;
      color: var(--error-color, #db4437);
      border: 1px solid var(--error-color, #db4437);
      border-radius: 8px;
    }
    .actions {
      margin-top: 12px;
    }
  `;

  declare hass?: HomeAssistant;
  declare _config?: HandlaCardConfig;
  declare _mode: Mode;
  declare _name: string;
  declare _pending: boolean;
  declare _error: string | null;
  /** This user's own choice of list (ICA offline id), kept in this browser. */
  declare _selected: string | null;
  /** The list the delete confirmation is about (ICA offline id). */
  declare _deleteTarget: string | null;

  constructor() {
    super();
    this._mode = "list";
    this._name = "";
    this._pending = false;
    this._error = null;
    this._selected = null;
    this._deleteTarget = null;
  }

  static getStubConfig(): Partial<HandlaCardConfig> {
    return {};
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this._selected = loadSelectedList();
  }

  setConfig(config: HandlaCardConfig): void {
    if (typeof config !== "object" || config === null) {
      throw new Error(localize(this.hass?.language, "card.invalid_config"));
    }
    this._config = config;
  }

  getCardSize(): number {
    return 2;
  }

  private _t(key: TranslationKey, params: Record<string, string | number> = {}): string {
    return localize(this.hass?.language, key, params);
  }

  override willUpdate(): void {
    // A confirmation must never outlive the list it is about
    if (this._mode === "delete") {
      const lists = readLists(this.hass)?.lists ?? [];
      if (!lists.some((item) => item.offlineId === this._deleteTarget)) {
        this._mode = "list";
        this._deleteTarget = null;
      }
    }
  }

  override updated(changed: PropertyValues<this>): void {
    if (changed.has("_mode") && this._mode === "create") {
      this.renderRoot.querySelector<HTMLInputElement>("input[type=text]")?.focus();
    }
  }

  // --- actions -------------------------------------------------------------

  private _select(offlineId: string): void {
    this._selected = offlineId;
    saveSelectedList(offlineId);
  }

  private async _openCreate(): Promise<void> {
    this._error = null;
    this._name = "";
    this._mode = "create";
    const hass = this.hass;
    if (!hass) return;
    try {
      const suggestion = await suggestListName(hass);
      // Do not overwrite what the user has already started typing
      if (this._mode === "create" && this._name === "") this._name = suggestion;
    } catch {
      // No suggestion: the user types a name themselves
    }
  }

  private _openDelete(list: ListInfo): void {
    this._error = null;
    this._deleteTarget = list.offlineId;
    this._mode = "delete";
  }

  private _cancel(): void {
    this._error = null;
    this._deleteTarget = null;
    this._mode = "list";
  }

  private async _submitCreate(event: Event): Promise<void> {
    event.preventDefault();
    const hass = this.hass;
    const title = this._name.trim();
    if (!hass || this._pending) return;
    if (!title) {
      this._error = this._t("create.name_required");
      return;
    }
    await this._run(async () => {
      const offlineId = await createList(hass, title);
      if (offlineId) this._select(offlineId);
      this._mode = "list";
    });
  }

  private async _confirmDelete(entityId: string, offlineId: string): Promise<void> {
    const hass = this.hass;
    if (!hass || this._pending) return;
    await this._run(async () => {
      await deleteList(hass, entityId);
      if (this._selected?.toLowerCase() === offlineId.toLowerCase()) {
        this._selected = null;
        saveSelectedList(null);
      }
      this._deleteTarget = null;
      this._mode = "list";
    });
  }

  /** Runs one action with the controls locked, so nobody can tap twice. */
  private async _run(action: () => Promise<void>): Promise<void> {
    this._pending = true;
    this._error = null;
    try {
      await action();
    } catch (err) {
      this._error = this._t("error.generic", { message: errorMessage(err) });
    } finally {
      this._pending = false;
    }
  }

  // --- rendering -----------------------------------------------------------

  override render() {
    if (!this._config) return nothing;
    const title = this._config.title ?? this._t("card.title");
    const state = readLists(this.hass);
    return html`
      <div class="card">
        <h2>${title}</h2>
        ${
          state === null
            ? html`<p class="muted" data-testid="not-running">${this._t("card.not_running")}</p>`
            : this._renderBody(state.lists, state.activeOfflineId)
        }
      </div>
    `;
  }

  private _renderBody(lists: ListInfo[], activeOfflineId: string | null) {
    const { status, detail } = readStatus(this.hass);
    const busy = this._pending || status === "creating" || status === "deleting";
    const selected = resolveSelected(lists, this._selected, activeOfflineId);
    const target = lists.find((item) => item.offlineId === this._deleteTarget);
    return html`
      ${this._renderProgress(status)} ${this._renderError(status, detail, busy)}
      ${
        this._mode === "create"
          ? this._renderCreate(busy)
          : this._mode === "delete" && target
            ? this._renderDelete(target, busy)
            : this._renderPicker(lists, selected, busy)
      }
      ${
        this._mode === "list" && selected
          ? html`<handla-ai .hass=${this.hass} .list=${selected} .locked=${busy}></handla-ai>
              <handla-items .hass=${this.hass} .list=${selected} .locked=${busy}></handla-items>`
          : nothing
      }
    `;
  }

  private _renderProgress(status: Status) {
    let key: TranslationKey | null = null;
    if (status === "creating") key = "busy.creating";
    else if (status === "deleting") key = "busy.deleting";
    else if (this._pending) key = "busy.working";
    if (key === null) return nothing;
    return html`
      <div class="progress" role="status" aria-live="polite" data-testid="progress">
        <span class="spinner"></span><span>${this._t(key)}</span>
      </div>
    `;
  }

  private _renderError(status: Status, detail: string | null, busy: boolean) {
    const message =
      this._error ??
      (status === "error" && !busy ? this._t("error.last", { detail: detail ?? "?" }) : null);
    if (message === null) return nothing;
    return html`<div class="error" role="alert" data-testid="error">${message}</div>`;
  }

  private _renderPicker(lists: ListInfo[], selected: ListInfo | null, busy: boolean) {
    return html`
      ${
        lists.length === 0
          ? html`<p class="muted" data-testid="no-lists">${this._t("lists.none")}</p>`
          : html`
              <label for="list">${this._t("lists.label")}</label>
              <div class="row">
                <select
                  id="list"
                  ?disabled=${busy}
                  @change=${(event: Event) =>
                    this._select((event.target as HTMLSelectElement).value)}
                >
                  ${lists.map(
                    (item) => html`
                      <option
                        value=${item.offlineId}
                        ?selected=${item.offlineId === selected?.offlineId}
                      >
                        ${listLabel(item)}
                      </option>
                    `,
                  )}
                </select>
              </div>
            `
      }
      <div class="row actions">
        <button
          class="primary"
          data-action="new-list"
          ?disabled=${busy}
          @click=${() => void this._openCreate()}
        >
          ${this._t("lists.new")}
        </button>
        ${
          selected
            ? html`
                <button
                  data-action="delete-list"
                  ?disabled=${busy}
                  @click=${() => this._openDelete(selected)}
                >
                  ${this._t("lists.delete")}
                </button>
              `
            : nothing
        }
      </div>
    `;
  }

  private _renderCreate(busy: boolean) {
    return html`
      <form @submit=${(event: Event) => void this._submitCreate(event)}>
        <label for="name">${this._t("create.label")}</label>
        <div class="row">
          <input
            id="name"
            type="text"
            autocomplete="off"
            enterkeyhint="done"
            .value=${this._name}
            ?disabled=${busy}
            @input=${(event: Event) => (this._name = (event.target as HTMLInputElement).value)}
          />
        </div>
        <div class="row actions">
          <button type="submit" class="primary" data-action="submit-create" ?disabled=${busy}>
            ${this._t("create.submit")}
          </button>
          <button
            type="button"
            data-action="cancel"
            ?disabled=${busy}
            @click=${() => this._cancel()}
          >
            ${this._t("create.cancel")}
          </button>
        </div>
      </form>
    `;
  }

  private _renderDelete(target: ListInfo, busy: boolean) {
    return html`
      <p data-testid="confirm">${this._t("delete.confirm", { title: target.title })}</p>
      <div class="row actions">
        <button
          class="danger"
          data-action="confirm-delete"
          ?disabled=${busy}
          @click=${() => void this._confirmDelete(target.entityId, target.offlineId)}
        >
          ${this._t("delete.submit")}
        </button>
        <button data-action="cancel" ?disabled=${busy} @click=${() => this._cancel()}>
          ${this._t("delete.cancel")}
        </button>
      </div>
    `;
  }
}

if (!customElements.get("handla-card")) {
  customElements.define("handla-card", HandlaCard);
}

window.customCards = window.customCards ?? [];
if (!window.customCards.some((card) => card.type === "handla-card")) {
  window.customCards.push({
    type: "handla-card",
    name: "Handla",
    description: "Shopping lists on top of ICA",
  });
}

console.info(`%c HANDLA %c v${__HANDLA_VERSION__} `, "background:#03a9f4;color:#fff", "");
