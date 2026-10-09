import { api, json, request } from "./client";
import { readEvents } from "./sse";
import { readNdjson, type VoiceEvent } from "./voice";
import type {
  BrainHit, BrainInsights, BrainNote, CameraLook, ChatEvent, ConversationSummary, HubApp, Hud, Inbox, InboxEvent, InboxItem,
  PendingToolCall, ProtocolPreview, ProtocolRunResult, SirisWidgets,
} from "./types";

export const hub = {
  apps: (opts: { widgets?: boolean; fresh?: boolean } = {}) =>
    hub.appsWithGuest(opts).then((r) => r.apps),
  /** The apps, and whether SirisAI's guest mode is hiding the personal widgets. */
  appsWithGuest: (opts: { widgets?: boolean; fresh?: boolean } = {}) =>
    api<{ apps: HubApp[]; guest_mode?: boolean }>(
      `/api/v1/hub/apps?widgets=${opts.widgets ? "true" : "false"}&fresh=${opts.fresh ? "true" : "false"}`,
    ),
  app: (id: string, fresh = false) => api<HubApp>(`/api/v1/hub/apps/${encodeURIComponent(id)}?fresh=${fresh}`),
};

export const brain = {
  search: (q: string, limit = 12) => api<BrainHit[]>(`/api/v1/brain/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  map: () => request("/api/v1/brain/map.html").then((r) => r.text()),
  today: () => api<{ date: string; items: { title: string; action: string }[] }>("/api/v1/brain/today"),
  insights: (days = 30) => api<BrainInsights>(`/api/v1/brain/insights?days=${days}`),
  link: (a: string, b: string) => api<{ action: string; a: string; b: string }>("/api/v1/brain/link", json({ a, b })),
  notRelated: (a: string, b: string) => api<{ action: string; a: string; b: string }>("/api/v1/brain/not-related", json({ a, b })),
  unlink: (a: string, b: string) => api<{ action: string; a: string; b: string }>("/api/v1/brain/unlink", json({ a, b })),
  autolink: () => api<{ linked: { a: string; b: string; confidence: number | null }[]; deferred: number }>("/api/v1/brain/autolink", { method: "POST" }),
  note: (title: string) => api<BrainNote>(`/api/v1/brain/note?title=${encodeURIComponent(title)}`),
  capture: (body: { text?: string; url?: string; title?: string; tags?: string[] }) =>
    api<{ saved: boolean; title: string; action?: string }>("/api/v1/brain/capture", json(body)),
};

/** The inbox (ADR 110): SirisAI's attention feed plus SirisOS's own items. */
export const inbox = {
  list: () => api<Inbox>("/api/v1/attention"),
  act: (id: string, action: string) =>
    api<{ item: Partial<InboxItem> & { id: string }; result: unknown }>(`/api/v1/attention/${encodeURIComponent(id)}/act`, json({ action })),
  dismiss: (id: string) => api<{ item: { id: string } }>(`/api/v1/attention/${encodeURIComponent(id)}/dismiss`, { method: "POST" }),
  /** Live: a snapshot first, then each change. Ends when the connection does. */
  async *stream(signal?: AbortSignal): AsyncGenerator<InboxEvent> {
    const response = await request("/api/v1/attention/stream", { signal });
    if (!response.body) return;
    yield* readEvents<InboxEvent>(response.body);
  },
};

export const assistant = {
  hud: () => api<Hud>("/api/v1/assistant/hud"),
  widgets: () => api<SirisWidgets>("/api/v1/assistant/widgets"),
  protocol: (name: string) => api<ProtocolPreview>(`/api/v1/assistant/protocols/${encodeURIComponent(name)}`),
  runProtocol: (name: string) => api<ProtocolRunResult>(`/api/v1/assistant/protocols/${encodeURIComponent(name)}/run`, json({ confirmed: true })),
  undoProtocol: () => api<ProtocolRunResult>("/api/v1/assistant/protocols/undo", json({ confirmed: true })),
  look: (camera: string, question?: string) =>
    api<CameraLook>(`/api/v1/assistant/cameras/${encodeURIComponent(camera)}/look`, json(question ? { question } : {})),
  /** The camera's latest frame as an object URL (the request carries the session token). Revoke it when done. */
  frame: (camera: string) =>
    request(`/api/v1/assistant/cameras/${encodeURIComponent(camera)}/latest.jpg?t=${Date.now()}`).then((r) => r.blob()).then((b) => URL.createObjectURL(b)),
  voice: () => api<{ stt: boolean; tts: boolean }>("/api/v1/assistant/voice"),
  /** One voice turn: a recording (or typed text) in, transcript + spoken sentences out. */
  async *converse(input: { audio?: Blob; text?: string }, conversationId?: string | null, signal?: AbortSignal): AsyncGenerator<VoiceEvent> {
    const form = new FormData();
    if (input.audio) form.append("file", input.audio, "sirisos.wav");
    if (input.text) form.append("text", input.text);
    if (conversationId) form.append("conversation_id", conversationId);
    const response = await request("/api/v1/assistant/voice/converse", { method: "POST", body: form, signal });
    if (!response.body) return;
    yield* readNdjson<VoiceEvent>(response.body);
  },
  conversations: (limit = 20) => api<ConversationSummary[]>(`/api/v1/assistant/conversations?limit=${limit}`),
  conversation: (id: string) =>
    api<{ role: string; content: string | null; tool_name: string | null; created_at: string }[]>(
      `/api/v1/assistant/conversations/${encodeURIComponent(id)}`,
    ),
  async *chat(prompt: string, conversationId?: string | null, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
    const response = await request("/api/v1/assistant/chat/stream", {
      ...json({ prompt, conversation_id: conversationId ?? undefined }),
      signal,
    });
    if (!response.body) return;
    yield* readEvents<ChatEvent>(response.body);
  },
  async *confirm(conversationId: string, call: PendingToolCall, usePlanner: boolean, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
    const response = await request("/api/v1/assistant/chat/confirm/stream", {
      ...json({ conversation_id: conversationId, tool_name: call.name, arguments: call.arguments, use_planner: usePlanner }),
      signal,
    });
    if (!response.body) return;
    yield* readEvents<ChatEvent>(response.body);
  },
};
