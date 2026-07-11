import { useState } from "react";

import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Shell, type PageName } from "./components/Shell";
import { Chat } from "./pages/Chat";
import { Documents } from "./pages/Documents";
import { Login } from "./pages/Login";

function Application() {
  const { token, user, loading, login, logout } = useAuth();
  const [page, setPage] = useState<PageName>("chat");

  if (loading) return <div className="app-loading" role="status">正在确认访问身份…</div>;
  if (!token || !user) return <Login onLogin={login} />;

  return (
    <Shell user={user} page={page} onNavigate={setPage} onLogout={logout}>
      {page === "documents" && user.roles.includes("admin") ? (
        <Documents token={token} />
      ) : (
        <Chat token={token} />
      )}
    </Shell>
  );
}

export function App() {
  return <AuthProvider><Application /></AuthProvider>;
}
