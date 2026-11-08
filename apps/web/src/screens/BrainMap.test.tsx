import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrainMap } from "./BrainMap";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const PAGE = "<title>Siris Brain Map</title><canvas id=stage></canvas>";

describe("<BrainMap />", () => {
  it("renders the vault's mind map sandboxed, and opens it full screen", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/brain/map.html": () => new Response(PAGE, { headers: { "Content-Type": "text/html" } }) });
    const user = userEvent.setup();
    render(<BrainMap />);

    const frame = await screen.findByTitle("Siris mind map");
    expect(frame).toHaveAttribute("srcdoc", PAGE);
    expect(frame).toHaveAttribute("sandbox", "allow-scripts allow-popups");
    expect(new Headers(calls[0].init.headers).get("Authorization")).toBe("Bearer test-token");

    await user.click(screen.getByRole("button", { name: "Open the mind map full screen" }));
    expect(screen.getByRole("dialog", { name: "Mind map" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("explains why the map is missing", async () => {
    signIn();
    mockFetch({ "/api/v1/brain/map.html": () => jsonResponse({ detail: "SirisAI: No second brain configured. Set SIRISAI_BRAIN_PATH." }, 404) });
    render(<BrainMap />);
    expect(await screen.findByText(/SIRISAI_BRAIN_PATH/)).toBeInTheDocument();
  });
});

describe("Deleting from the mind map (8.3)", () => {
  it("deletes what the map asks for after a confirm, offers undo, and ignores messages from anywhere else", async () => {
    signIn();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const calls = mockFetch({
      "/api/v1/brain/map.html": () => new Response(PAGE, { headers: { "Content-Type": "text/html" } }),
      "/api/v1/brain/delete": () => jsonResponse({ title: "Old idea", deleted: true }),
      "/api/v1/brain/restore": () => jsonResponse({ title: "Old idea", restored: true }),
    });
    render(<BrainMap />);
    const frame = (await screen.findByTitle("Siris mind map")) as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent("message", { data: { type: "siris-map:delete", title: "Not from the map" }, source: window }));
    window.dispatchEvent(new MessageEvent("message", { data: { type: "siris-map:delete", title: "Old idea" }, source: frame.contentWindow }));
    expect(await screen.findByText(/Deleted "Old idea"/)).toBeInTheDocument();
    expect(calls.filter((c) => c.url.endsWith("/brain/delete")).map((c) => c.init.body)).toEqual([JSON.stringify({ title: "Old idea", permanent: false })]);
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/brain/restore"))).toBe(true));
  });
});
