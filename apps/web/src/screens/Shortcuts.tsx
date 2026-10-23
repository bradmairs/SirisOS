import { useEffect, useState, type ReactNode } from "react";
import { Copy, KeyRound, LayoutGrid, Link2, Plus, Smartphone, Trash2, Wand2 } from "lucide-react";
import { shortcuts, type ShortcutKey, type ShortcutScope } from "../api/shortcuts";
import { Glass } from "../components/Glass";

const SCOPE_LABELS: Record<ShortcutScope, string> = {
  capture: "Capture to Siris",
  ask: "Ask SirisAI",
  today: "Read today's brief",
  protocols: "Run protocols (Wind Down, Lockdown…)",
};

function Card({ title, Icon, children }: { title: string; Icon: typeof Smartphone; children: ReactNode }) {
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label={title}>
      <header className="widget__head"><Icon aria-hidden="true" /><span>{title}</span></header>
      {children}
    </Glass>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className="icon-link" aria-label={label} title={label}
      onClick={() => navigator.clipboard?.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1500); }).catch(() => undefined)}>
      {done ? <span className="tone-good" style={{ fontSize: 12 }}>Copied</span> : <Copy size={15} aria-hidden="true" />}
    </button>
  );
}

/** Siris on the iPhone: links that open SirisOS where you want it, keys for
 * Apple Shortcuts (which can't sign in), and ready-made Shortcut recipes. */
export function ShortcutsScreen() {
  const origin = window.location.origin;
  const [keys, setKeys] = useState<ShortcutKey[] | null>(null);
  const [label, setLabel] = useState("iPhone");
  const [scopes, setScopes] = useState<ShortcutScope[]>(["capture", "ask", "today"]);
  const [fresh, setFresh] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "iPhone shortcuts · SirisOS";
    shortcuts.keys().then((r) => setKeys(r.keys)).catch((e) => setError(e.message));
  }, []);

  async function create() {
    setError(null);
    try {
      const made = await shortcuts.create(label, scopes);
      setFresh(made.secret);
      setKeys((k) => [...(k ?? []), made]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  async function revoke(id: string) {
    setKeys((k) => (k ?? []).filter((x) => x.id !== id));
    await shortcuts.revoke(id).catch(() => undefined);
  }

  const links = [
    { label: "Quick capture", url: `${origin}/capture` },
    { label: "Ask SirisAI", url: `${origin}/assistant` },
    { label: "This week", url: `${origin}/week` },
    { label: "Today's brief", url: `${origin}/brief` },
  ];
  const key = fresh ?? "sk_…your key…";
  const recipes = [
    { title: "Capture to Siris", say: "“Hey Siri, capture”", steps: [
      "Dictate Text",
      `Get Contents of URL: ${origin}/api/v1/shortcuts/capture · Method POST · Header Authorization: Bearer ${key} · Request Body: File → Dictated Text`,
      "Show Result",
    ] },
    { title: "Ask SirisAI", say: "“Hey Siri, ask SirisAI”", steps: [
      "Dictate Text",
      `Get Contents of URL: ${origin}/api/v1/shortcuts/ask · Method POST · same header · Request Body: File → Dictated Text`,
      "Speak Text: Contents of URL",
    ] },
    { title: "My day", say: "“Hey Siri, my day”", steps: [
      `Get Contents of URL: ${origin}/api/v1/shortcuts/today · same header`,
      "Speak Text: Contents of URL",
    ] },
    { title: "Wind Down", say: "“Hey Siri, wind down” (needs a key with Run protocols)", steps: [
      `Get Contents of URL: ${origin}/api/v1/shortcuts/protocols/wind_down · Method POST · same header`,
      "Show Result",
    ] },
  ];

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">Siris on your iPhone</p>
          <h1 className="page-head__title">iPhone shortcuts</h1>
        </div>
      </header>
      <div className="stack" style={{ marginTop: 16 }}>
        <Card title="Open SirisOS right where you want" Icon={Link2}>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            In Shortcuts, make a shortcut with <b>Open URLs</b> and one of these, then Share → <b>Add to Home Screen</b>. It opens in the SirisOS app if it's on your Home Screen.
          </p>
          <ul className="items">
            {links.map((l) => (
              <li key={l.url} className="item">
                <span className="item__text"><div className="item__title">{l.label}</div><div className="item__subtitle shortcut-url">{l.url}</div></span>
                <CopyButton text={l.url} label={`Copy the ${l.label} link`} />
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Shortcut keys" Icon={KeyRound}>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            Shortcuts can't sign in, so they use a key. Give each key only what it needs; revoke it here if a phone is lost.
          </p>
          {fresh && (
            <div className="shortcut-secret" role="status">
              <p style={{ margin: 0, fontSize: 14 }}><b>Copy this key now.</b> It won't be shown again.</p>
              <div className="row" style={{ gap: 6 }}>
                <code>{fresh}</code>
                <CopyButton text={fresh} label="Copy the new key" />
              </div>
            </div>
          )}
          <ul className="items">
            {keys?.map((k) => (
              <li key={k.id} className="item">
                <span className="item__text">
                  <div className="item__title">{k.label}</div>
                  <div className="item__subtitle">{k.scopes.map((s) => SCOPE_LABELS[s]).join(" · ")} · {k.last_used ? `last used ${new Date(k.last_used).toLocaleDateString()}` : "not used yet"}</div>
                </span>
                <button type="button" className="icon-link" onClick={() => revoke(k.id)} aria-label={`Revoke ${k.label}`}><Trash2 size={15} aria-hidden="true" /></button>
              </li>
            ))}
          </ul>
          <div className="stack" style={{ gap: 8 }}>
            <input className="field" value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Key name" placeholder="Key name, e.g. iPhone" />
            {(Object.keys(SCOPE_LABELS) as ShortcutScope[]).map((s) => (
              <label key={s} className="notify__topic">
                <input type="checkbox" checked={scopes.includes(s)} onChange={() => setScopes((x) => (x.includes(s) ? x.filter((y) => y !== s) : [...x, s]))} />
                <span>{SCOPE_LABELS[s]}</span>
              </label>
            ))}
            <button type="button" className="button button--small button--primary" style={{ alignSelf: "flex-start" }} disabled={scopes.length === 0} onClick={create}>
              <Plus size={15} aria-hidden="true" /> New key
            </button>
          </div>
          {error && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>}
        </Card>

        <WidgetScript origin={origin} keyText={key} />

        <Card title="Ready-made Shortcuts" Icon={Wand2}>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>Make each in the Shortcuts app with these actions; name it what you'll say to Siri.{fresh ? " Your new key is filled in below." : ""}</p>
          {recipes.map((r) => (
            <div key={r.title} className="shortcut-recipe">
              <div className="item__title">{r.title} <span className="muted" style={{ fontWeight: 400 }}>· {r.say}</span></div>
              <ol>{r.steps.map((s) => <li key={s}>{s}</li>)}</ol>
            </div>
          ))}
        </Card>
      </div>
    </>
  );
}

/** A Scriptable script for an iPhone home-screen widget (3.6): next event, top task, what needs you. */
export function widgetScript(origin: string, key: string): string {
  return `// SirisOS home-screen widget for Scriptable. Read-only: needs a key with "Today".
const URL = "${origin}";
const KEY = "${key}";
const req = new Request(URL + "/api/v1/shortcuts/glance");
req.headers = { Authorization: "Bearer " + KEY };
req.allowInsecureRequest = true; // SirisOS's own HTTPS certificate is self-signed
let d = null;
try { d = await req.loadJSON(); } catch (e) {}
const w = new ListWidget();
w.backgroundColor = new Color("#0b0f17");
w.url = URL;
const line = (text, size, color) => { const t = w.addText(text); t.font = Font.semiboldSystemFont(size); t.textColor = new Color(color); t.lineLimit = 2; };
line("SIRISOS", 10, "#5fd3ff");
w.addSpacer(4);
if (!d || d.detail) {
  line("Can't reach SirisOS", 12, "#ff6b6b");
} else {
  if (d.next_event) {
    line(d.next_event.title, 14, "#e6edf3");
    line(new Date(d.next_event.start).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }), 11, "#9aa4b2");
  } else line("Nothing else on today", 13, "#9aa4b2");
  w.addSpacer(6);
  if (d.top_task) line("○ " + d.top_task + (d.tasks_today > 1 ? "  +" + (d.tasks_today - 1) : ""), 12, "#e6edf3");
  if (d.needs_you) line(d.needs_you + (d.needs_you === 1 ? " thing needs" : " things need") + " you", 11, "#ffb454");
}
Script.setWidget(w);
Script.complete();
`;
}

function WidgetScript({ origin, keyText }: { origin: string; keyText: string }) {
  const [copied, setCopied] = useState(false);
  const script = widgetScript(origin, keyText);
  return (
    <Card title="Home-screen widget" Icon={LayoutGrid}>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        Your next event, the top task and what needs you, right on the home screen. Install the free <strong>Scriptable</strong> app, make a new script, paste this in, then add a Scriptable widget and pick the script. It needs a key with <strong>Today</strong>.
      </p>
      <pre className="terminal__output" style={{ maxHeight: 180 }}>{script}</pre>
      <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }}
        onClick={() => navigator.clipboard.writeText(script).then(() => setCopied(true))}>
        <Copy size={14} aria-hidden="true" /> {copied ? "Copied" : "Copy the script"}
      </button>
    </Card>
  );
}
