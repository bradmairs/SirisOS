import { memo, useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Activity, ArrowUp, Brain as BrainIcon, BookmarkPlus, Check, Cpu, History, Mic, Plus, Square, Wrench, X } from "lucide-react";
import { assistant, brain } from "../api/hub";
import type { ChatEvent, ChatResponse, ConversationSummary, PendingToolCall } from "../api/types";
import { ReplyPlayer, micUnavailableReason, startRecording, type Recording } from "../api/voice";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";
import { SirisOrb, type OrbState } from "../components/SirisOrb";
import { Ring, useHud } from "./HudWidgets";

export interface Message {
  role: "user" | "assistant";
  text: string;
  tools?: { name: string; status?: string }[];
  status?: string;
  pending?: PendingToolCall;
  usedPlanner?: boolean;
  error?: string;
  streaming?: boolean;
  /** Spoken rather than typed. */
  voice?: boolean;
  /** Saved to the Second Brain inbox from this screen. */
  saved?: boolean;
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

  // Voice, as on SirisAI's HUD.
  const [orb, setOrb] = useState<OrbState>("idle");
  const [hint, setHint] = useState("Tap to talk");
  const [voice, setVoice] = useState<{ stt: boolean; tts: boolean } | null>(null);
  const [recording, setRecording] = useState<Recording | null>(null);
  const player = useRef<ReplyPlayer | null>(null);
  if (player.current === null) player.current = new ReplyPlayer();

  // What the Second Brain picked up today, refreshed after each turn.
  const [learned, setLearned] = useState<{ title: string; action: string }[] | null>(null);
  const refreshLearned = useCallback(() => {
    brain.today().then((r) => setLearned(r.items)).catch(() => setLearned(null));
  }, []);
  const { hud } = useHud();

  useEffect(() => {
    assistant.voice().then(setVoice).catch(() => setVoice({ stt: false, tts: false }));
    refreshLearned();
    const p = player.current!;
    p.onSpeaking = (speaking) => speaking && setOrb("speaking");
    return () => p.stop();
  }, [refreshLearned]);

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
    // Fold stream events into the message at most once per frame: a fast
    // model emits many tokens per frame, and rendering each one is wasted work.
    let queue: ChatEvent[] = [];
    let frame = 0;
    const flush = () => {
      frame = 0;
      const batch = queue;
      queue = [];
      if (batch.length) update((m) => batch.reduce(applyEvent, m));
    };
    try {
      for await (const event of events(controller.signal)) {
        if (event.type === "final") setConversationId(event.response.conversation_id);
        queue.push(event);
        if (!frame) frame = nextFrame(flush);
      }
      cancelFrame(frame);
      flush();
      update((m) => (m.streaming ? { ...m, streaming: false, status: undefined } : m));
    } catch (err) {
      cancelFrame(frame);
      flush();
      const aborted = controller.signal.aborted;
      update((m) => ({ ...m, streaming: false, status: undefined, error: aborted ? undefined : err instanceof Error ? err.message : "Siris is unavailable." }));
    } finally {
      setBusy(false);
      abort.current = null;
      refreshLearned();
    }
  }, [refreshLearned]);

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

  // Search everything opens a past conversation with ?c=.
  useEffect(() => {
    const c = params.get("c");
    if (c) {
      setParams({}, { replace: true });
      resume(c).catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  // Stable callbacks for the memoised bubbles, always calling the latest handlers.
  const handlers = useRef({ saveToBrain: (_i: number) => {}, confirm: (_i: number, _a: boolean) => {} });
  const onSave = useCallback((i: number) => handlers.current.saveToBrain(i), []);
  const onConfirm = useCallback((i: number, approve: boolean) => handlers.current.confirm(i, approve), []);

  function confirm(index: number, approve: boolean) {
    const message = messages[index];
    if (!message.pending || !conversationId) return;
    const call = message.pending;
    setMessages((all) => all.map((m, i) => (i === index ? { ...m, pending: undefined } : m)));
    if (approve) run((signal) => assistant.confirm(conversationId, call, !!message.usedPlanner, signal));
    else setMessages((all) => [...all, { role: "assistant", text: `Okay, I won't run ${call.name}.` }]);
  }

  const voiceBlocked = micUnavailableReason() ?? (voice && !voice.stt ? "SirisAI's speech-to-text isn't set up (SIRISAI_STT_PROVIDER), so Siris can't hear yet. You can still type." : null);

  async function talk() {
    const p = player.current!;
    if (recording) {
      recording.stop();
      return;
    }
    if (orb === "speaking") {
      p.stop();
      setOrb("idle");
      setHint("Tap to talk");
      return;
    }
    if (busy) return;
    if (voiceBlocked) {
      setHint(voiceBlocked);
      return;
    }
    p.unlock();
    let rec: Recording;
    try {
      rec = await startRecording();
    } catch (err) {
      setHint(`Microphone unavailable: ${err instanceof Error ? err.message : "permission denied"}`);
      return;
    }
    setRecording(rec);
    setOrb("listening");
    setHint("Listening…");
    const wav = await rec.done;
    setRecording(null);
    await converse(wav);
  }

  async function converse(wav: Blob) {
    const p = player.current!;
    const controller = new AbortController();
    abort.current = controller;
    setBusy(true);
    setOrb("thinking");
    setHint("Thinking…");
    let expectsReply = false;
    let started = false;
    const update = (fn: (m: Message) => Message) => setMessages((all) => [...all.slice(0, -1), fn(all[all.length - 1])]);
    try {
      for await (const event of assistant.converse({ audio: wav }, conversationId, controller.signal)) {
        if (event.type === "transcript") {
          if (!event.text) {
            setHint("I didn't catch that. Tap to try again");
            break;
          }
          started = true;
          setMessages((m) => [...m, { role: "user", text: event.text, voice: true }, { role: "assistant", text: "", streaming: true, status: "Thinking", voice: true }]);
        } else if (event.type === "sentence" && started) {
          update((m) => ({ ...m, text: m.text ? `${m.text} ${event.text}` : event.text, status: undefined }));
          if (event.audio) p.play(event.audio);
        } else if ((event.type === "tool_start" || event.type === "tool_end") && started) {
          update((m) => applyEvent(m, event.type === "tool_start" ? { type: "tool_start", name: event.name, arguments: {} } : { type: "tool_end", name: event.name, status: (event.status as "ok") ?? "ok" }));
        } else if (event.type === "final") {
          if (event.conversation_id) setConversationId(event.conversation_id);
          expectsReply = !!event.expects_reply;
          if (started) update((m) => ({ ...m, text: m.text || event.response || "", streaming: false, status: undefined }));
        } else if (event.type === "error") {
          if (started) update((m) => ({ ...m, streaming: false, status: undefined, error: event.detail }));
          else setHint(event.detail);
        }
      }
    } catch (err) {
      if (!controller.signal.aborted) setHint(err instanceof Error ? err.message : "Siris is unavailable.");
    } finally {
      if (started) update((m) => (m.streaming ? { ...m, streaming: false, status: undefined } : m));
      setBusy(false);
      abort.current = null;
      refreshLearned();
    }
    await p.finished();
    setOrb("idle");
    setHint((h) => (h === "Thinking…" ? (expectsReply ? "Tap to answer" : "Tap to talk") : h));
  }

  /** Files a reply (and what was asked) into the Second Brain inbox. */
  async function saveToBrain(index: number) {
    const answer = messages[index];
    const asked = [...messages.slice(0, index)].reverse().find((m) => m.role === "user")?.text ?? "";
    try {
      await brain.capture({
        title: `Siris: ${(asked || answer.text).slice(0, 70)}`,
        text: asked ? `**Asked:** ${asked}\n\n${answer.text}` : answer.text,
        tags: ["siris", "sirisos"],
      });
      setMessages((all) => all.map((m, i) => (i === index ? { ...m, saved: true } : m)));
      refreshLearned();
    } catch (err) {
      setMessages((all) => all.map((m, i) => (i === index ? { ...m, error: err instanceof Error ? err.message : "Couldn't save to the Second Brain." } : m)));
    }
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

  handlers.current = { saveToBrain, confirm };

  return (
    <div className="siris">
    <div className="chat siris__main">
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

      <section className={`siris__stage ${messages.length ? "siris__stage--compact" : ""}`} aria-label="Voice">
        <SirisOrb
          state={orb}
          analyser={recording?.analyser}
          size={messages.length ? 104 : 210}
          onClick={talk}
          label={recording ? "Stop listening" : orb === "speaking" ? "Stop speaking" : "Talk to Siris"}
        />
        <div className="siris__status">
          <p className="siris__hint" role="status">{hint}</p>
          <Link to="/brain" className="brain-chip">
            <BrainIcon size={14} aria-hidden="true" />
            {learned ? `${learned.length} learned today` : "Second Brain"} · grows from every chat
          </Link>
        </div>
      </section>

      <div className="chat__log" aria-live="polite">
        {messages.length === 0 && (
          <div className="chat__empty siris__empty">
            <p className="muted">Talk or type. Ask about your day, your home, your projects or anything in your Second Brain.</p>
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
          <Bubble key={i} m={m} index={i} onSave={onSave} onConfirm={onConfirm} />
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
        <button
          type="button"
          className={`icon-link composer__mic ${recording ? "composer__mic--on" : ""}`}
          onClick={talk}
          aria-label={recording ? "Stop listening" : "Talk to Siris"}
          title={voiceBlocked ?? "Talk to Siris"}
        >
          <Mic size={18} aria-hidden="true" />
        </button>
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

    <aside className="siris__rail" aria-label="Siris status">
      <Glass as="section" className="widget" aria-label="Second Brain today">
        <header className="widget__head">
          <BrainIcon aria-hidden="true" />
          <span>Second Brain</span>
          <Link className="widget__source" to="/brain">Open</Link>
        </header>
        {learned === null ? (
          <p className="muted">The Second Brain isn't reachable.</p>
        ) : learned.length === 0 ? (
          <p className="muted">Nothing new yet today. Tonight Siris turns today's conversations into notes.</p>
        ) : (
          <ul className="items">
            {learned.slice(0, 6).map((item) => (
              <li key={item.title} className="item">
                <span className="item__dot" style={{ background: "#a78bfa" }} aria-hidden="true" />
                <span className="item__text">
                  <div className="item__title">{item.title}</div>
                  <div className="item__subtitle">{item.action}</div>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Glass>
      {hud?.system && (
        <Glass as="section" className="widget" aria-label="Systems">
          <header className="widget__head">
            <Cpu aria-hidden="true" />
            <span>Systems</span>
          </header>
          <div className="rings">
            <Ring label="CPU" percent={hud.system.cpu_percent} />
            {hud.system.memory && <Ring label="Memory" percent={hud.system.memory.percent_used} />}
            {hud.system.disk?.["/"] && <Ring label="Disk" percent={hud.system.disk["/"].percent_used} />}
          </div>
        </Glass>
      )}
      {hud?.autonomy && hud.autonomy.length > 0 && (
        <Glass as="section" className="widget" aria-label="Recent activity">
          <header className="widget__head">
            <Activity aria-hidden="true" />
            <span>Recent activity</span>
          </header>
          <ul className="items hud-log">
            {hud.autonomy.slice(-4).reverse().map((e, i) => (
              <li key={`${e.time}-${i}`} className="item">
                <span className="hud-log__time">{e.local_time}</span>
                <span className="item__text">
                  <div className="item__title">{e.what}</div>
                  <div className="item__subtitle">{e.outcome}</div>
                </span>
              </li>
            ))}
          </ul>
        </Glass>
      )}
    </aside>
    </div>
  );
}

/** One chat bubble. Memoised: typing in the composer or streaming the latest
 * reply re-renders only the bubble that changed, not the whole conversation. */
const Bubble = memo(function Bubble({
  m,
  index,
  onSave,
  onConfirm,
}: {
  m: Message;
  index: number;
  onSave: (index: number) => void;
  onConfirm: (index: number, approve: boolean) => void;
}) {
  return (
        <div className={`bubble-row bubble-row--${m.role}`}>
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
            {m.voice && m.role === "user" && <Mic size={13} className="bubble__voice" aria-label="Spoken" />}
            {m.text && <div className="bubble__text">{m.text}</div>}
            {m.streaming && m.status && <div className="bubble__status">{m.status}…</div>}
            {m.error && <div className="tone-critical bubble__status">{m.error}</div>}
            {m.role === "assistant" && !m.streaming && m.text && (
              <div className="bubble__actions">
                {m.saved ? (
                  <span className="tone-good bubble__saved">
                    <Check size={13} aria-hidden="true" /> Saved to Second Brain
                  </span>
                ) : (
                  <button type="button" className="icon-link" onClick={() => onSave(index)} aria-label="Save to Second Brain" title="Save to Second Brain">
                    <BookmarkPlus size={15} aria-hidden="true" />
                  </button>
                )}
              </div>
            )}
            {m.pending && (
              <div className="confirm">
                <p style={{ margin: "0 0 8px" }}>
                  Siris wants to run <strong>{m.pending.name}</strong>
                </p>
                <pre className="confirm__args">{JSON.stringify(m.pending.arguments, null, 2)}</pre>
                <div className="row">
                  <Glass as="button" variant="tint" shape="pill" interactive className="button button--small" onClick={() => onConfirm(index, true)}>
                    <Check aria-hidden="true" /> Allow
                  </Glass>
                  <Glass as="button" shape="pill" interactive className="button button--small" onClick={() => onConfirm(index, false)}>
                    <X aria-hidden="true" /> Cancel
                  </Glass>
                </div>
              </div>
            )}
          </Glass>
        </div>
  );
});

const nextFrame = (fn: () => void): number =>
  typeof requestAnimationFrame === "function" ? requestAnimationFrame(fn) : window.setTimeout(fn, 16);
const cancelFrame = (id: number) => {
  if (!id) return;
  if (typeof cancelAnimationFrame === "function") cancelAnimationFrame(id);
  window.clearTimeout(id);
};
