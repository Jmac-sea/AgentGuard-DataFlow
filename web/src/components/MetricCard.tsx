import type { LucideIcon } from "lucide-react";

type MetricCardProps = {
  label: string;
  value: string;
  tone: "cyan" | "amber" | "violet" | "green";
  icon: LucideIcon;
};

export function MetricCard({ label, value, tone, icon: Icon }: MetricCardProps) {
  return (
    <article className={`metric-card ${tone}`}>
      <div><span>{label}</span><strong>{value}</strong></div>
      <Icon size={32} />
    </article>
  );
}

