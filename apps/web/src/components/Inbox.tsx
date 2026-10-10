import { useEffect, useState, useSyncExternalStore } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowUpRight, Bell, CheckCircle2, Clock, Inbox as InboxIcon, Lightbulb, ShieldAlert } from "lucide-react";
import { inbox } from "../api/hub";
import type { InboxAction, InboxCounts, InboxEvent, InboxItem } from "../api/types";
import { Glass } from "./Glass";

/**
 * The inbox (ADR 110): everything that needs Brad, from SirisAI's attention
 * feed (alerts, approvals, suggestions, reviews) and SirisOS's own watch (apps
 * down, overdue tasks, the Archive queue). One live stream serves every
 * component that shows it -- Home, the Inbox screen, the menu badge -- and
 * reconnects by itself (5 s, backing off to 60 s) when the connection drops.
 */

interface State {
  items: InboxItem[];
  counts: InboxCounts;
  connected: boolean;
  loaded: boolean;
}

const SEVERITY_ORDER = { urgent: 0, attention: 1, info: 2 } as const;
let state: State = { items: [], counts: { open: 0, urgent: 0 }, connected: false, loaded: false };
const listeners = new Set<() => void>();
let controller: AbortController | null = null;
let stopTimer: number | null = null;

function set(next: Partial<State>) {
  state = { ...state, ...next };
  listeners.forEach((fn) => fn());
}

function sorted(items: InboxItem[]): InboxItem[] {
  return [...items].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || b.updated_at.localeCompare(a.updated_at));
}

export function applyEvent(items: InboxItem[], event: InboxEvent): InboxItem[] {
  if (event.type === "snapshot") return sorted(event.items);
  const ids = new Set(event.items.map((i) => i.id));
  const rest = items.filter((i) => !ids.has(i.id));
  return sorted(event.type === "upsert" ? [...rest, ...event.items] : rest);
}

function countsOf(items: InboxItem[]): InboxCounts {
  return { open: items.length, urgent: items.filter((i) => i.severity === "urgent").length };
}

async function run(signal: AbortSignal) {
  let delay = 5_000;
  while (!signal.aborted) {
    try {
      for await (const event of inbox.stream(signal)) {
        delay = 5_000;
        const items = applyEvent(state.items, event);
        set({ items, counts: countsOf(items), connected: true, loaded: true });
      }
    } catch {
      if (signal.aborted) return;
      // Fall back to one plain read so the list isn't empty while reconnecting.
      try {
        const now = await inbox.list();
        set({ items: sorted(now.items), counts: now.counts, loaded: true });
      } catch {
        set({ loaded: true });
      }
    }
    set({ connected: false });
    await new Promise((resolve) => window.setTimeout(resolve, delay));
    delay = Math.min(delay * 2, 60_000);
  }
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  if (stopTimer !== null) {
    window.clearTimeout(stopTimer);
    stopTimer = null;
  }
  if (!controller) {
    controller = new AbortController();
    void run(controller.signal);
  }
  return () => {
    listeners.delete(fn);
    if (listeners.size === 0) {
      // A short grace period, so navigating between screens keeps one stream.
      stopTimer = window.setTimeout(() => {
        controller?.abort();
        controller = null;
        stopTimer = null;
      }, 2_000);
    }
  };
}

/** For tests: forget everything and close the stream. */
export function resetInbox() {
  controller?.abort();
  controller = null;
  state = { items: [], counts: { open: 0, urgent: 0 }, connected: false, loaded: false };
}

export function useInbox() {
  const snapshot = useSyncExternalStore(subscribe, () => state);
  /** Do it, then drop the item. Not optimistic: an approval that fails must
   * stay on screen with its error, not vanish and come back. */
  async function act(item: InboxItem, action: string) {
    const result = action === "dismiss" ? await inbox.dismiss(item.id) : await inbox.act(item.id, action);
    const items = state.items.filter((i) => i.id !== item.id);
    set({ items, counts: countsOf(items) });
    return result;
  }
  return { ...snapshot, act };
}

const KIND_ICON = { alert: AlertTriangle, confirm: ShieldAlert, suggestion: Lightbulb, review: InboxIcon, waiting: Clock, notice: Bell } as const;

function linkFor(item: InboxItem): { to?: string; href?: string } {
  if (item.url) return { href: item.url };
  if (item.link?.startsWith("brain")) return { to: "/brain" };
  if (item.link?.startsWith("cameras")) return { to: "/#cameras" };
  return {};
}

export function InboxRow({ item, onAct }: { item: InboxItem; onAct: (item: InboxItem, action: string) => Promise<unknown> }) {
  const [asking, setAsking] = useState<InboxAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const Icon = KIND_ICON[item.kind] ?? Bell;
  const link = linkFor(item);

  async function go(action: string) {
    setBusy(true);
    setError(null);
    try {
      await onAct(item, action);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
      setAsking(null);
    }
  }

  return (
    <li className={`inbox-row inbox-row--${item.severity}`} aria-label={item.title}>
      <Icon className="inbox-row__icon" aria-hidden="true" />
      <div className="inbox-row__text">
        <div className="inbox-row__title">{item.title}</div>
        {item.body && <div className="inbox-row__body">{item.body}</div>}
        <div className="inbox-row__meta">
          {item.app}
          {item.source && item.source !== item.app && item.source !== "hub" ? ` · ${item.source}` : ""}
          {link.href && (
            <a href={link.href} target="_blank" rel="noreferrer" className="inbox-row__open">
              Open <ArrowUpRight size={12} aria-hidden="true" />
            </a>
          )}
          {link.to && <Link to={link.to} className="inbox-row__open">Open</Link>}
        </div>
        {error && <div className="inbox-row__error" role="alert">{error}</div>}
        {asking ? (
          <div className="inbox-row__actions" role="group" aria-label="Confirm">
            <span className="inbox-row__ask">{asking.confirm}</span>
            <button type="button" className={`button button--small button--${asking.style}`} disabled={busy} onClick={() => go(asking.id)}>Yes</button>
            <button type="button" className="button button--small" disabled={busy} onClick={() => setAsking(null)}>Cancel</button>
          </div>
        ) : (
          <div className="inbox-row__actions">
            {item.actions.map((a) => (
              <button key={a.id} type="button" className={`button button--small button--${a.style}`} disabled={busy}
                onClick={() => (a.confirm ? setAsking(a) : go(a.id))}>
                {a.label}
              </button>
            ))}
            {!item.actions.some((a) => a.id === "acknowledge" || a.id === "decline") && (
              <button type="button" className="button button--small button--quiet" disabled={busy} onClick={() => go("dismiss")} aria-label={`Dismiss ${item.title}`}>
                Dismiss
              </button>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

/** Home's "Needs you" section: the top few items, linking to the full inbox. */
export function InboxPanel({ limit = 4 }: { limit?: number }) {
  const { items, counts, act, loaded } = useInbox();
  if (!loaded || items.length === 0) return null;
  return (
    <Glass as="section" className="inbox-panel" aria-label="Needs you">
      <header className="widget__head">
        <InboxIcon aria-hidden="true" />
        <span>Needs you</span>
        {counts.urgent > 0 && <span className="badge badge--urgent">{counts.urgent} urgent</span>}
        {items.length > limit && <Link to="/inbox" className="widget__more">All {items.length}</Link>}
      </header>
      <ul className="inbox-list">
        {items.slice(0, limit).map((item) => <InboxRow key={item.id} item={item} onAct={act} />)}
      </ul>
    </Glass>
  );
}

/** The menu badge: how many open items, red when any is urgent. */
export function InboxBadge() {
  const { counts } = useInbox();
  if (!counts.open) return null;
  return <span className={`badge ${counts.urgent ? "badge--urgent" : ""}`} aria-label={`${counts.open} in the inbox`}>{counts.open}</span>;
}

export function InboxScreen() {
  const { items, act, loaded, connected } = useInbox();
  useEffect(() => {
    document.title = "Inbox · SirisOS";
  }, []);
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{connected ? "Live" : loaded ? "Reconnecting…" : "Connecting…"}</p>
          <h1 className="page-head__title">Inbox</h1>
        </div>
      </header>
      {loaded && items.length === 0 ? (
        <Glass className="widget empty-state">
          <CheckCircle2 aria-hidden="true" />
          <p>Nothing needs you right now.</p>
        </Glass>
      ) : (
        <Glass as="section" className="inbox-panel" aria-label="Inbox">
          <ul className="inbox-list">
            {items.map((item) => <InboxRow key={item.id} item={item} onAct={act} />)}
          </ul>
        </Glass>
      )}
    </>
  );
}
