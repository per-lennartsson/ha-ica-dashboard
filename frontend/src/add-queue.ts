/** The items a user has entered that have not reached the list yet, added one at a time. */

import { addItem, errorMessage } from "./api";
import type { HomeAssistant } from "./types";

/** An item the user has entered that has not reached the list yet. */
export interface QueuedAdd {
  text: string;
  entityId: string;
}

export interface AddFailure {
  text: string;
  message: string;
}

/**
 * Adds queued items in order, so fast typing never loses one. It stops at the first item
 * that needs an answer from the user: a duplicate to confirm, or a failure to retry or skip.
 */
export class AddQueue {
  items: QueuedAdd[] = [];
  /** The item at the head of the queue that already exists on the list. */
  duplicate: { text: string } | null = null;
  /** The item at the head of the queue that could not be added. */
  failure: AddFailure | null = null;

  private processing = false;

  /**
   * @param getHass the current connection to Home Assistant (it changes over time)
   * @param changed called after every change, so the owner can re-render
   */
  constructor(
    private readonly getHass: () => HomeAssistant | undefined,
    private readonly changed: () => void,
  ) {}

  enqueue(text: string, entityId: string): void {
    this.items = [...this.items, { text, entityId }];
    this.changed();
    void this.process();
  }

  /** Add the duplicate anyway, then carry on with the rest of the queue. */
  async confirmDuplicate(): Promise<void> {
    if (this.processing) return;
    this.duplicate = null;
    this.changed();
    this.processing = true;
    try {
      await this.attempt(true);
    } finally {
      this.processing = false;
    }
    void this.process();
  }

  skipDuplicate(): void {
    this.items = this.items.slice(1);
    this.duplicate = null;
    this.changed();
    void this.process();
  }

  retry(): void {
    this.failure = null;
    this.changed();
    void this.process();
  }

  skipFailed(): void {
    this.items = this.items.slice(1);
    this.failure = null;
    this.changed();
    void this.process();
  }

  /** Adds queued items one at a time; stops to ask about a duplicate or after a failure. */
  private async process(): Promise<void> {
    if (this.processing) return;
    this.processing = true;
    try {
      while (this.items.length > 0 && this.duplicate === null && this.failure === null) {
        await this.attempt(false);
      }
    } finally {
      this.processing = false;
    }
  }

  private async attempt(confirmDuplicate: boolean): Promise<void> {
    const head = this.items[0];
    const hass = this.getHass();
    if (!head || !hass) {
      this.items = [];
      this.changed();
      return;
    }
    try {
      const result = await addItem(hass, head.entityId, head.text, confirmDuplicate);
      if (result.added) this.items = this.items.slice(1);
      else if (result.duplicate) this.duplicate = { text: head.text };
      else this.failure = { text: head.text, message: errorMessage(null, hass.language) };
    } catch (err) {
      this.failure = { text: head.text, message: errorMessage(err, hass.language) };
    }
    this.changed();
  }
}
