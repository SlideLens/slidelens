import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { apiClient } from "@/api/client";
import { reviews as fixtureReviews } from "@/fixtures/reviews";
import CabinetPage from "./CabinetPage";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("CabinetPage", () => {
  it("shows the empty state when there are no reviews", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce([]);
    render(<CabinetPage />, { wrapper });
    expect(await screen.findByText("Пока нет Разборов")).toBeInTheDocument();
  });

  it("renders a card per review once loaded", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce(fixtureReviews);
    render(<CabinetPage />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText(fixtureReviews[0].deck_filename)).toBeInTheDocument(),
    );
    for (const review of fixtureReviews) {
      expect(screen.getByText(review.deck_filename)).toBeInTheDocument();
    }
  });

  it("shows an error state when the list fails to load", async () => {
    vi.spyOn(apiClient, "request").mockRejectedValueOnce(new Error("network down"));
    render(<CabinetPage />, { wrapper });
    expect(await screen.findByText("Не удалось загрузить Разборы")).toBeInTheDocument();
  });
});
