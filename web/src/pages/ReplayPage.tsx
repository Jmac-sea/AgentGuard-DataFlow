import { useEffect, useState } from "react";
import { PlayCircle } from "lucide-react";
import { api } from "../api";
import type { ReplayReport, TraceSummary } from "../types";

export function ReplayPage({ traces }: { traces: TraceSummary[] }) {
  const [traceId, setTraceId] = useState(traces[0]?.trace_id ?? "");
  const [report, setReport] = useState<ReplayReport | null>(null);
  useEffect(() => {
    if (!traceId && traces.length) setTraceId(traces[0].trace_id);
  }, [traceId, traces]);
  const run = async () => traceId && setReport(await api.replay(traceId));
  return (
    <section className="panel page-panel">
      <div className="panel-heading"><div><span className="eyebrow">DETERMINISTIC REPLAY</span><h2>攻击回放</h2><p>不调用模型和下游工具，仅使用保存的来源证据重新执行策略。</p></div></div>
      <div className="action-toolbar">
        <select value={traceId} onChange={(event) => setTraceId(event.target.value)}>{traces.map((trace) => <option key={trace.trace_id}>{trace.trace_id}</option>)}</select>
        <button className="primary-button inline" disabled={!traceId} onClick={() => void run()}><PlayCircle size={18} />运行回放</button>
      </div>
      <div className="decision-table">
        <div className="decision-row header"><span>工具</span><span>原始决策</span><span>回放决策</span><span>变化</span></div>
        {report?.decisions.map((decision) => <div className="decision-row" key={decision.call_id}><strong>{decision.tool_name}</strong><span>{decision.original_action}</span><span className={decision.replayed_action === "DENY" ? "danger" : "safe"}>{decision.replayed_action}</span><span>{decision.changed ? "CHANGED" : "—"}</span></div>)}
        {!report && <div className="empty-state">选择一条Trace开始离线回放</div>}
      </div>
    </section>
  );
}
