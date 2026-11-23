use crate::core::models::{ProviderId, ProviderSnapshot};

pub fn format_tray_label(snapshots: &[ProviderSnapshot]) -> String {
    let mut installed = snapshots
        .iter()
        .filter(|snapshot| snapshot.installed)
        .collect::<Vec<_>>();
    installed.sort_by_key(|snapshot| provider_rank(&snapshot.provider_id));
    let metrics = installed
        .into_iter()
        .map(|snapshot| {
            format!(
                "{} {}",
                provider_name(&snapshot.provider_id),
                provider_metric(snapshot)
            )
        })
        .collect::<Vec<_>>();

    if metrics.is_empty() {
        "KIO · No providers".into()
    } else {
        metrics.join(" · ")
    }
}

fn provider_rank(provider_id: &ProviderId) -> u8 {
    match provider_id {
        ProviderId::Claude => 0,
        ProviderId::Codex => 1,
        ProviderId::Gemini => 2,
        ProviderId::Cursor => 3,
        ProviderId::Copilot => 4,
        ProviderId::Antigravity => 5,
    }
}

fn provider_name(provider_id: &ProviderId) -> &'static str {
    match provider_id {
        ProviderId::Claude => "Claude",
        ProviderId::Codex => "Codex",
        ProviderId::Gemini => "Gemini",
        ProviderId::Cursor => "Cursor",
        ProviderId::Copilot => "Copilot",
        ProviderId::Antigravity => "Agy",
    }
}

fn provider_metric(snapshot: &ProviderSnapshot) -> String {
    let used_percent = snapshot.quota_windows.iter().find_map(|quota| {
        if !quota.reliable {
            return None;
        }
        quota
            .used_percent
            .or_else(|| quota.remaining_percent.map(|remaining| 100.0 - remaining))
    });
    if let Some(percent) = used_percent {
        return format!("{:.0}%", percent.clamp(0.0, 100.0));
    }
    snapshot
        .tokens
        .as_ref()
        .map(|tokens| format!("{}t", compact_number(tokens.total)))
        .unwrap_or_else(|| "—".into())
}

fn compact_number(value: u64) -> String {
    match value {
        0..=999 => value.to_string(),
        1_000..=999_999 => compact_scaled(value, 1_000, "K"),
        1_000_000..=999_999_999 => compact_scaled(value, 1_000_000, "M"),
        _ => compact_scaled(value, 1_000_000_000, "B"),
    }
}

fn compact_scaled(value: u64, divisor: u64, suffix: &str) -> String {
    let scaled = value as f64 / divisor as f64;
    if scaled >= 10.0 {
        format!("{scaled:.0}{suffix}")
    } else {
        format!("{scaled:.1}{suffix}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::models::{
        AdapterStatus, CostKind, DataSource, QuotaWindow, TokenUsage, UsageCost,
    };

    fn snapshot(provider_id: ProviderId) -> ProviderSnapshot {
        ProviderSnapshot {
            display_name: provider_name(&provider_id).into(),
            provider_id,
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
            data_source_label: "Test".into(),
            last_updated: None,
            stale: false,
            message: None,
        }
    }

    #[test]
    fn displays_reliable_quota_before_token_usage() {
        let mut claude = snapshot(ProviderId::Claude);
        claude.tokens = Some(TokenUsage {
            total: 12_400,
            ..Default::default()
        });
        claude.quota_windows.push(QuotaWindow {
            id: "weekly".into(),
            label: "Weekly".into(),
            used_percent: Some(42.4),
            remaining_percent: None,
            resets_at: None,
            source: DataSource::OfficialApi,
            reliable: true,
        });

        assert_eq!(format_tray_label(&[claude]), "Claude 42%");
    }

    #[test]
    fn displays_compact_local_token_usage_when_quota_is_unknown() {
        let mut codex = snapshot(ProviderId::Codex);
        codex.tokens = Some(TokenUsage {
            total: 1_250,
            source: DataSource::LocalUsageLogs,
            ..Default::default()
        });
        let antigravity = snapshot(ProviderId::Antigravity);

        assert_eq!(
            format_tray_label(&[codex, antigravity]),
            "Codex 1.2Kt · Agy —"
        );
    }

    #[test]
    fn handles_empty_and_not_installed_provider_lists() {
        let mut cursor = snapshot(ProviderId::Cursor);
        cursor.installed = false;

        assert_eq!(format_tray_label(&[]), "KIO · No providers");
        assert_eq!(format_tray_label(&[cursor]), "KIO · No providers");
    }

    #[test]
    fn uses_legacy_provider_order_and_compacts_billions() {
        let mut claude = snapshot(ProviderId::Claude);
        claude.tokens = Some(TokenUsage {
            total: 1_348_000_000,
            ..Default::default()
        });
        let antigravity = snapshot(ProviderId::Antigravity);

        assert_eq!(
            format_tray_label(&[antigravity, claude]),
            "Claude 1.3Bt · Agy —"
        );
    }
}
