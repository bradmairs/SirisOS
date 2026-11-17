import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { ExerciseImage } from "./ExerciseImage";
import { mockFetch, signIn } from "../test/helpers";

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe("exercise pictures (9.7)", () => {
  it("plays the start and end of the movement in turn", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    signIn();
    let n = 0;
    URL.createObjectURL = () => `blob:frame-${n++}`;
    const calls = mockFetch({ "/api/v1/gym/exercises/bench-press/image": () => new Response(new Blob(["jpg"]), { status: 200, headers: { "Content-Type": "image/jpeg" } }) });
    render(<ExerciseImage id="bench-press" name="Bench Press" frames={2} version="t1" />);
    const img = await screen.findByRole("img", { name: "Bench Press: start of the movement" });
    expect(calls.map((c) => c.url)).toEqual(["/api/v1/gym/exercises/bench-press/image?frame=0", "/api/v1/gym/exercises/bench-press/image?frame=1"]);
    act(() => { vi.advanceTimersByTime(1300); });
    expect(img).toHaveAccessibleName("Bench Press: end of the movement");
  });

  it("shows nothing when there's no picture to get", async () => {
    signIn();
    mockFetch({ "/api/v1/gym/exercises/nope/image": () => new Response(JSON.stringify({ detail: "No picture" }), { status: 404 }) });
    const { container } = render(<ExerciseImage id="nope" name="Nope" version="t2" />);
    await vi.waitFor(() => expect(container.querySelector(".skeleton")).toBeNull());
    expect(screen.queryByRole("img")).toBeNull();
  });
});
