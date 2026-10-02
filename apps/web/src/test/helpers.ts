import { vi } from "vitest";

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function sseResponse(events: unknown[], chunkSize = 7): Response {
  const text = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("") + ": keepalive\n\n";
  const bytes = new TextEncoder().encode(text);
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.slice(i, i + chunkSize));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

export function mockFetch(routes: Record<string, Handler>) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push({ url, init });
    const key = Object.keys(routes).find((k) => url.startsWith(k));
    if (!key) return jsonResponse({ detail: `unmocked ${url}` }, 404);
    return routes[key](url, init);
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

export function signIn(user = "brad") {
  localStorage.setItem("sirisos.token", "test-token");
  localStorage.setItem("sirisos.user", user);
}
