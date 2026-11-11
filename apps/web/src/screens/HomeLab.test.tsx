import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { layout, type HomeLab } from "../api/homelab";
import { HomeLabScreen } from "./HomeLab";

const LAB: HomeLab = { clients: { total: 3, online: 2 }, sources: { network: true, servers: true, docker: true }, nodes: [
  { id: "internet", label: "Internet", kind: "internet", parent: null, online: true, found: "built in" },
  { id: "net:gw", label: "UDM Pro", kind: "gateway", parent: "internet", online: true, found: "network", parent_guessed: true },
  { id: "net:sw", label: "USW 24", kind: "switch", parent: "net:gw", online: true, found: "network", parent_guessed: true },
  { id: "net:ap", label: "U6 Lite", kind: "access_point", parent: "net:sw", online: false, found: "network", parent_guessed: true },
  { id: "server:unraid", label: "unraid", kind: "server", parent: "net:sw", online: null, found: "terminal", detail: "192.168.0.100", parent_guessed: true }] };

describe("Home Lab (8.5)", () => {
  it("lays boxes out over what plugs into them", () => {
    const { placed } = layout(LAB.nodes);
    const at = Object.fromEntries(placed.map((p) => [p.id, p]));
    expect(at["internet"].depth).toBe(0);
    expect(at["net:ap"].depth).toBe(3);
    expect(at["net:sw"].x).toBe((at["net:ap"].x + at["server:unraid"].x) / 2);  // centred over its two
  });

  it("draws the hardware and saves a box's model and what it plugs into", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/homelab/": (_u, init) => jsonResponse({ ...LAB, nodes: LAB.nodes.map((n) => (n.id === "net:ap" ? { ...n, ...JSON.parse(String(init.body)), parent_guessed: false } : n)) }),
      "/api/v1/homelab": () => jsonResponse(LAB),
    });
    const user = userEvent.setup();
    render(<HomeLabScreen />);
    const diagram = await screen.findByRole("img", { name: /Home Lab: Internet; UDM Pro into Internet/ });
    expect(diagram).toBeInTheDocument();
    expect(screen.getByText("Plus 3 other devices on the network (2 online now).")).toBeInTheDocument();
    const list = screen.getByRole("region", { name: "Hardware list" });
    expect(within(list).getByText(/into USW 24 \(guessed\) · offline/)).toBeInTheDocument();
    await user.click(within(list).getByRole("button", { name: "Edit U6 Lite" }));
    const sheet = screen.getByRole("dialog", { name: "Edit U6 Lite" });
    await user.type(within(sheet).getByLabelText("Model"), "UniFi U6 Lite");
    await user.selectOptions(within(sheet).getByLabelText("Plugs into"), "net:gw");
    await user.click(within(sheet).getByRole("button", { name: "Save" }));
    const sent = JSON.parse(String(calls.find((c) => c.url.startsWith("/api/v1/homelab/"))!.init.body));
    expect(sent).toMatchObject({ model: "UniFi U6 Lite", parent: "net:gw" });
    expect(await within(list).findByText(/into UDM Pro · offline/)).toBeInTheDocument();
  });
});
