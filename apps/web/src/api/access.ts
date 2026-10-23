import { api, request } from "./client";
import { currentSubscription, isIOS, isStandalone, push, pushSupported } from "./push";

export type CheckState = "good" | "warn" | "bad" | "skip";
export interface Check {
  id: string;
  name: string;
  state: CheckState;
  detail: string;
  /** What to do about it, in plain words. */
  fix?: string;
}

interface ServerView {
  client_ip: string;
  network: "home" | "vpn" | "internet" | "unknown";
  host: string;
  certificate: { host: string; days_left: number | null; error?: string } | null;
  terminal: { enabled: boolean; hosts: { name: string; target: string; ms: number | null; reachable: boolean }[] };
}

const NETWORK: Record<ServerView["network"], string> = {
  home: "the home network",
  vpn: "your VPN (Tailscale)",
  internet: "the internet",
  unknown: "an address SirisOS can't place",
};

const withTimeout = <T,>(p: Promise<T>, ms: number, what: string) =>
  Promise.race([p, new Promise<T>((_, reject) => window.setTimeout(() => reject(new Error(`${what} took over ${ms / 1000} s`)), ms))]);

async function connection(): Promise<[Check, ServerView | null]> {
  const times: number[] = [];
  let view: ServerView | null = null;
  try {
    for (let i = 0; i < 3; i++) {
      const t = performance.now();
      view = await withTimeout(api<ServerView>("/api/v1/access"), 10_000, "SirisOS");
      times.push(performance.now() - t);
    }
  } catch (e) {
    return [{ id: "connection", name: "Reaching SirisOS", state: "bad", detail: e instanceof Error ? e.message : String(e),
      fix: "Check you're on Wi-Fi or mobile data, and that your VPN or tunnel to home is on." }, null];
  }
  const ms = Math.round(times.sort((a, b) => a - b)[1]);
  const slow = ms > 1500;
  return [{
    id: "connection", name: "Reaching SirisOS", state: slow ? "warn" : "good",
    detail: `Through ${NETWORK[view!.network]}${view!.client_ip ? ` (${view!.client_ip})` : ""} · ${ms} ms a request`,
    fix: slow ? "It works, but slowly: screens will take a moment. A weak signal or a far-away VPN exit does this." : undefined,
  }, view];
}

function secure(): Check {
  return window.isSecureContext
    ? { id: "https", name: "Secure connection", state: "good", detail: `HTTPS at ${location.host}` }
    : { id: "https", name: "Secure connection", state: "bad", detail: `Plain HTTP at ${location.host}`,
        fix: "Notifications, passkeys and the microphone need HTTPS. Open SirisOS at its https:// address (port 8444)." };
}

function certificate(view: ServerView | null): Check {
  const c = view?.certificate;
  if (!c || c.days_left == null) return { id: "certificate", name: "Certificate", state: "skip", detail: c?.error ? `Couldn't read it (${c.error})` : "Not checked from here" };
  if (c.days_left < 0) return { id: "certificate", name: "Certificate", state: "bad", detail: "Expired", fix: "Restart the https container (make up) so Caddy renews it." };
  return { id: "certificate", name: "Certificate", state: c.days_left < 21 ? "warn" : "good", detail: `Runs out in ${c.days_left} days`,
    fix: c.days_left < 21 ? "Caddy renews it by itself; if this keeps dropping, restart the https container." : undefined };
}

function app(): Check {
  if (isStandalone()) return { id: "app", name: "Home Screen app", state: "good", detail: "Opened from the Home Screen" };
  return { id: "app", name: "Home Screen app", state: isIOS() ? "warn" : "skip", detail: "Opened in the browser",
    fix: isIOS() ? "On iPhone, notifications only work from the Home Screen app: Share → Add to Home Screen, then open it from there." : undefined };
}

async function offline(): Promise<Check> {
  const reg = "serviceWorker" in navigator ? await navigator.serviceWorker.getRegistration().catch(() => undefined) : undefined;
  return reg?.active
    ? { id: "offline", name: "Works with no signal", state: "good", detail: "The app is kept on this device" }
    : { id: "offline", name: "Works with no signal", state: "warn", detail: "Not set up on this device yet", fix: "Reload SirisOS once; it sets itself up." };
}

/** Sends a test push and waits for the service worker to say it arrived. */
async function notifications(): Promise<Check> {
  if (!pushSupported()) return { id: "push", name: "Notifications", state: "skip", detail: "This browser can't get them" };
  if (Notification.permission === "denied") return { id: "push", name: "Notifications", state: "bad", detail: "Blocked for SirisOS",
    fix: isIOS() ? "Settings → Notifications → SirisOS → Allow Notifications." : "Allow notifications for this site in the browser's settings." };
  const sub = await currentSubscription().catch(() => null);
  if (!sub || Notification.permission !== "granted") return { id: "push", name: "Notifications", state: "warn", detail: "Not turned on for this device",
    fix: "Turn them on under Settings → Notifications in SirisOS." };
  const known = (await push.list().catch(() => ({ subscriptions: [] }))).subscriptions.some((s) => s.endpoint === sub.endpoint);
  if (!known) return { id: "push", name: "Notifications", state: "bad", detail: "SirisOS has forgotten this device", fix: "Turn notifications off and on again in SirisOS." };
  const started = performance.now();
  const arrived = new Promise<number>((resolve) => {
    const on = (e: MessageEvent) => {
      if (e.data?.type === "push" && e.data.tag === "test") {
        navigator.serviceWorker.removeEventListener("message", on);
        resolve(performance.now() - started);
      }
    };
    navigator.serviceWorker.addEventListener("message", on);
  });
  try {
    await push.test(sub.endpoint);
    const ms = await withTimeout(arrived, 20_000, "The test notification");
    return { id: "push", name: "Notifications", state: "good", detail: `A test arrived in ${(ms / 1000).toFixed(1)} s` };
  } catch (e) {
    return { id: "push", name: "Notifications", state: "warn", detail: e instanceof Error ? e.message : String(e),
      fix: "Apple or Google's push service didn't deliver it in time. Check Focus or Do Not Disturb, then try again." };
  }
}

/** Two events 1.5 s apart: arriving together means something buffers live updates. */
async function live(): Promise<Check> {
  const name = "Live updates";
  try {
    const response = await request("/api/v1/access/stream");
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    const at: number[] = [];
    let buffer = "";
    const read = async () => {
      while (at.length < 2) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const n = (buffer.match(/\n\n/g) ?? []).length;
        while (at.length < n) at.push(performance.now());
      }
    };
    await withTimeout(read(), 10_000, "Live updates");
    if (at.length < 2) throw new Error("The stream ended early");
    const gap = at[1] - at[0];
    return gap > 1000
      ? { id: "live", name, state: "good", detail: "The Inbox and chat update as things happen" }
      : { id: "live", name, state: "warn", detail: "Updates arrive in bursts",
          fix: "Something between you and home (a proxy or tunnel) holds updates back. The Inbox still works; it just refreshes late." };
  } catch (e) {
    return { id: "live", name, state: "bad", detail: e instanceof Error ? e.message : String(e), fix: "A proxy on this network is blocking streamed responses." };
  }
}

function websocket(): Promise<Check> {
  const name = "Terminal connection";
  return new Promise((resolve) => {
    let done = false;
    const finish = (c: Check) => { if (!done) { done = true; resolve(c); } };
    let ws: WebSocket;
    try {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v1/terminal/ws?probe=1`);
    } catch {
      return finish({ id: "websocket", name, state: "bad", detail: "This browser refused to open it" });
    }
    const timer = window.setTimeout(() => { ws.close(); finish({ id: "websocket", name, state: "bad", detail: "No answer in 8 s",
      fix: "A firewall or tunnel on the way blocks WebSockets, so the terminal won't connect from here." }); }, 8000);
    ws.onmessage = () => { window.clearTimeout(timer); finish({ id: "websocket", name, state: "good", detail: "WebSockets get through" }); };
    ws.onclose = (e) => { window.clearTimeout(timer); finish(e.code === 4403
      ? { id: "websocket", name, state: "bad", detail: "Refused: the address doesn't match", fix: "Open SirisOS at the same address the proxy forwards (Host header), or fix the proxy's Host setting." }
      : { id: "websocket", name, state: "bad", detail: `Closed before it opened (${e.code})`, fix: "Something on the way blocks WebSockets, so the terminal won't connect from here." }); };
  });
}

function hosts(view: ServerView | null): Check[] {
  if (!view?.terminal.enabled) return [];
  return view.terminal.hosts.map((h) => h.reachable
    ? { id: `ssh:${h.name}`, name: `Terminal host · ${h.name}`, state: "good", detail: `${h.target} answers (${h.ms} ms)` }
    : { id: `ssh:${h.name}`, name: `Terminal host · ${h.name}`, state: "bad", detail: `${h.target} doesn't answer from the server`, fix: "Check the machine is on and SSH is running." });
}

/** Every check, from this device, each reported as it finishes. */
export async function runAccessCheck(onCheck: (c: Check) => void): Promise<void> {
  onCheck(secure());
  onCheck(app());
  const [conn, view] = await connection();
  onCheck(conn);
  if (!view) return;
  onCheck(certificate(view));
  await Promise.all([offline().then(onCheck), live().then(onCheck), websocket().then(onCheck), notifications().then(onCheck)]);
  hosts(view).forEach(onCheck);
}
