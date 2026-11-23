import type { AlertRule, HistoryPoint, ProviderSnapshot, Settings, UsageSummary } from "../types/usage";

const now = new Date().toISOString();

export const demoProviders: ProviderSnapshot[] = [
  {
    providerId: "codex", displayName: "OpenAI Codex", installed: true, version: "demo", accountId: null,
    connection: "partially_supported", quotaWindows: [],
    tokens: { input: 842_000, output: 126_000, cachedInput: 410_000, cacheCreation: 0, reasoning: 32_000, total: 1_410_000, source: "local_usage_logs" },
    cost: { amountUsd: null, kind: "unavailable", pricingVersion: null }, dataSourceLabel: "Demo fixture — not provider data", lastUpdated: now, stale: false,
    message: "Account quota is unavailable through a documented interface.",
  },
  {
    providerId: "claude", displayName: "Claude Code", installed: true, version: "demo", accountId: null,
    connection: "partially_supported", quotaWindows: [],
    tokens: { input: 610_000, output: 84_000, cachedInput: 290_000, cacheCreation: 48_000, reasoning: 0, total: 1_032_000, source: "local_usage_logs" },
    cost: { amountUsd: null, kind: "unavailable", pricingVersion: null }, dataSourceLabel: "Demo fixture — not provider data", lastUpdated: now, stale: false,
    message: "Subscription quota is unavailable through a documented interface.",
  },
  {
    providerId: "cursor", displayName: "Cursor", installed: true, version: null, accountId: null,
    connection: "partially_supported", quotaWindows: [], tokens: null,
    cost: { amountUsd: null, kind: "unavailable", pricingVersion: null }, dataSourceLabel: "Demo fixture — not provider data", lastUpdated: null, stale: false,
    message: "Installation detected. Account usage is unsupported without explicit authorization.",
  },
];

export const demoSummary: UsageSummary = {
  detectedProviders: 3, connectedProviders: 3, totalTokens: 2_442_000,
  estimatedCostUsd: null, activeWarnings: 0, lastSuccessfulRefresh: now,
};

export const demoHistory: HistoryPoint[] = Array.from({ length: 7 }, (_, index) => ({
  date: new Date(Date.now() - (6 - index) * 86_400_000).toISOString().slice(0, 10),
  providerId: index % 2 ? "claude" : "codex",
  tokens: 120_000 + index * 34_000,
  estimatedCostUsd: null,
}));

export const demoSettings: Settings = {
  refreshIntervalMinutes: 5, notificationsEnabled: true, warningThreshold: 80,
  criticalThreshold: 95, startOnLogin: false, closeToTray: true, theme: "system",
};

export const demoAlertRules: AlertRule[] = [80, 95, 100].map((threshold) => ({ id: `global-${threshold}`, providerId: null, threshold, enabled: true }));
