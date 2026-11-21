import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { clearResources } from "../api/resource";
import { Sidebar, NAV } from "../components/Sidebar";
import { SECTIONS, SectionTabs, sectionFor, sectionHref } from "../components/Sections";

afterEach(() => { clearResources(); vi.restoreAllMocks(); localStorage.clear(); });

function Where() { return <span data-testid="where">{useLocation().pathname}</span>; }
const shell = (at: string) => render(
  <MemoryRouter initialEntries={[at]}>
    <Sidebar apps={[]} user="brad" open onClose={() => undefined} onSignOut={() => undefined} />
    <SectionTabs />
    <Routes><Route path="*" element={<Where />} /></Routes>
  </MemoryRouter>,
);

describe("SirisOS 10.5", () => {
  it("lists 13 sections under headings instead of 26 screens", () => {
    shell("/");
    const menu = screen.getByRole("navigation", { name: "Screens" });
    const sections = SECTIONS.flatMap((g) => g.sections);
    expect(sections).toHaveLength(13);
    for (const s of sections) expect(within(menu).getByRole("link", { name: s.label })).toBeInTheDocument();
    for (const gone of ["Wrap Up", "Weekly Review", "Your Year", "Engineering", "Home Lab", "Terminal", "Trips", "Meals"]) {
      expect(within(menu).queryByRole("link", { name: gone })).not.toBeInTheDocument();
    }
    expect(within(menu).getByText("Home & life")).toBeInTheDocument();
  });

  it("puts every screen in exactly one section, so none is lost from the menu", () => {
    for (const n of NAV) expect(sectionFor(n.to)?.section, n.to).toBeTruthy();
    const tabs = SECTIONS.flatMap((g) => g.sections.flatMap((s) => s.tabs.map((t) => t.to)));
    expect(new Set(tabs).size).toBe(tabs.length);
  });

  it("shows the section's tabs on a grouped screen and lights up its menu entry", async () => {
    shell("/engineering");
    const tabs = screen.getByRole("navigation", { name: "Work" });
    expect(within(tabs).getByRole("link", { name: "Engineering" })).toHaveAttribute("aria-current", "page");
    expect(within(screen.getByRole("navigation", { name: "Screens" })).getByRole("link", { name: "Work" })).toHaveAttribute("aria-current", "page");
    await userEvent.click(within(tabs).getByRole("link", { name: "Career" }));
    expect(screen.getByTestId("where")).toHaveTextContent("/career");
  });

  it("goes back to the tab you used last in a section", () => {
    const { unmount } = shell("/homelab");
    unmount();
    const server = SECTIONS.flatMap((g) => g.sections).find((s) => s.id === "server")!;
    expect(sectionHref(server)).toBe("/homelab");
    shell("/");
    expect(within(screen.getByRole("navigation", { name: "Screens" })).getByRole("link", { name: "Server" })).toHaveAttribute("href", "/homelab");
  });

  it("leaves single screens without tabs", () => {
    shell("/budget");
    expect(screen.queryByRole("navigation", { name: "Budget" })).not.toBeInTheDocument();
  });
});
