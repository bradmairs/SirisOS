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

describe("weight on Data sync (7.91)", () => {
  it("says when weight last came through, or how to send it", async () => {
    const { jsonResponse, mockFetch, signIn } = await import("../test/helpers");
    const { clearResources } = await import("../api/resource");
    const { HealthSyncCard } = await import("./HealthSync");
    const status = { has_key: true, key_hint: "abcd", made: null, path: "/api/v1/health/import", last: null,
      last_ok: { at: "2026-11-07T01:00:00Z", days: ["2026-11-07"] }, attempts: [] };
    signIn();
    clearResources();
    mockFetch({ "/api/v1/health/import/status": () => jsonResponse({ ...status, ignored: ["body_weight_scale"] }) });
    const first = render(<MemoryRouter><HealthSyncCard health={true} /></MemoryRouter>);
    const none = await screen.findByLabelText("Weight from Apple Health");
    expect(none).toHaveTextContent("No weight has come through yet. In Health Auto Export's Health Metrics automation, tick Weight & Body Mass");
    expect(none).toHaveTextContent("Sent under a name SirisAI doesn't use: body_weight_scale.");
    first.unmount();
    clearResources();
    mockFetch({ "/api/v1/health/import/status": () => jsonResponse({ ...status, last_weight: { date: "2026-11-06", kg: 82.4, at: "x" } }) });
    render(<MemoryRouter><HealthSyncCard health={true} /></MemoryRouter>);
    expect(await screen.findByLabelText("Weight from Apple Health")).toHaveTextContent("Weight: 82.4 kg on");
  });
});
