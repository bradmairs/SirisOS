import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { roomGlow, type HomeJob, type Maintenance } from "../api/maintenance";
import { HomeJobsWidget, MaintenanceCard } from "./Maintenance";

const job = (over: Partial<HomeJob>): HomeJob => ({
  id: "j", title: "Job", room: "office", appliance: null, every_days: 90, last_done: "2026-07-01", snoozed_until: null, notes: "",
  due_on: "2026-09-29", state: "overdue", days: -30, ...over,
});
const data = (jobs: HomeJob[]): Maintenance => ({
  today: "2026-10-29", jobs, appliances: [],
  summary: { overdue: jobs.filter((j) => j.state === "overdue").length, due: jobs.filter((j) => j.state === "due").length, soon: 0, unset: jobs.filter((j) => j.state === "unset").length, rooms: [], warranties_ending: [] },
});

describe("maintenance", () => {
  it("Home shows what's due, and Done ticks it off", async () => {
    signIn();
    clearResources();
    const ac = job({ id: "ac", title: "Clean the AC filters" });
    const calls = mockFetch({
      "/api/v1/maintenance/jobs/ac/done": () => jsonResponse(data([{ ...ac, state: "ok", days: 90, last_done: "2026-10-29" }])),
      "/api/v1/maintenance": () => jsonResponse(data([ac, job({ id: "bbq", title: "Clean the BBQ", room: "bbq", state: "ok", days: 20 })])),
    });
    const user = userEvent.setup();
    const { container } = render(<MemoryRouter><HomeJobsWidget /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Around the house" });
    expect(within(card).getByText("Office · Every 3 months · Overdue by 30 days")).toBeInTheDocument();
    expect(within(card).queryByText("Clean the BBQ")).not.toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Done: Clean the AC filters" }));
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(calls.some((c) => c.url.endsWith("/jobs/ac/done"))).toBe(true);
  });

  it("asks when a starter was last done, and adds a job", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/maintenance": () => jsonResponse(data([job({ id: "smoke", title: "Test the smoke alarms", room: "hall1", every_days: 30, last_done: null, due_on: null, state: "unset", days: null })])),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><MaintenanceCard /></MemoryRouter>);
    const field = await screen.findByLabelText("When you last did: Test the smoke alarms");
    await user.type(field, "2026-10-01");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.find((c) => c.init.method === "PATCH")).toBeTruthy());
    expect(JSON.parse(String(calls.find((c) => c.init.method === "PATCH")!.init.body))).toEqual({ last_done: "2026-10-01" });

    await user.click(screen.getByRole("button", { name: /Add a job/ }));
    const sheet = await screen.findByRole("dialog", { name: "Add a job" });
    await user.type(within(sheet).getByLabelText("Job"), "Flush the hot water system");
    await user.selectOptions(within(sheet).getByLabelText("Room"), "garage");
    await user.selectOptions(within(sheet).getByLabelText("How often"), "365");
    await user.click(within(sheet).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/maintenance/jobs") && c.init.method === "POST")).toBe(true));
    const sent = JSON.parse(String(calls.find((c) => c.url.endsWith("/maintenance/jobs"))!.init.body));
    expect(sent).toMatchObject({ title: "Flush the hot water system", room: "garage", every_days: 365 });
  });

  it("overdue rooms glow hotter than due ones", () => {
    const glow = roomGlow(data([job({ room: "office" }), job({ room: "kitchen", state: "due", days: 0 }), job({ room: "bbq", state: "ok" })]));
    expect(glow).toEqual({ office: { color: 0xff7a45, strength: 1 }, kitchen: { color: 0xffb454, strength: 0.7 } });
  });
});
