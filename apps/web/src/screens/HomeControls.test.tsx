import { describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { HomeControlsWidget } from "./SirisControls";

const controls = {
  configured: true, guest_mode: false,
  controls: [
    { entity_id: "cover.garage_door", name: "Garage door", kind: "garage", state: "closed", brightness_pct: null, confirm: "Open Garage door?" },
    { entity_id: "lock.front_door", name: "Front door", kind: "lock", state: "locked", brightness_pct: null, confirm: "Unlock Front door?" },
    { entity_id: "light.kitchen", name: "Kitchen", kind: "light", state: "on", brightness_pct: 50, confirm: null },
  ],
  scenes: [{ id: "siris:3", name: "Wind down", source: "siris" }],
};

describe("<HomeControlsWidget />", () => {
  it("toggles a light at once, asks before the garage, and runs scenes", async () => {
    signIn();
    clearResources();
    // A house that changes when it's told to: the next read of the controls shows it.
    const house = structuredClone(controls);
    const set = (id: string, state: string) => { house.controls.find((c) => c.entity_id === id)!.state = state; };
    const calls = mockFetch({
      "/api/v1/assistant/controls/light.kitchen": () => { set("light.kitchen", "off"); return jsonResponse({ entity_id: "light.kitchen", action: "toggle", state: "off" }); },
      "/api/v1/assistant/controls/cover.garage_door": () => { set("cover.garage_door", "open"); return jsonResponse({ entity_id: "cover.garage_door", action: "open", state: "open" }); },
      "/api/v1/assistant/controls": () => jsonResponse(house),
      "/api/v1/assistant/scenes/": () => jsonResponse({ entity_id: "siris:3", action: "run" }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><HomeControlsWidget /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Kitchen: On · 50%" }));
    expect(await screen.findByRole("button", { name: "Kitchen: Off" })).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("light.kitchen"))!.init.body))).toEqual({ action: "toggle", confirmed: false });

    await user.click(screen.getByRole("button", { name: "Garage door: Closed" }));
    expect(calls.some((c) => c.url.endsWith("cover.garage_door"))).toBe(false);
    expect(screen.getByRole("alertdialog", { name: "Open Garage door?" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Yes" }));
    expect(await screen.findByRole("button", { name: "Garage door: Open" })).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("cover.garage_door"))!.init.body))).toEqual({ action: "open", confirmed: true });

    await user.click(screen.getByRole("button", { name: "Front door: Locked" }));
    expect(screen.getByRole("alertdialog", { name: "Unlock Front door?" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();

    await user.click(screen.getByRole("button", { name: /Wind down/ }));
    expect(await screen.findByText("Wind down: done.")).toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/assistant/scenes/siris%3A3/run")).toBe(true);
  });

  it("shows a light switched somewhere else as it really is, not what SirisOS last set (9.42)", async () => {
    signIn();
    clearResources();
    const house = structuredClone(controls);
    const kitchen = () => house.controls.find((c) => c.entity_id === "light.kitchen")!;
    mockFetch({
      "/api/v1/assistant/controls/light.kitchen": () => { kitchen().state = "off"; return jsonResponse({ entity_id: "light.kitchen", action: "toggle", state: "off" }); },
      "/api/v1/assistant/controls": () => jsonResponse(house),
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<MemoryRouter><HomeControlsWidget /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Kitchen: On · 50%" }));
    expect(await screen.findByRole("button", { name: "Kitchen: Off" })).toBeInTheDocument();
    kitchen().state = "on";  // turned back on at the wall, or by the Home app
    await act(async () => { vi.advanceTimersByTime(31_000); });  // SirisOS reads the controls again every 30 s
    expect(await screen.findByRole("button", { name: "Kitchen: On · 50%" })).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("reads again shortly when SirisAI couldn't say what the light did", async () => {
    signIn();
    clearResources();
    const house = structuredClone(controls);
    let reads = 0;
    mockFetch({
      "/api/v1/assistant/controls/light.kitchen": () => jsonResponse({ entity_id: "light.kitchen", action: "toggle", state: null }),
      "/api/v1/assistant/controls": () => { reads += 1; if (reads > 1) house.controls.find((c) => c.entity_id === "light.kitchen")!.state = "off"; return jsonResponse(house); },
    });
    const user = userEvent.setup();
    render(<MemoryRouter><HomeControlsWidget /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Kitchen: On · 50%" }));
    expect(screen.getByRole("button", { name: /Kitchen: On/ })).toBeInTheDocument();  // never the old state passed off as new
    expect(await screen.findByRole("button", { name: "Kitchen: Off" }, { timeout: 4000 })).toBeInTheDocument();
  });

  it("stays hidden when Home Assistant isn't set up and there are no scenes", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/assistant/controls": () => jsonResponse({ configured: false, guest_mode: false, controls: [], scenes: [] }) });
    const { container } = render(<MemoryRouter><HomeControlsWidget /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
