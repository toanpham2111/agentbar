# Contributing to Kio Usage Monitoring

Thank you for your interest in contributing to **Kio Usage Monitoring**! We welcome community contributions, bug reports, and feature requests.

---

## Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please be respectful and constructive in all discussions, pull requests, and issues.

---

## Getting Started

### 1. Fork and Clone
```bash
git clone https://github.com/<your-username>/agentbar.git
cd agentbar
git checkout -b feature/my-new-feature
```

### 2. Environment Setup
Kio is a hybrid project with a Python menu-bar daemon, a React/TypeScript frontend, and a Rust Tauri core.

#### Python Daemon & CLI
```bash
pip install -r requirements.txt
python3 -m unittest discover -s tests -q
```

#### Web Frontend (React + TypeScript + Vite)
```bash
npm install
npm run typecheck
npm test
npm run build
```

#### Rust Core (Tauri 2)
```bash
cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check
cargo clippy --no-default-features --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --no-default-features --manifest-path src-tauri/Cargo.toml
```

---

## Development Guidelines

1. **Local-First & Data Integrity**:
   - Never fabricate or guess quota numbers (`0%` or artificial estimates). If telemetry is not available, explicitly report `--` with a clear explanation.
   - Credentials, tokens, and telemetry must **never** be sent to remote external servers.
2. **Minimal Diff & Backward Compatibility**:
   - Keep changes scoped to the feature or bug being addressed.
   - Preserve existing CLI flags, configuration schema (`settings.json`), and provider compatibility.
3. **Multi-Engine Support**:
   - New adapters or providers must include unit test fixtures covering:
     - Active session with valid quotas
     - Session without weekly limits / rolling quotas
     - Log files or local service not running (unavailable state)
     - Malformed or corrupt log data

---

## Submitting a Pull Request

1. **Verify All Quality Checks Pass**:
   ```bash
   python3 -m unittest discover -s tests -q
   npm run typecheck
   npm test
   cargo test --no-default-features --manifest-path src-tauri/Cargo.toml
   ```
2. **Commit Conventions**:
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat(<scope>): add support for ...`
   - `fix(<scope>): resolve ...`
   - `docs(<scope>): update ...`
   - `perf(<scope>): optimize ...`
   - `test(<scope>): add unit tests for ...`
3. **Open a PR**:
   - Provide a clear title and description explaining the motivation, changes made, and verification steps.
   - Reference any related issues (e.g., `Closes #12`).

---

## Reporting Issues

- **Bug Reports**: Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md). Include OS details, Python/Node versions, and steps to reproduce.
- **Security Vulnerabilities**: Please review our [Security Policy](docs/SECURITY.md) and report vulnerabilities responsibly. Do not open public issues for sensitive security exploits.
