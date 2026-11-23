import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string;
  helper: string;
  icon: LucideIcon;
  tone?: "primary" | "success" | "warning" | "neutral";
}

export function StatCard({ label, value, helper, icon: Icon, tone = "neutral" }: StatCardProps) {
  return (
    <article className={`stat-card stat-${tone}`}>
      <div className="stat-icon"><Icon aria-hidden="true" size={19} /></div>
      <div className="stat-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{helper}</small>
      </div>
    </article>
  );
}
