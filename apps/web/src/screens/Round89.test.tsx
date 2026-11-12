import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { flush, keep, waiting } from "../api/outbox";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { ServerCard } from "./ServerCard";
import { ShareCard } from "./ShareCard";

afterEach(() => { clearResources(); window.localStorage.removeItem("sirisos.outbox"); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("SirisOS 8.9", () => {
  it("shows a model that's spilled out of the GPU, and a disk filling up", async () => {
    signIn();
    mockFetch({ "/api/v1/machine": () => jsonResponse({ checked: "", warn_percent: 85, alert_percent: 95,
      disks: [{ label: "Data", path: "/app/data", total_gb: 500, free_gb: 40, used_percent: 92 }],
      ollama: { configured: true, error: null, models: [{ name: "llama3.1:8b", size_gb: 9, vram_gb: 6, ram_gb: 3, on_gpu_percent: 67 }] } }) });
    render(<MemoryRouter><ServerCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "The server" });
    expect(within(card).getByText("Data: 40 GB free of 500 GB")).toBeInTheDocument();
    expect(within(card).getByText("3 GB in system RAM (67% on the GPU)")).toHaveClass("tone-warning");
  });

  it("shows the share key once", async () => {
    signIn();
    mockFetch({ "/api/v1/share/key": (_url, init) => jsonResponse(init?.method === "POST" ? { key: "so_test", url: "/api/v1/share" } : { on: false, made: null }) });
    const user = userEvent.setup();
    render(<MemoryRouter><ShareCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Add to SirisOS" });
    await user.click(within(card).getByRole("button", { name: "Make a key" }));
    expect(await within(card).findByLabelText("Share key")).toHaveTextContent("so_test");
  });

  it("sends a task ticked and a receipt uploaded with no signal once SirisOS is back", async () => {
    signIn();
    keep({ kind: "task_done", task: { id: "t1", title: "Bins", source: "sirisos" } as never });
    keep({ kind: "document", name: "receipt.jpg", type: "image/jpeg", data: btoa("jpeg bytes") });
    const calls = mockFetch({ "/api/v1/tasks/t1/done": () => jsonResponse({ id: "t1", action: "done" }),
      "/api/v1/life/documents": () => jsonResponse({ id: 1, title: "Receipt", due: [] }) });
    expect(await flush()).toBe(2);
    expect(waiting()).toBe(0);
    const upload = calls.find((c) => c.url.includes("/life/documents"));
    expect((upload?.init.body as FormData).get("file")).toBeInstanceOf(File);
  });
});
