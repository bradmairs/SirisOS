import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { clearResources } from "../api/resource";

afterEach(() => {
  cleanup();
  localStorage.clear();
  clearResources();
});
