import { invoke } from "@tauri-apps/api/core";
import type { AlertRule, ExportPayload, HistoryPoint, ProviderSnapshot, QuotaWindow, Settings, UsageSummary } from "../types/usage";
import { demoAlertRules, demoHistory, demoProviders, demoSettings, demoSummary } from "./demo-data";

function isTauriRuntime(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

async function command<T>(name: string, args?: Record<string, unknown>): Promise<T> {
  if (import.meta.env.DEV && import.meta.env.VITE_DEMO_MODE === "true") {
    return demoCommand(name, args) as T;
  }
  if (!isTauriRuntime()) {
    throw new Error("Desktop backend unavailable. Run the app through Tauri.");
  }
  return invoke<T>(name, args);
}

function demoCommand(name: string, args?: Record<string, unknown>): unknown {
  switch (name) {
    case "discover_providers": case "get_providers": case "refresh_all": return demoProviders;
    case "refresh_provider": return demoProviders.find((provider) => provider.providerId === args?.providerId) ?? demoProviders[0];
    case "get_usage_summary": return demoSummary;
    case "get_usage_history": return demoHistory;
    case "get_quota_windows": return [];
    case "get_alert_rules": return demoAlertRules;
    case "update_alert_rules": return args?.rules;
    case "get_settings": return demoSettings;
    case "update_settings": return args?.settings;
    case "export_usage": return { format: args?.format, content: "Demo mode does not export provider data." };
    default: throw new Error(`Unsupported demo command: ${name}`);
  }
}

export const monitorApi = {
  discoverProviders: () => command<ProviderSnapshot[]>("discover_providers"),
  getProviders: () => command<ProviderSnapshot[]>("get_providers"),
  refreshProvider: (providerId: string) =>
    command<ProviderSnapshot>("refresh_provider", { providerId }),
  refreshAll: () => command<ProviderSnapshot[]>("refresh_all"),
  getUsageSummary: () => command<UsageSummary>("get_usage_summary"),
  getUsageHistory: (days: 7 | 30 | 90) =>
    command<HistoryPoint[]>("get_usage_history", { days }),
  getQuotaWindows: (providerId: string) =>
    command<QuotaWindow[]>("get_quota_windows", { providerId }),
  getAlertRules: () => command<AlertRule[]>("get_alert_rules"),
  updateAlertRules: (rules: AlertRule[]) =>
    command<AlertRule[]>("update_alert_rules", { rules }),
  getSettings: () => command<Settings>("get_settings"),
  updateSettings: (settings: Settings) =>
    command<Settings>("update_settings", { settings }),
  exportUsage: (format: "csv" | "json", days: 7 | 30 | 90) =>
    command<ExportPayload>("export_usage", { format, days }),
};
