# KIO Usage Monitor

KIO Usage Monitor is a local-first desktop dashboard for supported usage signals from AI developer tools. It detects installed providers, stores normalized history in SQLite, and makes unsupported data explicit instead of inventing quota values.

> Status: `0.1.0` migration MVP. The React frontend and independently testable Rust core are implemented. Native Linux bundling requires WebKitGTK development packages. Windows and macOS are configured for CI verification and are not claimed as locally verified.

## Features

- Tauri 2 desktop shell with system tray and close-to-tray behavior.
- React and TypeScript dashboard with light/dark system themes.
- Modular adapters for Claude Code, OpenAI Codex, Gemini CLI, Cursor, GitHub Copilot, and Google Antigravity.
- Safe local-log token collection for Claude Code and Codex.
- Explicit partial, unsupported, permission, stale, and error states.
- SQLite migrations and local history repository.
- Configurable 1, 5, 15, and 30 minute refresh intervals.
- Accessible charts, empty states, keyboard focus, and reduced-motion support.

## Provider support

| Provider | Detection | Local token usage | Account quota |
|---|---:|---:|---:|
| OpenAI Codex | Yes | Supported local session logs | Unavailable without a documented interface |
| Claude Code | Yes | Supported local session logs | Unavailable without a documented interface |
| Gemini CLI | Yes | Not yet supported | Unavailable |
| Cursor | Yes | Not supported | Unavailable |
| GitHub Copilot | Yes | Not supported | Requires an explicitly authorized metrics API |
| Google Antigravity | Yes | Not supported | Unavailable |

The application does not read browser cookies, provider credential stores, private OAuth endpoints, or private local RPC tokens.

## Development

Requirements: Node.js 20+, Rust stable 1.90+, and the official Tauri 2 prerequisites for the host platform.

```bash
npm install
npm run typecheck
npm run test
npm run build
cargo test --no-default-features --manifest-path src-tauri/Cargo.toml
npm run tauri dev
```

On Ubuntu, install the official Tauri Linux prerequisites before running the desktop shell:

```bash
sudo apt update
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
```

## Packaging

Run `npm run tauri build`. GitHub Actions builds native bundles on Linux, Windows, and macOS. A successful frontend build alone is not considered native OS verification. Signing and notarization require repository secrets owned by KIO Digital.

## Privacy

All data remains on the device. Credentials, prompts, project source code, browser cookies, and authentication databases are never collected.

## Documentation

- [Product requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Database](docs/DATABASE.md)
- [Provider specification](docs/PROVIDER_SPEC.md)
- [Security](docs/SECURITY.md)
- [Development](docs/DEVELOPMENT.md)
- [Release](docs/RELEASE.md)

## Contributing

Keep adapters independent, preserve unknown values as `null`, add happy-path, boundary, and error tests, and never add a provider integration based on an undocumented authentication bypass.

## License

License selection is pending project-owner approval.
