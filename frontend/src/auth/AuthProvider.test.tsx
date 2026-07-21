import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { apiClient } from "@/api/client";
import { AuthProvider, useAuth } from "./AuthProvider";

const STORAGE_KEY = "slidelens.tokens";

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

afterEach(() => {
  apiClient.setTokens(null);
  apiClient.setOnTokensChange(null);
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("AuthProvider", () => {
  it("starts unauthenticated with no stored tokens", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it("hydrates the session from localStorage on mount", async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ access_token: "a", refresh_token: "r" }),
    );
    vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      id: "u1",
      email: "user@example.com",
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.email).toBe("user@example.com");
  });

  it("login persists tokens to localStorage and sets user", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      access_token: "new-access",
      refresh_token: "new-refresh",
      user: { id: "u1", email: "user@example.com" },
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await result.current.login("user@example.com", "password1");

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    expect(stored).toEqual({ access_token: "new-access", refresh_token: "new-refresh" });
  });

  it("logout clears the stored session", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      access_token: "a",
      refresh_token: "r",
      user: { id: "u1", email: "user@example.com" },
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await result.current.login("user@example.com", "password1");
    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));

    result.current.logout();

    await waitFor(() => expect(result.current.isAuthenticated).toBe(false));
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("register authenticates the browser and persists tokens", async () => {
    vi.spyOn(apiClient, "request").mockResolvedValueOnce({
      access_token: "a",
      refresh_token: "r",
      user: { id: "u1", email: "new@example.com" },
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await result.current.register("new@example.com", "password1");

    await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
    expect(result.current.user?.email).toBe("new@example.com");
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    expect(stored).toEqual({ access_token: "a", refresh_token: "r" });
  });

  it("clears a stored session when /auth/me fails", async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ access_token: "stale", refresh_token: "stale" }),
    );
    vi.spyOn(apiClient, "request").mockRejectedValueOnce(new Error("expired"));

    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isAuthenticated).toBe(false);
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
