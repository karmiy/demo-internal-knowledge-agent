import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { api, type CurrentUser } from "../api/client";

type AuthValue = {
  token: string | null; user: CurrentUser | null; loading: boolean;
  login: (username: string, password: string) => Promise<void>; logout: () => void;
};
const AuthContext = createContext<AuthValue | null>(null);
const TOKEN_KEY = "knowledge-agent-token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(Boolean(token));

  useEffect(() => {
    if (!token) { setLoading(false); setUser(null); return; }
    let active = true;
    api.me(token).then((current) => { if (active) setUser(current); })
      .catch(() => { if (active) { localStorage.removeItem(TOKEN_KEY); setToken(null); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);

  async function login(username: string, password: string) {
    const result = await api.login(username, password);
    localStorage.setItem(TOKEN_KEY, result.access_token);
    setLoading(true); setToken(result.access_token);
  }
  function logout() { localStorage.removeItem(TOKEN_KEY); setToken(null); setUser(null); }
  const value = useMemo(() => ({ token, user, loading, login, logout }), [token, user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
