import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { BackupsCard } from "./BackupsCard";

const list = (n: number, extra = {}) => ({
  enabled: true, folder: "/app/backups", newest: "2026-10-22T16:00:00+00:00", count: n, stale: false, error: null, nightly_hour: 3,
  backups: Array.from({ length: n }, (_, i) => ({ name: `sirisos-2026102${i}-160000-nightly.tar.gz`, kind: "nightly", created: `2026-10-2${2 - i}T16:00:00+00:00`, bytes: 52_000 })),
  ...extra,
});

describe("<BackupsCard />", () => {
  it("lists backups, three at a time, and backs up now", async () => {
    signIn();
    clearResources();
    let made = false;
    const calls = mockFetch({
      "/api/v1/backups": (_url, init) => {
        if (init.method === "POST") { made = true; return jsonResponse({ name: "x", kind: "manual", created: "", bytes: 1, files: 12 }); }
        return jsonResponse(list(made ? 5 : 4));
      },
    });
    const user = userEvent.setup();
    render(<BackupsCard />);
    const card = await screen.findByRole("region", { name: "SirisOS backups" });
    expect(within(card).getAllByText(/Nightly · 51 KB/)).toHaveLength(3);
    await user.click(within(card).getByRole("button", { name: "Show all 4" }));
    expect(within(card).getAllByText(/Nightly/)).toHaveLength(4);
    await user.click(within(card).getByRole("button", { name: /Back up now/ }));
    expect(await within(card).findByText("Backed up 12 files.")).toBeInTheDocument();
    expect(calls.some((c) => c.init.method === "POST" && c.url === "/api/v1/backups")).toBe(true);
  });

  it("asks before restoring, then says how to undo", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/backups/": () => jsonResponse({ restored: 9, from: "a", undo: "b" }),
      "/api/v1/backups": () => jsonResponse(list(1)),
    });
    const user = userEvent.setup();
    render(<BackupsCard />);
    await user.click(await screen.findByRole("button", { name: /Restore the backup from/ }));
    expect(screen.getByText(/Anything changed since is saved first/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restore" }));
    expect(await screen.findByText(/Put back 9 files/)).toBeInTheDocument();
    const restore = calls.find((c) => c.url.endsWith("/restore"))!;
    expect(JSON.parse(String(restore.init.body))).toEqual({ confirm: "restore" });
  });

  it("says when the last backup failed", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/backups": () => jsonResponse(list(0, { error: "PermissionError: denied", newest: null, stale: true })) });
    render(<BackupsCard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The last backup failed: PermissionError: denied");
    expect(screen.getByText("None yet.")).toBeInTheDocument();
  });
});
