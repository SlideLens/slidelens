import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { apiClient } from "@/api/client";
import type { ReviewOut } from "@/api/schemas";
import { AuthProvider } from "@/auth/AuthProvider";
import ProfilePage from "./ProfilePage";

const STORAGE_KEY = "slidelens.tokens";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

/**
 * AuthProvider's /auth/me hydration and useReviewPolling's /reviews fire from
 * separate components — their relative order isn't guaranteed, so route by path
 * instead of chaining mockResolvedValueOnce by call order.
 */
function signIn(user: Record<string, unknown>, reviews: ReviewOut[] = []) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ access_token: "a", refresh_token: "r" }));
  vi.spyOn(apiClient, "request").mockImplementation((path: string) => {
    if (path === "/auth/me") return Promise.resolve(user);
    if (path === "/reviews") return Promise.resolve(reviews);
    return Promise.reject(new Error(`unexpected request in test: ${path}`));
  });
}

function review(overrides: Partial<ReviewOut>): ReviewOut {
  return {
    id: "r1",
    status: "done",
    deck_filename: "deck.pptx",
    n_slides: 10,
    has_audio: false,
    has_data: false,
    created_at: "2026-01-01T00:00:00Z",
    score: 80,
    ...overrides,
  };
}

afterEach(() => {
  apiClient.setTokens(null);
  apiClient.setOnTokensChange(null);
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("ProfilePage", () => {
  it("shows remaining free Разборы with correct pluralization", async () => {
    signIn({
      id: "u1",
      email: "user@example.com",
      plan: "free",
      free_reviews_left: 1,
      balance_reviews: 0,
      email_verified: true,
    });
    render(<ProfilePage />, { wrapper });

    expect(await screen.findByText("user@example.com")).toBeInTheDocument();
    expect(screen.getByText(/1 Разбор осталось/)).toBeInTheDocument();
  });

  it("shows the exhausted-quota message at 0 free Разборов", async () => {
    signIn({
      id: "u1",
      email: "user@example.com",
      plan: "free",
      free_reviews_left: 0,
      balance_reviews: 0,
      email_verified: true,
    });
    render(<ProfilePage />, { wrapper });

    await waitFor(() => expect(screen.getByText(/0 Разборов осталось/)).toBeInTheDocument());
    expect(screen.getByText(/пополните баланс/)).toBeInTheDocument();
  });

  it("tells a paid user with an empty balance to top up — there is no unlimited plan", async () => {
    signIn({
      id: "u1",
      email: "user@example.com",
      plan: "paid",
      free_reviews_left: 0,
      balance_reviews: 0,
      email_verified: true,
    });
    render(<ProfilePage />, { wrapper });

    expect(await screen.findByText(/пополните баланс/)).toBeInTheDocument();
  });

  it("shows the purchased pack and does not nag when the balance is positive", async () => {
    signIn({
      id: "u1",
      email: "user@example.com",
      plan: "paid",
      free_reviews_left: 0,
      balance_reviews: 10,
      email_verified: true,
    });
    render(<ProfilePage />, { wrapper });

    expect(await screen.findByText("10 Разборов")).toBeInTheDocument();
    expect(screen.queryByText(/пополните баланс/)).not.toBeInTheDocument();
  });

  it("keeps unlimited Разборы for an admin", async () => {
    signIn({
      id: "u1",
      email: "admin@demo.com",
      plan: "free",
      free_reviews_left: 0,
      balance_reviews: 0,
      email_verified: true,
      is_admin: true,
    });
    render(<ProfilePage />, { wrapper });

    expect(await screen.findByText(/Безлимитные Разборы/)).toBeInTheDocument();
    expect(screen.queryByText(/пополните баланс/)).not.toBeInTheDocument();
  });

  it("shows an empty-state message when there are no reviews yet", async () => {
    signIn({
      id: "u1",
      email: "user@example.com",
      plan: "free",
      free_reviews_left: 2,
      balance_reviews: 0,
      email_verified: true,
    });
    render(<ProfilePage />, { wrapper });

    expect(
      await screen.findByText("Пока нет завершённых Разборов — статистика появится после первого."),
    ).toBeInTheDocument();
  });

  it("computes total count, average score, and analyzed slides from done reviews", async () => {
    signIn(
      {
        id: "u1",
        email: "user@example.com",
        plan: "free",
        free_reviews_left: 0,
      balance_reviews: 0,
        email_verified: true,
      },
      [
        review({ id: "r1", score: 60, n_slides: 10 }),
        review({ id: "r2", score: 80, n_slides: 8 }),
        review({ id: "r3", status: "processing", score: null, n_slides: null }),
      ],
    );
    render(<ProfilePage />, { wrapper });

    expect(await screen.findByText("3")).toBeInTheDocument(); // всего Разборов (any status)
    expect(screen.getByText("70")).toBeInTheDocument(); // средний Скор — only over done reviews
    expect(screen.getByText("18")).toBeInTheDocument(); // слайдов проанализировано
  });
});
