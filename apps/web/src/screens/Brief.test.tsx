import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";
import type { Brief } from "../api/brief";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { BriefView, ago } from "./Brief";

const STATUS = { date: "2026-10-08", show: true, dismissed_today: false, from: "04:00", until: "09:00" };

const BRIEF: Brief = {
  date: "2026-10-08",
  weekday: "Thursday",
  generated_at: "2026-10-08T06:30:00+11:00",
  greeting: "Good morning, Brad",
  headline: ["21° today, showers, 70% chance of rain: take a jacket.", "2 things on today, starting with Site meeting at 9:30 am."],
  weather: { now: { temperature_c: 9.4, conditions: "Clear" }, today: { high_c: 21.4, low_c: 8, conditions: "Showers", rain_chance_percent: 70 } },
  schedule: [{ title: "Site meeting", time: "9:30 am", location: "Shepparton", calendar: "Gmail" }],
  tasks: [{ title: "Send RFI", detail: "Pump station · 2 days late", tone: "critical", source: "Second Brain" }],
  todo: ["Bins out"],
  email: { unread: 4, important: [{ from: "Jane Smith", subject: "Pump quote" }] },
  health: ["Slept 6.2 h"],
  home: ["Parcel: Bunnings order out for delivery"],
  apps_attention: [{ name: "Engineering Archive", state: "down", detail: "timeout" }],
  brain: { inbox: 3, auto_linked: 5, pending_links: 0, unsure_links: 2, highlights: ["3 notes this week."] },
  news: {
    interests_from: "Daily Briefing Preferences",
    topics: [
      { topic: "AI and emerging technology", stories: [
        { title: "Ollama ships a faster runtime", url: "https://news.example/1", source: "The Verge", published: new Date(Date.now() - 2 * 3600_000).toISOString(), topic: "AI", matches: ["ollama"] },
      ] },
      { topic: "Top stories", stories: [{ title: "National story", url: "https://news.example/2", source: "ABC News", published: null, topic: "Top stories", matches: [] }] },
    ],
  },
  unavailable: ["health"],
  status: STATUS,
};

describe("ago", () => {
  it("reads like a news byline", () => {
    const now = Date.parse("2026-10-08T08:00:00Z");
    expect(ago("2026-10-08T07:55:00Z", now)).toBe("5 min ago");
    expect(ago("2026-10-08T05:00:00Z", now)).toBe("3 h ago");
    expect(ago("2026-10-06T08:00:00Z", now)).toBe("2 d ago");
    expect(ago(null, now)).toBe("");
  });
});

describe("<BriefView />", () => {
  it("shows the day, the news picked for Brad, and what couldn't be reached", async () => {
    signIn();
    mockFetch({ "/api/v1/brief": () => jsonResponse(BRIEF) });
    render(
      <MemoryRouter>
        <BriefView />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { level: 1, name: "Good morning, Brad" })).toBeInTheDocument();
    const glance = screen.getByRole("region", { name: "At a glance" });
    expect(within(glance).getByText(/take a jacket/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Schedule" })).getByText("9:30 am · Gmail · Shepparton")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Tasks" })).getByText("Bins out")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Email" })).getByText("Pump quote")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Needs a look" })).getByText("Engineering Archive")).toBeInTheDocument();

    const ai = screen.getByRole("region", { name: "AI and emerging technology" });
    const story = within(ai).getByRole("link", { name: /Ollama ships a faster runtime/ });
    expect(story).toHaveAttribute("href", "https://news.example/1");
    expect(story).toHaveAttribute("target", "_blank");
    expect(story).toHaveTextContent("The Verge · 2 h ago · ollama");
    expect(screen.getByText(/Daily Briefing Preferences/)).toBeInTheDocument();
    expect(screen.getByText(/Couldn't reach: health/)).toBeInTheDocument();
    // Not the overlay: nothing to dismiss.
    expect(screen.queryByRole("button", { name: /start my day/i })).not.toBeInTheDocument();
  });

  it("refreshes on demand", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/brief": () => jsonResponse(BRIEF) });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <BriefView />
      </MemoryRouter>,
    );
    await screen.findByText("Good morning, Brad");
    await user.click(screen.getByRole("button", { name: "Refresh the brief" }));
    await waitFor(() => expect(calls.some((c) => c.url === "/api/v1/brief?fresh=true")).toBe(true));
  });
});

describe("morning overlay", () => {
  it("opens by itself in the morning and closing it dismisses it for the day", async () => {
    signIn("brad");
    const calls = mockFetch({
      "/api/v1/brief/dismiss": () => jsonResponse({ ...STATUS, show: false, dismissed_today: true }),
      "/api/v1/brief/status": () => jsonResponse(STATUS),
      "/api/v1/brief": () => jsonResponse(BRIEF),
      "/api/v1/hub/apps": () => jsonResponse({ apps: [] }),
    });
    const user = userEvent.setup();
    render(<App />);
    const overlay = await screen.findByRole("dialog", { name: "Today's brief" });
    expect(await within(overlay).findByText(/take a jacket/)).toBeInTheDocument();
    await user.click(within(overlay).getByRole("button", { name: /start my day/i }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Today's brief" })).not.toBeInTheDocument());
    const dismiss = calls.find((c) => c.url === "/api/v1/brief/dismiss");
    expect(dismiss?.init.method).toBe("POST");
  });

  it("stays closed outside the window or once dismissed", async () => {
    signIn("brad");
    mockFetch({
      "/api/v1/brief/status": () => jsonResponse({ ...STATUS, show: false }),
      "/api/v1/hub/apps": () => jsonResponse({ apps: [] }),
    });
    render(<App />);
    expect(await screen.findByRole("navigation", { name: "Main" })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByRole("dialog", { name: "Today's brief" })).not.toBeInTheDocument();
    for (const link of screen.getAllByRole("link", { name: "Today's brief" })) expect(link).toHaveAttribute("href", "/brief");
  });

  it("closes with Escape", async () => {
    signIn("brad");
    const calls = mockFetch({
      "/api/v1/brief/dismiss": () => jsonResponse({ ...STATUS, show: false, dismissed_today: true }),
      "/api/v1/brief/status": () => jsonResponse(STATUS),
      "/api/v1/brief": () => jsonResponse(BRIEF),
      "/api/v1/hub/apps": () => jsonResponse({ apps: [] }),
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("dialog", { name: "Today's brief" });
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Today's brief" })).not.toBeInTheDocument());
    expect(calls.some((c) => c.url === "/api/v1/brief/dismiss")).toBe(true);
  });
});
