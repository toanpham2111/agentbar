import { formatTimestamp } from "../../lib/format";
import type { QuotaWindow } from "../../types/usage";

export function QuotaMeter({ quota }: { quota: QuotaWindow }) {
  if (quota.usedPercent === null) {
    return (
      <div className="quota-unavailable">
        <span>{quota.label}</span>
        <strong>Quota unavailable</strong>
        <small>No supported source exposed this value.</small>
      </div>
    );
  }

  const clamped = Math.max(0, Math.min(100, quota.usedPercent));
  const level = clamped >= 95 ? "critical" : clamped >= 80 ? "warning" : "normal";

  return (
    <div className="quota-meter">
      <div className="quota-heading">
        <span>{quota.label}</span>
        <strong>{Math.round(clamped)}% used</strong>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={`${quota.label} quota used`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(clamped)}
      >
        <span className={`progress-fill ${level}`} style={{ width: `${clamped}%` }} />
      </div>
      <div className="quota-meta">
        <span>{quota.source.replaceAll("_", " ")}</span>
        <span>{quota.resetsAt ? `Resets ${formatTimestamp(quota.resetsAt)}` : "Reset unavailable"}</span>
      </div>
    </div>
  );
}
