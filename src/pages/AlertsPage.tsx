import { BellRing, ShieldCheck } from "lucide-react";
import { PageHeader } from "../components/layout/PageHeader";

const thresholds = [
  { label: "Warning", value: "80%", tone: "warning", description: "Early notice for a reliable quota window." },
  { label: "Critical", value: "95%", tone: "critical", description: "The provider is approaching its verified limit." },
  { label: "Limit reached", value: "100%", tone: "danger", description: "The verified quota window has been exhausted." },
];

export function AlertsPage() {
  return (
    <div className="page-wrap">
      <PageHeader eyebrow="Native notifications" title="Alerts" description="Threshold alerts are emitted only for reliable provider quota data." />
      <section className="alert-grid">
        {thresholds.map((threshold) => (
          <article className={`alert-card alert-${threshold.tone}`} key={threshold.label}>
            <BellRing aria-hidden="true" size={20} />
            <span>{threshold.label}</span><strong>{threshold.value}</strong><p>{threshold.description}</p>
          </article>
        ))}
      </section>
      <section className="info-panel"><ShieldCheck aria-hidden="true" size={22} /><div><h2>Deduplicated by quota window</h2><p>A threshold is notified once per provider and reset window. Estimated quotas never trigger alerts.</p></div></section>
    </div>
  );
}
