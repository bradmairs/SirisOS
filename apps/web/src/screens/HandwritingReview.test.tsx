import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HandwritingPanel } from "./HandwritingReview";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import type { HandwritingPage } from "../api/types";

const page = (title: string, text: string, odd: string[] = []): HandwritingPage => ({
  title, path: `Work/WSP/${title}.md`, source: `OneNote: WSP › Site › ${title}`, score: 5, illegible: 0, odd_words: odd, text,
});

describe("Handwriting to check", () => {
  beforeEach(() => {
    signIn();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:page", revokeObjectURL: () => {} }));
  });

  it("shows the shakiest page beside its reading, and takes it off the list when checked or corrected", async () => {
    const checks: { title: string; text: string }[] = [];
    mockFetch({
      "/api/v1/brain/handwriting/image": () =>
        new Response(new Blob(["png"], { type: "image/png" }), { status: 200, headers: { "X-Page-Parts": "1" } }),
      "/api/v1/brain/handwriting/check": (_u, init) => {
        checks.push(JSON.parse(init.body as string));
        return jsonResponse({ action: "checked", title: "x" });
      },
      "/api/v1/brain/handwriting": () =>
        jsonResponse([page("Site Visit", "Dellers underslip rear Meroh", ["meroh"]), page("Clean Page", "Riprap at the outlet.")]),
    });
    render(<HandwritingPanel />);
    expect(await screen.findByText("Site Visit")).toBeTruthy();
    expect(screen.getByText("meroh")).toBeTruthy();
    expect(await screen.findByAltText(/Site Visit, part 1/)).toBeTruthy();
    const reading = screen.getByLabelText("What the page says") as HTMLTextAreaElement;
    expect(reading.value).toBe("Dellers underslip rear Meroh");

    await userEvent.clear(reading);
    await userEvent.type(reading, "Dellows underslip near Moutere");
    await userEvent.click(screen.getByRole("button", { name: /Save my reading/ }));
    await waitFor(() => expect(checks[0]).toEqual({ title: "Site Visit", text: "Dellows underslip near Moutere" }));
    expect(await screen.findByText("Clean Page")).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: /It's right/ }));
    await waitFor(() => expect(checks[1]).toEqual({ title: "Clean Page", text: "" }));
    expect(await screen.findByText("Nothing left to check.")).toBeTruthy();
  });

  it("still lets Brad check the reading when the page can't be drawn", async () => {
    mockFetch({
      "/api/v1/brain/handwriting/image": () => jsonResponse({ detail: "SirisAI: OneNote isn't signed in." }, 404),
      "/api/v1/brain/handwriting": () => jsonResponse([page("Site Visit", "rear Meroh")]),
    });
    render(<HandwritingPanel />);
    expect(await screen.findByText(/OneNote isn't signed in/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /It's right/ })).toBeTruthy();
  });
});
