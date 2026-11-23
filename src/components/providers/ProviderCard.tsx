import { Bot, Clock3, Database, RefreshCw } from "lucide-react";
import { formatCost, formatTimestamp, formatTokens } from "../../lib/format";
import type { ProviderSnapshot } from "../../types/usage";
import { Button } from "../ui/Button";
import { StatusBadge } from "../ui/StatusBadge";
import { AntigravityDetails } from "./AntigravityDetails";
import { QuotaMeter } from "./QuotaMeter";

interface ProviderCardProps {
  provider: ProviderSnapshot;
  refreshing?: boolean;
  onRefresh?: () => void;
}

export function ProviderCard({ provider, refreshing = false, onRefresh }: ProviderCardProps) {
  return (
    <article className="provider-card">
      <header className="provider-header">
        <div className="provider-identity">
          <span className="provider-icon"><Bot aria-hidden="true" size={21} /></span>
          <div>
            <h3>{provider.displayName}</h3>
            <p>{provider.version ? `Version ${provider.version}` : "Version unavailable"}</p>
          </div>
        </div>
        <StatusBadge status={provider.connection} />
      </header>

      {provider.message && <p className="provider-message">{provider.message}</p>}

      <div className="quota-list">
        {provider.quotaWindows.length > 0 ? (
          provider.quotaWindows.map((quota) => <QuotaMeter key={quota.id} quota={quota} />)
        ) : (
          <div className="quota-unavailable">
            <span>Account quota</span>
            <strong>Unsupported by provider</strong>
            <small>Installation detection remains available.</small>
          </div>
        )}
      </div>

      <dl className="provider-metrics">
        <div><dt>Tokens</dt><dd>{formatTokens(provider.tokens?.total ?? null)}</dd></div>
        <div><dt>API-equivalent cost</dt><dd>{formatCost(provider.cost.amountUsd)}</dd></div>
      </dl>

      {provider.providerId === "antigravity" && <AntigravityDetails provider={provider} />}

      <footer className="provider-footer">
        <div className="provider-source">
          <span><Database aria-hidden="true" size={14} />{provider.dataSourceLabel}</span>
          <span><Clock3 aria-hidden="true" size={14} />{formatTimestamp(provider.lastUpdated)}</span>
        </div>
        <Button variant="secondary" onClick={onRefresh} disabled={refreshing || !provider.installed}>
          <RefreshCw aria-hidden="true" size={15} className={refreshing ? "spin" : ""} />
          {refreshing ? "Refreshing" : "Refresh"}
        </Button>
      </footer>
    </article>
  );
}
