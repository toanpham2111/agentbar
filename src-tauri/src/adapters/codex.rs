use std::{
    fs::File,
    io::{BufRead, BufReader},
    path::{Path, PathBuf},
};

use async_trait::async_trait;
use chrono::Utc;
use serde_json::Value;

use crate::{
    core::{
        adapter::AiProviderAdapter,
        error::AdapterError,
        models::{
            AdapterStatus, DataSource, DetectionResult, ProviderId, ProviderSnapshot, TokenUsage,
            UsageCost,
        },
    },
    platform::{
        discovery::{collect_files, find_executable},
        paths::home_dir,
    },
};

#[derive(Default)]
pub struct CodexAdapter {
    fixture_root: Option<PathBuf>,
}

impl CodexAdapter {
    #[cfg(test)]
    fn with_root(root: PathBuf) -> Self {
        Self {
            fixture_root: Some(root),
        }
    }
    fn root(&self) -> Option<PathBuf> {
        self.fixture_root
            .clone()
            .or_else(|| home_dir().map(|home| home.join(".codex/sessions")))
    }
}

#[async_trait]
impl AiProviderAdapter for CodexAdapter {
    fn id(&self) -> ProviderId {
        ProviderId::Codex
    }

    async fn detect(&self) -> Result<DetectionResult, AdapterError> {
        let executable = find_executable(&["codex"]);
        let logs_exist = self.root().is_some_and(|root| root.is_dir());
        let installed = executable.is_some() || logs_exist;
        Ok(DetectionResult {
            provider_id: self.id(),
            display_name: "OpenAI Codex".into(),
            installed,
            executable_path: executable.map(|path| path.to_string_lossy().into_owned()),
            version: None,
            status: if installed {
                AdapterStatus::PartiallySupported
            } else {
                AdapterStatus::NotInstalled
            },
        })
    }

    async fn collect_usage(&self) -> Result<ProviderSnapshot, AdapterError> {
        let detection = self.detect().await?;
        if !detection.installed {
            return Ok(ProviderSnapshot::unsupported(
                detection,
                "OpenAI Codex is not installed.",
            ));
        }
        let usage = self
            .root()
            .map(|root| parse_codex_logs(&root))
            .transpose()?
            .flatten();
        Ok(ProviderSnapshot {
            provider_id: detection.provider_id,
            display_name: detection.display_name,
            installed: true,
            version: detection.version,
            account_id: None,
            connection: AdapterStatus::PartiallySupported,
            quota_windows: Vec::new(),
            tokens: usage,
            cost: UsageCost::unavailable(),
            data_source_label: "Local Codex session logs".into(),
            last_updated: Some(Utc::now()),
            stale: false,
            message: Some(
                "Account quota is unavailable through a documented non-interactive interface."
                    .into(),
            ),
        })
    }
}

fn parse_codex_logs(root: &Path) -> Result<Option<TokenUsage>, AdapterError> {
    let files = collect_files(root, "", 8)
        .into_iter()
        .filter(|path| path.extension().is_some_and(|ext| ext == "jsonl"));
    let mut aggregate = TokenUsage {
        source: DataSource::LocalUsageLogs,
        ..Default::default()
    };
    for path in files {
        let file = File::open(&path).map_err(|error| io_error(&path, error))?;
        let mut file_max = TokenUsage {
            source: DataSource::LocalUsageLogs,
            ..Default::default()
        };
        for line in BufReader::new(file).lines().map_while(Result::ok) {
            let Ok(value) = serde_json::from_str::<Value>(&line) else {
                continue;
            };
            let Some(data) = value.pointer("/payload/info/total_token_usage") else {
                continue;
            };
            let candidate = TokenUsage {
                input: number(data, "input_tokens"),
                output: number(data, "output_tokens"),
                cached_input: number(data, "cached_input_tokens"),
                cache_creation: 0,
                reasoning: number(data, "reasoning_output_tokens"),
                total: number(data, "total_tokens"),
                source: DataSource::LocalUsageLogs,
            };
            if candidate.total >= file_max.total {
                file_max = candidate;
            }
        }
        aggregate.input = aggregate.input.saturating_add(file_max.input);
        aggregate.output = aggregate.output.saturating_add(file_max.output);
        aggregate.cached_input = aggregate.cached_input.saturating_add(file_max.cached_input);
        aggregate.reasoning = aggregate.reasoning.saturating_add(file_max.reasoning);
        aggregate.total = aggregate.total.saturating_add(file_max.total);
    }
    Ok((aggregate.total > 0).then_some(aggregate))
}

fn number(value: &Value, key: &str) -> u64 {
    value.get(key).and_then(Value::as_u64).unwrap_or(0)
}
fn io_error(path: &Path, error: std::io::Error) -> AdapterError {
    if error.kind() == std::io::ErrorKind::PermissionDenied {
        AdapterError::PermissionDenied {
            path: path.display().to_string(),
        }
    } else {
        AdapterError::Collection(error.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[tokio::test]
    async fn uses_latest_cumulative_usage_per_session_file() {
        let temp = tempfile::tempdir().unwrap();
        fs::write(temp.path().join("rollout.jsonl"), concat!(
            "{\"payload\":{\"info\":{\"total_token_usage\":{\"input_tokens\":10,\"output_tokens\":2,\"total_tokens\":12}}}}\n",
            "{\"payload\":{\"info\":{\"total_token_usage\":{\"input_tokens\":20,\"output_tokens\":5,\"total_tokens\":25}}}}\n",
        )).unwrap();
        let snapshot = CodexAdapter::with_root(temp.path().to_path_buf())
            .collect_usage()
            .await
            .unwrap();
        assert_eq!(snapshot.tokens.unwrap().total, 25);
        assert!(snapshot.quota_windows.is_empty());
    }

    #[tokio::test]
    async fn empty_log_returns_unknown_tokens_not_zero() {
        let temp = tempfile::tempdir().unwrap();
        fs::write(temp.path().join("rollout.jsonl"), "\n").unwrap();
        let snapshot = CodexAdapter::with_root(temp.path().to_path_buf())
            .collect_usage()
            .await
            .unwrap();
        assert!(snapshot.tokens.is_none());
    }
}
