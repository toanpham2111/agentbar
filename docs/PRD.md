# Product Requirements

KIO Usage Monitor `0.1.0` is a local-first Tauri desktop application for Linux, Windows 10/11, and macOS. It centralizes supported usage signals from installed AI developer tools without requiring a cloud backend.

## Goals

- Detect Claude Code, Codex, Gemini CLI, Cursor, Copilot, and Antigravity.
- Normalize reliable quota, token, reset, source, freshness, and cost fields.
- Persist local history and expose 7, 30, and 90 day analytics.
- Continue scheduled collection while the window is hidden.
- Notify once per reliable threshold and quota window.

## Non-goals

- Credential harvesting or browser-cookie access.
- Reverse engineering provider authentication or private billing endpoints.
- Running paid inference requests to obtain statistics.
- Presenting API-equivalent estimates as provider invoices.

The MVP is accepted only when frontend tests, Rust tests, native bundle jobs, migration tests, adapter fixture tests, and one verified provider collection path pass. An operating system is only marked verified after its native CI runner succeeds.
