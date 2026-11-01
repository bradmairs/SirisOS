import { afterEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { e1rm, plates, saveActive, type Gym } from "../api/gym";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { GymWorkoutScreen } from "./GymWorkout";
import { GymScreen } from "./Gym";

const GYM: Gym = {
  settings: { unit: "kg", bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25], increment: 2.5, rest_s: 90 },
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
