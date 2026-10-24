import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { GoalsCard } from "./Goals";

const goal = (over: object) => ({ id: "g", title: "x", kind: "done", target: null, unit: "", progress: 0, done: false, notes: "", value: 0, percent: 0, state: "open", source: null, ...over });

describe("<GoalsCard />", () => {
  it("shows each goal's progress against the year, counts and ticks", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/goals/": () => jsonResponse({}),
      "/api/v1/goals?year=2026": () => jsonResponse({ year: 2026, today: "2026-10-24", through_year: 81, set_them: false, goals: [
        goal({ id: "run", title: "Run 1,000 km", kind: "running_km", target: 1000, unit: "km", value: 612.4, percent: 61, state: "behind", source: "Running" }),
        goal({ id: "books", title: "Read 12 books", kind: "count", target: 12, unit: "books", progress: 10, value: 10, percent: 83, state: "on_track" }),
        goal({ id: "cpeng", title: "Get chartered" }),
      ] }),
    });
    const user = userEvent.setup();
    render(<GoalsCard thisYear={2026} />);
    const card = await screen.findByRole("region", { name: "2026 goals" });
    expect(await within(card).findByText("81% of the way through 2026.")).toBeInTheDocument();
    expect(within(card).getByText(/612.4 of 1,000 km/)).toBeInTheDocument();
    expect(within(card).getByText("Behind")).toBeInTheDocument();
    expect(within(card).getByRole("img", { name: "61% there" })).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: 'One more for "Read 12 books"' }));
    await user.click(within(card).getByRole("button", { name: 'Mark "Get chartered" done' }));
    const patches = calls.filter((c) => c.init.method === "PATCH").map((c) => [c.url, JSON.parse(String(c.init.body))]);
    expect(patches).toEqual([["/api/v1/goals/books?year=2026", { progress: 11 }], ["/api/v1/goals/cpeng?year=2026", { done: true }]]);
  });

  it("asks for the new year's goals in January, and adds one", async () => {
    signIn();
    clearResources();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const calls = mockFetch({ "/api/v1/goals?year=2027": (_u, init) => init.method === "POST" ? jsonResponse({ id: "n" }) : jsonResponse({ year: 2027, today: "2027-01-02", through_year: 1, set_them: true, goals: [] }) });
    const user = userEvent.setup();
    render(<GoalsCard thisYear={2027} />);
    expect(await screen.findByText(/A new year: what do you want to achieve in 2027/)).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Goal" }), "Run 1,000 km");
    await user.selectOptions(screen.getByRole("combobox", { name: "How it's tracked" }), "running_km");
    await user.type(screen.getByRole("spinbutton", { name: "Target" }), "1000");
    await user.click(screen.getByRole("button", { name: "Add goal" }));
    const post = calls.find((c) => c.init.method === "POST")!;
    expect(JSON.parse(String(post.init.body))).toEqual({ title: "Run 1,000 km", kind: "running_km", target: 1000 });
  });
});
