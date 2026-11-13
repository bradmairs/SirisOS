import { useEffect, useState } from "react";
import { Smartphone } from "lucide-react";
import { glance, widgetScript } from "../api/glance";
import { Glass } from "../components/Glass";

/** The iPhone widget (9.3): a read-only key for its feed, and the Scriptable script to paste. A new key stops the old. */
export function PhoneWidgetCard() {
  const [status, setStatus] = useState<{ set: boolean; created: string | null } | null>(null);
  const [key, setKey] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { glance.status().then(setStatus).catch(() => setStatus(null)); }, []);
  const url = key ? `${window.location.origin}/api/v1/glance?key=${encodeURIComponent(key)}` : null;
  const copy = async (text: string, what: string) => { try { await navigator.clipboard.writeText(text); setMsg(`${what} copied.`); } catch { setMsg("Couldn't copy: select it and copy by hand."); } };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="iPhone widget">
      <header className="widget__head"><Smartphone aria-hidden="true" /><span>iPhone widget</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>A Home Screen widget with the next event, tasks, readiness, your next workout, habits, a renewal due and a live rest timer. It reads from SirisOS with its own key, which can only read this summary.</p>
      {status?.set && !key && <p style={{ margin: 0, fontSize: 13 }}>A widget key is in use (made {status.created?.slice(0, 10)}).</p>}
      {url && (
        <div className="stack" style={{ gap: 6 }}>
          <p className="tone-warning" style={{ margin: 0, fontSize: 13 }}>Shown once. Copy the script now.</p>
          <ol className="mind-list" style={{ fontSize: 13 }}>
            <li>Install Scriptable from the App Store and make a new script.</li>
            <li>Paste the script below into it.</li>
            <li>Add a Scriptable widget to the Home Screen; long-press it, Edit Widget, and choose the script.</li>
          </ol>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="button button--primary" onClick={() => copy(widgetScript(url), "The script")}>Copy the script</button>
            <button type="button" className="button" onClick={() => copy(url, "The address")}>Copy the address only</button>
          </div>
        </div>
      )}
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="chip chip--button" onClick={async () => {
          if (status?.set && !window.confirm("Make a new key? The widget using the old one stops until you paste the new script.")) return;
          try { setKey((await glance.newKey()).key); setStatus({ set: true, created: new Date().toISOString() }); setMsg(null); } catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't make a key."); }
        }}>{status?.set ? "New key" : "Set up the widget"}</button>
        {status?.set && <button type="button" className="chip chip--button" onClick={async () => { await glance.stop(); setStatus({ set: false, created: null }); setKey(null); setMsg("The widget's key is stopped."); }}>Stop the widget</button>}
      </div>
      {msg && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
    </Glass>
  );
}
