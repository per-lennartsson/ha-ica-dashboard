/** Navigation inside Home Assistant's frontend without a page reload. */

/** True for dashboard paths such as /lovelace/inkop or /dashboard-inkop/start. */
export function isDashboardPath(path: unknown): path is string {
  return typeof path === "string" && path.startsWith("/") && !path.startsWith("//");
}

/**
 * Opens a dashboard path the way Home Assistant's own cards do: update the address
 * and tell the frontend's router about it.
 */
export function navigate(path: string): void {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
}
