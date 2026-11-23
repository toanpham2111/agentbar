# Native Windows and macOS Installers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add isolated, unsigned Tauri preview installers for Windows x64 and macOS Intel/Apple Silicon without changing or destabilizing the existing Python/Linux release.

**Architecture:** Keep the Python `.deb` workflow as a protected stable lane. Add a separate Tauri native-preview lane driven by validated `native-vX.Y.Z-preview.N` tags, platform-specific bundle configuration, deterministic artifact staging, checksums, and native smoke gates.

**Tech Stack:** Python 3.8+ stdlib `unittest`, Tauri 2, Rust 1.90, React 19, Vitest, GitHub Actions, NSIS/WiX, macOS DMG.

**Spec:** `docs/superpowers/specs/2026-11-23-native-windows-macos-installers-design.md`

## Global Constraints

- Do not modify `agentbar/**`, `scripts/build_linux_release.py`, `tests/test_agentbar.py`, or `.github/workflows/release.yml`.
- Linux `v*` releases and native `native-v*-preview.*` prereleases remain independent.
- macOS public minimum version is `13.0`.
- Windows preview targets x86_64 with NSIS per-user and MSI per-machine installers.
- Windows WebView2 uses `offlineInstaller`.
- Native preview sequence is an integer from `1` through `999`.
- Every artifact filename includes `preview.N`; preview manifest signing status is `unsigned-preview`.
- Never fabricate missing provider quota data.
- No source file may exceed 700 lines.
- No signing secret, credential, token, or absolute developer path may enter source, logs, manifests, or artifacts.
- Each task must keep the full discovered Python test suite green.
- Execute in an isolated worktree created from commit `13d2572` or later; do not reuse the dirty primary checkout.
- Before Task 1, record `protected_baseline: <git rev-parse HEAD>` in ignored `kio-memory/findings.md`; Task 9 compares protected paths against this exact SHA.

## File Map

| File | Responsibility |
|---|---|
| `scripts/native_release.py` | Parse preview tags, validate base versions, derive platform build identities, stage native artifacts, write manifest/checksums, and expose a CLI. |
| `scripts/smoke_windows.ps1` | Install, launch, verify app-data, upgrade, and uninstall NSIS/MSI previews on Windows. |
| `scripts/smoke_macos.sh` | Mount DMG, install, launch, verify app-data, upgrade, and remove preview app on macOS. |
| `tests/test_native_release.py` | Happy-path, boundary, malformed-input, duplicate-artifact, checksum, secret/path leakage, and workflow-contract tests. |
| `src-tauri/tauri.windows.conf.json` | Windows NSIS/MSI targets, install modes, WebView2 strategy, and stable WiX upgrade code. |
| `src-tauri/tauri.macos.conf.json` | DMG target and macOS 13 deployment floor. |
| `src-tauri/src/core/desktop_settings.rs` | Pure, platform-independent autostart and close behavior decisions with unit tests. |
| `src-tauri/src/desktop.rs` | Synchronize autostart with saved settings and honor `close_to_tray` through an atomic state flag. |
| `.github/workflows/quality.yml` | Preserve Python/Linux job and add platform-independent plus native non-publishing quality jobs. |
| `.github/workflows/native-preview.yml` | Build, verify, aggregate, and publish dedicated unsigned native prereleases. |
| `README.md` | Truthful platform/capability/install matrix. |
| `docs/RELEASE.md` | Native preview commands, tag format, artifact names, and stable-promotion gates. |
| `docs/DEVELOPMENT.md` | Local validation and native runner expectations. |
| `docs/SECURITY.md` | Unsigned preview, secret boundary, checksums, and future signing requirements. |
| `src/report-kio-usage-monitor.html` | Evidence-backed acceptance report; no fabricated Windows/macOS screenshots. |

---

### Task 1: Preview Version and Metadata Validation

**Files:**
- Create: `scripts/native_release.py`
- Create: `tests/test_native_release.py`

**Interfaces:**
- Produces: `PreviewVersion(base_version: str, sequence: int)`, `parse_preview_tag(tag: str) -> PreviewVersion`, `read_base_versions(root: Path) -> dict[str, str]`, `validate_base_versions(root: Path) -> str`, and `build_identity(preview: PreviewVersion) -> dict[str, str]`.
- Consumes: JSON metadata from `package.json` and `src-tauri/tauri.conf.json`; package-version lines from `pyproject.toml` and `src-tauri/Cargo.toml`.

- [ ] **Step 1: Write failing happy-path and boundary tests**

```python
class NativeReleaseVersionTests(unittest.TestCase):
    def test_parses_preview_tag_and_builds_platform_versions(self):
        preview = native_release.parse_preview_tag("native-v1.2.3-preview.7")
        self.assertEqual(preview.base_version, "1.2.3")
        self.assertEqual(preview.sequence, 7)
        self.assertEqual(native_release.build_identity(preview), {
            "tauri_version": "1.2.3-preview.7",
            "msi_version": "1.2.3.7",
            "macos_bundle_version": "1.2.3007",
        })

    def test_rejects_sequence_boundaries_and_malformed_tags(self):
        for tag in (
            "native-v1.2.3-preview.0",
            "native-v1.2.3-preview.1000",
            "v1.2.3",
            "native-v1.2-preview.1",
        ):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                native_release.parse_preview_tag(tag)

    def test_rejects_versions_outside_msi_numeric_bounds(self):
        for tag in ("native-v256.0.0-preview.1", "native-v1.256.0-preview.1", "native-v1.0.65536-preview.1"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                native_release.parse_preview_tag(tag)
```

- [ ] **Step 2: Run the tests and confirm the red phase**

Run: `python3 -m unittest tests.test_native_release.NativeReleaseVersionTests -v`

Expected: FAIL because `scripts.native_release` does not exist.

- [ ] **Step 3: Implement immutable preview metadata and strict parsing**

```python
@dataclass(frozen=True)
class PreviewVersion:
    base_version: str
    sequence: int

PREVIEW_TAG = re.compile(
    r"^native-v(?P<base>\d+\.\d+\.\d+)-preview\.(?P<sequence>\d+)$"
)

def parse_preview_tag(tag: str) -> PreviewVersion:
    match = PREVIEW_TAG.fullmatch(tag.strip())
    if match is None:
        raise ValueError("tag must match native-vX.Y.Z-preview.N")
    sequence = int(match.group("sequence"))
    if not 1 <= sequence <= 999:
        raise ValueError("preview sequence must be between 1 and 999")
    base = match.group("base")
    major, minor, patch = (int(part) for part in base.split("."))
    if major > 255 or minor > 255 or patch > 65_535:
        raise ValueError("version exceeds MSI numeric bounds")
    return PreviewVersion(base, sequence)

def build_identity(preview: PreviewVersion) -> dict[str, str]:
    major, minor, patch = (int(part) for part in preview.base_version.split("."))
    macos_build = patch * 1000 + preview.sequence
    return {
        "tauri_version": f"{preview.base_version}-preview.{preview.sequence}",
        "msi_version": f"{major}.{minor}.{patch}.{preview.sequence}",
        "macos_bundle_version": f"{major}.{minor}.{macos_build}",
    }
```

- [ ] **Step 4: Add version synchronization tests and implementation**

Test four matching `1.0.0` files, one mismatched file, a missing version, and a malformed TOML package section. `validate_base_versions()` must return the single version or raise a message naming every mismatched source. Parse only the root `[package]` or `[project]` section; do not match dependency versions.

- [ ] **Step 5: Run Task 1 tests and protected Linux regression**

Run:

```bash
python3 -m unittest tests.test_native_release.NativeReleaseVersionTests -v
python3 -m unittest discover -s tests -q
```

Expected: all tests PASS; no tracked asset or `dist/agentbar` change.

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/native_release.py tests/test_native_release.py
git commit -m "feat: validate native preview versions"
```

---

### Task 2: Config Overlay, Artifact Staging, Manifest, and Checksums

**Files:**
- Modify: `scripts/native_release.py`
- Modify: `tests/test_native_release.py`

**Interfaces:**
- Consumes: `PreviewVersion` and `build_identity()` from Task 1.
- Produces: `build_config_overlay(preview, platform) -> dict`, `stage_artifacts(artifacts: Mapping[str, Path], allowed_roots: Sequence[Path], destination: Path, preview: PreviewVersion, target: str) -> list[Path]`, `write_target_manifest(...) -> Path`, `write_combined_manifest(...) -> Path`, and `write_checksums(directory, included_paths) -> Path`.

- [ ] **Step 1: Write failing overlay tests**

```python
def test_builds_windows_and_macos_overlays(self):
    preview = PreviewVersion("1.0.0", 9)
    windows = build_config_overlay(preview, "windows-x64")
    macos = build_config_overlay(preview, "macos-arm64")
    self.assertEqual(windows["version"], "1.0.0-preview.9")
    self.assertEqual(windows["bundle"]["windows"]["wix"]["version"], "1.0.0.9")
    self.assertEqual(macos["bundle"]["macOS"]["bundleVersion"], "1.0.9")
    with self.assertRaises(ValueError):
        build_config_overlay(preview, "linux-x64")
```

- [ ] **Step 2: Run the overlay test and verify failure**

Run: `python3 -m unittest tests.test_native_release.NativeArtifactTests.test_builds_windows_and_macos_overlays -v`

Expected: FAIL because `build_config_overlay` is missing.

- [ ] **Step 3: Implement deterministic overlay dictionaries**

Windows overlay sets top-level preview version plus `bundle.windows.wix.version`; macOS overlay sets top-level preview version plus `bundle.macOS.bundleVersion`. Serialize with sorted keys and a trailing newline to `release/generated/tauri.preview.conf.json`; never modify tracked metadata.

- [ ] **Step 4: Write failing artifact classification tests**

Create temporary fixtures for:

- Valid Windows pair: one `-setup.exe` and one `.msi`.
- Valid macOS target: one `.dmg`.
- Missing artifact.
- Duplicate artifact.
- Unexpected extension.
- Paths containing spaces and Vietnamese Unicode.

Expected normalized names follow the spec exactly and use copied bytes, not shell interpolation.

- [ ] **Step 5: Implement safe artifact staging**

Accept explicit artifact mappings: Windows requires `{"nsis": bundle/nsis/*.exe, "msi": bundle/msi/*.msi}` and macOS requires `{"dmg": bundle/dmg/*.dmg}`. Resolve each path against its declared allowed bundle root, then use `shutil.copy2` and collision checks. Reject symlinks, directories, duplicate keys, duplicate resolved files, and files outside all allowed roots.

- [ ] **Step 6: Write failing manifest and checksum tests**

```python
def test_manifest_and_checksum_order(self):
    artifacts = [self.write_file("app.msi", b"msi"), self.write_file("setup.exe", b"exe")]
    manifest = write_target_manifest(self.output, self.preview, "abc123", "windows-x64", artifacts)
    checksums = write_checksums(self.output, [*artifacts, manifest])
    lines = checksums.read_text(encoding="utf-8").splitlines()
    self.assertEqual(len(lines), 3)
    self.assertFalse(any("SHA256SUMS" in line for line in lines))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    self.assertEqual(payload["signing_status"], "unsigned-preview")
```

Also test rejection when a manifest field contains an access-token pattern, the checkout absolute path, or a file whose hash changes between manifest and checksum generation.

- [ ] **Step 7: Implement manifest and checksum generation**

Target manifest fields are exactly: `channel`, `signing_status`, `tag`, `base_version`, `preview_sequence`, `commit_sha`, `target`, and `artifacts` (`kind`, `filename`, `size`, `sha256`). `write_combined_manifest()` accepts exactly one manifest for `windows-x64`, `macos-x64`, and `macos-arm64`, rejects duplicate/missing/unknown targets, and writes one deterministically sorted `targets` array containing all four installers exactly once. Generate installer hashes first, write the combined manifest, then hash installers plus the combined manifest into `SHA256SUMS`; exclude `SHA256SUMS` itself.

Add tests for missing target, duplicate target, duplicate artifact across targets, deterministic target/artifact ordering, and a valid four-installer combined manifest.

- [ ] **Step 8: Run Task 2 and regression tests**

Run:

```bash
python3 -m unittest tests.test_native_release.NativeArtifactTests -v
python3 -m unittest discover -s tests -q
git diff --check
```

- [ ] **Step 9: Commit Task 2**

```bash
git add scripts/native_release.py tests/test_native_release.py
git commit -m "feat: stage and verify native preview artifacts"
```

---

### Task 3: Platform-specific Tauri Bundle Configuration

**Files:**
- Create: `src-tauri/tauri.windows.conf.json`
- Create: `src-tauri/tauri.macos.conf.json`
- Modify: `tests/test_native_release.py`

**Interfaces:**
- Consumes: Tauri 2 platform-config merging and the generated overlay from Task 2.
- Produces: stable Windows/macOS bundle contracts validated by unit tests.

- [ ] **Step 1: Write failing config-contract tests**

Tests must load both JSON files and assert:

```python
self.assertEqual(windows["bundle"]["targets"], ["nsis", "msi"])
self.assertEqual(windows["bundle"]["windows"]["webviewInstallMode"]["type"], "offlineInstaller")
self.assertEqual(windows["bundle"]["windows"]["nsis"]["installMode"], "currentUser")
self.assertEqual(windows["bundle"]["windows"]["wix"]["upgradeCode"], "0284e666-2ca5-5fcd-a736-46577daeeb89")
self.assertEqual(macos["bundle"]["targets"], ["dmg"])
self.assertEqual(macos["bundle"]["macOS"]["minimumSystemVersion"], "13.0")
```

- [ ] **Step 2: Run the config test and verify failure**

Run: `python3 -m unittest tests.test_native_release.NativeConfigTests -v`

Expected: FAIL because platform config files are absent.

- [ ] **Step 3: Add minimal platform configuration**

`tauri.windows.conf.json` contains only bundle targets and Windows settings. `tauri.macos.conf.json` contains only DMG target and macOS settings. Validate both against `node_modules/@tauri-apps/cli/config.schema.json`, not only hand-written assertions. Do not duplicate product name, identifier, icons, CSP, or window configuration from the base config.

- [ ] **Step 4: Validate schemas and build the host-compatible frontend/core**

Run:

```bash
python3 -m json.tool src-tauri/tauri.windows.conf.json >/dev/null
python3 -m json.tool src-tauri/tauri.macos.conf.json >/dev/null
python3 -m unittest tests.test_native_release.NativeConfigTests -v
npm run typecheck
npm run test
npm run build
cargo test --no-default-features --manifest-path src-tauri/Cargo.toml
```

- [ ] **Step 5: Commit Task 3**

```bash
git add src-tauri/tauri.windows.conf.json src-tauri/tauri.macos.conf.json tests/test_native_release.py
git commit -m "build: configure Windows and macOS bundles"
```

---

### Task 4: Autostart and Close-to-tray Settings on Native Desktop

**Files:**
- Create: `src-tauri/src/core/desktop_settings.rs`
- Modify: `src-tauri/src/core/mod.rs`
- Modify: `src-tauri/src/desktop.rs`

**Interfaces:**
- Produces: `AutostartAction`, `autostart_action(current, desired)`, and `should_prevent_close(close_to_tray)` pure helpers; `update_settings` synchronizes the OS autostart plugin before persisting settings; `AppState.close_to_tray: AtomicBool` supports synchronous window events.
- Consumes: `tauri_plugin_autostart::ManagerExt` and existing `AppSettings`.

- [ ] **Step 1: Add failing Rust unit tests in the new core module**

```rust
#[test]
fn autostart_action_covers_enable_disable_and_noop() {
    assert_eq!(autostart_action(false, true), AutostartAction::Enable);
    assert_eq!(autostart_action(true, false), AutostartAction::Disable);
    assert_eq!(autostart_action(true, true), AutostartAction::None);
}

#[test]
fn close_behavior_honors_setting() {
    assert!(should_prevent_close(true));
    assert!(!should_prevent_close(false));
}
```

- [ ] **Step 2: Run Rust test and verify failure**

Run: `cargo test --no-default-features --manifest-path src-tauri/Cargo.toml desktop_settings::tests -v`

Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Implement pure decision helpers**

Define `AutostartAction::{Enable, Disable, None}` and the two pure functions in `core/desktop_settings.rs`. Export the module from `core/mod.rs`. Keep it free of Tauri and OS calls so it runs on Linux CI without desktop features.

- [ ] **Step 4: Synchronize the autostart plugin atomically enough for user-visible state**

Add `app: AppHandle` to `update_settings`, query `app.autolaunch().is_enabled()`, apply `enable()` or `disable()` based on the helper, and map plugin errors to `AppError::Validation("autostart update failed: ...")`. Return without saving database state when the OS operation fails. Persist settings only after the plugin succeeds, then store `settings.close_to_tray` into `AppState.close_to_tray`.

- [ ] **Step 5: Honor `close_to_tray`**

Add `close_to_tray: AtomicBool` to `AppState`, initialize it from the loaded settings, and use `Ordering::Relaxed` for this independent UI flag. In `on_window_event`, load the atomic flag. When true, prevent close and hide; when false, allow normal window close. Do not block the UI thread on the async `RwLock` and do not call `app.exit()` from the close event.

- [ ] **Step 6: Run Rust and frontend regression**

Run:

```bash
cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check
cargo clippy --no-default-features --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --no-default-features --manifest-path src-tauri/Cargo.toml
npm run test
```

- [ ] **Step 7: Commit Task 4**

```bash
git add src-tauri/src/core/desktop_settings.rs src-tauri/src/core/mod.rs src-tauri/src/desktop.rs
git commit -m "fix: synchronize native startup settings"
```

---

### Task 5: Expand Quality CI Without Weakening Linux

**Files:**
- Modify: `.github/workflows/quality.yml`
- Modify: `tests/test_native_release.py`

**Interfaces:**
- Produces: independent `python-menu-bar`, `tauri-core`, `native-windows`, `native-macos-intel`, and `native-macos-arm64` jobs.

- [ ] **Step 1: Add failing workflow-contract tests**

Read the workflow as text and assert that the existing `python-menu-bar` job and Linux build command remain present, while the native jobs use `windows-latest`, `macos-15-intel`, and `macos-15`. Assert every native job runs `npm ci`, frontend tests/build, Rust tests, and a non-publishing Tauri build.

- [ ] **Step 2: Run workflow tests and verify failure**

Run: `python3 -m unittest tests.test_native_release.NativeWorkflowTests.test_quality_contract -v`

- [ ] **Step 3: Strengthen the existing Linux job additively**

Install Xvfb and runtime dependencies, verify `SHA256SUMS`, inspect Debian metadata/contents, install the package, run `kio-usage-monitoring --version`, run `agentbar status --no-color`, and launch/close GTK under Xvfb. Do not rename or remove existing steps.

- [ ] **Step 4: Add platform-independent and native jobs**

Use official runner labels verified on 2026-11-23. Native jobs call `npm run tauri build` with the platform config plus generated preview overlay using a fixed test tag `native-v1.0.0-preview.1`; they upload workflow artifacts only and never create a GitHub Release.

- [ ] **Step 5: Validate workflow and full regression**

Run:

```bash
python3 -m unittest tests.test_native_release.NativeWorkflowTests.test_quality_contract -v
python3 -m unittest discover -s tests -q
npm run typecheck
npm run test
cargo test --no-default-features --manifest-path src-tauri/Cargo.toml
```

- [ ] **Step 6: Commit Task 5**

```bash
git add .github/workflows/quality.yml tests/test_native_release.py
git commit -m "ci: verify native desktop bundles"
```

---

### Task 6: Dedicated Native Preview Prerelease Workflow

**Files:**
- Create: `.github/workflows/native-preview.yml`
- Modify: `tests/test_native_release.py`

**Interfaces:**
- Consumes: CLI commands from `scripts/native_release.py` and platform configs from Task 3.
- Produces: complete Windows/macOS preview artifact set, manifest, `SHA256SUMS`, and GitHub prerelease for `native-v*-preview.*` tags.

- [ ] **Step 1: Add failing preview-workflow contract tests**

Tests assert:

- Trigger is `native-v*-preview.*`, not `v*`.
- Permissions are `contents: write` only at workflow or publish-job scope.
- Build jobs have `contents: read` and no signing secrets.
- Publish job depends on all three native targets.
- Release is marked `prerelease: true`.
- The workflow calls the utility to validate tag/version, write config overlay, stage artifacts, write manifest, and write checksums.
- `.github/workflows/release.yml` is never referenced or modified.

- [ ] **Step 2: Run preview workflow test and verify failure**

Run: `python3 -m unittest tests.test_native_release.NativeWorkflowTests.test_native_preview_contract -v`

- [ ] **Step 3: Implement three native build jobs**

Each job checks out the tag, sets up Node and Rust, runs platform-independent gates, generates its config overlay, builds native bundles, stages normalized artifacts, uploads an artifact named by target, and exposes no repository secret.

- [ ] **Step 4: Implement aggregation and prerelease publication**

The Ubuntu aggregation job downloads all target artifacts, rejects missing/duplicate/unexpected files, writes target manifests, writes a combined `native-preview-manifest.json`, writes `SHA256SUMS` excluding itself, verifies every hash, and publishes only when all jobs succeeded.

- [ ] **Step 5: Run workflow contract and utility tests**

Run:

```bash
python3 -m unittest tests.test_native_release -v
python3 -m unittest discover -s tests -q
git diff --check
```

- [ ] **Step 6: Commit Task 6**

```bash
git add .github/workflows/native-preview.yml tests/test_native_release.py
git commit -m "ci: publish isolated native preview installers"
```

---

### Task 7: Automated Native Lifecycle Smoke Scripts

**Files:**
- Create: `scripts/smoke_windows.ps1`
- Create: `scripts/smoke_macos.sh`
- Modify: `.github/workflows/native-preview.yml`
- Modify: `tests/test_native_release.py`

**Interfaces:**
- Produces: Windows `-Installer`, `-PreviousInstaller`, and `-Kind nsis|msi` smoke contract; macOS `--dmg` and optional `--previous-dmg` contract.
- Consumes: staged installers and platform-native application-data locations.

- [ ] **Step 1: Write failing smoke-contract tests**

Assert the PowerShell script contains strict error mode, exact `DisplayName` registry lookup, process launch/poll, `%APPDATA%\vn.kiodigital.usagemonitor\usage.db` polling, a Python SQLite query for `SELECT COUNT(*) FROM providers`, upgrade path, exit-code checks, NSIS `QuietUninstallString` fallback, MSI `msiexec /x`, and residue checks. Assert the shell script uses `set -euo pipefail`, `hdiutil attach -nobrowse`, copies to a temporary Applications directory, launches with `open`, polls `~/Library/Application Support/vn.kiodigital.usagemonitor/usage.db`, runs the same SQLite row-count query, tests replacement by the optional previous DMG, terminates the process, detaches the volume, and removes only the temporary installed app.

- [ ] **Step 2: Run smoke-contract tests and verify failure**

Run: `python3 -m unittest tests.test_native_release.NativeSmokeContractTests -v`

- [ ] **Step 3: Implement Windows lifecycle smoke**

Use `Set-StrictMode -Version Latest` and `$ErrorActionPreference = "Stop"`. Install silently, discover the uninstall record by exact display name, derive the executable path from `DisplayIcon`, start the app, poll process and `usage.db` with a 60-second deadline, then use runner Python's stdlib `sqlite3` to require `SELECT COUNT(*) FROM providers` to be greater than zero after the scheduler's immediate startup refresh. Install the new package over `-PreviousInstaller` when supplied, stop the process, uninstall, and assert the uninstall entry and executable are absent. Preserve app data by design.

- [ ] **Step 4: Implement macOS lifecycle smoke**

Mount each DMG into a `mktemp -d` mount point, copy the `.app` into a second temporary directory, remove quarantine only for this unsigned CI preview copy, launch it, poll process plus `usage.db` for 60 seconds, then use runner Python's stdlib `sqlite3` to require at least one `providers` row after the immediate startup refresh. Replace a previous app when supplied, terminate it, remove only the temporary app, and detach every mounted image through a cleanup trap. Preserve Application Support data.

- [ ] **Step 5: Wire smoke jobs before native publication**

Run lifecycle smoke on the same native runner immediately after bundle creation. Windows tests NSIS and MSI independently. Each macOS runner tests its architecture-specific DMG. The native-preview workflow uses GitHub's read-only release API to locate the highest earlier `native-v<same-base>-preview.N` prerelease and download its matching target artifact. Preview sequence `1` records `upgrade_status=not-applicable-first-preview` and performs same-version reinstall; sequence `N > 1` must find and test the previous target artifact or fail. Upload smoke logs with the installer artifact; a nonzero smoke exit blocks target artifact upload and aggregation.

- [ ] **Step 6: Run contract and regression tests**

```bash
python3 -m unittest tests.test_native_release.NativeSmokeContractTests -v
python3 -m unittest discover -s tests -q
git diff --check
```

- [ ] **Step 7: Commit Task 7**

```bash
git add scripts/smoke_windows.ps1 scripts/smoke_macos.sh .github/workflows/native-preview.yml tests/test_native_release.py
git commit -m "test: verify native installer lifecycle"
```

---

### Task 8: Truthful Platform Documentation and Install Cards

**Files:**
- Modify: `README.md`
- Modify: `docs/RELEASE.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/SECURITY.md`

**Interfaces:**
- Produces: platform cards and capability matrix that distinguish Linux stable from unsigned Windows/macOS preview.

- [ ] **Step 1: Add documentation assertions**

Extend `NativeWorkflowTests` or add `NativeDocumentationTests` to assert README contains three install cards, the words `Unsigned preview`, the capability difference for Python live quota collectors, and the `native-vX.Y.Z-preview.N` tag contract. Assert docs never call Windows/macOS `Stable` without the signing gate text.

- [ ] **Step 2: Run documentation test and verify failure**

Run: `python3 -m unittest tests.test_native_release.NativeDocumentationTests -v`

- [ ] **Step 3: Add three install cards to README**

Linux card links to stable `v1.0.0` `.deb`. Windows card explains NSIS/MSI preview and SmartScreen warning. macOS card lists separate Intel/Apple Silicon DMGs and Gatekeeper warning. Include a capability matrix showing that Python live quota collectors remain Linux-only in this phase.

- [ ] **Step 4: Update release, development, and security documentation**

Document exact runner labels, artifact names, checksum verification commands, NSIS/MSI silent install/uninstall commands, DMG install/uninstall behavior, retained app-data policy, prerelease tag creation, and stable signing/notarization gates.

- [ ] **Step 5: Validate local links and wording**

Run a read-only link checker over Markdown relative targets, `git diff --check`, and:

```bash
python3 -m unittest tests.test_native_release.NativeDocumentationTests -v
```

- [ ] **Step 6: Commit Task 8**

```bash
git add README.md docs/RELEASE.md docs/DEVELOPMENT.md docs/SECURITY.md tests/test_native_release.py
git commit -m "docs: add Windows and macOS preview installs"
```

---

### Task 9: Full Regression, Native Evidence Contract, and Acceptance Report

**Files:**
- Modify: `src/report-kio-usage-monitor.html`
- Create after real native runs: `docs/release-evidence/<native-preview-tag>/windows-x64.md`
- Create after real native runs: `docs/release-evidence/<native-preview-tag>/macos-x64.md`
- Create after real native runs: `docs/release-evidence/<native-preview-tag>/macos-arm64.md`

**Interfaces:**
- Consumes: completed workflow logs and artifacts from Tasks 1–8.
- Produces: final Kio acceptance evidence without invented screenshots or native results.

- [ ] **Step 1: Run the complete local Linux-safe gate**

```bash
VERSION="$(python3 -c 'from agentbar import __version__; print(__version__)')"
ARCH="$(dpkg --print-architecture)"
python3 -m compileall -q agentbar tests scripts
python3 -m unittest discover -s tests -q
python3 scripts/build_linux_release.py "$VERSION"
(cd release && sha256sum -c SHA256SUMS)
dpkg-deb --info "release/Kio-Usage-Monitoring_${VERSION}_${ARCH}.deb"
dpkg-deb --contents "release/Kio-Usage-Monitoring_${VERSION}_${ARCH}.deb"
npm run typecheck
npm run test
npm run build
cargo fmt --all --manifest-path src-tauri/Cargo.toml -- --check
cargo clippy --no-default-features --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --no-default-features --manifest-path src-tauri/Cargo.toml
```

Expected: exit code `0` for every command. A failure rejects delivery and returns to the owning task.

- [ ] **Step 2: Inspect protected-path integrity**

Run:

```bash
BASELINE="$(sed -n 's/^protected_baseline: //p' kio-memory/findings.md)"
test -n "$BASELINE"
git diff "$BASELINE" -- agentbar scripts/build_linux_release.py tests/test_agentbar.py .github/workflows/release.yml
```

Expected: no diff.

- [ ] **Step 3: Dispatch independent QA review**

QA reviews blast radius, workflow permissions, secret exposure, artifact completeness, and test coverage. Any missing happy path, boundary, error, or security case is a rejection.

- [ ] **Step 4: Collect real native evidence**

Run the quality workflow on all three native runners. Do not create a preview tag until build jobs pass. After a preview tag is created by an authorized maintainer, record workflow URLs, OS/architecture, artifact SHA-256, install/launch/tray/settings/refresh/close/autostart/upgrade/uninstall outcomes, logs, and real screenshots in the three evidence files.

- [ ] **Step 5: Update the acceptance report**

Add changelog, exact test commands/results, artifact table, capability differences, unsigned warnings, and links to real evidence. If native evidence is unavailable, mark those rows `UNVERIFIED` and do not embed demo or Linux screenshots as native proof.

- [ ] **Step 6: Final diff and file-size audit**

Run:

```bash
git diff --check
find scripts tests src-tauri/src -type f \( -name '*.py' -o -name '*.rs' \) -print0 | xargs -0 -n1 awk 'END { if (NR > 700) { print FILENAME ":" NR; exit 1 } }'
git status --short
```

- [ ] **Step 7: Commit evidence-backed report changes**

```bash
git add src/report-kio-usage-monitor.html docs/release-evidence
git commit -m "docs: record native preview acceptance evidence"
```

If native runner evidence is not yet available, commit only the report with explicit `UNVERIFIED` status and do not create empty evidence files.

## Execution Checkpoints

- After Task 2: review the public Python utility interface and security boundaries.
- After Task 4: run full Rust/frontend regression before touching workflows.
- After Task 6: review workflow permissions and prove Linux/native tag isolation.
- After Task 7: review native lifecycle logs and uninstall residue checks.
- After Task 8: review every support claim against actual feature parity.
- After Task 9: Kio QA must sign off all five pillars; otherwise status remains `Preview/Unverified`.

## Official References

- [GitHub-hosted runner labels](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [Tauri distribution targets](https://v2.tauri.app/distribute/)
- [Tauri Windows installers](https://v2.tauri.app/distribute/windows-installer/)
