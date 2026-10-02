import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowUp, Check, History, Plus, Square, Wrench, X } from "lucide-react";
import { assistant } from "../api/hub";
import type { ChatEvent, ChatResponse, ConversationSummary, PendingToolCall } from "../api/types";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";

export interface Message {
  role: "user" | "assistant";
  text: string;
  tools?: { name: string; status?: string }[];
  status?: string;
  pending?: PendingToolCall;
  usedPlanner?: boolean;
  error?: string;
  streaming?: boolean;
}

/** Folds one stream event into the assistant message being written. */
export function applyEvent(message: Message, event: ChatEvent): Message {
  switch (event.type) {
    case "status":
      return { ...message, status: event.message };
    case "thinking":
      return { ...message, status: "Thinking" };
    case "content":
      return { ...message, text: message.text + event.delta, status: undefined };
    case "tool_start":
      // Provisional text before a tool call is replaced by the post-tool answer.
      return { ...message, text: "", status: `Using ${event.name}`, tools: [...(message.tools ?? []), { name: event.name }] };
    case "tool_end":
      return {
        ...message,
        tools: (message.tools ?? []).map((t, i, all) => (i === all.length - 1 && t.name === event.name ? { ...t, status: event.status } : t)),
      };
    case "final":
      return finalise(message, event.response);
    case "error":
      return { ...message, streaming: false, status: undefined, error: event.detail || `Error ${event.status}` };
  }
}

function finalise(message: Message, response: ChatResponse): Message {
  let text = response.response ?? message.text;
  if (!text && response.tool_call) text = `Ran ${response.tool_call.name}.`;
  return {
    ...message,
    text,
    streaming: false,
    status: undefined,
    pending: response.confirmation_required ?? undefined,
    usedPlanner: response.used_planner,
  };
}

export function Assistant() {
  const [params, setParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<ConversationSummary[] | null>(null);
  const abort = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // Braces matter: newer browsers return a Promise from scrollIntoView, and
  // React would call a returned value as the effect's cleanup.
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages]);

  const run = useCallback(async (events: (signal: AbortSignal) => AsyncGenerator<ChatEvent>) => {
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true);
    setMessages((m) => [...m, { role: "assistant", text: "", streaming: true, status: "Connecting" }]);
    const update = (fn: (m: Message) => Message) =>
      setMessages((all) => [...all.slice(0, -1), fn(all[all.length - 1])]);
    try {
      for await (const event of events(controller.signal)) {
        if (event.type === "final") setConversationId(event.response.conversation_id);
        update((m) => applyEvent(m, event));
      }
      update((m) => (m.streaming ? { ...m, streaming: false, status: undefined } : m));
    } catch (err) {
      const aborted = controller.signal.aborted;
      update((m) => ({ ...m, streaming: false, status: undefined, error: aborted ? undefined : err instanceof Error ? err.message : "Siris is unavailable." }));
    } finally {
      setBusy(false);
      abort.current = null;
    }
  }, []);

  const send = useCallback(
    (prompt: string) => {
      if (!prompt.trim() || busy) return;
      setMessages((m) => [...m, { role: "user", text: prompt.trim() }]);
      setInput("");
      run((signal) => assistant.chat(prompt.trim(), conversationId, signal));
    },
    [busy, conversationId, run],
  );

  // Home's "Ask Siris" bar hands off with ?q=.
  useEffect(() => {
    const q = params.get("q");
    if (q) {
      setParams({}, { replace: true });
      send(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function confirm(index: number, approve: boolean) {
    const message = messages[index];
    if (!message.pending || !conversationId) return;
    const call = message.pending;
    setMessages((all) => all.map((m, i) => (i === index ? { ...m, pending: undefined } : m)));
    if (approve) run((signal) => assistant.confirm(conversationId, call, !!message.usedPlanner, signal));
    else setMessages((all) => [...all, { role: "assistant", text: `Okay, I won't run ${call.name}.` }]);
  }

  async function openHistory() {
    setHistory([]);
    try {
      setHistory(await assistant.conversations());
    } catch {
      setHistory([]);
    }
  }

  async function resume(id: string) {
    setHistory(null);
    const rows = await assistant.conversation(id);
    setConversationId(id);
    setMessages(
      rows
        .filter((r) => (r.role === "user" || r.role === "assistant") && r.content)
        .map((r) => ({ role: r.role as Message["role"], text: r.content ?? "" })),
    );
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  return (
    <div className="chat">
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">SirisAI</p>
          <h1 className="page-head__title">Siris</h1>
        </div>
        <div className="row">
          <Glass as="button" shape="pill" interactive className="button button--icon" onClick={openHistory} aria-label="Conversation history">
            <History aria-hidden="true" />
          </Glass>
          <Glass
            as="button"
            shape="pill"
            interactive
            className="button button--icon"
            onClick={() => {
              abort.current?.abort();
              setMessages([]);
              setConversationId(null);
            }}
            aria-label="New conversation"
          >
            <Plus aria-hidden="true" />
          </Glass>
        </div>
      </header>

      <div className="chat__log" aria-live="polite">
        {messages.length === 0 && (
          <div className="chat__empty">
            <p className="muted">Ask about your day, your home, your projects or anything in your Second Brain.</p>
            <div className="row" style={{ flexWrap: "wrap", justifyContent: "center" }}>
              {["What's on today?", "Brief me", "What did I learn this week?"].map((s) => (
                <Glass key={s} as="button" shape="pill" interactive className="button button--small" onClick={() => send(s)}>
                  {s}
                </Glass>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble-row bubble-row--${m.role}`}>
            <Glass variant={m.role === "user" ? "tint" : "regular"} shape="md" className={`bubble bubble--${m.role}`}>
              {m.tools && m.tools.length > 0 && (
                <div className="row" style={{ flexWrap: "wrap", gap: 6, marginBottom: m.text ? 8 : 0 }}>
                  {m.tools.map((t, j) => (
                    <span key={j} className="chip">
                      <Wrench size={12} aria-hidden="true" /> {t.name}
                      {t.status === "error" && <span className="tone-critical">failed</span>}
                    </span>
                  ))}
                </div>
              )}
              {m.text && <div className="bubble__text">{m.text}</div>}
              {m.streaming && m.status && <div className="bubble__status">{m.status}…</div>}
              {m.error && <div className="tone-critical bubble__status">{m.error}</div>}
              {m.pending && (
                <div className="confirm">
                  <p style={{ margin: "0 0 8px" }}>
                    Siris wants to run <strong>{m.pending.name}</strong>
                  </p>
                  <pre className="confirm__args">{JSON.stringify(m.pending.arguments, null, 2)}</pre>
                  <div className="row">
                    <Glass as="button" variant="tint" shape="pill" interactive className="button button--small" onClick={() => confirm(i, true)}>
                      <Check aria-hidden="true" /> Allow
                    </Glass>
                    <Glass as="button" shape="pill" interactive className="button button--small" onClick={() => confirm(i, false)}>
                      <X aria-hidden="true" /> Cancel
                    </Glass>
                  </div>
                </div>
              )}
            </Glass>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <Glass as="form" shape="pill" className="composer" onSubmit={submit}>
        <textarea
          className="composer__input"
          rows={1}
          placeholder="Message Siris"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          aria-label="Message Siris"
        />
        {busy ? (
          <Glass as="button" type="button" variant="tint" shape="pill" interactive className="button button--icon button--small" onClick={() => abort.current?.abort()} aria-label="Stop">
            <Square aria-hidden="true" />
          </Glass>
        ) : (
          <Glass as="button" type="submit" variant="tint" shape="pill" interactive className="button button--icon button--small" disabled={!input.trim()} aria-label="Send">
            <ArrowUp size={18} strokeWidth={2.5} aria-hidden="true" />
          </Glass>
        )}
      </Glass>

      {history && (
        <Sheet label="Conversations" onClose={() => setHistory(null)}>
          <h2 className="app-sheet__name" style={{ marginBottom: 12 }}>Conversations</h2>
          {history.length === 0 ? (
            <p className="muted">No conversations yet.</p>
          ) : (
            <ul className="items">
              {history.map((c) => (
                <li key={c.conversation_id}>
                  <button className="item item--button" onClick={() => resume(c.conversation_id)}>
                    <span className="item__text">
                      <div className="item__title">{c.started_with || "Conversation"}</div>
                      <div className="item__subtitle">{new Date(c.last_at).toLocaleString()}</div>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
      )}
    </div>
  );
}
