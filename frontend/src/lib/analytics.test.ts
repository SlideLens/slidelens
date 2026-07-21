import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.resetModules();
  document.head.innerHTML = "";
});

afterEach(() => {
  vi.unstubAllEnvs();
  delete window.plausible;
});

describe("initAnalytics", () => {
  it("injects nothing when VITE_PLAUSIBLE_DOMAIN is unset", async () => {
    vi.stubEnv("VITE_PLAUSIBLE_DOMAIN", "");
    const { initAnalytics } = await import("./analytics");
    initAnalytics();
    expect(document.querySelector("script[data-domain]")).toBeNull();
  });

  it("injects the script exactly once, even across repeated calls", async () => {
    vi.stubEnv("VITE_PLAUSIBLE_DOMAIN", "example.com");
    const { initAnalytics } = await import("./analytics");
    initAnalytics();
    initAnalytics();
    expect(document.querySelectorAll('script[data-domain="example.com"]')).toHaveLength(1);
  });
});

describe("trackPlausibleEvent", () => {
  it("calls window.plausible when present", async () => {
    const { trackPlausibleEvent } = await import("./analytics");
    const plausible = vi.fn();
    window.plausible = plausible;
    trackPlausibleEvent("cta_click");
    expect(plausible).toHaveBeenCalledWith("cta_click");
  });

  it("does not throw when window.plausible is absent", async () => {
    const { trackPlausibleEvent } = await import("./analytics");
    expect(() => trackPlausibleEvent("cta_click")).not.toThrow();
  });
});
