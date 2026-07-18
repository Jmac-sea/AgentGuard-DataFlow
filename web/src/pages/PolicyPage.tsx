import { useEffect, useState } from "react";
import { CheckCircle2, FileWarning } from "lucide-react";
import { api } from "../api";

const DEFAULT_POLICY = `version: "1.0"
policy_id: agentguard-default
defaults:
  read: allow
  external_write: allow
rules:
  - id: block_secret_to_external
    priority: 100
    when:
      all:
        - target.category.eq: external_write
        - provenance.labels.contains: sensitivity:secret
        - provenance.confidence.gte: 0.85
    action: deny
    severity: critical
`;

export function PolicyPage() {
  const [yaml, setYaml] = useState(DEFAULT_POLICY);
  const [activeId, setActiveId] = useState("agentguard-default");
  const [result, setResult] = useState<{ valid: boolean; errors: string[] } | null>(null);
  useEffect(() => {
    void api.activePolicy().then((policy) => setActiveId(policy.policy_id)).catch(() => undefined);
  }, []);
  const validate = async () => setResult(await api.validatePolicy(yaml));
  return (
    <section className="panel page-panel">
      <div className="panel-heading"><div><span className="eyebrow">ACTIVE {activeId}</span><h2>工具策略</h2><p>在发布前验证YAML策略结构和规则字段。</p></div></div>
      <div className="editor-layout">
        <textarea aria-label="策略YAML" value={yaml} onChange={(event) => setYaml(event.target.value)} spellCheck={false} />
        <aside className="validation-panel">
          <h3>验证结果</h3>
          {!result && <p>修改策略后点击验证。当前页面不会直接激活策略。</p>}
          {result?.valid && <div className="validation-result valid"><CheckCircle2 />策略结构有效</div>}
          {result && !result.valid && <div className="validation-result invalid"><FileWarning />{result.errors.join("\n")}</div>}
          <button className="primary-button" onClick={() => void validate()}>验证策略</button>
        </aside>
      </div>
    </section>
  );
}

