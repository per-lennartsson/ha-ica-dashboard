import { LitElement, css, html, nothing } from "lit";
import { isAiReady } from "./ai";
import { errorMessage, setCategory, suggestCategories } from "./api";
import { groupLabel, type CategoryData, type CategorySuggestion } from "./categories";
import { localize, type TranslationKey } from "./i18n";
import type { ListInfo } from "./lists";
import type { HomeAssistant } from "./types";

type Phase = "closed" | "reading" | "review" | "saving";

/** One suggestion in the review: can be ticked off, the group can be changed, may fail to save. */
interface Row {
  uid: string;
  name: string;
  current: number;
  group: number;
  selected: boolean;
  error: string | null;
}

/**
 * Optional AI helper: suggests store groups for the items on the list, lets the user review
 * them and saves the chosen ones. Renders nothing unless the integration reports AI as ready.
 */
export class HandlaCategorize extends LitElement {
  static override properties = {
    hass: { attribute: false },
    list: { attribute: false },
    data: { attribute: false },
    locked: { type: Boolean },
    _phase: { state: true },
    _includeAll: { state: true },
    _rows: { state: true },
    _error: { state: true },
    _note: { state: true },
  };

  static override styles = css`
    :host {
      display: block;
      margin-top: 12px;
    }
    .panel {
      padding: 12px;
      border: 1px solid var(--divider-color, #cfcfcf);
      border-radius: 8px;
    }
    .muted {
      color: var(--secondary-text-color, #727272);
    }
    .row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-top: 8px;
    }
    label.check {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 44px;
    }
    input[type="checkbox"] {
      width: 24px;
      height: 24px;
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
    button:disabled,
    select:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    select {
      min-height: 44px;
      max-width: 100%;
      /* 16px stops iOS from zooming in when the field gets focus */
      font-size: 16px;
      color: inherit;
      background: var(--secondary-background-color, #f4f4f5);
      border: 1px solid var(--divider-color, #cfcfcf);
      border-radius: 8px;
    }
    ul {
      list-style: none;
      margin: 8px 0 0;
      padding: 0;
    }
    li.suggestion {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 4px 8px;
      padding: 4px 0;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    li.suggestion .name {
      flex: 1 1 120px;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    li.suggestion .note {
      flex: 1 0 100%;
      margin-left: 36px;
      font-size: 0.85rem;
      color: var(--secondary-text-color, #727272);
    }
    li.suggestion .note.error {
      color: var(--error-color, #db4437);
    }
    .notice {
      margin: 8px 0;
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid var(--divider-color, #cfcfcf);
    }
    .notice.error {
      color: var(--error-color, #db4437);
      border-color: var(--error-color, #db4437);
    }
  `;

  declare hass?: HomeAssistant;
  declare list?: ListInfo | null;
  /** The groups and the current group of each item; the groups fill the pickers. */
  declare data?: CategoryData | null;
  /** True while a list is created or deleted: nothing may change then. */
  declare locked: boolean;
  declare _phase: Phase;
  declare _includeAll: boolean;
  declare _rows: Row[];
  declare _error: string | null;
  declare _note: string | null;

  /** Bumped on every start and close, so an answer that arrives late is ignored. */
  private _request = 0;

  constructor() {
    super();
    this.locked = false;
    this._phase = "closed";
    this._includeAll = false;
    this._rows = [];
    this._error = null;
    this._note = null;
  }

  private _t(key: TranslationKey, params: Record<string, string | number> = {}): string {
    return localize(this.hass?.language, key, params);
  }

  private _groupName(id: number): string {
    const group = this.data?.groups.find((entry) => entry.id === id);
    return group ? groupLabel(this.hass?.language, group) : String(id);
  }

  private get _busy(): boolean {
    return this._phase === "reading" || this._phase === "saving";
  }

  // --- asking ------------------------------------------------------------------

  private async _suggest(): Promise<void> {
    const { hass, list } = this;
    if (!hass || !list || this._busy || this.locked) return;
    const request = ++this._request;
    this._phase = "reading";
    this._error = null;
    this._note = null;
    try {
      const result = await suggestCategories(hass, list.entityId, this._includeAll);
      if (request !== this._request) return;
      this._rows = result.items.map((entry) => this._rowFor(entry));
      if (this._rows.length === 0) {
        this._note = this._t("categorize.none");
        this._phase = "closed";
        return;
      }
      this._note = result.truncated
        ? this._t("categorize.truncated", { count: result.asked })
        : null;
      this._phase = "review";
    } catch (err) {
      if (request !== this._request) return;
      this._error = this._t("categorize.failed", {
        message: errorMessage(err, hass.language),
      });
      this._phase = "closed";
    }
  }

  private _rowFor(entry: CategorySuggestion): Row {
    return {
      uid: entry.uid,
      name: entry.name,
      current: entry.current,
      group: entry.suggested,
      selected: true,
      error: null,
    };
  }

  private _close(): void {
    this._request += 1;
    this._phase = "closed";
    this._rows = [];
    this._error = null;
    this._note = null;
  }

  // --- reviewing and saving ----------------------------------------------------

  private _update(uid: string, change: Partial<Row>): void {
    this._rows = this._rows.map((row) => (row.uid === uid ? { ...row, ...change } : row));
  }

  private get _selected(): Row[] {
    return this._rows.filter((row) => row.selected);
  }

  private async _save(): Promise<void> {
    const { hass, list } = this;
    const chosen = this._selected;
    if (!hass || !list || this._busy || this.locked || chosen.length === 0) return;
    const request = ++this._request;
    this._phase = "saving";
    this._error = null;
    let saved: ReadonlySet<string> = new Set();
    let message: string | null = null;
    try {
      const result = await setCategory(
        hass,
        list.entityId,
        chosen.map((row) => ({ uid: row.uid, groupId: row.group })),
      );
      saved = new Set(result.updated);
    } catch (err) {
      message = errorMessage(err, hass.language);
    }
    if (request !== this._request) return;
    this._finishSave(chosen, saved, message);
  }

  private _finishSave(chosen: Row[], saved: ReadonlySet<string>, message: string | null): void {
    const asked = new Set(chosen.map((row) => row.uid));
    const rest = this._rows
      .filter((row) => !saved.has(row.uid))
      .map((row) =>
        asked.has(row.uid)
          ? {
              ...row,
              error:
                message === null
                  ? this._t("categorize.row_missing")
                  : this._t("categorize.row_failed", { message }),
            }
          : row,
      );
    this._rows = rest;
    if (saved.size > 0) {
      this.dispatchEvent(new CustomEvent("categories-changed", { bubbles: true, composed: true }));
    }
    if (rest.length === 0) {
      this._phase = "closed";
      this._note = this._t("categorize.done", { count: saved.size });
      return;
    }
    this._phase = "review";
    this._note = this._t("categorize.retry_hint", { count: rest.length });
  }

  // --- rendering ---------------------------------------------------------------

  override render() {
    if (!isAiReady(this.hass) || !this.list) return nothing;
    return html`
      ${this._phase === "closed" ? this._renderStart() : nothing}
      ${this._phase === "reading" ? this._renderReading() : nothing}
      ${this._phase === "review" || this._phase === "saving" ? this._renderReview() : nothing}
    `;
  }

  private _renderStart() {
    return html`
      ${this._renderMessages()}
      <div class="row">
        <button data-action="suggest" ?disabled=${this.locked} @click=${() => void this._suggest()}>
          ${this._t("categorize.open")}
        </button>
        <label class="check">
          <input
            type="checkbox"
            data-action="include-all"
            .checked=${this._includeAll}
            @change=${(event: Event) =>
              (this._includeAll = (event.target as HTMLInputElement).checked)}
          />
          ${this._t("categorize.include_all")}
        </label>
      </div>
    `;
  }

  private _renderReading() {
    return html`<p class="muted" data-testid="reading">${this._t("categorize.reading")}</p>`;
  }

  private _renderMessages() {
    return html`
      ${
        this._error
          ? html`<div class="notice error" role="alert" data-testid="error">${this._error}</div>`
          : nothing
      }
      ${this._note ? html`<p class="muted" data-testid="note">${this._note}</p>` : nothing}
    `;
  }

  private _renderReview() {
    const saving = this._phase === "saving";
    const chosen = this._selected.length;
    return html`
      <div class="panel" data-testid="review">
        <strong>${this._t("categorize.review")}</strong>
        ${this._renderMessages()}
        <ul>
          ${this._rows.map((row) => this._renderRow(row, saving))}
        </ul>
        <div class="row">
          <button
            class="primary"
            data-action="save"
            ?disabled=${saving || this.locked || chosen === 0}
            @click=${() => void this._save()}
          >
            ${saving ? this._t("categorize.saving") : this._t("categorize.save", { count: chosen })}
          </button>
          <button data-action="close" ?disabled=${saving} @click=${() => this._close()}>
            ${this._t("categorize.close")}
          </button>
        </div>
      </div>
    `;
  }

  private _renderRow(row: Row, saving: boolean) {
    return html`
      <li class="suggestion" data-uid=${row.uid}>
        <input
          type="checkbox"
          data-action="select"
          aria-label=${this._t("categorize.select", { item: row.name })}
          .checked=${row.selected}
          ?disabled=${saving}
          @change=${(event: Event) =>
            this._update(row.uid, { selected: (event.target as HTMLInputElement).checked })}
        />
        <span class="name">${row.name}</span>
        <select
          data-action="group"
          aria-label=${this._t("categorize.pick", { item: row.name })}
          ?disabled=${saving}
          @change=${(event: Event) =>
            this._update(row.uid, { group: Number((event.target as HTMLSelectElement).value) })}
        >
          ${(this.data?.groups ?? []).map(
            (group) => html`
              <option value=${group.id} ?selected=${group.id === row.group}>
                ${groupLabel(this.hass?.language, group)}
              </option>
            `,
          )}
        </select>
        <span class="note"
          >${this._t("categorize.from", { group: this._groupName(row.current) })}</span
        >
        ${row.error ? html`<span class="note error" role="alert">${row.error}</span>` : nothing}
      </li>
    `;
  }
}

if (!customElements.get("handla-categorize")) {
  customElements.define("handla-categorize", HandlaCategorize);
}
