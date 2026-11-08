import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { GoalsPromptCard } from "./GoalsPrompt";
import { GoalsCard } from "./Goals";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

describe("SirisAI's goals prompt on Home (8.3)", () => {
  it("asks to set the year's goals, and stops when you say so", async () => {
    signIn();
    let prompt: unknown = { kind: "set", year: 2027, goals: 2 };
    const calls = mockFetch({
      "/api/v1/goals/prompt": () => jsonResponse({ prompt }),
      "/api/v1/goals/set": () => { prompt = null; return jsonResponse({ prompt: null }); },
    });
    render(<MemoryRouter><GoalsPromptCard /></MemoryRouter>);
    expect(await screen.findByText("Time to set your 2027 goals")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Set them" })).toHaveAttribute("href", "/year");
    await userEvent.click(screen.getByRole("button", { name: "I've set them" }));
    await vi.waitFor(() => expect(screen.queryByText("Time to set your 2027 goals")).not.toBeInTheDocument());
    expect(calls.some((c) => c.url.endsWith("/goals/set?year=2027"))).toBe(true);
  });

  it("asks for December's review and links to it", async () => {
    signIn();
    mockFetch({ "/api/v1/goals/prompt": () => jsonResponse({ prompt: { kind: "review", year: 2026, goals: 3 } }) });
    render(<MemoryRouter><GoalsPromptCard /></MemoryRouter>);
    expect(await screen.findByText("Time to review your 2026 goals")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review them" })).toHaveAttribute("href", "/year?review=2026");
  });
});

describe("The year's review (8.3)", () => {
  it("ticks the unfinished to carry, and finishes the review", async () => {
    signIn();
    const goal = (id: string, title: string, state: string) => ({ id, title, kind: "done", target: null, unit: "", progress: 0, done: state === "done", notes: "", value: null, percent: null, state, source: null });
    const calls = mockFetch({
      "/api/v1/goals/review": () => jsonResponse({ carried: [goal("n", "Learn Spanish", "open")], into: 2027 }),
      "/api/v1/goals": () => jsonResponse({ year: 2026, today: "2026-12-05", through_year: 93, set_them: false, review_due: true,
        goals: [goal("a", "Get chartered", "done"), goal("b", "Learn Spanish", "open"), goal("c", "Paint", "open")] }),
    });
    render(<GoalsCard thisYear={2026} />);
    expect(await screen.findByText(/1 of 3 done in 2026/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Paint" }));
    await userEvent.click(screen.getByRole("button", { name: "Finish the review and carry 1 into 2027" }));
    expect(await screen.findByText("Review done: 1 carried into 2027.")).toBeInTheDocument();
    expect(calls.find((c) => c.url.includes("/goals/review"))?.init.body).toBe(JSON.stringify({ carry: ["b"] }));
  });
});
