import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { ReviewCard } from "./ReviewCard";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

const QUEUE = [
  { title: "Plex", path: "Notes/Plex.md", links: 23, as_of: "2026-11-20", excerpt: "Media server.", card: "Plex (status: running) — Runs in Docker on the home server." },
  { title: "Home Server", path: "Notes/Home Server.md", links: 40, as_of: "2026-11-19", excerpt: "Linux box.", card: "Home Server — Linux server at 192.168.0.100." },
];

describe("Is this right? (11.6.0)", () => {
  it("marks a note right, skips one, and fixes one by editing it", async () => {
    signIn();
    const marked: string[] = [];
    const edits: string[] = [];
    mockFetch({
      // mockFetch matches by prefix: the longer path first.
      "/api/v1/brain/reviewed": (_url, init) => { marked.push(JSON.parse(String(init.body)).title); return jsonResponse({ reviewed: true, title: "x" }); },
      "/api/v1/brain/review": () => jsonResponse(QUEUE),
      "/api/v1/brain/note": () => jsonResponse({ title: "Home Server", path: "x", links: [], backlinks: [], body: "Linux server at 192.168.0.100.", version: "v1" }),
      "/api/v1/brain/edit": (_url, init) => { edits.push(JSON.parse(String(init.body)).body); return jsonResponse({ action: "edited", title: "Home Server", path: "x", links_added: [], version: "v2" }); },
    });
    render(<ReviewCard />);
    expect(await screen.findByText("Plex")).toBeInTheDocument();
    expect(screen.getByText("Runs in Docker on the home server.")).toBeInTheDocument();
    expect(screen.getByText("status: running")).toBeInTheDocument();
    expect(screen.getByText(/2 left this week/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Not now" }));
    expect(await screen.findByText("Home Server")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fix it" }));
    const box = await screen.findByLabelText("Text of Home Server");
    await userEvent.clear(box);
    await userEvent.type(box, "Linux server at 192.168.0.100 with 32 GB RAM.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Thanks: 1 checked.");
    expect(edits).toEqual(["Linux server at 192.168.0.100 with 32 GB RAM."]);
    expect(marked).toEqual(["Home Server"]);   // a fix counts as checking it; Plex was only skipped
  });

  it("stays hidden with nothing to check or no SirisAI", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/brain/review": () => jsonResponse({ detail: "offline" }, 503) });
    const { container } = render(<ReviewCard />);
    await vi.waitFor(() => expect(calls.length).toBeGreaterThan(0));
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
