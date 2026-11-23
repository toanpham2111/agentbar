# Native Windows and macOS Installers — Design Specification

**Date:** 2026-11-23<br>
**Status:** Proposed for implementation review<br>
**Approved direction:** Tauri native preview, with the existing Python/Linux release preserved

## 1. Context

Kio Usage Monitoring currently has two desktop implementations:

- The Python application is the verified Linux release. It provides the GTK menu-bar experience and the current live quota collectors. GitHub Actions publishes it as a Debian package.
- The React/Tauri application is the cross-platform desktop architecture. It already contains native tray behavior, platform-aware paths, SQLite persistence, scheduling, notifications, autostart integration, icons, and Tauri bundle configuration, but it is not built or published on native Windows and macOS runners.

The existing Python macOS and Windows packaging helpers are not standalone installers. The macOS bundle calls a system Python runtime, while the Windows shortcut calls `pythonw.exe` and references the source checkout. Neither path provides a signed installer, verified upgrade behavior, or an uninstaller.

## 2. Goals

1. Produce installable Tauri preview artifacts on native GitHub Actions runners:
   - Windows x64: NSIS setup executable and MSI package.
   - macOS Apple Silicon and Intel: DMG containing the native application bundle.
2. Preserve the current Python/Linux application, Debian package, live quota collectors, and Linux release workflow behavior.
3. Run frontend and Rust regression tests before any native bundle is accepted.
4. Label unsigned artifacts as preview builds and avoid claiming stable platform support without signing and native smoke-test evidence.
5. Generate SHA-256 checksums for every published artifact.
6. Define a promotion gate from preview to stable without changing the artifact architecture.

## 3. Non-goals

- Rewriting Python live quota collectors in Rust in this phase.
- Claiming provider parity between the Python/Linux application and the Tauri preview.
- Replacing or removing the existing Linux Debian package.
- Cross-compiling macOS or Windows artifacts from Linux.
- Publishing unsigned Windows or macOS artifacts as stable releases.
- Adding auto-update support in this phase.
- Shipping a macOS PKG or Windows ARM64 installer in the first preview.

## 4. Release Architecture

The release system has two isolated lanes.

### 4.1 Linux stable lane

The existing Python workflow remains the source of the Linux stable package:

```text
Python source → unit tests → Linux zipapp → Debian package → checksum → GitHub Release
```

The following behavior is protected from changes in this feature:

- `scripts/build_linux_release.py`
- `agentbar/` collectors and GTK UI
- `Kio-Usage-Monitoring_<version>_<architecture>.deb`
- Existing Python unit tests
- Existing user-local Linux installation behavior

Native installer implementation must not edit `agentbar/**`, `scripts/build_linux_release.py`, `tests/test_agentbar.py`, or `.github/workflows/release.yml`. If a native change appears to require one of these paths, implementation stops and returns for a separate design review. A Windows or macOS failure never blocks publication of a Linux `v*` release.

### 4.2 Windows and macOS preview lane

The Tauri application is built independently on each target operating system:

```text
React build + Rust tests
          ↓
Native Tauri build on target runner
          ↓
Stage and normalize artifact names
          ↓
Platform verification + SHA-256
          ↓
Preview workflow artifact or preview GitHub Release asset
```

The preview lane does not import or package the Python application. It uses a separate `.github/workflows/native-preview.yml` workflow and tags in the form `native-v<base-version>-preview.<sequence>`. These tags do not match the Linux stable workflow trigger `v*`.

## 5. Target Matrix and Artifacts

| Platform | Runner | Architecture | Bundle targets | Normalized artifacts |
|---|---|---:|---|---|
| Windows 10/11 | `windows-latest` | x86_64 | NSIS, MSI | `Kio-Usage-Monitoring-<base-version>-preview.<sequence>-windows-x64-setup.exe`, `Kio-Usage-Monitoring-<base-version>-preview.<sequence>-windows-x64.msi` |
| macOS 13+ | `macos-15-intel` | x86_64 | app, DMG | `Kio-Usage-Monitoring-<base-version>-preview.<sequence>-macos-x64.dmg` |
| macOS 13+ | `macos-15` | arm64 | app, DMG | `Kio-Usage-Monitoring-<base-version>-preview.<sequence>-macos-arm64.dmg` |

The first release uses separate macOS architecture artifacts. A universal DMG is deferred until both native builds are stable and a universal binary is verified on real hardware.

## 6. Capability Contract

The README and release notes must distinguish platform installation support from provider feature parity.

| Capability | Linux stable | Windows preview | macOS preview |
|---|:---:|:---:|:---:|
| Installable native artifact | ✅ | ✅ | ✅ |
| Launch, tray, settings, close-to-tray | ✅ | Required | Required |
| Local SQLite history | Tauri lane only | Required | Required |
| Provider installation detection | ✅ | Required | Required |
| Python live quota collectors | ✅ | ❌ | ❌ |
| Tauri documented local usage signals | N/A | Preview scope | Preview scope |
| Signed and trusted by OS | Debian package | Only after Authenticode gate | Only after Developer ID/notarization gate |

Unknown or unavailable provider data must remain unavailable. The Tauri preview must not fabricate quota values to imitate the Linux application.

## 7. Bundle Configuration

`src-tauri/tauri.conf.json` remains the canonical bundle metadata source. The base application version in that file is the source of truth and must exactly match `package.json`, `src-tauri/Cargo.toml`, and `pyproject.toml`. A native preview tag contributes only the preview sequence; `native-v1.0.0-preview.1` is valid only when all four files contain base version `1.0.0`. A mismatch fails validation and is never auto-corrected by CI.

The native release utility generates an untracked Tauri config overlay for each preview build. For base version `X.Y.Z` and sequence `N` (`1 <= N <= 999`):

- Tauri/NSIS application version is `X.Y.Z-preview.N`.
- MSI package version is `X.Y.Z.N`.
- macOS `CFBundleShortVersionString` is `X.Y.Z-preview.N`.
- macOS `CFBundleVersion` is `X.Y.(Z * 1000 + N)`.

This gives every preview a monotonic platform-compatible upgrade identity without modifying the four tracked base-version files.

Implementation must:

- Keep product name `Kio Usage Monitoring`, identifier `vn.kiodigital.usagemonitor`, and version synchronized with `package.json`, `src-tauri/Cargo.toml`, and `pyproject.toml`.
- Use explicit platform bundle targets in CI rather than relying on `targets: "all"` from a single host.
- Preserve the existing `.ico` and `.icns` icon families.
- Set macOS minimum and public support version to `13.0` for the preview contract.
- Configure NSIS as the recommended per-user Windows installer with WebView2 `offlineInstaller`, so a clean installation does not depend on network access.
- Keep MSI as the managed per-machine alternative. Its product identity and upgrade code must remain stable across preview builds.
- Document silent install contracts: NSIS `<setup.exe> /S`; MSI `msiexec /i <package> /qn /norestart`.
- For NSIS uninstall automation, locate the HKCU uninstall entry whose `DisplayName` is exactly `Kio Usage Monitoring`, invoke `QuietUninstallString` when present or `UninstallString` with `/S` otherwise, and require exit code `0`. MSI uninstall uses `msiexec /x <product-code> /qn /norestart` and requires exit code `0`.
- Keep Tauri capabilities minimal; no unrestricted shell, filesystem, or HTTP permissions may be added for packaging convenience.

## 8. CI and Release Workflows

### 8.1 Quality workflow

The quality workflow adds native jobs without changing the existing Python/Linux job:

1. Frontend gate: `npm ci`, typecheck, Vitest, and production build.
2. Rust core gate: format, Clippy with warnings denied, and tests without desktop features.
3. Windows native bundle job: Tauri build for NSIS and MSI, artifact existence checks, executable metadata checks, and upload as workflow artifacts.
4. macOS x64 native bundle job: Tauri DMG build, architecture and bundle metadata checks, and artifact upload.
5. macOS arm64 native bundle job: Tauri DMG build, architecture and bundle metadata checks, and artifact upload.

Native jobs must depend on the platform-independent gates. Failure in any required gate blocks artifact publication.

### 8.2 Native preview workflow

The new tag-triggered `.github/workflows/native-preview.yml` workflow is independent from the existing Linux release workflow. It runs only for `native-v*-preview.*` tags. A final native aggregation job:

- Downloads all successful artifacts.
- Normalizes filenames.
- Generates `native-preview-manifest.json` after hashing all installers, then generates `SHA256SUMS` covering every installer and the manifest. `SHA256SUMS` excludes itself.
- Verifies expected artifacts are present exactly once.
- Publishes artifacts to a dedicated GitHub prerelease whose tag is the native preview tag.

Unsigned native artifacts include `preview` in every filename. The prerelease contains `native-preview-manifest.json` with `channel`, `signing_status`, `tag`, `base_version`, `commit_sha`, target architecture, artifact filename, size, and SHA-256. `signing_status` is exactly `unsigned-preview` until the stable promotion design is implemented.

## 9. Signing and Promotion

### 9.1 Preview state

The initial implementation supports unsigned preview builds because signing credentials are not stored in the repository. CI records `unsigned-preview` in the manifest and release notes. The preview workflow contains no signing branches or empty-secret fallbacks.

### 9.2 Windows stable promotion

Windows becomes stable only when all conditions pass:

- The application binary and installer carry a valid, timestamped Authenticode signature.
- `Get-AuthenticodeSignature` reports `Valid` and matches the protected repository variable `WINDOWS_SIGNING_PUBLISHER`, populated from the final certificate subject during the separate stable-promotion change.
- Clean Windows 10 and Windows 11 installation, launch, tray, autostart, upgrade, and uninstall tests pass.

### 9.3 macOS stable promotion

macOS becomes stable only when all conditions pass:

- The app uses a Developer ID Application signature and hardened runtime.
- The DMG is notarized and stapled.
- `codesign --verify`, `spctl --assess`, and `stapler validate` pass.
- Clean Intel and Apple Silicon installation, launch, menu-bar, autostart, upgrade, and uninstall tests pass.

Signing identities and credentials exist only in encrypted GitHub Actions secrets. They must never be committed, printed, embedded in artifacts, or exposed to pull-request jobs.

## 10. Error Handling

- The preview workflow never reads signing secrets and always produces an explicitly unsigned preview manifest.
- A missing expected installer fails the workflow before release publication.
- Checksum mismatch fails the aggregation job.
- A native bundle whose embedded product name, identifier, base version, architecture, or executable path differs from the contract is rejected.
- Provider discovery or network failure after installation must not crash the desktop shell; unavailable data remains visibly unavailable.
- User cancellation, denied permissions, or failed installation must not be reported as successful by smoke-test scripts.

## 11. Test Strategy

### 11.1 Protected Linux regression

Every change must pass:

```bash
VERSION="$(python3 -c 'from agentbar import __version__; print(__version__)')"
ARCH="$(dpkg --print-architecture)"
python3 -m compileall -q agentbar tests scripts
python3 -m unittest discover -s tests -q
python3 scripts/build_linux_release.py "$VERSION"
(cd release && sha256sum -c SHA256SUMS)
dpkg-deb --info "release/Kio-Usage-Monitoring_${VERSION}_${ARCH}.deb"
dpkg-deb --contents "release/Kio-Usage-Monitoring_${VERSION}_${ARCH}.deb"
```

CI additionally installs the package with `apt`, runs `kio-usage-monitoring --version`, runs `agentbar status --no-color`, and performs a GTK launch/close smoke under Xvfb. The complete discovered Python test suite must pass; the gate is not tied to a fixed test count. No existing test may be disabled, weakened, or deleted to make native packaging pass.

### 11.2 Platform-independent tests

Tests must cover:

- Base-version synchronization across four metadata files and native preview tag parsing.
- Preview build-version mapping for sequences `1`, `999`, rejected `0`, and rejected `1000`.
- Artifact filename normalization.
- Expected-artifact detection for complete, missing, duplicate, and unexpected input.
- Checksum generation and verification.
- Manifest generation order and `SHA256SUMS` self-exclusion.
- Paths containing spaces and Unicode.
- Missing or malformed metadata.
- Protection against absolute build paths or secrets in release manifests.

### 11.3 Native smoke gates

Automated CI smoke tests verify:

1. Install on a clean runner or VM.
2. Launch from Applications or Start Menu.
3. Create application data in the platform-appropriate directory.
4. Refresh providers without crashing when none are installed.
5. Reinstall or upgrade without losing settings/history.
6. Uninstall without leaving application binaries or startup entries.

Manual native QA verifies tray/menu-bar visibility, opening the main window and settings, close-to-tray, quit, notifications, and autostart enable/disable. Evidence is stored under `docs/release-evidence/<native-preview-tag>/<platform>.md` with tester, OS version, architecture, artifact SHA-256, timestamp, pass/fail for each action, console output, and screenshots. The QA Lead approves the evidence. Missing evidence blocks only the `Stable` label, not publication of an explicitly unsigned preview.

Windows uninstall retains settings and SQLite history by default; the documentation gives the application-data path for optional manual removal. macOS uninstall means quitting the app, disabling autostart, and removing the app from `/Applications`; settings and SQLite history are retained by default and documented separately.

## 12. Rollout

1. Add testable version/artifact validation utilities and tests.
2. Add native quality builds as non-publishing workflow artifacts.
3. Resolve native compile and bundle failures without touching the protected Linux lane.
4. Run and document Windows/macOS smoke tests.
5. Add independent `native-v*-preview.*` tag-release aggregation for preview artifacts.
6. Update README and release documentation with an explicit capability matrix and preview warnings.
7. Add signing and notarization only after credentials are provisioned.
8. Promote each OS independently after its stable gate passes.

## 13. Expected File Changes

- `.github/workflows/quality.yml`
- `.github/workflows/native-preview.yml`
- `src-tauri/tauri.conf.json`
- `src-tauri/Cargo.toml` only if required by verified native configuration
- `src-tauri/entitlements.plist` only if required by the final macOS capabilities
- `scripts/native_release.py` release validation and artifact staging utility
- `tests/test_native_release.py` unit tests for the native release utility
- `docs/RELEASE.md`
- `docs/DEVELOPMENT.md`
- `docs/SECURITY.md`
- `README.md`

The Python collector and GTK implementation under `agentbar/`, `scripts/build_linux_release.py`, `tests/test_agentbar.py`, and `.github/workflows/release.yml` are outside the allowed change set.

## 14. Acceptance Criteria

- Existing Python/Linux compile, full discovered unit-test suite, Debian build, checksum, metadata, installed CLI, status command, and Xvfb GTK smoke gates remain green.
- Native Tauri builds run on Windows and both macOS architectures.
- Expected Windows and macOS preview artifacts are created with deterministic names and verified checksums.
- The native preview workflow never publishes a partial native artifact set; native failure never blocks or modifies an independent Linux `v*` release.
- Documentation states provider capability differences and unsigned preview status accurately.
- No signing secret, provider credential, access token, or absolute developer path is committed or embedded.
- Stable support is not claimed until signing and clean-machine lifecycle tests pass for that platform.
