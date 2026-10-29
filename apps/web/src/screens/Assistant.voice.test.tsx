import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const recordings: { maxSeconds?: number }[] = [];
/** What each recording in turn picks up: speech or nothing. */
let heardPlan: boolean[] = [];

vi.mock("../api/voice", async (importOriginal) => {
  const real = await importOriginal<typeof import("../api/voice")>();
  class FakePlayer {
    onSpeaking: ((speaking: boolean) => void) | null = null;
    unlock() {}
    play() {}
    stop() {}
    async finished() {}
  }
  return {
    ...real,
    ReplyPlayer: FakePlayer,
    micUnavailableReason: () => null,
    micContext: () => ({}),
    startRecording: async (options: { maxSeconds?: number } = {}) => {
      recordings.push(options);
      const heard = heardPlan.shift() ?? false;
      return { analyser: {}, done: Promise.resolve(new Blob(["wav"])), stop: () => {}, heard: () => heard };
    },
  };
});

const { Assistant } = await import("./Assistant");

function ndjson(events: unknown[]): Response {
  return new Response(events.map((e) => JSON.stringify(e)).join("\n") + "\n", { headers: { "content-type": "application/x-ndjson" } });
}

describe("<Assistant /> voice", () => {
  beforeEach(() => {
    recordings.length = 0;
    heardPlan = [];
  });

  it("listens again by itself when SirisAI asks something, in the same conversation", async () => {
    signIn();
    heardPlan = [true, true];
    let turn = 0;
    const calls = mockFetch({
      "/api/v1/assistant/voice/converse": () =>
        ++turn === 1
          ? ndjson([
              { type: "transcript", text: "turn the lights off" },
              { type: "sentence", text: "Which room, the lounge or the office?", audio: null },
              { type: "final", conversation_id: "c3", response: "Which room, the lounge or the office?", expects_reply: true },
            ])
          : ndjson([
              { type: "transcript", text: "the lounge" },
              { type: "sentence", text: "Done.", audio: null },
              { type: "final", conversation_id: "c3", response: "Done.", expects_reply: false },
            ]),
      "/api/v1/assistant/voice": () => jsonResponse({ stt: true, tts: true }),   // after converse: routes match by prefix
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Assistant />
      </MemoryRouter>,
    );
    await user.click((await screen.findAllByRole("button", { name: "Talk to SirisAI" }))[0]);

    expect(await screen.findByText("Done.")).toBeInTheDocument();
    expect(recordings).toEqual([{}, { maxSeconds: 8 }]);           // the second one started without a tap
    const converse = calls.filter((c) => c.url.endsWith("/voice/converse"));
    expect(converse).toHaveLength(2);
    expect((converse[1].init.body as FormData).get("conversation_id")).toBe("c3");
    await waitFor(() => expect(recordings).toHaveLength(2));       // and it doesn't keep going after a plain answer
  });

  it("stops quietly when nothing is said after a question", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/assistant/voice/converse": () =>
        ndjson([
          { type: "transcript", text: "lights off" },
          { type: "final", conversation_id: "c4", response: "Which room?", expects_reply: true },
        ]),
      "/api/v1/assistant/voice": () => jsonResponse({ stt: true, tts: true }),
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Assistant />
      </MemoryRouter>,
    );
    heardPlan = [true, false];                                       // the follow-up hears nothing
    const [orb] = await screen.findAllByRole("button", { name: "Talk to SirisAI" });
    await user.click(orb);
    await waitFor(() => expect(recordings).toHaveLength(2));
    expect(await screen.findByText("Tap to talk")).toBeInTheDocument();
    expect(calls.filter((c) => c.url.endsWith("/voice/converse"))).toHaveLength(1);
  });
});
