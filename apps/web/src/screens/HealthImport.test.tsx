import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { Health } from "../api/health";
import fixture from "./__health_fixture.json";
import { ImportStatus } from "./Health";

const base = fixture as unknown as Health;
const empty = (imp?: object): Health => ({ ...base, today: "2026-11-01", activity: { ...base.activity!, steps: null },
  sleep: { ...base.sleep, last_night: null }, sources: { ...base.sources, imports: imp ? { health_auto_export: imp as never } : {} } });

describe("why today is empty (6.91)", () => {
  it("says the export stops at yesterday", () => {
    render(<MemoryRouter><ImportStatus h={empty({ at: new Date().toISOString(), last_day: "2026-10-31" })} /></MemoryRouter>);
    expect(screen.getByRole("status")).toHaveTextContent("only went up to 2026-10-31, so today isn't in it. In Health Auto Export, set Date Range to Default");
  });
  it("says nothing has arrived for hours", () => {
    render(<MemoryRouter><ImportStatus h={empty({ at: new Date(Date.now() - 7 * 3600_000).toISOString(), last_day: "2026-11-01" })} /></MemoryRouter>);
    expect(screen.getByRole("status")).toHaveTextContent("Nothing from Health Auto Export since 7 hours ago");
  });
  it("is quiet when today's data is in", () => {
    const { container } = render(<MemoryRouter><ImportStatus h={base} /></MemoryRouter>);
    expect(container).toBeEmptyDOMElement();
  });
});
