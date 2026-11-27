import { useState } from "react";
import { MessageCircleQuestion } from "lucide-react";
import { useResource } from "../api/resource";
import { askKey } from "../api/ask";
import { Glass } from "../components/Glass";

/** Ask Siris from anywhere (11.16): the Action Button or "Hey Siri, Ask Siris" runs a Shortcut that asks SirisAI
 * and speaks the answer. A key for that one Shortcut, shown once. */
export function AskCard() {
  const res = useResource("ask-key", () => askKey.get(), {});
  const [key, setKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const on = !!res.data?.on;
  const url = `${window.location.origin}/api/v1/ask`;
  const make = async () => {
    if (on && !window.confirm("Make a new key? The Shortcut using the old one stops working until you paste the new one in.")) return;
    setBusy(true); try { setKey((await askKey.make()).key); await res.reload(true); } finally { setBusy(false); }
  };
  const drop = async () => { if (!window.confirm("Turn off Ask Siris?")) return; setBusy(true); try { await askKey.drop(); setKey(null); await res.reload(true); } finally { setBusy(false); } };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Ask Siris">
      <header className="widget__head"><MessageCircleQuestion aria-hidden="true" /><span>Ask Siris</span>{on && <span className="widget__source tone-good">On</span>}</header>
      <p style={{ margin: 0, fontSize: 14 }}>Ask SirisAI anything from your iPhone, at home or away: press the Action Button (or say "Hey Siri, Ask Siris"), speak, and hear the answer. A question within ten minutes carries on the same conversation.</p>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>This key can ask anything you could ask in the app, and SirisAI can do everyday things with it (lights, timers). It can never approve anything: what needs your OK waits for you here. Keep it only in that Shortcut; make a new one if your phone is lost.</p>
      {key && (
        <>
          <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>Copy this key now: it won't be shown again.</p>
          <code className="gym-key" aria-label="Ask key">{key}</code>
          <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => void navigator.clipboard?.writeText(key)}>Copy the key</button>
        </>
      )}
      <details>
        <summary style={{ fontSize: 14 }}>Make the Shortcut</summary>
        <ol style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 13 }}>
          <li>In Shortcuts, make one called <strong>Ask Siris</strong>.</li>
          <li>Add <strong>Dictate Text</strong> (Stop Listening: After Pause).</li>
          <li>Add <strong>Get Contents of URL</strong>: URL <code>{url}</code>, Method POST, Header <code>X-SirisOS-Key</code> = your key, Request Body <strong>JSON</strong> with a text field <code>text</code> set to Dictated Text.</li>
          <li>Add <strong>Get Dictionary Value</strong> for <code>say</code>, then <strong>Speak Text</strong> (or <strong>Show Result</strong>).</li>
          <li>In Settings → Action Button, choose <strong>Shortcut</strong> → Ask Siris. "Hey Siri, Ask Siris" works too.</li>
        </ol>
      </details>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className={`button ${on ? "" : "button--primary"}`} disabled={busy} onClick={make}>{on ? "Make a new key" : "Make a key"}</button>
        {on && <button type="button" className="chip chip--button" disabled={busy} onClick={drop}>Turn off</button>}
      </div>
    </Glass>
  );
}
