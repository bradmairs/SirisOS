import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { HealthScreen } from "./Health";
import { lockNow, type Clarity, type Mind } from "../api/mind";

const day = (i: number) => new Date(Date.UTC(2026, 10, 1 + i)).toISOString().slice(0, 10);
const MIND: Mind = {
  available: true,
  days: Array.from({ length: 12 }, (_, i) => ({ date: day(i), valence: i % 2 ? -0.3 : 0.5, word: i % 2 ? "Slightly unpleasant" : "Pleasant", mindful_minutes: 5, here_minutes: null })),
  today: { date: day(11), valence: 0.5, word: "Pleasant", mindful_minutes: 12, here_minutes: 2 },
  week: { valence: 0.3, word: "Slightly pleasant", before: 0.1, mindful_minutes: 40, mindful_before: 20, mood_days: 6 },
  patterns: [{ key: "sleep", text: "Your mood is better after 7 hours' sleep or more than after less.", with: 0.5, without: -0.2, days: 20 }],
  journal_count: 1, locking: false,
  tools_minutes_week: 6,
};
const CLARITY: Clarity = { started: "2026-11-02", streak: 10, best: 12, next: { days: 14, left: 4 }, clear_last_30: 10,
  month: Array.from({ length: 30 }, (_, i) => ({ date: day(i), status: i > 19 ? "clear" as const : null })), checked_today: null,
  urges_week: 1, rode_out_week: 1, rode_out_all: 3, triggers: [{ trigger: "bored", count: 2 }], times: [{ part: "late night", count: 2 }],
  urges: [], reasons: ["Be present"], plan: [], nudge: false, risky: { hour: 22, count: 3, nudge_at: "21:30" } };
const JOURNAL = { journal: [{ id: "j1", at: "2026-11-11T20:00:00+11:00", kind: "gratitude", text: "Coffee with Sam" }] };

afterEach(() => { lockNow(); clearResources(); vi.restoreAllMocks(); });

function setup(extra: Record<string, (u: string, init?: RequestInit) => Response> = {}, m: Mind = MIND) {
  signIn();
  return mockFetch({ ...extra, "/api/v1/mind/lock": () => jsonResponse({ locked: true }), "/api/v1/mind/journal": () => jsonResponse(JOURNAL),
    "/api/v1/mind/clarity": () => jsonResponse(CLARITY), "/api/v1/mind": () => jsonResponse(m),
    "/api/v1/health": () => jsonResponse({ available: false, guest_mode: false, sources: { sirisai: true, days: 0 } }) });
}

describe("Health 9.1: Mental health", () => {
  it("shows mood, mindful minutes and what helps, even without the rest of Health", async () => {
    setup();
    render(<MemoryRouter initialEntries={["/health?view=mind"]}><HealthScreen /></MemoryRouter>);
    const mood = await screen.findByRole("region", { name: "Mood" });
    expect(within(mood).getByText("Pleasant")).toBeInTheDocument();
    expect(within(mood).getByText("Up")).toBeInTheDocument();
    expect(within(mood).getByRole("img", { name: "Mood over the last 12 days" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Mindful minutes" })).getByText("14")).toBeInTheDocument();
    expect(screen.getByText(/better after 7 hours' sleep/)).toBeInTheDocument();
    expect(await screen.findByText("Coffee with Sam")).toBeInTheDocument();  // no passkey: nothing to lock
    expect(within(mood).queryByRole("button", { name: /Mood \d/ })).not.toBeInTheDocument();  // mood is logged in Apple Health
    expect(screen.getByRole("link", { name: "Lifeline 13 11 14" })).toHaveAttribute("href", "tel:131114");
  });

  it("saves a reframed thought to the journal", async () => {
    const calls = setup({ "/api/v1/mind/journal": () => jsonResponse({ id: "j2" }) });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/health?view=mind"]}><HealthScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("tab", { name: "Reframe" }));
    await user.type(screen.getByLabelText("What did you tell yourself?"), "I always let things slip");
    await user.type(screen.getByLabelText("A fairer way to see it"), "One miss doesn't undo the week");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved to your journal.")).toBeInTheDocument();
    const sent = JSON.parse(String(calls.find((c) => c.url === "/api/v1/mind/journal" && c.init?.method === "POST")!.init.body));
    expect(sent).toEqual({ kind: "reframe", text: "One miss doesn't undo the week", extra: { situation: "", thought: "I always let things slip", evidence: "" } });
  });

  it("keeps Clarity closed, and only loads it when opened", async () => {
    const calls = setup({ "/api/v1/mind/clarity/urge": () => jsonResponse({ ...CLARITY, rode_out_all: 4 }) });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/health?view=mind"]}><HealthScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Clarity" });
    expect(within(card).queryByText("Days clear")).not.toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/mind/clarity")).toBe(false);
    await user.click(within(card).getByRole("button", { name: "Clarity" }));
    expect(await within(card).findByText("Days clear")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "I'm having an urge" }));
    expect(within(card).getByText("Be present")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Bored" }));
    await user.click(within(card).getByRole("button", { name: "It passed" }));
    expect(await within(card).findByText("Ridden out. That's 4.")).toBeInTheDocument();
    const sent = JSON.parse(String(calls.find((c) => c.url === "/api/v1/mind/clarity/urge")!.init.body));
    expect(sent).toMatchObject({ trigger: "bored", outcome: "rode" });
  });
});

describe("Health 9.2: the lock, the nudge and habits", () => {
  it("keeps the journal and Clarity behind Face ID, and drops them when it locks", async () => {
    const calls = setup({}, { ...MIND, locking: true });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/health?view=mind"]}><HealthScreen /></MemoryRouter>);
    const journal = await screen.findByRole("region", { name: "Journal" });
    expect(within(journal).getByText(/Your journal \(1 entry\) is locked/)).toBeInTheDocument();
    expect(screen.queryByText("Coffee with Sam")).not.toBeInTheDocument();
    const card = screen.getByRole("region", { name: "Clarity" });
    await user.click(within(card).getByRole("button", { name: "Clarity" }));
    expect(within(card).getByText(/Clarity is locked/)).toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/mind/clarity" || c.url === "/api/v1/mind/journal")).toBe(false);

    // Face ID: the browser's passkey prompt, stood in for here; SirisOS checks the answer and hands back a token.
    const get = vi.fn(async () => ({ id: "cred1", response: { clientDataJSON: new ArrayBuffer(2), authenticatorData: new ArrayBuffer(2), signature: new ArrayBuffer(2), userHandle: null } }));
    Object.defineProperty(navigator, "credentials", { value: { get }, configurable: true });
    const more = setup({ "/api/v1/mind/unlock/options": () => jsonResponse({ challenge: "Y2hhbGxlbmdl", rpId: "localhost", userVerification: "required", allowCredentials: [{ type: "public-key", id: "Y3JlZDE" }], timeout: 60000 }),
      "/api/v1/mind/unlock": () => jsonResponse({ token: "tok", seconds: 300 }) }, { ...MIND, locking: true });
    await user.click(within(card).getByRole("button", { name: "Unlock with Face ID" }));
    expect(await within(card).findByText("Days clear")).toBeInTheDocument();
    expect(await within(journal).findByText("Coffee with Sam")).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(1);
    const fetched = more.find((c) => c.url === "/api/v1/mind/clarity")!;
    expect(new Headers(fetched.init.headers).get("X-Mind-Unlock")).toBe("tok");

    await user.click(within(journal).getByRole("button", { name: "Lock" }));
    expect(within(journal).queryByText("Coffee with Sam")).not.toBeInTheDocument();
    expect(within(card).queryByText("Days clear")).not.toBeInTheDocument();
    expect(within(card).getByText(/Clarity is locked/)).toBeInTheDocument();
  });

  it("turns the nudge on from Clarity", async () => {
    setup({ "/api/v1/mind/clarity/nudge": () => jsonResponse({ ...CLARITY, nudge: true }) });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/health?view=mind"]}><HealthScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Clarity" });
    await user.click(within(card).getByRole("button", { name: "Clarity" }));
    const box = await within(card).findByRole("checkbox", { name: /A quiet nudge before your usual time \(21:30/ });
    await user.click(box);
    expect(await within(card).findByRole("checkbox", { name: /quiet nudge/ })).toBeChecked();
  });

  it("tracks habits with streaks, and fixes a missed day", async () => {
    const h = (today: boolean, streak: number) => ({ id: "h1", name: "Stretch", created: day(0), streak, best: 5, today, rate: 40,
      month: Array.from({ length: 30 }, (_, i) => ({ date: day(i), done: i === 29 ? today : i > 25 })) });
    const calls = setup({ "/api/v1/mind/habits/h1/check": () => jsonResponse({ habits: [h(true, 4)] }), "/api/v1/mind/habits": () => jsonResponse({ habits: [h(false, 3)] }) });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/health?view=habits"]}><HealthScreen /></MemoryRouter>);
    expect(await screen.findByText(/3-day streak · best 5 · 40% in 30 days/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Stretch: done today" }));
    expect(await screen.findByText(/4-day streak/)).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url === "/api/v1/mind/habits/h1/check")!.init.body))).toEqual({ done: true, date: null });
  });
});
