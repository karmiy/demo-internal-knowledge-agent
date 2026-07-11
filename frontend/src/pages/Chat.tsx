import { type FormEvent, useLayoutEffect, useRef, useState } from "react";
import { api, type ChatResult } from "../api/client";
import { Citations } from "../components/Citations";
import { MarkdownMessage } from "../components/MarkdownMessage";

type Message = { id: number; role: "user" | "assistant"; text: string; result?: ChatResult };
const BOTTOM_THRESHOLD_PX = 48;

export function isNearBottom(element: HTMLElement) {
  return element.scrollHeight - element.scrollTop - element.clientHeight <= BOTTOM_THRESHOLD_PX;
}

export function Chat({ token, sendChat = api.chat }: { token: string; sendChat?: typeof api.chat }) {
  const [question, setQuestion] = useState("");
  const [threadId, setThreadId] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const conversationRef = useRef<HTMLElement>(null);
  const shouldFollowRef = useRef(true);

  useLayoutEffect(() => {
    const element = conversationRef.current;
    if (element && shouldFollowRef.current) element.scrollTop = element.scrollHeight;
  }, [messages, busy, error]);

  async function submit(event: FormEvent) {
    event.preventDefault(); const text = question.trim(); if (!text || busy) return;
    setQuestion(""); setError(""); setBusy(true);
    setMessages((items) => [...items, { id: Date.now(), role: "user", text }]);
    try {
      const result = await sendChat(token, text, threadId); setThreadId(result.thread_id);
      setMessages((items) => [...items, { id: Date.now() + 1, role: "assistant", text: result.answer, result }]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "问答请求失败"); }
    finally { setBusy(false); }
  }
  return (
    <div className="chat-page">
      <header className="page-header"><div><p className="micro-label">SECURE ANSWER DESK / LIVE</p><h1>知识问答</h1></div><span className="status-chip">ACL 已启用</span></header>
      <section ref={conversationRef} className="conversation" aria-live="polite" onScroll={(event) => { shouldFollowRef.current = isNearBottom(event.currentTarget); }}>
        {!messages.length && <div className="empty-conversation"><span>ASK / VERIFY / TRACE</span><h2>从一个具体问题开始</h2><p>试试“工程发布流程是什么？”或“我的薪资是多少？”</p></div>}
        {messages.map((message) => <article key={message.id} className={`message ${message.role}`}><span>{message.role === "user" ? "YOU" : "AGENT"}</span><div>{message.role === "assistant" ? <MarkdownMessage content={message.text} /> : <p>{message.text}</p>}{message.result && <><Citations items={message.result.citations} /><div className="activity">{message.result.activity.map((item) => <small key={item}>{item === "searched_documents" ? "已检索授权文档" : "已查询授权数据"}</small>)}</div></>}</div></article>)}
        {busy && <div className="thinking" role="status"><i /><i /><i /> 正在检索授权证据</div>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </section>
      <form className="composer" onSubmit={submit}><textarea id="question" aria-label="问题" rows={2} value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="输入关于内部制度、工程流程或本人数据的问题…" /><button disabled={busy || !question.trim()} aria-label="发送">↗</button><small>回答仅依据当前身份可访问的信息</small></form>
    </div>
  );
}
