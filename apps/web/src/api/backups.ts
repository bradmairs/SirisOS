import { api, json, request } from "./client";

export interface Backup {
  name: string;
  kind: "nightly" | "manual" | "before-restore";
  created: string;
  bytes: number;
}

export interface Backups {
  enabled: boolean;
  folder: string;
  newest: string | null;
  count: number;
  stale: boolean;
  error: string | null;
  nightly_hour: number;
  backups: Backup[];
}

const B = "/api/v1/backups";

export const backups = {
  list: () => api<Backups>(B),
  create: () => api<Backup & { files: number }>(B, { method: "POST" }),
  restore: (name: string) => api<{ restored: number; from: string; undo: string }>(`${B}/${encodeURIComponent(name)}/restore`, json({ confirm: "restore" })),
  async download(name: string) {
    const blob = await (await request(`${B}/${encodeURIComponent(name)}`)).blob();
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
  },
};
