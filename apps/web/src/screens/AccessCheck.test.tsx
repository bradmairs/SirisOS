import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { AccessCheckCard } from "./AccessCheck";

const view = (extra = {}) => ({
  client_ip: "149.167.20.9", network: "internet", host: "sirisos.home:8444",
  certificate: { host: "sirisos.home:8444", days_left: 60 },
  terminal: { enabled: true, hosts: [{ name: "home", target: "brad@192.168.0.100", ms: 4, reachable: true }, { name: "nas", target: "brad@192.168.0.20", ms: null, reachable: false }] },
  ...extra,
});

/** Two SSE events, `gap` ms apart. */
function stream(gap: number) {
  const enc = new TextEncoder();
  return new Response(new ReadableStream({
    async start(c) {
      c.enqueue(enc.encode('data: {"n":1}\n\n'));
      await new Promise((r) => setTimeout(r, gap));
      c.enqueue(enc.encode('data: {"n":2}\n\n'));
      c.close();
    },
  }), { headers: { "Content-Type": "text/event-stream" } });
}

class FakeSocket {
  static mode: "open" | "blocked" = "open";
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  constructor(public url: string) {
    setTimeout(() => (FakeSocket.mode === "open" ? this.onmessage?.({ data: '{"type":"probe"}' } as MessageEvent) : this.onclose?.({ code: 1006 } as CloseEvent)), 5);
  }
  close() {}
}

afterEach(() => vi.unstubAllGlobals());

describe("<AccessCheckCard />", () => {
  it("runs every check from this device and says what to fix", async () => {
    signIn();
    FakeSocket.mode = "blocked";
    vi.stubGlobal("WebSocket", FakeSocket);
    mockFetch({
      "/api/v1/access/stream": () => stream(1200),
      "/api/v1/access": () => jsonResponse(view()),
    });
    const user = userEvent.setup();
    render(<AccessCheckCard />);
    await user.click(screen.getByRole("button", { name: "Check from here" }));
    expect(await screen.findByText(/won't work from here/, {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText(/Through the internet \(149.167.20.9\)/)).toBeInTheDocument();
    expect(screen.getByText("Runs out in 60 days")).toBeInTheDocument();
    expect(screen.getByText("The Inbox and chat update as things happen")).toBeInTheDocument();
    expect(screen.getByText(/Closed before it opened \(1006\)/)).toBeInTheDocument();
    expect(screen.getByText(/the terminal won't connect from here/)).toBeInTheDocument();
    expect(screen.getByText("brad@192.168.0.100 answers (4 ms)")).toBeInTheDocument();
    expect(screen.getByText(/brad@192.168.0.20 doesn't answer/)).toBeInTheDocument();
  });

  it("flags buffered live updates and stops when SirisOS can't be reached", async () => {
    signIn();
    FakeSocket.mode = "open";
    vi.stubGlobal("WebSocket", FakeSocket);
    mockFetch({ "/api/v1/access/stream": () => stream(0), "/api/v1/access": () => jsonResponse(view({ terminal: { enabled: false, hosts: [] } })) });
    const user = userEvent.setup();
    const { unmount } = render(<AccessCheckCard />);
    await user.click(screen.getByRole("button", { name: "Check from here" }));
    expect(await screen.findByText("Updates arrive in bursts", {}, { timeout: 5000 })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("WebSockets get through")).toBeInTheDocument());
    unmount();

    mockFetch({ "/api/v1/access": () => jsonResponse({ detail: "Bad Gateway" }, 502) });
    render(<AccessCheckCard />);
    await user.click(screen.getByRole("button", { name: "Check from here" }));
    expect(await screen.findByText(/your VPN or tunnel to home is on/)).toBeInTheDocument();
    expect(screen.queryByText("Live updates")).toBeNull();
  });
});
