import type { Benchmark, Lineage, TraceSummary } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  traces: () => getJson<TraceSummary[]>("/api/v1/traces"),
  lineage: (traceId: string) => getJson<Lineage>(`/api/v1/traces/${traceId}/lineage`),
  benchmarks: () => getJson<Benchmark[]>("/api/v1/benchmarks"),
};

