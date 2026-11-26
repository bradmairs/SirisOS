import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { loadActive, saveActive, saveRest, shortcuts, type Gym, type Session } from "../api/gym";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { GymWorkoutScreen } from "./GymWorkout";

const EX = (id: string, name: string) => ({ id, name, primary: "chest", secondary: [], equipment: "dumbbell", kind: "weight" as const, custom: false });
const GYM = {
  settings: { unit: "kg", bar: 20, plates: [20, 10, 5, 2.5], increment: 2.5, rest_s: 90, rest_between_s: 120, current_gym: "home", warmups: true, warmup_steps: [],
    gyms: [{ id: "home", name: "Home", bar: 20, plates: [20, 10, 5, 2.5], dumbbells: [], stack_step: null }] },
  exercises: [EX("curl", "Curl")], routines: [], active: null, recent: [], week: { week_of: "2026-11-23", sessions: 0, sets_by_muscle: {}, volume: 0 }, streak_weeks: 0, total_sessions: 0,
} as unknown as Gym;
const hinted = (w: number, r: number, type: "normal" | "warmup" = "normal") => ({ weight: null, reps: null, hint: { weight: w, reps: r }, done: false, type });
const workout = (sets: Session["entries"][number]["sets"]): Session => ({ id: "w119", title: "Arms", started_at: new Date().toISOString(), entries: [{ exercise: "curl", sets }] });

afterEach(() => { saveActive(null); saveRest(null); clearResources(); localStorage.removeItem("sirisos.gym.return"); vi.restoreAllMocks(); });

describe("SirisGym 11.9: last session's numbers, faintly", () => {
  it("shows them in empty boxes, takes what you type with nothing to delete, and a tick without typing uses them", async () => {
    signIn();
    saveActive(workout([hinted(12, 10), hinted(12, 9)]));
    mockFetch({ "/api/v1/gym/rest": () => jsonResponse({ ok: true }), "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const curl = await screen.findByRole("region", { name: "Curl" });
    const w1 = within(curl).getByRole("textbox", { name: "Set 1 weight" });
    expect(w1).toHaveValue("");
    expect(w1).toHaveAttribute("placeholder", "12");
    expect(within(curl).getByRole("textbox", { name: "Set 2 reps" })).toHaveAttribute("placeholder", "9");
    await user.click(w1);
    await user.keyboard("14");   // straight in: nothing to delete first
    await user.tab();
    expect(w1).toHaveValue("14");
    await user.click(within(curl).getByRole("button", { name: "Set 1 done" }));
    expect(loadActive()!.entries[0].sets[0]).toMatchObject({ weight: 14, reps: 10, done: true });   // reps from the faint 10
    await user.click(within(curl).getByRole("button", { name: "Set 2 done" }));
    expect(loadActive()!.entries[0].sets[1]).toMatchObject({ weight: 14, reps: 9, done: true });    // the 14 carried down
  });

  it("never saves the hints", async () => {
    signIn();
    saveActive(workout([{ ...hinted(12, 10), weight: 12, reps: 10, done: true }, hinted(12, 9)]));
    const calls = mockFetch({ "/api/v1/gym/sessions": () => jsonResponse({ summary: { title: "Arms" } }), "/api/v1/gym": () => jsonResponse(GYM) });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    await user.click((await screen.findAllByRole("button", { name: /Finish/ }))[0]);
    await waitFor(() => expect(calls.some((c) => c.url.startsWith("/api/v1/gym/sessions"))).toBe(true));
    const body = String(calls.find((c) => c.url.startsWith("/api/v1/gym/sessions"))!.init.body);
    expect(body).not.toContain("hint");
  });
});

describe("SirisGym 11.9: removing sets and warm-ups", () => {
  it("removes a set, and the warm-ups not done, from the exercise's menu", async () => {
    signIn();
    saveActive(workout([hinted(6, 10, "warmup"), hinted(8, 6, "warmup"), hinted(12, 10), hinted(12, 10), hinted(12, 10)]));
    mockFetch({ "/api/v1/gym": () => jsonResponse(GYM) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const curl = await screen.findByRole("region", { name: "Curl" });
    await user.click(within(curl).getByRole("button", { name: "More for Curl" }));
    await user.click(within(curl).getByRole("button", { name: /Remove warm-ups/ }));
    expect(loadActive()!.entries[0].sets.map((x) => x.type)).toEqual(["normal", "normal", "normal"]);
    await user.click(within(curl).getByRole("button", { name: "More for Curl" }));
    await user.click(within(curl).getByRole("button", { name: /Remove sets/ }));
    await user.click(within(curl).getByRole("button", { name: "Remove set 3" }));
    expect(loadActive()!.entries[0].sets).toHaveLength(2);
    await user.click(within(curl).getByRole("button", { name: /Done/ }));
    expect(within(curl).getByRole("button", { name: "Set 1 done" })).toBeInTheDocument();
  });
});

describe("SirisGym 11.9: coming back from Shortcuts", () => {
  it("uses the link set on this iPhone in the Home Screen app, and none without one", () => {
    vi.spyOn(shortcuts, "standalone").mockReturnValue(true);
    expect(shortcuts.back("/gym/workout")).toBeNull();
    shortcuts.setReturnLink("webapp://{url}");
    expect(shortcuts.back("/gym/workout")).toBe(`webapp://${window.location.origin}/gym/workout`);
    expect(shortcuts.url("Start", shortcuts.back("/gym/workout"))).toContain("x-success=webapp");
    shortcuts.setReturnLink("");
    expect(shortcuts.back("/gym/workout")).toBeNull();
  });
});
