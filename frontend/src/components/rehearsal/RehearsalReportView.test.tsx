import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { apiClient } from "@/api/client";
import type { RehearsalReportOut } from "@/api/schemas";
import { RehearsalReportView } from "./RehearsalReportView";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const baseReport: RehearsalReportOut = {
  rehearsal_id: "reh-1",
  review_id: "r1",
  attempt_num: 1,
  status: "done",
  delivery: { words_per_minute: 120, filler_words: { ну: 3 }, long_pauses: [] },
  timing_map: [
    { slide_num: 1, start: 0, end: 5, duration: 5, pacing: "stub" },
    { slide_num: 2, start: 5, end: 65, duration: 60, pacing: null },
  ],
  findings: [
    {
      id: "f1",
      slide_num: 1,
      category: "NARRATIVE",
      severity: "MINOR",
      title: "Слайд пролистан слишком быстро",
      description: "Слайд 1 показан 5 с.",
      fix_suggestion: "Уберите слайд.",
    },
  ],
  delta: null,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RehearsalReportView", () => {
  it("renders delivery, timing map, and findings once loaded", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(baseReport);
    render(<RehearsalReportView rehearsalId="reh-1" />, { wrapper });

    expect(await screen.findByText("Карта тайминга")).toBeInTheDocument();
    expect(screen.getByText("заглушка")).toBeInTheDocument();
    expect(screen.getByText("Слайд пролистан слишком быстро")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument(); // words_per_minute
  });

  it("shows the empty state when there are no findings", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce({ ...baseReport, findings: [] });
    render(<RehearsalReportView rehearsalId="reh-1" />, { wrapper });

    expect(await screen.findByText("Явных проблем в подаче не нашли 🎉")).toBeInTheDocument();
  });

  it("renders the delta panel when a previous attempt exists", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      ...baseReport,
      delta: {
        previous_attempt_num: 1,
        words_per_minute_delta: 15,
        filler_words_delta: -2,
        long_pauses_delta: 0,
      },
    });
    render(<RehearsalReportView rehearsalId="reh-2" />, { wrapper });

    expect(await screen.findByText("Прогресс с попытки №1")).toBeInTheDocument();
    expect(screen.getByText("+15")).toBeInTheDocument();
    expect(screen.getByText("-2")).toBeInTheDocument();
  });

  it("shows an error state when the report fails to load", async () => {
    const { ApiError } = await import("@/api/client");
    vi.spyOn(apiClient, "request").mockRejectedValueOnce(
      new ApiError(409, "Репетиция ещё обрабатывается", null),
    );
    render(<RehearsalReportView rehearsalId="reh-1" />, { wrapper });

    expect(await screen.findByText("Репетиция ещё обрабатывается")).toBeInTheDocument();
  });
});
