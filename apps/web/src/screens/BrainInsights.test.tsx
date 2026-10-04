import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrainInsights } from "./BrainInsights";
import type { BrainInsights as Insights } from "../api/types";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const INSIGHTS: Insights = {
  date: "2026-10-03",
  highlights: ["24 notes learned or updated this week (up from 10).", "Race is due in 7 days (2026-10-10)."],
  summary: { notes: 76, links: 262, learned_by_siris: 68, links_per_note: 6.9, this_week: 24, previous_week: 10, streak_days: 3, open_tasks: 11, inbox: 2 },
  activity: [
    { date: "2026-10-01", notes: 0 },
    { date: "2026-10-02", notes: 5 },
    { date: "2026-10-03", notes: 2 },
  ],
  topics: [{ tag: "self-hosting", notes: 22, previous: 4 }],
  hubs: [{ title: "SirisOS", links: 26 }],
  orphans: [],
  stale_projects: [{ title: "Old Thing", last_activity: "2026-08-01", days_idle: 63 }],
  deadlines: [{ title: "Race", due: "2026-10-10", days_left: 7 }],
  overdue_tasks: [{ task: "Taper", note: "Race", due: "2026-10-01", days_late: 2 }],
  inbox: { count: 2, oldest: "2026-09-20" },
  gaps: { fill_in: 7 },
  suggested_links: [{ a: "Immich", b: "Siris Engineering Archive", score: 0.06, why: "both mention photos, videos" }],
};

describe("<BrainInsights />", () => {
  it("shows what the brain noticed, the numbers, and what needs attention", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/brain/insights": () => jsonResponse(INSIGHTS) });
    render(<BrainInsights />);

    expect(await screen.findByText("24 notes learned or updated this week (up from 10).")).toBeInTheDocument();
    expect(calls[0].url).toBe("/api/v1/brain/insights?days=30");
    expect(screen.getByText("This week · +14 vs last")).toBeInTheDocument();
    expect(screen.getByText("Last 3 days · 7 note updates")).toBeInTheDocument();
    expect(screen.getByText("Race · 2 days late")).toBeInTheDocument();
    expect(screen.getByText("Untouched for 63 days")).toBeInTheDocument();
    expect(screen.getByText("Inbox: 2 items")).toBeInTheDocument();
    expect(screen.getByText("Immich ↔ Siris Engineering Archive")).toBeInTheDocument();
    expect(screen.getByText("#self-hosting")).toBeInTheDocument();

    // The per-day numbers are readable without the chart, too.
    const table = screen.getByRole("table", { name: "Notes learned or updated per day" });
    expect(within(table).getByRole("rowheader", { name: "2026-10-02" }).nextSibling).toHaveTextContent("5");
  });

  it("reads out a day when the pointer is on its bar", async () => {
    signIn();
    mockFetch({ "/api/v1/brain/insights": () => jsonResponse(INSIGHTS) });
    const { container } = render(<BrainInsights />);
    await screen.findByText("What the brain noticed");
    fireEvent.pointerEnter(container.querySelectorAll(".activity__slot")[1]);
    expect(screen.getByText(/· 5 notes$/)).toBeInTheDocument();
    fireEvent.pointerLeave(container.querySelector(".activity__bars")!);
    expect(screen.getByText("Last 3 days · 7 note updates")).toBeInTheDocument();
  });

  it("says why insights are missing", async () => {
    signIn();
    mockFetch({ "/api/v1/brain/insights": () => jsonResponse({ detail: "SirisAI: No second brain configured. Set SIRISAI_BRAIN_PATH." }, 404) });
    render(<BrainInsights />);
    expect(await screen.findByText(/SIRISAI_BRAIN_PATH/)).toBeInTheDocument();
  });

  it("links a suggested pair, then refreshes so the next suggestion moves up", async () => {
    signIn();
    const two = { ...INSIGHTS, suggested_links: [
      { a: "Nicole Mairs", b: "Ryan Mairs", score: 0.85, why: "similar meaning" },
      { a: "Finances", b: "Health", score: 0.83, why: "similar meaning" },
    ] };
    let served = two;
    const calls = mockFetch({
      "/api/v1/brain/insights": () => jsonResponse(served),
      "/api/v1/brain/link": (_u, init) => {
        served = { ...two, suggested_links: [two.suggested_links[1], { a: "Creativity", b: "Learning", score: 0.8, why: "similar meaning" }] };
        const { a, b } = JSON.parse(init.body as string);
        return jsonResponse({ action: "linked", a, b });
      },
    });
    const user = userEvent.setup();
    render(<BrainInsights />);
    await user.click(await screen.findByRole("button", { name: "Link Nicole Mairs and Ryan Mairs" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Linked Nicole Mairs and Ryan Mairs");
    const sent = calls.find((c) => c.url === "/api/v1/brain/link")!;
    expect(JSON.parse(sent.init.body as string)).toEqual({ a: "Nicole Mairs", b: "Ryan Mairs" });
    expect(screen.queryByText("Nicole Mairs ↔ Ryan Mairs")).not.toBeInTheDocument();
    expect(await screen.findByText("Creativity ↔ Learning")).toBeInTheDocument();
  });

  it("dismisses a pair as not related, and shows an error in place if it fails", async () => {
    signIn();
    const pairs = { ...INSIGHTS, suggested_links: [{ a: "Finances", b: "Health", score: 0.83, why: "similar meaning" }] };
    let fail = true;
    const calls = mockFetch({
      "/api/v1/brain/insights": () => jsonResponse(pairs),
      "/api/v1/brain/not-related": () =>
        fail ? jsonResponse({ detail: "SirisAI: No note called 'Health'" }, 422) : jsonResponse({ action: "dismissed", a: "Finances", b: "Health" }),
    });
    const user = userEvent.setup();
    render(<BrainInsights />);
    const dismiss = await screen.findByRole("button", { name: "Finances and Health aren't related" });
    await user.click(dismiss);
    expect(await screen.findByText("SirisAI: No note called 'Health'")).toBeInTheDocument();
    expect(screen.getByText("Finances ↔ Health")).toBeInTheDocument();

    fail = false;
    await user.click(screen.getByRole("button", { name: "Finances and Health aren't related" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Won't suggest Finances and Health again");
    await waitFor(() => expect(calls.filter((c) => c.url === "/api/v1/brain/not-related")).toHaveLength(2));
  });
});
