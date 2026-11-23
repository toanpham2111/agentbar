# Architecture

```text
React UI → typed Tauri commands → collector services → adapter registry
                                  ↘ SQLite repository
Tokio scheduler → collector → normalized snapshot → Tauri events
System tray → open/settings/refresh/quit
```

The React frontend never receives credentials or unrestricted shell/filesystem access. Provider adapters own detection and collection. Unknown data remains optional and each quota carries its source and reliability flag.

The Rust core compiles separately from the desktop feature so adapter, pricing, validation, and SQLite behavior can be tested without a webview. The Tauri layer contains native commands, events, tray handling, notification/autostart plugins, and application paths.

The legacy Python AgentBar remains only as migration reference. Its private OAuth/RPC collection paths are not part of the production architecture.
