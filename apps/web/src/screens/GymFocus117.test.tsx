import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { saveActive, saveRest, type Gym, type Session } from "../api/gym";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { GymWorkoutScreen, firstUndone, nextUp } from "./GymWorkout";

const EX = (id: string, name: string) => ({ id, name, primary: "chest", secondary: [], equipment: "barbell", kind: "weight" as const, custom: false });
const GYM = {
  settings: { unit: "kg", bar: 20, plates: [20, 10, 5, 2.5], increment: 2.5, rest_s: 90, rest_between_s: 120, current_gym: "home", warmups: false, warmup_steps: [],
    gyms: [{ id: "home", name: "Home", bar: 20, plates: [20, 10, 5, 2.5], dumbbells: [], stack_step: null }] },
  exercises: [EX("bench-press", "Bench Press"), EX("barbell-row", "Barbell Row"), EX("curl", "Curl")],
  routines: [], active: null, recent: [], week: { week_of: "2026-11-23", sessions: 0, sets_by_muscle: {}, volume: 0 }, streak_weeks: 0, total_sessions: 0,
} as unknown as Gym;
const set = (weight: number | null, done = false) => ({ weight, reps: 5, done, type: "normal" as const });
const workout = (entries: Session["entries"]): Session => ({ id: "w117", title: "Push", started_at: new Date().toISOString(), entries });

afterEach(() => { saveActive(null); saveRest(null); clearResources(); localStorage.removeItem("sirisos.gym.view"); vi.restoreAllMocks(); });

describe("SirisGym 11.7: where One at a time goes next", () => {
  const e = (exercise: string, sets: ReturnType<typeof set>[], group: string | null = null) => ({ exercise, sets, group });
  it("stays until an exercise is done, then the next one not done, wrapping round", () => {
    const entries = [e("a", [set(1, true), set(1)]), e("b", [set(1, true)]), e("c", [set(1)])];
    expect(nextUp(entries, 0)).toBe(0);
    entries[0].sets[1].done = true;
    expect(nextUp(entries, 0)).toBe(2);   // b's already done
    expect(nextUp([e("a", [set(1)]), e("b", [set(1, true)])], 1)).toBe(0);   // back to one skipped earlier
    expect(firstUndone(entries)).toBe(2);
  });
  it("goes back and forth in a superset, then on once it's all done", () => {
    const entries = [e("a", [set(1, true), set(1)], "A"), e("b", [set(1, true), set(1)], "A"), e("c", [set(1)])];
    expect(nextUp(entries, 0)).toBe(1);
    expect(nextUp(entries, 1)).toBe(0);
    entries[0].sets[1].done = true;
    entries[1].sets[1].done = true;
    expect(nextUp(entries, 1)).toBe(2);
  });
});

describe("SirisGym 11.7: One at a time", () => {
  it("switches view, shows one exercise as a page, moves between them, and moves on by itself when one's done", async () => {
    signIn();
    saveActive(workout([{ exercise: "bench-press", sets: [set(80)] }, { exercise: "barbell-row", sets: [set(60)] }, { exercise: "curl", sets: [set(20)] }]));
    mockFetch({ "/api/v1/gym/rest": () => jsonResponse({ ok: true }), "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    expect(await screen.findByRole("region", { name: "Bench Press" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Barbell Row" })).toBeInTheDocument();   // the list: all of them

    await user.click(screen.getByRole("button", { name: /One at a time/ }));
    expect(localStorage.getItem("sirisos.gym.view")).toBe("focus");
    expect(screen.getByRole("region", { name: "Bench Press" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Barbell Row" })).not.toBeInTheDocument();
    expect(screen.getByText("Exercise 1 of 3 · 0 done")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next: Barbell Row" }));
    expect(screen.getByRole("region", { name: "Barbell Row" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "1. Bench Press" }));
    const bench = screen.getByRole("region", { name: "Bench Press" });

    await user.click(within(bench).getByRole("button", { name: "Set 1 done" }));
    // Done with the bench: the row comes up by itself.
    expect(await screen.findByRole("region", { name: "Barbell Row" }, { timeout: 2000 })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "1. Bench Press, done" })).toBeInTheDocument();
  });

  it("turns the page with a swipe, but not one on the sets", async () => {
    signIn();
    localStorage.setItem("sirisos.gym.view", "focus");
    saveActive(workout([{ exercise: "bench-press", sets: [set(80)] }, { exercise: "barbell-row", sets: [set(60)] }]));
    mockFetch({ "/api/v1/gym": () => jsonResponse(GYM) });
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const bench = await screen.findByRole("region", { name: "Bench Press" });
    const sets = within(bench).getByRole("table", { name: "Sets" });
    fireEvent.touchStart(sets, { touches: [{ clientX: 300, clientY: 400 }] });
    fireEvent.touchEnd(sets, { changedTouches: [{ clientX: 100, clientY: 405 }] });
    expect(screen.getByRole("region", { name: "Bench Press" })).toBeInTheDocument();
    const head = within(bench).getByRole("button", { name: "Bench Press" });
    fireEvent.touchStart(head, { touches: [{ clientX: 300, clientY: 200 }] });
    fireEvent.touchEnd(head, { changedTouches: [{ clientX: 100, clientY: 210 }] });
    await waitFor(() => expect(screen.getByRole("region", { name: "Barbell Row" })).toBeInTheDocument());
  });
});
