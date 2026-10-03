import { api, json, request } from "./client";
import { readEvents } from "./sse";
import { readNdjson, type VoiceEvent } from "./voice";
import type { BrainHit, ChatEvent, ConversationSummary, HubApp, Hud, PendingToolCall } from "./types";

export const hub = {
  apps: (opts: { widgets?: boolean; fresh?: boolean } = {}) =>
    api<{ apps: HubApp[] }>(
      `/api/v1/hub/apps?widgets=${opts.widgets ? "true" : "false"}&fresh=${opts.fresh ? "true" : "false"}`,
    ).then((r) => r.apps),
  app: (id: string, fresh = false) => api<HubApp>(`/api/v1/hub/apps/${encodeURIComponent(id)}?fresh=${fresh}`),
};

export const brain = {
  search: (q: string, limit = 12) => api<BrainHit[]>(`/api/v1/brain/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  map: () => request("/api/v1/brain/map.html").then((r) => r.text()),
  today: () => api<{ date: string; items: { title: string; action: string }[] }>("/api/v1/brain/today"),
  capture: (body: { text?: string; url?: string; title?: string; tags?: string[] }) =>
    api<{ saved: boolean; title: string; action?: string }>("/api/v1/brain/capture", json(body)),
};

export const assistant = {
  hud: () => api<Hud>("/api/v1/assistant/hud"),
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
