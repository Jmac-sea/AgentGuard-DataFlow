import type { Benchmark } from "../types";

const percent = (value: number) => `${Math.round(value * 100)}%`;

export function BenchmarkPage({ benchmark, live }: { benchmark: Benchmark; live: boolean }) {
  return (
    <section className="panel benchmark-page">
      <div className="panel-heading"><div><span className="eyebrow">{benchmark.run_id}</span><h2>防护效果基准评测</h2><p>每种模式运行 {benchmark.runs_per_mode} 次</p></div><span className={`live-pill ${live ? "connected" : "demo"}`}>{live ? "LIVE DATA" : "DEMO DATA"}</span></div>
      <div className="benchmark-table">
        <div className="benchmark-row header"><span>模式</span><span>攻击成功率</span><span>秘密泄漏率</span><span>阻断率</span><span>任务完成率</span></div>
        {benchmark.metrics.map((metric) => (
          <div className="benchmark-row" key={metric.mode}>
            <strong>{metric.mode}</strong>
            <span className={metric.attack_success_rate > 0 ? "danger" : "safe"}>{percent(metric.attack_success_rate)}</span>
            <span>{percent(metric.secret_leak_rate)}</span>
            <span>{percent(metric.blocking_rate)}</span>
            <span>{percent(metric.normal_task_completion_rate)}</span>
          </div>
        ))}
      </div>
      <div className="comparison-bars">
        {benchmark.metrics.filter((metric) => ["baseline", "protected", "protected-base64", "protected-split"].includes(metric.mode)).map((metric) => (
          <div className="bar-item" key={metric.mode}><span>{metric.mode}</span><div><i style={{ width: `${Math.max(2, metric.attack_success_rate * 100)}%` }} className={metric.attack_success_rate > 0 ? "bad-bar" : "good-bar"} /></div><strong>{percent(metric.attack_success_rate)}</strong></div>
        ))}
      </div>
    </section>
  );
}

