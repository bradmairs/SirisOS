import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Bell, Check } from "lucide-react";
import { act, type Act } from "../api/act";
import { Glass } from "../components/Glass";

/** Where a tapped notification lands when it has buttons (3.8). iPhone shows
 * no buttons on notifications, so they're here, one tap away, signed in or not. */
export function ActScreen({ signedIn }: { signedIn: boolean }) {
  const token = new URLSearchParams(useLocation().search).get("t") ?? "";
  const navigate = useNavigate();
  const [data, setData] = useState<Act | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [said, setSaid] = useState<string | null>(null);
  const [needsPin, setNeedsPin] = useState<string | null>(null);
  const [pin, setPin] = useState("");

  useEffect(() => {
    document.title = "Notification · SirisOS";
    act.get(token).then(setData).catch((e) => setError(e.message));
  }, [token]);

  async function press(id: string, withPin?: string) {
    setBusy(id);
    setError(null);
    try {
      setSaid((await act.press(token, id, withPin)).message);
      setNeedsPin(null);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      if (message.includes("pin_required")) setNeedsPin(id);
      else setError(message.replace(/^SirisAI: /, ""));
      if (withPin && /wrong pin|too many wrong pins/i.test(message)) setNeedsPin(id);
    } finally {
      setBusy(null);
      setPin("");
    }
  }

  const pressed = said ?? (data?.done ? `Already done: ${data.actions.find((a) => a.id === data.done)?.title ?? data.done}.` : null);
  return (
    <main className="act-screen">
      <Glass as="section" className="widget act-card" aria-label="Notification">
        <header className="widget__head"><Bell aria-hidden="true" /><span>SirisOS</span></header>
        {!data && !error && <div className="skeleton" style={{ height: 80 }} />}
        {data && (
          <>
            <h1 className="act-card__title">{data.title}</h1>
            {data.body && <p className="muted" style={{ margin: 0 }}>{data.body}</p>}
            {needsPin && !pressed ? (
              <form className="act-card__buttons" aria-label="Approval PIN" onSubmit={(e) => { e.preventDefault(); if (pin) press(needsPin, pin); }}>
                <label className="muted" htmlFor="act-pin" style={{ fontSize: 14 }}>This needs your SirisAI approval PIN.</label>
                <input id="act-pin" className="field" type="password" inputMode="numeric" autoComplete="off" autoFocus maxLength={32}
                  value={pin} onChange={(e) => setPin(e.target.value)} placeholder="PIN" />
                <button type="submit" className="button button--primary" disabled={busy !== null || !pin}>
                  {data.actions.find((a) => a.id === needsPin)?.title ?? "Approve"}
                </button>
              </form>
            ) : pressed ? (
              <p className="tone-good" role="status" style={{ margin: 0 }}><Check size={16} aria-hidden="true" style={{ verticalAlign: "-3px" }} /> {pressed}</p>
            ) : (
              <div className="act-card__buttons">
                {data.actions.map((a, i) => (
                  <button key={a.id} type="button" className={`button ${i === 0 ? "button--primary" : ""}`} disabled={busy !== null} onClick={() => press(a.id)}>
                    {busy === a.id ? "…" : a.title}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
        {error && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>}
        <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }} onClick={() => navigate(signedIn && data ? data.url : "/", { replace: true })}>
          {signedIn ? "Open in SirisOS" : "Sign in to SirisOS"}
        </button>
      </Glass>
    </main>
  );
}
