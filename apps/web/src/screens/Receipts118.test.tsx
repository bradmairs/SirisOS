import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ReceiptView } from "./ReceiptView";
import { ReceiptsCard, financialYear } from "./Life";
import { nameFrom } from "../api/save";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

const zip = (name: string) => new Response("PK", { headers: { "content-type": "application/zip", "content-disposition": `attachment; filename="x.zip"; filename*=UTF-8''${encodeURIComponent(name)}`, "x-receipts": "2" } });

describe("SirisOS 11.8.0: downloading receipts", () => {
  it("reads the file name SirisOS gives, and knows the financial year", () => {
    expect(nameFrom(`attachment; filename="a.pdf"; filename*=UTF-8''2026-11-03%20Bunnings%20-%20Drill.pdf`, "x")).toBe("2026-11-03 Bunnings - Drill.pdf");
    expect(nameFrom(null, "fallback.zip")).toBe("fallback.zip");
    expect(financialYear(new Date(2026, 10, 25))).toEqual(["2026-07-01", "2027-06-30"]);
    expect(financialYear(new Date(2026, 2, 1), 1)).toEqual(["2024-07-01", "2025-06-30"]);
  });

  it("downloads one receipt, named by date and shop", async () => {
    signIn();
    URL.createObjectURL = () => "blob:x";
    URL.revokeObjectURL = () => undefined;
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const calls = mockFetch({
      "/api/v1/life/documents/9/download": () => new Response("pdf", { headers: { "content-type": "application/pdf", "content-disposition": "attachment; filename*=UTF-8''2026-01-08%20Bunnings%20-%20Drill.pdf" } }),
      "/api/v1/life/documents/9/files/INV.pdf": () => new Response("pdf", { headers: { "content-type": "application/pdf" } }),
      "/api/v1/life/documents/9": () => jsonResponse({ id: 9, title: "Drill", summary: "", files: ["INV.pdf"], receipt_file: "INV.pdf", due: [], kind: "receipt" }),
    });
    const user = userEvent.setup();
    render(<ReceiptView id={9} />);
    await user.click(await screen.findByRole("button", { name: /Download/ }));
    await waitFor(() => expect(click).toHaveBeenCalled());
    expect((click.mock.instances[0] as unknown as HTMLAnchorElement).download).toBe("2026-01-08 Bunnings - Drill.pdf");
    expect(calls.some((c) => c.url === "/api/v1/life/documents/9/download")).toBe(true);
  });

  it("downloads the receipts shown, or a financial year's, as a zip", async () => {
    signIn();
    URL.createObjectURL = () => "blob:x";
    URL.revokeObjectURL = () => undefined;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const calls = mockFetch({
      "/api/v1/life/receipts/download": () => zip("Receipts.zip"),
      "/api/v1/life/email": () => jsonResponse({ connected: true, address: "me@example.com", label: "Receipts" }),
      "/api/v1/life/documents": () => jsonResponse([{ id: 1, added_at: "2026-11-03", title: "Drill", sender: "Bunnings", summary: "", kind: "receipt", due: [], filename: "", note_title: null },
        { id: 2, added_at: "2026-10-03", title: "Shoes", sender: "The Iconic", summary: "", kind: "receipt", due: [], filename: "", note_title: null }]),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><ReceiptsCard /></MemoryRouter>);
    const which = await screen.findByRole("combobox", { name: "Which receipts to download" });
    expect(screen.getByRole("option", { name: "All 2" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Download/ }));
    expect(await screen.findByText(/Saved Receipts.zip/)).toBeInTheDocument();
    await user.selectOptions(which, "lastfy");
    await user.click(screen.getByRole("button", { name: /Download/ }));
    await waitFor(() => expect(calls.filter((c) => c.url.startsWith("/api/v1/life/receipts/download"))).toHaveLength(2));
    expect(calls.filter((c) => c.url.startsWith("/api/v1/life/receipts/download"))[1].url).toMatch(/start=\d{4}-07-01&end=\d{4}-06-30/);
  });
});
