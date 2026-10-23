import { api, json } from "./client";

export interface TerminalHost {
  name: string;
  target: string;
  /** SHA256 fingerprint pinned on the first connection, or null before then. */
  host_key: string | null;
}

export interface TerminalActivity {
  at: string;
  event: string;
  host?: string;
  client?: string;
  reason?: string;
  minutes?: number;
}

export interface TerminalStatus {
  enabled: boolean;
  hosts: TerminalHost[];
  two_factor: { set_up: boolean; since: string | null; broken: boolean };
  public_key: string | null;
  idle_minutes: number;
  max_minutes: number;
  sessions: { id: string; host: string; client: string; started: string }[];
  activity: TerminalActivity[];
}

export interface TerminalCommand {
  id: string;
  name: string;
  command: string;
  host: string | null;
  builtin: boolean;
}

export interface CommandResult {
  name: string;
  host: string;
  command: string;
  exit: number | null;
  output: string;
  truncated: boolean;
  timed_out: boolean;
  seconds: number;
}

export const terminal = {
  status: () => api<TerminalStatus>("/api/v1/terminal"),
  setup: (password: string) => api<{ secret: string; uri: string; qr_svg: string }>("/api/v1/terminal/2fa/setup", json({ password })),
  confirm: (code: string) => api<{ two_factor: TerminalStatus["two_factor"] }>("/api/v1/terminal/2fa/confirm", json({ code })),
  off: (password: string, code: string) => api<{ two_factor: TerminalStatus["two_factor"] }>("/api/v1/terminal/2fa/off", json({ password, code })),
  unlock: (host: string, code: string) => api<{ ticket: string; expires_in: number }>("/api/v1/terminal/unlock", json({ host, code })),
  commands: () => api<{ commands: TerminalCommand[]; seconds: number }>("/api/v1/terminal/commands"),
  addCommand: (name: string, command: string, host: string | null) => api<TerminalCommand>("/api/v1/terminal/commands", json({ name, command, host })),
  removeCommand: (id: string) => api(`/api/v1/terminal/commands/${encodeURIComponent(id)}`, { method: "DELETE" }),
  run: (ticket: string, command: string) => api<CommandResult>("/api/v1/terminal/run", json({ ticket, command })),
  socketUrl: (ticket: string) =>
    `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v1/terminal/ws?ticket=${encodeURIComponent(ticket)}`,
};
