import { describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { clearResources, useResource } from "./resource";

function Reader({ id, fetcher }: { id: string; fetcher: () => Promise<string> }) {
  const { data, loading } = useResource("test:key", fetcher);
  return <span data-testid={id}>{data ?? (loading ? "loading" : "empty")}</span>;
}

describe("useResource", () => {
  it("shares one request between every reader of a key", async () => {
    const fetcher = vi.fn(async () => "apps");
    render(
      <>
        <Reader id="sidebar" fetcher={fetcher} />
        <Reader id="home" fetcher={fetcher} />
        <Reader id="engineering" fetcher={fetcher} />
      </>,
    );
    await waitFor(() => expect(screen.getByTestId("home")).toHaveTextContent("apps"));
    expect(screen.getByTestId("sidebar")).toHaveTextContent("apps");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("renders the cached value instantly when a screen is revisited", async () => {
    const fetcher = vi.fn(async () => "cached");
    const first = render(<Reader id="a" fetcher={fetcher} />);
    await waitFor(() => expect(screen.getByTestId("a")).toHaveTextContent("cached"));
    first.unmount();

    render(<Reader id="b" fetcher={fetcher} />);
    // No loading state: the last value is on screen in the first render.
    expect(screen.getByTestId("b")).toHaveTextContent("cached");
    expect(fetcher).toHaveBeenCalledTimes(1); // still fresh, so no refetch
  });

  it("forgets everything on sign-out", async () => {
    const fetcher = vi.fn(async () => "secret");
    const view = render(<Reader id="a" fetcher={fetcher} />);
    await waitFor(() => expect(screen.getByTestId("a")).toHaveTextContent("secret"));
    view.unmount();
    act(() => clearResources());
    fetcher.mockImplementation(() => new Promise(() => {}));
    render(<Reader id="b" fetcher={fetcher} />);
    expect(screen.getByTestId("b")).not.toHaveTextContent("secret");
  });
});
