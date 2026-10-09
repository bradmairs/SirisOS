import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Home } from "./Home";
import { CameraSheet, ProtocolsWidget, protocolLabel } from "./SirisControls";
import { resetInbox } from "../components/Inbox";
import { jsonResponse, mockFetch, signIn, sseResponse } from "../test/helpers";
import type { SirisWidgets } from "../api/types";

// SirisAI's own example payloads (ADR 110), shared with the backend tests.
const contract = (name: string) =>
  JSON.parse(readFileSync(resolve(process.cwd(), "../backend/tests/contracts/sirisai-hub-v1", `${name}.json`), "utf8"));
const WIDGETS = contract("widgets") as SirisWidgets;

afterEach(() => resetInbox());

describe("protocols", () => {
  it("previews, runs only after confirming, and offers undo", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/assistant/protocols/lockdown/run": () => jsonResponse(contract("protocol_run")),
      "/api/v1/assistant/protocols/undo": () => jsonResponse({ name: "lockdown", ran: ["lock lock"], skipped: [], failed: [], can_undo: false }),
      "/api/v1/assistant/protocols/lockdown": () => jsonResponse(contract("protocol_preview")),
    });
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<ProtocolsWidget protocols={WIDGETS.protocols} lastRun={{ protocol: "away", at: null, undone: false, can_undo: true }} onChanged={onChanged} />);

    await user.click(screen.getByRole("button", { name: "Lock down" }));
    const sheet = await screen.findByRole("dialog", { name: "Lock down" });
    expect(await within(sheet).findByText("Lock every lock")).toBeInTheDocument();
    expect(calls.some((c) => c.url.endsWith("/run"))).toBe(false); // nothing ran yet
    await user.click(within(sheet).getByRole("button", { name: "Run lock down" }));
    expect(await within(sheet).findByRole("status")).toHaveTextContent(/Lock down: \d+ steps? done/);
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/run"))!.init.body))).toEqual({ confirmed: true });
    expect(onChanged).toHaveBeenCalled();

    await user.click(within(sheet).getByRole("button", { name: "Done" }));
    await user.click(screen.getByRole("button", { name: /undo/i }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/protocols/undo"))).toBe(true));
    expect(await screen.findByText("Undid Lock down.")).toBeInTheDocument();
  });

  it("names protocols for people", () => {
    expect(protocolLabel("guest_off")).toBe("Guests gone");
    expect(protocolLabel("movie_night")).toBe("Movie night");
  });
});

describe("cameras", () => {
  it("shows the latest frame and what the vision model sees", async () => {
    signIn();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:frame", revokeObjectURL: () => undefined }));
    mockFetch({
      "/api/v1/assistant/cameras/front_door/latest.jpg": () => new Response(new Blob(["jpeg"], { type: "image/jpeg" })),
      "/api/v1/assistant/cameras/front_door/look": () => jsonResponse(contract("camera_look")),
    });
    const user = userEvent.setup();
    render(<CameraSheet camera="front_door" onClose={() => undefined} />);
    expect(await screen.findByRole("img", { name: "Latest frame from front door" })).toHaveAttribute("src", "blob:frame");
    await user.click(screen.getByRole("button", { name: /what's there/i }));
    expect(await screen.findByRole("status")).toHaveTextContent("A courier is holding a brown parcel.");
  });
});

describe("<Home /> with SirisAI's widgets", () => {
  const routes = (guest: boolean) => ({
    "/api/v1/hub/apps": () => jsonResponse({ apps: [], guest_mode: guest }),
    "/api/v1/assistant/hud": () => jsonResponse({ next_events: [{ summary: "Dentist", start: "2026-10-09T10:00:00+11:00" }] }),
    "/api/v1/assistant/widgets": () => jsonResponse({ ...WIDGETS, guest_mode: guest }),
    "/api/v1/attention/stream": () => sseResponse([{ type: "snapshot", items: [], counts: { open: 0, urgent: 0 } }]),
    "/api/v1/attention": () => jsonResponse({ items: [], counts: { open: 0, urgent: 0 } }),
  });

  it("shows protocols, car, power and parcels", async () => {
    signIn();
    mockFetch(routes(false));
    render(<MemoryRouter><Home /></MemoryRouter>);
    expect(await screen.findByRole("region", { name: "Protocols" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Car" })).toHaveTextContent("24%");
    expect(screen.getByRole("region", { name: "Power" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Parcels" })).toHaveTextContent("New drill");
    expect(screen.getByText("Dentist")).toBeInTheDocument();
    expect(screen.queryByText(/Guest mode is on/)).not.toBeInTheDocument();
  });

  it("hides the calendar in guest mode and says why", async () => {
    signIn();
    mockFetch(routes(true));
    render(<MemoryRouter><Home /></MemoryRouter>);
    expect(await screen.findByText(/Guest mode is on/)).toBeInTheDocument();
    await screen.findByRole("region", { name: "Protocols" });
    expect(screen.queryByText("Dentist")).not.toBeInTheDocument();
  });
});
