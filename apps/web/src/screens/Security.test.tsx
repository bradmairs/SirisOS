import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { SecurityScreen } from "./Security";
import { Login } from "./Login";

const buf = (s: string) => new TextEncoder().encode(s).buffer;

function stubWebAuthn(hostname = "sirisos.home") {
  vi.stubGlobal("PublicKeyCredential", function PublicKeyCredential() {});
  vi.stubGlobal("isSecureContext", true);
  vi.spyOn(window, "location", "get").mockReturnValue({ ...window.location, hostname } as Location);
  const create = vi.fn(async () => ({ id: "cred1", response: { clientDataJSON: buf("{}"), attestationObject: buf("att") } }));
  const get = vi.fn(async () => ({ id: "cred1", response: { clientDataJSON: buf("{}"), authenticatorData: buf("auth"), signature: buf("sig"), userHandle: buf("brad") } }));
  Object.defineProperty(navigator, "credentials", { configurable: true, value: { create, get } });
  return { create, get };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("passkeys", () => {
  it("adds a passkey with Face ID and lists the settings check", async () => {
    signIn();
    const { create } = stubWebAuthn();
    const calls = mockFetch({
      "/api/v1/auth/passkeys/register/options": () => jsonResponse({ challenge: "Y2hhbGxlbmdl", rp: { id: "sirisos.home", name: "SirisOS" }, user: { id: "YnJhZA", name: "brad", displayName: "Brad" },
        pubKeyCredParams: [{ type: "public-key", alg: -7 }], authenticatorSelection: { residentKey: "required", userVerification: "required" }, attestation: "none", excludeCredentials: [], timeout: 300000 }),
      "/api/v1/auth/passkeys/register": () => jsonResponse({ id: "cred1", label: "iPhone", rp_id: "sirisos.home", created_at: "2026-10-17T00:00:00Z", last_used: null }),
      "/api/v1/auth/passkeys": () => jsonResponse({ passkeys: [] }),
      "/api/v1/security": () => jsonResponse({ passkeys: 0, checks: [{ level: "critical", title: "Sign-in secret is a default or too short", fix: "Set SIRISOS_JWT_SECRET." }] }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><SecurityScreen /></MemoryRouter>);
    expect(await screen.findByText("Sign-in secret is a default or too short")).toBeInTheDocument();
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
    const card = screen.getByRole("region", { name: "Passkeys" });
    await user.clear(within(card).getByLabelText("Passkey name"));
    await user.type(within(card).getByLabelText("Passkey name"), "iPhone");
    await user.click(within(card).getByRole("button", { name: /Add a passkey/ }));
    expect(await within(card).findByText(/Added “iPhone”/)).toBeInTheDocument();
    expect(create).toHaveBeenCalled();
    const sent = JSON.parse(String(calls.find((c) => c.url === "/api/v1/auth/passkeys/register")!.init.body));
    expect(sent).toMatchObject({ challenge: "Y2hhbGxlbmdl", id: "cred1", label: "iPhone", response: { attestationObject: "YXR0" } });
  });

  it("explains that a bare IP address can't use passkeys", async () => {
    signIn();
    stubWebAuthn("192.168.0.100");
    mockFetch({ "/api/v1/auth/passkeys": () => jsonResponse({ passkeys: [] }), "/api/v1/security": () => jsonResponse({ passkeys: 0, checks: [] }) });
    render(<MemoryRouter><SecurityScreen /></MemoryRouter>);
    expect(await screen.findByText(/not an IP address/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Add a passkey/ })).not.toBeInTheDocument();
  });

  it("signs in with a passkey", async () => {
    const { get } = stubWebAuthn();
    mockFetch({
      "/api/v1/auth/passkeys/login/options": () => jsonResponse({ challenge: "Y2hhbGxlbmdl", rpId: "sirisos.home", userVerification: "required", timeout: 300000 }),
      "/api/v1/auth/passkeys/login": () => jsonResponse({ access_token: "jwt", token_type: "bearer", expires_in: 86400, username: "brad" }),
    });
    const user = userEvent.setup();
    let who = "";
    render(<Login onLogin={(u) => (who = u)} />);
    await user.click(screen.getByRole("button", { name: /Sign in with a passkey/ }));
    await vi.waitFor(() => expect(who).toBe("brad"));
    expect(get).toHaveBeenCalled();
    expect(localStorage.getItem("sirisos.token")).toBe("jwt");
  });
});
