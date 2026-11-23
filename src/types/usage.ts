export type AdapterStatus =
  | "available"
  | "partially_supported"
  | "not_installed"
  | "authentication_required"
  | "permission_required"
  | "unsupported"
  | "error";

export type DataSource =
  | "official_api"
  | "documented_cli"
  | "local_usage_logs"
  | "estimated"
  | "unavailable";

export interface QuotaWindow {
  id: string;
  label: string;
  usedPercent: number | null;
  remainingPercent: number | null;
  resetsAt: string | null;
  source: DataSource;
  reliable: boolean;
}

export interface TokenUsage {
  input: number;
  output: number;
  cachedInput: number;
  cacheCreation: number;
  reasoning: number;
  total: number;
  source: DataSource;
}

export interface UsageCost {
  amountUsd: number | null;
  kind: "actual" | "api_equivalent_estimate" | "unavailable";
  pricingVersion: string | null;
}

export interface ProviderSnapshot {
  providerId: string;
  displayName: string;
  installed: boolean;
  version: string | null;
  accountId: string | null;
  connection: AdapterStatus;
  quotaWindows: QuotaWindow[];
  tokens: TokenUsage | null;
  cost: UsageCost;
  dataSourceLabel: string;
  lastUpdated: string | null;
  stale: boolean;
  message: string | null;
}

export interface UsageSummary {
  detectedProviders: number;
  connectedProviders: number;
  totalTokens: number | null;
  estimatedCostUsd: number | null;
  activeWarnings: number;
  lastSuccessfulRefresh: string | null;
}

export interface HistoryPoint {
  date: string;
  providerId: string;
  tokens: number;
  estimatedCostUsd: number | null;
}

export interface Settings {
  refreshIntervalMinutes: 1 | 5 | 15 | 30;
  notificationsEnabled: boolean;
  warningThreshold: number;
  criticalThreshold: number;
  startOnLogin: boolean;
  closeToTray: boolean;
  theme: "system" | "light" | "dark";
}

export interface AlertRule {
  id: string;
  providerId: string | null;
  threshold: number;
  enabled: boolean;
}

export interface ExportPayload {
  format: "csv" | "json";
  content: string;
}
