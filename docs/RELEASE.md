# Release

Stable releases publish the GTK menu-bar application as a Debian package.

## Build and verify

```bash
python3 -m compileall -q agentbar tests scripts
python3 -m unittest discover -s tests -q
python3 scripts/build_linux_release.py 1.0.0
dpkg-deb --info release/Kio-Usage-Monitoring_1.0.0_amd64.deb
dpkg-deb --contents release/Kio-Usage-Monitoring_1.0.0_amd64.deb
(cd release && sha256sum -c SHA256SUMS)
```

Pushing a stable `v*` tag runs the release workflow, repeats verification, and
publishes the `.deb` installer plus `SHA256SUMS` to GitHub Releases.

Windows and macOS installers are not published until they have native build,
signing, installation, startup, tray, and uninstall verification.
