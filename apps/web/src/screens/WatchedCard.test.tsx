import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { WatchedCard, type Tracking } from "./WatchedCard";

describe("What SirisAI watches (8.4)", () => {
  it("switches off a container removed on purpose", async () => {
    signIn();
    clearResources();
    let state: Tracking = { containers: [
      { name: "open-webui", state: "exited", status: "Exited (0) 2 days ago", tracked: true },
      { name: "plex", state: "running", status: "Up 3 days", tracked: true }], untracked: [] };
    const calls = mockFetch({
      "/api/v1/assistant/tracking": (_u, init) => {
        if (init.method === "PUT") {
          const b = JSON.parse(String(init.body));
          state = { containers: state.containers!.map((c) => (c.name === b.name ? { ...c, tracked: b.tracked } : c)),
            untracked: b.tracked ? [] : [{ kind: "container", name: b.name, since: "2026-11-08", why: b.why }] };
        }
        return jsonResponse(state);
      },
    });
    const user = userEvent.setup();
    render(<WatchedCard />);
    const card = await screen.findByRole("region", { name: "What SirisAI watches" });
    expect(within(card).getByText("open-webui")).toBeInTheDocument();
    expect(within(card).queryByText("plex")).not.toBeInTheDocument();  // running and watched: only under "All"
    await user.click(within(card).getByRole("switch", { name: "Watch open-webui" }));
    expect(JSON.parse(String(calls.find((c) => c.init.method === "PUT")!.init.body))).toEqual({ kind: "container", name: "open-webui", tracked: false, why: "switched off in SirisOS" });
    expect(await within(card).findByText(/Not watched/)).toBeInTheDocument();
    expect(within(card).getByRole("switch", { name: "Watch open-webui" })).toHaveAttribute("aria-checked", "false");
    await user.click(within(card).getByRole("button", { name: "All 2" }));
    expect(within(card).getByText("plex")).toBeInTheDocument();
  });

  it("offers to watch again something no longer in Docker", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/assistant/tracking": () => jsonResponse({ containers: [], untracked: [{ kind: "container", name: "open-webui", since: "x", why: "removed it" }] }) });
    render(<WatchedCard />);
    expect(await screen.findByText(/no longer in Docker/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Watch again" })).toBeInTheDocument();
  });
});
