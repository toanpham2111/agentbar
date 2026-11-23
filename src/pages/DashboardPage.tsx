import { AlertTriangle, Bot, CircleDollarSign, Clock3, RefreshCw, Waypoints } from "lucide-react";
import { ProviderCard } from "../components/providers/ProviderCard";
import { StatCard } from "../components/dashboard/StatCard";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { ErrorState, LoadingState } from "../components/ui/QueryState";
import { useProviders, useRefreshAll, useRefreshProvider, useUsageSummary } from "../hooks/use-monitor-data";
import { formatCost, formatTimestamp, formatTokens } from "../lib/format";

export function DashboardPage() {
  const providers = useProviders();
  const summary = useUsageSummary();
  const refreshAll = useRefreshAll();
  const refreshProvider = useRefreshProvider();

  const retry = () => {
    void providers.refetch();
    void summary.refetch();
  };

  return (
    <div className="page-wrap">
      <PageHeader
        eyebrow="Local-first telemetry"
        title="Usage overview"
        description="Verified usage signals from AI developer tools installed on this device."
        actions={
          <Button onClick={() => refreshAll.mutate()} disabled={refreshAll.isPending}>
            <RefreshCw aria-hidden="true" size={16} className={refreshAll.isPending ? "spin" : ""} />
            {refreshAll.isPending ? "Refreshing" : "Refresh all"}
          </Button>
        }
      />

      {(providers.isLoading || summary.isLoading) && <LoadingState />}
      {(providers.error || summary.error) && (
        <ErrorState
          message={(providers.error ?? summary.error)?.message ?? "The desktop backend did not respond."}
          onRetry={retry}
        />
      )}

      {summary.data && (
        <section className="stats-grid" aria-label="Usage summary">
          <StatCard label="Detected providers" value={String(summary.data.detectedProviders)} helper="Installed on this device" icon={Bot} tone="primary" />
          <StatCard label="Connected" value={String(summary.data.connectedProviders)} helper="Reporting supported data" icon={Waypoints} tone="success" />
          <StatCard label="Total tokens" value={formatTokens(summary.data.totalTokens)} helper="Known local usage only" icon={Clock3} />
          <StatCard label="Estimated cost" value={formatCost(summary.data.estimatedCostUsd)} helper="API-equivalent estimate" icon={CircleDollarSign} />
          <StatCard label="Active warnings" value={String(summary.data.activeWarnings)} helper="Reliable quota sources only" icon={AlertTriangle} tone="warning" />
          <StatCard label="Last refresh" value={formatTimestamp(summary.data.lastSuccessfulRefresh)} helper="Most recent successful run" icon={RefreshCw} />
        </section>
      )}

      {providers.data && (
        <section className="section-block">
          <div className="section-heading-row">
            <div><span className="eyebrow">Providers</span><h2>Connection and quota status</h2></div>
            <span className="section-note">Unavailable values are never replaced with zero.</span>
          </div>
          <div className="provider-grid">
            {providers.data.map((provider) => (
              <ProviderCard
                key={provider.providerId}
                provider={provider}
                refreshing={refreshProvider.isPending && refreshProvider.variables === provider.providerId}
                onRefresh={() => refreshProvider.mutate(provider.providerId)}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
