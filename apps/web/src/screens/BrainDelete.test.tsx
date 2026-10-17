import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Brain } from "./Brain";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import type { BrainDeleted, SirisMemory } from "../api/types";

const HIT = { title: "Old Router", path: "Notes/Old Router.md", type: "note", excerpts: ["A Netgear box"] };
const MEMORY: SirisMemory = { id: 7, position: 1, content: "Brad prefers metric units", created_at: "2026-10-01T09:00:00", recall_count: 2, last_recalled_at: null };

/** A fake SirisOS API for the Brain screen. `state` is shared so a delete shows up in later reads. */
function fakeBrain(opts: { refuse?: string } = {}) {
  const state = { deleted: [] as BrainDeleted[], memories: [MEMORY] };
  const calls = mockFetch({
    "/api/v1/brain/search": () => jsonResponse(state.deleted.some((d) => d.title === HIT.title) ? [] : [HIT]),
    "/api/v1/brain/note": () => jsonResponse({ title: "Old Router", path: HIT.path, links: [], backlinks: ["Home Lab", "UniFi Network"] }),
    "/api/v1/brain/deleted": () => jsonResponse(state.deleted),
    "/api/v1/brain/delete": (_u, init) => {
      const { title, permanent } = JSON.parse(init.body as string);
      if (opts.refuse) return jsonResponse({ detail: opts.refuse }, 422);
      state.deleted = [{ title, type: "note", path: HIT.path, date: "2026-10-16", linked_from: ["Home Lab"], restorable: !permanent }];
      return jsonResponse({ action: "deleted", title, permanent, linked_from: ["Home Lab", "UniFi Network"] });
    },
    "/api/v1/brain/restore": (_u, init) => {
      const { title } = JSON.parse(init.body as string);
      state.deleted = state.deleted.filter((d) => d.title !== title);
      return jsonResponse({ action: "restored", title, relinked: ["Home Lab"] });
    },
    "/api/v1/brain/purge": (_u, init) => {
      const { title } = JSON.parse(init.body as string);
      state.deleted = state.deleted.filter((d) => d.title !== title);
      return jsonResponse({ action: "purged", title });
    },
    "/api/v1/brain/today": () => jsonResponse({ date: "2026-10-16", items: [{ title: "Old Router", action: "learned" }] }),
    "/api/v1/memories/": (_u, init) => {
      if (init.method === "DELETE") state.memories = [];
      return new Response(null, { status: 204 });
    },
    "/api/v1/memories": () => jsonResponse(state.memories),
  });
  return { state, calls };
}

/** The Delete button on the search result card (not the one in Learned today). */
async function deleteInResult() {
  const card = (await screen.findByText("A Netgear box")).closest(".widget") as HTMLElement;
  return within(card).getByRole("button", { name: "Delete Old Router" });
}

function renderBrain() {
  render(
    <MemoryRouter>
      <Brain />
    </MemoryRouter>,
  );
}

describe("Deleting from Siris", () => {
  it("deletes a note from search after a confirmation that says what will happen, then undoes it", async () => {
    signIn();
    const { calls } = fakeBrain();
    const user = userEvent.setup();
    renderBrain();
    await user.type(screen.getByPlaceholderText("Search your notes"), "router");
    await user.click(await deleteInResult());

    const sheet = await screen.findByRole("dialog", { name: "Delete Old Router" });
    expect(await within(sheet).findByText(/2 other notes link to it/)).toBeInTheDocument();
    expect(within(sheet).getByText(/restore it from Recently deleted/)).toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: /^Delete$/ }));

    expect(JSON.parse(calls.find((c) => c.url === "/api/v1/brain/delete")!.init.body as string)).toEqual({ title: "Old Router", permanent: false });
    expect(await screen.findByText("Deleted Old Router")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("A Netgear box")).not.toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /undo/i }));
    await waitFor(() => expect(calls.some((c) => c.url === "/api/v1/brain/restore")).toBe(true));
    expect(await screen.findByText("A Netgear box")).toBeInTheDocument();
    expect(screen.queryByText("Deleted Old Router")).not.toBeInTheDocument();
  });

  it("deletes permanently when asked, with no undo", async () => {
    signIn();
    const { calls } = fakeBrain();
    const user = userEvent.setup();
    renderBrain();
    await user.type(screen.getByPlaceholderText("Search your notes"), "router");
    await user.click(await deleteInResult());
    const sheet = await screen.findByRole("dialog");
    await user.click(within(sheet).getByRole("checkbox", { name: /delete permanently/i }));
    await user.click(within(sheet).getByRole("button", { name: "Delete permanently" }));
    expect(JSON.parse(calls.find((c) => c.url === "/api/v1/brain/delete")!.init.body as string).permanent).toBe(true);
    expect(await screen.findByText("Deleted Old Router permanently")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /undo/i })).not.toBeInTheDocument();
  });

  it("shows a refusal in the sheet and deletes nothing", async () => {
    signIn();
    fakeBrain({ refuse: "SirisAI: Health is one of the hubs the brain is organised around, so it can't be deleted" });
    const user = userEvent.setup();
    renderBrain();
    await user.type(screen.getByPlaceholderText("Search your notes"), "router");
    await user.click(await deleteInResult());
    const sheet = await screen.findByRole("dialog");
    await user.click(within(sheet).getByRole("button", { name: /^Delete$/ }));
    expect(await within(sheet).findByRole("alert")).toHaveTextContent("hubs the brain is organised around");
    expect(screen.getByText("A Netgear box")).toBeInTheDocument();
  });

  it("deletes from Learned today, which then stops listing it, and restores it from Recently deleted", async () => {
    signIn();
    const { calls } = fakeBrain();
    const user = userEvent.setup();
    renderBrain();
    const learned = (await screen.findByText("Learned today")).closest(".widget") as HTMLElement;
    await user.click(await within(learned).findByRole("button", { name: "Delete Old Router" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: /^Delete$/ }));

    await waitFor(() => expect(within(learned).queryByText("Old Router")).not.toBeInTheDocument());
    const bin = screen.getByRole("region", { name: "Manage" }).querySelector('[aria-label="Recently deleted"]') as HTMLElement;
    await user.click(await within(bin).findByRole("button", { name: "Restore Old Router" }));
    expect(await within(bin).findByText("Restored Old Router")).toBeInTheDocument();
    expect(calls.filter((c) => c.url === "/api/v1/brain/restore")).toHaveLength(1);
    expect(await within(learned).findByText("Old Router")).toBeInTheDocument();
  });

  it("deletes a note forever from Recently deleted, after a second tap", async () => {
    signIn();
    const { state, calls } = fakeBrain();
    state.deleted = [{ title: "Spare Pi", type: "note", path: "Notes/Spare Pi.md", date: "2026-10-15", linked_from: [], restorable: true }];
    const user = userEvent.setup();
    renderBrain();
    const bin = (await screen.findByText("Recently deleted")).closest(".widget") as HTMLElement;
    await user.click(await within(bin).findByRole("button", { name: "Delete Spare Pi forever" }));
    await user.click(within(bin).getByRole("button", { name: "Delete forever" }));
    expect(await within(bin).findByText("Deleted Spare Pi permanently")).toBeInTheDocument();
    expect(JSON.parse(calls.find((c) => c.url === "/api/v1/brain/purge")!.init.body as string)).toEqual({ title: "Spare Pi" });
  });

  it("lists SirisAI's memories and deletes one after confirming", async () => {
    signIn();
    const { calls } = fakeBrain();
    const user = userEvent.setup();
    renderBrain();
    const panel = (await screen.findByText("SirisAI's memories")).closest(".widget") as HTMLElement;
    expect(await within(panel).findByText("Brad prefers metric units")).toBeInTheDocument();
    expect(within(panel).getByText(/recalled 2 times/)).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Delete memory: Brad prefers metric units" }));
    await user.click(within(panel).getByRole("button", { name: "Delete" }));
    expect(await within(panel).findByText(/Deleted: “Brad prefers metric units”/)).toBeInTheDocument();
    const del = calls.find((c) => c.init.method === "DELETE")!;
    expect(del.url).toBe("/api/v1/memories/7");
    expect(within(panel).queryByText("Brad prefers metric units")).not.toBeInTheDocument();
  });
});
