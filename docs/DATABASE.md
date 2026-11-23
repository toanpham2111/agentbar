# Database

SQLite is stored under the OS application-data directory as `usage.db`. On Unix, the directory is restricted to `0700` and the database to `0600`.

Migration `0001_initial.sql` creates providers, installations, accounts, quota snapshots, usage events, daily aggregates, pricing, alert rules/history, collector runs, and app settings.

Usage events have a unique deduplication key. Daily usage is unique by provider, model, and UTC day. Alert history is unique by rule, provider, quota window, threshold, and reset timestamp. Credentials are not stored.
