import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/QueryState";
import { monitorApi } from "../lib/api";
import { formatTokens } from "../lib/format";

export function AnalyticsPage() {
  const [days, setDays] = useState<7 | 30 | 90>(7);
  const history = useQuery({
    queryKey: ["usage-history", days],
    queryFn: () => monitorApi.getUsageHistory(days),
  });

  return (
    <div className="page-wrap">
      <PageHeader
        eyebrow="Historical usage"
        title="Analytics"
        description="Explore locally stored token and API-equivalent cost trends."
        actions={<div className="segmented-control" aria-label="Date range">{([7, 30, 90] as const).map((value) => <Button key={value} variant={days === value ? "primary" : "ghost"} aria-pressed={days === value} onClick={() => setDays(value)}>{value} days</Button>)}</div>}
      />
      {history.isLoading && <LoadingState label="Loading usage history" />}
      {history.error && <ErrorState message={history.error.message} onRetry={() => void history.refetch()} />}
      {history.data?.length === 0 && <EmptyState title="No usage history yet" message="History will appear after a supported provider reports token usage." />}
      {history.data && history.data.length > 0 && (
        <section className="chart-card" aria-label="Token usage trend">
          <div className="chart-heading"><div><span className="eyebrow">Tokens</span><h2>{days}-day trend</h2></div><strong>{formatTokens(history.data.reduce((sum, point) => sum + point.tokens, 0))}</strong></div>
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history.data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <defs><linearGradient id="usage-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7a5af8" stopOpacity={0.32} /><stop offset="100%" stopColor="#7a5af8" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} />
                <YAxis tickFormatter={(value) => formatTokens(Number(value))} tickLine={false} axisLine={false} />
                <Tooltip formatter={(value) => [formatTokens(Number(value)), "Tokens"]} />
                <Area type="monotone" dataKey="tokens" stroke="#7a5af8" strokeWidth={2} fill="url(#usage-fill)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <table className="sr-only"><caption>Token usage history</caption><thead><tr><th>Date</th><th>Provider</th><th>Tokens</th></tr></thead><tbody>{history.data.map((point) => <tr key={`${point.providerId}-${point.date}`}><td>{point.date}</td><td>{point.providerId}</td><td>{point.tokens}</td></tr>)}</tbody></table>
        </section>
      )}
    </div>
  );
}
