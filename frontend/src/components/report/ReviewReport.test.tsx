import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { apiClient } from "@/api/client";
import type { ReportOut } from "@/api/schemas";
import { ReviewReport } from "./ReviewReport";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

const baseReport: ReportOut = {
  review_id: "r1",
  score: 80,
  n_slides: 3,
  findings: [],
  auto_fixed_count: 0,
  pdf_asset_id: "pdf-1",
  fixed_pptx_asset_id: null,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ReviewReport downloads", () => {
  it("shows only the PDF button when fixed_pptx_asset_id is null", () => {
    render(<ReviewReport report={baseReport} />, { wrapper });
    expect(screen.getByRole("button", { name: /Скачать PDF-отчёт/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Скачать исправленный PPTX/ })).not.toBeInTheDocument();
  });

  it("downloads the PDF via an authenticated request, not a bare link", async () => {
    const downloadSpy = vi
      .spyOn(apiClient, "download")
      .mockResolvedValueOnce(new Blob(["%PDF"], { type: "application/pdf" }));
    // jsdom implements neither URL.createObjectURL nor real anchor navigation.
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:mock"),
      revokeObjectURL: vi.fn(),
    });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<ReviewReport report={baseReport} />, { wrapper });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Скачать PDF-отчёт/ }));

    await waitFor(() => expect(downloadSpy).toHaveBeenCalledWith("/files/pdf-1"));
    expect(clickSpy).toHaveBeenCalled();
  });

  it("shows an error and keeps the button usable when the download fails", async () => {
    const { ApiError } = await import("@/api/client");
    vi.spyOn(apiClient, "download").mockRejectedValueOnce(
      new ApiError(404, "Не найдено", null),
    );

    render(<ReviewReport report={baseReport} />, { wrapper });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Скачать PDF-отчёт/ }));

    expect(await screen.findByText("Не найдено")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Скачать PDF-отчёт/ })).not.toBeDisabled();
  });
});
