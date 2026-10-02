import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Engineering } from "../Engineering";
import { jsonResponse, mockFetch, signIn } from "../../test/helpers";

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/engineering/*" element={<Engineering />} />
      </Routes>
    </MemoryRouter>,
  );
}

const doc = {
  id: "s1", title: "Sewerage Design Guide", authority: "Melbourne Water", reference: "MWD-01", edition: "2024", filename: "a.pdf",
  uploaded_at: "", pages: 80, indexed: true, extraction_method: "native", ocr_attempted: false, ocr_error: null, active: true,
  archived_at: null, supersedes_id: null, superseded_by_id: null, revision: 1,
};

describe("engineering", () => {
  it("lists the native tools on the engineering home", async () => {
    signIn();
    mockFetch({ "/api/v1/hub/apps": () => jsonResponse({ apps: [] }) });
    at("/engineering");
    for (const name of ["SirisHydro", "Calculators", "Standards", "Projects"]) {
      expect(screen.getByRole("link", { name: new RegExp(name) })).toBeInTheDocument();
    }
  });

  it("asks SirisHydro and shows the answer with cited evidence", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/engineering/sirishydro/history": () => jsonResponse({ history: [] }),
      "/api/v1/engineering/sirishydro/evidence": () =>
        jsonResponse({
          question: "minimum cover", sufficient_evidence: true, context_text: "", guidance: "Evidence found using local hybrid retrieval.", retrieval_strategy: "hybrid",
          synthesized_answer: "Minimum cover is 600 mm in road reserves [MWD-01 p.12].",
          evidence: [{ document_id: "s1", title: "Sewerage Design Guide", authority: "Melbourne Water", reference: "MWD-01", edition: "2024", page: 12, citation: "MWD-01 · p.12", excerpt: "Cover shall be not less than 600 mm", score: 9 }],
        }),
      "/api/v1/engineering/standards/s1/pages/12": () => jsonResponse({ document: doc, page: 12, text: "Full page text", citation: "MWD-01 · p.12" }),
    });
    const user = userEvent.setup();
    at("/engineering/hydro");
    await user.type(screen.getByLabelText("Engineering question"), "minimum cover");
    await user.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/600 mm in road reserves/)).toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("question=minimum+cover"))).toBe(true);
    await user.click(screen.getByRole("button", { name: "View page 12" }));
    expect(await screen.findByText("Full page text")).toBeInTheDocument();
  });

  it("computes live and saves a calculation with Flutter-compatible inputs", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/engineering/calculations": () => jsonResponse({ id: "c1" }, 201) });
    const user = userEvent.setup();
    at("/engineering/calculators/fullPipe");
    const results = screen.getByRole("region", { name: "Results" });
    expect(within(results).getByText("202 L/s")).toBeInTheDocument();

    const d = screen.getByLabelText("Internal diameter (m)");
    await user.clear(d);
    await user.type(d, "0.6");
    expect(within(results).getByText("434 L/s")).toBeInTheDocument();

    await user.clear(d);
    await user.type(d, "x");
    expect(within(results).getByText(/must be a number/)).toBeInTheDocument();
    await user.clear(d);
    await user.type(d, "0.45");

    await user.click(screen.getByRole("button", { name: /save calculation/i }));
    const sheet = await screen.findByRole("dialog", { name: "Save calculation" });
    await user.clear(within(sheet).getByLabelText("Title"));
    await user.type(within(sheet).getByLabelText("Title"), "Trunk main check");
    await user.click(within(sheet).getByRole("button", { name: "Save" }));
    await screen.findByText(/Saved “Trunk main check”/);
    const body = JSON.parse(calls.find((c) => c.init.method === "POST")!.init.body as string);
    expect(body).toMatchObject({
      calculator_id: "fullPipe",
      title: "Trunk main check",
      inputs: { "Internal diameter (m)": 0.45, "Manning n": 0.013, "Hydraulic grade (m/m)": 0.005 },
      cited_standard_id: null,
    });
    expect(body.results[1]).toEqual({ label: "Flow", value: "202 L/s" });
  });

  it("searches standards and archives one", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/engineering/standards/s1": () => jsonResponse({ ...doc, active: false }),
      "/api/v1/engineering/standards": () => jsonResponse({ query: "", hits: [{ document: doc, page: null, snippet: null, score: null, citation: null }] }),
    });
    const user = userEvent.setup();
    at("/engineering/standards");
    expect(await screen.findByText("Sewerage Design Guide")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Archive Sewerage Design Guide" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "DELETE" && c.url.endsWith("/standards/s1"))).toBe(true));
  });

  it("links a saved calculation to a project", async () => {
    signIn();
    const project = { id: "p1", name: "Bendigo PS", description: "", kind: "engineering", status: "active", tags: [], created_at: "", updated_at: "" };
    const calc = { id: "c1", calculator_id: "fullPipe", title: "Trunk main check", inputs: {}, results: [{ label: "Flow", value: "202 L/s" }], notes: "", cited_standard_id: null, cited_standard_label: null, created_at: "2026-10-01T00:00:00Z" };
    const calls = mockFetch({
      "/api/v1/projects/current": () => jsonResponse({ project: null, selected_at: null }),
      "/api/v1/projects/p1/relationships": (_u, init) =>
        init.method === "POST" ? jsonResponse({ id: "r1" }, 201) : jsonResponse({ project_id: "p1", relationships: [] }),
      "/api/v1/projects/p1": () => jsonResponse(project),
      "/api/v1/engineering/calculations": () => jsonResponse({ calculations: [calc] }),
    });
    const user = userEvent.setup();
    at("/engineering/projects/p1");
    expect(await screen.findByRole("heading", { name: "Bendigo PS" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /link/i }));
    await user.click(await screen.findByRole("button", { name: /Trunk main check/ }));
    await waitFor(() => {
      const post = calls.find((c) => c.init.method === "POST");
      expect(post && JSON.parse(post.init.body as string)).toEqual({ target_type: "calculation", target_id: "c1", kind: "contains" });
    });
  });
});
