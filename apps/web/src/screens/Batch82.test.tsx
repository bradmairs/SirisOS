import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { ProjectScreen, ProjectsScreen } from "./Projects";
import { ReceiptView } from "./ReceiptView";

afterEach(() => { clearResources(); vi.restoreAllMocks(); window.sessionStorage.clear(); });

describe("Projects (8.2)", () => {
  it("creates a project in Siris and opens it", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/siris-projects/Kitchen": () => jsonResponse({ title: "Kitchen", status: "active", areas: [], about: "", links: [], backlinks: [], tasks: [], meetings: [], deadline: null }),
      "/api/v1/siris-projects": (url, init) => init?.method === "POST" ? jsonResponse({ title: "Kitchen" }) : jsonResponse({ projects: [], available: true }),
    });
    render(<MemoryRouter initialEntries={["/projects"]}><Routes><Route path="/projects" element={<ProjectsScreen />} /><Route path="/projects/:title" element={<p>Opened</p>} /></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: /New project/ }));
    await userEvent.type(screen.getByLabelText("Name"), "Kitchen");
    await userEvent.click(screen.getByRole("button", { name: "Create in Siris" }));
    expect(await screen.findByText("Opened")).toBeInTheDocument();
    expect(calls.find((c) => c.init.method === "POST")?.init.body).toContain('"title":"Kitchen"');
  });

  it("says when the name's taken", async () => {
    signIn();
    mockFetch({ "/api/v1/siris-projects": (url, init) => init?.method === "POST" ? jsonResponse({ detail: "Siris already has a note called 'Kitchen'." }, 409) : jsonResponse({ projects: [], available: true }) });
    render(<MemoryRouter><ProjectsScreen /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: /New project/ }));
    await userEvent.type(screen.getByLabelText("Name"), "Kitchen");
    await userEvent.click(screen.getByRole("button", { name: "Create in Siris" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/already has a note/);
  });

  it("deletes after asking, and offers to undo", async () => {
    signIn();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const calls = mockFetch({
      "/api/v1/siris-projects/Kitchen/restore": () => jsonResponse({ action: "restore" }),
      "/api/v1/siris-projects/Kitchen": (url, init) => init?.method === "DELETE" ? jsonResponse({ action: "delete" })
        : jsonResponse({ title: "Kitchen", status: "active", aliases: [], path: null, names: ["Kitchen"], about: "", areas: [], source: null, updated: null, links: [], backlinks: [],
          deadline: null, days_idle: null, tasks: [], meetings: { upcoming: [], recent: [] }, guest_mode: false, unavailable: [] }),
      "/api/v1/siris-projects": () => jsonResponse({ projects: [], available: true }),
    });
    render(<MemoryRouter initialEntries={["/projects/Kitchen"]}><Routes><Route path="/projects" element={<ProjectsScreen />} /><Route path="/projects/:title" element={<ProjectScreen />} /></Routes></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: /Delete project/ }));
    expect(await screen.findByText(/Deleted "Kitchen"/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/Kitchen/restore"))).toBe(true));
  });
});

describe("A receipt shows the receipt itself (8.2)", () => {
  it("puts the invoice first and the email behind it", async () => {
    signIn();
    URL.createObjectURL = () => "blob:x";
    URL.revokeObjectURL = () => undefined;
    mockFetch({
      "/api/v1/life/documents/9/files/INV.pdf": () => new Response("pdf", { headers: { "content-type": "application/pdf" } }),
      "/api/v1/life/documents/9/files/email.html": () => new Response("<p>Invoice attached</p>", { headers: { "content-type": "text/html" } }),
      "/api/v1/life/documents/9": () => jsonResponse({ id: 9, title: "Bunnings", summary: "Bunnings, 8 Jan 2026", files: ["INV.pdf", "email.html"], receipt_file: "INV.pdf", due: [], kind: "receipt" }),
    });
    render(<ReceiptView id={9} />);
    expect(await screen.findByTitle("Receipt: Bunnings")).toHaveAttribute("src", "blob:x");
    expect(screen.getByRole("link", { name: "Open INV.pdf" })).toBeInTheDocument();
    expect(screen.getByText("The email it came with")).toBeInTheDocument();
    expect(screen.getByTitle("Email: Bunnings")).toHaveAttribute("sandbox", "");
  });
});
