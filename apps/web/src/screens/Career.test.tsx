import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Career as CareerData } from "../api/career";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { Career } from "./Career";

const steps = (titles: string[]) => titles.map((t, i) => ({ id: `s${i}`, title: t, detail: "", status: "todo" as const, note: "", done_on: null }));

function data(): CareerData {
  return {
    document: {
      profile: { discipline: "Civil", area_of_practice: "Water infrastructure", brain_notes: ["CPEng Chartership"] },
      pathways: [{ id: "cpeng", name: "Chartered Professional Engineer (CPEng)", body: "Engineers Australia", url: "https://ea.example", summary: "All 16 elements.", steps: steps(["Self-assess against the 16 elements", "Collect evidence"]) }],
      elements: [
        { id: "1", unit: "Personal commitment", title: "Deal with ethical issues" },
        { id: "6", unit: "Obligation to community", title: "Identify, assess and manage risks" },
      ],
      evidence: [],
      goals: [],
      cpd: {
        records: [
          { id: "r1", date: "2026-06-12", title: "Ozwater 2026", provider: "AWA", type: "Conference", hours: 14, split: { risk: 2, business: 3, area: 9 }, basis: "export", notes: "" },
          { id: "r2", date: "2026-03-01", title: "Toastmasters", provider: "", type: "", hours: 1, split: { other: 1 }, basis: "guess", notes: "" },
        ],
        imports: [{ at: "2026-10-09T00:00:00+00:00", filename: "ea.csv", added: 2, updated: 0, unchanged: 0 }],
        overrides: {},
      },
      updated_at: null,
    },
    overview: {
      cpd: {
        window: { from: "2023-10-10", to: "2026-10-10", years: 3 }, total: 15, required: 150, short: 135, met: false,
        categories: { area: 9, risk: 2, business: 3, other: 1 },
        minimums: [
          { category: "area", label: "Area of practice", hours: 9, minimum: 50, short: 41 },
          { category: "risk", label: "Risk management", hours: 2, minimum: 10, short: 8 },
          { category: "business", label: "Business & management", hours: 3, minimum: 15, short: 12 },
        ],
        by_year: { "2026": 15 }, expiring_90_days: 0, guessed: 1, records: 2,
        last_import: { at: "2026-10-09T00:00:00+00:00", filename: "ea.csv", added: 2, updated: 0, unchanged: 0 }, latest_activity: "2026-06-12",
      },
      pathways: [{ id: "cpeng", name: "Chartered Professional Engineer (CPEng)", done: 0, total: 2, next: { id: "s0", title: "Self-assess against the 16 elements", status: "todo" } }],
      competencies: { total: 2, evidenced: 0, counts: { "1": 0, "6": 0 }, gaps: [] },
      goals: [],
      next_steps: [
        { title: "Self-assess against the 16 elements", detail: "Chartered Professional Engineer (CPEng)", kind: "pathway" },
        { title: "8 more hours of risk management CPD", detail: "CPD minimum", kind: "cpd" },
      ],
      categories: { area: "Area of practice", risk: "Risk management", business: "Business & management", other: "Other" },
    },
  };
}

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Career />
    </MemoryRouter>,
  );
}

describe("<Career />", () => {
  it("shows CPD against the requirement, next steps and the brain notes", async () => {
    signIn();
    mockFetch({ "/api/v1/career": () => jsonResponse(data()) });
    renderAt("/career");
    const cpd = await screen.findByRole("region", { name: "CPD" });
    expect(within(cpd).getByText("15")).toBeInTheDocument();
    expect(within(cpd).getByText("2/10")).toBeInTheDocument(); // risk management
    expect(within(cpd).getByText(/From Engineers Australia, imported/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Next steps" })).getByText("8 more hours of risk management CPD")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CPEng Chartership" })).toHaveAttribute("href", "/brain?q=CPEng%20Chartership");
  });

  it("imports an Engineers Australia export and lets a guessed category be corrected", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/career/cpd/import": () => jsonResponse({ ...data(), import: { at: "", filename: "ea.csv", added: 0, updated: 1, unchanged: 1 } }),
      "/api/v1/career/cpd/r2/category": () => jsonResponse(data()),
      "/api/v1/career": () => jsonResponse(data()),
    });
    const user = userEvent.setup();
    renderAt("/career?view=cpd");
    await screen.findByText("2 activities");
    await user.upload(screen.getByLabelText("CPD export file"), new File(["Date,Title,Hours"], "ea.csv", { type: "text/csv" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Imported ea.csv: 0 new, 1 updated, 1 already here.");
    const upload = calls.find((c) => c.url === "/api/v1/career/cpd/import")!;
    expect(upload.init.body).toBeInstanceOf(FormData);

    // The export split Ozwater itself; Toastmasters was a guess and can be changed.
    expect(screen.getByText("Risk 2 · Business 3 · Area 9")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Category for Toastmasters"), "business");
    await waitFor(() => expect(calls.some((c) => c.url === "/api/v1/career/cpd/r2/category")).toBe(true));
    const put = calls.find((c) => c.url === "/api/v1/career/cpd/r2/category")!;
    expect(JSON.parse(put.init.body as string)).toEqual({ category: "business" });
  });

  it("ticks off pathway steps and saves the whole edit", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/career": (_url, init) => jsonResponse(init.method === "PUT" ? { ...data(), document: { ...data().document, ...JSON.parse(init.body as string) } } : data()) });
    const user = userEvent.setup();
    renderAt("/career?view=pathways");
    await user.click(await screen.findByRole("button", { name: "Self-assess against the 16 elements: To do. Change status" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PUT")).toBe(true));
    const sent = JSON.parse(calls.find((c) => c.init.method === "PUT")!.init.body as string);
    expect(sent.pathways[0].steps[0].status).toBe("doing");
    expect(Object.keys(sent).sort()).toEqual(["evidence", "goals", "pathways", "profile"]); // never CPD
    expect(await screen.findByRole("button", { name: /In progress/ })).toBeInTheDocument();
  });

  it("adds evidence tagged with competency elements and a Second Brain link", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/career": (_url, init) => jsonResponse(init.method === "PUT" ? { ...data(), document: { ...data().document, ...JSON.parse(init.body as string) } } : data()) });
    const user = userEvent.setup();
    renderAt("/career?view=competencies");
    expect(await screen.findAllByText("No evidence yet")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Evidence" }));
    const sheet = screen.getByRole("dialog", { name: "Add evidence" });
    await user.type(within(sheet).getByLabelText("Title"), "Pump station risk workshop");
    await user.click(within(sheet).getByRole("button", { name: "6. Identify, assess and manage risks" }));
    await user.type(within(sheet).getByLabelText("Add a link"), "Pump Station 4 upgrade{Enter}");
    expect(within(sheet).getByRole("link", { name: "Pump Station 4 upgrade" })).toHaveAttribute("href", "/brain?q=Pump%20Station%204%20upgrade");
    await user.click(within(sheet).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PUT")).toBe(true));
    const sent = JSON.parse(calls.find((c) => c.init.method === "PUT")!.init.body as string);
    expect(sent.evidence[0]).toMatchObject({ title: "Pump station risk workshop", elements: ["6"], links: [{ label: "Pump Station 4 upgrade", url: "/brain?q=Pump%20Station%204%20upgrade" }] });
    expect(await screen.findByRole("button", { name: "Pump station risk workshop" })).toBeInTheDocument();
  });

  it("adds a goal with a target date and next step", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/career": (_url, init) => jsonResponse(init.method === "PUT" ? { ...data(), document: { ...data().document, ...JSON.parse(init.body as string) } } : data()) });
    const user = userEvent.setup();
    renderAt("/career?view=goals");
    await user.type(await screen.findByLabelText("Goal"), "Chartered by mid 2027");
    await user.type(screen.getByLabelText("Next step"), "Draft element 6");
    await user.click(screen.getByRole("button", { name: "Add goal" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PUT")).toBe(true));
    const sent = JSON.parse(calls.find((c) => c.init.method === "PUT")!.init.body as string);
    expect(sent.goals[0]).toMatchObject({ title: "Chartered by mid 2027", next_step: "Draft element 6", status: "active" });
  });
});
