import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { apiClient } from "@/api/client";
import * as AuthProviderModule from "@/auth/AuthProvider";
import LandingPage from "./LandingPage";
import * as analytics from "@/lib/analytics";

function renderLanding(authOverrides: Partial<ReturnType<typeof AuthProviderModule.useAuth>> = {}) {
  vi.spyOn(AuthProviderModule, "useAuth").mockReturnValue({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    ...authOverrides,
  });

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("LandingPage", () => {
  it("renders the offer, a register-tab CTA, and the live example report — no auth required", () => {
    renderLanding();
    expect(
      screen.getByText("Загрузите Деку. Получите взгляд, которого не хватает перед сценой"),
    ).toBeInTheDocument();
    const cta = screen.getByRole("link", { name: "Начать бесплатно" });
    expect(cta).toHaveAttribute("href", "/login?mode=register");
    expect(screen.getByText("Живой пример Отчёта")).toBeInTheDocument();
    // the real ReviewReport component, not a lookalike:
    expect(screen.getByText("Серьёзность")).toBeInTheDocument();
  });

  it("hides the download buttons on the example report (fixture has no real files)", () => {
    renderLanding();
    expect(screen.queryByRole("button", { name: /Скачать PDF-отчёт/ })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Скачать исправленный PPTX/ }),
    ).not.toBeInTheDocument();
  });

  it("lets 👍/👎 color visually on the example report without calling the API", async () => {
    const requestSpy = vi.spyOn(apiClient, "request");
    renderLanding();
    const user = userEvent.setup();

    const [likeButton] = screen.getAllByLabelText("Пометить находку как полезную");
    await user.click(likeButton);

    expect(likeButton).toHaveAttribute("aria-pressed", "true");
    expect(requestSpy).not.toHaveBeenCalled();
  });

  it("initializes analytics on mount", () => {
    const initSpy = vi.spyOn(analytics, "initAnalytics").mockImplementation(() => {});
    renderLanding();
    expect(initSpy).toHaveBeenCalledTimes(1);
  });

  it("tracks a cta_click event when the CTA is clicked", async () => {
    const trackSpy = vi.spyOn(analytics, "trackPlausibleEvent").mockImplementation(() => {});
    renderLanding();
    const user = userEvent.setup();
    await user.click(screen.getByRole("link", { name: "Начать бесплатно" }));
    expect(trackSpy).toHaveBeenCalledWith("cta_click");
  });

  it("sends an already-authenticated visitor straight to the cabinet, not to login/register", () => {
    renderLanding({
      isAuthenticated: true,
      user: {
        id: "u1",
        email: "user@example.com",
        plan: "free",
        free_reviews_left: 2,
      balance_reviews: 0,
        email_verified: true,
        is_admin: false,
      },
    });

    const cta = screen.getByRole("link", { name: "Перейти в Кабинет" });
    expect(cta).toHaveAttribute("href", "/cabinet");
    expect(screen.queryByRole("link", { name: "Начать бесплатно" })).not.toBeInTheDocument();
  });
});
