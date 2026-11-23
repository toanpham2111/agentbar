use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProviderId {
    Claude,
    Codex,
    Gemini,
    Cursor,
    Copilot,
    Antigravity,
}

impl ProviderId {
    pub const fn as_str(&self) -> &'static str {
        match self {
            Self::Claude => "claude",
            Self::Codex => "codex",
            Self::Gemini => "gemini",
            Self::Cursor => "cursor",
            Self::Copilot => "copilot",
            Self::Antigravity => "antigravity",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AdapterStatus {
    Available,
    PartiallySupported,
    NotInstalled,
    AuthenticationRequired,
    PermissionRequired,
    Unsupported,
    Error,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DataSource {
    OfficialApi,
    DocumentedCli,
    LocalUsageLogs,
    Estimated,
    #[default]
    Unavailable,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct QuotaWindow {
    pub id: String,
    pub label: String,
    pub used_percent: Option<f64>,
    pub remaining_percent: Option<f64>,
    pub resets_at: Option<DateTime<Utc>>,
    pub source: DataSource,
    pub reliable: bool,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TokenUsage {
    pub input: u64,
    pub output: u64,
    pub cached_input: u64,
    pub cache_creation: u64,
    pub reasoning: u64,
    pub total: u64,
    pub source: DataSource,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CostKind {
    Actual,
    ApiEquivalentEstimate,
    Unavailable,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UsageCost {
    pub amount_usd: Option<f64>,
    pub kind: CostKind,
    pub pricing_version: Option<String>,
}

impl UsageCost {
    pub fn unavailable() -> Self {
        Self {
            amount_usd: None,
            kind: CostKind::Unavailable,
            pricing_version: None,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DetectionResult {
    pub provider_id: ProviderId,
    pub display_name: String,
    pub installed: bool,
    pub executable_path: Option<String>,
    pub version: Option<String>,
    pub status: AdapterStatus,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProviderSnapshot {
    pub provider_id: ProviderId,
    pub display_name: String,
    pub installed: bool,
    pub version: Option<String>,
    pub account_id: Option<String>,
    pub connection: AdapterStatus,
    pub quota_windows: Vec<QuotaWindow>,
    pub tokens: Option<TokenUsage>,
    pub cost: UsageCost,
    pub data_source_label: String,
    pub last_updated: Option<DateTime<Utc>>,
    pub stale: bool,
    pub message: Option<String>,
}

impl ProviderSnapshot {
    pub fn unsupported(detection: DetectionResult, message: impl Into<String>) -> Self {
        let installed = detection.installed;
        Self {
            provider_id: detection.provider_id,
            display_name: detection.display_name,
            installed,
            version: detection.version,
            account_id: None,
            connection: if installed {
                AdapterStatus::PartiallySupported
            } else {
                AdapterStatus::NotInstalled
            },
            quota_windows: Vec::new(),
            tokens: None,
            cost: UsageCost::unavailable(),
            data_source_label: "Installation detection".into(),
            last_updated: None,
            stale: false,
            message: Some(message.into()),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UsageSummary {
    pub detected_providers: usize,
    pub connected_providers: usize,
    pub total_tokens: Option<u64>,
    pub estimated_cost_usd: Option<f64>,
    pub active_warnings: usize,
    pub last_successful_refresh: Option<DateTime<Utc>>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HistoryPoint {
    pub date: String,
    pub provider_id: String,
    pub tokens: u64,
    pub estimated_cost_usd: Option<f64>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    pub refresh_interval_minutes: u16,
    pub notifications_enabled: bool,
    pub warning_threshold: u8,
    pub critical_threshold: u8,
    pub start_on_login: bool,
    pub close_to_tray: bool,
    pub theme: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AlertRule {
    pub id: String,
    pub provider_id: Option<String>,
    pub threshold: u8,
    pub enabled: bool,
}

impl AlertRule {
    pub fn defaults() -> Vec<Self> {
        [80, 95, 100]
            .into_iter()
            .map(|threshold| Self {
                id: format!("global-{threshold}"),
                provider_id: None,
                threshold,
                enabled: true,
            })
            .collect()
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportPayload {
    pub format: String,
    pub content: String,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            refresh_interval_minutes: 5,
            notifications_enabled: true,
            warning_threshold: 80,
            critical_threshold: 95,
            start_on_login: false,
            close_to_tray: true,
            theme: "system".into(),
        }
    }
}
