use std::{collections::HashMap, sync::Arc};

use tokio::sync::Mutex;

use crate::{
    adapters::ProviderRegistry,
    core::{
        error::AppError,
        models::{AdapterStatus, ProviderId, ProviderSnapshot, UsageSummary},
    },
    database::repository::UsageRepository,
};

#[derive(Clone)]
pub struct CollectorService {
    registry: Arc<ProviderRegistry>,
    repository: UsageRepository,
    provider_locks: Arc<HashMap<ProviderId, Arc<Mutex<()>>>>,
}

impl CollectorService {
    pub fn new(registry: Arc<ProviderRegistry>, repository: UsageRepository) -> Self {
        let provider_locks = [
            ProviderId::Claude,
            ProviderId::Codex,
            ProviderId::Gemini,
            ProviderId::Cursor,
            ProviderId::Copilot,
            ProviderId::Antigravity,
        ]
        .into_iter()
        .map(|id| (id, Arc::new(Mutex::new(()))))
        .collect();
        Self {
            registry,
            repository,
            provider_locks: Arc::new(provider_locks),
        }
    }

    pub async fn refresh_provider(
        &self,
        provider_id: ProviderId,
    ) -> Result<ProviderSnapshot, AppError> {
        let lock = self
            .provider_locks
            .get(&provider_id)
            .ok_or_else(|| AppError::Validation("unknown provider".into()))?;
        let _guard = lock
            .try_lock()
            .map_err(|_| AppError::Validation("provider refresh already in progress".into()))?;
        let snapshot = self.registry.collect(&provider_id).await?;
        self.repository.save_snapshot(&snapshot).await?;
        Ok(snapshot)
    }

    pub async fn refresh_all(&self) -> Vec<ProviderSnapshot> {
        let snapshots = self.registry.collect_all().await;
        for snapshot in &snapshots {
            let _ = self.repository.save_snapshot(snapshot).await;
        }
        snapshots
    }

    pub async fn current(&self) -> Vec<ProviderSnapshot> {
        self.registry.collect_all().await
    }

    pub fn summary(snapshots: &[ProviderSnapshot]) -> UsageSummary {
        let detected = snapshots
            .iter()
            .filter(|snapshot| snapshot.installed)
            .collect::<Vec<_>>();
        let token_values = detected
            .iter()
            .filter_map(|snapshot| snapshot.tokens.as_ref().map(|tokens| tokens.total))
            .collect::<Vec<_>>();
        let cost_values = detected
            .iter()
            .filter_map(|snapshot| snapshot.cost.amount_usd)
            .collect::<Vec<_>>();
        UsageSummary {
            detected_providers: detected.len(),
            connected_providers: detected
                .iter()
                .filter(|snapshot| {
                    matches!(
                        snapshot.connection,
                        AdapterStatus::Available | AdapterStatus::PartiallySupported
                    )
                })
                .count(),
            total_tokens: (!token_values.is_empty()).then(|| token_values.iter().sum()),
            estimated_cost_usd: (!cost_values.is_empty()).then(|| cost_values.iter().sum()),
            active_warnings: detected
                .iter()
                .flat_map(|snapshot| &snapshot.quota_windows)
                .filter(|quota| {
                    quota.reliable && quota.used_percent.is_some_and(|value| value >= 80.0)
                })
                .count(),
            last_successful_refresh: detected
                .iter()
                .filter_map(|snapshot| snapshot.last_updated)
                .max(),
        }
    }
}

pub fn parse_provider_id(value: &str) -> Result<ProviderId, AppError> {
    match value {
        "claude" => Ok(ProviderId::Claude),
        "codex" => Ok(ProviderId::Codex),
        "gemini" => Ok(ProviderId::Gemini),
        "cursor" => Ok(ProviderId::Cursor),
        "copilot" => Ok(ProviderId::Copilot),
        "antigravity" => Ok(ProviderId::Antigravity),
        _ => Err(AppError::Validation("unknown provider id".into())),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::models::{CostKind, UsageCost};

    #[test]
    fn summary_preserves_unknown_values() {
        let snapshots = vec![ProviderSnapshot {
            provider_id: ProviderId::Cursor,
            display_name: "Cursor".into(),
            installed: true,
            version: None,
            account_id: None,
            connection: AdapterStatus::PartiallySupported,
            quota_windows: Vec::new(),
            tokens: None,
            cost: UsageCost {
                amount_usd: None,
                kind: CostKind::Unavailable,
                pricing_version: None,
            },
            data_source_label: "Detection".into(),
            last_updated: None,
            stale: false,
            message: None,
        }];
        let summary = CollectorService::summary(&snapshots);
        assert_eq!(summary.total_tokens, None);
        assert_eq!(summary.estimated_cost_usd, None);
    }

    #[test]
    fn rejects_unknown_provider_ids() {
        assert!(parse_provider_id("other").is_err());
    }
}
