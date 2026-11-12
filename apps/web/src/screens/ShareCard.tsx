import { useState } from "react";
import { Share } from "lucide-react";
import { useResource } from "../api/resource";
import { shareKey } from "../api/share";
import { Glass } from "../components/Glass";

/** Add to SirisOS from any app's Share Sheet (8.9): a key for one iPhone Shortcut, shown once. */
export function ShareCard() {
  const res = useResource("share-key", () => shareKey.get(), {});
  const [key, setKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const on = !!res.data?.on;
  const url = `${window.location.origin}/api/v1/share`;
  const make = async () => {
    if (on && !window.confirm("Make a new key? The Shortcut using the old one stops working until you paste the new one in.")) return;
    setBusy(true); try { setKey((await shareKey.make()).key); await res.reload(true); } finally { setBusy(false); }
  };
  const drop = async () => { if (!window.confirm("Turn off Add to SirisOS?")) return; setBusy(true); try { await shareKey.drop(); setKey(null); await res.reload(true); } finally { setBusy(false); } };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Add to SirisOS">
      <header className="widget__head"><Share aria-hidden="true" /><span>Add to SirisOS</span>{on && <span className="widget__source tone-good">On</span>}</header>
      <p style={{ margin: 0, fontSize: 14 }}>Share a photo, PDF, link or text from any app. A receipt or bill goes to Life admin (with what you bought added to Things you own), a link or text to Siris, and "todo …" or "remind me …" becomes a task.</p>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>The key can only add things: it can't read, change or delete anything.</p>
      {key && (
        <>
          <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>Copy this key now: it won't be shown again.</p>
          <code className="gym-key" aria-label="Share key">{key}</code>
          <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => void navigator.clipboard?.writeText(key)}>Copy the key</button>
        </>
      )}
      <details>
        <summary style={{ fontSize: 14 }}>Make the Shortcut</summary>
        <ol style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 13 }}>
          <li>In Shortcuts, make one called <strong>Add to SirisOS</strong>. In its settings (ⓘ), turn on <strong>Show in Share Sheet</strong> and let it take Images, PDFs, URLs and Text.</li>
          <li>Add <strong>If</strong> Shortcut Input <em>has any value</em> (so it also works on its own, asking what to add).</li>
          <li>Add <strong>Get Contents of URL</strong>: URL <code>{url}</code>, Method POST, Header <code>X-SirisOS-Key</code> = your key, Request Body <strong>Form</strong>, a <strong>File</strong> field called <code>file</code> set to Shortcut Input.</li>
          <li>For links and text, a second <strong>Get Contents of URL</strong> with Request Body <strong>JSON</strong> and a text field <code>text</code> works too (add <code>task</code> = true to always make a task).</li>
          <li>Add <strong>Get Dictionary Value</strong> for <code>say</code>, then <strong>Show Notification</strong>.</li>
        </ol>
      </details>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className={`button ${on ? "" : "button--primary"}`} disabled={busy} onClick={make}>{on ? "Make a new key" : "Make a key"}</button>
        {on && <button type="button" className="chip chip--button" disabled={busy} onClick={drop}>Turn off</button>}
      </div>
    </Glass>
  );
}
