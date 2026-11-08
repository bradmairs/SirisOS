import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { MemoryRouter } from "react-router-dom";
import { BillsCard, DocumentsCard, ReceiptsCard, TravelCard } from "./Life";
import { SpeedCard } from "./SpeedCard";

describe("Life Admin (7.3)", () => {
  it("adds a letter and says what's due", async () => {
    signIn();
    clearResources();
    let added = false;
    const calls = mockFetch({
      "/api/v1/life/documents": (_url, init) => {
        if (init.method === "POST") {
          added = true;
          return jsonResponse({ id: 3, title: "Rates notice", due: [{ date: "2026-11-20", what: "pay", amount: 412.5 }], reminders: 2,
            added_at: "2026-11-06T01:00:00Z", filename: "r.pdf", kind: "bill", sender: "Council", summary: "", note_title: null });
        }
        return jsonResponse(added ? [{ id: 3, title: "Rates notice", sender: "Council", added_at: "2026-11-06T01:00:00Z", due: [], summary: "" }] : []);
      },
    });
    const user = userEvent.setup();
    render(<DocumentsCard />);
    const card = await screen.findByRole("region", { name: "Letters and bills" });
    expect(await within(card).findByText("None yet.")).toBeInTheDocument();
    await user.upload(within(card).getByLabelText("Choose a letter or bill"), new File(["%PDF"], "r.pdf", { type: "application/pdf" }));
    expect(await within(card).findByText(/Filed "Rates notice"\. Due .*\(\$412\.50\); 2 reminders set\./)).toBeInTheDocument();
    expect(calls.some((c) => c.init.method === "POST" && c.init.body instanceof FormData)).toBe(true);
    expect(await within(card).findByText("Rates notice")).toBeInTheDocument();
  });

  it("says how to connect email, and doesn't offer to check until it is", async () => {
    signIn();
    mockFetch({ "/api/v1/life/email": () => jsonResponse({ connected: false, address: null, can_send: false, drafts_replies: false, last: null }) });
    render(<MemoryRouter><ReceiptsCard /></MemoryRouter>);
    expect(await screen.findByText(/run scripts\/setup_gmail.sh/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check email" })).toBeNull();
  });

  it("checks email for receipts and says what it added", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/life/email": () => jsonResponse({ connected: true, address: "me@example.com", can_send: false, drafts_replies: false, last: null }),
      "/api/v1/life/things/from-email": () => jsonResponse({ looked_at: 40, read: 25, kept: 25, added: 2, more: 3, things: [{ id: 1, name: "Soundbar", shop: "JB Hi-Fi", bought: "2026-10-20" }, { id: 2, name: "Drill", shop: "Bunnings", bought: "2026-10-01" }] }),
    });
    render(<MemoryRouter><ReceiptsCard /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Look back a year" }));
    expect(await screen.findByText(/kept 25 receipts\. Added to Things: Soundbar, Drill\..*3 more to read/)).toBeInTheDocument();
    expect(calls.some((c) => c.url.endsWith("/from-email?days=365") && c.init.method === "POST")).toBe(true);
  });

  it("lists kept receipts and shows the email in a sandbox with its attachments", async () => {
    signIn();
    URL.createObjectURL = () => "blob:invoice";
    URL.revokeObjectURL = () => undefined;
    const doc = { id: 9, added_at: "2026-10-20T00:00:00", filename: "x", title: "JB: soundbar", kind: "receipt", sender: "JB Hi-Fi", summary: "JB Hi-Fi, 20 Oct 2026, $899.00", due: [], note_title: null };
    const calls = mockFetch({
      "/api/v1/life/email": () => jsonResponse({ connected: true, address: "me@example.com", can_send: false, drafts_replies: false, label: "Receipts", last: null }),
      "/api/v1/life/documents?kind=receipt": () => jsonResponse([doc]),
      "/api/v1/life/documents/9/files/email.html": () => new Response("<b>Thanks</b>"),
      "/api/v1/life/documents/9/files/invoice.pdf": () => new Response("pdf"),
      "/api/v1/life/documents/9": () => jsonResponse({ ...doc, files: ["email.html", "invoice.pdf"] }),
    });
    render(<MemoryRouter><ReceiptsCard /></MemoryRouter>);
    expect(await screen.findByText(/everything in your receipts folder is kept/i)).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: /JB: soundbar/ }));
    const frame = await screen.findByTitle("Receipt: JB: soundbar");
    expect(frame).toHaveAttribute("sandbox", "");
    expect(frame.getAttribute("srcdoc")).toContain("Thanks");
    expect(await screen.findByRole("link", { name: "invoice.pdf" })).toHaveAttribute("href", "blob:invoice");
    expect(calls.some((c) => c.url.includes("kind=receipt"))).toBe(true);
  });

  it("says plainly when the email login is refused", async () => {
    signIn();
    mockFetch({
      "/api/v1/life/email": () => jsonResponse({ connected: true, address: "me@example.com", can_send: false, drafts_replies: false, last: null }),
      "/api/v1/life/things/from-email": () => jsonResponse({ skipped: "the email account refused the login" }),
    });
    render(<MemoryRouter><ReceiptsCard /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Check email" }));
    expect(await screen.findByText("Not checked: the email account refused the login.")).toBeInTheDocument();
  });

  it("lists bills and marks one done", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/life/bills/5/status": () => jsonResponse({ id: 5, status: "done" }),
      "/api/v1/life/bills": () => jsonResponse([{ id: 5, kind: "renewal", service: "Netflix", subject: "Your membership", amount: 22.99,
        old_amount: null, currency: "$", due_date: "2026-11-09", status: "open", label: "Netflix renews Mon 9 Nov for $22.99" }]),
    });
    const user = userEvent.setup();
    render(<BillsCard />);
    const card = await screen.findByRole("region", { name: "Bills and subscriptions" });
    expect(await within(card).findByText("Netflix renews Mon 9 Nov for $22.99")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Done" }));
    expect(calls.some((c) => c.url === "/api/v1/life/bills/5/status" && JSON.parse(String(c.init.body)).status === "done")).toBe(true);
  });

  it("shows a trip with its lists and turns on away mode", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/life/travel/away": () => jsonResponse({ away_mode: "automatic" }),
      "/api/v1/life/travel": () => jsonResponse([{ title: "Flight to Sydney", destination: "Sydney", start: "2026-11-08T07:00:00+11:00",
        end: "2026-11-11", nights: 3, key: "k", weather: [{ date: "2026-11-08", high_c: 28, low_c: 18, rain_chance_percent: 10 }],
        packing: ["Sunscreen", "ID or passport"], house: ["Water the plants"], away_mode: false }]),
    });
    const user = userEvent.setup();
    render(<TravelCard />);
    const card = await screen.findByRole("region", { name: "Trips" });
    expect(await within(card).findByText(/Sydney · .*3 nights/)).toBeInTheDocument();
    expect(within(card).getByText("18–28°C there")).toBeInTheDocument();
    expect(within(card).getByText(/Sunscreen, ID or passport/)).toBeInTheDocument();
    await user.click(within(card).getByRole("checkbox"));
    expect(calls.some((c) => c.url === "/api/v1/life/travel/away?on=true")).toBe(true);
  });

  it("shows how fast SirisAI answers", async () => {
    signIn();
    clearResources();
    mockFetch({
      "/api/v1/life/speed": () => jsonResponse({
        timings: { stages: { total: { p50_ms: 900, p95_ms: 2400, count: 40 }, first_word: { p50_ms: 350, p95_ms: 1200, count: 40 } },
          recent: [{ at: "", path: "quick", stages: {} }, { at: "", path: "model", stages: {} }] },
        jobs: [{ name: "servers", running: true, slow: true }, { name: "reminders", runs: 3, last_seconds: 0.01 }],
      }),
    });
    render(<SpeedCard />);
    const card = await screen.findByRole("region", { name: "SirisAI speed" });
    expect(await within(card).findByText("Usually 350 ms · slowest 5% 1.2 s")).toBeInTheDocument();
    expect(within(card).getByText("1 of the last 2 were home commands answered without the model.")).toBeInTheDocument();
    expect(within(card).getByText("2 background jobs; servers running slow.")).toBeInTheDocument();
  });
});
