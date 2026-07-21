import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { apiClient } from "@/api/client";
import type { ReviewOut } from "@/api/schemas";
import { ReviewCard } from "./ReviewCard";

const review: ReviewOut = {
  id: "r1",
  status: "done",
  score: 82,
  deck_filename: "pitch.pptx",
  n_slides: 8,
  has_audio: false,
  has_data: false,
  created_at: "2026-07-10T09:15:00Z",
  finished_at: "2026-07-10T09:18:40Z",
};

function renderCard(r: ReviewOut = review) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  return render(<ReviewCard review={r} />, { wrapper });
}

describe("ReviewCard", () => {
  it("shows the upload date", () => {
    renderCard();
    expect(screen.getByText(/загружено 10 июля 2026/)).toBeInTheDocument();
  });

  it("links to the report", () => {
    renderCard();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/reviews/r1");
  });

  it("requires confirmation before deleting", async () => {
    renderCard();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Удалить Разбор" }));

    expect(await screen.findByText("Удалить «pitch.pptx»?")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("deletes the review via a real request after confirming", async () => {
    const requestSpy = vi.spyOn(apiClient, "request").mockResolvedValueOnce(undefined);
    renderCard();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Удалить Разбор" }));
    await user.click(await screen.findByRole("button", { name: "Да, удалить" }));

    expect(requestSpy).toHaveBeenCalledWith("/reviews/r1", { method: "DELETE" });
  });

  it("cancels without deleting", async () => {
    const requestSpy = vi.spyOn(apiClient, "request");
    renderCard();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Удалить Разбор" }));
    await user.click(await screen.findByRole("button", { name: "Отмена" }));

    expect(screen.queryByText("Удалить «pitch.pptx»?")).not.toBeInTheDocument();
    expect(screen.getByRole("link")).toBeInTheDocument();
    expect(requestSpy).not.toHaveBeenCalled();
  });
});
