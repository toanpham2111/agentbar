use crate::{
    adapters::detection_only,
    core::{
        adapter::AiProviderAdapter,
        error::AdapterError,
        models::{DetectionResult, ProviderId, ProviderSnapshot},
    },
};
use async_trait::async_trait;

#[derive(Default)]
pub struct AntigravityAdapter;

#[async_trait]
impl AiProviderAdapter for AntigravityAdapter {
    fn id(&self) -> ProviderId {
        ProviderId::Antigravity
    }
    async fn detect(&self) -> Result<DetectionResult, AdapterError> {
        Ok(detection_only::detect(
            self.id(),
            "Google Antigravity",
            &["agy", "antigravity"],
        ))
    }
    async fn collect_usage(&self) -> Result<ProviderSnapshot, AdapterError> {
        Ok(detection_only::snapshot(
            self.detect().await?,
            "Antigravity usage is unsupported because no documented telemetry interface is available.",
        ))
    }
}
