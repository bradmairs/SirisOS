import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { jsonResponse, mockFetch } from "../test/helpers";
import { ActScreen } from "./Act";

const note = { title: "Call the plumber", body: "Due now", url: "/tasks", actions: [{ id: "done", title: "Done" }, { id: "later", title: "In an hour" }], done: null };

function show(signedIn = false) {
  render(
    <MemoryRouter initialEntries={["/act?t=tok.en"]}>
      <Routes>
        <Route path="/act" element={<ActScreen signedIn={signedIn} />} />
        <Route path="/tasks" element={<p>Tasks screen</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("<ActScreen />", () => {
  it("shows the notification's buttons without signing in, and presses one", async () => {
    localStorage.clear();
    const calls = mockFetch({
      "/api/v1/push/act?t=": () => jsonResponse(note),
      "/api/v1/push/act": () => jsonResponse({ done: "later", message: "Moved to 10:30.", url: "/tasks" }),
    });
    const user = userEvent.setup();
    show();
    expect(await screen.findByRole("heading", { name: "Call the plumber" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "In an hour" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Moved to 10:30.");
    const post = calls.find((c) => c.init.method === "POST")!;
    expect(JSON.parse(String(post.init.body))).toEqual({ token: "tok.en", action: "later" });
    expect(new Headers(post.init.headers).get("Authorization")).toBeNull();
    expect(screen.getByRole("button", { name: "Sign in to SirisOS" })).toBeInTheDocument();
  });

  it("says when it was already done, and opens the screen when signed in", async () => {
    mockFetch({ "/api/v1/push/act": () => jsonResponse({ ...note, done: "done" }) });
    const user = userEvent.setup();
    show(true);
    expect(await screen.findByRole("status")).toHaveTextContent("Already done: Done.");
    expect(screen.queryByRole("button", { name: "In an hour" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Open in SirisOS" }));
    expect(screen.getByText("Tasks screen")).toBeInTheDocument();
  });

  it("explains an expired notification", async () => {
    mockFetch({ "/api/v1/push/act": () => jsonResponse({ detail: "This notification is more than two days old. Open SirisOS to act on it." }, 403) });
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("more than two days old");
  });

  it("asks for SirisAI's approval PIN when a button needs it", async () => {
    const bodies: unknown[] = [];
    mockFetch({
      "/api/v1/push/act?t=": () => jsonResponse({ ...note, title: "2 updates waiting", actions: [{ id: "install", title: "Install updates" }] }),
      "/api/v1/push/act": (_url, init) => {
        const body = JSON.parse(String(init.body));
        bodies.push(body);
        return body.pin ? jsonResponse({ done: "install", message: "Install updates: done.", url: "/inbox" })
          : jsonResponse({ detail: "SirisAI: pin_required: approving this needs your PIN" }, 403);
      },
    });
    const user = userEvent.setup();
    show();
    await user.click(await screen.findByRole("button", { name: "Install updates" }));
    await user.type(await screen.findByLabelText("This needs your SirisAI approval PIN."), "4321");
    await user.click(screen.getByRole("button", { name: "Install updates" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Install updates: done.");
    expect(bodies).toEqual([{ token: "tok.en", action: "install" }, { token: "tok.en", action: "install", pin: "4321" }]);
  });
});
