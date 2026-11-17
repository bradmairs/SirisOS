import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { setE1rm } from "../api/gym";
import { cardData } from "../components/WorkoutCard";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { GoodSessionsCard } from "./GymProgress";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

const APU = { id: "my-apu", name: "Assisted Pull-Up", primary: "back", secondary: [], equipment: "machine", kind: "weight" as const, custom: true, assisted: true };

describe("SirisGym 9.6", () => {
  it("works out an assisted set's 1RM from bodyweight less the help", () => {
    expect(setE1rm(APU, 20, 8, 80)).toBe(76);   // 60 kg lifted for 8
    expect(setE1rm(APU, 20, 8, null)).toBeNull();
    expect(setE1rm({ ...APU, assisted: false }, 20, 8, 80)).toBe(25.3);
  });

  it("shows what makes a good session", async () => {
    signIn();
    mockFetch({ "/api/v1/gym/good-sessions": () => jsonResponse({ scored: 30, health: true, note: null,
      findings: [{ key: "sleep", text: "You lift about 4% more after 7 hours' sleep or more than after less.", gap: 4, with: 98, without: 94, sessions: 30, counts: "16 sessions after a good night, 14 after a short one" }] }) });
    render(<MemoryRouter><GoodSessionsCard /></MemoryRouter>);
    expect(await screen.findByText(/4% more after 7 hours' sleep/)).toBeInTheDocument();
    expect(screen.getByText(/From 30 workouts/)).toBeInTheDocument();
  });

  it("says when there isn't enough to go on", async () => {
    signIn();
    mockFetch({ "/api/v1/gym/good-sessions": () => jsonResponse({ scored: 3, health: false, findings: [], note: "Not enough yet: it needs more." }) });
    render(<MemoryRouter><GoodSessionsCard /></MemoryRouter>);
    expect(await screen.findByText("Not enough yet: it needs more.")).toBeInTheDocument();
  });

  it("puts the workout on a card: best sets, new bests and the Watch", () => {
    const d = cardData({
      title: "Push", started_at: "2026-11-16T07:00:00+11:00",
      summary: { id: "s1", title: "Push", date: "2026-11-16", started_at: "2026-11-16T07:00:00+11:00", minutes: 62, sets: 16, exercises: 2, volume: 12450, names: [], held: false, feel: null },
      records: [{ exercise: "bench-press", name: "Bench Press", kind: "e1rm", text: "Bench Press: best estimated 1RM, 102" }],
      entries: [
        { name: "Bench Press", exercise: "bench-press", sets: [{ weight: 40, reps: 10, done: true, type: "warmup" }, { weight: 85, reps: 6, done: true, type: "normal" }, { weight: 90, reps: 4, done: true, type: "normal" }] },
        { name: "Plank", exercise: "plank", sets: [{ seconds: 60, done: true, type: "normal" }, { seconds: 75, done: true, type: "normal" }] },
        { name: "Assisted Dip", exercise: "my-ad", assisted: true, sets: [{ weight: 30, reps: 8, done: true, type: "normal" }, { weight: 25, reps: 6, done: true, type: "normal" }] },
        { name: "Single Arm Row", exercise: "my-sar", per_side: true, sets: [{ weight: 32, reps: 10, done: true, type: "normal" }] },
        { name: "Skipped", exercise: "fly", sets: [{ weight: 20, reps: 10, done: false, type: "normal" }] },
      ],
      watch: { name: "Strength", start: "", minutes: 60, avg_hr: 118.4, max_hr: 161, kj: 1520 },
    });
    expect(d.stats).toEqual([{ value: "62", label: "minutes" }, { value: "16", label: "sets" }, { value: "12.4 t", label: "lifted" }]);
    expect(d.lifts).toEqual([{ name: "Bench Press", best: "2 × 4 · top 90 kg" }, { name: "Plank", best: "2 × 75 s" },
      { name: "Assisted Dip", best: "2 × 6 · 25 kg help" }, { name: "Single Arm Row", best: "1 × 10 · top 32 kg a side" }]);
    expect(d.records).toEqual(["Bench Press: best estimated 1RM, 102"]);
    expect(d.heart).toBe("118 bpm average · 161 max · 1,520 kJ");
  });
});
