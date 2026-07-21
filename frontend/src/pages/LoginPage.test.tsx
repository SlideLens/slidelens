import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import LoginPage from "./LoginPage";
import * as AuthProviderModule from "@/auth/AuthProvider";
import { ApiError } from "@/api/client";

function renderLoginPage(
  authOverrides: Partial<ReturnType<typeof AuthProviderModule.useAuth>> = {},
  initialPath = "/login",
) {
  vi.spyOn(AuthProviderModule, "useAuth").mockReturnValue({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    ...authOverrides,
  });

  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/cabinet" element={<div>Cabinet page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  it("shows a field error for an invalid email and does not call login", async () => {
    const login = vi.fn();
    renderLoginPage({ login });
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("you@company.com"), "not-an-email");
    await user.type(screen.getByPlaceholderText("••••••••"), "password1");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByText("Введите корректный email")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("navigates to /cabinet after a successful login", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    renderLoginPage({ login });
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("you@company.com"), "user@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "password1");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    await waitFor(() => expect(login).toHaveBeenCalledWith("user@example.com", "password1"));
    expect(await screen.findByText("Cabinet page")).toBeInTheDocument();
  });

  it("shows the API error message when login fails", async () => {
    const login = vi.fn().mockRejectedValue(new ApiError(401, "Неверный email или пароль", null));
    renderLoginPage({ login });
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("you@company.com"), "user@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "wrongpass");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByText("Неверный email или пароль")).toBeInTheDocument();
  });

  it("navigates to /cabinet after a successful register", async () => {
    const register = vi.fn().mockResolvedValue(undefined);
    renderLoginPage({ register });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Регистрация" }));
    await user.type(screen.getByPlaceholderText("you@company.com"), "new@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "password1");
    await user.click(screen.getByRole("button", { name: "Зарегистрироваться" }));

    await waitFor(() => expect(register).toHaveBeenCalledWith("new@example.com", "password1"));
    expect(await screen.findByText("Cabinet page")).toBeInTheDocument();
  });

  it("rejects a short password on register", async () => {
    const register = vi.fn();
    renderLoginPage({ register });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Регистрация" }));
    await user.type(screen.getByPlaceholderText("you@company.com"), "new@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "short");
    await user.click(screen.getByRole("button", { name: "Зарегистрироваться" }));

    expect(await screen.findByText("Минимум 8 символов")).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });

  it("opens on the register tab when arriving via ?mode=register", () => {
    renderLoginPage({}, "/login?mode=register");
    expect(screen.getByRole("button", { name: "Зарегистрироваться" })).toBeInTheDocument();
  });
});
