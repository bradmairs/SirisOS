import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { UndoBanner, undoable, flushUndoables } from "../components/Undo";
import { jsonResponse, mockFetch } from "../test/helpers";
import { WallScreen } from "./Wall";

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); window.history.replaceState(null, "", "/"); });

describe("SirisOS 11.15", () => {
  it("does a delete on screen at once, sends it after a few seconds, and Undo puts it back", async () => {
    vi.useFakeTimers();
    const run = vi.fn(), hide = vi.fn(), restore = vi.fn();
    render(<UndoBanner />);
    act(() => undoable({ text: "Removed Car rego", run, hide, restore }));
    expect(hide).toHaveBeenCalled();
    expect(screen.getByText("Removed Car rego")).toBeInTheDocument();
    act(() => { screen.getByRole("button", { name: /Undo/ }).click(); });
    expect(restore).toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(7000); });
    expect(run).not.toHaveBeenCalled();  // undone: never sent

    const run2 = vi.fn();
    act(() => undoable({ text: "Deleted the video", run: run2 }));
    await act(async () => { vi.advanceTimersByTime(6500); });
    expect(run2).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Deleted the video")).toBeNull();
  });

  it("sends what's waiting straight away when the app goes away", async () => {
    const run = vi.fn();
    render(<UndoBanner />);
    act(() => undoable({ text: "Removed a set", run }));
    await act(async () => { flushUndoables(); });
    expect(run).toHaveBeenCalledTimes(1);
  });

  it("shows the wall from its own key, without signing in", async () => {
    window.history.replaceState(null, "", "/wall?key=wall_test");
    const calls = mockFetch({ "/api/v1/wall": () => jsonResponse({ now: "2026-11-27T18:00", phase: "evening", dim: false,
      weather: { summary: "Showers", max_c: 19, min_c: 11, rain_chance: 60 }, today: [{ title: "Dentist", start: "2026-11-27T15:00:00", all_day: false }],
      tomorrow: [], bins: { next: { date: "2026-11-28", text: "Rubbish and recycling" }, when: "tonight" }, dinner: { title: "Tacos" }, parcels: [] }) });
    render(<WallScreen />);
    expect(await screen.findByText("Tacos")).toBeInTheDocument();
    expect(screen.getByText("Dentist")).toBeInTheDocument();
    expect(screen.getByText(/Rubbish and recycling/)).toBeInTheDocument();
    expect(calls[0].url).toBe("/api/v1/wall?key=wall_test");
    expect(new Headers(calls[0].init.headers).get("Authorization")).toBeNull();
    expect(localStorage.getItem("sirisos.wall.key")).toBe("wall_test");
  });
});
