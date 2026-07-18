import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import App from "./App";

vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

test("renders the AgentGuard data lineage workspace", async () => {
  render(<App />);
  expect(screen.getByText("AgentGuard")).toBeInTheDocument();
  expect(screen.getByText("DataFlow")).toBeInTheDocument();
  expect(screen.getByText("跨工具数据血缘")).toBeInTheDocument();
  expect(screen.getByText("泄漏阻断详情")).toBeInTheDocument();
  expect(await screen.findByText("离线演示模式")).toBeInTheDocument();
});

test("navigates to the policy workspace", () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "工具策略" }));
  expect(screen.getByRole("heading", { name: "工具策略" })).toBeInTheDocument();
  expect(screen.getByLabelText("策略YAML")).toBeInTheDocument();
});
