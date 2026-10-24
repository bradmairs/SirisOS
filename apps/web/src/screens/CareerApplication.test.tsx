import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import type { ApplicationView } from "../api/career";
import { ApplicationTab } from "./CareerApplication";

const blank = {
  area_of_practice: "", additional_area: "", additional_reason: "", cpd_evidence: null, cpd_answers: {},
  part1: {}, part2: {}, part3: {}, signed: false,
  bia: { required: null, state: null, cv: false, building_cpd: false, statement: "" }, files: {},
};

function view(app = blank): ApplicationView {
  return {
    application: app as ApplicationView["application"],
    documents: [
      { id: "cpd", title: "CPD questionnaire", form: "3 ASM TPL CPD Questionnaire v2.0", summary: "Evidence that you do CPD." },
      { id: "reflection", title: "Self-reflection on the chartered competencies", form: "v4.1", summary: "Parts 1 to 4." },
      { id: "bia", title: "Building Industry Assessment", form: "v4", summary: "Only for building work." },
    ],
    cpd_questions: [{ id: "conferences", q: "What conferences or seminars have you attended?", type: "Type II" }],
    part1: [{ id: "risk", q: "Are you familiar with your organisation's risk framework?", elements: ["6"] }],
    part2: [{ id: "ready", q: "Do you feel ready to proceed to the Chartered interview?" }],
    elements: [{ id: "11", unit: "Value in the workplace", title: "Judgement", meaning: "You exercise sound judgement." }],
    bia_states: { VIC: { name: "Victorian Building Industry Endorsement", years: 3, laws: "the Building Act 1993" }, WA: { name: "WA", years: 5, laws: "x" }, ACT: { name: "ACT", years: 3, laws: "y" } },
    readiness: {
      percent: 0, done: 0, total: 8,
      items: [{ id: "part3", label: "A comment on every element (Part 3)", done: false, detail: "0 of 16 written" }],
      prepare: [],
    },
  };
}

describe("<ApplicationTab />", () => {
  it("shows what's left, saves answers, and starts comments and CPD answers from your records", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/career/application/draft/element/11": () => jsonResponse({ id: "11", text: "On Melrose (May 2026), I chose to bypass the valve." }),
      "/api/v1/career/application/draft/cpd/conferences": () => jsonResponse({ id: "conferences", text: "About 14 hours: Ozwater 2026" }),
      "/api/v1/career/application": (_u, init) => {
        if (init.method === "PUT") {
          const body = JSON.parse(String(init.body));
          return jsonResponse({ ...view({ ...body, files: {} }), readiness: { ...view().readiness, percent: 13, done: 1 } });
        }
        return jsonResponse(view());
      },
    });
    const user = userEvent.setup();
    render(<MemoryRouter><ApplicationTab areaHint="Water infrastructure" /></MemoryRouter>);

    const ready = await screen.findByRole("region", { name: "Ready for the interview" });
    expect(within(ready).getByText("0 of 16 written")).toBeInTheDocument();

    const reflection = screen.getByRole("region", { name: "Self-reflection on the chartered competencies" });
    await user.click(within(reflection).getByText("Self-reflection on the chartered competencies"));
    await user.click(within(within(reflection).getByRole("radiogroup", { name: /risk framework/ })).getByRole("radio", { name: "Not sure" }));
    await waitFor(() => expect(within(ready).getByText("13%")).toBeInTheDocument());
    let put = JSON.parse(String(calls.filter((c) => c.init.method === "PUT").at(-1)!.init.body));
    expect(put.part1).toEqual({ risk: "not_sure" });
    expect(put.files).toBeUndefined();

    await user.click(within(reflection).getByRole("button", { name: /Start from my evidence/ }));
    expect(await within(reflection).findByDisplayValue(/I chose to bypass the valve/)).toBeInTheDocument();
    put = JSON.parse(String(calls.filter((c) => c.init.method === "PUT").at(-1)!.init.body));
    expect(put.part3["11"]).toMatch(/Melrose/);

    const cpd = screen.getByRole("region", { name: "CPD questionnaire" });
    await user.click(within(cpd).getByText("CPD questionnaire"));
    await user.click(within(cpd).getByRole("radio", { name: "Answer the questionnaire" }));
    await user.click(await within(cpd).findByRole("button", { name: /Fill from my CPD/ }));
    expect(await within(cpd).findByDisplayValue(/Ozwater 2026/)).toBeInTheDocument();

    const bia = screen.getByRole("region", { name: "Building Industry Assessment" });
    await user.click(within(bia).getByText("Building Industry Assessment"));
    await user.click(within(within(bia).getByRole("radiogroup", { name: /Do you need/ })).getByRole("radio", { name: "Yes" }));
    await user.click(await within(bia).findByRole("radio", { name: "VIC" }));
    expect(await within(bia).findByText(/Victorian Building Industry Endorsement\./)).toBeInTheDocument();
  });
});
