import { useEffect, useState } from "react";
import { BellOff, BellRing, Send } from "lucide-react";
import { TOPIC_LABELS, currentSubscription, disablePush, enablePush, isIOS, isStandalone, push, pushSupported, type DeviceSubscription, type Topic } from "../api/push";
import { Glass } from "./Glass";

const ALL: Topic[] = ["apps", "inbox", "brief", "career", "home", "nudges", "gym"];

type Delivery = { last_ok?: string | null; last_error?: string | null; failing?: boolean };
type State = { kind: "checking" } | { kind: "unsupported" } | { kind: "off" } | { kind: "on"; endpoint: string; topics: Topic[]; delivery?: Delivery };

const ago = (iso: string) => {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  return mins < 60 ? `${Math.max(mins, 1)} min ago` : mins < 48 * 60 ? `${Math.round(mins / 60)} h ago` : `${Math.round(mins / 1440)} days ago`;
};

/** "Notifications on this device": turn phone notifications on or off and
 * pick what they're for. Each device (phone, Mac...) is set up on its own. */
export function NotificationSettings() {
  const [state, setState] = useState<State>({ kind: "checking" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [topics, setTopics] = useState<Topic[]>(ALL);

  useEffect(() => {
    let live = true;
    (async () => {
      if (!pushSupported()) return live && setState({ kind: "unsupported" });
      const sub = await currentSubscription().catch(() => null);
      if (!sub) return live && setState({ kind: "off" });
      const known = await push.list().catch(() => null);
      const mine = known?.subscriptions.find((s) => s.endpoint === sub.endpoint);
      if (live) setState(mine ? { kind: "on", endpoint: sub.endpoint, topics: mine.topics, delivery: mine } : { kind: "off" });
    })();
    return () => {
      live = false;
    };
  }, []);

  async function run(job: () => Promise<void>) {
    setBusy(true);
    setMessage(null);
    try {
      await job();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const turnOn = () => run(async () => {
    const sub = await enablePush(topics);
    setState({ kind: "on", endpoint: sub.endpoint, topics: sub.topics });
  });
  const turnOff = () => run(async () => {
    await disablePush();
    setState({ kind: "off" });
  });
  const toggle = (topic: Topic) => {
    if (state.kind !== "on") {
      setTopics((t) => (t.includes(topic) ? t.filter((x) => x !== topic) : [...t, topic]));
      return;
    }
    const next = state.topics.includes(topic) ? state.topics.filter((x) => x !== topic) : [...state.topics, topic];
    run(async () => {
      const sub = await enablePush(next);
      setState({ kind: "on", endpoint: sub.endpoint, topics: sub.topics });
    });
  };
  const test = () => run(async () => {
    if (state.kind === "on") await push.test(state.endpoint);
    setMessage("Sent. It should arrive in a few seconds.");
  });

  const chosen = state.kind === "on" ? state.topics : topics;

  return (
    <Glass as="section" className="widget notify" aria-label="Notifications on this device">
      <header className="widget__head">
        {state.kind === "on" ? <BellRing aria-hidden="true" /> : <BellOff aria-hidden="true" />}
        <span>Notifications on this device</span>
      </header>
      {state.kind === "checking" && <p className="muted" style={{ margin: 0 }}>Checking…</p>}
      {state.kind === "unsupported" && (
        <p className="muted" style={{ margin: 0 }}>
          {isIOS() && !isStandalone()
            ? "On iPhone, add SirisOS to your Home Screen first (Share → Add to Home Screen), then open it from there and turn notifications on."
            : "This browser can't receive notifications."}
        </p>
      )}
      {(state.kind === "off" || state.kind === "on") && (
        <>
          <ul className="notify__topics">
            {ALL.map((topic) => (
              <li key={topic}>
                <label className="notify__topic">
                  <input type="checkbox" checked={chosen.includes(topic)} disabled={busy} onChange={() => toggle(topic)} />
                  <span>{TOPIC_LABELS[topic]}</span>
                </label>
              </li>
            ))}
          </ul>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            {state.kind === "off" ? (
              <button type="button" className="button button--small button--primary" disabled={busy || topics.length === 0} onClick={turnOn}>
                <BellRing size={15} aria-hidden="true" /> Turn on notifications
              </button>
            ) : (
              <>
                <button type="button" className="button button--small" disabled={busy} onClick={test}>
                  <Send size={15} aria-hidden="true" /> Send a test
                </button>
                <button type="button" className="button button--small" disabled={busy} onClick={turnOff}>
                  <BellOff size={15} aria-hidden="true" /> Turn off
                </button>
              </>
            )}
          </div>
        </>
      )}
      {state.kind === "on" && state.delivery?.failing && (
        <p role="alert" className="tone-critical" style={{ margin: 0, fontSize: 14 }}>
          Notifications aren't reaching this device: {state.delivery.last_error}. Turn them off and on again.
        </p>
      )}
      {state.kind === "on" && !state.delivery?.failing && state.delivery?.last_ok && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>Last one went out {ago(state.delivery.last_ok)}.</p>
      )}
      {message && <p className="muted" role="status" style={{ margin: 0 }}>{message}</p>}
      <Devices current={state.kind === "on" ? state.endpoint : null} />
    </Glass>
  );
}


/** 7.9: every device SirisOS sends to. Two of the same phone means each notification arrives twice: remove the old one. */
function Devices({ current }: { current: string | null }) {
  const [list, setList] = useState<DeviceSubscription[] | null>(null);
  const load = () => push.list().then((r) => setList(r.subscriptions)).catch(() => setList(null));
  useEffect(() => { load(); }, [current]);
  if (!list || list.length < 2) return null;
  const same = list.filter((d) => d.label === list.find((x) => x.endpoint === current)?.label).length > 1;
  return (
    <section aria-label="Devices getting notifications" className="stack" style={{ gap: 6 }}>
      <h3 className="maint__h" style={{ margin: "6px 0 0" }}>Devices getting notifications</h3>
      {same && <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>This {list.find((x) => x.endpoint === current)?.label ?? "device"} is listed more than once, so notifications can arrive twice. Remove the one that isn't this device (unless it's someone else's).</p>}
      <ul className="items">
        {list.map((d) => (
          <li key={d.endpoint} className="item">
            <span className="item__text">
              <span className="item__title">{d.label || "A device"}{d.endpoint === current ? " (this device)" : ""}</span>
              <span className="item__subtitle">Added {d.created_at.slice(0, 10)}{d.last_ok ? ` · last delivered ${d.last_ok.slice(0, 10)}` : ""}</span>
            </span>
            {d.endpoint !== current && (
              <button type="button" className="button button--small" aria-label={`Remove ${d.label} added ${d.created_at.slice(0, 10)}`}
                onClick={async () => { await push.unsubscribe(d.endpoint).catch(() => undefined); load(); }}>Remove</button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
