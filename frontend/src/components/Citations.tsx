import type { Citation } from "../api/client";

export function Citations({ items }: { items: Citation[] }) {
  if (!items.length) return null;
  return (
    <section className="citations" aria-label="回答引用">
      <p className="micro-label">AUTHORIZED SOURCES / {items.length}</p>
      {items.map((item) => (
        <article className="citation" key={item.evidence_id}>
          <div><strong>{item.document_title}</strong><span>{item.source_locator}</span></div>
          <blockquote>{item.snippet}</blockquote>
        </article>
      ))}
    </section>
  );
}
