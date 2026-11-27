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
    shell("/gym");
    expect(screen.queryByRole("navigation", { name: "SirisGym" })).not.toBeInTheDocument();
  });
});

describe("SirisOS 10.61", () => {
  it("opens each screen at its top, but keeps your place going back", async () => {
    const { ScrollToTop } = await import("../components/Sections");
    const { Link, useNavigate } = await import("react-router-dom");
    const spy = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    function Back() { const nav = useNavigate(); return <button type="button" onClick={() => nav(-1)}>Back</button>; }
    render(
      <MemoryRouter initialEntries={["/"]}>
        <ScrollToTop />
        <Link to="/health">Health</Link><Link to="/health?view=sleep">Sleep</Link><Link to="/fitness">Fitness</Link><Back />
        <Routes><Route path="*" element={<Where />} /></Routes>
      </MemoryRouter>,
    );
    expect(spy).not.toHaveBeenCalled();  // first load: the browser's place
    await userEvent.click(screen.getByRole("link", { name: "Health" }));
    expect(spy).toHaveBeenLastCalledWith(0, 0);
    spy.mockClear();
    await userEvent.click(screen.getByRole("link", { name: "Sleep" }));  // a tab within Health: no jump
    expect(spy).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("link", { name: "Fitness" }));
    expect(spy).toHaveBeenCalledTimes(1);
    spy.mockClear();
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByTestId("where")).toHaveTextContent("/health");
    expect(spy).not.toHaveBeenCalled();
  });
});
