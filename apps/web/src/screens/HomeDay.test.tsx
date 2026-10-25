import { afterEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Home } from "./Home";
import { clearResources } from "../api/resource";
import { DAY_HIDDEN, type DayPhase, type HomeContext } from "../api/home";
import { jsonResponse, mockFetch, signIn, sseResponse } from "../test/helpers";

/** An ISO time with the device's own offset, as SirisAI sends events ("2026-10-23T09:00:00+11:00"). */
function local(d: Date): string {
  const pad = (n: number) => String(Math.abs(n)).padStart(2, "0");
  const off = -d.getTimezoneOffset();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00${off >= 0 ? "+" : "-"}${pad(Math.floor(Math.abs(off) / 60))}:${pad(Math.abs(off) % 60)}`;
}
const inMinutes = (m: number) => new Date(Date.now() + m * 60_000);
const tomorrowAt = (h: number) => { const d = new Date(); d.setDate(d.getDate() + 1); d.setHours(h, 0, 0, 0); return d; };

const TASKS = {
  date: "", counts: { overdue: 0, today: 2, week: 0, later: 0, someday: 0 },
  groups: { overdue: [], week: [], later: [], someday: [], today: [
    { id: "sirisos:a", source: "sirisos", title: "Send the GVW report", detail: null, due: null, time: null, repeat: "none", group: "today", area: "work", area_set: false },
    { id: "sirisos:b", source: "sirisos", title: "Book the vet", detail: null, due: null, time: null, repeat: "none", group: "today", area: "personal", area_set: true },
  ] },
};

function renderAt(phase: DayPhase, over: Partial<HomeContext> = {}, extra: { system?: object; car?: object } = {}) {
  signIn("brad");
  clearResources();
  for (const k of Object.keys(localStorage)) if (k.startsWith("sirisos.resource.")) localStorage.removeItem(k);
  localStorage.removeItem("sirisos.resource.home:context");
  const ctx: HomeContext = { phase, local_time: "", home: true, wrapped_up: false, top3: [], tomorrow_top3: [], hidden: DAY_HIDDEN[phase],
    sections: ["Today", "Home", "Now"], leave_minutes: 30, events: [], ...over };
  const calls = mockFetch({
    "/api/v1/hub/apps": () => jsonResponse({ apps: [] }),
    "/api/v1/assistant/hud": () => jsonResponse({ weather: { temperature_c: 15, conditions: "clear" }, next_events: [],
      system: extra.system ?? { cpu_percent: 12, memory: { total_gb: 32, used_gb: 8, percent_used: 25 } },
      brain: [{ title: "Pump Station 4", action: "updated" }] }),
    "/api/v1/assistant/widgets": () => jsonResponse({ generated_at: "", guest_mode: false, hidden: [], car: extra.car ?? null, parcels: [], energy: null,
      protocols: [], last_protocol: null, cameras: [], autonomy: null, attention: { open: 2, urgent: 0 }, unavailable: [] }),
    "/api/v1/home/context": () => jsonResponse(ctx),
    "/api/v1/home/layout": () => jsonResponse({ phone: { order: [], hidden: [] }, desktop: { order: [], hidden: [] } }),
    "/api/v1/tasks/sirisos%3Aa/done": () => jsonResponse({ id: "sirisos:a", action: "done" }),
    "/api/v1/tasks": () => jsonResponse(TASKS),
    "/api/v1/attention/stream": () => sseResponse([{ type: "snapshot", items: [], counts: { open: 0, urgent: 0 } }]),
    "/api/v1/attention": () => jsonResponse({ items: [], counts: { open: 0, urgent: 0 } }),
  });
  render(<MemoryRouter><Home /></MemoryRouter>);
  return calls;
}

afterEach(() => localStorage.removeItem("sirisos.home.adaptive"));

describe("Home through the day", () => {
  it("winds down to tomorrow, what the brain learned and a capture box, dimmed, with everything one tap away", async () => {
    const user = userEvent.setup();
    renderAt("winddown", {
      events: [{ title: "Site visit", start: local(tomorrowAt(9)), all_day: false, location: "Werribee" }],
      weather_tomorrow: { date: "", high_c: 19, rain_chance_percent: 10, conditions: "sunny" },
    });
    const card = await screen.findByRole("region", { name: "Tomorrow" });
    expect(card).toHaveTextContent("Site visit");
    expect(card).toHaveTextContent("Werribee");
    expect(card).toHaveTextContent("leave by");
    expect(card).toHaveTextContent("Tomorrow: 19°");
    expect(await screen.findByRole("region", { name: "Learned today" })).toHaveTextContent("Pump Station 4");
    expect(screen.getByRole("region", { name: "Quick capture" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Tasks" })).not.toBeInTheDocument();
    expect(document.querySelector(".home--quiet")).not.toBeNull();

    await user.click(screen.getByRole("button", { name: /Show everything \(\d+ more\)/ }));
    expect(await screen.findByRole("region", { name: "Tasks" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show less" }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Tasks" })).not.toBeInTheDocument());
  });

  it("at work: the next meeting's countdown, work tasks only, the top 3 ticked off in place, and the server only when it needs you", async () => {
    const user = userEvent.setup();
    const calls = renderAt("work", { top3: ["Send the GVW report", "Think about lunch"],
      events: [{ title: "Design review", start: local(inMinutes(25)), all_day: false, location: null }] });
    const next = await screen.findByRole("region", { name: "Next up" });
    expect(next).toHaveTextContent(/Design review\s*in 2[45] min/);
    const tasks = await screen.findByRole("region", { name: "Tasks" });
    expect(within(tasks).getByText("Work tasks")).toBeInTheDocument();
    expect(within(tasks).getByText("Send the GVW report")).toBeInTheDocument();
    expect(within(tasks).queryByText("Book the vet")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Home server" })).not.toBeInTheDocument();   // healthy: quiet

    await user.click(within(within(next).getByRole("list", { name: "Top 3" })).getByRole("button", { name: "Done: Send the GVW report" }));
    await waitFor(() => expect(calls.some((c) => c.url === "/api/v1/tasks/sirisos%3Aa/done")).toBe(true));
    expect(within(next).queryByRole("button", { name: "Done: Think about lunch" })).not.toBeInTheDocument();   // not a task
  });

  it("shows the server when a disk is nearly full", async () => {
    renderAt("work", {}, { system: { cpu_percent: 12, disk: { "/": { total_gb: 100, used_gb: 96, percent_used: 96 } } } });
    await waitFor(() => expect(screen.getByRole("region", { name: "Home server" })).toHaveTextContent("96"));
  });

  it("welcomes you home in the evening, with your own tasks, and the car only when it needs charging", async () => {
    renderAt("evening", { home_since: new Date(Date.now() - 10 * 60_000).toISOString() },
      { car: { name: "the Tesla", summary: "", battery_percent: 30, range: 120, range_unit: "km", charging: false, plugged_in: false, locked: true, location: null, low_battery: false } });
    const card = await screen.findByRole("region", { name: "This evening" });
    expect(within(card).getByRole("status")).toHaveTextContent("Welcome home. 2 things in your inbox");
    const tasks = await screen.findByRole("region", { name: "Tasks" });
    expect(within(tasks).getByText("Book the vet")).toBeInTheDocument();
    expect(within(tasks).queryByText("Send the GVW report")).not.toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "Tesla" })).toBeInTheDocument();
  });

  it("leaves a charged car out of the evening, and doesn't welcome you hours after you got home", async () => {
    renderAt("evening", { home_since: new Date(Date.now() - 3 * 3600_000).toISOString() },
      { car: { name: "the Tesla", summary: "", battery_percent: 80, range: 400, range_unit: "km", charging: false, plugged_in: true, locked: true, location: null, low_battery: false } });
    const card = await screen.findByRole("region", { name: "This evening" });
    expect(within(card).queryByText(/Welcome home/)).not.toBeInTheDocument();
    await screen.findByRole("region", { name: "Tasks" });
    expect(screen.queryByRole("region", { name: "Tesla" })).not.toBeInTheDocument();
  });

  it("says when to leave in the morning for an event with a place", async () => {
    const start = inMinutes(90);
    renderAt("morning", { events: [{ title: "Dentist", start: local(start), all_day: false, location: "Northcote" }] });
    const card = await screen.findByRole("region", { name: "This morning" });
    const leave = new Date(start.getTime() - 30 * 60_000).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    expect(card).toHaveTextContent(`leave by ${leave}`);
  });
});
