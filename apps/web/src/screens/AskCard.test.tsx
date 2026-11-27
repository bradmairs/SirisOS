import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { AskCard } from "./AskCard";

afterEach(() => { clearResources(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("SirisOS 11.16: Ask Siris", () => {
  it("shows the key once, with the Shortcut's address", async () => {
    signIn();
    mockFetch({ "/api/v1/ask/key": (_url, init) => jsonResponse(init?.method === "POST" ? { key: "sa_test", url: "/api/v1/ask" } : { on: false, made: null }) });
    const user = userEvent.setup();
    render(<MemoryRouter><AskCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Ask Siris" });
    expect(within(card).getByText(/never approve anything/)).toBeInTheDocument();
    expect(within(card).getByText(`${window.location.origin}/api/v1/ask`)).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Make a key" }));
    expect(await within(card).findByLabelText("Ask key")).toHaveTextContent("sa_test");
  });
});
