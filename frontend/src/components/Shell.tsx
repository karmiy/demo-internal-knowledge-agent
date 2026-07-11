import type { ReactNode } from "react";
import type { CurrentUser } from "../api/client";

export type PageName = "chat" | "documents";
export function Shell({ user, page, onNavigate, onLogout, children }: {
  user: CurrentUser; page: PageName; onNavigate: (page: PageName) => void;
  onLogout: () => void; children: ReactNode;
}) {
  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand"><span className="brand-mark">K</span><span>Knowledge<br />Registry</span></div>
        <nav aria-label="主导航">
          <button className={page === "chat" ? "active" : ""} onClick={() => onNavigate("chat")}><span>01</span>知识问答</button>
          {user.roles.includes("admin") && <button className={page === "documents" ? "active" : ""} onClick={() => onNavigate("documents")}><span>02</span>文档管理</button>}
        </nav>
        <div className="identity">
          <span className="identity-dot" aria-hidden="true" />
          <div><strong>{user.username}</strong><small>{user.department} · {user.roles.join(", ")}</small></div>
          <button onClick={onLogout}>退出</button>
        </div>
      </aside>
      <main className="workspace">{children}</main>
    </div>
  );
}
