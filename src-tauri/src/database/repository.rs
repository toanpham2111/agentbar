use std::{path::Path, str::FromStr};

use chrono::Utc;
use sqlx::{
    Row, SqlitePool,
    sqlite::{SqliteConnectOptions, SqlitePoolOptions},
};
use uuid::Uuid;

use crate::core::{
    error::AppError,
    models::{AppSettings, DataSource, HistoryPoint, ProviderSnapshot},
};

#[derive(Clone)]
pub struct UsageRepository {
    pool: SqlitePool,
}

impl UsageRepository {
    pub async fn open(path: &Path) -> Result<Self, AppError> {
        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent).await?;
        }
        let options = SqliteConnectOptions::from_str(&format!("sqlite://{}", path.display()))?
            .create_if_missing(true)
            .foreign_keys(true);
        let pool = SqlitePoolOptions::new()
            .max_connections(4)
            .connect_with(options)
            .await?;
        sqlx::migrate!("./migrations").run(&pool).await?;
        secure_file_permissions(path)?;
        Ok(Self { pool })
    }

    pub async fn save_snapshot(&self, snapshot: &ProviderSnapshot) -> Result<(), AppError> {
        let mut tx = self.pool.begin().await?;
        let now = Utc::now().timestamp();
        sqlx::query("INSERT INTO providers(id, display_name, adapter_status, created_at_utc, updated_at_utc) VALUES(?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name, adapter_status=excluded.adapter_status, updated_at_utc=excluded.updated_at_utc")
            .bind(snapshot.provider_id.as_str()).bind(&snapshot.display_name).bind(format!("{:?}", snapshot.connection).to_lowercase()).bind(now).bind(now).execute(&mut *tx).await?;

        for quota in &snapshot.quota_windows {
            sqlx::query("INSERT OR IGNORE INTO quota_snapshots(id, provider_id, account_id, window_key, label, used_percent, remaining_percent, resets_at_utc, source, reliable, collected_at_utc) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
                .bind(Uuid::new_v4().to_string()).bind(snapshot.provider_id.as_str()).bind(&snapshot.account_id).bind(&quota.id).bind(&quota.label).bind(quota.used_percent).bind(quota.remaining_percent).bind(quota.resets_at.map(|value| value.timestamp())).bind(data_source(&quota.source)).bind(quota.reliable).bind(now).execute(&mut *tx).await?;
        }

        if let Some(tokens) = &snapshot.tokens {
            let day = Utc::now().format("%Y-%m-%d").to_string();
            sqlx::query("INSERT INTO usage_daily(id, provider_id, model_id, usage_date_utc, input_tokens, output_tokens, cached_input_tokens, total_tokens) VALUES(?, ?, '', ?, ?, ?, ?, ?) ON CONFLICT(provider_id, model_id, usage_date_utc) DO UPDATE SET input_tokens=excluded.input_tokens, output_tokens=excluded.output_tokens, cached_input_tokens=excluded.cached_input_tokens, total_tokens=excluded.total_tokens")
                .bind(Uuid::new_v4().to_string()).bind(snapshot.provider_id.as_str()).bind(day).bind(tokens.input as i64).bind(tokens.output as i64).bind(tokens.cached_input as i64).bind(tokens.total as i64).execute(&mut *tx).await?;
        }
        tx.commit().await?;
        Ok(())
    }

    pub async fn history(&self, days: u16) -> Result<Vec<HistoryPoint>, AppError> {
        if !matches!(days, 7 | 30 | 90) {
            return Err(AppError::Validation(
                "history range must be 7, 30, or 90 days".into(),
            ));
        }
        let rows = sqlx::query("SELECT usage_date_utc, provider_id, SUM(COALESCE(total_tokens, 0)) AS tokens, SUM(estimated_cost_usd) AS cost FROM usage_daily WHERE usage_date_utc >= date('now', ?) GROUP BY usage_date_utc, provider_id ORDER BY usage_date_utc")
            .bind(format!("-{} days", days - 1)).fetch_all(&self.pool).await?;
        rows.into_iter()
            .map(|row| {
                Ok(HistoryPoint {
                    date: row.try_get("usage_date_utc")?,
                    provider_id: row.try_get("provider_id")?,
                    tokens: row.try_get::<i64, _>("tokens")?.max(0) as u64,
                    estimated_cost_usd: row.try_get("cost")?,
                })
            })
            .collect()
    }

    pub async fn get_settings(&self) -> Result<AppSettings, AppError> {
        let value =
            sqlx::query_scalar::<_, String>("SELECT value_json FROM app_settings WHERE key='main'")
                .fetch_optional(&self.pool)
                .await?;
        value
            .map(|raw| {
                serde_json::from_str(&raw)
                    .map_err(|error| AppError::Validation(format!("invalid settings: {error}")))
            })
            .unwrap_or_else(|| Ok(AppSettings::default()))
    }

    pub async fn save_settings(&self, settings: &AppSettings) -> Result<(), AppError> {
        validate_settings(settings)?;
        sqlx::query("INSERT INTO app_settings(key, value_json, updated_at_utc) VALUES('main', ?, ?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at_utc=excluded.updated_at_utc")
            .bind(serde_json::to_string(settings).map_err(|error| AppError::Validation(error.to_string()))?).bind(Utc::now().timestamp()).execute(&self.pool).await?;
        Ok(())
    }
}

pub fn validate_settings(settings: &AppSettings) -> Result<(), AppError> {
    if !matches!(settings.refresh_interval_minutes, 1 | 5 | 15 | 30) {
        return Err(AppError::Validation(
            "refresh interval must be 1, 5, 15, or 30 minutes".into(),
        ));
    }
    if settings.warning_threshold >= settings.critical_threshold
        || settings.critical_threshold > 100
    {
        return Err(AppError::Validation(
            "alert thresholds must be ordered and no greater than 100".into(),
        ));
    }
    if !matches!(settings.theme.as_str(), "system" | "light" | "dark") {
        return Err(AppError::Validation(
            "theme must be system, light, or dark".into(),
        ));
    }
    Ok(())
}

fn data_source(source: &DataSource) -> &'static str {
    match source {
        DataSource::OfficialApi => "official_api",
        DataSource::DocumentedCli => "documented_cli",
        DataSource::LocalUsageLogs => "local_usage_logs",
        DataSource::Estimated => "estimated",
        DataSource::Unavailable => "unavailable",
    }
}

#[cfg(unix)]
fn secure_file_permissions(path: &Path) -> Result<(), AppError> {
    use std::os::unix::fs::PermissionsExt;
    if let Some(parent) = path.parent() {
        std::fs::set_permissions(parent, std::fs::Permissions::from_mode(0o700))?;
    }
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))?;
    Ok(())
}

#[cfg(not(unix))]
fn secure_file_permissions(_path: &Path) -> Result<(), AppError> {
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn migrations_create_all_required_tables() {
        let temp = tempfile::tempdir().unwrap();
        let repo = UsageRepository::open(&temp.path().join("usage.db"))
            .await
            .unwrap();
        let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('providers','installations','accounts','quota_snapshots','usage_events','usage_daily','pricing_catalog','alert_rules','alert_history','collector_runs','app_settings')").fetch_one(&repo.pool).await.unwrap();
        assert_eq!(count, 11);
    }

    #[tokio::test]
    async fn rejects_invalid_settings_boundaries() {
        let settings = AppSettings {
            refresh_interval_minutes: 2,
            ..AppSettings::default()
        };
        assert!(validate_settings(&settings).is_err());
        let settings = AppSettings {
            refresh_interval_minutes: 5,
            warning_threshold: 95,
            critical_threshold: 80,
            ..AppSettings::default()
        };
        assert!(validate_settings(&settings).is_err());
    }

    #[tokio::test]
    async fn empty_history_is_not_fabricated() {
        let temp = tempfile::tempdir().unwrap();
        let repo = UsageRepository::open(&temp.path().join("usage.db"))
            .await
            .unwrap();
        assert!(repo.history(7).await.unwrap().is_empty());
        assert!(repo.history(8).await.is_err());
    }
}
