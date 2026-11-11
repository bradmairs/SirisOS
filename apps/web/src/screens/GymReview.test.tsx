import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { loadActive, saveActive, savePlan, saveRest, type Gym, type Plan, type Session } from "../api/gym";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { GymWorkoutScreen } from "./GymWorkout";
import { ExerciseSheet, GymScreen } from "./Gym";
import { ExerciseFixesCard, LinkHistoryCard, RecoveryCard } from "./GymReview";

const EX = (id: string, name: string, equipment = "barbell") => ({ id, name, primary: "quads", secondary: [], equipment, kind: "weight" as const, custom: false });
const GYM = {
  settings: { unit: "kg", bar: 20, plates: [20, 10, 5, 2.5, 1.25], increment: 2.5, rest_s: 90, rest_between_s: 120, current_gym: "home", warmups: false, warmup_steps: [],
    gyms: [{ id: "home", name: "Home", bar: 20, plates: [20, 10, 5, 2.5, 1.25], dumbbells: [], stack_step: null }] },
  exercises: [EX("back-squat", "Back Squat"), EX("leg-press", "Leg Press", "machine")],
  routines: [], active: null, recent: [{ id: "old1", title: "Legs", date: "2026-11-09", started_at: "2026-11-09T07:00:00", minutes: 40, sets: 6, exercises: 2, volume: 5000, names: [] }],
  week: { week_of: "2026-11-09", sessions: 1, sets_by_muscle: {}, volume: 0 }, streak_weeks: 1, total_sessions: 1, recent_max: { "back-squat": 90, "leg-press": 170 },
  recovery: [{ muscle: "quads", last: "2026-11-09T07:00:00+11:00", hours: 50, ready: 69 }, { muscle: "chest", last: null, hours: null, ready: null }], links: 0,
} as unknown as Gym;
const workout = (entries: Session["entries"], extra: Partial<Session> = {}): Session => ({ id: "w87", title: "Anytime Fitness - November 2026: Legs", routine_id: "r1", started_at: new Date().toISOString(), entries, ...extra });
const PLAN = { routine: "r1", day: 0, title: "Anytime Fitness - November 2026: Legs", exercises: [
  { exercise: "back-squat", sets: 2, reps: "6-10", rest_s: 90, name: "Back Squat", kind: "weight", equipment: "barbell", suggest: { weight: 60, reps: 8, why: "Same as last time." },
    last: [{ weight: 57.5, reps: 8, done: true, type: "normal" }, { weight: 60, reps: 6, done: true, type: "normal" }], best_e1rm: 80, recent_max: 90 }] } as unknown as Plan;

afterEach(() => { saveActive(null); saveRest(null); clearResources(); vi.restoreAllMocks(); });

describe("The workout on the phone (8.7)", () => {
  it("shows the day's name, plates under the bar, and how each set compares with last time", async () => {
    signIn();
    saveActive(workout([{ exercise: "back-squat", sets: [{ weight: 62.5, reps: 8, done: false, type: "normal" }, { weight: 60, reps: 7, done: false, type: "normal" }] }]));
    savePlan("w87", PLAN);
    mockFetch({ "/api/v1/gym": () => jsonResponse(GYM) });
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Legs" })).toBeInTheDocument();
    expect(screen.getByText("Anytime Fitness - November 2026")).toBeInTheDocument();
    expect(screen.getByText("20 + 1.25 a side · +5 kg on last time")).toBeInTheDocument();
    expect(screen.getByText("20 a side · +1 rep on last time")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Swap Back Squat" })).not.toBeInTheDocument();  // behind ⋯
    await userEvent.click(screen.getByRole("button", { name: "More for Back Squat" }));
    expect(screen.getByRole("button", { name: "Swap Back Squat" })).toBeInTheDocument();
  });

  it("asks before ticking a weight far above anything lately, and marks a new best", async () => {
    signIn();
    saveActive(workout([{ exercise: "back-squat", sets: [{ weight: 210, reps: 8, done: false, type: "normal" }, { weight: 85, reps: 5, done: false, type: "normal" }] }]));
    savePlan("w87", PLAN);
    mockFetch({ "/api/v1/gym/rest": () => jsonResponse({}), "/api/v1/gym": () => jsonResponse(GYM) });
    const ask = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const squat = await screen.findByRole("region", { name: "Back Squat" });
    await userEvent.click(within(squat).getByRole("button", { name: "Set 1 done" }));
    expect(ask).toHaveBeenCalledWith(expect.stringContaining("210 kg? That's well over your heaviest lately (90 kg)"));
    expect(within(squat).getByRole("button", { name: "Set 1 done" })).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(within(squat).getByRole("button", { name: "Set 2 done" }));
    expect(within(squat).getByText(/New best: est. 1RM 99.2 kg/)).toBeInTheDocument();
  });

  it("swipe right ticks a set, swipe left offers to delete it", async () => {
    signIn();
    saveActive(workout([{ exercise: "leg-press", sets: [{ weight: 170, reps: 8, done: false, type: "normal" }, { weight: 170, reps: 8, done: false, type: "normal" }] }]));
    mockFetch({ "/api/v1/gym/rest": () => jsonResponse({}), "/api/v1/gym": () => jsonResponse(GYM) });
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const press = await screen.findByRole("region", { name: "Leg Press" });
    const rows = press.querySelectorAll(".gym-sets__set");
    fireEvent.touchStart(rows[0], { touches: [{ clientX: 50, clientY: 100 }] });
    fireEvent.touchEnd(rows[0], { changedTouches: [{ clientX: 200, clientY: 105 }] });
    expect(within(press).getByRole("button", { name: "Set 1 done" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.touchStart(rows[1], { touches: [{ clientX: 300, clientY: 100 }] });
    fireEvent.touchEnd(rows[1], { changedTouches: [{ clientX: 150, clientY: 102 }] });
    await userEvent.click(within(press).getByRole("button", { name: "Delete set 2" }));
    expect(loadActive()!.entries[0].sets).toHaveLength(1);
  });

  it("after finishing: against last time, and how it felt", async () => {
    signIn();
    saveActive(workout([{ exercise: "leg-press", sets: [{ weight: 170, reps: 8, done: true, type: "normal" }] }]));
    const calls = mockFetch({
      "/api/v1/gym/sessions/w87/feel": () => jsonResponse({ id: "w87", feel: 4 }),
      "/api/v1/gym/sessions": () => jsonResponse({ summary: { id: "w87", title: "Legs", date: "", started_at: "", minutes: 30, sets: 1, exercises: 1, volume: 1360, names: [] }, records: [],
        compare: { date: "2026-11-02", title: "Legs", sets: 2, volume: 900, minutes: -5 } }),
      "/api/v1/gym": () => jsonResponse(GYM) });
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Finish the workout" }));
    expect(await screen.findByLabelText("Against last time")).toHaveTextContent("+2 sets, +900 kg volume, 5 min quicker.");
    await userEvent.click(screen.getByRole("radio", { name: "Good" }));
    await vi.waitFor(() => expect(calls.find((c) => c.url.endsWith("/feel"))?.init.body).toBe(JSON.stringify({ feel: 4 })));
  });
});

describe("Your history and your exercises (8.7)", () => {
  it("links a routine exercise to the one your history is under, or keeps it", async () => {
    signIn();
    let links = [{ exercise: "back-squat", name: "Back Squat", sessions: 0, options: [{ id: "my-1", name: "Barbell Squat", sessions: 127, equipment: "barbell" }] },
      { exercise: "face-pull", name: "Face Pull", sessions: 0, options: [{ id: "my-2", name: "Cable Rope Face Pull", sessions: 5, equipment: "cable" }] }];
    const calls = mockFetch({ "/api/v1/gym/links": (_u, init) => { if (init?.method === "POST") links = links.slice(1); return jsonResponse({ links, changed: 1 }); } });
    const changed = vi.fn();
    render(<LinkHistoryCard onChange={changed} />);
    expect(await screen.findByText("Link your history (2)")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Use it" })[0]);
    expect(await screen.findByText("Back Squat now uses your Barbell Squat history (127 workouts).")).toBeInTheDocument();
    expect(calls.find((c) => c.init.method === "POST")?.init.body).toBe(JSON.stringify({ source: "back-squat", into: "my-1" }));
    await userEvent.click(screen.getByRole("button", { name: "Keep as is" }));
    await vi.waitFor(() => expect(calls.filter((c) => c.init.method === "POST")[1]?.init.body).toBe(JSON.stringify({ source: "face-pull", keep: true })));
    expect(changed).toHaveBeenCalled();
  });

  it("tidies imported exercises one at a time or all together", async () => {
    signIn();
    const fixes = [{ id: "a", name: "Back Hyperextension", sessions: 53, now: { kind: "weight", equipment: "other", primary: "triceps" }, change: { kind: "bodyweight", primary: "back" } },
      { id: "b", name: "Sit-Up", sessions: 12, now: { kind: "weight", equipment: "other", primary: "full body" }, change: { kind: "bodyweight" } }];
    const calls = mockFetch({ "/api/v1/gym/exercise-fixes": (_u, init) => jsonResponse(init?.method === "POST" ? { changed: 2, fixes: [] } : { fixes }) });
    render(<ExerciseFixesCard onChange={() => undefined} />);
    expect(await screen.findByText("bodyweight reps, works back")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fix all" }));
    expect(await screen.findByText(/Tidied 2 exercises/)).toBeInTheDocument();
    expect(calls.find((c) => c.init.method === "POST")?.init.body).toBe(JSON.stringify({ ids: ["a", "b"], keep: false }));
  });

  it("fixes a typo in a past workout from the exercise's history", async () => {
    signIn();
    const detail = { exercise: { id: "back-squat", name: "Barbell Squat", primary: "quads", secondary: [], equipment: "barbell", kind: "weight", custom: true },
      records: {}, series: [], videos: [], history: [
        { session: "s1", date: "2026-09-14", sets: [{ weight: 70, reps: 8, done: true, type: "normal" }], e1rm: 88.7, volume: 560 },
        { session: "s2", date: "2026-09-21", sets: [{ weight: 210, reps: 8, done: true, type: "normal" }], e1rm: 266, volume: 1680 },
        { session: "s3", date: "2026-09-28", sets: [{ weight: 70, reps: 8, done: true, type: "normal" }], e1rm: 88.7, volume: 560 }] };
    const calls = mockFetch({ "/api/v1/gym/sessions/s2/sets": () => jsonResponse({ summary: {}, records: [] }), "/api/v1/gym/exercises/back-squat": () => jsonResponse(detail) });
    render(<MemoryRouter><ExerciseSheet id="back-squat" unit="kg" onClose={() => undefined} /></MemoryRouter>);
    expect(await screen.findByText(/looks like a typo/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Fix the sets on .*(21 Sep|Sep 21)/ }));
    const box = screen.getByRole("textbox", { name: "Set 1 weight" });
    await userEvent.clear(box);
    await userEvent.type(box, "70");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(calls.find((c) => c.url.endsWith("/s2/sets"))?.init.body).toBe(JSON.stringify({ exercise: "back-squat", sets: [{ weight: 70, reps: 8, seconds: null, km: null }] })));
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();  // your own exercise: editable
  });

  it("shows recovery, and repeats the last workout", async () => {
    signIn();
    render(<RecoveryCard recovery={(GYM as unknown as { recovery: never[] }).recovery} />);
    expect(screen.getByTitle("quads: trained 2 days ago")).toHaveTextContent("69%");
    expect(screen.getByTitle("chest: trained not lately")).toHaveTextContent("fresh");
    clearResources();
    mockFetch({
      "/api/v1/gym/sessions/old1": () => jsonResponse({ id: "old1", title: "Legs", started_at: "2026-11-09T07:00:00", routine_id: "r1", day: 4, summary: {}, records: [],
        entries: [{ exercise: "leg-press", name: "Leg Press", sets: [{ weight: 170, reps: 8, done: true, type: "normal" }, { weight: 180, reps: 6, done: true, type: "normal" }] }] }),
      "/api/v1/gym": () => jsonResponse(GYM) });
    render(<MemoryRouter><GymScreen /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: /Repeat last/ }));
    await vi.waitFor(() => expect(loadActive()?.entries[0].sets.map((x) => [x.weight, x.reps, x.done])).toEqual([[170, 8, false], [180, 6, false]]));
  });
});
