export type CurrentUser = { id: string; username: string; department: string; roles: string[] };
export type Citation = { evidence_id: string; document_title: string; source_locator: string; snippet: string };
export type ChatResult = { thread_id: string; answer: string; citations: Citation[]; activity: string[] };
export type DocumentItem = { id: string; title: string; status: string; error: string | null };
export type DocumentPermission = { subject_type: string; subject_id: string };
export type DocumentChunk = {
  chunk_index: number;
  section: string | null;
  page_number: number | null;
  content: string;
};
export type DocumentDetail = DocumentItem & {
  created_at: string;
  updated_at: string;
  permissions: DocumentPermission[];
  chunk_count: number;
  chunks: DocumentChunk[];
};

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(payload.detail || `请求失败 (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  async login(username: string, password: string) {
    return request<{ access_token: string }>("/api/auth/login", {
      method: "POST", body: JSON.stringify({ username, password }),
    });
  },
  me: (token: string) => request<CurrentUser>("/api/auth/me", {}, token),
  chat: (token: string, message: string, threadId?: string) => request<ChatResult>("/api/chat", {
    method: "POST", body: JSON.stringify({ message, thread_id: threadId }),
  }, token),
  documents: (token: string) => request<DocumentItem[]>("/api/admin/documents", {}, token),
  document: (token: string, id: string) => request<DocumentDetail>(`/api/admin/documents/${id}`, {}, token),
  uploadDocument: (token: string, form: FormData) => request<DocumentItem>("/api/admin/documents", {
    method: "POST", body: form,
  }, token),
  retryDocument: (token: string, id: string) => request<DocumentItem>(`/api/admin/documents/${id}/retry`, {
    method: "POST",
  }, token),
};
