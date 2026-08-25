"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError, type UserOut } from "@/api/client";

type AuthStatus = "checking" | "authenticated" | "anonymous";

interface AuthState {
  status: AuthStatus;
  user: UserOut | null;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [user, setUser] = useState<UserOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await api.auth.me();
      setUser(me);
      setStatus("authenticated");
    } catch {
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const me = await api.auth.login({ email, password });
      setUser(me);
      setStatus("authenticated");
    } catch (err) {
      setStatus("anonymous");
      setError(err instanceof ApiError ? err.message : "Login failed.");
      throw err;
    }
  }, []);

  // V1.6 B: POST /v1/auth/register sets the session + CSRF cookies itself
  // (auto-login) — the returned UserOut is already the authenticated user. The
  // server stays authoritative for the role via GET /v1/auth/me; nothing about
  // the user is ever persisted client-side.
  const register = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const me = await api.auth.register({ email, password });
      setUser(me);
      setStatus("authenticated");
    } catch (err) {
      setStatus("anonymous");
      setError(err instanceof ApiError ? err.message : "Registration failed.");
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } finally {
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  const value = useMemo(
    () => ({ status, user, error, login, register, logout, refresh }),
    [status, user, error, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
