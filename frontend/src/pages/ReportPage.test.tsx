import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { apiClient } from "@/api/client";
import type { ReviewOut } from "@/api/schemas";
import ReportPage from "./ReportPage";

function renderAt(reviewId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/reviews/${reviewId}`]}>
        <Routes>
          <Route path="/reviews/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const baseReview: ReviewOut = {
  id: "r1",
  status: "queued",
  deck_filename: "deck.pptx",
  has_audio: false,
  has_data: false,
  created_at: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ReportPage", () => {
  it("shows the processing view while queued/processing, without fetching the report", async () => {
    const requestSpy = vi
      .spyOn(apiClient, "request")
      .mockResolvedValueOnce({ ...baseReview, status: "processing" });
    renderAt("r1");

    expect(await screen.findByText("SlideLens изучает вашу Деку…")).toBeInTheDocument();
    expect(requestSpy).not.toHaveBeenCalledWith("/reviews/r1/report");
  });

  it("shows the real fail_reason when failed", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      ...baseReview,
      status: "failed",
      fail_reason: "Файл повреждён",
    });
    renderAt("r1");
    expect(await screen.findByText("Файл повреждён")).toBeInTheDocument();
  });

  it("fetches and renders the report when done", async () => {
    vi.spyOn(apiClient, "request")
      .mockResolvedValueOnce({ ...baseReview, status: "done", score: 72 })
      .mockResolvedValueOnce({
        review_id: "r1",
        score: 72,
        n_slides: 5,
        findings: [],
        auto_fixed_count: 0,
      });
    renderAt("r1");

    await waitFor(() => expect(screen.getByText("Серьёзных проблем не нашли 🎉")).toBeInTheDocument());
  });
});
