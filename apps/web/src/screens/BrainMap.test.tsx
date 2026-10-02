import { describe, expect, it } from "vitest";
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

    const frame = await screen.findByTitle("Second Brain mind map");
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
