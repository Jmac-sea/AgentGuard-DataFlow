import { useEffect, useState } from "react";
import { api } from "../api";
import type { Approval } from "../types";

export function ApprovalPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [issuedToken, setIssuedToken] = useState<string | null>(null);
  const refresh = async () => setApprovals(await api.approvals());
  useEffect(() => { void refresh().catch(() => undefined); }, []);
  const approve = async (id: string) => { const result = await api.approve(id); setIssuedToken(result.token ?? null); await refresh(); };
  const reject = async (id: string) => { await api.reject(id); await refresh(); };
  return (
    <section className="panel page-panel">
      <div className="panel-heading"><div><span className="eyebrow">HUMAN IN THE LOOP</span><h2>审批中心</h2><p>Token绑定会话、工具和参数摘要，过期或消费后无法复用。</p></div></div>
      {issuedToken && <div className="token-banner"><strong>一次性Approval Token</strong><code>{issuedToken}</code><button onClick={() => setIssuedToken(null)}>关闭</button></div>}
      <div className="approval-list">
        {approvals.map((approval) => <article key={approval.approval_id} className="approval-card"><div><span className={`status-pill ${approval.status}`}>{approval.status}</span><h3>{approval.tool_name}</h3><p>{approval.reason}</p><code>{approval.arguments_digest.slice(0, 20)}…</code></div>{approval.status === "pending" && <div className="approval-actions"><button className="approve-button" onClick={() => void approve(approval.approval_id)}>批准</button><button className="reject-button" onClick={() => void reject(approval.approval_id)}>拒绝</button></div>}</article>)}
        {!approvals.length && <div className="empty-state">当前没有审批请求</div>}
      </div>
    </section>
  );
}
