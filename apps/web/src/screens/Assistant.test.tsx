import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Assistant, applyEvent, type Message } from "./Assistant";
import { jsonResponse, mockFetch, signIn, sseResponse } from "../test/helpers";

describe("applyEvent", () => {
  const base: Message = { role: "assistant", text: "", streaming: true };

  it("streams content, drops provisional text when a tool starts, and finalises", () => {
    let m = applyEvent(base, { type: "content", delta: "Let me check" });
    m = applyEvent(m, { type: "tool_start", name: "weather_current", arguments: {} });
    expect(m.text).toBe("");
    m = applyEvent(m, { type: "tool_end", name: "weather_current", status: "ok" });
    m = applyEvent(m, { type: "content", delta: "It's 18°" });
    m = applyEvent(m, {
      type: "final",
      response: { conversation_id: "c1", response: "It's 18° and sunny", tool_call: null, confirmation_required: null, plan: null, used_planner: false },
    });
    expect(m).toMatchObject({ text: "It's 18° and sunny", streaming: false, tools: [{ name: "weather_current", status: "ok" }] });
  });

  it("surfaces confirmations and errors", () => {
    const pending = { name: "lights_off", arguments: { room: "lounge" } };
    const m = applyEvent(base, {
      type: "final",
      response: { conversation_id: "c1", response: null, tool_call: null, confirmation_required: pending, plan: null, used_planner: true },
    });
    expect(m.pending).toEqual(pending);
    expect(m.usedPlanner).toBe(true);
    expect(applyEvent(base, { type: "error", status: 503, detail: "LLM down" }).error).toBe("LLM down");
  });
});

describe("<Assistant />", () => {
  it("sends a prompt, streams the reply, and runs a confirmed tool", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/assistant/chat/stream": () =>
        sseResponse([
          { type: "status", message: "Thinking" },
          { type: "content", delta: "Turning " },
          { type: "final", response: { conversation_id: "c7", response: "I can turn the lounge lights off.", tool_call: null, confirmation_required: { name: "lights_off", arguments: { room: "lounge" } }, plan: null, used_planner: false } },
        ]),
      "/api/v1/assistant/chat/confirm/stream": () =>
        sseResponse([{ type: "final", response: { conversation_id: "c7", response: "Done, lounge lights are off.", tool_call: null, confirmation_required: null, plan: null, used_planner: false } }]),
      "/api/v1/assistant/conversations": () => jsonResponse([]),
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Assistant />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText("Message Siris"), "lights off{Enter}");
    expect(await screen.findByText("I can turn the lounge lights off.")).toBeInTheDocument();
    expect(JSON.parse(calls[0].init.body as string)).toEqual({ prompt: "lights off" });
    expect(new Headers(calls[0].init.headers).get("Authorization")).toBe("Bearer test-token");

    await user.click(screen.getByRole("button", { name: /allow/i }));
    expect(await screen.findByText("Done, lounge lights are off.")).toBeInTheDocument();
    const confirm = calls.find((c) => c.url.includes("confirm"))!;
    expect(JSON.parse(confirm.init.body as string)).toEqual({ conversation_id: "c7", tool_name: "lights_off", arguments: { room: "lounge" }, use_planner: false });
  });

  it("continues the same conversation on the next turn", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/assistant/chat/stream": () =>
        sseResponse([{ type: "final", response: { conversation_id: "c9", response: "ok", tool_call: null, confirmation_required: null, plan: null, used_planner: false } }]),
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Assistant />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText("Message Siris"), "one{Enter}");
    await screen.findByText("ok");
    await user.type(screen.getByLabelText("Message Siris"), "two{Enter}");
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(JSON.parse(calls[1].init.body as string)).toEqual({ prompt: "two", conversation_id: "c9" });
  });
});
