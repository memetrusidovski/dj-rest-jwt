import { createContext, createElement, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";
import type { AuthClient } from "./client";
import type { AuthState } from "./types";

const AuthContext = createContext<AuthClient | null>(null);

/** Provides `client` to `useAuth()` and loads the session once on mount. */
export function AuthProvider({ client, children }: { client: AuthClient; children?: ReactNode }) {
  useEffect(() => {
    if (client.getState().status === "unknown") void client.getSession();
  }, [client]);
  return createElement(AuthContext.Provider, { value: client }, children);
}

/** The auth client and its live state. Re-renders on sign-in, sign-out and flow changes. */
export function useAuth(): { client: AuthClient } & AuthState {
  const client = useContext(AuthContext);
  if (!client) throw new Error("useAuth() needs an <AuthProvider>.");
  const state = useSyncExternalStore(client.subscribe, client.getState, client.getState);
  return { client, ...state };
}
