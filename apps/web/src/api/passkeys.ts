import { api, json, session } from "./client";

export interface PasskeyInfo {
  id: string;
  label: string;
  rp_id: string;
  created_at: string;
  last_used: string | null;
}

export interface SecurityCheck {
  level: "critical" | "warning" | "info";
  title: string;
  fix: string;
}

function toBytes(b64url: string): ArrayBuffer {
  const padded = (b64url + "=".repeat((4 - (b64url.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out.buffer;
}

function toB64url(buf: ArrayBuffer): string {
  let s = "";
  new Uint8Array(buf).forEach((b) => (s += String.fromCharCode(b)));
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Passkeys work here: the browser has WebAuthn and SirisOS is on a name, not an IP address. */
export function passkeyProblem(): string | null {
  if (typeof window === "undefined" || !window.PublicKeyCredential || !navigator.credentials) return "This browser doesn't support passkeys.";
  if (!window.isSecureContext) return "Passkeys need SirisOS on its HTTPS address.";
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(location.hostname) || location.hostname.includes(":")) {
    return "Passkeys need SirisOS opened on a name (for example its Tailscale name), not an IP address.";
  }
  return null;
}

interface CreateOptions {
  challenge: string;
  rp: { id: string; name: string };
  user: { id: string; name: string; displayName: string };
  pubKeyCredParams: { type: "public-key"; alg: number }[];
  authenticatorSelection: AuthenticatorSelectionCriteria;
  attestation: AttestationConveyancePreference;
  excludeCredentials: { type: "public-key"; id: string }[];
  timeout: number;
}

export const passkeys = {
  list: () => api<{ passkeys: PasskeyInfo[] }>("/api/v1/auth/passkeys"),
  remove: (id: string) => api<{ removed: boolean }>(`/api/v1/auth/passkeys/${encodeURIComponent(id)}`, { method: "DELETE" }),
  checks: () => api<{ checks: SecurityCheck[]; passkeys: number }>("/api/v1/security"),

  /** Make a passkey on this device (Face ID) and register it with SirisOS. */
  async add(label: string): Promise<PasskeyInfo> {
    const o = await api<CreateOptions>("/api/v1/auth/passkeys/register/options", { method: "POST" });
    const cred = (await navigator.credentials.create({
      publicKey: {
        challenge: toBytes(o.challenge),
        rp: o.rp,
        user: { ...o.user, id: toBytes(o.user.id) },
        pubKeyCredParams: o.pubKeyCredParams,
        authenticatorSelection: o.authenticatorSelection,
        attestation: o.attestation,
        excludeCredentials: o.excludeCredentials.map((c) => ({ type: c.type, id: toBytes(c.id) })),
        timeout: o.timeout,
      },
    })) as PublicKeyCredential | null;
    if (!cred) throw new Error("No passkey was made.");
    const r = cred.response as AuthenticatorAttestationResponse;
    return api<PasskeyInfo>("/api/v1/auth/passkeys/register", json({
      challenge: o.challenge,
      id: cred.id,
      label,
      response: { clientDataJSON: toB64url(r.clientDataJSON), attestationObject: toB64url(r.attestationObject) },
    }));
  },

  /** Sign in with a passkey (no username: the device offers its SirisOS passkey). */
  async signIn(): Promise<string> {
    const o = await api<{ challenge: string; rpId: string; userVerification: UserVerificationRequirement; timeout: number }>(
      "/api/v1/auth/passkeys/login/options", { method: "POST" });
    const cred = (await navigator.credentials.get({
      publicKey: { challenge: toBytes(o.challenge), rpId: o.rpId, userVerification: o.userVerification, allowCredentials: [], timeout: o.timeout },
    })) as PublicKeyCredential | null;
    if (!cred) throw new Error("No passkey was chosen.");
    const r = cred.response as AuthenticatorAssertionResponse;
    const token = await api<{ access_token: string; username: string }>("/api/v1/auth/passkeys/login", json({
      challenge: o.challenge,
      id: cred.id,
      response: {
        clientDataJSON: toB64url(r.clientDataJSON),
        authenticatorData: toB64url(r.authenticatorData),
        signature: toB64url(r.signature),
        userHandle: r.userHandle ? toB64url(r.userHandle) : null,
      },
    }));
    session.save(token.access_token, token.username);
    return token.username;
  },
};
