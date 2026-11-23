mod antigravity;
mod claude;
mod codex;
mod copilot;
mod cursor;
mod detection_only;
mod gemini;

use std::{collections::HashMap, sync::Arc};

use crate::core::{
    adapter::AiProviderAdapter,
    error::AdapterError,
    models::{ProviderId, ProviderSnapshot},
};

pub use antigravity::AntigravityAdapter;
pub use claude::ClaudeAdapter;
pub use codex::CodexAdapter;
pub use copilot::CopilotAdapter;
pub use cursor::CursorAdapter;
pub use gemini::GeminiAdapter;

pub struct ProviderRegistry {
    adapters: HashMap<ProviderId, Arc<dyn AiProviderAdapter>>,
}

impl Default for ProviderRegistry {
    fn default() -> Self {
        Self::new(vec![
            Arc::new(CodexAdapter::default()),
            Arc::new(ClaudeAdapter::default()),
            Arc::new(GeminiAdapter),
            Arc::new(CursorAdapter),
            Arc::new(CopilotAdapter),
            Arc::new(AntigravityAdapter),
        ])
    }
}

impl ProviderRegistry {
    pub fn new(adapters: Vec<Arc<dyn AiProviderAdapter>>) -> Self {
        Self {
            adapters: adapters
                .into_iter()
                .map(|adapter| (adapter.id(), adapter))
                .collect(),
        }
    }

    pub async fn collect_all(&self) -> Vec<ProviderSnapshot> {
        let mut snapshots = Vec::with_capacity(self.adapters.len());
        for adapter in self.adapters.values() {
            match adapter.collect_usage().await {
                Ok(snapshot) => snapshots.push(snapshot),
                Err(error) => snapshots.push(error_snapshot(adapter.id(), error)),
            }
        }
        snapshots.sort_by_key(|snapshot| snapshot.provider_id.as_str());
        snapshots
    }

    pub async fn collect(&self, id: &ProviderId) -> Result<ProviderSnapshot, AdapterError> {
        let adapter = self
            .adapters
            .get(id)
            .ok_or_else(|| AdapterError::Unsupported {
                reason: "unknown provider".into(),
            })?;
        adapter.collect_usage().await
    }
}

fn error_snapshot(provider_id: ProviderId, error: AdapterError) -> ProviderSnapshot {
    let not_installed = matches!(&error, AdapterError::NotInstalled);
    ProviderSnapshot {
        display_name: provider_id.as_str().into(),
        provider_id,
        installed: !not_installed,
        version: None,
        account_id: None,
        connection: if not_installed {
            crate::core::models::AdapterStatus::NotInstalled
        } else {
            crate::core::models::AdapterStatus::Error
        },
        quota_windows: Vec::new(),
        tokens: None,
        cost: crate::core::models::UsageCost::unavailable(),
        data_source_label: "Unavailable".into(),
        last_updated: None,
        stale: false,
        message: Some(error.to_string()),
    }
}
