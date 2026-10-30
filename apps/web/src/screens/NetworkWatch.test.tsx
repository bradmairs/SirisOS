import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import type { WatchedDevice } from "../api/netwatch";
import { NetworkWatchCard } from "./NetworkWatch";

const d = (over: Partial<WatchedDevice>): WatchedDevice => ({ id: "x", name: "x", kind: "client", first_seen: "2026-10-29T09:00:00+00:00", last_seen: null,
  trusted: true, important: false, blocked: false, online: true, offline_minutes: null, ...over });

describe("<NetworkWatchCard />", () => {
  it("asks about new devices, shows what's watched, and blocks", async () => {
    signIn();
    clearResources();
    const devices = [d({ id: "cc:09", name: "espressif", trusted: false }), d({ id: "bb:01", name: "Synology NAS", important: true, online: false, offline_minutes: 14 }),
      d({ id: "bb:02", name: "Brad's iPhone" })];
    const calls = mockFetch({
      "/api/v1/netwatch/cc%3A09/block": () => jsonResponse({ watching: true, devices: [{ ...devices[0], blocked: true, trusted: true }, ...devices.slice(1)] }),
      "/api/v1/netwatch": () => jsonResponse({ watching: true, devices }),
    });
    const user = userEvent.setup();
    render(<NetworkWatchCard />);
    const card = await screen.findByRole("region", { name: "Network watch" });
    expect(await within(card).findByText("espressif")).toBeInTheDocument();
    expect(within(card).getByText("Offline for 14 min")).toBeInTheDocument();
    expect(within(card).getByText("Everything else (1): star one to watch it")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Block it" }));
    await waitFor(() => expect(within(card).getByRole("button", { name: "Unblock" })).toBeInTheDocument());
    expect(JSON.parse(String(calls.at(-1)!.init.body))).toEqual({ blocked: true });
  });
});
