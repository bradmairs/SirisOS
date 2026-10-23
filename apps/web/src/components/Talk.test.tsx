import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { Talk } from "./Talk";

describe("<Talk />", () => {
  it("does what's typed when there's no microphone, says the reply and opens the place", async () => {
    signIn();
    localStorage.removeItem("sirisos.talk.muted");
    const spoken: string[] = [];
    vi.stubGlobal("speechSynthesis", { cancel: () => undefined, speak: (u: { text: string }) => spoken.push(u.text) });
    vi.stubGlobal("SpeechSynthesisUtterance", class { lang = ""; constructor(public text: string) {} });
    const calls = mockFetch({ "/api/v1/command": () => jsonResponse({ intent: "task", reply: "Added: Call the plumber, Friday.", link: "/tasks" }) });
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<Talk onClose={onClose} />} />
          <Route path="/tasks" element={<p>Tasks screen</p>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/HTTPS/);  // jsdom isn't a secure context: no mic
    expect(screen.getByText(/What's on tomorrow/)).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Say it in words" }), "add a task to call the plumber Friday");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Added: Call the plumber, Friday.")).toBeInTheDocument();
    expect(screen.getByText("“add a task to call the plumber Friday”")).toBeInTheDocument();
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ text: "add a task to call the plumber Friday" });
    expect(spoken).toEqual(["Added: Call the plumber, Friday."]);
    await user.click(screen.getByRole("button", { name: /Open/ }));
    expect(onClose).toHaveBeenCalled();
    expect(screen.getByText("Tasks screen")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("stays quiet when muted", async () => {
    signIn();
    const spoken: string[] = [];
    vi.stubGlobal("speechSynthesis", { cancel: () => undefined, speak: (u: { text: string }) => spoken.push(u.text) });
    vi.stubGlobal("SpeechSynthesisUtterance", class { constructor(public text: string) {} });
    mockFetch({ "/api/v1/command": () => jsonResponse({ intent: "ask", reply: "Showers.", link: null }) });
    const user = userEvent.setup();
    render(<MemoryRouter><Talk onClose={() => undefined} /></MemoryRouter>);
    await user.click(screen.getByRole("button", { name: "Don't read replies aloud" }));
    await user.type(screen.getByRole("textbox", { name: "Say it in words" }), "weather?{enter}");
    expect(await screen.findByText("Showers.")).toBeInTheDocument();
    expect(spoken).toEqual([]);
    expect(localStorage.getItem("sirisos.talk.muted")).toBe("1");
    vi.unstubAllGlobals();
  });
});
