import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { DebriefCard } from "./DebriefCard";

afterEach(() => { clearResources(); vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear(); });

const OPEN = {
  asked: "2026-11-20", answered: null, dismissed: null, open: true, projects: ["Melrose East Pump Station", "Sunday Creek Reservoir"],
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
    // 10.33: another project, or done.
    await userEvent.click(screen.getByRole("button", { name: "Add another" }));
    expect(screen.getByLabelText("Project")).toHaveValue("");
    expect(screen.getByRole("button", { name: "That's all" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "That's all" }));
    expect(screen.queryByRole("region", { name: "Friday debrief" })).not.toBeInTheDocument();
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

  it("is put away with 'Nothing this week', and 'Done' after saving hides it", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/brain/debrief/dismiss": () => jsonResponse({ ...OPEN, open: false, dismissed: "2026-11-20" }),
      "/api/v1/brain/debrief": (_url, init) => (init.method === "POST" ? jsonResponse({ filed: "Work Debriefs", decision: false, lesson: false }) : jsonResponse(OPEN)),
    });
    const first = render(<DebriefCard />);
    await userEvent.click(await screen.findByRole("button", { name: "Nothing this week" }));
    await vi.waitFor(() => expect(first.container).toBeEmptyDOMElement());
    expect(calls.some((c) => c.url === "/api/v1/brain/debrief/dismiss" && c.init.method === "POST")).toBe(true);
    first.unmount();
    clearResources();
    render(<DebriefCard />);
    await userEvent.type(await screen.findByLabelText("What went wrong or surprised you?"), "Too many meetings");
    await userEvent.click(screen.getByRole("button", { name: "Save to Siris" }));
    await userEvent.click(await screen.findByRole("button", { name: "Done" }));
    expect(screen.queryByRole("region", { name: "Friday debrief" })).not.toBeInTheDocument();
  });

  it("with an older SirisAI, shows on Fridays only and is dismissed on this device", async () => {
    signIn();
    const { dismissed: _d, ...older } = OPEN;
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date(2026, 10, 21, 6, 40) });  // Saturday morning, as in Brad's screenshot
    const calls = mockFetch({ "/api/v1/brain/debrief/dismiss": () => jsonResponse({ detail: "Not Found" }, 404), "/api/v1/brain/debrief": () => jsonResponse(older) });
    const sat = render(<DebriefCard />);
    await vi.waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(sat.container).toBeEmptyDOMElement();
    sat.unmount();
    clearResources();
    vi.setSystemTime(new Date(2026, 10, 27, 15, 0));  // the next Friday
    render(<DebriefCard />);
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(await screen.findByRole("button", { name: "Nothing this week" }));
    expect(localStorage.getItem("sirisos.debrief.dismissed")).toBe("2026-11-27");
    expect(screen.queryByRole("region", { name: "Friday debrief" })).not.toBeInTheDocument();
  });
});
