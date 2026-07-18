import type {
  Approval,
  Benchmark,
  Lineage,
  MCPRegistry,
  PlaygroundRun,
  PlaygroundScenario,
  RemoteGateway,
  PolicyDocument,
  ReplayReport,
  TraceDetail,
  TraceSummary,
} from "./types";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function sendJson<T>(url: string, method: "POST", body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  traces: () => getJson<TraceSummary[]>("/api/v1/traces"),
  trace: (traceId: string) => getJson<TraceDetail>(`/api/v1/traces/${traceId}`),
  lineage: (traceId: string) => getJson<Lineage>(`/api/v1/traces/${traceId}/lineage`),
  benchmarks: () => getJson<Benchmark[]>("/api/v1/benchmarks"),
  activePolicy: () => getJson<PolicyDocument>("/api/v1/policies/active"),
  validatePolicy: (yaml: string) =>
    sendJson<{ valid: boolean; policy_id?: string; errors: string[] }>(
      "/api/v1/policies/validate",
      "POST",
      { yaml },
    ),
  replay: (traceId: string) =>
    sendJson<ReplayReport>("/api/v1/replays", "POST", { trace_id: traceId }),
  approvals: () => getJson<Approval[]>("/api/v1/approvals"),
  approve: (approvalId: string) =>
    sendJson<Approval>(`/api/v1/approvals/${approvalId}/approve`, "POST"),
  reject: (approvalId: string) =>
    sendJson<Approval>(`/api/v1/approvals/${approvalId}/reject`, "POST"),
  playgroundScenarios: () =>
    getJson<PlaygroundScenario[]>("/api/v1/playground/scenarios"),
  runPlayground: (mode: string) =>
    sendJson<PlaygroundRun>("/api/v1/playground/runs", "POST", { mode }),
  mcpServers: () => getJson<MCPRegistry>("/api/v1/mcp/servers"),
  discoverMcpServers: () =>
    sendJson<MCPRegistry>("/api/v1/mcp/servers/discover", "POST"),
  remoteGateway: () => getJson<RemoteGateway>("/api/v1/gateway/remote"),
};
