import { Bot, CheckCheck, GitBranch, Play, PlugZap, Scale, Settings2, ShieldCheck } from "lucide-react";

export type Page = "playground" | "connections" | "lineage" | "policy" | "replay" | "approvals" | "benchmark";

type SidebarProps = { page: Page; onPageChange: (page: Page) => void };

const items = [
  { label: "Agent 演练场", icon: Bot, page: "playground" as const },
  { label: "MCP 接入中心", icon: PlugZap, page: "connections" as const },
  { label: "数据血缘", icon: GitBranch, page: "lineage" as const },
  { label: "工具策略", icon: ShieldCheck, page: "policy" as const },
  { label: "攻击回放", icon: Play, page: "replay" as const },
  { label: "审批中心", icon: CheckCheck, page: "approvals" as const },
  { label: "基准评测", icon: Scale, page: "benchmark" as const },
];

export function Sidebar({ page, onPageChange }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><ShieldCheck size={28} /></div><div><strong>AgentGuard</strong><span>DataFlow</span></div></div>
      <nav>{items.map((item) => { const Icon = item.icon; return <button key={item.page} className={`nav-item ${item.page === page ? "active" : ""}`} onClick={() => onPageChange(item.page)}><Icon size={19} /><span>{item.label}</span></button>; })}</nav>
      <div className="sidebar-footer"><Settings2 size={18} /><span>v0.1.0</span></div>
    </aside>
  );
}
