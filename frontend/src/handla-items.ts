import { LitElement, css, html, nothing } from "lit";
import { AddQueue, type QueuedAdd } from "./add-queue";
import { clearTicked, errorMessage, getCategories, removeItem, setCategory, tickItem } from "./api";
import { UNSPECIFIED_GROUP, buildSections, groupLabel, type CategoryData } from "./categories";
import "./handla-categorize";
import { localize, type TranslationKey } from "./i18n";
import "./handla-quick-manage";
import { availabilityOf, orderItems, readQuickItems, subscribeItems, type TodoItem } from "./items";
import type { ListInfo } from "./lists";
import { loadGroupByCategory, saveGroupByCategory } from "./storage";
import type { HomeAssistant } from "./types";

/** Wait this long after a change before reading the categories again (changes come in bursts). */
const CATEGORY_FETCH_DELAY_MS = 300;

/**
 * The items of one list: add (Enter adds and the field keeps focus), quick-add buttons,
 * tick, remove and clear ticked. Added items are queued, so fast typing never loses one.
 */
export class HandlaItems extends LitElement {
  static override properties = {
    hass: { attribute: false },
    list: { attribute: false },
    locked: { type: Boolean },
    _items: { state: true },
    _loadError: { state: true },
    _text: { state: true },
    _busyUids: { state: true },
    _clearing: { state: true },
    _actionError: { state: true },
    _managing: { state: true },
    _categories: { state: true },
    _categoryError: { state: true },
    _groupBy: { state: true },
    _pickerFor: { state: true },
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
    label.group-toggle {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 44px;
    }
    label.group-toggle input {
      width: 24px;
      height: 24px;
    }
    li.group {
      margin-top: 16px;
      padding-bottom: 4px;
      font-size: 0.8rem;
      font-weight: 500;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--secondary-text-color, #727272);
      border-bottom: 2px solid var(--divider-color, #cfcfcf);
    }
    li.picker {
      padding: 4px 0 8px 48px;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    li.picker select {
      min-height: 44px;
      max-width: 100%;
      /* 16px stops iOS from zooming in when the field gets focus */
      font-size: 16px;
      color: inherit;
      background: var(--secondary-background-color, #f4f4f5);
      border: 1px solid var(--divider-color, #cfcfcf);
      border-radius: 8px;
    }
  `;

  declare hass?: HomeAssistant;
  declare list?: ListInfo | null;
  /** True while a list is being created or deleted: nothing may change then. */
  declare locked: boolean;
  declare _items: TodoItem[] | null;
  declare _loadError: string | null;
  declare _text: string;
  declare _busyUids: ReadonlySet<string>;
  declare _clearing: boolean;
  declare _actionError: string | null;
  declare _managing: boolean;
  /** Store groups and each item's group; null until read (the list then shows flat). */
  declare _categories: CategoryData | null;
  declare _categoryError: string | null;
  declare _groupBy: boolean;
  /** The item whose category picker is open. */
  declare _pickerFor: string | null;

  private _subscribedFor: string | null = null;
  private _stop: (() => void) | undefined;
  private _generation = 0;
  private _categoryGeneration = 0;
  private _categoryTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly _adds = new AddQueue(
    () => this.hass,
    () => this.requestUpdate(),
  );

  constructor() {
    super();
    this.locked = false;
    this._managing = false;
    this._categories = null;
    this._categoryError = null;
    this._groupBy = loadGroupByCategory();
    this._pickerFor = null;
    this._items = null;
    this._loadError = null;
    this._text = "";
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
    this._stopCategories();
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
    this._stopCategories();
    this._subscribedFor = wanted;
    this._items = null;
    this._loadError = null;
    this._categories = null;
    this._categoryError = null;
    this._pickerFor = null;
    if (wanted && this.hass) this._startSubscription(this.hass, wanted);
  }

  private _startSubscription(hass: HomeAssistant, entityId: string): void {
    const generation = ++this._generation;
    subscribeItems(hass, entityId, (items) => {
      if (generation !== this._generation) return;
      this._items = items;
      this._loadError = null;
      this._scheduleCategories();
    })
      .then((stop) => {
        if (generation === this._generation) this._stop = stop;
        else stop();
      })
      .catch((err: unknown) => {
        if (generation === this._generation)
          this._loadError = errorMessage(err, this.hass?.language);
      });
  }

  private _stopSubscription(): void {
    this._generation += 1;
    this._stop?.();
    this._stop = undefined;
  }

  // --- categories ----------------------------------------------------------

  /** Read the categories soon: the subscription does not carry them. */
  private _scheduleCategories(delay = CATEGORY_FETCH_DELAY_MS): void {
    clearTimeout(this._categoryTimer);
    this._categoryTimer = setTimeout(() => void this._fetchCategories(), delay);
  }

  private async _fetchCategories(): Promise<void> {
    const { hass } = this;
    const entityId = this._subscribedFor;
    if (!hass || !entityId) return;
    const generation = ++this._categoryGeneration;
    try {
      const data = await getCategories(hass, entityId);
      if (generation !== this._categoryGeneration) return;
      this._categories = data;
      this._categoryError = null;
    } catch (err) {
      if (generation === this._categoryGeneration) {
        this._categoryError = errorMessage(err, hass.language);
      }
    }
  }

  private _stopCategories(): void {
    this._categoryGeneration += 1;
    clearTimeout(this._categoryTimer);
  }

  private _toggleGroupBy(enabled: boolean): void {
    this._groupBy = enabled;
    saveGroupByCategory(enabled);
  }

  /** Optimistic: show the new group at once, put the old one back if ICA refuses. */
  private async _changeCategory(item: TodoItem, groupId: number): Promise<void> {
    const { hass, list } = this;
    const before = this._categories;
    this._pickerFor = null;
    if (!hass || !list || !before || this.locked) return;
    this._categories = { ...before, groupOf: { ...before.groupOf, [item.uid]: groupId } };
    this._actionError = null;
    let failure: string | null = null;
    try {
      const result = await setCategory(hass, list.entityId, [{ uid: item.uid, groupId }]);
      if (!result.updated.includes(item.uid)) failure = this._t("categorize.row_missing");
    } catch (err) {
      failure = errorMessage(err, hass.language);
    }
    if (failure === null) return;
    this._categories = this._categories
      ? {
          ...this._categories,
          groupOf: {
            ...this._categories.groupOf,
            [item.uid]: before.groupOf[item.uid] ?? UNSPECIFIED_GROUP,
          },
        }
      : this._categories;
    this._actionError = this._t("categories.failed", { message: failure });
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
    this._adds.enqueue(text, entityId);
    this._focusInput();
  }

  private _quickAdd(name: string): void {
    const entityId = this.list?.entityId;
    if (entityId && this._canAdd) this._adds.enqueue(name, entityId);
  }

  // --- tick, remove, clear -------------------------------------------------

  private async _rowAction(uid: string, action: () => Promise<void>): Promise<void> {
    if (this._busyUids.has(uid)) return;
    this._busyUids = new Set(this._busyUids).add(uid);
    this._actionError = null;
    try {
      await action();
    } catch (err) {
      this._actionError = errorMessage(err, this.hass?.language);
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
      this._actionError = errorMessage(err, this.hass?.language);
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
      ${available ? this._renderCategoryTools(list) : nothing}
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
    if (this._managing) {
      return html`<handla-quick-manage
        .hass=${this.hass}
        @close=${() => (this._managing = false)}
      ></handla-quick-manage>`;
    }
    const quick = readQuickItems(this.hass);
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
        <button class="chip manage" data-action="manage" @click=${() => (this._managing = true)}>
          <ha-icon icon="mdi:pencil"></ha-icon><span>${this._t("quick.manage")}</span>
        </button>
      </div>
    `;
  }

  private _renderNotices() {
    return html`
      ${
        this._adds.duplicate
          ? html`
              <div class="notice" role="alertdialog" data-testid="duplicate">
                ${this._t("duplicate.prompt", { item: this._adds.duplicate.text })}
                <div class="row">
                  <button
                    class="primary"
                    data-action="duplicate-add"
                    @click=${() => void this._adds.confirmDuplicate()}
                  >
                    ${this._t("duplicate.add")}
                  </button>
                  <button data-action="duplicate-skip" @click=${() => this._adds.skipDuplicate()}>
                    ${this._t("duplicate.skip")}
                  </button>
                </div>
              </div>
            `
          : nothing
      }
      ${
        this._adds.failure
          ? html`
              <div class="notice error" role="alert" data-testid="add-failed">
                ${this._t("add.failed", {
                  item: this._adds.failure.text,
                  message: this._adds.failure.message,
                })}
                <div class="row">
                  <button
                    class="primary"
                    data-action="add-retry"
                    @click=${() => this._adds.retry()}
                  >
                    ${this._t("add.retry")}
                  </button>
                  <button data-action="add-skip" @click=${() => this._adds.skipFailed()}>
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

  private _renderCategoryTools(list: ListInfo) {
    return html`
      <label class="group-toggle">
        <input
          type="checkbox"
          data-action="group-by"
          .checked=${this._groupBy}
          @change=${(event: Event) =>
            this._toggleGroupBy((event.target as HTMLInputElement).checked)}
        />
        ${this._t("categories.group_by")}
      </label>
      ${
        this._categoryError
          ? html`<div class="notice error" role="alert" data-testid="categories-failed">
              ${this._t("categories.load_error", { message: this._categoryError })}
            </div>`
          : nothing
      }
      <handla-categorize
        .hass=${this.hass}
        .list=${list}
        .data=${this._categories}
        .locked=${this.locked}
        @categories-changed=${() => void this._fetchCategories()}
      ></handla-categorize>
    `;
  }

  private _renderItems(list: ListInfo) {
    if (this._loadError) {
      return html`<div class="notice error" role="alert" data-testid="load-failed">
        ${this._t("items.load_error", { message: this._loadError })}
      </div>`;
    }
    const pending = this._adds.items.filter((entry) => entry.entityId === list.entityId);
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
        ${this._renderOpenRows(items.filter((item) => !item.completed))}
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

  private _renderOpenRows(open: TodoItem[]) {
    const data = this._categories;
    if (!this._groupBy || !data) return open.map((item) => this._renderRow(item));
    return buildSections(open, data).map(
      (section) => html`
        <li class="group" role="presentation" data-group=${section.group.id}>
          ${groupLabel(this.hass?.language, section.group)}
        </li>
        ${section.items.map((item) => this._renderRow(item))}
      `,
    );
  }

  private _renderPicker(item: TodoItem) {
    const data = this._categories;
    if (!data || this._pickerFor !== item.uid) return nothing;
    const current = data.groupOf[item.uid] ?? UNSPECIFIED_GROUP;
    return html`
      <li class="picker" data-picker=${item.uid}>
        <select
          aria-label=${this._t("categories.pick", { item: item.summary })}
          @change=${(event: Event) =>
            void this._changeCategory(item, Number((event.target as HTMLSelectElement).value))}
        >
          ${data.groups.map(
            (group) => html`
              <option value=${group.id} ?selected=${group.id === current}>
                ${groupLabel(this.hass?.language, group)}
              </option>
            `,
          )}
        </select>
      </li>
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
        ${
          this._categories && !item.completed
            ? html`<button
                class="icon-button"
                data-action="category"
                aria-label=${this._t("categories.change", { item: item.summary })}
                aria-expanded=${this._pickerFor === item.uid ? "true" : "false"}
                ?disabled=${busy}
                @click=${() => (this._pickerFor = this._pickerFor === item.uid ? null : item.uid)}
              >
                <ha-icon icon="mdi:tag-outline"></ha-icon>
              </button>`
            : nothing
        }
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
      ${this._renderPicker(item)}
    `;
  }
}

if (!customElements.get("handla-items")) {
  customElements.define("handla-items", HandlaItems);
}
