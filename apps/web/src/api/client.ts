import { clearResources } from "./resource";

const TOKEN_KEY = "sirisos.token";
const USER_KEY = "sirisos.user";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export const session = {
  token(): string | null {
    return storage()?.getItem(TOKEN_KEY) ?? null;
  },
  user(): string | null {
    return storage()?.getItem(USER_KEY) ?? null;
  },
  save(token: string, user: string) {
    storage()?.setItem(TOKEN_KEY, token);
    storage()?.setItem(USER_KEY, user);
  },
  clear() {
    storage()?.removeItem(TOKEN_KEY);
    storage()?.removeItem(USER_KEY);
    // Never show the previous session's data to the next sign-in.
    clearResources();
  },
};

type Listener = () => void;
const unauthorisedListeners = new Set<Listener>();
export function onUnauthorised(fn: Listener): () => void {
  unauthorisedListeners.add(fn);
  return () => unauthorisedListeners.delete(fn);
}

async function detail(response: Response): Promise<string> {
  try {
    const body = await response.clone().json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {
    /* not JSON */
  }
  return response.statusText || `HTTP ${response.status}`;
}

/**
 * 11.4: everyday edits that can wait for a connection. With no connection, one of these is kept on the phone (the
 * outbox) and sent, in order, when SirisOS can be reached; the caller gets {queued: true}. Anything that controls a
 * device, approves something, runs a command, signs in or uploads a file is never queued: hours later it could be
 * wrong. Each has a label for the "waiting" list.
 */
const QUEUEABLE: [RegExp, string][] = [
  [/^\/api\/v1\/tasks(\/|$|\?)/, "A task change"],
  [/^\/api\/v1\/mind\/habits\//, "A habit"],
  [/^\/api\/v1\/mind\/(journal|mood|log|checkin)/, "Journal or mood"],
  [/^\/api\/v1\/health\/(log|goals)/, "A health log"],
  [/^\/api\/v1\/wrapup(\/|$)/, "The wrap-up"],
  [/^\/api\/v1\/work\/(timesheet|focus|todo-done|wrapup|cpd)/, "Work"],
  [/^\/api\/v1\/meals(\/|$|\?)/, "Meals"],
  [/^\/api\/v1\/budget\/(actuals\/(?!import)|balances|accounts|recurring)/, "Budget"],
  [/^\/api\/v1\/gym\/(routines|settings|exercises|gyms|bodyweight|measurements)/, "SirisGym"],
  [/^\/api\/v1\/brain\/(edit|done)$/, "A Siris note"],
  [/^\/api\/v1\/career\/cpd/, "CPD"],
  [/^\/api\/v1\/goals(\/|$)/, "Goals"],
  [/^\/api\/v1\/(weekend\/routes|bins|garden\/watered|catchups)/, "Around the week"],
  [/^\/api\/v1\/travel(\/|$)/, "Trips"],
  [/^\/api\/v1\/review(\/|$)/, "Weekly review"],
  [/^\/api\/v1\/(brief\/dismiss|recap\/|resurface\/respond|brain\/debrief\/)/, "A card on Home"],
  [/^\/api\/v1\/home\/layout$/, "Home layout"],
];

type Keeper = (method: string, path: string, body: string | null, label: string) => boolean;
let keeper: Keeper | null = null;
/** The outbox registers itself here (no import cycle). */
export function setOfflineKeeper(fn: Keeper | null): void {
  keeper = fn;
}

function queueable(path: string, init: RequestInit): string | null {
  const method = (init.method ?? "GET").toUpperCase();
  if (method === "GET" || (init.body != null && typeof init.body !== "string")) return null;
  if (new Headers(init.headers).has("X-Sirisos-Replay")) return null;  // the outbox sending it: never queue twice
  const hit = QUEUEABLE.find(([re]) => re.test(path));
  return hit ? hit[1] : null;
}

function offlineAnswer(): Response {
  return new Response(JSON.stringify({ queued: true }), { status: 202, headers: { "Content-Type": "application/json" } });
}

export async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const label = keeper ? queueable(path, init) : null;
  try {
    return await send(path, init);
  } catch (e) {
    const gone = e instanceof ApiError && (e.status === 0 || [502, 503, 504].includes(e.status) || (e.status >= 520 && e.status <= 524));
    if (label && gone && keeper?.((init.method ?? "POST").toUpperCase(), path, (init.body as string | undefined) ?? null, label)) return offlineAnswer();
    throw e;
  }
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = session.token();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch (e) {
    // Safari says only "Load failed": the connection dropped, or the phone
    // stopped waiting (about a minute), before any answer came back.
    if (e instanceof Error && e.name === "AbortError") throw e;
    throw new ApiError(0, "Lost the connection before SirisOS answered. If that started something long, it may still be running: check back in a minute.");
  }
  if (response.status === 401 && token) {
    session.clear();
    unauthorisedListeners.forEach((fn) => fn());
  }
  if (!response.ok) throw new ApiError(response.status, await detail(response));
  return response;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await request(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function json(body: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(body) };
}

export async function login(username: string, password: string): Promise<string> {
  const result = await api<{ access_token: string; username: string }>("/api/v1/auth/login", json({ username, password }));
  session.save(result.access_token, result.username);
  return result.username;
}
