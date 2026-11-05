import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { loadActive, saveActive, type Gym, type SetLog } from "../api/gym";
import { dockBadges } from "../components/Dock";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { GymCoachCard, MorningGymCard } from "./GymCards";
import { GymScreen, startWorkout } from "./Gym";
import { GymWorkoutScreen } from "./GymWorkout";

const GYM = {
  settings: { unit: "kg", bar: 20, plates: [20], increment: 2.5, rest_s: 90, current_gym: "home", warmups: true, warmup_steps: [], gyms: [{ id: "home", name: "Home", bar: 20, plates: [20], dumbbells: [], stack_step: null }] },
  exercises: [{ id: "bench-press", name: "Bench Press", primary: "chest", secondary: [], equipment: "barbell", kind: "weight", custom: false }],
  routines: [], active: null, recent: [], week: { week_of: "2026-11-02", sessions: 0, sets_by_muscle: {}, volume: 0 }, streak_weeks: 0, total_sessions: 3,
} as unknown as Gym;
const SIX = new Date(2026, 10, 5, 6, 30);
const MORNING = { plan: { done: false, title: "PPL: Push", lifts: [{ name: "Bench Press", sets: 3, reps: "5-8", weight: 80 }], more: 2, note: null }, routine: "r1", day: 1, gym: "home", shortcut: "", readiness: { score: 72, band: "Steady" } };

afterEach(() => { saveActive(null); clearResources(); window.sessionStorage.clear(); vi.restoreAllMocks(); });

describe("Morning gym card (7.0)", () => {
  it("shows today's plan and readiness, and starts it in one tap", async () => {
    signIn();
    const plan = { routine: "r1", day: 1, title: "Push", exercises: [{ exercise: "bench-press", sets: 1, reps: "5-8", rest_s: 90, name: "Bench Press", kind: "weight", last: [], suggest: { weight: 80, reps: 8, why: "" } }] };
    const calls = mockFetch({ "/api/v1/gym/morning": () => jsonResponse(MORNING), "/api/v1/gym/plan": () => jsonResponse(plan) });
    render(<MemoryRouter><MorningGymCard at={SIX} /></MemoryRouter>);
    expect(await screen.findByText("PPL: Push")).toBeInTheDocument();
    expect(screen.getByText("Readiness 72 · Steady")).toBeInTheDocument();
    expect(screen.getByText(/Bench Press 3 × 5-8 at 80 kg · and 2 more/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Start it" }));
    await vi.waitFor(() => expect(loadActive()?.title).toBe("Push"));
    expect(calls.some((c) => c.url.includes("/api/v1/gym/plan?routine=r1&day=1"))).toBe(true);
  });

  it("isn't there outside gym time, on a rest day, or once it's done", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/gym/morning": () => jsonResponse(MORNING) });
    const { container } = render(<MemoryRouter><MorningGymCard at={new Date(2026, 10, 5, 8, 0)} /></MemoryRouter>);
    expect(container).toBeEmptyDOMElement();
    expect(calls.some((c) => c.url.includes("/gym/morning"))).toBe(false);
    clearResources();
    mockFetch({ "/api/v1/gym/morning": () => jsonResponse({ plan: { done: false, rest: true, title: "Rest day" } }) });
    const rest = render(<MemoryRouter><MorningGymCard at={SIX} /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 20));
    expect(rest.container).toBeEmptyDOMElement();
  });
});

describe("Weekly coach (7.0)", () => {
  it("shows the changes and why, and nothing when there are none", async () => {
    signIn();
    mockFetch({ "/api/v1/gym/coach": () => jsonResponse({ enough: true, text: "", changes: [{ area: "sleep", title: "Get to bed earlier", why: "Six hours on average." }] }) });
    render(<MemoryRouter><GymCoachCard /></MemoryRouter>);
    expect(await screen.findByText("Get to bed earlier")).toBeInTheDocument();
    expect(screen.getByText("Six hours on average.")).toBeInTheDocument();
    expect(screen.getByText("One change this week")).toBeInTheDocument();
  });
});

describe("Imported days to check (7.0)", () => {
  it("asks about each one and sends your call", async () => {
    signIn();
    const held = { id: "import-20250225", title: "Chest and Back", date: "2025-02-25", started_at: "2025-02-25T07:00:00", minutes: null, sets: 1073, exercises: 40, volume: 524744, names: [], held: true };
    const calls = mockFetch({ "/api/v1/gym/sessions/import-20250225/review": () => jsonResponse({ id: held.id, review: "wrong", left: 0 }), "/api/v1/gym": () => jsonResponse({ ...GYM, held: [held] }) });
    render(<MemoryRouter><GymScreen /></MemoryRouter>);
    expect(await screen.findByText("1 imported day to check")).toBeInTheDocument();
    expect(screen.getByText(/1,073 sets · 524,744 kg/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Leave out" }));
    await vi.waitFor(() => expect(calls.find((c) => c.url.endsWith("/review"))?.init.body).toContain('"wrong"'));
  });
});

describe("Merging duplicates (7.0)", () => {
  it("offers the pair, asks, and merges", async () => {
    signIn();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let dupes = [{ from: "my-a", from_name: "Cable V Bar Pull Down", from_sets: 24, into: "my-b", into_name: "Cable V Bar Pulldown", into_sets: 70, sure: true }];
    const calls = mockFetch({ "/api/v1/gym/duplicates": () => jsonResponse({ duplicates: dupes }), "/api/v1/gym/merge": () => { dupes = []; return jsonResponse({ sets_moved: 24, workouts: 5 }); }, "/api/v1/gym": () => jsonResponse(GYM) });
    window.history.pushState({}, "", "/gym");
    render(<MemoryRouter initialEntries={["/gym?view=exercises"]}><GymScreen /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Merge" }));
    expect(await screen.findByText(/24 sets from 5 workouts moved/)).toBeInTheDocument();
    expect(calls.find((c) => c.url.endsWith("/merge"))?.init.body).toContain("my-a");
  });
});

describe("In a workout (7.0)", () => {
  const session = (sets: SetLog[]) => saveActive({ id: "abc", title: "Push", started_at: new Date().toISOString(), entries: [{ exercise: "bench-press", sets }] });
  const plan = (last: SetLog[]) => window.sessionStorage.setItem("sirisos.gym.plan.abc", JSON.stringify({ routine: "r1", day: 0, title: "Push", exercises: [{ exercise: "bench-press", sets: 2, reps: "5-8", rest_s: 90, name: "Bench Press", kind: "weight", last, suggest: { weight: 100, reps: 8, why: "" } }] }));

  it("lines Last up with working sets, past the warm-ups", async () => {
    signIn();
    mockFetch({ "/api/v1/gym": () => jsonResponse(GYM) });
    plan([{ weight: 100, reps: 8, done: true, type: "normal" }, { weight: 95, reps: 7, done: true, type: "normal" }]);
    session([{ weight: 40, reps: 5, done: false, type: "warmup" }, { weight: 60, reps: 3, done: false, type: "warmup" }, { weight: 100, reps: 8, done: false, type: "normal" }, { weight: 100, reps: 8, done: false, type: "normal" }]);
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await screen.findByText("Push");
    const prev = [...document.querySelectorAll(".gym-sets__prev")].map((e) => e.textContent);
    expect(prev).toEqual(["–", "–", "100×8", "95×7"]);
  });

  it("warns before finishing with sets not ticked, and stays if you say no", async () => {
    signIn();
    const ask = vi.spyOn(window, "confirm").mockReturnValue(false);
    const calls = mockFetch({ "/api/v1/gym/sessions": () => jsonResponse({ summary: {}, records: [] }), "/api/v1/gym": () => jsonResponse(GYM) });
    session([{ weight: 100, reps: 8, done: true, type: "normal" }, { weight: 100, reps: 8, done: false, type: "normal" }]);
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Finish" }));
    expect(ask).toHaveBeenCalledWith(expect.stringContaining("1 set isn't ticked"));
    expect(calls.some((c) => c.url.endsWith("/gym/sessions"))).toBe(false);
    expect(loadActive()).not.toBeNull();
  });

  it("starts sets at last time's reps or the bottom of the range, never the top, and not for timed work", async () => {
    signIn();
    const p = { routine: "r1", day: 0, title: "Push", exercises: [
      { exercise: "bench-press", sets: 1, reps: "5-8", rest_s: 90, name: "Bench Press", kind: "weight", last: [], suggest: { weight: 100, reps: 8, why: "" } },
      { exercise: "row", sets: 1, reps: "6-10", rest_s: 90, name: "Row", kind: "weight", last: [{ weight: 80, reps: 9, done: true, type: "normal" }], suggest: { weight: 80, reps: 10, why: "" } },
      { exercise: "squat", sets: 1, reps: "6-10", rest_s: 90, name: "Squat", kind: "weight", last: [{ weight: 80, reps: 10, done: true, type: "normal" }], suggest: { weight: 82.5, reps: 6, why: "" } },
      { exercise: "plank", sets: 1, reps: "1", rest_s: 90, name: "Plank", kind: "time", last: [], suggest: { weight: null, reps: 1, why: "" } }] };
    mockFetch({ "/api/v1/gym/plan": () => jsonResponse(p) });
    await startWorkout(() => undefined, { id: "r1" } as never, 0);
    expect(loadActive()?.entries.map((e) => e.sets[0].reps)).toEqual([5, 9, 6, null]);
  });
});

describe("The tab bar's dot", () => {
  it("goes by the count", () => {
    expect(dockBadges([], 3)["/brain"]).toContain("3");
    expect(dockBadges([], 0)["/brain"]).toBeUndefined();
  });
});
