import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import App from "./App";

vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

test("renders the AgentGuard data lineage workspace", () => {
  render(<App />);
  expect(screen.getByText("AgentGuard")).toBeInTheDocument();
  expect(screen.getByText("DataFlow")).toBeInTheDocument();
  expect(screen.getByText("跨工具数据血缘")).toBeInTheDocument();
  expect(screen.getByText("泄漏阻断详情")).toBeInTheDocument();
});
