import { LitElement, css, html, nothing } from "lit";
import { addItem, clearTicked, errorMessage, removeItem, tickItem } from "./api";
import { localize, type TranslationKey } from "./i18n";
import { availabilityOf, orderItems, readQuickItems, subscribeItems, type TodoItem } from "./items";
import type { ListInfo } from "./lists";
import type { HomeAssistant } from "./types";

/** An item the user has entered that has not reached the list yet. */
interface QueuedAdd {
  text: string;
  entityId: string;
}

/**
 * The items of one list: add (Enter adds and the field keeps focus), quick-add buttons,
 * tick, remove and clear ticked. Added items are queued, so fast typing never loses one.
 */
export class InkopItems extends LitElement {
  static override properties = {
    hass: { attribute: false },
    list: { attribute: false },
    locked: { type: Boolean },
    _items: { state: true },
    _loadError: { state: true },
    _text: { state: true },
    _queue: { state: true },
    _duplicate: { state: true },
    _addFailure: { state: true },
    _busyUids: { state: true },
    _clearing: { state: true },
    _actionError: { state: true },
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
    .row {
      display: flex;
      gap: 8px;
    }
    input[type="text"] {
      flex: 1 1 auto;
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
    button:disabled,
    input:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 12px 0;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 44px;
      padding: 0 14px;
      border-radius: 22px;
    }
    .chip ha-icon {
      --mdc-icon-size: 20px;
      color: var(--primary-color, #03a9f4);
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
    ul {
      list-style: none;
      margin: 8px 0 0;
      padding: 0;
    }
    li.item {
      display: flex;
      align-items: center;
      gap: 4px;
      min-height: 48px;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    li.item .text {
      flex: 1 1 auto;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    li.item.done .text {
      text-decoration: line-through;
      color: var(--secondary-text-color, #727272);
    }
    li.item.pending {
      color: var(--secondary-text-color, #727272);
      font-style: italic;
    }
    .icon-button {
      flex: 0 0 auto;
      width: 44px;
      min-width: 44px;
      padding: 0;
      background: none;
      border: none;
      font-size: 1.25rem;
      line-height: 1;
    }
    .box {
      display: inline-block;
      width: 22px;
      height: 22px;
      box-sizing: border-box;
      border: 2px solid var(--secondary-text-color, #727272);
      border-radius: 4px;
      line-height: 18px;
      font-size: 16px;
      text-align: center;
    }
    .done .box {
      color: var(--text-primary-color, white);
      background: var(--primary-color, #03a9f4);
      border-color: var(--primary-color, #03a9f4);
    }
    li.divider {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 20px;
      padding-bottom: 4px;
      font-size: 0.8rem;
      font-weight: 500;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--secondary-text-color, #727272);
    }
    li.divider::after {
      content: "";
      flex: 1 1 auto;
      border-top: 2px solid var(--divider-color, #cfcfcf);
    }
    .clear {
      margin-top: 12px;
    }
  `;

  declare hass?: HomeAssistant;
  declare list?: ListInfo | null;
  /** True while a list is being created or deleted: nothing may change then. */
  declare locked: boolean;
  declare _items: TodoItem[] | null;
  declare _loadError: string | null;
  declare _text: string;
  declare _queue: QueuedAdd[];
  declare _duplicate: { text: string } | null;
  declare _addFailure: { text: string; message: string } | null;
  declare _busyUids: ReadonlySet<string>;
  declare _clearing: boolean;
  declare _actionError: string | null;

  private _subscribedFor: string | null = null;
  private _stop: (() => void) | undefined;
  private _generation = 0;
  private _processing = false;

  constructor() {
    super();
    this.locked = false;
    this._items = null;
    this._loadError = null;
    this._text = "";
    this._queue = [];
    this._duplicate = null;
    this._addFailure = null;
    this._busyUids = new Set();
    this._clearing = false;
    this._actionError = null;
  }

  override connectedCallback(): void {
    super.connectedCallback();
    // Dashboards detach and re-attach cards when switching views: subscribe again
    this.requestUpdate();
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._stopSubscription();
    this._subscribedFor = null;
  }

  private _t(key: TranslationKey, params: Record<string, string | number> = {}): string {
    return localize(this.hass?.language, key, params);
  }

  // --- live items ----------------------------------------------------------

  override willUpdate(): void {
    const entityId = this.list?.entityId;
    const wanted =
      entityId && availabilityOf(this.hass, entityId) === "ok" && this.hass ? entityId : null;
    if (wanted === this._subscribedFor) return;
    this._stopSubscription();
    this._subscribedFor = wanted;
    this._items = null;
    this._loadError = null;
    if (wanted && this.hass) this._startSubscription(this.hass, wanted);
  }

  private _startSubscription(hass: HomeAssistant, entityId: string): void {
    const generation = ++this._generation;
    subscribeItems(hass, entityId, (items) => {
      if (generation !== this._generation) return;
      this._items = items;
      this._loadError = null;
    })
      .then((stop) => {
        if (generation === this._generation) this._stop = stop;
        else stop();
      })
      .catch((err: unknown) => {
        if (generation === this._generation) this._loadError = errorMessage(err);
      });
  }

  private _stopSubscription(): void {
    this._generation += 1;
    this._stop?.();
    this._stop = undefined;
  }

  // --- adding --------------------------------------------------------------

  private get _canAdd(): boolean {
    const entityId = this.list?.entityId;
    return (
      !!this.hass && !!entityId && !this.locked && availabilityOf(this.hass, entityId) === "ok"
    );
  }

  private _focusInput(): void {
    this.renderRoot.querySelector<HTMLInputElement>("input[type=text]")?.focus();
  }

  private _submit(event: Event): void {
    event.preventDefault();
    const text = this._text.trim();
    const entityId = this.list?.entityId;
    if (!text || !entityId || !this._canAdd) return;
    this._text = "";
    const field = this.renderRoot.querySelector<HTMLInputElement>("input[type=text]");
    if (field) field.value = "";
    this._enqueue(text, entityId);
    this._focusInput();
  }

  private _enqueue(text: string, entityId: string): void {
    this._queue = [...this._queue, { text, entityId }];
    void this._process();
  }

  private _quickAdd(name: string): void {
    const entityId = this.list?.entityId;
    if (entityId && this._canAdd) this._enqueue(name, entityId);
  }

  /** Adds queued items one at a time; stops to ask about a duplicate or after a failure. */
  private async _process(): Promise<void> {
    if (this._processing) return;
    this._processing = true;
    try {
      while (this._queue.length > 0 && this._duplicate === null && this._addFailure === null) {
        await this._attempt(false);
      }
    } finally {
      this._processing = false;
    }
  }

  private async _attempt(confirmDuplicate: boolean): Promise<void> {
    const head = this._queue[0];
    const hass = this.hass;
    if (!head || !hass) {
      this._queue = [];
      return;
    }
    try {
      const result = await addItem(hass, head.entityId, head.text, confirmDuplicate);
      if (result.added) this._queue = this._queue.slice(1);
      else if (result.duplicate) this._duplicate = { text: head.text };
      else this._addFailure = { text: head.text, message: errorMessage(null) };
    } catch (err) {
      this._addFailure = { text: head.text, message: errorMessage(err) };
    }
  }

  private async _confirmDuplicate(): Promise<void> {
    if (this._processing) return;
    this._duplicate = null;
    this._processing = true;
    try {
      await this._attempt(true);
    } finally {
      this._processing = false;
    }
    void this._process();
  }

  private _skipDuplicate(): void {
    this._queue = this._queue.slice(1);
    this._duplicate = null;
    void this._process();
  }

  private _retryAdd(): void {
    this._addFailure = null;
    void this._process();
  }

  private _skipFailedAdd(): void {
    this._queue = this._queue.slice(1);
    this._addFailure = null;
    void this._process();
  }

  // --- tick, remove, clear -------------------------------------------------

  private async _rowAction(uid: string, action: () => Promise<void>): Promise<void> {
    if (this._busyUids.has(uid)) return;
    this._busyUids = new Set(this._busyUids).add(uid);
    this._actionError = null;
    try {
      await action();
    } catch (err) {
      this._actionError = errorMessage(err);
    } finally {
      const rest = new Set(this._busyUids);
      rest.delete(uid);
      this._busyUids = rest;
    }
  }

  private _tick(item: TodoItem): Promise<void> {
    const { hass, list } = this;
    if (!hass || !list) return Promise.resolve();
    return this._rowAction(item.uid, () =>
      tickItem(hass, list.entityId, item.uid, !item.completed),
    );
  }

  private _remove(item: TodoItem): Promise<void> {
    const { hass, list } = this;
    if (!hass || !list) return Promise.resolve();
    return this._rowAction(item.uid, () => removeItem(hass, list.entityId, item.uid));
  }

  private async _clearTicked(): Promise<void> {
    const { hass, list } = this;
    if (!hass || !list || this._clearing) return;
    this._clearing = true;
    this._actionError = null;
    try {
      await clearTicked(hass, list.entityId);
    } catch (err) {
      this._actionError = errorMessage(err);
    } finally {
      this._clearing = false;
    }
  }

  // --- rendering -----------------------------------------------------------

  override render() {
    const list = this.list;
    if (!list) return nothing;
    const available = availabilityOf(this.hass, list.entityId) === "ok";
    return html`
      ${
        available
          ? nothing
          : html`<p class="muted" data-testid="unavailable">${this._t("items.unavailable")}</p>`
      }
      ${this._renderAddForm()} ${this._renderQuickItems()} ${this._renderNotices()}
      ${available ? this._renderItems(list) : nothing}
    `;
  }

  private _renderAddForm() {
    const canAdd = this._canAdd;
    return html`
      <form @submit=${(event: Event) => this._submit(event)}>
        <div class="row">
          <input
            type="text"
            aria-label=${this._t("items.add_label")}
            placeholder=${this._t("items.add_placeholder")}
            enterkeyhint="send"
            autocomplete="off"
            .value=${this._text}
            ?disabled=${!canAdd}
            @input=${(event: Event) => (this._text = (event.target as HTMLInputElement).value)}
          />
          <button type="submit" class="primary" data-action="add" ?disabled=${!canAdd}>
            ${this._t("items.add_button")}
          </button>
        </div>
      </form>
    `;
  }

  private _renderQuickItems() {
    const quick = readQuickItems(this.hass);
    if (quick.length === 0) return nothing;
    const canAdd = this._canAdd;
    return html`
      <div class="chips" role="group" aria-label=${this._t("quick.label")}>
        ${quick.map(
          (item) => html`
            <button
              class="chip"
              data-quick=${item.name}
              ?disabled=${!canAdd}
              @click=${() => this._quickAdd(item.name)}
            >
              <ha-icon icon=${item.icon}></ha-icon><span>${item.name}</span>
            </button>
          `,
        )}
      </div>
    `;
  }

  private _renderNotices() {
    return html`
      ${
        this._duplicate
          ? html`
              <div class="notice" role="alertdialog" data-testid="duplicate">
                ${this._t("duplicate.prompt", { item: this._duplicate.text })}
                <div class="row">
                  <button
                    class="primary"
                    data-action="duplicate-add"
                    @click=${() => void this._confirmDuplicate()}
                  >
                    ${this._t("duplicate.add")}
                  </button>
                  <button data-action="duplicate-skip" @click=${() => this._skipDuplicate()}>
                    ${this._t("duplicate.skip")}
                  </button>
                </div>
              </div>
            `
          : nothing
      }
      ${
        this._addFailure
          ? html`
              <div class="notice error" role="alert" data-testid="add-failed">
                ${this._t("add.failed", {
                  item: this._addFailure.text,
                  message: this._addFailure.message,
                })}
                <div class="row">
                  <button class="primary" data-action="add-retry" @click=${() => this._retryAdd()}>
                    ${this._t("add.retry")}
                  </button>
                  <button data-action="add-skip" @click=${() => this._skipFailedAdd()}>
                    ${this._t("add.skip")}
                  </button>
                </div>
              </div>
            `
          : nothing
      }
      ${
        this._actionError
          ? html`
              <div class="notice error" role="alert" data-testid="action-failed">
                ${this._t("action.failed", { message: this._actionError })}
                <div class="row">
                  <button data-action="dismiss" @click=${() => (this._actionError = null)}>
                    ${this._t("common.dismiss")}
                  </button>
                </div>
              </div>
            `
          : nothing
      }
    `;
  }

  private _renderItems(list: ListInfo) {
    if (this._loadError) {
      return html`<div class="notice error" role="alert" data-testid="load-failed">
        ${this._t("items.load_error", { message: this._loadError })}
      </div>`;
    }
    const pending = this._queue.filter((entry) => entry.entityId === list.entityId);
    if (this._items === null) {
      return pending.length === 0
        ? html`<p class="muted" data-testid="loading">${this._t("items.loading")}</p>`
        : this._renderRows([], pending);
    }
    const items = orderItems(this._items);
    if (items.length === 0 && pending.length === 0) {
      return html`<p class="muted" data-testid="empty">${this._t("items.empty")}</p>`;
    }
    return this._renderRows(items, pending);
  }

  private _renderRows(items: TodoItem[], pending: QueuedAdd[]) {
    const ticked = items.filter((item) => item.completed).length;
    return html`
      <ul data-testid="items">
        ${pending.map(
          (entry) => html`
            <li class="item pending" data-pending>
              <span class="text">${entry.text} <small>${this._t("items.adding")}</small></span>
            </li>
          `,
        )}
        ${items.filter((item) => !item.completed).map((item) => this._renderRow(item))}
        ${
          ticked > 0
            ? html`<li class="divider" role="separator" data-testid="ticked-divider">
                ${this._t("items.ticked", { count: ticked })}
              </li>`
            : nothing
        }
        ${items.filter((item) => item.completed).map((item) => this._renderRow(item))}
      </ul>
      ${
        ticked > 0
          ? html`
              <button
                class="clear"
                data-action="clear-ticked"
                ?disabled=${this._clearing || this.locked}
                @click=${() => void this._clearTicked()}
              >
                ${this._t("items.clear", { count: ticked })}
              </button>
            `
          : nothing
      }
    `;
  }

  private _renderRow(item: TodoItem) {
    const busy = this._busyUids.has(item.uid) || this._clearing || this.locked;
    return html`
      <li class="item ${item.completed ? "done" : ""}" data-uid=${item.uid}>
        <button
          class="icon-button"
          data-action="tick"
          aria-pressed=${item.completed ? "true" : "false"}
          aria-label=${this._t(item.completed ? "items.untick" : "items.tick", {
            item: item.summary,
          })}
          ?disabled=${busy}
          @click=${() => void this._tick(item)}
        >
          <span class="box">${item.completed ? "✓" : ""}</span>
        </button>
        <span class="text">${item.summary}</span>
        <button
          class="icon-button"
          data-action="remove"
          aria-label=${this._t("items.remove", { item: item.summary })}
          ?disabled=${busy}
          @click=${() => void this._remove(item)}
        >
          ×
        </button>
      </li>
    `;
  }
}

if (!customElements.get("inkop-items")) {
  customElements.define("inkop-items", InkopItems);
}
