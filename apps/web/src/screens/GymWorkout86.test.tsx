import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { changeSet, loadRest, moveEntry, saveActive, saveRest, shortcuts, type Gym, type Session } from "../api/gym";
import { unreachable, waiting } from "../api/outbox";
import { ApiError } from "../api/client";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { GymWorkoutScreen } from "./GymWorkout";
import { GymScreen } from "./Gym";

const EX = (id: string, name: string) => ({ id, name, primary: "chest", secondary: [], equipment: "barbell", kind: "weight" as const, custom: false });
const GYM: Gym = {
  settings: { unit: "kg", bar: 20, plates: [20, 10, 5, 2.5], increment: 2.5, rest_s: 90, rest_between_s: 120, current_gym: "home", warmups: false, warmup_steps: [],
    gyms: [{ id: "home", name: "Home", bar: 20, plates: [20, 10, 5, 2.5], dumbbells: [], stack_step: null }] },
  exercises: [EX("bench-press", "Bench Press"), EX("barbell-row", "Barbell Row")],
  routines: [{ id: "r1", name: "PPL", days: [{ name: "Push", exercises: [{ exercise: "bench-press", sets: 3, reps: "5-8", rest_s: 90 }, { exercise: "barbell-row", sets: 3, reps: "8", rest_s: 90 }] }], active: true }],
  active: { routine: "r1", next_day: 0 }, recent: [], week: { week_of: "2026-11-09", sessions: 0, sets_by_muscle: {}, volume: 0 }, streak_weeks: 0, total_sessions: 0,
} as Gym;
const set = (weight: number | null, done = false) => ({ weight, reps: 5, done, type: "normal" as const });
const workout = (entries: Session["entries"]): Session => ({ id: "w86", title: "Push", started_at: new Date().toISOString(), entries });

afterEach(() => { saveActive(null); saveRest(null); clearResources(); window.localStorage.removeItem("sirisos.outbox"); vi.restoreAllMocks(); });

describe("SirisGym 8.6: weights", () => {
  it("doesn't take the sets below down a digit at a time while you retype a weight", async () => {
    signIn();
    saveActive(workout([{ exercise: "bench-press", sets: [set(100), set(100), set(100)] }]));
    mockFetch({ "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const bench = await screen.findByRole("region", { name: "Bench Press" });
    const box = within(bench).getByRole("textbox", { name: "Set 1 weight" });
    await user.click(box);
    await user.keyboard("{Backspace}{Backspace}{Backspace}105");
    expect(within(bench).getByRole("textbox", { name: "Set 2 weight" })).toHaveValue("100");  // not yet: you're still typing
    await user.tab();
    expect(within(bench).getByRole("textbox", { name: "Set 2 weight" })).toHaveValue("105");
    expect(within(bench).getByRole("textbox", { name: "Set 3 weight" })).toHaveValue("105");
  });

  it("carries from the weight before you started, and leaves one set on purpose alone", () => {
    const sets = [set(100), set(100), set(90)];
    expect(changeSet(sets, 0, { weight: 1 }, { carry: false }).map((x) => x.weight)).toEqual([1, 100, 90]);
    expect(changeSet([set(1), set(100), set(90)], 0, { weight: 105 }, { from: 100 }).map((x) => x.weight)).toEqual([105, 105, 90]);
  });
});

describe("SirisGym 8.6: rest", () => {
  it("rests longer between exercises, and the timer survives a reload", async () => {
    signIn();
    saveActive(workout([{ exercise: "bench-press", sets: [set(80), set(80)] }, { exercise: "barbell-row", sets: [set(60)] }]));
    mockFetch({ "/api/v1/gym/rest": () => jsonResponse({ ok: true }), "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    const first = render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const bench = await screen.findByRole("region", { name: "Bench Press" });
    await user.click(within(bench).getByRole("button", { name: "Set 1 done" }));
    expect(screen.getByRole("timer", { name: "Rest" })).toHaveTextContent("1:30");
    await user.click(within(bench).getByRole("button", { name: "Set 2 done" }));
    expect(screen.getByRole("timer", { name: "Rest" })).toHaveTextContent("2:00");  // the last of the bench: rest before the row
    expect(loadRest("w86")?.next).toMatch(/Barbell Row, set 1/);
    first.unmount();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);  // iOS reloaded the app
    expect(await screen.findByRole("timer", { name: "Rest" })).toHaveTextContent(/1:5\d|2:00/);
  });

  it("says the rest is over on screen while the app is open", async () => {
    signIn();
    saveActive(workout([{ exercise: "bench-press", sets: [set(80, true), set(80)] }]));
    saveRest({ until: Date.now() + 1000, total: 90, next: "Bench Press, set 2: 80 kg", session: "w86" });
    mockFetch({ "/api/v1/gym": () => jsonResponse(GYM) });
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    expect(await screen.findByRole("timer", { name: "Rest" })).toBeInTheDocument();
    expect(await screen.findByRole("alert", {}, { timeout: 3000 })).toHaveTextContent("Rest's over · Bench Press, set 2: 80 kg");
    expect(loadRest("w86")).toBeNull();
  });

  it("runs the rest Shortcut with the seconds, for a Clock timer on the lock screen", async () => {
    signIn();
    vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)");
    const opened: string[] = [];
    vi.spyOn(shortcuts, "open").mockImplementation((u: string) => { opened.push(u); });
    vi.spyOn(shortcuts, "standalone").mockReturnValue(true);
    saveActive(workout([{ exercise: "bench-press", sets: [set(80), set(80)] }]));
    mockFetch({ "/api/v1/gym/rest": () => jsonResponse({ ok: true }), "/api/v1/gym": () => jsonResponse({ ...GYM, settings: { ...GYM.settings, shortcut_rest: "SirisGym Rest" } }) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await user.click(within(await screen.findByRole("region", { name: "Bench Press" })).getByRole("button", { name: "Set 1 done" }));
    expect(opened).toEqual(["shortcuts://run-shortcut?name=SirisGym%20Rest&input=text&text=90"]);  // the Home Screen app: no link back to Safari
  });
});

describe("SirisGym 8.6: the workout", () => {
  it("moves exercises up and down, with Finish at the bottom too", async () => {
    signIn();
    saveActive(workout([{ exercise: "bench-press", sets: [set(80, true)] }, { exercise: "barbell-row", sets: [set(60)] }]));
    const calls = mockFetch({ "/api/v1/gym/sessions": () => jsonResponse({ summary: { id: "w86", title: "Push", date: "", started_at: "", minutes: 30, sets: 1, exercises: 1, volume: 400, names: [] }, records: [] }),
      "/api/v1/gym/rest": () => jsonResponse({}), "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "More for Barbell Row" }));  // 8.7: behind ⋯
    await user.click(screen.getByRole("button", { name: "Move Barbell Row up" }));
    expect(screen.getAllByRole("region").map((r) => r.getAttribute("aria-label"))).toEqual(["Barbell Row", "Bench Press"]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Finish the workout" }));
    expect(await screen.findByText("Back to the gym")).toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/gym/sessions")).toBe(true);
  });

  it("keeps a superset together when moving", () => {
    const items = [{ id: 1, group: "A" }, { id: 2, group: "A" }, { id: 3, group: null }];
    expect(moveEntry(items, 0, 1)).toEqual([{ id: 2, group: "A" }, { id: 1, group: "A" }, { id: 3, group: null }]);
    expect(moveEntry(items, 1, 2)).toEqual([{ id: 1, group: null }, { id: 3, group: null }, { id: 2, group: null }]);
  });

  it("keeps the workout on the phone when SirisOS is down (a 502), to send when it's back", async () => {
    signIn();
    expect(unreachable(new ApiError(502, "Bad gateway"))).toBe(true);
    expect(unreachable(new ApiError(422, "No"))).toBe(false);
    saveActive(workout([{ exercise: "bench-press", sets: [set(80, true)] }]));
    mockFetch({ "/api/v1/gym/sessions": () => jsonResponse({ detail: "Bad gateway" }, 502), "/api/v1/gym/rest": () => jsonResponse({}, 502), "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Finish" }));
    expect(await screen.findByText(/saved on this phone/)).toBeInTheDocument();
    expect(waiting()).toBe(1);
  });
});

describe("SirisGym 8.6: merges", () => {
  it("says a pair isn't the same, and unmerges one", async () => {
    signIn();
    let dup = [{ from: "my-a", from_name: "Pull Down", from_sets: 3, into: "lat-pulldown", into_name: "Lat Pulldown", into_sets: 30, sure: false }];
    let merges = [{ id: "m1", at: "2026-11-01T10:00:00", from_name: "Tricep Press", into: "my-b", into_name: "Triceps Press", sets_moved: 6, workouts: 2 }];
    const calls = mockFetch({
      "/api/v1/gym/duplicates/dismiss": () => { dup = []; return jsonResponse({ duplicates: [] }); },
      "/api/v1/gym/duplicates": () => jsonResponse({ duplicates: dup }),
      "/api/v1/gym/merges/m1/undo": () => { merges = []; return jsonResponse({ exercise: "my-c", name: "Tricep Press", sets_back: 6, workouts: 2 }); },
      "/api/v1/gym/merges": () => jsonResponse({ merges }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/gym?view=exercises"]}><GymScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Pull Down and Lat Pulldown aren't the same" }));
    expect(await screen.findByText("Pull Down and Lat Pulldown stay apart.")).toBeInTheDocument();
    await user.click(screen.getByText("Merged (1)"));
    await user.click(screen.getByRole("button", { name: "Unmerge Tricep Press" }));
    expect(await screen.findByText("Tricep Press is back, with 6 sets from 2 workouts.")).toBeInTheDocument();
    expect(calls.map((c) => c.url)).toContain("/api/v1/gym/merges/m1/undo");
  });
});

describe("SirisGym 8.6: Shortcuts from the Home Screen app", () => {
  it("asks for no link back, which would open Safari", () => {
    expect(shortcuts.url("SirisGym Start", null)).toBe("shortcuts://run-shortcut?name=SirisGym%20Start");
    expect(shortcuts.url("SirisGym Finish", null, "finished")).toBe("shortcuts://run-shortcut?name=SirisGym%20Finish&input=text&text=finished");
  });
});


describe("SirisGym 9.0: last time, set by set", () => {
  it("shows what you lifted last time in a workout with no plan, before you fill it in", async () => {
    signIn();
    saveActive(workout([{ exercise: "barbell-row", sets: [set(null), { ...set(null), reps: null }] }]));
    const calls = mockFetch({
      "/api/v1/gym/last": () => jsonResponse({ last: { "barbell-row": { date: "2026-11-04", sets: [{ weight: 60, reps: 10, done: true, type: "normal" }, { weight: 62.5, reps: 8, done: true, type: "normal" }] } } }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const row = await screen.findByRole("region", { name: "Barbell Row" });
    expect(await within(row).findByLabelText("Last time")).toHaveTextContent(/Last time \(.*4.*\): 60×10, 62.5×8/);
    expect(within(row).getByText("62.5×8")).toBeInTheDocument();  // set 2's Last column
    expect(within(row).getByRole("textbox", { name: "Set 2 weight" })).toHaveAttribute("placeholder", "62.5");
    expect(calls.find((c) => c.url.startsWith("/api/v1/gym/last"))!.url).toBe("/api/v1/gym/last?exercises=barbell-row");
  });
});
