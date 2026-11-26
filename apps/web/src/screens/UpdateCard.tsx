import { useEffect, useState } from "react";
import { ArrowUpCircle, CheckCircle2 } from "lucide-react";
import { useResource } from "../api/resource";
import { terminal } from "../api/terminal";
import { updates, type Updates } from "../api/updates";
import { Glass } from "../components/Glass";

/** Update SirisOS from SirisOS (11.11): is there a newer version, and Update now (with the Terminal's 2FA code). The
 * update runs on the server by itself; this page waits for the new version to answer, then loads it. */
export function UpdateCard() {
  const res = useResource<Updates>("updates", (fresh) => updates.get(fresh), { staleMs: 30 * 60_000 });
  const term = useResource("update:terminal", () => terminal.status(), { staleMs: 60_000 });
  const [code, setCode] = useState("");
  const [state, setState] = useState<"idle" | "starting" | "updating" | "done">("idle");
  const [msg, setMsg] = useState<string | null>(null);
  const u = res.data;
  const host = term.data?.hosts?.[0]?.name;
  const twoFactor = !!term.data?.two_factor?.set_up;

  // While updating: ask every 10 seconds; when the new version answers, load it.
  useEffect(() => {
    if (state !== "updating" || !u?.latest) return undefined;
    const target = u.latest;
    const t = window.setInterval(async () => {
      try {
        const now = await updates.get(false);
        res.mutate?.(now);
        if (now.current === target) { setState("done"); window.setTimeout(() => window.location.reload(), 1500); }
      } catch { /* restarting: it's down for a moment */ }
    }, 10_000);
    return () => window.clearInterval(t);
  }, [state, u?.latest]);  // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    if (!host) return;
    setMsg(null);
    setState("starting");
    try {
      const { ticket } = await terminal.unlock(host, code.trim());
      const out = await terminal.run(ticket, updates.command);
      setMsg(out.output?.trim() || "Updating.");
      setCode("");
      setState("updating");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Couldn't start the update.");
      setState("idle");
    }
  };

  if (!u) return null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="SirisOS version">
      <header className="widget__head">{u.newer ? <ArrowUpCircle aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}<span>SirisOS {u.current}</span>
        <button type="button" className="widget__source icon-link" onClick={() => void res.reload(true)}>Check</button></header>
      {u.error && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{u.error}</p>}
      {!u.newer && !u.error && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Up to date{u.latest ? ` (${u.latest} is the newest)` : ""}.</p>}
      {u.newer && (
        <>
          <p style={{ margin: 0 }}><strong>{u.latest} is out</strong>{u.headline ? `: ${u.headline}` : "."}
            {u.notes && <> <a href={u.notes} target="_blank" rel="noreferrer">What's new</a></>}</p>
          {state === "idle" && (host && twoFactor ? (
            <form className="row" style={{ gap: 8, flexWrap: "wrap" }} onSubmit={(e) => { e.preventDefault(); if (code.trim().length >= 6) void start(); }}>
              <input className="field" style={{ width: 130 }} inputMode="numeric" autoComplete="one-time-code" placeholder="2FA code" aria-label="Terminal 2FA code"
                value={code} maxLength={12} onChange={(e) => setCode(e.target.value.replace(/\s/g, ""))} />
              <button type="submit" className="button button--primary" disabled={code.trim().length < 6}>Update now</button>
            </form>
          ) : (
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>Update now needs the Terminal set up with 2FA (Server → Terminal). Until then: <code>make update</code> on the server.</p>
          ))}
          {state === "starting" && <p role="status" style={{ margin: 0 }}>Starting the update…</p>}
          {state === "updating" && <p role="status" style={{ margin: 0 }}>Updating on the server: a few minutes. SirisOS goes away for a moment, then this page loads the new version.</p>}
          {state === "done" && <p role="status" className="tone-good" style={{ margin: 0 }}>Updated to {u.current}. Loading it…</p>}
        </>
      )}
      {msg && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
      {u.log.length > 0 && (state !== "idle" || u.newer) && (
        <details>
          <summary style={{ fontSize: 13 }}>The last update's log</summary>
          <pre className="update-log">{u.log.join("\n")}</pre>
        </details>
      )}
    </Glass>
  );
}
