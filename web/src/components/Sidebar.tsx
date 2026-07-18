import { Activity, GitBranch, Play, Scale, Settings2, ShieldCheck } from "lucide-react";

export type Page = "lineage" | "benchmark";

type SidebarProps = {
  page: Page;
  onPageChange: (page: Page) => void;
};

const items = [
  { label: "流量总览", icon: Activity, disabled: true },
  { label: "数据血缘", icon: GitBranch, page: "lineage" as const },
  { label: "工具策略", icon: ShieldCheck, disabled: true },
  { label: "攻击回放", icon: Play, disabled: true },
  { label: "基准评测", icon: Scale, page: "benchmark" as const },
];

export function Sidebar({ page, onPageChange }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark"><ShieldCheck size={28} /></div>
        <div><strong>AgentGuard</strong><span>DataFlow</span></div>
      </div>
      <nav>
        {items.map((item) => {
          const Icon = item.icon;
          const active = item.page === page;
          return (
            <button
              key={item.label}
              className={`nav-item ${active ? "active" : ""}`}
              disabled={item.disabled}
              onClick={() => item.page && onPageChange(item.page)}
            >
              <Icon size={19} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidebar-footer"><Settings2 size={18} /><span>v0.1.0</span></div>
    </aside>
  );
}

