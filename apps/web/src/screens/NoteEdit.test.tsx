import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { BrainManage } from "./BrainManage";
import { NoteHit } from "./NoteHit";
import { PresencePhonesCard } from "./PresencePhones";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

describe("editing Siris (7.2)", () => {
  it("edits a note's text with the version it was opened at", async () => {
    signIn();
    let body = "# Gym Plan\n\nThree days a week.";
    const calls = mockFetch({
      "/api/v1/brain/note": () => jsonResponse({ title: "Gym Plan", path: "Notes/Gym Plan.md", links: [], backlinks: [], body, version: "abc123" }),
      "/api/v1/brain/edit": (_u, init) => { body = JSON.parse(String(init.body)).body; return jsonResponse({ action: "edited", title: "Gym Plan", path: "Notes/Gym Plan.md", links_added: ["Back Squat"], version: "def456" }); },
      "/api/v1/brain/note-connections": () => jsonResponse({}),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><NoteHit hit={{ title: "Gym Plan", path: "Notes/Gym Plan.md", type: "note", tags: [], excerpts: [] }} onOpen={() => {}} onDeleted={() => {}} /></MemoryRouter>);
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const box = await screen.findByLabelText("Text of Gym Plan");
    await user.clear(box);
    await user.type(box, "Four days a week, with Back Squat.");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved, and linked Back Squat.")).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/brain/edit"))!.init.body))).toEqual({ title: "Gym Plan", body: "Four days a week, with Back Squat.", version: "abc123" });
  });

  it("corrects one of SirisAI's memories", async () => {
    signIn();
    const m = { id: 7, position: 1, content: "Dom's birthday is 3 March", created_at: "2026-10-01T00:00:00Z", recall_count: 0, last_recalled_at: null };
    const calls = mockFetch({
      "/api/v1/memories/7": () => jsonResponse({ ...m, content: "Dom's birthday is 4 March" }),
      "/api/v1/memories": () => jsonResponse([m]),
      "/api/v1/brain/deleted": () => jsonResponse([]),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><BrainManage /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Edit memory: Dom's birthday is 3 March" }));
    const box = screen.getByLabelText("Memory");
    await user.clear(box);
    await user.type(box, "Dom's birthday is 4 March");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Dom's birthday is 4 March")).toBeInTheDocument();
    const put = calls.find((c) => c.url === "/api/v1/memories/7");
    expect(put!.init.method).toBe("PUT");
    expect(JSON.parse(String(put!.init.body))).toEqual({ content: "Dom's birthday is 4 March" });
  });
});

describe("who counts as home (7.2)", () => {
  it("lists the phones, adds one from the network and removes an added one", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/presence/phones": () => jsonResponse({ home: true, phones: [] }),
      "/api/v1/presence": () => jsonResponse({ home: true, checked_at: null, since: null, phones: [
        { name: "brads-iphone", source: "settings", home: false }, { name: "Dom's iPhone", source: "added", home: true }] }),
      "/api/v1/netwatch": () => jsonResponse({ watching: true, devices: [{ id: "aa", name: "Guest Pixel", kind: "client", first_seen: null, last_seen: null, trusted: true, type: "Phone" }] }),
    });
    const user = userEvent.setup();
    render(<PresencePhonesCard />);
    expect(await screen.findByText("Dom's iPhone")).toBeInTheDocument();
    expect(screen.getByText("Someone's home")).toBeInTheDocument();
    expect(screen.getByText("Away · from SirisAI's settings")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "+ Guest Pixel" }));
    await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/presence/phones"))).toBe(true));
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/presence/phones"))!.init.body))).toEqual({ added: ["Dom's iPhone", "Guest Pixel"] });
    await user.click(screen.getByRole("button", { name: "Stop counting Dom's iPhone" }));
    await vi.waitFor(() => expect(calls.filter((c) => c.url.endsWith("/presence/phones")).length).toBe(2));
    expect(JSON.parse(String(calls.filter((c) => c.url.endsWith("/presence/phones"))[1].init.body))).toEqual({ added: [] });
  });
});
