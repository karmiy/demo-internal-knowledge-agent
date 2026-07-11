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
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const titleId = `document-preview-${detail.id}`;

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus();
    };
  }, [onClose]);

  return (
    <div className="preview-backdrop">
      <aside className="document-preview" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className="preview-header">
          <div>
            <p className="micro-label">EXTRACTED CONTENT / READ ONLY</p>
            <h2 id={titleId}>{detail.title}</h2>
          </div>
          <button ref={closeButtonRef} className="preview-close" type="button" onClick={onClose} aria-label="关闭文档预览">
            <span aria-hidden="true">×</span>
          </button>
        </header>

        {loading && <p className="preview-state">正在读取提取内容…</p>}
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
              <p className="preview-state">暂无可预览的提取内容。</p>
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
