declare global {
  interface Window {
    plausible?: (event: string, options?: { props?: Record<string, string | number | boolean> }) => void;
  }
}

let injected = false;

/**
 * Landing-page-only pageview tracking (ADR 0007: "На лендинге — Plausible/Я.Метрика",
 * separate from the authenticated POST /events funnel). No-ops when unconfigured —
 * no real account exists in this environment; same convention as the backend's
 * Sentry/Langfuse no-op-when-unset pattern.
 */
export function initAnalytics(): void {
  if (injected) return;
  const domain = import.meta.env.VITE_PLAUSIBLE_DOMAIN as string | undefined;
  if (!domain) return;

  injected = true;
  const script = document.createElement("script");
  script.defer = true;
  script.dataset.domain = domain;
  script.src = "https://plausible.io/js/script.js";
  document.head.appendChild(script);
}

export function trackPlausibleEvent(name: string): void {
  window.plausible?.(name);
}
