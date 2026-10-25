import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ProtocolsManager, describeStep } from "./ProtocolEditor";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import type { ProtocolCatalogue } from "../api/types";

// SirisAI's own example (ADR 110), shared with the backend tests.
const CATALOGUE = JSON.parse(readFileSync(resolve(process.cwd(), "../backend/tests/contracts/sirisai-hub-v1/protocols.json"), "utf8")) as ProtocolCatalogue;

function withEntities(over: Partial<ProtocolCatalogue> = {}): ProtocolCatalogue {
  return {
    ...CATALOGUE,
    entities: [{ entity_id: "light.lounge", name: "Lounge lamp", domain: "light" }, { entity_id: "cover.lounge_blind", name: "Lounge blind", domain: "cover", device_class: "blind" }],
    ...over,
  };
}

function setup(cat = withEntities(), save: (body: unknown) => Response = (b) => jsonResponse({ name: "x", ...(b as object) })) {
  signIn();
  clearResources();
  const calls = mockFetch({
    "/api/v1/assistant/protocols/": (_u, init) => (init.method === "DELETE" ? jsonResponse({ name: "away", deleted: true, restored_builtin: true }) : save(JSON.parse(String(init.body)))),
    "/api/v1/assistant/protocols": () => jsonResponse(cat),
  });
  render(<MemoryRouter><ProtocolsManager /></MemoryRouter>);
  return calls;
}

describe("<ProtocolsManager />", () => {
  it("lists every protocol, and changes a built-in's step into your version", async () => {
    const user = userEvent.setup();
    const calls = setup();
    const card = await screen.findByRole("region", { name: "Protocols" });
    expect(card).toHaveTextContent("Lock down");
    expect(within(card).getAllByText("Built-in").length).toBeGreaterThan(1);

    await user.click(within(card).getByRole("button", { name: "Edit Away" }));
    const sheet = await screen.findByRole("dialog", { name: "Edit Away" });
    expect(within(sheet).getByText(/Saving makes this your version/)).toBeInTheDocument();
    await user.selectOptions(within(sheet).getByLabelText("Step 1: when"), "nobody_home");
    await user.click(within(sheet).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PUT")).toBe(true));
    const put = calls.find((c) => c.init.method === "PUT")!;
    expect(put.url).toBe("/api/v1/assistant/protocols/away");
    const body = JSON.parse(String(put.init.body));
    expect(body.steps[0]).toMatchObject({ tool: "home_assistant_call_service", when: "nobody_home", arguments: { domain: "light", service: "turn_off", entity_id: "all" } });
    expect(body.steps).toHaveLength(CATALOGUE.protocols.find((p) => p.name === "away")!.steps.length);
    expect(await within(card).findByText("Saved Away.")).toBeInTheDocument();
  });

  it("makes a new protocol from device, notification and guest steps", async () => {
    const user = userEvent.setup();
    const calls = setup();
    await user.click(await screen.findByRole("button", { name: /New protocol/ }));
    const sheet = await screen.findByRole("dialog", { name: "New protocol" });
    await user.type(within(sheet).getByLabelText("Protocol name"), "Movie night");
    await user.type(within(sheet).getByLabelText("What it's for"), "Film time");
    await user.selectOptions(within(sheet).getByLabelText("Step 1: which"), "light.lounge");
    await user.type(within(sheet).getByLabelText("Step 1: brightness"), "20");
    await user.selectOptions(within(sheet).getByLabelText("Step 1: when"), "night");

    await user.click(within(sheet).getByRole("button", { name: /Add a step/ }));
    await user.selectOptions(within(sheet).getByLabelText("Step 2: device type"), "cover");
    await user.selectOptions(within(sheet).getByLabelText("Step 2: action"), "close_cover");
    await user.selectOptions(within(sheet).getByLabelText("Step 2: which"), "cover.lounge_blind");

    await user.click(within(sheet).getByRole("button", { name: /Add a step/ }));
    await user.selectOptions(within(sheet).getByLabelText("Step 3: kind"), "notify");
    await user.type(within(sheet).getByLabelText("Step 3: message"), "Enjoy the film");
    await user.click(within(sheet).getByRole("button", { name: "Move step 3 up" }));

    await user.click(within(sheet).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PUT")).toBe(true));
    const put = calls.find((c) => c.init.method === "PUT")!;
    expect(put.url).toBe("/api/v1/assistant/protocols/movie_night");
    expect(JSON.parse(String(put.init.body))).toEqual({
      description: "Film time",
      steps: [
        { tool: "home_assistant_call_service", when: "night", arguments: { domain: "light", service: "turn_on", entity_id: "light.lounge", service_data: { brightness_pct: 20 } } },
        { tool: "notify", arguments: { message: "Enjoy the film", title: "" } },
        { tool: "home_assistant_call_service", arguments: { domain: "cover", service: "close_cover", entity_id: "cover.lounge_blind" } },
      ],
    });
  });

  it("shows SirisAI's reason when it won't save, and won't reuse a name", async () => {
    const user = userEvent.setup();
    setup(withEntities(), () => jsonResponse({ detail: "SirisAI: brightness pct is 1 to 100." }, 422));
    await user.click(await screen.findByRole("button", { name: /New protocol/ }));
    const sheet = await screen.findByRole("dialog", { name: "New protocol" });
    await user.type(within(sheet).getByLabelText("Protocol name"), "Lockdown");
    await user.click(within(sheet).getByRole("button", { name: "Save" }));
    expect(within(sheet).getByRole("alert")).toHaveTextContent("already a protocol called Lock down");
    await user.clear(within(sheet).getByLabelText("Protocol name"));
    await user.type(within(sheet).getByLabelText("Protocol name"), "Bedtime");
    await user.click(within(sheet).getByRole("button", { name: "Save" }));
    expect(await within(sheet).findByRole("alert")).toHaveTextContent("brightness pct is 1 to 100.");
  });

  it("takes your version of a built-in back to the original, after asking, and keeps steps made in chat", async () => {
    const user = userEvent.setup();
    const away = CATALOGUE.protocols.find((p) => p.name === "away")!;
    const mine = { ...away, builtin: false, customised: true,
      steps: [{ tool: "docker_restart_container", arguments: { container: "plex" }, label: null, when: null, undo: null }, ...away.steps] };
    const calls = setup(withEntities({ protocols: [mine] }));
    const card = await screen.findByRole("region", { name: "Protocols" });
    expect(within(card).getByText("Your version")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Edit Away" }));
    const sheet = await screen.findByRole("dialog", { name: "Edit Away" });
    expect(within(sheet).getByText(/Made in chat \(docker restart container\)/)).toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: /Back to built-in/ }));
    await user.click(within(sheet).getByRole("button", { name: "Yes, go back" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "DELETE" && c.url === "/api/v1/assistant/protocols/away")).toBe(true));
    expect(await within(card).findByText("Away is back to the built-in version.")).toBeInTheDocument();
  });

  it("says what a step does", () => {
    const cat = withEntities();
    expect(describeStep({ tool: "home_assistant_call_service", arguments: { domain: "cover", service: "close_cover", entity_id: { select: { domain: "cover", device_class: ["garage"] } } } }, cat)).toBe("Close garage doors and gates");
    expect(describeStep({ tool: "home_assistant_call_service", arguments: { domain: "light", service: "turn_on", entity_id: "light.lounge" } }, cat)).toBe("Turn on Lounge lamp");
    expect(describeStep({ tool: "set_guest_mode", arguments: { on: true, hours: 12 } })).toBe("Guest mode on for 12 h");
  });
});
