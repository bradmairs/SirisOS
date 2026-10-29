import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { ResurfaceWidget } from "./DayWidgets";

const note = (title: string) => ({ date: "2026-10-29", title, path: `Notes/${title}.md`, tags: [], excerpt: "PE100 vs DICL for rising mains.", why: "Related to your project Home Lab", as_of: "2026-03-01", age_days: 242 });

describe("<ResurfaceWidget />", () => {
  it("shows today's older note, and Not useful brings another", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/resurface/respond": () => jsonResponse({ note: note("Old Pump Station Lessons") }),
      "/api/v1/resurface": () => jsonResponse({ note: note("Pipe Materials") }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><ResurfaceWidget /></MemoryRouter>);
    expect(await screen.findByRole("link", { name: "Pipe Materials" })).toHaveAttribute("href", "/brain?q=Pipe%20Materials");
    expect(screen.getByText("8 months ago")).toBeInTheDocument();
    expect(screen.getByText("Related to your project Home Lab")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Not useful" }));
    expect(await screen.findByRole("link", { name: "Old Pump Station Lessons" })).toBeInTheDocument();
    expect(JSON.parse(String(calls.at(-1)!.init.body))).toEqual({ title: "Pipe Materials", answer: "not_useful" });
  });

  it("is hidden when there's nothing to resurface", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/resurface": () => jsonResponse({ note: null }) });
    const { container } = render(<MemoryRouter><ResurfaceWidget /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 30));
    expect(container).toBeEmptyDOMElement();
  });
});
