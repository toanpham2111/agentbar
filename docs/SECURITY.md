# Security

- Local-first SQLite storage; no cloud backend.
- Minimal Tauri capability grants: `core:default` only.
- No unrestricted shell, HTTP, or filesystem commands exposed to React.
- No browser cookies, authentication databases, plaintext credentials, prompts, or project source collection.
- No automatic provider configuration changes or OAuth token refresh.
- Provider IDs, history ranges, thresholds, themes, and scheduler intervals are validated.
- Logs and frontend payloads exclude account email and access tokens.
- Native notifications only use reliable quota sources and are deduplicated.

Dependency and SAST scans run in CI. Release signing keys belong in GitHub encrypted secrets and must never be committed.
