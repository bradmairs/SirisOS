import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Links } from "./Links";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const DOC = {
  groups: [
    { id: "g1", name: "Media", links: [{ id: "plex", name: "Plex", url: "http://10.0.0.5:32400", icon: null, note: "LAN" }] },
    { id: "g2", name: "Work", links: [{ id: "pm", name: "Project Management", url: "https://pm.example.com", icon: null, note: "" }] },
  ],
};

describe("<Links />", () => {
  it("shows grouped links with their status, and filters them", async () => {
    signIn();
    mockFetch({
      "/api/v1/links/status": () => jsonResponse({ plex: { up: true, status: 200, ms: 12 }, pm: { up: false, status: null, ms: null } }),
      "/api/v1/links": () => jsonResponse(DOC),
    });
    const user = userEvent.setup();
    render(<Links />);
    const plex = await screen.findByRole("link", { name: "Plex: up" });
    expect(plex).toHaveAttribute("href", "http://10.0.0.5:32400");
    expect(plex).toHaveAttribute("target", "_blank");
    expect(within(plex).getByText("LAN · 10.0.0.5:32400")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Project Management: down" })).toBeInTheDocument();
    expect(screen.getByText(/2 links · 1 up/)).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Find an app"), "plex");
    expect(screen.queryByRole("region", { name: "Work" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Media" })).toBeInTheDocument();
  });

  it("adds a link to a new group and saves the whole document", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/links/status": () => jsonResponse({}),
      "/api/v1/links": (_url, init) => jsonResponse(init.method === "PUT" ? JSON.parse(init.body as string) : DOC),
    });
    const user = userEvent.setup();
    render(<Links />);
    await screen.findByRole("link", { name: /Plex/ });
    await user.click(screen.getByRole("button", { name: "Edit links" }));
    await user.click(screen.getByRole("button", { name: /add link/i }));
    const sheet = await screen.findByRole("dialog", { name: "Add link" });
    await user.type(within(sheet).getByLabelText("Name"), "Grafana");
    await user.clear(within(sheet).getByLabelText("Address"));
    await user.type(within(sheet).getByLabelText("Address"), "http://10.0.0.5:3000");
    await user.clear(within(sheet).getByLabelText("Group"));
    await user.type(within(sheet).getByLabelText("Group"), "System");
    await user.click(within(sheet).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(calls.some((c) => c.init.method === "PUT")).toBe(true));
    const saved = JSON.parse(calls.find((c) => c.init.method === "PUT")!.init.body as string);
    expect(saved.groups.map((g: { name: string }) => g.name)).toEqual(["Media", "Work", "System"]);
    expect(saved.groups[2].links[0]).toMatchObject({ name: "Grafana", url: "http://10.0.0.5:3000" });
    expect(await screen.findByRole("button", { name: "Edit Grafana" })).toBeInTheDocument();
  });

  it("removes a link", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/links/status": () => jsonResponse({}),
      "/api/v1/links": (_url, init) => jsonResponse(init.method === "PUT" ? JSON.parse(init.body as string) : DOC),
    });
    const user = userEvent.setup();
    render(<Links />);
    await screen.findByRole("link", { name: /Plex/ });
    await user.click(screen.getByRole("button", { name: "Edit links" }));
    await user.click(screen.getByRole("button", { name: "Edit Plex" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: /remove/i }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PUT")).toBe(true));
    const saved = JSON.parse(calls.find((c) => c.init.method === "PUT")!.init.body as string);
    expect(saved.groups.map((g: { name: string }) => g.name)).toEqual(["Work"]);
  });
});
