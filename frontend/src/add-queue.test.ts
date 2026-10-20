import { describe, expect, it, vi } from "vitest";
import { AddQueue } from "./add-queue";
import type { HomeAssistant } from "./types";

type Answer = { added: boolean; duplicate: boolean };
const ADDED: Answer = { added: true, duplicate: false };
const DUPLICATE: Answer = { added: false, duplicate: true };
const NEITHER: Answer = { added: false, duplicate: false };

/** A queue whose add_item service answers with `answer(item, confirmDuplicate)`. */
function setup(answer: (item: string, confirm: boolean) => Answer | Error) {
  const callService = vi.fn(async (_domain, _service, data) => {
    const result = answer(String(data["item"]), data["confirm_duplicate"] === true);
    if (result instanceof Error) throw result;
    return { context: {}, response: { ...result, item: data["item"], duplicates: [] } };
  });
  const hass = { language: "en", states: {}, callService } as unknown as HomeAssistant;
  const changed = vi.fn();
  let current: HomeAssistant | undefined = hass;
  const queue = new AddQueue(() => current, changed);
  return {
    queue,
    callService,
    changed,
    dropHass: () => {
      current = undefined;
    },
  };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const items = (queue: AddQueue) => queue.items.map((entry) => entry.text);

describe("AddQueue", () => {
  it("adds items in the order they were entered", async () => {
    const { queue, callService } = setup(() => ADDED);
    queue.enqueue("mjölk", "todo.a");
    queue.enqueue("ägg", "todo.a");
    await settle();

    expect(callService.mock.calls.map((call) => call[2]["item"])).toEqual(["mjölk", "ägg"]);
    expect(queue.items).toEqual([]);
    expect(queue.duplicate).toBeNull();
    expect(queue.failure).toBeNull();
  });

  it("tells its owner about every change", async () => {
    const { queue, changed } = setup(() => ADDED);
    queue.enqueue("mjölk", "todo.a");
    await settle();
    expect(changed).toHaveBeenCalled();
  });

  describe("a duplicate", () => {
    it("stops the queue and keeps the rest waiting", async () => {
      const { queue, callService } = setup((item) => (item === "mjölk" ? DUPLICATE : ADDED));
      queue.enqueue("mjölk", "todo.a");
      queue.enqueue("ägg", "todo.a");
      await settle();

      expect(queue.duplicate).toEqual({ text: "mjölk" });
      expect(items(queue)).toEqual(["mjölk", "ägg"]);
      expect(callService).toHaveBeenCalledTimes(1);
    });

    it("is added when confirmed, then the queue goes on", async () => {
      const { queue, callService } = setup((item, confirm) =>
        item === "mjölk" && !confirm ? DUPLICATE : ADDED,
      );
      queue.enqueue("mjölk", "todo.a");
      queue.enqueue("ägg", "todo.a");
      await settle();
      await queue.confirmDuplicate();
      await settle();

      expect(callService.mock.calls.map((call) => call[2]["confirm_duplicate"])).toEqual([
        false,
        true,
        false,
      ]);
      expect(queue.items).toEqual([]);
      expect(queue.duplicate).toBeNull();
    });

    it("is dropped when skipped, then the queue goes on", async () => {
      const { queue } = setup((item) => (item === "mjölk" ? DUPLICATE : ADDED));
      queue.enqueue("mjölk", "todo.a");
      queue.enqueue("ägg", "todo.a");
      await settle();
      queue.skipDuplicate();
      await settle();

      expect(queue.items).toEqual([]);
      expect(queue.duplicate).toBeNull();
    });
  });

  describe("a failure", () => {
    it("stops the queue with the error message", async () => {
      const { queue } = setup((item) => (item === "mjölk" ? new Error("ICA is down") : ADDED));
      queue.enqueue("mjölk", "todo.a");
      queue.enqueue("ägg", "todo.a");
      await settle();

      expect(queue.failure).toEqual({ text: "mjölk", message: "ICA is down" });
      expect(items(queue)).toEqual(["mjölk", "ägg"]);
    });

    it("treats an answer that is neither added nor a duplicate as a failure", async () => {
      const { queue } = setup(() => NEITHER);
      queue.enqueue("mjölk", "todo.a");
      await settle();
      expect(queue.failure).toEqual({ text: "mjölk", message: "Unknown error" });
    });

    it("is tried again on retry", async () => {
      let failing = true;
      const { queue, callService } = setup(() => (failing ? new Error("down") : ADDED));
      queue.enqueue("mjölk", "todo.a");
      await settle();
      failing = false;
      queue.retry();
      await settle();

      expect(callService).toHaveBeenCalledTimes(2);
      expect(queue.items).toEqual([]);
      expect(queue.failure).toBeNull();
    });

    it("is dropped when skipped, then the queue goes on", async () => {
      const { queue } = setup((item) => (item === "mjölk" ? new Error("down") : ADDED));
      queue.enqueue("mjölk", "todo.a");
      queue.enqueue("ägg", "todo.a");
      await settle();
      queue.skipFailed();
      await settle();

      expect(queue.items).toEqual([]);
      expect(queue.failure).toBeNull();
    });
  });

  it("clears the queue when there is no connection to Home Assistant", async () => {
    const { queue, callService, dropHass } = setup(() => ADDED);
    dropHass();
    queue.enqueue("mjölk", "todo.a");
    await settle();

    expect(queue.items).toEqual([]);
    expect(callService).not.toHaveBeenCalled();
  });

  it("does not start a second run while one is going", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const callService = vi.fn(async (_d, _s, data) => {
      await gate;
      return { context: {}, response: { added: true, duplicate: false, item: data["item"] } };
    });
    const hass = { language: "en", states: {}, callService } as unknown as HomeAssistant;
    const queue = new AddQueue(
      () => hass,
      () => undefined,
    );
    queue.enqueue("mjölk", "todo.a");
    queue.enqueue("ägg", "todo.a");
    await settle();
    expect(callService).toHaveBeenCalledTimes(1);
    release();
    await settle();
    expect(callService).toHaveBeenCalledTimes(2);
  });
});
