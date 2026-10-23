import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmailScreen } from "./Email";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const REPLY = { id: "ai:12", who: "Dana Lee", subject: "Werribee levels", snippet: "Hi Brad, attached are the levels…",
  draft: "Thanks Dana, I'll check them tomorrow.\n\nBrad", in_drafts_folder: true, can_send: true, created_at: null };

describe("<EmailScreen />", () => {
  it("sends an edited reply after a confirm", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/email/triage": () => jsonResponse({ replies: [REPLY], snoozed: 0, unavailable: false }),
      "/api/v1/attention/ai%3A12/act": () => jsonResponse({ item: { id: "ai:12" }, result: { sent: true } }),
    });
    const user = userEvent.setup();
    render(<EmailScreen />);
    const box = await screen.findByLabelText("Reply to Dana Lee");
    expect(box).toHaveValue(REPLY.draft);
    await user.clear(box);
    await user.type(box, "Thanks Dana, checking them now.");
    expect(screen.getByText(/Edited: the version above is what's sent/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Send edited reply/ }));
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Sent your reply to Dana Lee");
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/act"))!.init.body))).toEqual({ action: "send", body: "Thanks Dana, checking them now." });
    await waitFor(() => expect(screen.queryByLabelText("Reply to Dana Lee")).not.toBeInTheDocument());
  });

  it("snoozes one until tomorrow", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/email/triage": () => jsonResponse({ replies: [REPLY], snoozed: 0, unavailable: false }),
      "/api/v1/attention/ai%3A12/snooze": () => jsonResponse({ id: "ai:12", until: "2026-10-24T08:00:00+00:00" }),
    });
    const user = userEvent.setup();
    render(<EmailScreen />);
    await user.click(await screen.findByRole("button", { name: /Tomorrow/ }));
    expect(await screen.findByRole("status")).toHaveTextContent("Snoozed Dana Lee until tomorrow morning");
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/snooze"))!.init.body))).toEqual({ until: "tomorrow" });
  });

  it("says when nothing is waiting", async () => {
    signIn();
    mockFetch({ "/api/v1/email/triage": () => jsonResponse({ replies: [], snoozed: 2, unavailable: false }) });
    render(<EmailScreen />);
    expect(await screen.findByText(/No replies waiting.*2 snoozed/)).toBeInTheDocument();
  });
});
