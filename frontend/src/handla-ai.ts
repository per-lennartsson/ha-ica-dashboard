import { LitElement, css, html, nothing } from "lit";
import { MAX_TEXT_LENGTH, isAiReady, type Suggestion } from "./ai";
import { addItem, errorMessage, extractItems } from "./api";
import { localize, type TranslationKey } from "./i18n";
import { availabilityOf } from "./items";
import type { ListInfo } from "./lists";
import type { HomeAssistant } from "./types";

type Phase = "closed" | "paste" | "reading" | "review" | "adding";

/** One suggestion in the review: editable, can be ticked off, may have failed to add. */
interface Row {
  id: number;
  text: string;
  selected: boolean;
  existing: string | null;
  error: string | null;
}

/**
 * Optional AI helper: paste a text, review the suggested items, add the chosen ones.
 * Renders nothing unless the integration reports AI as ready, so with AI off the card
 * looks exactly as it does without this element.
 */
export class HandlaAi extends LitElement {
  static override properties = {
    hass: { attribute: false },
    list: { attribute: false },
    locked: { type: Boolean },
    _phase: { state: true },
    _text: { state: true },
    _rows: { state: true },
    _error: { state: true },
    _done: { state: true },
  };

  static override styles = css`
    :host {
      display: block;
      margin-top: 16px;
    }
    p {
      margin: 8px 0;
    }
    .muted {
      color: var(--secondary-text-color, #727272);
    }
    .panel {
      padding: 12px;
      border: 1px solid var(--divider-color, #cfcfcf);
      border-radius: 8px;
    }
    textarea,
    input[type="text"] {
      width: 100%;
      box-sizing: border-box;
      padding: 8px 12px;
      /* 16px stops iOS from zooming in when the field gets focus */
      font-size: 16px;
      font-family: inherit;
      color: inherit;
      background: var(--secondary-background-color, #f4f4f5);
      border: 1px solid var(--divider-color, #cfcfcf);
      border-radius: 8px;
    }
    textarea {
      min-height: 140px;
      resize: vertical;
    }
    input[type="text"] {
      min-height: 44px;
    }
    .row {
      display: flex;
      gap: 8px;
      margin-top: 8px;
      flex-wrap: wrap;
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
    input:disabled,
    textarea:disabled {
      opacity: 0.5;
      cursor: not-allowed;
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
    li.suggestion input[type="checkbox"] {
      flex: 0 0 auto;
      width: 24px;
      height: 24px;
      margin: 10px;
    }
    li.suggestion input[type="text"] {
      flex: 1 1 160px;
      min-width: 0;
    }
    li.suggestion .note {
      flex: 1 0 100%;
      margin-left: 44px;
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
  /** True while a list is being created or deleted: nothing may change then. */
  declare locked: boolean;
  declare _phase: Phase;
  declare _text: string;
  declare _rows: Row[];
  declare _error: string | null;
  declare _done: number | null;

  private _nextId = 0;

  constructor() {
    super();
    this.locked = false;
    this._phase = "closed";
    this._text = "";
    this._rows = [];
    this._error = null;
    this._done = null;
  }

  private _t(key: TranslationKey, params: Record<string, string | number> = {}): string {
    return localize(this.hass?.language, key, params);
  }

  private get _busy(): boolean {
    return this._phase === "reading" || this._phase === "adding";
  }

  private get _listReady(): boolean {
    const entityId = this.list?.entityId;
    return (
      !!this.hass && !!entityId && !this.locked && availabilityOf(this.hass, entityId) === "ok"
    );
  }

  // --- steps ---------------------------------------------------------------

  private _open(): void {
    this._done = null;
    this._error = null;
    this._phase = "paste";
  }

  private _close(): void {
    if (this._busy) return;
    this._phase = "closed";
    this._rows = [];
    this._error = null;
  }

  private _backToText(): void {
    if (this._busy) return;
    this._rows = [];
    this._error = null;
    this._phase = "paste";
  }

  private async _read(): Promise<void> {
    const { hass, list } = this;
    const text = this._text.trim();
    if (!hass || !list || !text || this._phase !== "paste") return;
    this._phase = "reading";
    this._error = null;
    try {
      const suggestions = await extractItems(hass, list.entityId, text);
      this._rows = suggestions.map((suggestion) => this._rowOf(suggestion));
      this._error = suggestions.length === 0 ? "none" : null;
      this._phase = suggestions.length === 0 ? "paste" : "review";
    } catch (err) {
      this._error = errorMessage(err);
      this._phase = "paste";
    }
  }

  private _rowOf(suggestion: Suggestion): Row {
    return {
      id: this._nextId++,
      text: suggestion.item,
      selected: suggestion.selected,
      existing: suggestion.onList ? suggestion.existing : null,
      error: null,
    };
  }

  private _update(id: number, change: Partial<Row>): void {
    this._rows = this._rows.map((row) => (row.id === id ? { ...row, ...change } : row));
  }

  private get _chosen(): Row[] {
    return this._rows.filter((row) => row.selected && row.text.trim() !== "");
  }

  /** Adds the chosen rows one at a time; rows that fail stay, with their message. */
  private async _addChosen(): Promise<void> {
    const { hass, list } = this;
    if (!hass || !list || this._phase !== "review" || !this._listReady) return;
    const chosen = this._chosen;
    if (chosen.length === 0) return;
    this._phase = "adding";
    this._rows = this._rows.map((row) => (row.error === null ? row : { ...row, error: null }));
    let added = 0;
    for (const row of chosen) {
      try {
        // The user has reviewed the item, so an existing one is added again on purpose
        const result = await addItem(hass, list.entityId, row.text.trim(), true);
        if (!result.added) throw new Error(errorMessage(null));
        this._rows = this._rows.filter((other) => other.id !== row.id);
        added += 1;
      } catch (err) {
        this._update(row.id, { error: errorMessage(err) });
      }
    }
    this._finishAdding(added);
  }

  private _finishAdding(added: number): void {
    const failed = this._rows.filter((row) => row.error !== null);
    if (failed.length === 0) {
      this._rows = [];
      this._text = "";
      this._done = added;
      this._phase = "closed";
      return;
    }
    // Failed rows stay chosen, with their message; rows left unticked stay as they are
    this._phase = "review";
  }

  // --- rendering -----------------------------------------------------------

  override render() {
    if (!isAiReady(this.hass) || !this.list) return nothing;
    return html`${this._renderDone()} ${this._renderPhase()}`;
  }

  private _renderDone() {
    return this._done === null || this._phase !== "closed"
      ? nothing
      : html`<p class="muted" role="status" data-testid="ai-done">
          ${this._t("ai.done", { count: this._done })}
        </p>`;
  }

  private _renderPhase() {
    switch (this._phase) {
      case "closed":
        return html`<button
          data-action="ai-open"
          ?disabled=${!this._listReady}
          @click=${() => this._open()}
        >
          ${this._t("ai.open")}
        </button>`;
      case "review":
      case "adding":
        return this._renderReview();
      default:
        return this._renderPaste();
    }
  }

  private _renderPaste() {
    const reading = this._phase === "reading";
    const text = this._text.trim();
    return html`
      <div class="panel" data-testid="ai-paste">
        <label for="ai-text">${this._t("ai.text_label")}</label>
        <textarea
          id="ai-text"
          maxlength=${MAX_TEXT_LENGTH}
          .value=${this._text}
          ?disabled=${reading}
          @input=${(event: Event) => (this._text = (event.target as HTMLTextAreaElement).value)}
        ></textarea>
        ${reading ? html`<p class="muted" role="status" data-testid="ai-reading">${this._t("ai.reading")}</p>` : nothing}
        ${this._renderPasteError()}
        <div class="row">
          <button
            class="primary"
            data-action="ai-find"
            ?disabled=${reading || text === "" || !this._listReady}
            @click=${() => void this._read()}
          >
            ${this._t("ai.find")}
          </button>
          <button data-action="ai-close" ?disabled=${reading} @click=${() => this._close()}>
            ${this._t("ai.close")}
          </button>
        </div>
      </div>
    `;
  }

  private _renderPasteError() {
    if (this._error === null) return nothing;
    return this._error === "none"
      ? html`<p class="muted" role="status" data-testid="ai-none">${this._t("ai.none_found")}</p>`
      : html`<div class="notice error" role="alert" data-testid="ai-error">
          ${this._t("ai.read_failed", { message: this._error })}
        </div>`;
  }

  private _renderReview() {
    const adding = this._phase === "adding";
    const failed = this._rows.filter((row) => row.error !== null).length;
    const count = this._chosen.length;
    return html`
      <div class="panel" data-testid="ai-review">
        <strong>${this._t("ai.review")}</strong>
        <p class="muted">${this._t("ai.review_hint")}</p>
        ${
          failed > 0 && !adding
            ? html`<div class="notice error" role="alert" data-testid="ai-retry">
                ${this._t("ai.retry_hint", { count: failed })}
              </div>`
            : nothing
        }
        <ul>
          ${this._rows.map((row) => this._renderRow(row, adding))}
        </ul>
        <div class="row">
          <button
            class="primary"
            data-action="ai-add"
            ?disabled=${adding || count === 0 || !this._listReady}
            @click=${() => void this._addChosen()}
          >
            ${adding ? this._t("ai.adding") : this._t("ai.add_selected", { count })}
          </button>
          <button data-action="ai-back" ?disabled=${adding} @click=${() => this._backToText()}>
            ${this._t("ai.back")}
          </button>
          <button data-action="ai-close" ?disabled=${adding} @click=${() => this._close()}>
            ${this._t("ai.close")}
          </button>
        </div>
      </div>
    `;
  }

  private _renderRow(row: Row, adding: boolean) {
    return html`
      <li class="suggestion" data-row=${row.id}>
        <input
          type="checkbox"
          aria-label=${this._t("ai.select", { item: row.text })}
          .checked=${row.selected}
          ?disabled=${adding}
          @change=${(event: Event) =>
            this._update(row.id, { selected: (event.target as HTMLInputElement).checked })}
        />
        <input
          type="text"
          aria-label=${this._t("ai.edit", { item: row.text })}
          autocomplete="off"
          .value=${row.text}
          ?disabled=${adding}
          @input=${(event: Event) =>
            this._update(row.id, { text: (event.target as HTMLInputElement).value })}
        />
        ${
          row.existing !== null
            ? html`<span class="note" data-note="on-list"
                >${this._t("ai.on_list", { existing: row.existing })}</span
              >`
            : nothing
        }
        ${
          row.error !== null
            ? html`<span class="note error" role="alert" data-note="failed"
                >${this._t("ai.row_failed", { message: row.error })}</span
              >`
            : nothing
        }
      </li>
    `;
  }
}

if (!customElements.get("handla-ai")) {
  customElements.define("handla-ai", HandlaAi);
}
