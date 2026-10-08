import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { App } from "../App";
import { Assistant } from "../screens/Assistant";
import type { SearchResponse } from "../api/search";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { SearchPalette, score } from "./SearchPalette";

const RESULTS: SearchResponse = {
  query: "pump",
  took_ms: 40,
  failed: ["Engineering Archive"],
  groups: [
    { id: "brain", label: "Second Brain", icon: "brain", best: 3, hits: [
      { title: "Pump curves", subtitle: "Reading a pump curve", url: "/brain?q=Pump%20curves", external: false, kind: "resource", app_id: null, score: 3 },
    ] },
    { id: "apd-pm", label: "Project Management", icon: "kanban", best: 3, hits: [
      { title: "Pump station upgrade", subtitle: "Project", url: "http://apd/projects/p1", external: true, kind: "project", app_id: "apd-pm", score: 3 },
    ] },
    { id: "apps", label: "Apps", icon: "layout-grid", best: 1, hits: [
      { title: "Engineering Reviewer", subtitle: "Drawing pre-review", url: "http://reviewer", external: true, kind: "app", app_id: "reviewer", score: 1 },
    ] },
  ],
};

function Where() {
  const location = useLocation();
  return <output aria-label="location">{location.pathname + location.search}</output>;
}

function renderPalette(onOpenApp = vi.fn(), onClose = vi.fn()) {
  render(
    <MemoryRouter>
      <Routes>
        <Route path="*" element={<><SearchPalette onClose={onClose} onOpenApp={onOpenApp} /><Where /></>} />
      </Routes>
    </MemoryRouter>,
  );
  return { onOpenApp, onClose };
}

afterEach(() => localStorage.removeItem("sirisos.search.recent"));

describe("score", () => {
  it("ranks title matches like the server", () => {
    expect(score("pump", "Pump")).toBe(4);
    expect(score("pump", "Pump curves")).toBe(3);
    expect(score("pump", "Big pump")).toBe(2.5);
    expect(score("pump", "Sumps", "a pump")).toBe(1);
    expect(score("pump", "Sumps")).toBe(0);
  });
});

describe("<SearchPalette />", () => {
  it("matches screens and calculators instantly, without the server for one letter", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/search": () => jsonResponse({ ...RESULTS, groups: [] }) });
    const user = userEvent.setup();
    renderPalette();
    await user.type(screen.getByRole("combobox", { name: "Search everything" }), "m");
    expect(calls).toHaveLength(0);
    await user.type(screen.getByRole("combobox"), "anning");
    const calcs = screen.getByRole("region", { name: "Calculators" });
    expect(within(calcs).getByText(/Full pipe/)).toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("status", { name: "location" })).toHaveTextContent("/engineering/calculators/");
  });

  it("shows results from every source, says what couldn't be reached, and opens a result", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/search": () => jsonResponse(RESULTS) });
    const user = userEvent.setup();
    const { onClose } = renderPalette();
    await user.type(screen.getByRole("combobox"), "pump");
    expect(await screen.findByText("Couldn't reach: Engineering Archive.")).toBeInTheDocument();
    expect(calls.map((c) => c.url)).toEqual(["/api/v1/search?q=pump"]); // debounced: one request
    expect(within(screen.getByRole("region", { name: "Project Management" })).getByText(/station upgrade/)).toBeInTheDocument();
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    // The instant "Pump power" calculator ties with the server's best and stays first; "Ask Siris" is always last.
    expect(options[0]).toMatch(/^Pump power/);
    expect(options[1]).toMatch(/^Pump curves/);
    expect(options.at(-1)).toMatch(/^Ask Siris “pump”/);

    // Down once to the brain note; Enter goes there inside SirisOS.
    expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowDown}{Enter}");
    expect(screen.getByRole("status", { name: "location" })).toHaveTextContent("/brain?q=Pump%20curves");
    expect(onClose).toHaveBeenCalled();
    expect(JSON.parse(localStorage.getItem("sirisos.search.recent")!)).toEqual(["pump"]);
  });

  it("opens other apps in a new tab and apps in their status sheet", async () => {
    signIn();
    mockFetch({ "/api/v1/search": () => jsonResponse(RESULTS) });
    const opened = vi.spyOn(window, "open").mockReturnValue(null);
    const user = userEvent.setup();
    const { onOpenApp } = renderPalette();
    await user.type(screen.getByRole("combobox"), "pump");
    await user.click(await screen.findByRole("option", { name: /Pump station upgrade/ }));
    expect(opened).toHaveBeenCalledWith("http://apd/projects/p1", "_blank", "noopener,noreferrer");
    await user.click(screen.getByRole("option", { name: /Engineering Reviewer/ }));
    expect(onOpenApp).toHaveBeenCalledWith("reviewer");
    opened.mockRestore();
  });

  it("moves with the arrow keys and closes with Escape", async () => {
    signIn();
    mockFetch({ "/api/v1/search": () => jsonResponse(RESULTS) });
    const user = userEvent.setup();
    const { onClose } = renderPalette();
    await user.type(screen.getByRole("combobox"), "pump");
    await screen.findByRole("option", { name: /Pump curves/ });
    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(screen.getByRole("option", { name: /Pump station upgrade/ })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{ArrowUp}");
    expect(screen.getByRole("option", { name: /Pump curves/ })).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});

describe("search in the shell", () => {
  it("opens with Ctrl+K and from the menu", async () => {
    signIn("brad");
    mockFetch({ "/api/v1/hub/apps": () => jsonResponse({ apps: [] }), "/api/v1/brief/status": () => jsonResponse({ show: false }) });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("navigation", { name: "Main" });
    await user.keyboard("{Control>}k{/Control}");
    expect(await screen.findByRole("dialog", { name: "Search everything" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Search everything" })).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Search everything" }));
    expect(await screen.findByRole("dialog", { name: "Search everything" })).toBeInTheDocument();
  });

  it("a chat result reopens that conversation", async () => {
    signIn();
    mockFetch({
      "/api/v1/assistant/conversations/c1": () => jsonResponse([
        { role: "user", content: "What size pump?", tool_name: null, created_at: "" },
        { role: "assistant", content: "About 2 kW.", tool_name: null, created_at: "" },
      ]),
    });
    render(
      <MemoryRouter initialEntries={["/assistant?c=c1"]}>
        <Assistant />
      </MemoryRouter>,
    );
    expect(await screen.findByText("About 2 kW.")).toBeInTheDocument();
  });
});
