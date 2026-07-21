import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "@/auth/AuthProvider";
import PricingPage from "./PricingPage";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <MemoryRouter>{children}</MemoryRouter>
    </AuthProvider>
  );
}

function renderPage() {
  return render(<PricingPage />, { wrapper });
}

describe("PricingPage", () => {
  it("shows every pack with its per-Разбор price", () => {
    renderPage();

    expect(screen.getByText("149 ₽")).toBeInTheDocument();
    expect(screen.getByText("595 ₽")).toBeInTheDocument();
    expect(screen.getByText("1 980 ₽")).toBeInTheDocument();
    // 595 / 5 — цена за единицу считается, а не хардкодится в разметке.
    expect(screen.getByText(/119 ₽ за Разбор/)).toBeInTheDocument();
  });

  it("explains that payment is not wired up instead of pretending to charge", async () => {
    renderPage();

    expect(screen.queryByText(/Оплата пока не подключена/)).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getAllByRole("button", { name: "Купить" })[0]);

    expect(screen.getByRole("status")).toHaveTextContent(/Оплата пока не подключена/);
    expect(screen.getByRole("link", { name: /midavnibush@gmail.com/ })).toBeInTheDocument();
  });

  it("states the per-Разбор limits up front, not after payment", () => {
    renderPage();

    expect(screen.getByText(/25 слайдов/)).toBeInTheDocument();
    expect(screen.getByText(/30 минут/)).toBeInTheDocument();
  });

  it("sends an anonymous visitor to register rather than to checkout", () => {
    renderPage();

    expect(screen.getByRole("link", { name: "Начать бесплатно" })).toHaveAttribute(
      "href",
      "/login?mode=register",
    );
  });
});
