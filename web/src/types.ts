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
};

export type Benchmark = {
  run_id: string;
  created_at: string;
  runs_per_mode: number;
  metrics: BenchmarkMetric[];
};

