import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { ShortcutsScreen } from "./Shortcuts";

describe("<ShortcutsScreen />", () => {
  it("makes a key with chosen actions, shows it once in the recipes, and revokes it", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/shortcuts/keys/k1": () => jsonResponse({ revoked: true }),
      "/api/v1/shortcuts/keys": (_u, init) =>
        init?.method === "POST"
          ? jsonResponse({ id: "k1", label: "Brad's iPhone", scopes: ["capture", "ask", "today", "protocols"], created_at: "", last_used: null, secret: "sk_abc123" })
          : jsonResponse({ keys: [], scopes: ["capture", "ask", "today", "protocols"] }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><ShortcutsScreen /></MemoryRouter>);
    const links = await screen.findByRole("region", { name: "Open SirisOS right where you want" });
    expect(within(links).getByText(`${window.location.origin}/capture`)).toBeInTheDocument();

    const keys = screen.getByRole("region", { name: "Shortcut keys" });
    await user.clear(within(keys).getByLabelText("Key name"));
    await user.type(within(keys).getByLabelText("Key name"), "Brad's iPhone");
    await user.click(within(keys).getByLabelText("Run protocols (Wind Down, Lockdown…)"));
    await user.click(within(keys).getByRole("button", { name: /New key/ }));
    expect(await within(keys).findByText("sk_abc123")).toBeInTheDocument();
    const body = JSON.parse(String(calls.find((c) => c.init.method === "POST")!.init.body));
    expect(body).toEqual({ label: "Brad's iPhone", scopes: ["capture", "ask", "today", "protocols"] });
    expect(screen.getByRole("region", { name: "Ready-made Shortcuts" })).toHaveTextContent("Authorization: Bearer sk_abc123");

    await user.click(within(keys).getByRole("button", { name: "Revoke Brad's iPhone" }));
    expect(within(keys).queryByRole("button", { name: "Revoke Brad's iPhone" })).not.toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/shortcuts/keys/k1" && c.init.method === "DELETE")).toBe(true);
  });
});
