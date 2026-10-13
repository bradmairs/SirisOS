import { useState, type FormEvent } from "react";
import { ArrowRight, Eye, EyeOff } from "lucide-react";
import { login } from "../api/client";
import { Glass } from "../components/Glass";
import { Logo } from "../components/Logo";

export function Login({ onLogin }: { onLogin: (user: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onLogin(await login(username.trim(), password));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <Glass as="form" variant="strong" shape="xl" className="login__card stack" onSubmit={submit} aria-label="Sign in">
        <div className="login__logo"><Logo size={64} /></div>
        <p className="login__tagline">Your apps, one glass.</p>
        <label className="sr-only" htmlFor="username">Username</label>
        <input id="username" className="field" placeholder="Username" autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false} value={username} onChange={(e) => setUsername(e.target.value)} required />
        <label className="sr-only" htmlFor="password">Password</label>
        <div className="password-field">
          <input id="password" className="field" type={show ? "text" : "password"} placeholder="Password" autoComplete="current-password" autoCapitalize="none" autoCorrect="off" spellCheck={false} value={password} onChange={(e) => setPassword(e.target.value)} required />
          <button type="button" className="icon-link password-field__toggle" onClick={() => setShow((s) => !s)} aria-label={show ? "Hide password" : "Show password"} aria-pressed={show}>
            {show ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
          </button>
        </div>
        {error && (
          <div className="error-banner" role="alert">
            {error}
            {error.startsWith("Incorrect") && <span className="login__hint"> The username and password are case-sensitive; use the eye to check what you typed.</span>}
          </div>
        )}
        <Glass as="button" type="submit" variant="tint" shape="pill" interactive className="button" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"} <ArrowRight aria-hidden="true" />
        </Glass>
      </Glass>
    </main>
  );
}
