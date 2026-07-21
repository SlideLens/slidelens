import { describe, expect, it, vi, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { apiClient } from "@/api/client";
import type { ReviewOut } from "@/api/schemas";
import { listPollInterval, statusPollInterval, useReviewPolling } from "./useReviewPolling";

const base: ReviewOut = {
  id: "1",
  status: "done",
  score: 80,
  deck_filename: "a.pptx",
  n_slides: 5,
  has_audio: false,
  has_data: false,
  created_at: "2026-01-01T00:00:00Z",
  finished_at: "2026-01-01T00:01:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("listPollInterval", () => {
  it("returns false when every review is terminal", () => {
    expect(listPollInterval([{ ...base, status: "done" }, { ...base, status: "failed" }])).toBe(
      false,
    );
  });

  it("returns the interval when any review is queued or processing", () => {
    expect(listPollInterval([{ ...base, status: "done" }, { ...base, status: "queued" }])).toBe(
      5000,
    );
    expect(listPollInterval([{ ...base, status: "processing" }])).toBe(5000);
  });

  it("returns false for undefined/empty data", () => {
    expect(listPollInterval(undefined)).toBe(false);
    expect(listPollInterval([])).toBe(false);
  });
});

describe("statusPollInterval", () => {
  it("polls while queued or processing, stops when done or failed", () => {
    expect(statusPollInterval("queued")).toBe(5000);
    expect(statusPollInterval("processing")).toBe(5000);
    expect(statusPollInterval("done")).toBe(false);
    expect(statusPollInterval("failed")).toBe(false);
    expect(statusPollInterval(undefined)).toBe(false);
  });
});

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useReviewPolling", () => {
  it("fetches the reviews list", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce([base]);
    const { result } = renderHook(() => useReviewPolling(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual([base]));
  });
});
