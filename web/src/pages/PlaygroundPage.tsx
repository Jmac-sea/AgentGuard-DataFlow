import { useEffect, useState } from "react";
import { ArrowRight, Bot, CheckCircle2, Play, ShieldAlert } from "lucide-react";
import { api } from "../api";
import type { PlaygroundRun, PlaygroundScenario } from "../types";

const fallbackScenarios: PlaygroundScenario[] = [
  {
    mode: "normal",
    title: "正常工单处理",
    description: "读取客户邮件并创建模拟 Issue，不包含敏感数据。",
    protection_enabled: false,
    attack_variant: "none",
  },
  {
    mode: "baseline",
    title: "无防护攻击基线",
    description: "展示没有安全网关时，间接提示注入如何导致数据泄漏。",
    protection_enabled: false,
    attack_variant: "indirect_prompt_injection",
  },
  {
    mode: "protected",
    title: "敏感数据外发拦截",
    description: "开启 AgentGuard，在外部写入执行前阻止敏感数据。",
    protection_enabled: true,
    attack_variant: "exact_or_embedded",
  },
];

export function PlaygroundPage({ onOpenTrace }: { onOpenTrace: (traceId: string) => void }) {
  const [scenarios, setScenarios] = useState(fallbackScenarios);
  const [selectedMode, setSelectedMode] = useState("protected");
  const [result, setResult] = useState<PlaygroundRun | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.playgroundScenarios().then(setScenarios).catch(() => undefined);
  }, []);

  const run = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.runPlayground(selectedMode));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "运行失败");
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="playground-layout">
      <article className="panel playground-config">
        <div className="panel-heading">
          <div><span className="eyebrow">DETERMINISTIC MCP AGENT</span><h2>Agent 安全演练场</h2><p>无需模型密钥，直接运行真实 MCP 工具链并观察安全决策。</p></div>
          <Bot size={28} />
        </div>
        <div className="scenario-list">
          {scenarios.map((scenario) => (
            <button className={`scenario-card ${selectedMode === scenario.mode ? "selected" : ""}`} key={scenario.mode} onClick={() => setSelectedMode(scenario.mode)}>
              <span className={`scenario-risk ${scenario.protection_enabled ? "protected" : "open"}`}>{scenario.protection_enabled ? "PROTECTED" : "UNPROTECTED"}</span>
              <strong>{scenario.title}</strong>
              <small>{scenario.description}</small>
              <code>{scenario.attack_variant}</code>
            </button>
          ))}
        </div>
        <button className="run-agent-button" onClick={() => void run()} disabled={running}><Play size={19} />{running ? "正在启动 MCP Agent…" : "运行安全场景"}</button>
        <p className="simulator-note">Playground 使用确定性 Agent Simulator，执行与真实 Agent 相同的 MCP 调用链，不会调用外部大模型。</p>
      </article>

      <article className="panel playground-result">
        <div className="panel-heading">
          <div><span className="eyebrow">RUN RESULT</span><h2>执行轨迹与安全结果</h2></div>
          {result && <span className={`result-status ${result.report.attack_succeeded ? "danger" : "safe"}`}>{result.report.attack_succeeded ? "ATTACK SUCCEEDED" : "ATTACK BLOCKED"}</span>}
        </div>
        {!result && !running && !error && <div className="playground-empty"><ShieldAlert size={42} /><strong>选择一个场景开始演练</strong><span>运行后这里会显示每一步工具调用和最终安全结果。</span></div>}
        {running && <div className="playground-empty running"><i /><strong>正在启动四层 MCP 进程链</strong><span>通常需要 5–8 秒，请保持页面打开。</span></div>}
        {error && <div className="playground-error">{error}</div>}
        {result && <>
          <div className="agent-step-list">
            {result.steps.map((step, index) => <div className="agent-step" key={`${step.tool}-${index}`}><span>{index + 1}</span><div><strong>{step.tool}</strong><small>{step.action}</small></div><ArrowRight size={16} /><b className={step.decision === "DENY" ? "deny-text" : "allow-text"}>{step.decision}</b></div>)}
          </div>
          <div className="run-summary-grid">
            <div><span>敏感数据泄漏</span><strong>{result.report.secret_leaked ? "是" : "否"}</strong></div>
            <div><span>阻止调用</span><strong>{result.report.blocked_calls}</strong></div>
            <div><span>执行耗时</span><strong>{(result.report.duration_ms / 1000).toFixed(2)}s</strong></div>
            <div><span>命中策略</span><strong>{result.report.matched_rules[0] ?? "无"}</strong></div>
          </div>
          <button className="trace-link-button" onClick={() => onOpenTrace(result.report.trace_id)}><CheckCircle2 size={18} />查看完整数据血缘 · {result.report.trace_id}</button>
        </>}
      </article>
    </section>
  );
}
