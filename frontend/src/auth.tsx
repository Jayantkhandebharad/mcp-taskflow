// Who is logged in, and how to log in and out — as React context, so any
// component can ask `useAuth()` without the answer being threaded through
// props from the top.
//
// The token itself lives in api.ts. This file owns the *user*: the answer to
// `GET /auth/me` for the token we hold. On startup, if a token exists in
// localStorage, we ask the backend who it belongs to. That call is also how
// an expired token gets noticed: it comes back 401, api.ts drops it, and the
// user sees the login page instead of a broken app.

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, hasToken, onUnauthorized, setToken } from "./api";
import type { User } from "./types";

interface AuthContextValue {
  /** `undefined` while the startup /auth/me call is in flight. */
  user: User | null | undefined;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, fullName: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(hasToken() ? undefined : null);

  useEffect(() => {
    // Registered once. When any request's token stops working, forget the
    // user; the `RequireAuth` route guard turns that into a redirect.
    onUnauthorized(() => setUser(null));

    if (!hasToken()) return;
    api.me().then(setUser, () => {
      // 401 already cleared the token via the handler. Anything else (the
      // backend is down) also means we can't prove who this is.
      setToken(null);
      setUser(null);
    });
  }, []);

  async function login(email: string, password: string): Promise<void> {
    const { access_token } = await api.login(email, password);
    setToken(access_token);
    // The login response is only a token. Two requests instead of one, but
    // it keeps /auth/login's shape identical for every client (PLAN.md §6).
    setUser(await api.me());
  }

  async function register(email: string, fullName: string, password: string): Promise<void> {
    await api.register(email, fullName, password);
    await login(email, password);
  }

  function logout(): void {
    // There is nothing to tell the server: a JWT can't be revoked (ADR 0002).
    // Forgetting it on this side is the whole of "logging out".
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}
