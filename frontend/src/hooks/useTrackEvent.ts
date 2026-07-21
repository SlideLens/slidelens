import { useCallback } from "react";
import { apiClient } from "@/api/client";

/** Fire-and-forget POST /events — analytics must never block or error the UI. */
export function useTrackEvent(): (name: string, properties?: Record<string, unknown>) => void {
  return useCallback((name: string, properties?: Record<string, unknown>) => {
    apiClient
      .request("/events", { method: "POST", body: [{ name, properties }] })
      .catch(() => {
        // best-effort — a dropped analytics event is not a user-facing failure
      });
  }, []);
}
