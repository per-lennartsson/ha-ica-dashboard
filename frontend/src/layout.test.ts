import { LitElement, html } from "lit";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WideLayout } from "./layout";

class LayoutProbe extends LitElement {
  readonly layout = new WideLayout(this, 600);
  renders = 0;
  override render() {
    this.renders += 1;
    return html`${this.layout.wide ? "wide" : "narrow"}`;
  }
}
customElements.define("layout-probe", LayoutProbe);

type Callback = (entries: Array<{ contentRect: { width: number } }>) => void;

function stubResizeObserver() {
  const state: { callback: Callback | null; disconnected: boolean } = {
    callback: null,
    disconnected: false,
  };
  vi.stubGlobal(
    "ResizeObserver",
    class {
      constructor(callback: Callback) {
        state.callback = callback;
      }
      observe(): void {}
      disconnect(): void {
        state.disconnected = true;
      }
    },
  );
  return state;
}

async function mount(): Promise<LayoutProbe> {
  const probe = document.createElement("layout-probe") as LayoutProbe;
  document.body.append(probe);
  await probe.updateComplete;
  return probe;
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

describe("WideLayout", () => {
  it("stays narrow when ResizeObserver is missing", async () => {
    vi.stubGlobal("ResizeObserver", undefined);
    const probe = await mount();
    expect(probe.layout.wide).toBe(false);
  });

  it("switches to wide at the minimum width and back below it", async () => {
    const observer = stubResizeObserver();
    const probe = await mount();
    observer.callback?.([{ contentRect: { width: 599 } }]);
    await probe.updateComplete;
    expect(probe.layout.wide).toBe(false);
    observer.callback?.([{ contentRect: { width: 600 } }]);
    await probe.updateComplete;
    expect(probe.layout.wide).toBe(true);
    expect(probe.shadowRoot?.textContent).toContain("wide");
    observer.callback?.([{ contentRect: { width: 300 } }]);
    await probe.updateComplete;
    expect(probe.layout.wide).toBe(false);
  });

  it("does not render again while the layout stays the same", async () => {
    const observer = stubResizeObserver();
    const probe = await mount();
    const before = probe.renders;
    observer.callback?.([{ contentRect: { width: 100 } }]);
    observer.callback?.([{ contentRect: { width: 200 } }]);
    await probe.updateComplete;
    expect(probe.renders).toBe(before);
  });

  it("stops observing when the element is removed", async () => {
    const observer = stubResizeObserver();
    const probe = await mount();
    probe.remove();
    expect(observer.disconnected).toBe(true);
  });
});
