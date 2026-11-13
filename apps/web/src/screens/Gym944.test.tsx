import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { EditExerciseSheet, RecoveryCard } from "./GymReview";
import { NewExercise } from "./GymExercises";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

describe("SirisGym 9.44: helper muscles", () => {
  it("edits an exercise's helpers", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/gym/exercises/my-a": () => jsonResponse({}) });
    const user = userEvent.setup();
    render(<MemoryRouter><EditExerciseSheet exercise={{ id: "my-a", name: "Cable V Bar Pulldown", primary: "back", secondary: ["biceps"], equipment: "cable", kind: "weight", custom: true }}
      onClose={() => {}} onSaved={() => {}} /></MemoryRouter>);
    const helpers = screen.getByRole("group", { name: "Helper muscles" });
    expect(within(helpers).getByRole("button", { name: "biceps" })).toHaveAttribute("aria-pressed", "true");
    expect(within(helpers).queryByRole("button", { name: "back" })).toBeNull();  // the main muscle isn't offered
    await user.click(within(helpers).getByRole("button", { name: "forearms" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(JSON.parse(String(calls.find((c) => c.url === "/api/v1/gym/exercises/my-a")!.init.body)).secondary).toEqual(["biceps", "forearms"]);
  });

  it("fills a new exercise's muscles from its name", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/gym/anatomy": () => jsonResponse({ primary: "back", secondary: ["biceps", "forearms"] }),
      "/api/v1/gym/exercises": () => jsonResponse({ id: "my-b" }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><NewExercise onClose={() => {}} onSaved={() => {}} /></MemoryRouter>);
    await user.type(screen.getByRole("textbox", { name: "Name" }), "Meadows Row");
    await user.tab();
    expect(await screen.findByRole("combobox", { name: "Main muscle" })).toHaveValue("back");
    expect(screen.getByRole("button", { name: "biceps" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(JSON.parse(String(calls.find((c) => c.url === "/api/v1/gym/exercises")!.init.body))).toMatchObject({ name: "Meadows Row", primary: "back", secondary: ["biceps", "forearms"] });
  });

  it("says when a muscle is tired from helping", () => {
    render(<RecoveryCard recovery={[{ muscle: "biceps", last: "2026-11-10T07:00:00Z", hours: 9, ready: 50, via: "helper" }, { muscle: "back", last: "2026-11-10T07:00:00Z", hours: 9, ready: 19, via: "main" }]} />);
    expect(screen.getByText(/· helping/)).toBeInTheDocument();
    expect(screen.getAllByText(/helping/)).toHaveLength(1);
  });
});
