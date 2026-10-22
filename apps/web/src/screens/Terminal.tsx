import { useEffect, useRef, useState, type FormEvent } from "react";
import { Copy, KeyRound, Lock, ScrollText, Server, ShieldCheck, SquareTerminal } from "lucide-react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { terminal, type TerminalStatus } from "../api/terminal";
import { Glass } from "../components/Glass";

const when = (iso: string) => new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

const EVENTS: Record<string, string> = {
  unlocked: "Unlocked", "session-start": "Terminal opened", "session-end": "Terminal closed", "code-refused": "Wrong code",
  "password-refused": "Wrong password", "2fa-on": "2FA turned on", "2fa-off": "2FA turned off", "2fa-setup-started": "2FA setup started",
  "2fa-reset-on-server": "2FA reset on the server", "host-key-pinned": "Host key remembered", "host-key-forgotten": "Host key forgotten",
};

/** A six-digit code box that suits phone autofill and authenticator apps. */
function CodeField({ value, onChange, label = "6-digit code" }: { value: string; onChange: (v: string) => void; label?: string }) {
  return (
    <input className="field terminal__code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9 ]*" maxLength={7}
      placeholder="123 456" aria-label={label} value={value} onChange={(e) => onChange(e.target.value.replace(/[^0-9 ]/g, ""))} />
  );
}

function Setup2FA({ onDone }: { onDone: () => void }) {
  const [password, setPassword] = useState("");
  const [started, setStarted] = useState<{ secret: string; uri: string; qr_svg: string } | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function begin(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setStarted(await terminal.setup(password));
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }
  async function confirm(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await terminal.confirm(code);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Set up 2FA">
      <header className="widget__head"><ShieldCheck aria-hidden="true" /><span>Set up 2FA for the terminal</span></header>
      {!started ? (
        <form className="stack" style={{ gap: 10 }} onSubmit={begin}>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            Every terminal needs a fresh code from an authenticator app: the iPhone's Passwords app, Google Authenticator or 1Password. Enter your SirisOS password to start.
          </p>
          <input className="field" type="password" autoComplete="current-password" placeholder="SirisOS password" aria-label="SirisOS password"
            value={password} onChange={(e) => setPassword(e.target.value)} />
          <button type="submit" className="button button--small button--primary" disabled={busy || !password}>{busy ? "Checking…" : "Continue"}</button>
        </form>
      ) : (
        <form className="stack" style={{ gap: 10 }} onSubmit={confirm}>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            Scan this with your authenticator app. On this iPhone, <a href={started.uri}>tap here to add it to Passwords</a> instead.
          </p>
          <div className="terminal__qr" aria-label="QR code for your authenticator app" dangerouslySetInnerHTML={{ __html: started.qr_svg }} />
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>Or type this key: <code className="terminal__secret">{started.secret.match(/.{1,4}/g)?.join(" ")}</code></p>
          <CodeField value={code} onChange={setCode} label="First code from the app" />
          <button type="submit" className="button button--small button--primary" disabled={busy || code.replace(/\D/g, "").length !== 6}>{busy ? "Checking…" : "Turn on 2FA"}</button>
        </form>
      )}
      {error && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 14 }}>{error}</p>}
    </Glass>
  );
}

function Unlock({ status, onTicket }: { status: TerminalStatus; onTicket: (host: string, ticket: string) => void }) {
  const [host, setHost] = useState(status.hosts[0]?.name ?? "");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await terminal.unlock(host, code);
      onTicket(host, r.ticket);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
      setCode("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Glass as="form" className="widget" style={{ minHeight: 0 }} onSubmit={submit} aria-label="Unlock the terminal">
      <header className="widget__head"><Lock aria-hidden="true" /><span>Unlock</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        Enter the code from your authenticator app. Each code works once, and a terminal closes after {status.idle_minutes} minutes with no typing.
      </p>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        {status.hosts.length > 1 && (
          <select className="field" style={{ flex: "1 1 140px" }} value={host} onChange={(e) => setHost(e.target.value)} aria-label="Host">
            {status.hosts.map((h) => <option key={h.name} value={h.name}>{h.name} · {h.target}</option>)}
          </select>
        )}
        <CodeField value={code} onChange={setCode} />
        <button type="submit" className="button button--small button--primary" disabled={busy || code.replace(/\D/g, "").length !== 6}>
          <SquareTerminal size={15} aria-hidden="true" /> {busy ? "Checking…" : `Open ${status.hosts.length === 1 ? status.hosts[0].name : "terminal"}`}
        </button>
      </div>
      {error && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 14 }}>{error}</p>}
    </Glass>
  );
}

/** Keys a phone keyboard doesn't have. Ctrl applies to the next key typed. */
const KEYS: { label: string; send?: string; ctrl?: true }[] = [
  { label: "Esc", send: "\x1b" }, { label: "Tab", send: "\t" }, { label: "Ctrl", ctrl: true },
  { label: "↑", send: "\x1b[A" }, { label: "↓", send: "\x1b[B" }, { label: "←", send: "\x1b[D" }, { label: "→", send: "\x1b[C" },
  { label: "|", send: "|" }, { label: "~", send: "~" }, { label: "/", send: "/" }, { label: "-", send: "-" },
];

function Session({ host, ticket, onEnd }: { host: string; ticket: string; onEnd: (message: string) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const socket = useRef<WebSocket | null>(null);
  const ctrl = useRef(false);
  const [ctrlOn, setCtrlOn] = useState(false);
  const [target, setTarget] = useState(host);

  const send = (data: string) => {
    let out = data;
    if (ctrl.current && data.length === 1) {
      const c = data.toUpperCase().charCodeAt(0);
      if (c >= 64 && c <= 95) out = String.fromCharCode(c - 64);
      ctrl.current = false;
      setCtrlOn(false);
    }
    if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify({ type: "input", data: out }));
  };

  useEffect(() => {
    const term = new XTerm({
      cursorBlink: true, fontSize: 14, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", scrollback: 5000,
      theme: { background: "#0b0f17", foreground: "#e6edf3", cursor: "#5fd3ff", selectionBackground: "#5fd3ff55" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(box.current!);
    fit.fit();
    term.focus();
    let ended = "Terminal closed.";
    const ws = new WebSocket(terminal.socketUrl(ticket));
    ws.binaryType = "arraybuffer";
    socket.current = ws;
    const resize = () => {
      try { fit.fit(); } catch { /* hidden */ }
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
    };
    ws.onmessage = (e) => {
      if (typeof e.data !== "string") {
        term.write(new Uint8Array(e.data as ArrayBuffer));
        return;
      }
      const msg = JSON.parse(e.data) as { type: string; message?: string; target?: string };
      if (msg.type === "ready") {
        setTarget(msg.target ?? host);
        resize();
      } else if (msg.message) {
        ended = msg.message;
        term.write(`\r\n\x1b[33m${msg.message}\x1b[0m\r\n`);
      }
    };
    ws.onclose = (e) => {
      if (e.code === 4401) ended = "That unlock expired. Enter a new code.";
      else if (e.code === 4429) ended = "Two terminals are already open. Close one first.";
      else if (e.code === 4403) ended = "The terminal only opens from SirisOS itself.";
      onEnd(ended);
    };
    const typing = term.onData(send);
    const observer = new ResizeObserver(resize);
    observer.observe(box.current!);
    return () => {
      observer.disconnect();
      typing.dispose();
      ws.onclose = null;
      ws.close();
      term.dispose();
    };
    // The ticket is single use: this runs once per unlock.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticket]);

  return (
    <section className="terminal" aria-label={`Terminal on ${host}`}>
      <div className="row terminal__bar">
        <span className="terminal__target"><Server size={14} aria-hidden="true" /> {target}</span>
        <button type="button" className="chip chip--button" onClick={() => { socket.current?.close(); }}>
          <Lock size={13} aria-hidden="true" /> Lock
        </button>
      </div>
      <div className="terminal__screen" ref={box} />
      <div className="terminal__keys" role="toolbar" aria-label="Extra keys">
        {KEYS.map((k) => (
          <button key={k.label} type="button" className={`terminal__key${k.ctrl && ctrlOn ? " terminal__key--on" : ""}`}
            aria-pressed={k.ctrl ? ctrlOn : undefined}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              if (k.ctrl) {
                ctrl.current = !ctrl.current;
                setCtrlOn(ctrl.current);
              } else send(k.send!);
            }}>
            {k.label}
          </button>
        ))}
      </div>
    </section>
  );
}

function Details({ status, onChanged }: { status: TerminalStatus; onChanged: () => void }) {
  const [copied, setCopied] = useState(false);
  const [offOpen, setOffOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function turnOff(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await terminal.off(password, code);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    }
  }

  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Hosts">
        <header className="widget__head"><KeyRound aria-hidden="true" /><span>Hosts and keys</span></header>
        <ul className="items">
          {status.hosts.map((h) => (
            <li key={h.name} className="item">
              <span className="item__text">
                <div className="item__title">{h.name} · {h.target}</div>
                <div className="item__subtitle">{h.host_key ? `Host key ${h.host_key}` : "Not connected yet: its key is remembered on the first connection"}</div>
              </span>
            </li>
          ))}
        </ul>
        {status.public_key && (
          <>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>SirisOS signs in with this key. Add it to <code>~/.ssh/authorized_keys</code> on each host:</p>
            <div className="row" style={{ gap: 8 }}>
              <code className="terminal__pubkey">{status.public_key}</code>
              <button type="button" className="icon-link" aria-label="Copy SirisOS's public key" title="Copy"
                onClick={() => navigator.clipboard.writeText(status.public_key!).then(() => setCopied(true))}>
                <Copy size={15} aria-hidden="true" />
              </button>
            </div>
            {copied && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>Copied.</p>}
          </>
        )}
        {status.two_factor.set_up && (
          offOpen ? (
            <form className="row" style={{ gap: 8, flexWrap: "wrap" }} onSubmit={turnOff}>
              <input className="field" style={{ flex: "1 1 140px" }} type="password" placeholder="SirisOS password" aria-label="SirisOS password" value={password} onChange={(e) => setPassword(e.target.value)} />
              <CodeField value={code} onChange={setCode} />
              <button type="submit" className="button button--small" disabled={!password || code.replace(/\D/g, "").length !== 6}>Turn off 2FA</button>
            </form>
          ) : (
            <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <span className="muted" style={{ fontSize: 13 }}>2FA on{status.two_factor.since ? ` since ${when(status.two_factor.since)}` : ""}.</span>
              <button type="button" className="button button--small" onClick={() => setOffOpen(true)}>Turn off or move to a new phone</button>
            </div>
          )
        )}
        {error && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 14 }}>{error}</p>}
      </Glass>
      {status.activity.length > 0 && (
        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Recent activity">
          <header className="widget__head"><ScrollText aria-hidden="true" /><span>Recent activity</span></header>
          <ul className="items">
            {status.activity.map((a, i) => (
              <li key={`${a.at}-${i}`} className="item">
                <span className={`item__dot${a.event.endsWith("refused") ? " dot-critical" : ""}`} aria-hidden="true" />
                <span className="item__text">
                  <div className="item__title">{EVENTS[a.event] ?? a.event}{a.host ? ` · ${a.host}` : ""}</div>
                  <div className="item__subtitle">{when(a.at)}{a.client ? ` · ${a.client}` : ""}{a.minutes !== undefined ? ` · ${a.minutes} min` : ""}{a.reason && a.reason !== "closed" ? ` · ${a.reason}` : ""}</div>
                </span>
              </li>
            ))}
          </ul>
        </Glass>
      )}
    </>
  );
}

/** A shell on a machine at home (2.8), behind a fresh 2FA code every time. */
export function TerminalScreen() {
  const [status, setStatus] = useState<TerminalStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<{ host: string; ticket: string } | null>(null);
  const [ended, setEnded] = useState<string | null>(null);

  const refresh = () => terminal.status().then(setStatus).catch((err) => setError(err instanceof Error ? err.message : "Couldn't load the terminal."));
  useEffect(() => {
    document.title = "Terminal · SirisOS";
    refresh();
  }, []);

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{open ? "Connected" : status?.two_factor.set_up ? "Locked" : "Home network"}</p>
          <h1 className="page-head__title">Terminal</h1>
        </div>
      </header>
      <div className="stack" style={{ marginTop: 16 }}>
        {error && <p className="tone-critical">{error}</p>}
        {!status && !error && <div className="skeleton" style={{ height: 120 }} aria-label="Loading" />}
        {status && !status.enabled && (
          <Glass as="section" className="widget" style={{ minHeight: 0 }}>
            <header className="widget__head"><SquareTerminal aria-hidden="true" /><span>The terminal is off</span></header>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              To turn it on, set <code>SIRISOS_TERMINAL_HOSTS</code> in SirisOS's <code>.env</code> on the server (for example <code>home=brad@192.168.0.100</code>) and run <code>make up</code>.
              Then add the key from <code>make terminal-key</code> to that user's <code>~/.ssh/authorized_keys</code>.
            </p>
          </Glass>
        )}
        {status?.enabled && status.two_factor.broken && (
          <p className="tone-warning" style={{ margin: 0 }}>SirisOS's sign-in secret changed, so the old 2FA can't be checked. Run <code>make terminal-reset-2fa</code> on the server, then set it up again.</p>
        )}
        {status?.enabled && !status.two_factor.set_up && <Setup2FA onDone={refresh} />}
        {status?.enabled && status.two_factor.set_up && !status.two_factor.broken && (
          open ? (
            <Session host={open.host} ticket={open.ticket} onEnd={(message) => { setOpen(null); setEnded(message); refresh(); }} />
          ) : (
            <>
              {ended && <p className="muted" role="status" style={{ margin: 0 }}>{ended}</p>}
              <Unlock status={status} onTicket={(host, ticket) => { setEnded(null); setOpen({ host, ticket }); }} />
            </>
          )
        )}
        {status?.enabled && !open && <Details status={status} onChanged={refresh} />}
      </div>
    </>
  );
}
