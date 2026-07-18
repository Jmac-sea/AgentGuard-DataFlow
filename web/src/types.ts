export type TraceSummary = {
  trace_id: string;
  event_count: number;
  blocked: boolean;
  last_event_at: string | null;
};

export type LineageNode = {
  id: string;
  type: "tool_call" | "data_artifact";
  label: string;
  category?: string;
  labels?: string[];
  status: string;
};

export type LineageEdge = {
  source: string;
  target: string;
  type: string;
  confidence?: number;
  target_path?: string;
};

export type Lineage = {
  trace_id: string;
  nodes: LineageNode[];
  edges: LineageEdge[];
};

export type BenchmarkMetric = {
  mode: string;
  runs: number;
  attack_success_rate: number;
  secret_leak_rate: number;
  issue_creation_rate: number;
  blocking_rate: number;
  normal_task_completion_rate: number;
  average_duration_ms: number;
  p50_duration_ms: number;
  p95_duration_ms: number;
};

export type Benchmark = {
  run_id: string;
  created_at: string;
  runs_per_mode: number;
  transport?: string;
  metrics: BenchmarkMetric[];
};

export type TraceEvent = {
  event_id: string;
  trace_id: string;
  session_id: string;
  timestamp: string;
  type: string;
  payload: Record<string, unknown>;
};

export type TraceDetail = {
  trace_id: string;
  events: TraceEvent[];
};

export type PolicyDocument = {
  version: string;
  policy_id: string;
  defaults: Record<string, string>;
  rules: Array<Record<string, unknown>>;
};

export type ReplayDecision = {
  call_id: string;
  tool_name: string;
  original_action: string;
  replayed_action: string;
  original_rule: string | null;
  replayed_rule: string | null;
  changed: boolean;
};

export type ReplayReport = {
  trace_id: string;
  policy_id: string;
  decisions: ReplayDecision[];
};

export type Approval = {
  approval_id: string;
  request_call_id: string;
  session_id: string;
  tool_name: string;
  arguments_digest: string;
  status: "pending" | "approved" | "rejected" | "consumed" | "expired";
  severity: string;
  reason: string;
  matched_rule: string | null;
  created_at: string;
  expires_at: string | null;
  token?: string;
};

export type PlaygroundScenario = {
  mode: string;
  title: string;
  description: string;
  protection_enabled: boolean;
  attack_variant: string;
};

export type PlaygroundStep = {
  tool: string;
  action: string;
  decision: "ALLOW" | "DENY";
};

export type ScenarioReport = {
  scenario: string;
  mode: string;
  trace_id: string;
  normal_task_completed: boolean;
  attack_succeeded: boolean;
  secret_leaked: boolean;
  issue_created: boolean;
  blocked_calls: number;
  matched_rules: string[];
  trace_path: string;
  duration_ms: number;
};

export type PlaygroundRun = {
  simulator: string;
  scenario: PlaygroundScenario;
  report: ScenarioReport;
  steps: PlaygroundStep[];
};

export type MCPToolConnection = {
  downstream_name: string;
  expose_as: string;
  category: string;
  description: string | null;
};

export type MCPServerConnection = {
  id: string;
  command: string;
  status: "configured" | "healthy" | "error";
  tools: MCPToolConnection[];
  discovered_tools?: string[];
  hidden_tools?: string[];
};

export type MCPRegistry = {
  config_path: string;
  status: "configured" | "healthy" | "error";
  last_checked_at: string | null;
  duration_ms?: number;
  servers: MCPServerConnection[];
};

export type RemoteGateway = {
  status: "online" | "offline" | "degraded";
  transport: "streamable-http";
  endpoint: string;
  health_endpoint: string;
  authentication: string;
};
