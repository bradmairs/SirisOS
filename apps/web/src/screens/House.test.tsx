import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { HouseScreen } from "./House";

const scene = vi.hoisted(() => ({ setFloor: vi.fn(), setNetwork: vi.fn(), setSelected: vi.fn(), setLinksVisible: vi.fn(), setRoomGlow: vi.fn(), focusRoom: vi.fn(), dispose: vi.fn() }));
vi.mock("../house/scene", () => ({ createHouseScene: () => scene }));

const network = {
  configured: true, guest_mode: false, checked_at: "2026-10-24T09:00:00Z",
  wan: { rx_bps: 2_500_000, tx_bps: 125_000, isp: "Aussie" },
  nodes: [
    { id: "gw", name: "UCG Ultra", kind: "gateway", model: "UCGULTRA", wired: true, online: true, uplink: null, rx_bps: 2_500_000, tx_bps: 125_000 },
    { id: "tv", name: "Lounge Apple TV", kind: "client", model: null, wired: false, online: true, uplink: "gw", rx_bps: 2_000_000, tx_bps: 1000 },
    { id: "ha", name: "Home Assistant", kind: "client", model: null, wired: true, online: true, uplink: "gw", rx_bps: 500, tx_bps: 500 },
  ],
};
const controls = { configured: true, controls: [{ entity_id: "light.kitchen", name: "Kitchen lights", kind: "light", state: "on" }], scenes: [] };

describe("<HouseScreen />", () => {
  it("shows the network now and the devices, and saves a device's room", async () => {
    signIn();
    clearResources();
    localStorage.removeItem("sirisos.resource.house:placements");
    const calls = mockFetch({
      "/api/v1/assistant/network": () => jsonResponse(network),
      "/api/v1/assistant/controls": () => jsonResponse(controls),
      "/api/v1/house/placements": (_u, init) => jsonResponse(init.method === "PUT" ? JSON.parse(String(init.body)) : { placements: {} }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><HouseScreen /></MemoryRouter>);

    const now = await screen.findByRole("region", { name: "Network now" });
    expect(await within(now).findByText("20 Mb/s")).toBeInTheDocument();
    expect(within(now).getByText("1.0 Mb/s")).toBeInTheDocument();
    // The lights, garage and scenes card lives here since 4.8, not on Home; no link back to this page.
    const card = await screen.findByRole("region", { name: "Home controls" });
    expect(within(card).queryByText("The house in 3D →")).not.toBeInTheDocument();
    const devices = await screen.findByRole("region", { name: "Devices" });
    const titles = within(devices).getAllByText(/UCG Ultra|Lounge Apple TV|Home Assistant|Kitchen lights/).map((e) => e.textContent);
    expect(titles[0]).toBe("UCG Ultra");
    expect(within(devices).getByLabelText("Room for Lounge Apple TV")).toHaveValue("lounge");
    expect(within(devices).getByLabelText("Room for Kitchen lights")).toHaveValue("kitchen");

    await waitFor(() => expect(scene.setNetwork).toHaveBeenCalled());
    const last = scene.setNetwork.mock.calls.at(-1)!;
    expect(last[0].find((n: { id: string }) => n.id === "light.kitchen").uplink).toBe("ha");

    await user.selectOptions(within(devices).getByLabelText("Room for Lounge Apple TV"), "main");
    await waitFor(() => expect(calls.some((c) => c.init.method === "PUT")).toBe(true));
    const put = calls.find((c) => c.init.method === "PUT")!;
    expect(JSON.parse(String(put.init.body)).placements.tv).toEqual({ room: "main" });

    await user.click(screen.getByRole("button", { name: "Roof" }));
    expect(scene.setFloor).toHaveBeenLastCalledWith("roof");
  });
});
