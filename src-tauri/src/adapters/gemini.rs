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
pub struct GeminiAdapter;

#[async_trait]
impl AiProviderAdapter for GeminiAdapter {
    fn id(&self) -> ProviderId {
        ProviderId::Gemini
    }
    async fn detect(&self) -> Result<DetectionResult, AdapterError> {
        Ok(detection_only::detect(self.id(), "Gemini CLI", &["gemini"]))
    }
    async fn collect_usage(&self) -> Result<ProviderSnapshot, AdapterError> {
        Ok(detection_only::snapshot(
            self.detect().await?,
            "Gemini CLI does not expose a documented non-interactive quota interface.",
        ))
    }
}
