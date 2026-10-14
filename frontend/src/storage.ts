/**
 * Per-user UI state lives in this browser only (not in Home Assistant helpers, which
 * are shared by every user and device).
 */

const SELECTED_LIST_KEY = "inkop:selected-list";

/** The list this user last picked on this device (ICA offline id), if any. */
export function loadSelectedList(): string | null {
  try {
    return window.localStorage.getItem(SELECTED_LIST_KEY);
  } catch {
    return null; // storage can be blocked (private mode, policies)
  }
}

export function saveSelectedList(offlineId: string | null): void {
  try {
    if (offlineId === null) window.localStorage.removeItem(SELECTED_LIST_KEY);
    else window.localStorage.setItem(SELECTED_LIST_KEY, offlineId);
  } catch {
    // The choice is simply not remembered
  }
}
