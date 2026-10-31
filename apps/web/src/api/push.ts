import { api, json } from "./client";

export type Topic = "apps" | "inbox" | "brief" | "career" | "home";

export const TOPIC_LABELS: Record<Topic, string> = {
  apps: "An app goes down",
  inbox: "Alerts and approvals from SirisAI",
  brief: "Your daily brief is ready",
  career: "Career goals due and CPD reminders",
  home: "Home jobs due, warranties, the network and power",
};

export interface DeviceSubscription {
  endpoint: string;
  label: string;
  topics: Topic[];
  created_at: string;
  /** 6.0: when the last notification got through, and the last failure. */
  last_ok?: string | null;
  last_error?: string | null;
  last_error_at?: string | null;
  failing?: boolean;
}

export const push = {
  key: () => api<{ public_key: string; topics: Topic[] }>("/api/v1/push/key"),
  list: () => api<{ subscriptions: DeviceSubscription[] }>("/api/v1/push/subscriptions"),
  subscribe: (sub: PushSubscriptionJSON, label: string, topics: Topic[]) =>
    api<DeviceSubscription>("/api/v1/push/subscribe", json({ endpoint: sub.endpoint, keys: sub.keys, label, topics })),
  unsubscribe: (endpoint: string) => api<{ removed: boolean }>("/api/v1/push/unsubscribe", json({ endpoint })),
  test: (endpoint: string) => api<{ sent: boolean }>("/api/v1/push/test", json({ endpoint })),
};

/** Push works in this browser (on iPhone: only once SirisOS is on the Home Screen). */
export function pushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function isIOS(): boolean {
  return /iPhone|iPad|iPod/.test(navigator.userAgent);
}

export function isStandalone(): boolean {
  return window.matchMedia?.("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export function registerServiceWorker(): void {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => undefined));
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = (base64url + "=".repeat((4 - (base64url.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return (await reg?.pushManager.getSubscription()) ?? null;
}

/** Ask permission, subscribe this browser and register it with SirisOS. */
export async function enablePush(topics: Topic[]): Promise<DeviceSubscription> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Notifications are blocked for SirisOS in this browser's settings.");
  const reg = (await navigator.serviceWorker.getRegistration()) ?? (await navigator.serviceWorker.register("/sw.js"));
  await navigator.serviceWorker.ready;
  const { public_key } = await push.key();
  const sub = (await reg.pushManager.getSubscription()) ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) }));
  return push.subscribe(sub.toJSON(), deviceLabel(), topics);
}

export async function disablePush(): Promise<void> {
  const sub = await currentSubscription();
  if (!sub) return;
  await push.unsubscribe(sub.endpoint).catch(() => undefined);
  await sub.unsubscribe();
}

export function deviceLabel(): string {
  const ua = navigator.userAgent;
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Android/.test(ua)) return "Android";
  if (/Mac/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows PC";
  return "This browser";
}
