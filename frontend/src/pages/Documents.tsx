import { type FormEvent, useCallback, useEffect, useState } from "react";
import { api, type DocumentDetail, type DocumentItem } from "../api/client";
import { DocumentPreview } from "../components/DocumentPreview";

export function Documents({ token }: { token: string }) {
  const [items, setItems] = useState<DocumentItem[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<DocumentItem | null>(null);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");

  useEffect(() => {
    let active = true;
    api.documents(token)
      .then((documents) => { if (active) setItems(documents); })
      .catch((reason) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [token]);

  useEffect(() => {
    if (!selected) return;
    let active = true;
    setDetail(null);
    setPreviewError("");
    setPreviewLoading(true);
    api.document(token, selected.id)
      .then((document) => { if (active) setDetail(document); })
      .catch((reason) => {
        if (active) setPreviewError(reason instanceof Error ? reason.message : "无法读取文档");
      })
      .finally(() => { if (active) setPreviewLoading(false); });
    return () => { active = false; };
  }, [selected, token]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    form.set("subjects", JSON.stringify([{ type: form.get("acl"), id: form.get("subject_id") || null }]));
    form.delete("acl");
    form.delete("subject_id");
    try {
      const created = await api.uploadDocument(token, form);
      setItems((old) => [created, ...old]);
      formElement.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function retry(id: string) {
    setError("");
    try {
      const next = await api.retryDocument(token, id);
      setItems((old) => old.map((document) => document.id === id ? next : document));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重试失败");
    }
  }

  const closePreview = useCallback(() => {
    setSelected(null);
    setDetail(null);
    setPreviewError("");
  }, []);

  return (
    <div className="documents-page">
      <header className="page-header">
        <div><p className="micro-label">INGESTION REGISTER / ADMIN</p><h1>文档管理</h1></div>
        <span className="status-chip">{items.length} 份文档</span>
      </header>
      <div className="documents-grid">
        <form className="upload-panel" onSubmit={upload}>
          <h2>登记新文档</h2>
          <p>支持 PDF、DOCX、Markdown 与 TXT，最大 20 MB。</p>
          <label htmlFor="title">文档标题</label><input id="title" name="title" required />
          <label htmlFor="file">选择文件</label><input id="file" name="file" type="file" accept=".pdf,.docx,.md,.txt" required />
          <label htmlFor="acl">访问范围</label>
          <select id="acl" name="acl"><option value="authenticated">所有登录用户</option><option value="department">指定部门</option><option value="role">指定角色</option><option value="user">指定用户 ID</option></select>
          <label htmlFor="subject_id">范围标识（全员可留空）</label><input id="subject_id" name="subject_id" />
          <button className="primary-button" disabled={busy}>{busy ? "正在登记…" : "登记并等待处理"}</button>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>
        <section className="document-register">
          <div className="register-head"><span>文档</span><span>处理状态</span></div>
          {!items.length && <p className="empty-list">还没有已登记文档。</p>}
          {items.map((item) => (
            <article key={item.id}>
              <button className="document-open" type="button" onClick={() => setSelected(item)}>
                <strong>{item.title}</strong><small>{item.id.slice(0, 8)}</small>
              </button>
              <div>
                <span className={`doc-status ${item.status}`}>{item.status}</span>
                {item.status === "failed" && <button type="button" onClick={() => void retry(item.id)}>重试</button>}
              </div>
            </article>
          ))}
        </section>
      </div>
      {selected && (
        <DocumentPreview
          detail={detail || selected}
          loading={previewLoading}
          error={previewError}
          onClose={closePreview}
        />
      )}
    </div>
  );
}
