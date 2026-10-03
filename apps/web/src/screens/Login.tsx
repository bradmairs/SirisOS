import { useState, type FormEvent } from "react";
import { ArrowRight } from "lucide-react";
import { login } from "../api/client";
import { Glass } from "../components/Glass";
import { Logo } from "../components/Logo";

export function Login({ onLogin }: { onLogin: (user: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
        <input id="username" className="field" placeholder="Username" autoComplete="username" autoCapitalize="none" value={username} onChange={(e) => setUsername(e.target.value)} required />
        <label className="sr-only" htmlFor="password">Password</label>
        <input id="password" className="field" type="password" placeholder="Password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <div className="error-banner" role="alert">{error}</div>}
        <Glass as="button" type="submit" variant="tint" shape="pill" interactive className="button" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"} <ArrowRight aria-hidden="true" />
        </Glass>
      </Glass>
    </main>
  );
}
