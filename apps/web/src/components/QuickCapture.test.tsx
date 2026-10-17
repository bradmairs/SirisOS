import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuickCapture } from "./QuickCapture";
import { downsample } from "../api/voice";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

describe("<QuickCapture />", () => {
  it("captures a note with a photo into Siris' inbox", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/brain/capture": () => jsonResponse({ saved: true, title: "Pit lid cracked", action: "created" }) });
    const user = userEvent.setup();
    let closed = false;
    render(<QuickCapture onClose={() => (closed = true)} />);
    await user.type(screen.getByLabelText("Capture text"), "Pit lid cracked at Mooroopna PS");
    const photo = new File([new Uint8Array([0xff, 0xd8, 0xff])], "IMG_0001.jpg", { type: "image/jpeg" });
    await user.upload(screen.getByLabelText("Photo file"), photo);
    expect(await screen.findByAltText("Photo to capture", undefined, { timeout: 3000 })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Save/ }));
    expect(await screen.findByText(/Saved to Siris' inbox as “Pit lid cracked”/)).toBeInTheDocument();
    const body = JSON.parse(String(calls.find((c) => c.url === "/api/v1/brain/capture")!.init.body));
    expect(body.text).toBe("Pit lid cracked at Mooroopna PS");
    expect(body.image).toMatch(/^data:image\/jpeg;base64,/);
    await new Promise((r) => setTimeout(r, 950));
    expect(closed).toBe(true);
  });

  it("sends a bare link as a url", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/brain/capture": () => jsonResponse({ saved: true, title: "x" }) });
    const user = userEvent.setup();
    render(<QuickCapture onClose={() => undefined} />);
    await user.type(screen.getByLabelText("Capture text"), "https://www.ipwea.org/events");
    await user.click(screen.getByRole("button", { name: /Save/ }));
    await screen.findByRole("status");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ url: "https://www.ipwea.org/events" });
  });
});

describe("downsample", () => {
  it("averages 48 kHz down to 16 kHz", () => {
    const { chunks, rate } = downsample([new Float32Array([0.3, 0.6, 0.9, -0.3, -0.6, -0.9])], 48000, 16000);
    expect(rate).toBe(16000);
    expect(Array.from(chunks[0]).map((v) => Math.round(v * 10) / 10)).toEqual([0.6, -0.6]);
  });
});
