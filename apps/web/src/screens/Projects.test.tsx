import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { ProjectScreen, ProjectsScreen } from "./Projects";

const summary = (title: string, extra = {}) => ({ title, status: "active", aliases: [], path: null, due: null, days_left: null, days_idle: null, open_tasks: 0, ...extra });

const page = {
  title: "Werribee Drainage", status: "active", aliases: ["WD"], path: null, names: ["Werribee Drainage", "WD"],
  about: "Upgrading the Werribee outfall drains.", areas: ["Work"], source: "GVW", updated: "2026-10-20",
  links: ["Dana Lee", "Werribee"], backlinks: ["GVW Projects"], deadline: { title: "Werribee Drainage", due: "2026-10-27", days_left: 4 }, days_idle: null,
  tasks: [{ id: "siris:Werribee Drainage|Send levels to Dana", source: "siris", title: "Send levels to Dana", detail: "Werribee Drainage", note: "Werribee Drainage", due: null, time: null, repeat: "none", group: "someday" }],
  meetings: { upcoming: [{ title: "WD design review", start: "2026-10-25T10:00:00+11:00", end: null, all_day: false, location: null, calendar: "Work" }], recent: [] },
  emails: [{ uid: "41", sender: "Dana Lee", subject: "Werribee Drainage levels", date: "Tue, 20 Oct 2026 09:12:00 +1100", snippet: "Attached." }],
  email_configured: true, guest_mode: false, unavailable: [],
};

function at(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/projects" element={<ProjectsScreen />} />
        <Route path="/projects/:title" element={<ProjectScreen />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Projects", () => {
  it("lists active projects with what's due, and finished ones apart", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/siris-projects": () => jsonResponse({ available: true, projects: [
      summary("Werribee Drainage", { days_left: 4, open_tasks: 2 }), summary("CPEng Chartership", { days_idle: 19 }), summary("Akaroa Upgrade", { status: "done" }),
    ] }) });
    at("/projects");
    expect(await screen.findByText("2 active")).toBeInTheDocument();
    const active = screen.getByRole("region", { name: "Active projects" });
    expect(within(active).getByText("Due in 4 days · 2 open tasks")).toBeInTheDocument();
    expect(within(active).getByText("quiet 19 days")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Finished projects" })).getByText("Akaroa Upgrade")).toBeInTheDocument();
    expect(within(active).getByRole("link", { name: /Werribee Drainage/ })).toHaveAttribute("href", "/projects/Werribee%20Drainage");
  });

  it("shows one project's note, tasks, meetings and emails, and adds a task", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/siris-projects/Werribee%20Drainage/tasks": () => jsonResponse({ id: "x", title: "Ring Dana" }),
      "/api/v1/siris-projects/Werribee%20Drainage": () => jsonResponse(page),
    });
    const user = userEvent.setup();
    at("/projects/Werribee%20Drainage");
    expect(await screen.findByRole("heading", { name: "Werribee Drainage" })).toBeInTheDocument();
    expect(screen.getByText("Upgrading the Werribee outfall drains.")).toBeInTheDocument();
    expect(screen.getByText("Due in 4 days")).toBeInTheDocument();
    expect(screen.getByText("Send levels to Dana")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /WD design review/ }).getAttribute("href")).toContain("/meeting?title=WD%20design%20review");
    expect(screen.getByText("Werribee Drainage levels")).toBeInTheDocument();
    expect(screen.getByText("GVW Projects")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "New task for this project" }), "ring Dana friday");
    await user.click(screen.getByRole("button", { name: "Add task" }));
    const post = calls.find((c) => c.init.method === "POST")!;
    expect(JSON.parse(String(post.init.body))).toEqual({ text: "ring Dana friday" });
  });

  it("explains an empty email list", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/siris-projects/X": () => jsonResponse({ ...page, title: "X", emails: [], email_configured: false, meetings: { upcoming: [], recent: [] }, tasks: [] }) });
    at("/projects/X");
    expect(await screen.findByText("Email isn't set up in SirisAI.")).toBeInTheDocument();
    expect(screen.getByText("Nothing open.")).toBeInTheDocument();
    expect(screen.getByText("None in the calendar naming Werribee Drainage or WD.")).toBeInTheDocument();
  });
});
