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

export async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = session.token();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers });
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
