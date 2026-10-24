import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HomeTimes } from "./HomeTimes";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const PLAN = {
  weekday: { morning: "05:00", day: "08:30", evening: "16:30", night: "23:00" },
  weekend: { morning: "05:00", day: "10:00", evening: "17:00", night: "23:00" },
  sections: {
    morning: ["Now", "Today", "Home"], work: ["Today", "Now", "Home"], weekend: ["Home", "Today", "Now"],
    evening: ["Today", "Home", "Now"], night: ["Today", "Home", "Now"],
  },
};

describe("<HomeTimes />", () => {
  it("changes a start time and an order, and saves them for every device", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/home/schedule": (_u, init) => jsonResponse(init.method === "PUT" ? JSON.parse(String(init.body)) : PLAN) });
    const onSaved = vi.fn(), onClose = vi.fn();
    const user = userEvent.setup();
    render(<HomeTimes onClose={onClose} onSaved={onSaved} />);
    const work = await screen.findByLabelText("Work · Daytime, weekdays");
    expect(work).toHaveValue("08:30");
    fireEvent.change(work, { target: { value: "09:00" } });   // jsdom types into time fields one segment at a time
    await user.click(screen.getByRole("button", { name: "Evening: move Home up" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    const saved = JSON.parse(String(calls.find((c) => c.init.method === "PUT")!.init.body));
    expect(saved.weekday.day).toBe("09:00");
    expect(saved.sections.evening).toEqual(["Home", "Today", "Now"]);
    expect(onClose).toHaveBeenCalled();
  });

  it("won't save a day that runs backwards", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/home/schedule": () => jsonResponse({ ...PLAN, weekday: { ...PLAN.weekday, evening: "08:00" } }) });
    const user = userEvent.setup();
    render(<HomeTimes onClose={() => undefined} onSaved={() => undefined} />);
    await user.click(await screen.findByRole("button", { name: "Save" }));
    expect(screen.getByRole("alert")).toHaveTextContent("start after the one before it");
    expect(calls.some((c) => c.init.method === "PUT")).toBe(false);
  });
});
