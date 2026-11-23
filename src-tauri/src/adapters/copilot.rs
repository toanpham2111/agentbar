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
pub struct CopilotAdapter;

#[async_trait]
impl AiProviderAdapter for CopilotAdapter {
    fn id(&self) -> ProviderId {
        ProviderId::Copilot
    }
    async fn detect(&self) -> Result<DetectionResult, AdapterError> {
        Ok(detection_only::detect(
            self.id(),
            "GitHub Copilot",
            &["github-copilot-cli", "copilot"],
        ))
    }
    async fn collect_usage(&self) -> Result<ProviderSnapshot, AdapterError> {
        Ok(detection_only::snapshot(
            self.detect().await?,
            "Copilot personal usage metrics are unavailable without an explicitly authorized API.",
        ))
    }
}
