import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Brain } from "./Brain";
import { readable } from "./NoteHit";
import { NoteBody } from "../components/NoteBody";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const HOME_LAB = {
  title: "Home Lab", path: "Notes/Home Lab.md", tags: ["home-lab", "network"], as_of: "2026-10-04",
  links: ["UniFi Network", "Synology NAS"], backlinks: ["Brad Mairs", "UniFi Network"],
  body: "# Home Lab\n\nThe **server** runs Docker on [[Home Server|the .100 box]].\n\n## Kit\n- UCG Ultra\n- [ ] Add a UPS\n- [x] Swap the switch\n\n## Connections\n- [[UniFi Network]]\n",
};
const UNIFI = { title: "UniFi Network", path: "Notes/UniFi Network.md", links: [], backlinks: ["Home Lab"], body: "Two U6+ access points.", tags: [], as_of: null };

function setup() {
  signIn();
  clearResources();
  const calls = mockFetch({
    "/api/v1/brain/search": (u) => {
      const q = new URL(u, "http://x").searchParams.get("q") ?? "";
      return jsonResponse(q.toLowerCase().startsWith("unifi")
        ? [{ title: "UniFi Network", path: UNIFI.path, type: "note", excerpts: ["Two U6+ access points."] }]
        : [{ title: "Home Lab", path: HOME_LAB.path, type: "note", excerpts: ["The server runs Docker"] }, { title: "Synology NAS", path: "Notes/Synology NAS.md", type: "note", excerpts: ["The NAS"] }]);
    },
    "/api/v1/brain/note": (u) => jsonResponse(new URL(u, "http://x").searchParams.get("title") === "UniFi Network" ? UNIFI : HOME_LAB),
    "/api/v1/brain/today": () => jsonResponse({ date: "2026-10-25", items: [] }),
    "/api/v1/brain/deleted": () => jsonResponse([]),
    "/api/v1/memories": () => jsonResponse([]),
  });
  render(<MemoryRouter><Brain /></MemoryRouter>);
  return calls;
}

describe("Searching your notes", () => {
  it("opens a result in place to read the whole note, and its links open those notes", async () => {
    const user = userEvent.setup();
    const calls = setup();
    await user.type(screen.getByPlaceholderText("Search your notes"), "server");
    const head = await screen.findByRole("button", { name: /Home Lab/, expanded: false });
    expect(head).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("The server runs Docker")).toBeInTheDocument();
    expect(calls.some((c) => c.url.startsWith("/api/v1/brain/note"))).toBe(false);   // fetched only when opened

    await user.click(head);
    expect(head).toHaveAttribute("aria-expanded", "true");
    const card = head.closest(".widget") as HTMLElement;
    expect(await within(card).findByText("server", { selector: "strong" })).toBeInTheDocument();
    expect(within(card).getByRole("checkbox", { name: "Done" })).toBeChecked();
    expect(within(card).getByText("Add a UPS")).toBeInTheDocument();
    expect(card.querySelector(".note-hit__meta")).toHaveTextContent(/^Updated .*2026 · #home-lab #network$/);
    expect(within(card).queryByRole("heading", { name: "Connections" })).not.toBeInTheDocument();   // shown as links instead
    const connected = within(card).getByLabelText("Connected notes");
    expect(within(connected).getAllByRole("button").map((b) => b.textContent)).toEqual(["Brad Mairs", "Synology NAS", "UniFi Network"]);

    await user.click(within(connected).getByRole("button", { name: "UniFi Network" }));
    expect(screen.getByPlaceholderText("Search your notes")).toHaveValue("UniFi Network");
    const unifi = await screen.findByRole("button", { name: /UniFi Network/, expanded: true });
    expect(await within(unifi.closest(".widget") as HTMLElement).findByText("Two U6+ access points.")).toBeInTheDocument();

    await user.click(unifi);
    await waitFor(() => expect(unifi).toHaveAttribute("aria-expanded", "false"));
  });

});

describe("<NoteBody />", () => {
  it("renders the note's Markdown as elements, never as HTML", () => {
    const opened: string[] = [];
    const { container } = render(<NoteBody onOpen={(t) => opened.push(t)} text={[
      "## Plan", "Some *notes* with `code` and a [site](https://example.com).", "", "1. First", "2. Second", "",
      "> Quoted", "", "| A | B |", "|---|---|", "| 1 | 2 |", "", "<script>alert(1)</script> ![[photo.jpg]]",
      "", "See [[Dom Mairs|Dom]].",
    ].join("\n")} />);
    expect(screen.getByRole("heading", { name: "Plan" })).toBeInTheDocument();
    expect(screen.getByText("notes", { selector: "em" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "site" })).toHaveAttribute("href", "https://example.com");
    expect(container.querySelectorAll("ol li")).toHaveLength(2);
    expect(container.querySelector("table td")?.textContent).toBe("1");
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
    expect(screen.getByText(/📎 photo.jpg/)).toBeInTheDocument();
    screen.getByRole("button", { name: "Dom" }).click();
    expect(opened).toEqual(["Dom Mairs"]);
  });

  it("drops the note's own title line and its Connections list", () => {
    expect(readable(HOME_LAB.body, "Home Lab")).toBe("The **server** runs Docker on [[Home Server|the .100 box]].\n\n## Kit\n- UCG Ultra\n- [ ] Add a UPS\n- [x] Swap the switch");
    expect(readable("# Something else\nText", "Home Lab")).toBe("# Something else\nText");
  });
});
