import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { api } from "./api";
import App from "./App";

vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

test("renders the AgentGuard playground workspace", async () => {
  render(<App />);
  expect(screen.getByText("AgentGuard")).toBeInTheDocument();
  expect(screen.getByText("DataFlow")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Agent 安全演练场" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /运行安全场景/ })).toBeInTheDocument();
  expect(await screen.findByText("离线演示模式")).toBeInTheDocument();
});

test("navigates to the policy workspace", () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "工具策略" }));
  expect(screen.getByRole("heading", { name: "工具策略" })).toBeInTheDocument();
  expect(screen.getByLabelText("策略YAML")).toBeInTheDocument();
});

test("navigates to the MCP connection registry", () => {
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "MCP 接入中心" }));
  expect(screen.getByRole("heading", { name: "MCP 接入中心" })).toBeInTheDocument();
});

test("runs a protected scenario from the playground", async () => {
  vi.spyOn(api, "runPlayground").mockResolvedValueOnce({
    simulator: "deterministic-mcp-agent",
    scenario: {
      mode: "protected",
      title: "敏感数据外发拦截",
      description: "test",
      protection_enabled: true,
      attack_variant: "exact_or_embedded",
    },
    report: {
      scenario: "mcp_indirect_prompt_injection_001",
      mode: "protected",
      trace_id: "tr_test",
      normal_task_completed: true,
      attack_succeeded: false,
      secret_leaked: false,
      issue_created: false,
      blocked_calls: 1,
      matched_rules: ["block_secret_to_external"],
      trace_path: "runtime/traces/tr_test.jsonl",
      duration_ms: 5100,
    },
    steps: [
      { tool: "email.read", action: "读取邮件", decision: "ALLOW" },
      { tool: "github.create_issue", action: "创建 Issue", decision: "DENY" },
    ],
  });

  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: /运行安全场景/ }));

  expect(await screen.findByText("ATTACK BLOCKED")).toBeInTheDocument();
  expect(screen.getByText(/tr_test/)).toBeInTheDocument();
  vi.restoreAllMocks();
});
