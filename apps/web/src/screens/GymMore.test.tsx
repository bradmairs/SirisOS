import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { saveActive, type Session } from "../api/gym";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { BackupsCard, FitnessLine, NigglesCard } from "./GymCards";
import { GymWorkoutScreen } from "./GymWorkout";

afterEach(() => { saveActive(null); clearResources(); window.sessionStorage.clear(); vi.restoreAllMocks(); });

const GYM = {
  settings: { unit: "kg", bar: 20, plates: [20], increment: 2.5, rest_s: 90, current_gym: "home", warmups: true, warmup_steps: [], gyms: [{ id: "home", name: "Home", bar: 20, plates: [20], dumbbells: [], stack_step: null }] },
  exercises: [{ id: "bench-press", name: "Bench Press", primary: "chest", secondary: [], equipment: "barbell", kind: "weight", custom: false },
    { id: "back-squat", name: "Back Squat", primary: "quads", secondary: [], equipment: "barbell", kind: "weight", custom: false },
    { id: "leg-press", name: "Leg Press", primary: "quads", secondary: [], equipment: "machine", kind: "weight", custom: false }],
  routines: [], active: null, recent: [], week: { week_of: "2026-11-02", sessions: 0, sets_by_muscle: {}, volume: 0 }, streak_weeks: 0, total_sessions: 3,
};

describe("Niggles (7.1)", () => {
  it("adds a sore spot and marks it healed", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/gym/niggles/n1/healed": () => jsonResponse({}), "/api/v1/gym/niggles": () => jsonResponse({ id: "n1" }) });
    const changed = vi.fn();
    const { rerender } = render(<NigglesCard niggles={[]} onChange={changed} />);
    await userEvent.click(screen.getByRole("button", { name: "Something's sore" }));
    await userEvent.click(screen.getByRole("radio", { name: "knee" }));
    await userEvent.type(screen.getByLabelText("Note"), "after running");
    await userEvent.click(screen.getByRole("button", { name: "Spare my knee" }));
    await vi.waitFor(() => expect(changed).toHaveBeenCalled());
    const add = calls.find((c) => c.url.endsWith("/api/v1/gym/niggles"));
    expect(JSON.parse(String(add?.init?.body))).toEqual({ area: "knee", note: "after running" });
    rerender(<NigglesCard niggles={[{ id: "n1", area: "knee", note: "after running", started: "2026-11-05" }]} onChange={changed} />);
    expect(screen.getByText("Sore knee")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Healed" }));
    await vi.waitFor(() => expect(calls.some((c) => c.url.includes("/niggles/n1/healed"))).toBe(true));
  });
});

describe("The workout (7.1)", () => {
  it("says why an exercise was swapped and why the rest changed, and can film a set", async () => {
    signIn();
    const s: Session = { id: "w1", title: "Legs", started_at: new Date().toISOString(), entries: [{ exercise: "leg-press", sets: [{ weight: 100, reps: 10, done: false, type: "normal" }] }] };
    saveActive(s);
    window.sessionStorage.setItem("sirisos.gym.plan.w1", JSON.stringify({ routine: "r", day: 0, title: "Legs", exercises: [{
      exercise: "leg-press", sets: 1, reps: "8-10", rest_s: 150, name: "Leg Press", kind: "weight", last: [], suggest: { weight: 100, reps: 10, why: "Same as last time." },
      niggle: { area: "knee", swap: "leg-press", name: "Leg Press", why: "Swapped to spare your knee.", from: "back-squat" },
      rest_learned: { seconds: 150, planned: 90, why: "Your heart rate took about 150 s to settle after a set." } }] }));
    const calls = mockFetch({ "/api/v1/gym/videos": () => jsonResponse({ id: "v1" }), "/api/v1/gym": () => jsonResponse(GYM) });
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    expect(await screen.findByText("Swapped to spare your knee. (instead of Back Squat)")).toBeInTheDocument();
    expect(screen.getByText(/Rest 150 s, not 90: Your heart rate took about 150 s/)).toBeInTheDocument();
    await userEvent.upload(screen.getByLabelText("Film a set of Leg Press"), new File(["x"], "set.mp4", { type: "video/mp4" }));
    await vi.waitFor(() => expect(screen.getByText("Filmed")).toBeInTheDocument());
    const up = calls.find((c) => c.url.endsWith("/api/v1/gym/videos"));
    const body = up?.init?.body as FormData;
    expect(body.get("exercise")).toBe("leg-press");
    expect(body.get("set")).toBe("1");
    expect(body.get("weight")).toBe("100");
    expect(body.get("session")).toBe("w1");
  });
});

describe("Fitness and backups (7.1)", () => {
  it("shows heart rate at the same weight", () => {
    render(<FitnessLine f={{ weight: 80, first: "2026-10-01", latest: "2026-11-02", times: 3, first_peak: 150, latest_peak: 139, delta_bpm: -11, verdict: "fitter",
      text: "At 80 kg your heart rate peaks 11 bpm lower than on 2026-10-01 (150 → 139 bpm): fitter at the same weight.", series: [] }} />);
    expect(screen.getByText(/11 bpm lower/)).toHaveClass("tone-good");
  });

  it("lists backups and restores one after asking", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/gym/backups/restore": () => jsonResponse({ restored: "gym.before-cleanup.20261105-010203.json", sessions: 412, saved_current_as: "gym.before-restore.x.json" }),
      "/api/v1/gym/backups": () => jsonResponse({ backups: [{ name: "gym.before-cleanup.20261105-010203.json", tag: "before-cleanup", saved_at: "2026-11-05T01:02:03+00:00", bytes: 20480, sessions: 412 }] }),
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<BackupsCard onChange={() => {}} />);
    expect(await screen.findByText("Before the tidy of empty exercises")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Restore" }));
    expect(await screen.findByText(/Restored: 412 workouts/)).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/restore"))?.init?.body))).toEqual({ name: "gym.before-cleanup.20261105-010203.json" });
    expect(screen.getByRole("button", { name: /Every set \(CSV\)/ })).toBeInTheDocument();
  });
});
