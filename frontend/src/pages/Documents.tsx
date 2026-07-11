import { type FormEvent, useEffect, useState } from "react";
import { api, type DocumentItem } from "../api/client";

export function Documents({ token }: { token: string }) {
  const [items, setItems] = useState<DocumentItem[]>([]); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api.documents(token).then((documents) => { if (active) setItems(documents); })
      .catch((reason) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [token]);
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); const formElement = event.currentTarget; const form = new FormData(formElement);
    form.set("subjects", JSON.stringify([{ type: form.get("acl"), id: form.get("subject_id") || null }])); form.delete("acl"); form.delete("subject_id");
    try { const created = await api.uploadDocument(token, form); setItems((old) => [created, ...old]); formElement.reset(); } catch (e) { setError(e instanceof Error ? e.message : "上传失败"); } finally { setBusy(false); }
  }
  return <div className="documents-page"><header className="page-header"><div><p className="micro-label">INGESTION REGISTER / ADMIN</p><h1>文档管理</h1></div><span className="status-chip">{items.length} 份文档</span></header><div className="documents-grid"><form className="upload-panel" onSubmit={upload}><h2>登记新文档</h2><p>支持 PDF、DOCX、Markdown 与 TXT，最大 20 MB。</p><label htmlFor="title">文档标题</label><input id="title" name="title" required /><label htmlFor="file">选择文件</label><input id="file" name="file" type="file" accept=".pdf,.docx,.md,.txt" required /><label htmlFor="acl">访问范围</label><select id="acl" name="acl"><option value="authenticated">所有登录用户</option><option value="department">指定部门</option><option value="role">指定角色</option><option value="user">指定用户 ID</option></select><label htmlFor="subject_id">范围标识（全员可留空）</label><input id="subject_id" name="subject_id" /><button className="primary-button" disabled={busy}>{busy ? "正在登记…" : "登记并等待处理"}</button>{error && <p className="form-error" role="alert">{error}</p>}</form><section className="document-register"><div className="register-head"><span>文档</span><span>处理状态</span></div>{!items.length && <p className="empty-list">还没有已登记文档。</p>}{items.map((item) => <article key={item.id}><div><strong>{item.title}</strong><small>{item.id.slice(0, 8)}</small></div><div><span className={`doc-status ${item.status}`}>{item.status}</span>{item.status === "failed" && <button onClick={async () => { const next = await api.retryDocument(token, item.id); setItems((old) => old.map((doc) => doc.id === item.id ? next : doc)); }}>重试</button>}</div></article>)}</section></div></div>;
}
