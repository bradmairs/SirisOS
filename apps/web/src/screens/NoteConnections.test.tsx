import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NoteConnections } from "./NoteConnections";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

describe("<NoteConnections />", () => {
  it("lists a note's links both ways and unlinks one", async () => {
    signIn();
    let note = { title: "SirisOS", path: "01-Projects/SirisOS.md", links: ["Apple Health", "SirisAI"], backlinks: ["SirisAI", "Home Server"] };
    const calls = mockFetch({
      "/api/v1/brain/note": () => jsonResponse(note),
      "/api/v1/brain/unlink": (_u, init) => {
        note = { ...note, links: ["SirisAI"] };
        const { a, b } = JSON.parse(init.body as string);
        return jsonResponse({ action: "unlinked", a, b });
      },
    });
    const user = userEvent.setup();
    render(<NoteConnections title="SirisOS" />);

    await user.click(screen.getByRole("button", { name: "Connections" }));
    expect(await screen.findByText("Apple Health")).toBeInTheDocument();
    expect(screen.getAllByText(/SirisAI|Home Server/)).toHaveLength(2); // deduplicated across directions
    expect(calls[0].url).toBe("/api/v1/brain/note?title=SirisOS");

    await user.click(screen.getByRole("button", { name: "Unlink SirisOS and Apple Health" }));
    expect(await screen.findByText("Unlinked Apple Health")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unlink SirisOS and Apple Health" })).not.toBeInTheDocument();
  });
});
