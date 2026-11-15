import type { ReactiveController, ReactiveControllerHost } from "lit";

type Host = ReactiveControllerHost & HTMLElement;

/**
 * Tells a component whether its own element is wide enough for the wide layout, and asks it
 * to render again when that changes. Rendering a different template (not hiding one with CSS)
 * keeps the tab order and the reading order right in both layouts. Without `ResizeObserver`
 * (old browsers, jsdom) the component stays in the narrow layout.
 */
export class WideLayout implements ReactiveController {
  /** True while the host is at least `minWidth` pixels wide. */
  wide = false;

  private readonly _host: Host;
  private readonly _minWidth: number;
  private _observer: ResizeObserver | undefined;

  constructor(host: Host, minWidth: number) {
    this._host = host;
    this._minWidth = minWidth;
    host.addController(this);
  }

  hostConnected(): void {
    if (typeof ResizeObserver === "undefined") return;
    this._observer = new ResizeObserver((entries) => {
      const entry = entries[entries.length - 1];
      if (entry) this.setWidth(entry.contentRect.width);
    });
    this._observer.observe(this._host);
  }

  hostDisconnected(): void {
    this._observer?.disconnect();
    this._observer = undefined;
  }

  /** Feed a measured width; renders again only when the layout changes. */
  setWidth(width: number): void {
    const wide = width >= this._minWidth;
    if (wide === this.wide) return;
    this.wide = wide;
    this._host.requestUpdate();
  }
}
