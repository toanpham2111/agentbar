import type { ProviderSnapshot, UsageSummary } from "../types/usage";

export const providerFixture: ProviderSnapshot = {
  providerId: "codex",
  displayName: "OpenAI Codex",
  installed: true,
  version: null,
  accountId: null,
  connection: "partially_supported",
  quotaWindows: [],
  tokens: {
    input: 900,
    output: 100,
    cachedInput: 0,
    cacheCreation: 0,
    reasoning: 0,
    total: 1000,
    source: "local_usage_logs",
  },
  cost: { amountUsd: null, kind: "unavailable", pricingVersion: null },
  dataSourceLabel: "Local Codex session logs",
  lastUpdated: "2026-11-23T00:00:00Z",
  stale: false,
  message: "Account quota is unavailable through a documented interface.",
};

export const summaryFixture: UsageSummary = {
  detectedProviders: 1,
  connectedProviders: 1,
  totalTokens: 1000,
  estimatedCostUsd: null,
  activeWarnings: 0,
  lastSuccessfulRefresh: "2026-11-23T00:00:00Z",
};
