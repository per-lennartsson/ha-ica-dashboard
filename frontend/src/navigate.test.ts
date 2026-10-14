import { afterEach, describe, expect, it, vi } from "vitest";
import { isDashboardPath, navigate } from "./navigate";

afterEach(() => {
  window.history.replaceState(null, "", "/");
  vi.restoreAllMocks();
});

describe("isDashboardPath", () => {
  it.each(["/lovelace/inkop", "/dashboard-inkop/start", "/"])("accepts %s", (path) => {
    expect(isDashboardPath(path)).toBe(true);
  });

  it.each(["lovelace/inkop", "", "//evil.example/path", "https://example.com", undefined, null, 5])(
    "rejects %j",
    (path) => {
      expect(isDashboardPath(path)).toBe(false);
    },
  );
});

describe("navigate", () => {
  it("changes the address and tells Home Assistant's router", () => {
    const events: CustomEvent[] = [];
    window.addEventListener("location-changed", (event) => events.push(event as CustomEvent), {
      once: true,
    });

    navigate("/lovelace/inkop");

    expect(window.location.pathname).toBe("/lovelace/inkop");
    expect(events).toHaveLength(1);
    expect(events[0]?.detail).toEqual({ replace: false });
  });
});
