import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { Sidebar } from "../components/Sidebar";
import { SectionsUseScreen } from "./SectionsUse";
import { UpdateCard } from "./UpdateCard";

afterEach(() => { clearResources(); vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); });

const usage = (hidden: string[] = []) => ({ on: true, phases: {}, usually: {}, sections: { "/gym": 20, "/tasks": 26, "/week": 0 },
  counting_since: "2026-10-27", menu_hidden: hidden });

describe("SirisOS 11.11", () => {
  it("offers a newer version and starts the update with the Terminal's code", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/updates": () => jsonResponse({ current: "11.10.0", latest: "11.11.0", newer: true, headline: "Update now, and Sections you use.",
        notes: "https://github.com/x/blob/main/docs/releases/11.11.0.md", error: null, log: [] }),
      "/api/v1/terminal/unlock": () => jsonResponse({ ticket: "t-123456789012", expires_in: 30 }),
      "/api/v1/terminal/run": () => jsonResponse({ name: "Update SirisOS", host: "home", command: "x", exit: 0, output: "Updating in ~/x: it carries on by itself.",
        truncated: false, timed_out: false, seconds: 0.4 }),
      "/api/v1/terminal": () => jsonResponse({ enabled: true, hosts: [{ name: "home", target: "brad@host", host_key: null }],
        two_factor: { set_up: true, since: null, broken: false }, public_key: null, idle_minutes: 15, max_minutes: 120 }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><UpdateCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "SirisOS version" });
    expect(within(card).getByText(/11.11.0 is out/)).toBeInTheDocument();
    await user.type(await within(card).findByRole("textbox", { name: "Terminal 2FA code" }), "123456");
    await user.click(within(card).getByRole("button", { name: "Update now" }));
    expect(await within(card).findByText(/Updating on the server/)).toBeInTheDocument();
    const run = calls.find((c) => c.url.endsWith("/terminal/run"));
    expect(JSON.parse(String(run?.init.body))).toEqual({ ticket: "t-123456789012", command: "builtin:update-sirisos" });
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/terminal/unlock"))?.init.body))).toEqual({ host: "home", code: "123456" });
  });

  it("shows how often each section is opened, and takes one out of the menu", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/home/usage/menu": () => jsonResponse(usage(["household"])), "/api/v1/home/usage": () => jsonResponse(usage()) });
    const user = userEvent.setup();
    render(<MemoryRouter><SectionsUseScreen /></MemoryRouter>);
    const list = await screen.findByRole("region", { name: "Sections" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Tasks");  // most used first
    expect(within(list).getByText(/Household/).closest("li")).toHaveTextContent("not opened");
    await user.click(within(list).getByRole("button", { name: "Hide Household in the menu" }));
    await waitFor(() => expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/usage/menu"))?.init.body))).toEqual({ hidden: ["household"] }));
    expect(await within(list).findByRole("button", { name: "Show Household in the menu" })).toBeInTheDocument();
  });

  it("leaves hidden sections out of the side menu, except the one you're in", async () => {
    signIn();
    mockFetch({ "/api/v1/home/usage": () => jsonResponse(usage(["household", "budget"])) });
    render(<MemoryRouter initialEntries={["/budget"]}><Sidebar apps={[]} user="brad" open onClose={() => undefined} onSignOut={() => undefined} /></MemoryRouter>);
    const nav = await screen.findByRole("navigation", { name: "Screens" });
    await waitFor(() => expect(within(nav).queryByRole("link", { name: /Household/ })).toBeNull());
    expect(within(nav).getByRole("link", { name: /Budget/ })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: /SirisGym/ })).toBeInTheDocument();
  });
});
