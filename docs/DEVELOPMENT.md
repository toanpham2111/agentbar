# Development

```bash
npm ci
npm run typecheck
npm run test
npm run build
cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check
cargo clippy --no-default-features --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --no-default-features --manifest-path src-tauri/Cargo.toml
```

Native development additionally requires the official Tauri 2 prerequisites for the host OS. Do not add mock usage to production commands. Browser-only Vite sessions should show a backend-unavailable state.

New adapters require sanitized fixtures for valid data, empty data, malformed input, and permission failures. Keep modules under 700 lines.
