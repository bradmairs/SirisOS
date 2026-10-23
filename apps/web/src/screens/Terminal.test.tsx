import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TerminalScreen } from "./Terminal";
import type { TerminalStatus } from "../api/terminal";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

// xterm draws with real layout, which jsdom doesn't have: a stand-in that records what it was given.
const written: string[] = [];
let typed: ((data: string) => void) | null = null;
vi.mock("@xterm/xterm", () => ({
  Terminal: class {
    cols = 80;
    rows = 24;
    loadAddon() {}
    open() {}
    focus() {}
    dispose() {}
    write(data: string | Uint8Array) { written.push(typeof data === "string" ? data : new TextDecoder().decode(data)); }
    onData(fn: (data: string) => void) { typed = fn; return { dispose() {} }; }
  },
}));
vi.mock("@xterm/addon-fit", () => ({ FitAddon: class { fit() {} } }));
vi.mock("@xterm/xterm/css/xterm.css", () => ({}));

class FakeSocket {
  static last: FakeSocket | null = null;
  static OPEN = 1;
  readyState = 1;
  binaryType = "";
  sent: string[] = [];
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  constructor(public url: string) { FakeSocket.last = this; }
  send(data: string) { this.sent.push(data); }
  close() { this.onclose?.({ code: 1000 }); }
}

const STATUS: TerminalStatus = {
  enabled: true,
  hosts: [{ name: "home", target: "brad@192.168.0.100", host_key: null }],
  two_factor: { set_up: false, since: null, broken: false },
  public_key: "ssh-ed25519 AAAAC3Nza sirisos-terminal",
  idle_minutes: 15,
  max_minutes: 120,
  sessions: [],
  activity: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
  written.length = 0;
});

describe("<TerminalScreen />", () => {
  it("explains how to turn it on", async () => {
    signIn();
    mockFetch({ "/api/v1/terminal": () => jsonResponse({ ...STATUS, enabled: false, hosts: [], public_key: null }) });
    render(<TerminalScreen />);
    expect(await screen.findByText("The terminal is off")).toBeInTheDocument();
    expect(screen.getByText("SIRISOS_TERMINAL_HOSTS")).toBeInTheDocument();
  });

  it("sets up 2FA with the password, a QR code and a first code", async () => {
    signIn();
    let status = STATUS;
    const calls = mockFetch({
      "/api/v1/terminal/2fa/setup": () => jsonResponse({ secret: "ABCDEFGHIJKLMNOP", uri: "otpauth://totp/SirisOS:brad?secret=ABCDEFGHIJKLMNOP", qr_svg: "<svg data-testid='qr'></svg>" }),
      "/api/v1/terminal/2fa/confirm": () => {
        status = { ...STATUS, two_factor: { set_up: true, since: "2026-10-22T01:00:00+00:00", broken: false } };
        return jsonResponse({ two_factor: status.two_factor });
      },
      "/api/v1/terminal": () => jsonResponse(status),
    });
    const user = userEvent.setup();
    render(<TerminalScreen />);
    await user.type(await screen.findByLabelText("SirisOS password"), "hunter2-long");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(JSON.parse(calls.find((c) => c.url.endsWith("/2fa/setup"))!.init.body as string)).toEqual({ password: "hunter2-long" });
    expect(await screen.findByText("ABCD EFGH IJKL MNOP")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /add it to Passwords/ })).toHaveAttribute("href", expect.stringMatching(/^otpauth:/));

    await user.type(screen.getByLabelText("First code from the app"), "123456");
    await user.click(screen.getByRole("button", { name: "Turn on 2FA" }));
    expect(await screen.findByRole("form", { name: "Unlock the terminal" })).toBeInTheDocument();
  });

  it("unlocks with a code, connects, types and locks again", async () => {
    signIn();
    vi.stubGlobal("WebSocket", FakeSocket);
    vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
    const ready = { ...STATUS, two_factor: { set_up: true, since: "2026-10-22T01:00:00+00:00", broken: false } };
    const calls = mockFetch({
      "/api/v1/terminal/unlock": () => jsonResponse({ ticket: "tkt-1", expires_in: 30 }),
      "/api/v1/terminal/commands": () => jsonResponse({ commands: [{ id: "builtin:disk", name: "Disk space", command: "df -h", host: null, builtin: true }], seconds: 60 }),
      "/api/v1/terminal": () => jsonResponse(ready),
    });
    const user = userEvent.setup();
    render(<TerminalScreen />);
    const open = await screen.findByRole("button", { name: /Open home/ });
    expect(open).toBeDisabled();
    await user.type(screen.getByLabelText("6-digit code"), "654321");
    await user.click(open);
    expect(JSON.parse(calls.find((c) => c.url.endsWith("/unlock"))!.init.body as string)).toEqual({ host: "home", code: "654321" });

    await waitFor(() => expect(FakeSocket.last?.url).toMatch(/\/api\/v1\/terminal\/ws\?ticket=tkt-1$/));
    const ws = FakeSocket.last!;
    ws.onmessage?.({ data: JSON.stringify({ type: "ready", target: "brad@192.168.0.100" }) });
    expect(await screen.findByText("brad@192.168.0.100")).toBeInTheDocument();
    expect(ws.sent.map((s) => JSON.parse(s))).toContainEqual({ type: "resize", cols: 80, rows: 24 });
    ws.onmessage?.({ data: new TextEncoder().encode("brad@home:~$ ").buffer });
    expect(written.join("")).toContain("brad@home:~$ ");

    await user.click(await screen.findByRole("button", { name: "Type Disk space" }));
    expect(JSON.parse(ws.sent.at(-1)!)).toEqual({ type: "input", data: "df -h" });  // typed, not run: Enter is yours
    typed?.("ls\r");
    await user.click(screen.getByRole("button", { name: "Esc" }));
    await user.click(screen.getByRole("button", { name: "Ctrl" }));
    expect(screen.getByRole("button", { name: "Ctrl" })).toHaveAttribute("aria-pressed", "true");
    typed?.("c");
    expect(ws.sent.slice(-3).map((s) => JSON.parse(s).data)).toEqual(["ls\r", "\x1b", "\x03"]);

    await user.click(screen.getByRole("button", { name: "Lock" }));
    expect(await screen.findByText("Terminal closed.")).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Unlock the terminal" })).toBeInTheDocument();
  });

  it("runs a shortcut behind a fresh code and shows its output", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/terminal/unlock": () => jsonResponse({ ticket: "tkt-2", expires_in: 30 }),
      "/api/v1/terminal/run": () => jsonResponse({ name: "Disk space", host: "home", command: "df -h", exit: 0, output: "/dev/sda1  50%  /", truncated: false, timed_out: false, seconds: 0.4 }),
      "/api/v1/terminal/commands": () => jsonResponse({ commands: [{ id: "builtin:disk", name: "Disk space", command: "df -h", host: null, builtin: true }], seconds: 60 }),
      "/api/v1/terminal": () => jsonResponse({ ...STATUS, two_factor: { set_up: true, since: null, broken: false } }),
    });
    const user = userEvent.setup();
    render(<TerminalScreen />);
    await user.click(await screen.findByRole("button", { name: /Disk space/ }));
    const form = screen.getByRole("form", { name: "Run Disk space" });
    await user.type(within(form).getByLabelText("6-digit code"), "222333");
    await user.click(within(form).getByRole("button", { name: /Run on home/ }));
    expect((await screen.findByRole("status")).parentElement).toHaveTextContent("/dev/sda1 50% /");
    expect(screen.getByRole("status")).toHaveTextContent("Disk space on home: done");
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/run"))!.init.body))).toEqual({ ticket: "tkt-2", command: "builtin:disk" });
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/unlock"))!.init.body))).toEqual({ host: "home", code: "222333" });
  });

  it("shows a wrong code and clears it", async () => {
    signIn();
    mockFetch({
      "/api/v1/terminal/unlock": () => jsonResponse({ detail: "That code didn't work. Codes work once: wait for the next one." }, 401),
      "/api/v1/terminal": () => jsonResponse({ ...STATUS, two_factor: { set_up: true, since: null, broken: false } }),
    });
    const user = userEvent.setup();
    render(<TerminalScreen />);
    await user.type(await screen.findByLabelText("6-digit code"), "111111");
    await user.click(screen.getByRole("button", { name: /Open home/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Codes work once");
    expect(screen.getByLabelText("6-digit code")).toHaveValue("");
  });
});
