import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { saveActive, type Gym, type Session } from "../api/gym";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { DoneNote, NoteActionsCard } from "./GymNotes";
import { GymWorkoutScreen } from "./GymWorkout";

afterEach(() => { clearResources(); saveActive(null); vi.restoreAllMocks(); });

const action = (id: string, kind: "spare" | "up", text: string) => ({ id, session: "s1", date: "2026-11-26", kind, quote: "Bench felt light", text, status: "open" });

describe("SirisGym 11.14", () => {
  it("reads a note written after finishing and offers what it asks", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/gym/sessions/s1/note": () => jsonResponse({ note: "Bench felt light", note_actions: [action("n1", "up", "Go up 2.5 kg on Bench Press next time")] }),
      "/api/v1/gym/note-actions/n1": () => jsonResponse({ done: "Bench Press: +2.5 kg next time.", actions: [] }),
    });
    const user = userEvent.setup();
    render(<DoneNote session="s1" initial={[]} />);
    await user.type(screen.getByRole("textbox"), "Bench felt light");
    await user.click(screen.getByRole("button", { name: "Save the note" }));
    const list = await screen.findByRole("list", { name: "From your note" });
    expect(within(list).getByText("Go up 2.5 kg on Bench Press next time")).toBeInTheDocument();
    await user.click(within(list).getByRole("button", { name: "Do it" }));
    expect(await screen.findByText("Bench Press: +2.5 kg next time.")).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/note-actions/n1"))?.init.body))).toEqual({ act: "apply" });
  });

  it("shows waiting suggestions on Today, and No leaves one", async () => {
    signIn();
    const changed = vi.fn();
    const calls = mockFetch({ "/api/v1/gym/note-actions/n2": () => jsonResponse({ done: "", actions: [] }) });
    const user = userEvent.setup();
    render(<NoteActionsCard actions={[action("n2", "spare", "Spare your shoulder next time")]} onChange={changed} />);
    const card = screen.getByRole("region", { name: "From your notes" });
    await user.click(within(card).getByRole("button", { name: "No" }));
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ act: "dismiss" });
  });

  it("keeps RPE and set types behind More unless Settings shows them", async () => {
    signIn();
    const gym = { settings: { unit: "kg", bar: 20, plates: [20, 10], increment: 2.5, rest_s: 90, current_gym: "home", warmups: false, warmup_steps: [],
      gyms: [{ id: "home", name: "Home", bar: 20, plates: [20, 10], dumbbells: [], stack_step: null }], show_extras: false },
      exercises: [{ id: "bench-press", name: "Bench Press", primary: "chest", secondary: [], equipment: "barbell", kind: "weight", custom: false }],
      routines: [], active: null, recent: [], week: { week_of: "2026-11-23", sessions: 0, sets_by_muscle: {}, volume: 0 }, streak_weeks: 0, total_sessions: 0 } as unknown as Gym;
    const s: Session = { id: "w1", title: "Push", started_at: new Date().toISOString(), entries: [{ exercise: "bench-press", sets: [{ weight: 80, reps: 5, done: true, type: "normal" }] }] };
    saveActive(s);
    mockFetch({ "/api/v1/gym": () => jsonResponse(gym) });
    const user = userEvent.setup();
    render(<MemoryRouter><GymWorkoutScreen /></MemoryRouter>);
    const bench = await screen.findByRole("region", { name: "Bench Press" });
    expect(within(bench).queryByRole("button", { name: /effort \(RPE\)/ })).toBeNull();
    expect(within(bench).queryByRole("button", { name: /change type/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "More" }));
    expect(within(bench).getByRole("button", { name: /effort \(RPE\)/ })).toBeInTheDocument();
    expect(within(bench).getByRole("button", { name: /change type/ })).toBeInTheDocument();
  });
});
