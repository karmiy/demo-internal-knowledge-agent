import { type FormEvent, useState } from "react";

export function Login({ onLogin }: { onLogin: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState("alice.programmer");
  const [password, setPassword] = useState("demo-password");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { await onLogin(username, password); } catch (reason) { setError(reason instanceof Error ? reason.message : "登录失败"); setBusy(false); }
  }
  return (
    <main className="login-page">
      <section className="login-intro">
        <p className="micro-label">INTERNAL / AUTHORIZED ACCESS ONLY</p>
        <div className="login-mark">K</div>
        <h1>让内部知识<br /><em>有据可查。</em></h1>
        <p>权限先于检索，证据先于回答。这个轻量 Demo 展示文档 ACL、结构化数据工具和可追溯引用。</p>
      </section>
      <form className="login-form" onSubmit={submit}>
        <header><span>ACCESS CARD</span><strong>01 — 03</strong></header>
        <h2>身份验证</h2>
        <label htmlFor="username">用户名</label>
        <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        <label htmlFor="password">密码</label>
        <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button" disabled={busy}>{busy ? "验证中…" : "进入知识库 →"}</button>
        <div className="demo-users"><span>演示身份</span>{["alice.programmer", "helen.hr", "andy.admin"].map((name) => <button type="button" key={name} onClick={() => setUsername(name)}>{name}</button>)}</div>
      </form>
    </main>
  );
}
