import { PageHeader } from "../components/layout/PageHeader";
import { ProviderCard } from "../components/providers/ProviderCard";
import { ErrorState, LoadingState } from "../components/ui/QueryState";
import { useProviders, useRefreshProvider } from "../hooks/use-monitor-data";

export function ProvidersPage() {
  const providers = useProviders();
  const refresh = useRefreshProvider();
  return (
    <div className="page-wrap">
      <PageHeader eyebrow="Adapter registry" title="AI Providers" description="Installation detection and supported local usage sources for each provider." />
      {providers.isLoading && <LoadingState />}
      {providers.error && <ErrorState message={providers.error.message} onRetry={() => void providers.refetch()} />}
      <div className="provider-grid">
        {providers.data?.map((provider) => <ProviderCard key={provider.providerId} provider={provider} refreshing={refresh.isPending && refresh.variables === provider.providerId} onRefresh={() => refresh.mutate(provider.providerId)} />)}
      </div>
    </div>
  );
}
