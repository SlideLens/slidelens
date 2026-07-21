import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiClient, type TokenPair } from "@/api/client";
import type { AuthTokens, User } from "@/api/schemas";

const STORAGE_KEY = "slidelens.tokens";

function loadTokens(): TokenPair | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as TokenPair) : null;
  } catch {
    return null;
  }
}

function saveTokens(tokens: TokenPair | null): void {
  // Pick only the two token fields — callers (e.g. login()) may pass a superset
  // object (AuthTokens also carries `user`), which must never end up in storage.
  if (tokens) {
    const { access_token, refresh_token } = tokens;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ access_token, refresh_token }));
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

type AuthContextValue = {
  user: User | null;
  isAuthenticated: boolean;
  /** True until the initial localStorage → /auth/me hydration settles. */
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    apiClient.setOnTokensChange(saveTokens);
    return () => apiClient.setOnTokensChange(null);
  }, []);

  useEffect(() => {
    const tokens = loadTokens();
    if (!tokens) {
      setIsLoading(false);
      return;
    }
    apiClient.setTokens(tokens);
    apiClient
      .request<User>("/auth/me")
      .then((me) => setUser(me))
      .catch(() => {
        apiClient.setTokens(null);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await apiClient.request<AuthTokens>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    });
    apiClient.setTokens(tokens);
    setUser(tokens.user);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const tokens = await apiClient.request<AuthTokens>("/auth/register", {
      method: "POST",
      body: { email, password },
      auth: false,
    });
    apiClient.setTokens(tokens);
    setUser(tokens.user);
  }, []);

  const logout = useCallback(() => {
    apiClient.setTokens(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isAuthenticated: user !== null, isLoading, login, register, logout }),
    [user, isLoading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
