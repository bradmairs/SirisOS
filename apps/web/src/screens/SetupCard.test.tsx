import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { SetupCard } from "./SetupCard";

const items = [
  { id: "sirisai", title: "SirisAI", area: "SirisAI", state: "on", detail: "Connected, version 3.11.", fix: "", settings: [], link: null },
  { id: "unifi", title: "UniFi network", area: "Smart home", state: "off", detail: "No live network.", fix: "In SirisAI, set the gateway's address and an API key.", settings: ["SIRISAI_UNIFI_BASE_URL", "SIRISAI_UNIFI_API_KEY"], link: "/house?view=network" },
  { id: "health", title: "Apple Health", area: "You", state: "problem", detail: "A key is made, but nothing has arrived in two days.", fix: "Open Health Auto Export.", settings: [], link: "/training#health" },
];

describe("<SetupCard />", () => {
  it("leads with what needs a look, with the fix and settings, and hides what's on", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/setup": () => jsonResponse({ items, counts: { on: 1, off: 1, problem: 1 }, checked_at: "" }) });
    const user = userEvent.setup();
    render(<MemoryRouter><SetupCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Setup" });
    expect(within(card).getByText("1 on · 1 not set up · 1 needs a look")).toBeInTheDocument();
    const rows = within(card).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Apple Health");
    expect(within(rows[1]).getByText("SIRISAI_UNIFI_BASE_URL")).toBeInTheDocument();
    expect(within(card).queryByText("SirisAI")).not.toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Show the 1 that are on" }));
    expect(within(card).getByText("Connected, version 3.11.")).toBeInTheDocument();
  });
});
