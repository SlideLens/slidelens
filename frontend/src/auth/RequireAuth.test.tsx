import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./RequireAuth";
import * as AuthProviderModule from "./AuthProvider";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>Login page</div>} />
        <Route
          path="/cabinet"
          element={
            <RequireAuth>
              <div>Private cabinet</div>
            </RequireAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireAuth", () => {
  it("redirects to /login when not authenticated", () => {
    vi.spyOn(AuthProviderModule, "useAuth").mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    renderAt("/cabinet");
    expect(screen.getByText("Login page")).toBeInTheDocument();
    expect(screen.queryByText("Private cabinet")).not.toBeInTheDocument();
  });

  it("renders children when authenticated", () => {
    vi.spyOn(AuthProviderModule, "useAuth").mockReturnValue({
      user: {
        id: "u1",
        email: "user@example.com",
        plan: "free",
        free_reviews_left: 2,
      balance_reviews: 0,
        email_verified: true,
        is_admin: false,
      },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    renderAt("/cabinet");
    expect(screen.getByText("Private cabinet")).toBeInTheDocument();
  });

  it("renders nothing while the session is still loading", () => {
    vi.spyOn(AuthProviderModule, "useAuth").mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    renderAt("/cabinet");
    expect(screen.queryByText("Private cabinet")).not.toBeInTheDocument();
    expect(screen.queryByText("Login page")).not.toBeInTheDocument();
  });
});
