import { LitElement, css, html, nothing } from "lit";
import { addQuickItem, errorMessage, getQuickItems, mergeQuickItems, removeQuickItem } from "./api";
import { localize, type TranslationKey } from "./i18n";
import type { QuickItem } from "./items";
import type { HomeAssistant } from "./types";

/**
 * Manage the quick-add items: remove one, merge several into one (you pick the name that
 * stays) and pin a new one. All rules live in the integration; this only calls it.
 * Fires `close` when the user is done.
 */
export class HandlaQuickManage extends LitElement {
  static override properties = {
    hass: { attribute: false },
    _items: { state: true },
    _loadError: { state: true },
    _selected: { state: true },
    _merging: { state: true },
    _mergeTarget: { state: true },
    _newName: { state: true },
    _busy: { state: true },
    _error: { state: true },
  };

  static override styles = css`
    :host {
      display: block;
      margin: 12px 0;
    }
    h3 {
      margin: 0;
      font-size: 1rem;
      font-weight: 500;
    }
    .head,
    .row {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .head {
      justify-content: space-between;
    }
    .muted {
      color: var(--secondary-text-color, #727272);
      font-size: 0.85rem;
    }
    p {
      margin: 8px 0;
    }
    ul {
      list-style: none;
      margin: 8px 0;
      padding: 0;
    }
    li {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 48px;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    li .name {
      flex: 1 1 auto;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    li ha-icon {
      --mdc-icon-size: 20px;
      color: var(--primary-color, #03a9f4);
    }
    input[type="checkbox"],
    input[type="radio"] {
      width: 22px;
      height: 22px;
      margin: 0 6px;
    }
    input[type="text"] {
      flex: 1 1 auto;
      min-width: 0;
      min-height: 44px;
      padding: 0 12px;
      box-sizing: border-box;
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
    button.icon-button {
      width: 44px;
      min-width: 44px;
      padding: 0;
      background: none;
      border: none;
      font-size: 1.25rem;
    }
    button:disabled,
    input:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .notice {
      margin: 12px 0;
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid var(--divider-color, #cfcfcf);
    }
    .notice.error {
      color: var(--error-color, #db4437);
      border-color: var(--error-color, #db4437);
    }
    .notice .row {
      margin-top: 8px;
      flex-wrap: wrap;
    }
    label.choice {
      display: flex;
      align-items: center;
      min-height: 44px;
    }
  `;

  declare hass?: HomeAssistant;
  declare _items: QuickItem[] | null;
  declare _loadError: string | null;
  declare _selected: ReadonlySet<string>;
  declare _merging: boolean;
  declare _mergeTarget: string;
  declare _newName: string;
  declare _busy: boolean;
  declare _error: string | null;

  constructor() {
    super();
    this._items = null;
    this._loadError = null;
    this._selected = new Set();
    this._merging = false;
    this._mergeTarget = "";
    this._newName = "";
    this._busy = false;
    this._error = null;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    void this._load();
  }

  private _t(key: TranslationKey, params: Record<string, string | number> = {}): string {
    return localize(this.hass?.language, key, params);
  }

  private async _load(): Promise<void> {
    if (!this.hass) return;
    try {
      const items = await getQuickItems(this.hass);
      const names = new Set(items.map((item) => item.name));
      this._items = items;
      this._loadError = null;
      this._selected = new Set([...this._selected].filter((name) => names.has(name)));
    } catch (err) {
      this._loadError = errorMessage(err);
    }
  }

  /** Runs a change, then reloads the list; a failure is shown and nothing else changes. */
  private async _change(action: (hass: HomeAssistant) => Promise<void>): Promise<boolean> {
    if (!this.hass || this._busy) return false;
    this._busy = true;
    this._error = null;
    try {
      await action(this.hass);
      await this._load();
      return true;
    } catch (err) {
      this._error = errorMessage(err);
      return false;
    } finally {
      this._busy = false;
    }
  }

  private _toggle(name: string, checked: boolean): void {
    const next = new Set(this._selected);
    if (checked) next.add(name);
    else next.delete(name);
    this._selected = next;
  }

  /** The selected items, most added first (the first one is the default name to keep). */
  private get _selectedItems(): QuickItem[] {
    return (this._items ?? [])
      .filter((item) => this._selected.has(item.name))
      .sort((a, b) => b.count - a.count);
  }

  private _startMerge(): void {
    this._mergeTarget = this._selectedItems[0]?.name ?? "";
    this._merging = true;
  }

  private async _merge(): Promise<void> {
    const sources = this._selectedItems.map((item) => item.name);
    const target = this._mergeTarget;
    const done = await this._change((hass) => mergeQuickItems(hass, sources, target));
    if (done) {
      this._merging = false;
      this._selected = new Set();
    }
  }

  private async _add(event: Event): Promise<void> {
    event.preventDefault();
    const name = this._newName.trim();
    if (!name) return;
    if (await this._change((hass) => addQuickItem(hass, name))) this._newName = "";
  }

  private _close(): void {
    this.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true }));
  }

  override render() {
    return html`
      <div class="head">
        <h3>${this._t("quick.title")}</h3>
        <button class="primary" data-action="done" @click=${this._close}>
          ${this._t("quick.done")}
        </button>
      </div>
      <p class="muted">${this._t("quick.hint")}</p>
      ${this._renderList()} ${this._renderMerge()} ${this._renderAddForm()}
      ${
        this._error
          ? html`<div class="notice error" role="alert" data-testid="error">
              ${this._t("quick.failed", { message: this._error })}
            </div>`
          : nothing
      }
    `;
  }

  private _renderList() {
    if (this._loadError) {
      return html`<div class="notice error" role="alert" data-testid="load-error">
        ${this._t("quick.load_error", { message: this._loadError })}
      </div>`;
    }
    if (this._items === null) return html`<p class="muted">${this._t("quick.loading")}</p>`;
    if (this._items.length === 0) return html`<p class="muted">${this._t("quick.empty")}</p>`;
    return html`
      <ul>
        ${this._items.map(
          (item) => html`
            <li data-name=${item.name}>
              <input
                type="checkbox"
                aria-label=${this._t("quick.select", { item: item.name })}
                .checked=${this._selected.has(item.name)}
                ?disabled=${this._busy}
                @change=${(event: Event) =>
                  this._toggle(item.name, (event.target as HTMLInputElement).checked)}
              />
              <ha-icon icon=${item.icon}></ha-icon>
              <span class="name">
                ${item.name}
                <span class="muted">
                  ${item.pinned ? `${this._t("quick.pinned")} · ` : ""}${item.count}×
                </span>
              </span>
              <button
                class="icon-button"
                data-action="remove"
                aria-label=${this._t("quick.remove", { item: item.name })}
                ?disabled=${this._busy}
                @click=${() => this._change((hass) => removeQuickItem(hass, item.name))}
              >
                ✕
              </button>
            </li>
          `,
        )}
      </ul>
    `;
  }

  private _renderMerge() {
    const selected = this._selectedItems;
    if (this._merging && selected.length >= 2) {
      return html`
        <div class="notice" role="group" data-testid="merge">
          <div>${this._t("quick.merge_prompt")}</div>
          ${selected.map(
            (item) => html`
              <label class="choice">
                <input
                  type="radio"
                  name="merge-target"
                  .value=${item.name}
                  .checked=${this._mergeTarget === item.name}
                  @change=${() => (this._mergeTarget = item.name)}
                />
                ${item.name}
              </label>
            `,
          )}
          <div class="row">
            <button
              class="primary"
              data-action="merge-submit"
              ?disabled=${this._busy}
              @click=${this._merge}
            >
              ${this._t("quick.merge_submit")}
            </button>
            <button data-action="merge-cancel" @click=${() => (this._merging = false)}>
              ${this._t("quick.merge_cancel")}
            </button>
          </div>
        </div>
      `;
    }
    if (selected.length < 2) return nothing;
    return html`<button data-action="merge" ?disabled=${this._busy} @click=${this._startMerge}>
      ${this._t("quick.merge", { count: selected.length })}
    </button>`;
  }

  private _renderAddForm() {
    return html`
      <form @submit=${this._add}>
        <div class="row">
          <input
            type="text"
            aria-label=${this._t("quick.new_label")}
            placeholder=${this._t("quick.new_placeholder")}
            .value=${this._newName}
            ?disabled=${this._busy}
            @input=${(event: Event) => (this._newName = (event.target as HTMLInputElement).value)}
          />
          <button type="submit" data-action="new" ?disabled=${this._busy || !this._newName.trim()}>
            ${this._t("quick.new_add")}
          </button>
        </div>
      </form>
    `;
  }
}

if (!customElements.get("handla-quick-manage")) {
  customElements.define("handla-quick-manage", HandlaQuickManage);
}
