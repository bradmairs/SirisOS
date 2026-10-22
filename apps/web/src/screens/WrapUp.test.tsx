import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { WrapUpScreen } from "./WrapUp";
import type { WrapUpOverview } from "../api/wrapup";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const TODAY: WrapUpOverview = {
  date: "2026-10-22",
  done: [{ id: "sirisos:a", title: "Send RFI" }],
  open: [{ id: "sirisos:b", source: "sirisos", title: "Call the plumber", detail: null, due: "2026-10-22", time: null, repeat: "none", group: "today" }],
  meetings: [
    { title: "IPWEA stormwater webinar", start: "2026-10-22T12:00:00+11:00", end: "2026-10-22T13:30:00+11:00", location: "Online",
      cpd: { key: "k1", title: "IPWEA stormwater webinar", hours: 1.5, category: "Formal learning" } },
    { title: "Werribee design review", start: "2026-10-22T14:00:00+11:00", end: "2026-10-22T15:00:00+11:00", location: null, cpd: null },
  ],
  calendar_unavailable: false,
  suggested_top3: ["Draft the drainage report"],
  saved: null,
};

const wrap = () => render(<MemoryRouter><WrapUpScreen /></MemoryRouter>);

describe("<WrapUpScreen />", () => {
  it("walks through today, CPD, tomorrow's top 3 and a line about the day", async () => {
    signIn();
    let served = TODAY;
    const calls = mockFetch({
      "/api/v1/wrapup/cpd/k1": () => {
        served = { ...TODAY, meetings: [{ ...TODAY.meetings[0], cpd: null }, TODAY.meetings[1]] };
        return jsonResponse({ key: "k1", task: { title: "Log it" } });
      },
      "/api/v1/wrapup": (_u, init) => {
        if (init.method === "POST") {
          const body = JSON.parse(String(init.body));
          served = { ...served, saved: { ...body, journal_saved_as: "Day 2026-10-22", at: "2026-10-22T17:40" } };
          return jsonResponse(served.saved);
        }
        return jsonResponse(served);
      },
    });
    const user = userEvent.setup();
    wrap();
    expect(await screen.findByText("Done today: Send RFI.")).toBeInTheDocument();
    expect(screen.getByText("Call the plumber")).toBeInTheDocument();
    expect(screen.getByText(/looks like CPD · 1.5 h/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Log Werribee design review as CPD" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Log IPWEA stormwater webinar as CPD" }));
    expect(await screen.findByRole("status")).toHaveTextContent("log “IPWEA stormwater webinar” in Engineers Australia tomorrow");

    expect(screen.getByLabelText("Top 1")).toHaveValue("Draft the drainage report");
    await user.type(screen.getByLabelText("Top 2"), "Call Dana");
    await user.type(screen.getByLabelText("One line about today"), "Good site visit.");
    await user.click(screen.getByRole("button", { name: "Done for today" }));

    const sent = JSON.parse(String(calls.find((c) => c.url === "/api/v1/wrapup" && c.init.method === "POST")!.init.body));
    expect(sent).toEqual({ top3: ["Draft the drainage report", "Call Dana"], journal: "Good site visit." });
    const done = await screen.findByRole("region", { name: "Wrapped up" });
    expect(within(done).getByText("Call Dana")).toBeInTheDocument();
    expect(within(done).getByText(/saved to Siris/)).toBeInTheDocument();
  });

  it("moves what's left to tomorrow in one go", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/tasks/sirisos%3Ab/snooze": () => jsonResponse({ id: "sirisos:b", snoozed_until: "2026-10-23" }),
      "/api/v1/wrapup": () => jsonResponse(TODAY),
    });
    const user = userEvent.setup();
    wrap();
    await user.click(await screen.findByRole("button", { name: "Move the rest to tomorrow" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Moved 1 to tomorrow");
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/snooze"))!.init.body))).toEqual({ until: "tomorrow" });
  });
});
