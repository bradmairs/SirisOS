import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { saveActive, saveRest, loadActive, type Gym, type Session } from "../api/gym";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { applySaid, GymWorkoutScreen } from "./GymWorkout";
import { GymScreen } from "./Gym";

const EX = (id: string, name: string) => ({ id, name, primary: "chest", secondary: [], equipment: "barbell", kind: "weight" as const, custom: false });
const GYM = {
  settings: { unit: "kg", bar: 20, plates: [20, 10, 5, 2.5], increment: 2.5, rest_s: 90, rest_between_s: 120, current_gym: "home", warmups: false, warmup_steps: [],
    gyms: [{ id: "home", name: "Home", bar: 20, plates: [20, 10, 5, 2.5], dumbbells: [], stack_step: null }], keep_awake: true, voice_key: false },
  exercises: [EX("bench-press", "Bench Press"), EX("barbell-row", "Barbell Row")],
  routines: [{ id: "r1", name: "PPL", days: [{ name: "Push", exercises: [{ exercise: "bench-press", sets: 3, reps: "5-8", rest_s: 90 }] }], active: true }],
  active: { routine: "r1", next_day: 0 }, recent: [], week: { week_of: "2026-11-09", sessions: 0, sets_by_muscle: {}, volume: 0 }, streak_weeks: 0, total_sessions: 0,
} as unknown as Gym;
const set = (weight: number | null, done = false) => ({ weight, reps: 5, done, type: "normal" as const });
const workout = (entries: Session["entries"]): Session => ({ id: "w88", title: "Push", started_at: new Date().toISOString(), entries });
const names = new Map(GYM.exercises.map((e) => [e.id, e] as const));

afterEach(() => { saveActive(null); saveRest(null); clearResources(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("SirisGym 8.8: sets said aloud", () => {
  it("goes into the exercise it names, else the next set not ticked", () => {
    const s = workout([{ exercise: "bench-press", sets: [set(80, true), set(80)] }, { exercise: "barbell-row", sets: [set(60)] }]);
    const a = applySaid(s, { weight: 82.5, reps: 6 }, names);
    expect("session" in a && a.session.entries[0].sets[1]).toMatchObject({ weight: 82.5, reps: 6, done: true });
    const b = applySaid(s, { weight: 70, reps: 8, name: "row" }, names);
    expect("session" in b && b.session.entries[1].sets[0]).toMatchObject({ weight: 70, reps: 8, done: true });
    expect(applySaid(s, { weight: 70 }, names)).toEqual({ error: "Didn't catch the reps." });
  });

  it("takes sets said to Siri from the queue into the workout, and says so", async () => {
    signIn();
    saveActive(workout([{ exercise: "bench-press", sets: [set(80), set(80)] }]));
    const calls = mockFetch({
      "/api/v1/gym/voice-log/ack": () => jsonResponse({ taken: 1 }),
      "/api/v1/gym/voice-log": () => jsonResponse({ items: [{ id: "v1", text: "100 by 5", parsed: { weight: 100, reps: 5 }, at: "" }] }),
      "/api/v1/gym/rest": () => jsonResponse({ ok: true }),
      "/api/v1/gym": () => jsonResponse({ ...GYM, settings: { ...GYM.settings, voice_key: true } }),
    });
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    expect(await screen.findByText(/From Siri: Logged Bench Press: 100 × 5/)).toBeInTheDocument();
    expect(loadActive()?.entries[0].sets[0]).toMatchObject({ weight: 100, reps: 5, done: true });
    const ack = calls.find((c) => c.url.includes("/voice-log/ack"));
    expect(JSON.parse(String(ack?.init.body))).toEqual({ ids: ["v1"] });
  });
});

describe("SirisGym 8.8: the workout screen", () => {
  it("keeps the screen on", async () => {
    signIn();
    const request = vi.fn(async () => ({ release: async () => {} }));
    Object.defineProperty(navigator, "wakeLock", { value: { request }, configurable: true });
    saveActive(workout([{ exercise: "bench-press", sets: [set(80)] }]));
    mockFetch({ "/api/v1/gym": () => jsonResponse(GYM) });
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await screen.findByRole("region", { name: "Bench Press" });
    await waitFor(() => expect(request).toHaveBeenCalledWith("screen"));
    delete (navigator as unknown as Record<string, unknown>).wakeLock;
  });

  it("goes through AMRAP and rest-pause when you tap a set's number", async () => {
    signIn();
    saveActive(workout([{ exercise: "bench-press", sets: [set(80)] }]));
    mockFetch({ "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const bench = await screen.findByRole("region", { name: "Bench Press" });
    for (let i = 0; i < 3; i++) await user.click(within(bench).getByRole("button", { name: /change type/ }));
    expect(within(bench).getByRole("button", { name: /change type/ })).toHaveTextContent("1A");
    await user.click(within(bench).getByRole("button", { name: /change type/ }));
    expect(within(bench).getByRole("button", { name: /change type/ })).toHaveTextContent("1R");
    expect(loadActive()?.entries[0].sets[0].type).toBe("restpause");
  });
});

describe("SirisGym 8.8: Today", () => {
  it("asks for a lighter plan when you're tired", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/gym/plan": () => jsonResponse({ routine: "r1", day: 0, title: "PPL: Push", deload: false, exercises: [], mode: "tired", mode_note: "You're tired today." }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><GymScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("radio", { name: "I'm tired" }));
    await user.click(screen.getByRole("button", { name: "Start Push" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/plan?") && c.url.includes("mode=tired"))).toBe(true));
  });

  it("shows the Siri key once, and never sends it back", async () => {
    signIn();
    mockFetch({
      "/api/v1/gym/voice-key": () => jsonResponse({ key: "sg_test", url: "/api/v1/gym-voice/log" }),
      "/api/v1/gym": () => jsonResponse(GYM),
    });
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/gym?view=settings"]}><GymScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Log sets with Siri" });
    await user.click(within(card).getByRole("button", { name: "Make a key" }));
    expect(await within(card).findByLabelText("Siri key")).toHaveTextContent("sg_test");
    expect(within(card).getByText(/won't be shown again/)).toBeInTheDocument();
  });
});
