import { Binary, CircleOff, Database, ShieldCheck } from "lucide-react";
import { formatTimestamp } from "../../lib/format";
import type { ProviderSnapshot } from "../../types/usage";

export function AntigravityDetails({ provider }: { provider: ProviderSnapshot }) {
  const detectionLabel = provider.installed ? "Detected" : "Not detected";

  return (
    <section className="antigravity-details" aria-labelledby="antigravity-details-title">
      <div className="provider-detail-heading">
        <div>
          <span className="eyebrow">Provider detail</span>
          <h4 id="antigravity-details-title">Google Antigravity</h4>
        </div>
        <span className={`detection-state ${provider.installed ? "detected" : "not-detected"}`}>
          {detectionLabel}
        </span>
      </div>

      <dl className="capability-grid">
        <div>
          <dt><Binary aria-hidden="true" size={16} />CLI detection</dt>
          <dd>{detectionLabel}</dd>
          <small>Checks the documented binary aliases <code>agy</code> and <code>antigravity</code>.</small>
        </div>
        <div>
          <dt><Database aria-hidden="true" size={16} />Usage telemetry</dt>
          <dd>Unavailable</dd>
          <small>No documented non-interactive usage interface is currently available.</small>
        </div>
        <div>
          <dt><CircleOff aria-hidden="true" size={16} />Quota and cost</dt>
          <dd>Unavailable</dd>
          <small>KIO does not infer quota, tokens, reset windows, or account cost.</small>
        </div>
        <div>
          <dt><ShieldCheck aria-hidden="true" size={16} />Privacy boundary</dt>
          <dd>Local detection only</dd>
          <small>Private RPC ports, CSRF tokens, browser cookies, and credentials are never read.</small>
        </div>
      </dl>

      <div className="provider-detail-meta">
        <span>Source: {provider.dataSourceLabel}</span>
        <span>Last checked: {formatTimestamp(provider.lastUpdated)}</span>
      </div>
    </section>
  );
}
