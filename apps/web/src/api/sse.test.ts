import { describe, expect, it } from "vitest";
import { readEvents } from "./sse";
import { sseResponse } from "../test/helpers";

async function collect(response: Response) {
  const out: unknown[] = [];
  for await (const e of readEvents(response.body!)) out.push(e);
  return out;
}

describe("readEvents", () => {
  it("reassembles events split across chunks and skips keepalives", async () => {
    const events = [{ type: "status", message: "Thinking" }, { type: "content", delta: "Hi ✨ there" }, { type: "final", response: { conversation_id: "c" } }];
    for (const size of [1, 3, 64, 4096]) {
      expect(await collect(sseResponse(events, size))).toEqual(events);
    }
  });

  it("handles CRLF framing, multi-line data and a final unterminated event", async () => {
    const body = new Response('data: {"a":\r\ndata: 1}\r\n\r\ndata: not json\n\ndata: {"b":2}');
    expect(await collect(body)).toEqual([{ a: 1 }, { b: 2 }]);
  });
});
