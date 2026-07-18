import { Activity, Clock3, ShieldAlert, Target } from "lucide-react";
import { LineageGraph } from "../components/LineageGraph";
import { MetricCard } from "../components/MetricCard";
import type { Lineage } from "../types";

export function LineagePage({ lineage, live }: { lineage: Lineage; live: boolean }) {
  const criticalEdge = lineage.edges.find((edge) => edge.confidence !== undefined);
  const blockedNode = lineage.nodes.find((node) => node.status === "blocked");
  const artifact = lineage.nodes.find((node) => node.type === "data_artifact");
  return (
    <>
      <section className="metric-grid">
        <MetricCard label="受保护调用" value="1,284" tone="cyan" icon={Activity} />
        <MetricCard label="泄漏尝试" value="7" tone="amber" icon={ShieldAlert} />
        <MetricCard label="误报率" value="1.8%" tone="violet" icon={Target} />
        <MetricCard label="P95 延迟" value="18ms" tone="green" icon={Clock3} />
      </section>
      <section className="workspace-grid">
        <article className="panel lineage-panel">
          <div className="panel-heading"><div><span className="eyebrow">TRACE {lineage.trace_id}</span><h2>跨工具数据血缘</h2></div><span className={`live-pill ${live ? "connected" : "demo"}`}>{live ? "LIVE DATA" : "DEMO DATA"}</span></div>
          <LineageGraph lineage={lineage} />
        </article>
        <aside className="panel incident-panel">
          <div className="panel-heading"><div><span className="eyebrow">POLICY DECISION</span><h2>泄漏阻断详情</h2></div></div>
          <div className="deny-banner"><OctagonXIcon /> DENY</div>
          <dl className="incident-list">
            <div><dt>来源</dt><dd>{artifact?.label ?? "Unknown"}</dd></div>
            <div><dt>目标</dt><dd>{blockedNode?.label ?? "github.create_issue"}</dd></div>
            <div><dt>数据匹配</dt><dd className="danger">{criticalEdge?.confidence ? `${Math.round(criticalEdge.confidence * 100)}%` : "—"}</dd></div>
            <div><dt>变形方式</dt><dd>{criticalEdge?.type ?? "—"}</dd></div>
            <div><dt>命中策略</dt><dd>block_secret_to_external</dd></div>
            <div><dt>处理结果</dt><dd className="danger">写入已阻止</dd></div>
          </dl>
          <button className="primary-button">回放攻击轨迹</button>
        </aside>
      </section>
      <section className="bottom-grid">
        <article className="panel compact-panel"><h2>数据变形检测</h2>{["原文匹配", "子串匹配", "Base64", "拆分重组"].map((label) => <div className="check-row" key={label}><span>{label}</span><strong>PASS</strong><small>96%</small></div>)}</article>
        <article className="panel compact-panel"><h2>最近工具调用</h2>{lineage.nodes.filter((node) => node.type === "tool_call").map((node) => <div className="tool-row" key={node.id}><span>{node.label}</span><code>{node.category}</code><strong className={node.status === "blocked" ? "deny-text" : "allow-text"}>{node.status === "blocked" ? "DENY" : "ALLOW"}</strong></div>)}</article>
      </section>
    </>
  );
}

function OctagonXIcon() {
  return <ShieldAlert size={26} />;
}

