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
pub struct CursorAdapter;

#[async_trait]
impl AiProviderAdapter for CursorAdapter {
    fn id(&self) -> ProviderId {
        ProviderId::Cursor
    }
    async fn detect(&self) -> Result<DetectionResult, AdapterError> {
        Ok(detection_only::detect(
            self.id(),
            "Cursor",
            &["cursor", "Cursor"],
        ))
    }
    async fn collect_usage(&self) -> Result<ProviderSnapshot, AdapterError> {
        Ok(detection_only::snapshot(
            self.detect().await?,
            "Cursor account usage requires a supported provider interface and explicit user authorization.",
        ))
    }
}
