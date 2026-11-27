import { useState } from "react";
import { Smartphone } from "lucide-react";
import { api } from "../api/client";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

interface TapState { on: boolean; made: string | null; last: string | null; count: number; taps: number; unsorted: number; spent: number }

/** Budget → Apple Pay to the budget (11.16): each Apple Pay purchase sent by an iPhone Shortcuts automation, the moment
 * it's made, into the month's spending. A key for the Shortcut, shown once, that can only add a spend. */
export function ApplePayCard() {
  const res = useResource<TapState>("budget:tap-key", () => api("/api/v1/budget/tap-key"), { staleMs: 60_000 });
  const [key, setKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const s = res.data;
  const on = !!s?.on;
  const url = `${window.location.origin}/api/v1/budget-tap`;
  const make = async () => {
    if (on && !window.confirm("Make a new key? The Shortcut stops logging until you paste the new one into it.")) return;
    setBusy(true);
    try { setKey((await api<{ key: string }>("/api/v1/budget/tap-key", { method: "POST" })).key); await res.reload(true); } finally { setBusy(false); }
  };
  const off = async () => {
    if (!window.confirm("Stop logging Apple Pay taps?")) return;
    setBusy(true);
    try { await api("/api/v1/budget/tap-key", { method: "DELETE" }); setKey(null); await res.reload(true); } finally { setBusy(false); }
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Apple Pay to the budget">
      <header className="widget__head"><Smartphone aria-hidden="true" /><span>Apple Pay to the budget</span>{on && <span className="widget__source tone-good">On</span>}</header>
      <p style={{ margin: 0, fontSize: 14 }}>CommBank has no feed for personal accounts, so each Apple Pay purchase is sent from your iPhone the moment you tap, and goes on the right line here. A NetBank CSV later replaces it with the bank's own line, so nothing counts twice; direct debits and BPAY still come from the CSV.</p>
      {on && s && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          This month: {s.taps} tap{s.taps === 1 ? "" : "s"}, ${Math.round(s.spent).toLocaleString()}{s.unsorted ? `, ${s.unsorted} to sort` : ""}{s.last ? ` · last ${new Date(s.last).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}` : ""}.
        </p>
      )}
      {key && (
        <>
          <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>Copy this key into the Shortcut now: it won't be shown again.</p>
          <code className="gym-key" aria-label="Apple Pay key">{key}</code>
          <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => void navigator.clipboard?.writeText(key)}>Copy the key</button>
        </>
      )}
      <details>
        <summary style={{ fontSize: 14 }}>Set up the automation (iPhone, iOS 17 or later)</summary>
        <ol style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 13 }}>
          <li>Shortcuts → <strong>Automation</strong> → <strong>New Automation</strong> → <strong>Transaction</strong>. Choose your CommBank card(s), and <strong>Run Immediately</strong>.</li>
          <li>Add <strong>Get Contents of URL</strong>: URL <code>{url}</code>, Method <strong>POST</strong>, Header <code>X-SirisOS-Key</code> = your key.</li>
          <li>Request Body <strong>JSON</strong>, three Text fields: <code>merchant</code> = Shortcut Input › <em>Merchant</em>, <code>amount</code> = Shortcut Input › <em>Amount</em>, <code>card</code> = Shortcut Input › <em>Card</em>. (Tap Shortcut Input, then choose the field.)</li>
          <li>Optional: <strong>Get Dictionary Value</strong> for <code>say</code>, then <strong>Show Notification</strong>: "Logged $12.50 at Woolworths on Groceries".</li>
        </ol>
        <p className="muted" style={{ margin: "6px 0 0", fontSize: 12 }}>Away from home it goes through the VPN, so keep WireGuard on demand. A tap that doesn't get through is still in the next NetBank CSV.</p>
      </details>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className={`button ${on ? "" : "button--primary"}`} disabled={busy} onClick={make}>{on ? "Make a new key" : "Make a key"}</button>
        {on && <button type="button" className="chip chip--button" disabled={busy} onClick={off}>Turn off</button>}
      </div>
    </Glass>
  );
}
