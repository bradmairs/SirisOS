import { useEffect, useState } from "react";
import { AlertTriangle, Fingerprint, Info, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { passkeyProblem, passkeys, type PasskeyInfo, type SecurityCheck } from "../api/passkeys";
import { deviceLabel } from "../api/push";
import { Glass } from "../components/Glass";

const ICON = { critical: AlertTriangle, warning: AlertTriangle, info: Info } as const;
const TONE = { critical: "tone-critical", warning: "tone-warning", info: "muted" } as const;

/** Passkeys (Face ID sign-in) and a check of this install's security settings. */
export function SecurityScreen() {
  const [items, setItems] = useState<PasskeyInfo[] | null>(null);
  const [checks, setChecks] = useState<SecurityCheck[] | null>(null);
  const [label, setLabel] = useState(deviceLabel());
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const problem = passkeyProblem();

  const refresh = () => {
    passkeys.list().then((r) => setItems(r.passkeys)).catch(() => setItems([]));
    passkeys.checks().then((r) => setChecks(r.checks)).catch(() => setChecks([]));
  };
  useEffect(() => {
    document.title = "Security · SirisOS";
    refresh();
  }, []);

  async function add() {
    setBusy(true);
    setNote(null);
    try {
      const made = await passkeys.add(label.trim() || deviceLabel());
      setNote({ ok: true, text: `Added “${made.label}”. Next time, sign in with a passkey.` });
      refresh();
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      setNote({ ok: false, text: name === "NotAllowedError" ? "Cancelled." : name === "InvalidStateError" ? "This device already has a SirisOS passkey." : err instanceof Error ? err.message : "Couldn't add it." });
    } finally {
      setBusy(false);
    }
  }
  async function remove(id: string) {
    setItems((x) => (x ?? []).filter((p) => p.id !== id));
    await passkeys.remove(id).catch(() => undefined);
    refresh();
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{checks ? (checks.some((c) => c.level === "critical") ? "Needs attention" : "Looks good") : "Checking…"}</p>
          <h1 className="page-head__title">Security</h1>
        </div>
      </header>
      <div className="stack" style={{ marginTop: 16 }}>
        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Passkeys">
          <header className="widget__head"><Fingerprint aria-hidden="true" /><span>Passkeys</span></header>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>Sign in with Face ID or Touch ID instead of the password. A passkey stays on your devices (and in iCloud Keychain); SirisOS only keeps its public half.</p>
          {problem && <p className="tone-warning" style={{ margin: 0, fontSize: 14 }}>{problem}</p>}
          <ul className="items">
            {items?.map((p) => (
              <li key={p.id} className="item">
                <span className="item__text">
                  <div className="item__title">{p.label}</div>
                  <div className="item__subtitle">{p.rp_id} · added {new Date(p.created_at).toLocaleDateString()} · {p.last_used ? `last used ${new Date(p.last_used).toLocaleDateString()}` : "not used yet"}</div>
                </span>
                <button type="button" className="icon-link" onClick={() => remove(p.id)} aria-label={`Remove ${p.label}`}><Trash2 size={15} aria-hidden="true" /></button>
              </li>
            ))}
          </ul>
          {!problem && (
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <input className="field" style={{ flex: "1 1 160px" }} value={label} onChange={(e) => setLabel(e.target.value)} aria-label="Passkey name" />
              <button type="button" className="button button--small button--primary" onClick={add} disabled={busy}>
                <Plus size={15} aria-hidden="true" /> {busy ? "Waiting for Face ID…" : "Add a passkey"}
              </button>
            </div>
          )}
          {note && <p className={note.ok ? "tone-good" : "tone-critical"} role="status" style={{ margin: 0, fontSize: 14 }}>{note.text}</p>}
        </Glass>

        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Settings check">
          <header className="widget__head"><ShieldCheck aria-hidden="true" /><span>Settings check</span></header>
          {checks?.length === 0 && <p className="tone-good" style={{ margin: 0 }}>Nothing to fix.</p>}
          <ul className="items">
            {checks?.map((c) => {
              const Icon = ICON[c.level];
              return (
                <li key={c.title} className="item">
                  <Icon size={15} className={TONE[c.level]} aria-hidden="true" />
                  <span className="item__text"><div className="item__title">{c.title}</div><div className="item__subtitle">{c.fix}</div></span>
                </li>
              );
            })}
          </ul>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>Wrong passwords are limited to 8 every 15 minutes from one device. Shortcut keys are managed on the iPhone shortcuts screen.</p>
        </Glass>
      </div>
    </>
  );
}
