import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { PresencePhonesCard } from "./PresencePhones";

describe("When everyone's out (8.5)", () => {
  it("says how long the phones must be gone, and switches SirisAI's own away run off", async () => {
    signIn();
    clearResources();
    let mode = "auto";
    const calls = mockFetch({
      "/api/v1/presence/away": (_u, init) => { if (init.method === "PUT") mode = JSON.parse(String(init.body)).mode; return jsonResponse({ mode, protocol: "away", away_after_minutes: 10 }); },
      "/api/v1/presence": () => jsonResponse({ home: true, phones: [{ name: "Brad's iPhone", source: "settings", home: true }] }),
      "/api/v1/netwatch": () => jsonResponse({ devices: [] }),
    });
    const user = userEvent.setup();
    render(<PresencePhonesCard />);
    expect(await screen.findByText(/off the Wi-Fi for 10 minutes in a row/)).toBeInTheDocument();
    expect(await screen.findByRole("radio", { name: "Run it" })).toHaveAttribute("aria-checked", "true");
    await user.click(screen.getByRole("radio", { name: "Nothing" }));
    expect(JSON.parse(String(calls.find((c) => c.init.method === "PUT")!.init.body))).toEqual({ mode: "off" });
    expect(await screen.findByText(/Apple Home \(or nothing\) handles it/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Nothing" })).toHaveAttribute("aria-checked", "true");
  });
});
