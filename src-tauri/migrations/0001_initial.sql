PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS providers (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  adapter_status TEXT NOT NULL,
  created_at_utc INTEGER NOT NULL,
  updated_at_utc INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS installations (
  id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
  executable_path TEXT NOT NULL,
  version TEXT,
  detected_at_utc INTEGER NOT NULL,
  UNIQUE(provider_id, executable_path)
);

CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
  opaque_account_id TEXT,
  connection_status TEXT NOT NULL,
  created_at_utc INTEGER NOT NULL,
  updated_at_utc INTEGER NOT NULL,
  UNIQUE(provider_id, opaque_account_id)
);

CREATE TABLE IF NOT EXISTS quota_snapshots (
  id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
  account_id TEXT,
  window_key TEXT NOT NULL,
  label TEXT NOT NULL,
  used_percent REAL,
  remaining_percent REAL,
  resets_at_utc INTEGER,
  source TEXT NOT NULL,
  reliable INTEGER NOT NULL CHECK(reliable IN (0, 1)),
  collected_at_utc INTEGER NOT NULL,
  UNIQUE(provider_id, account_id, window_key, collected_at_utc)
);

CREATE TABLE IF NOT EXISTS usage_events (
  id TEXT PRIMARY KEY,
  dedupe_key TEXT NOT NULL UNIQUE,
  provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
  model_id TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cached_input_tokens INTEGER,
  cache_creation_tokens INTEGER,
  reasoning_tokens INTEGER,
  total_tokens INTEGER,
  source TEXT NOT NULL,
  occurred_at_utc INTEGER NOT NULL,
  collected_at_utc INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_daily (
  id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
  model_id TEXT NOT NULL DEFAULT '',
  usage_date_utc TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  cached_input_tokens INTEGER,
  total_tokens INTEGER,
  estimated_cost_usd REAL,
  pricing_version TEXT,
  UNIQUE(provider_id, model_id, usage_date_utc)
);

CREATE TABLE IF NOT EXISTS pricing_catalog (
  id TEXT PRIMARY KEY,
  provider_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  version TEXT NOT NULL,
  input_per_million REAL,
  output_per_million REAL,
  cached_input_per_million REAL,
  effective_from_utc INTEGER NOT NULL,
  source_url TEXT NOT NULL,
  UNIQUE(provider_id, model_id, version)
);

CREATE TABLE IF NOT EXISTS alert_rules (
  id TEXT PRIMARY KEY,
  provider_id TEXT,
  threshold INTEGER NOT NULL CHECK(threshold BETWEEN 1 AND 100),
  enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
  created_at_utc INTEGER NOT NULL,
  updated_at_utc INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_history (
  id TEXT PRIMARY KEY,
  rule_id TEXT NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
  provider_id TEXT NOT NULL,
  window_key TEXT NOT NULL,
  threshold INTEGER NOT NULL,
  reset_at_utc INTEGER NOT NULL DEFAULT 0,
  notified_at_utc INTEGER NOT NULL,
  UNIQUE(rule_id, provider_id, window_key, threshold, reset_at_utc)
);

CREATE TABLE IF NOT EXISTS collector_runs (
  id TEXT PRIMARY KEY,
  provider_id TEXT,
  status TEXT NOT NULL,
  started_at_utc INTEGER NOT NULL,
  completed_at_utc INTEGER,
  error_code TEXT,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at_utc INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_events_provider_time ON usage_events(provider_id, occurred_at_utc);
CREATE INDEX IF NOT EXISTS idx_usage_daily_provider_date ON usage_daily(provider_id, usage_date_utc);
CREATE INDEX IF NOT EXISTS idx_quota_provider_collected ON quota_snapshots(provider_id, collected_at_utc);
CREATE INDEX IF NOT EXISTS idx_collector_status_started ON collector_runs(status, started_at_utc);
