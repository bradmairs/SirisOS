import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { DebriefCard } from "./DebriefCard";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

const OPEN = {
  asked: "2026-11-20", answered: null, open: true, projects: ["Melrose East Pump Station", "Sunday Creek Reservoir"],
  cpeng_question: "CPEng: you have no evidence yet for 10 Taking action. Tell me about a time you took it on yourself.",
};

describe("The Friday debrief card (9.9)", () => {
  it("files the answers on the project and says where they went", async () => {
    signIn();
    let sent: Record<string, string> | null = null;
    mockFetch({
      "/api/v1/brain/debrief": (_url, init) => {
        if (init.method === "POST") {
          sent = JSON.parse(String(init.body));
          return jsonResponse({ filed: "Melrose East Pump Station", decision: true, lesson: true });
        }
        return jsonResponse(OPEN);
      },
    });
    render(<DebriefCard />);
    const save = await screen.findByRole("button", { name: "Save to Siris" });
    expect(save).toBeDisabled();   // nothing written yet
    await userEvent.selectOptions(screen.getByLabelText("Project"), "Melrose East Pump Station");
    await userEvent.type(screen.getByLabelText("What did you decide this week, and why?"), "Ductile iron for the rising main");
    await userEvent.type(screen.getByLabelText("What would you do differently next time?"), "Order the survey earlier");
    await userEvent.type(screen.getByLabelText(OPEN.cpeng_question), "Chased the survey myself");
    await userEvent.click(save);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Filed on Melrose East Pump Station, and in the Decision Log and Lessons Learned.");
    expect(sent).toEqual({ project: "Melrose East Pump Station", decided: "Ductile iron for the rising main", went_wrong: "",
      differently: "Order the survey earlier", cpeng: "Chased the survey myself" });
  });

  it("stays hidden when the debrief isn't open, or SirisAI is older", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/brain/debrief": () => jsonResponse({ ...OPEN, open: false }) });
    const { container } = render(<DebriefCard />);
    await vi.waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(container).toBeEmptyDOMElement();
    clearResources();
    const old = mockFetch({ "/api/v1/brain/debrief": () => jsonResponse({ detail: "Not Found" }, 404) });
    const second = render(<DebriefCard />);
    await vi.waitFor(() => expect(old.length).toBeGreaterThan(0));
    await vi.waitFor(() => expect(second.container).toBeEmptyDOMElement());
  });
});
