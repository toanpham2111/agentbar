use std::{
    collections::HashSet,
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
pub struct ClaudeAdapter {
    fixture_root: Option<PathBuf>,
}

impl ClaudeAdapter {
    #[cfg(test)]
    fn with_root(root: PathBuf) -> Self {
        Self {
            fixture_root: Some(root),
        }
    }

    fn root(&self) -> Option<PathBuf> {
        self.fixture_root
            .clone()
            .or_else(|| home_dir().map(|home| home.join(".claude/projects")))
    }
}

#[async_trait]
impl AiProviderAdapter for ClaudeAdapter {
    fn id(&self) -> ProviderId {
        ProviderId::Claude
    }

    async fn detect(&self) -> Result<DetectionResult, AdapterError> {
        let executable = find_executable(&["claude", "claude-code"]);
        let logs_exist = self.root().is_some_and(|root| root.is_dir());
        let installed = executable.is_some() || logs_exist;
        Ok(DetectionResult {
            provider_id: self.id(),
            display_name: "Claude Code".into(),
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
                "Claude Code is not installed.",
            ));
        }
        let usage = self
            .root()
            .map(|root| parse_claude_logs(&root))
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
            data_source_label: "Local Claude Code session logs".into(),
            last_updated: Some(Utc::now()),
            stale: false,
            message: Some(
                "Subscription quota is unavailable through a documented interface.".into(),
            ),
        })
    }
}

fn parse_claude_logs(root: &Path) -> Result<Option<TokenUsage>, AdapterError> {
    let files = collect_files(root, "", 5)
        .into_iter()
        .filter(|path| path.extension().is_some_and(|ext| ext == "jsonl"))
        .collect::<Vec<_>>();
    let mut seen = HashSet::new();
    let mut usage = TokenUsage {
        source: DataSource::LocalUsageLogs,
        ..Default::default()
    };
    for path in files {
        let file = File::open(&path).map_err(|error| io_error(&path, error))?;
        for line in BufReader::new(file).lines().map_while(Result::ok) {
            let Ok(value) = serde_json::from_str::<Value>(&line) else {
                continue;
            };
            let Some(data) = value.pointer("/message/usage") else {
                continue;
            };
            let request_id = value.get("requestId").and_then(Value::as_str);
            if request_id.is_some_and(|id| !seen.insert(id.to_owned())) {
                continue;
            }
            usage.input = usage.input.saturating_add(number(data, "input_tokens"));
            usage.output = usage.output.saturating_add(number(data, "output_tokens"));
            usage.cached_input = usage
                .cached_input
                .saturating_add(number(data, "cache_read_input_tokens"));
            usage.cache_creation = usage
                .cache_creation
                .saturating_add(number(data, "cache_creation_input_tokens"));
        }
    }
    usage.total = usage
        .input
        .saturating_add(usage.output)
        .saturating_add(usage.cached_input)
        .saturating_add(usage.cache_creation);
    Ok((usage.total > 0).then_some(usage))
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
    async fn parses_usage_and_deduplicates_request_ids() {
        let temp = tempfile::tempdir().unwrap();
        let project = temp.path().join("demo");
        fs::create_dir_all(&project).unwrap();
        fs::write(project.join("session.jsonl"), concat!(
            "{\"requestId\":\"one\",\"message\":{\"usage\":{\"input_tokens\":10,\"output_tokens\":5,\"cache_read_input_tokens\":2}}}\n",
            "{\"requestId\":\"one\",\"message\":{\"usage\":{\"input_tokens\":10,\"output_tokens\":5}}}\n",
        )).unwrap();
        let snapshot = ClaudeAdapter::with_root(temp.path().to_path_buf())
            .collect_usage()
            .await
            .unwrap();
        assert_eq!(snapshot.tokens.unwrap().total, 17);
        assert!(snapshot.quota_windows.is_empty());
    }

    #[tokio::test]
    async fn malformed_lines_do_not_crash_collection() {
        let temp = tempfile::tempdir().unwrap();
        fs::write(temp.path().join("broken.jsonl"), "not-json\n").unwrap();
        let snapshot = ClaudeAdapter::with_root(temp.path().to_path_buf())
            .collect_usage()
            .await
            .unwrap();
        assert!(snapshot.tokens.is_none());
    }
}
