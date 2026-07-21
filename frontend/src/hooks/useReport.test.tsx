import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { apiClient } from "@/api/client";
import { useReport } from "./useReport";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useReport", () => {
  it("does not fetch when not enabled", () => {
    const requestSpy = vi.spyOn(apiClient, "request");
    renderHook(() => useReport("r1", false), { wrapper });
    expect(requestSpy).not.toHaveBeenCalled();
  });

  it("fetches the report once enabled", async () => {
    const requestSpy = vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      review_id: "r1",
      score: 80,
      n_slides: 5,
      findings: [],
      auto_fixed_count: 0,
    });
    const { result } = renderHook(() => useReport("r1", true), { wrapper });
    await waitFor(() => expect(result.current.data?.review_id).toBe("r1"));
    expect(requestSpy).toHaveBeenCalledWith("/reviews/r1/report");
  });
});
