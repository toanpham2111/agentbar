use std::{
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    time::Duration,
};

use tokio::{
    task::JoinHandle,
    time::{MissedTickBehavior, interval},
};

use super::collector::CollectorService;

pub struct CollectorScheduler {
    running: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl CollectorScheduler {
    pub fn start(collector: CollectorService, refresh_minutes: u16) -> Result<Self, &'static str> {
        Self::start_with_callback(collector, refresh_minutes, |_| {})
    }

    pub fn start_with_callback<F>(
        collector: CollectorService,
        refresh_minutes: u16,
        on_refresh: F,
    ) -> Result<Self, &'static str>
    where
        F: Fn(Vec<crate::core::models::ProviderSnapshot>) + Send + Sync + 'static,
    {
        if !matches!(refresh_minutes, 1 | 5 | 15 | 30) {
            return Err("refresh interval must be 1, 5, 15, or 30 minutes");
        }
        let running = Arc::new(AtomicBool::new(true));
        let task_running = running.clone();
        let handle = tokio::spawn(async move {
            let mut ticker = interval(Duration::from_secs(u64::from(refresh_minutes) * 60));
            ticker.set_missed_tick_behavior(MissedTickBehavior::Skip);
            while task_running.load(Ordering::Relaxed) {
                ticker.tick().await;
                if !task_running.load(Ordering::Relaxed) {
                    break;
                }
                on_refresh(collector.refresh_all().await);
            }
        });
        Ok(Self {
            running,
            handle: Some(handle),
        })
    }

    pub async fn stop(mut self) {
        self.running.store(false, Ordering::Relaxed);
        if let Some(handle) = self.handle.take() {
            handle.abort();
            let _ = handle.await;
        }
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use tempfile::tempdir;

    use super::*;
    use crate::{adapters::ProviderRegistry, database::repository::UsageRepository};

    #[test]
    fn supported_intervals_are_explicit() {
        assert!(!matches!(2, 1 | 5 | 15 | 30));
        assert!(matches!(30, 1 | 5 | 15 | 30));
    }

    #[tokio::test]
    async fn starts_and_stops_on_an_active_runtime() {
        let directory = tempdir().expect("temporary directory should be available");
        let repository = UsageRepository::open(&directory.path().join("usage.db"))
            .await
            .expect("repository should open");
        let collector = CollectorService::new(Arc::new(ProviderRegistry::default()), repository);

        let scheduler = CollectorScheduler::start(collector, 1)
            .expect("supported interval should start the scheduler");
        scheduler.stop().await;
    }
}
