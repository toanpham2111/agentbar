use async_trait::async_trait;

use super::{
    error::AdapterError,
    models::{DetectionResult, ProviderId, ProviderSnapshot},
};

#[async_trait]
pub trait AiProviderAdapter: Send + Sync {
    fn id(&self) -> ProviderId;
    async fn detect(&self) -> Result<DetectionResult, AdapterError>;
    async fn collect_usage(&self) -> Result<ProviderSnapshot, AdapterError>;
}
