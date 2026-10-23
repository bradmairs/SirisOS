import { useEffect, useState } from "react";
import { AlarmClock, Check, Mail, Send } from "lucide-react";
import { email, type DraftReply } from "../api/email";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

function Reply({ reply, onDone }: { reply: DraftReply; onDone: (text: string) => void }) {
  const [text, setText] = useState(reply.draft);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const edited = text.trim() !== reply.draft.trim();

  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setError(null);
    try {
      onDone(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
      setBusy(false);
    }
  }

  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label={`Reply to ${reply.who ?? "email"}: ${reply.subject}`}>
      <header className="widget__head"><Mail aria-hidden="true" /><span>{reply.who ?? "Email"}</span></header>
      <div className="item__title" style={{ whiteSpace: "normal" }}>{reply.subject}</div>
      {reply.snippet && <p className="muted" style={{ margin: 0, fontSize: 14 }}>{reply.snippet}</p>}
      {reply.draft ? (
        <>
          <textarea className="field email__draft" rows={Math.min(10, Math.max(4, text.split("\n").length + 1))} value={text}
            onChange={(e) => setText(e.target.value)} aria-label={`Reply to ${reply.who ?? "them"}`} />
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>
            {edited ? "Edited: the version above is what's sent." : reply.in_drafts_folder ? "SirisAI's draft, also saved in your Drafts folder." : "SirisAI's draft."}
          </p>
        </>
      ) : <p className="muted" style={{ margin: 0, fontSize: 14 }}>No draft for this one: reply from your mail app.</p>}
      {error && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>}
      {confirming ? (
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }} role="group" aria-label="Confirm">
          <span style={{ fontSize: 14 }}>Send this to {reply.who ?? "them"} now?</span>
          <button type="button" className="button button--small button--primary" disabled={busy}
            onClick={() => run(async () => { await email.send(reply.id, text); return `Sent your reply to ${reply.who ?? "them"}`; })}>
            <Send size={14} aria-hidden="true" /> {busy ? "Sending…" : "Send"}
          </button>
          <button type="button" className="button button--small" disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>
        </div>
      ) : (
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          {reply.can_send && reply.draft && (
            <button type="button" className="button button--small button--primary" disabled={busy || !text.trim()} onClick={() => setConfirming(true)}>
              <Send size={14} aria-hidden="true" /> Send{edited ? " edited reply" : ""}
            </button>
          )}
          {(["later", "tomorrow"] as const).map((until) => (
            <button key={until} type="button" className="chip chip--button" disabled={busy}
              onClick={() => run(async () => { await email.snooze(reply.id, until); return `Snoozed ${reply.who ?? "it"} until ${until === "later" ? "later today" : "tomorrow morning"}`; })}>
              <AlarmClock size={13} aria-hidden="true" /> {until === "later" ? "Later" : "Tomorrow"}
            </button>
          ))}
          <button type="button" className="chip chip--button" disabled={busy}
            onClick={() => run(async () => { await email.leave(reply.id); return `Left ${reply.who ?? "it"} for you to handle`; })}>
            I'll handle it
          </button>
        </div>
      )}
    </Glass>
  );
}

/** The replies SirisAI drafted this morning: read, edit, send, snooze or leave them (3.3). */
export function EmailScreen() {
  const res = useResource("email:triage", () => email.triage(), { staleMs: 30_000 });
  const data = res.data ?? null;
  const [note, setNote] = useState<string | null>(null);
  const [gone, setGone] = useState<string[]>([]);
  useEffect(() => {
    document.title = "Email · SirisOS";
  }, []);
  const shown = (data?.replies ?? []).filter((r) => !gone.includes(r.id));

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{data ? (shown.length ? `${shown.length} repl${shown.length === 1 ? "y" : "ies"} drafted` : "All caught up") : "Loading…"}</p>
          <h1 className="page-head__title">Email</h1>
        </div>
      </header>
      {note && <p className="tone-good suggest__done" role="status" style={{ marginTop: 12 }}><Check size={14} aria-hidden="true" /> {note}</p>}
      <div className="stack" style={{ marginTop: 14 }}>
        {!data && !res.error && <div className="skeleton" style={{ height: 180 }} aria-label="Loading" />}
        {data?.unavailable && <p className="muted">SirisAI didn't answer, so its drafted replies can't be shown right now.</p>}
        {data && !data.unavailable && shown.length === 0 && (
          <p className="muted">No replies waiting. Each morning SirisAI drafts replies to the emails that need you, and they show up here.{data.snoozed ? ` ${data.snoozed} snoozed.` : ""}</p>
        )}
        {shown.map((r) => <Reply key={r.id} reply={r} onDone={(text) => { setNote(text); setGone((g) => [...g, r.id]); }} />)}
        {data && data.snoozed > 0 && shown.length > 0 && <p className="muted" style={{ fontSize: 13 }}>{data.snoozed} snoozed; they come back by themselves.</p>}
      </div>
    </>
  );
}
