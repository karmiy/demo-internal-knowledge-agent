import { useEffect, useRef } from "react";
import type { DocumentDetail, DocumentItem } from "../api/client";

type DocumentPreviewProps = {
  detail: DocumentDetail | DocumentItem;
  loading: boolean;
  error: string;
  onClose: () => void;
};

function isDocumentDetail(detail: DocumentDetail | DocumentItem): detail is DocumentDetail {
  return "chunks" in detail;
}

export function DocumentPreview({ detail, loading, error, onClose }: DocumentPreviewProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const titleId = `document-preview-${detail.id}`;

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;

      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
        "button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
      ));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) {
        event.preventDefault();
        return;
      }

      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    }
    function handleFocusIn(event: FocusEvent) {
      const dialog = dialogRef.current;
      if (dialog && !dialog.contains(event.target as Node)) closeButtonRef.current?.focus();
    }
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("focusin", handleFocusIn);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("focusin", handleFocusIn);
      previousFocus?.focus();
    };
  }, [onClose]);

  return (
    <div className="preview-backdrop">
      <aside ref={dialogRef} className="document-preview" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="preview-header">
          <div>
            <p className="micro-label">EXTRACTED CONTENT / READ ONLY</p>
            <h2 id={titleId}>{detail.title}</h2>
          </div>
          <button ref={closeButtonRef} className="preview-close" type="button" onClick={onClose} aria-label="关闭文档预览">
            <span aria-hidden="true">×</span>
          </button>
        </header>

        {loading && <p className="preview-state" role="status">正在读取提取内容…</p>}
        {!loading && error && <p className="preview-state preview-error" role="alert">{error}</p>}
        {!loading && !error && isDocumentDetail(detail) && (
          <div className="preview-content">
            <section className="preview-summary" aria-label="文档信息">
              <div><span>处理状态</span><strong className={`doc-status ${detail.status}`}>{detail.status}</strong></div>
              <div><span>提取片段</span><strong>{detail.chunk_count}</strong></div>
              <div className="preview-permissions">
                <span>访问权限</span>
                <ul>
                  {detail.permissions.map((permission) => (
                    <li key={`${permission.subject_type}:${permission.subject_id}`}>
                      {permission.subject_type}: {permission.subject_id}
                    </li>
                  ))}
                </ul>
              </div>
            </section>

            {detail.chunks.length === 0 ? (
              <p className="preview-state">文档尚未完成处理</p>
            ) : (
              <ol className="chunk-list">
                {detail.chunks.map((chunk) => (
                  <li key={chunk.chunk_index}>
                    <div className="chunk-heading">
                      <span>{String(chunk.chunk_index + 1).padStart(2, "0")}</span>
                      <h3>{chunk.section || "未命名片段"}</h3>
                      {chunk.page_number !== null && <small>第 {chunk.page_number} 页</small>}
                    </div>
                    <p>{chunk.content}</p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
