import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { MeetingScreen } from "./Meeting";
import type { MeetingPrep } from "../api/meetings";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const PREP: MeetingPrep = {
  title: "Werribee drainage design review", start: "2026-10-23T10:00:00+11:00", end: "2026-10-23T11:00:00+11:00", location: "GVW Shepparton", found: true,
  people: [{ email: "dana.lee@example.com", name: "Dana Lee" }],
  notes: [{ title: "Werribee Drainage", excerpt: "Levels due to Dana by Friday.", type: "project" }],
  emails: [{ uid: "41", sender: "Dana Lee", subject: "Werribee levels", date: "Tue, 20 Oct 2026 09:12:00 +1100", snippet: "Attached." }],
  tasks: [],
};

const at = (url: string) => render(
  <MemoryRouter initialEntries={[url]}><Routes><Route path="/meeting" element={<MeetingScreen />} /></Routes></MemoryRouter>,
);

describe("<MeetingScreen />", () => {
  it("shows the prep and files notes into Siris with actions as tasks", async () => {
    signIn();
    localStorage.clear();
    const calls = mockFetch({
      "/api/v1/meetings/prep": () => jsonResponse(PREP),
      "/api/v1/meetings/notes": () => jsonResponse({ saved_as: "Meeting: Werribee drainage design review (2026-10-23)", tasks: ["Update the pipe sizing"] }),
    });
    const user = userEvent.setup();
    at(`/meeting?title=${encodeURIComponent(PREP.title)}&start=${encodeURIComponent(PREP.start!)}`);
    expect(await screen.findByText("Dana Lee", { selector: ".chip" })).toBeInTheDocument();
    expect(screen.getByText("Levels due to Dana by Friday.")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Recent emails" })).getByText("Werribee levels")).toBeInTheDocument();
    expect(calls[0].url).toBe(`/api/v1/meetings/prep?title=${encodeURIComponent(PREP.title)}&start=${encodeURIComponent(PREP.start!)}`);

    await user.type(screen.getByLabelText("Meeting notes"), "Agreed levels.{enter}- [[ ] Update the pipe sizing");
    await user.click(screen.getByRole("button", { name: "Save to Siris" }));
    expect(await screen.findByRole("status")).toHaveTextContent("added 1 task: Update the pipe sizing");
    const sent = JSON.parse(String(calls.find((c) => c.url === "/api/v1/meetings/notes")!.init.body));
    expect(sent).toEqual({ title: PREP.title, start: PREP.start, text: "Agreed levels.\n- [ ] Update the pipe sizing" });
  });

  it("lists upcoming meetings when none is picked", async () => {
    signIn();
    mockFetch({ "/api/v1/meetings": () => jsonResponse({ meetings: [{ title: "Site visit", start: "2026-10-23T14:00:00+11:00", end: null, location: "Werribee", attendees: ["a@b.com"] }] }) });
    at("/meeting");
    const link = await screen.findByRole("link", { name: "Site visit" });
    expect(link.getAttribute("href")).toMatch(/^\/meeting\?title=Site%20visit&start=/);
  });
});
