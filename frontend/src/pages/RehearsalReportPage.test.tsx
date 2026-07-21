import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { apiClient, ApiError } from "@/api/client";
import type { RehearsalOut, RehearsalReportOut } from "@/api/schemas";
import RehearsalReportPage from "./RehearsalReportPage";

function renderAt(reviewId: string, rehearsalId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/rehearsal/${reviewId}/attempts/${rehearsalId}`]}>
        <Routes>
          <Route path="/rehearsal/:reviewId/attempts/:rehearsalId" element={<RehearsalReportPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const baseRehearsal: RehearsalOut = {
  id: "reh-1",
  review_id: "r1",
  status: "processing",
  attempt_num: 1,
  created_at: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RehearsalReportPage", () => {
  it("shows the processing view while queued/processing", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(baseRehearsal);
    renderAt("r1", "reh-1");

    expect(await screen.findByText("SlideLens разбирает вашу репетицию…")).toBeInTheDocument();
  });

  it("offers the recording download even while the attempt is still processing", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(baseRehearsal);
    renderAt("r1", "reh-1");

    expect(await screen.findByRole("button", { name: /Скачать запись/ })).toBeInTheDocument();
  });

  it("downloads the recording via an authenticated request", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(baseRehearsal);
    const downloadSpy = vi
      .spyOn(apiClient, "download")
      .mockResolvedValueOnce(new Blob(["webm"], { type: "audio/webm" }));
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:mock"),
      revokeObjectURL: vi.fn(),
    });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    renderAt("r1", "reh-1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Скачать запись/ }));

    await waitFor(() => expect(downloadSpy).toHaveBeenCalledWith("/rehearsals/reh-1/audio"));
    expect(clickSpy).toHaveBeenCalled();
  });

  it("shows an error when the recording download fails", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(baseRehearsal);
    vi.spyOn(apiClient, "download").mockRejectedValueOnce(new ApiError(404, "Не найдено", null));

    renderAt("r1", "reh-1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /Скачать запись/ }));

    expect(await screen.findByText("Не найдено")).toBeInTheDocument();
  });

  it("shows the real fail_reason when failed", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      ...baseRehearsal,
      status: "failed",
      fail_reason: "Файл повреждён или не открывается",
    });
    renderAt("r1", "reh-1");

    expect(await screen.findByText("Репетицию не удалось обработать")).toBeInTheDocument();
    expect(screen.getByText("Файл повреждён или не открывается")).toBeInTheDocument();
  });

  it("fetches and renders the report when done", async () => {
    const report: RehearsalReportOut = {
      rehearsal_id: "reh-1",
      review_id: "r1",
      attempt_num: 1,
      status: "done",
      delivery: null,
      timing_map: [],
      findings: [],
      delta: null,
    };
    vi.spyOn(apiClient, "request")
      .mockResolvedValueOnce({ ...baseRehearsal, status: "done" })
      .mockResolvedValueOnce(report);
    renderAt("r1", "reh-1");

    expect(await screen.findByText("Явных проблем в подаче не нашли 🎉")).toBeInTheDocument();
    expect(screen.getByText("Попытка №1")).toBeInTheDocument();
  });
});
