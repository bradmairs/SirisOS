import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { e1rm, plates, saveActive, shortcuts, type Gym } from "../api/gym";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { GymWorkoutScreen } from "./GymWorkout";
import { GymScreen } from "./Gym";
import * as voice from "../api/voice";

const GYM: Gym = {
  settings: { unit: "kg", bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25], increment: 2.5, rest_s: 90, current_gym: "home", warmups: true,
    warmup_steps: [{ percent: 0.4, reps: 5 }, { percent: 0.6, reps: 3 }, { percent: 0.8, reps: 2 }],
    gyms: [{ id: "home", name: "Home", bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25], dumbbells: [], stack_step: null },
           { id: "work", name: "Work gym", bar: 15, plates: [20, 10, 5, 2.5], dumbbells: [10, 12.5, 15], stack_step: 5 }] },
  exercises: [{ id: "bench-press", name: "Bench Press", primary: "chest", secondary: ["triceps"], equipment: "barbell", kind: "weight", custom: false }],
  routines: [{ id: "r1", name: "Push, pull, legs", days: [{ name: "Push", exercises: [{ exercise: "bench-press", sets: 3, reps: "5-8", rest_s: 120 }] }], active: true }],
  active: { routine: "r1", next_day: 0 }, recent: [], week: { week_of: "2026-11-02", sessions: 1, sets_by_muscle: { chest: 3, triceps: 1.5 }, volume: 2400 },
  streak_weeks: 4, total_sessions: 12,
};

afterEach(() => { saveActive(null); clearResources(); });

describe("gym maths (6.5)", () => {
  it("estimates a 1RM and loads the bar", () => {
    expect(e1rm(100, 5)).toBe(116.7);
    expect(plates(102.5, 20, GYM.settings.plates)).toEqual({ perSide: [25, 15, 1.25], left: 0 });
  });
});

describe("<GymScreen />", () => {
  it("offers today's routine day and shows the week by muscle", async () => {
    signIn();
    mockFetch({ "/api/v1/gym": () => jsonResponse(GYM) });
    render(<MemoryRouter><GymScreen /></MemoryRouter>);
    expect(await screen.findByRole("button", { name: "Start Push" })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Sets by muscle this week" })).getByText("chest")).toBeInTheDocument();
    expect(screen.getByText("12 workouts · 4-week streak")).toBeInTheDocument();
  });
});

describe("SirisGym 6.7", () => {
  it("starts at the chosen gym with warm-ups and per-set weights, and keeps supersets", async () => {
    signIn();
    const plan = { routine: "r1", day: 0, title: "Push", gym: "work", exercises: [
      { exercise: "bench-press", sets: 2, reps: "5", rest_s: 120, group: "A", progression: "percent", name: "Bench Press", kind: "weight", equipment: "barbell", last: [],
        suggest: { weight: 72.5, reps: 5, per_set: [72.5, 85], training_max: 105, why: "70%, 80% of your training max", last_note: "Elbows in" },
        warmups: [{ weight: 15, reps: 10 }, { weight: 30, reps: 5 }] }] };
    const calls = mockFetch({ "/api/v1/gym/plan": () => jsonResponse(plan), "/api/v1/gym/settings": () => jsonResponse(GYM.settings), "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("radio", { name: "Work gym" }));
    await user.click(screen.getByRole("button", { name: "Start Push" }));
    expect(calls.some((c) => c.url.includes("/api/v1/gym/plan?routine=r1&day=0&gym=work"))).toBe(true);
    const s = JSON.parse(window.localStorage.getItem("sirisos.gym.active")!);
    expect(s.gym).toBe("work");
    expect(s.entries[0].group).toBe("A");
    expect(s.entries[0].sets.map((x: { type: string; weight: number }) => `${x.type}:${x.weight}`)).toEqual(["warmup:15", "warmup:30", "normal:72.5", "normal:85"]);
  });

  it("rests after the superset's last exercise, and records effort and a note", async () => {
    signIn();
    saveActive({ id: "w2", title: "Push", started_at: new Date().toISOString(), entries: [
      { exercise: "bench-press", group: "A", sets: [{ weight: 80, reps: 8, done: false, type: "normal" }] },
      { exercise: "barbell-row", group: "A", sets: [{ weight: 60, reps: 10, done: false, type: "normal" }] }] });
    mockFetch({ "/api/v1/gym": () => jsonResponse({ ...GYM, exercises: [...GYM.exercises,
      { id: "barbell-row", name: "Barbell Row", primary: "back", secondary: [], equipment: "barbell", kind: "weight", custom: false }] }) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const bench = await screen.findByRole("region", { name: "Bench Press" });
    await user.click(within(bench).getByRole("button", { name: "Set 1 done" }));
    expect(screen.queryByRole("timer", { name: "Rest" })).not.toBeInTheDocument();  // straight to the row
    await user.click(within(bench).getByRole("button", { name: "Set 1 effort (RPE)" }));
    await user.click(within(bench).getByRole("button", { name: "Set 1 effort (RPE)" }));
    await user.type(within(bench).getByRole("textbox", { name: "Note for Bench Press" }), "Elbows in");
    await user.click(within(screen.getByRole("region", { name: "Barbell Row" })).getByRole("button", { name: "Set 1 done" }));
    expect(screen.getByRole("timer", { name: "Rest" })).toBeInTheDocument();
    const kept = JSON.parse(window.localStorage.getItem("sirisos.gym.active")!);
    expect(kept.entries[0].sets[0].rpe).toBe(8);
    expect(kept.entries[0].note).toBe("Elbows in");
  });

  it("edits a gym's dumbbells in Settings and saves", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/gym/settings": (_u, init) => jsonResponse(JSON.parse(String(init?.body))), "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/gym?view=settings"]}><GymScreen /></MemoryRouter>);
    const home = await screen.findByRole("region", { name: "Gym: Home" });
    const dbs = within(home).getByLabelText(/Dumbbells on the rack/);
    await user.type(dbs, "5, 7.5, 10");
    await user.tab();
    await user.click(screen.getByRole("button", { name: "Save settings" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    const sent = JSON.parse(String(calls.find((c) => c.url === "/api/v1/gym/settings")!.init.body));
    expect(sent.gyms[0].dumbbells).toEqual([5, 7.5, 10]);
  });
});

describe("SirisGym 6.8", () => {
  it("shows today's readiness, offers a deload, and the week's sets against targets", async () => {
    signIn();
    const g = { ...GYM, readiness: { score: 38, band: "Recover" }, deload: { active: false, until: null, suggest: true, why: ["bench Press has stalled for three sessions"] },
      muscles: [{ muscle: "chest", sets: 12, target: [10, 20], status: "in range" }, { muscle: "back", sets: 4, target: [10, 20], status: "under" }] };
    const calls = mockFetch({ "/api/v1/gym/deload": () => jsonResponse({ active: true, until: "2026-11-10", suggest: false, why: [] }), "/api/v1/gym": () => jsonResponse(g) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymScreen /></MemoryRouter>);
    expect(await screen.findByText(/Readiness 38: today's plan is a set lighter/)).toBeInTheDocument();
    expect(screen.getByText(/Under the 10-20 sets a week: back/)).toBeInTheDocument();
    const card = screen.getByRole("region", { name: "Deload" });
    expect(card).toHaveTextContent("Bench Press has stalled for three sessions");
    await user.click(within(card).getByRole("button", { name: "Start a deload week" }));
    expect(JSON.parse(String(calls.find((c) => c.url === "/api/v1/gym/deload")!.init.body))).toEqual({ on: true, days: 7 });
  });

  it("shows strength against bodyweight and the year in review", async () => {
    signIn();
    mockFetch({
      "/api/v1/gym/strength": () => jsonResponse({ bodyweight: 80, lifts: [{ exercise: "bench-press", name: "Bench Press", best: 116.7, date: "2026-03-01", this_year: 116.7, last_year: 105, ratio: 1.46, level: "intermediate" }] }),
      "/api/v1/gym/year": () => jsonResponse({ year: 2026, sessions: 120, hours: 130, sets: 2400, volume: 480000, previous: { sessions: 100, hours: 110, sets: 2000, volume: 400000 },
        months: Array.from({ length: 12 }, (_, i) => ({ month: `2026-${String(i + 1).padStart(2, "0")}`, sessions: 10, volume: 40000, records: i === 2 ? 2 : 0 })),
        muscles: [{ muscle: "chest", sets: 500 }], best: [{ exercise: "bench-press", name: "Bench Press", e1rm: 116.7, date: "2026-03-01" }] }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    render(<MemoryRouter initialEntries={["/gym?view=progress"]}><GymScreen /></MemoryRouter>);
    const strength = await screen.findByRole("region", { name: "Strength" });
    expect(await within(strength).findByText("Bench Press: 116.7 kg")).toBeInTheDocument();
    expect(strength).toHaveTextContent("1.46× bw");
    expect(strength).toHaveTextContent("this year 116.7 (+11% on last year)");
    const year = screen.getByRole("region", { name: "Year in review" });
    expect(await within(year).findByText("480 t")).toBeInTheDocument();
    expect(year).toHaveTextContent("Workouts +20%");
  });
});

describe("SirisGym 6.9", () => {
  it("drafts a programme from a goal into the routine editor", async () => {
    signIn();
    const routine = { id: "", name: "Muscle, 4 days", active: false, note: "", days: [{ name: "Upper 1", exercises: [{ exercise: "bench-press", sets: 3, reps: "6-10", rest_s: 120 }] }] };
    const calls = mockFetch({
      "/api/v1/gym/builder": () => jsonResponse({ routine, chosen: { days: 4, goal: "muscle", minutes: 60, equipment: "gym", avoid: ["shoulder"] }, read: {},
        note: "4 days a week for muscle, about 60 minutes, in a gym. Spares the shoulder." }),
      "/api/v1/gym/templates": () => jsonResponse({ templates: [] }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/gym?view=routines"]}><GymScreen /></MemoryRouter>);
    await user.type(await screen.findByRole("textbox", { name: "Your goal" }), "4 days, hypertrophy, bad left shoulder");
    await user.click(screen.getByRole("button", { name: "knee" }));
    await user.click(screen.getByRole("button", { name: "Draft it" }));
    expect(await screen.findByRole("textbox", { name: "Routine name" })).toHaveValue("Muscle, 4 days");
    const sent = JSON.parse(String(calls.find((c) => c.url === "/api/v1/gym/builder")!.init.body));
    expect(sent).toMatchObject({ text: "4 days, hypertrophy, bad left shoulder", avoid: ["knee"] });
  });

  it("logs a set by voice and rings when the rest is over", async () => {
    signIn();
    saveActive({ id: "w3", title: "Push", started_at: new Date().toISOString(), entries: [
      { exercise: "bench-press", sets: [{ weight: 80, reps: null, done: false, type: "normal" }, { weight: 80, reps: null, done: false, type: "normal" }] }] });
    vi.spyOn(voice, "micUnavailableReason").mockReturnValue(null);
    vi.spyOn(voice, "startRecording").mockResolvedValue({ done: Promise.resolve(new Blob(["x"])), stop: () => {}, heard: () => true } as unknown as voice.Recording);
    const calls = mockFetch({
      "/api/v1/assistant/voice/transcribe": () => jsonResponse({ text: "Bench eighty two point five by eight RPE 8" }),
      "/api/v1/gym/rest": () => jsonResponse({ ringing_in: 90 }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Log a set by voice" }));
    expect(await screen.findByText("Logged Bench Press: 82.5 × 8 at RPE 8.")).toBeInTheDocument();
    const kept = JSON.parse(window.localStorage.getItem("sirisos.gym.active")!);
    expect(kept.entries[0].sets[0]).toMatchObject({ weight: 82.5, reps: 8, rpe: 8, done: true });
    const rest = calls.find((c) => c.url === "/api/v1/gym/rest" && c.init.method === "POST")!;
    expect(JSON.parse(String(rest.init.body))).toEqual({ seconds: 90, next: "Bench Press, set 2: 80 kg" });
    vi.restoreAllMocks();
  });

  it("shows measurements against the weight trend, and compares two photos", async () => {
    signIn();
    window.URL.createObjectURL = vi.fn(() => "blob:photo");
    mockFetch({
      "/api/v1/gym/body": () => jsonResponse({ measurements: [{ id: "a", date: "2026-08-01", waist: 88 }, { id: "b", date: "2026-11-01", waist: 84.5, arm: 38 }],
        photos: [{ id: "p1", date: "2026-08-01", pose: "front", note: "" }, { id: "p2", date: "2026-11-01", pose: "front", note: "" }],
        weight: [{ date: "2026-10-01", kg: 83, trend: 83.2 }, { date: "2026-11-01", kg: 81.2, trend: 81.5 }] }),
      "/api/v1/gym/photos/": () => new Response(new Blob(["img"], { type: "image/jpeg" })),
      "/api/v1/gym/strength": () => jsonResponse({ bodyweight: null, lifts: [] }),
      "/api/v1/gym/year": () => jsonResponse({ year: 2026, sessions: 0, hours: 0, sets: 0, volume: 0, previous: { sessions: 0, hours: 0, sets: 0, volume: 0 }, months: [], muscles: [], best: [] }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    render(<MemoryRouter initialEntries={["/gym?view=progress"]}><GymScreen /></MemoryRouter>);
    const body = await screen.findByRole("region", { name: "Body" });
    expect(await within(body).findByText("Waist: 84.5 cm")).toBeInTheDocument();
    expect(body).toHaveTextContent("-3.5 cm since");
    expect(body).toHaveTextContent("81.2 kg");
    const photos = screen.getByRole("region", { name: "Progress photos" });
    expect(await within(photos).findByRole("img", { name: "front, 2026-08-01" })).toHaveAttribute("src", "blob:photo");
    expect(within(photos).getByRole("img", { name: "front, 2026-11-01" })).toBeInTheDocument();
  });
});

describe("SirisGym 6.92: Shortcuts", () => {
  it("runs the start Shortcut on iPhone and comes back to the workout", async () => {
    signIn();
    const ua = vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)");
    const opened: string[] = [];
    const open = vi.spyOn(shortcuts, "open").mockImplementation((u: string) => { opened.push(u); });
    const plan = { routine: "r1", day: 0, title: "Push", exercises: [] };
    mockFetch({ "/api/v1/gym/plan": () => jsonResponse(plan), "/api/v1/gym": () => jsonResponse({ ...GYM, settings: { ...GYM.settings, shortcut_start: "SirisGym Start" } }) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Start Push" }));
    expect(opened[0]).toBe(`shortcuts://x-callback-url/run-shortcut?name=SirisGym%20Start&x-success=${encodeURIComponent(`${window.location.origin}/gym/workout`)}`
      + `&x-cancel=${encodeURIComponent(`${window.location.origin}/gym/workout`)}&x-error=${encodeURIComponent(`${window.location.origin}/gym/workout`)}`);
    expect(window.localStorage.getItem("sirisos.gym.active")).not.toBeNull();
    open.mockRestore(); ua.mockRestore();
  });

  it("does nothing off iPhone or without a name", () => {
    const open = vi.spyOn(shortcuts, "open").mockImplementation(() => {});
    expect(shortcuts.run("SirisGym Start", "/gym/workout")).toBe(false);  // jsdom isn't an iPhone
    expect(shortcuts.run("", "/gym/workout")).toBe(false);
    expect(open).not.toHaveBeenCalled();
    open.mockRestore();
  });
});

describe("SirisGym 6.93", () => {
  it("swaps an exercise mid-workout for the same movement", async () => {
    signIn();
    saveActive({ id: "w5", title: "Push", started_at: new Date().toISOString(), entries: [{ exercise: "bench-press", sets: [{ weight: 80, reps: null, done: false, type: "normal" }] }] });
    mockFetch({
      "/api/v1/gym/swap": () => jsonResponse({ options: [{ id: "db-bench-press", name: "Dumbbell Bench Press", equipment: "dumbbell", same_pattern: true, last: [{ weight: 32, reps: 8, done: true, type: "normal" }], weight: 34 }] }),
      "/api/v1/gym": () => jsonResponse({ ...GYM, exercises: [...GYM.exercises, { id: "db-bench-press", name: "Dumbbell Bench Press", primary: "chest", secondary: [], equipment: "dumbbell", kind: "weight", custom: false }] }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Swap Bench Press" }));
    await user.click(await screen.findByRole("button", { name: /Dumbbell Bench Press/ }));
    const kept = JSON.parse(window.localStorage.getItem("sirisos.gym.active")!);
    expect(kept.entries[0]).toMatchObject({ exercise: "db-bench-press", sets: [{ weight: 34, reps: null, done: false }] });
  });

  it("shows protein against the target and books gym time", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/gym/protein": () => jsonResponse({ target_g: 160, eaten_g: 120, per_kg: 2, bodyweight: 80, training_day: true, left_g: 40 }),
      "/api/v1/gym/schedule": (_u, init) => jsonResponse(JSON.parse(String(init?.body)).dry_run
        ? { slot: { start: "2026-11-04T17:00:00+11:00", end: "2026-11-04T18:00:00+11:00" }, title: "Gym: Push" }
        : { slot: { start: "2026-11-04T17:00:00+11:00", end: "2026-11-04T18:00:00+11:00" }, title: "Gym: Push", added: true }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><GymScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Protein and gym time" });
    expect(await within(card).findByText("120 / 160 g")).toBeInTheDocument();
    expect(card).toHaveTextContent("40 g to go");
    await user.click(within(card).getByRole("button", { name: "Find gym time today" }));
    await user.click(await within(card).findByRole("button", { name: "Add to calendar" }));
    expect(await within(card).findByText(/Added: Gym: Push/)).toBeInTheDocument();
    expect(calls.filter((c) => c.url === "/api/v1/gym/schedule").map((c) => JSON.parse(String(c.init.body)).dry_run)).toEqual([true, false]);
  });
});

describe("SirisGym 6.94: weekdays", () => {
  it("shows the week, says when today's a rest day, and sets a day's weekdays", async () => {
    signIn();
    const week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((w, i) => ({ weekday: w, day: i === 0 || i === 3 ? 0 : null, name: i === 0 || i === 3 ? "Push" : null }));
    const g = { ...GYM, routines: [{ ...GYM.routines[0], days: [{ ...GYM.routines[0].days[0], weekdays: [0, 3] }] }],
      active: { routine: "r1", next_day: 0, schedule: { today: null, rest: true, next: { day: 0, date: "2026-11-09", weekday: "Monday" }, week } } };
    const calls = mockFetch({ "/api/v1/gym/routines/r1": (_u, init) => jsonResponse(JSON.parse(String(init?.body))), "/api/v1/gym/templates": () => jsonResponse({ templates: [] }), "/api/v1/gym": () => jsonResponse(g) });
    const user = userEvent.setup();
    const { unmount } = render(<MemoryRouter><GymScreen /></MemoryRouter>);
    expect(await screen.findByText(/Rest day: next is Push on Monday/)).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "This week's days" })).getAllByText("Push")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Do Push today" })).toBeInTheDocument();
    unmount();
    render(<MemoryRouter initialEntries={["/gym?view=routines"]}><GymScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: /Push, pull, legs/ }));
    const days = screen.getByRole("group", { name: "Days for Push" });
    expect(within(days).getByRole("button", { name: "Mon" })).toHaveAttribute("aria-pressed", "true");
    await user.click(within(days).getByRole("button", { name: "Sat" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    const sent = JSON.parse(String(calls.find((c) => c.url === "/api/v1/gym/routines/r1")!.init.body));
    expect(sent.days[0].weekdays).toEqual([0, 3, 5]);
  });
});

describe("SirisGym 6.95: tidy", () => {
  it("shows exercises with nothing logged, then takes them out", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/gym/cleanup": (u) => jsonResponse(u.includes("dry_run=true") ? { entries_removed: 12, exercises_removed: 2, names: ["Push Day", "Leg Day"], sessions_kept: 300 }
        : { entries_removed: 12, exercises_removed: 2, names: ["Push Day", "Leg Day"], sessions_kept: 300 }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/gym?view=settings"]}><GymScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Tidy up" });
    await user.click(within(card).getByRole("button", { name: "Look for them" }));
    expect(await within(card).findByText(/Push Day, Leg Day and 12 empty entries/)).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Take them out" }));
    expect(await within(card).findByText("Took out 2 exercises and 12 empty entries; all 300 workouts kept.")).toBeInTheDocument();
    expect(calls.filter((c) => c.url.startsWith("/api/v1/gym/cleanup")).map((c) => c.url)).toEqual(["/api/v1/gym/cleanup?dry_run=true", "/api/v1/gym/cleanup?dry_run=false"]);
  });
});

describe("Import from JEFIT (6.6)", () => {
  it("previews an export, lets you change a match, then imports with your choices", async () => {
    signIn();
    const preview = { sets: 1200, workouts: 310, from: "2021-03-05", to: "2026-10-30", replacing: 0, exercises: [
      { name: "Barbell Bench Press", sets: 800, match: "bench-press", match_name: "Bench Press", how: "close", new_muscle: "chest" },
      { name: "Zercher Carry", sets: 400, match: null, match_name: null, how: "none", new_muscle: "full body" }] };
    const calls = mockFetch({
      "/api/v1/gym/import": (_url, init) => jsonResponse((init?.body as FormData).get("dry_run") === "true"
        ? { preview } : { imported: { workouts: 310, sets: 1200, new_exercises: 1 } }),
      "/api/v1/gym/sessions": () => jsonResponse({ sessions: [] }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/gym?view=history"]}><GymScreen /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "SirisGym" })).toBeInTheDocument();
    await user.upload(await screen.findByLabelText("Export file"), new File(["mydate,ename,logs"], "jefit.csv", { type: "text/csv" }));
    expect(await screen.findByText("310 workouts, 1,200 sets")).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Exercises to match" });
    expect(within(list).getByRole("combobox", { name: "Zercher Carry is" })).toHaveValue("new");
    await user.selectOptions(within(list).getByRole("combobox", { name: "Barbell Bench Press is" }), "bench-press");
    await user.click(screen.getByRole("button", { name: "Import 310 workouts" }));
    expect(await screen.findByText(/Imported 310 workouts and 1,200 sets, with 1 new exercises/)).toBeInTheDocument();
    const sent = calls.filter((c) => c.url === "/api/v1/gym/import").pop()!.init.body as FormData;
    expect(JSON.parse(String(sent.get("choices")))).toEqual({ "Barbell Bench Press": "bench-press", "Zercher Carry": "new" });
  });
});

describe("<GymWorkoutScreen />", () => {
  it("logs a set from last time, starts the rest timer, and finishes with the records", async () => {
    signIn();
    saveActive({ id: "w1", title: "Push, pull, legs: Push", started_at: new Date().toISOString(),
      entries: [{ exercise: "bench-press", sets: [{ weight: 82.5, reps: null, done: false, type: "normal" }] }] });
    window.sessionStorage.setItem("sirisos.gym.plan.w1", JSON.stringify({ routine: "r1", day: 0, title: "Push", exercises: [
      { exercise: "bench-press", sets: 1, reps: "5-8", rest_s: 120, name: "Bench Press", kind: "weight", last: [{ weight: 80, reps: 8, done: true, type: "normal" }],
        suggest: { weight: 82.5, reps: 5, why: "Last time every set at 80 reached 8: add 2.5." } }] }));
    const calls = mockFetch({
      "/api/v1/gym/sessions": () => jsonResponse({ summary: { id: "w1", title: "Push", date: "2026-11-04", started_at: "", minutes: 41, sets: 1, exercises: 1, volume: 660, names: [] },
        records: [{ exercise: "bench-press", name: "Bench Press", kind: "heaviest", text: "Bench Press: heaviest ever, 82.5" }] }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    expect(await screen.findByText(/add 2.5/)).toBeInTheDocument();
    expect(screen.getByText("80×8")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Set 1 done" }));
    expect(screen.getByRole("timer", { name: "Rest" })).toHaveTextContent("120 s");
    expect(screen.getByRole("textbox", { name: "Set 1 reps" })).toHaveValue("8");  // filled from last time
    await user.click(screen.getByRole("button", { name: "Finish" }));
    expect(await screen.findByText("Bench Press: heaviest ever, 82.5")).toBeInTheDocument();
    const sent = JSON.parse(String(calls.find((c) => c.url === "/api/v1/gym/sessions")!.init.body));
    expect(sent.entries[0].sets).toEqual([{ weight: 82.5, reps: 8, done: true, type: "normal" }]);
    expect(window.localStorage.getItem("sirisos.gym.active")).toBeNull();
  });
});
