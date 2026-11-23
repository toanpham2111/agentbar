# Release

GitHub Actions builds Linux DEB/AppImage, Windows NSIS/MSI, and macOS DMG artifacts on native runners. Release publication requires all quality, native-test, and bundle jobs to pass.

Before public distribution:

1. Replace the provisional KIO icon with approved brand assets.
2. Configure Apple signing/notarization secrets.
3. Configure Windows code-signing secrets.
4. Verify the installed app, system tray, notification permissions, autostart, SQLite persistence, and clean uninstall on every target.
5. Publish SHA-256 checksums and provider limitations.

CI configuration is not equivalent to completed OS verification. Record the successful workflow URL and artifact hashes in each release note.
