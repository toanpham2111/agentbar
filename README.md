# Kio Usage Monitoring

Kio Usage Monitoring is a lightweight Linux menu-bar app that displays verified
usage signals for AI development tools without opening a dashboard window.

## Supported providers

| Provider | Menu-bar usage | Detail popup | Source |
|---|---:|---:|---|
| Claude Code | Yes | Session and weekly limits | Local OAuth session + Anthropic usage API |
| OpenAI Codex | Yes | Five-hour and weekly limits | Local OAuth session + OpenAI usage API |
| Google Antigravity | Yes when its language server is running | Every quota group returned by Antigravity | Local Antigravity RPC |
| Qoder | Detection only | Live quota unavailable | No verified live quota source |

Unknown or unavailable usage is shown as `--`. The app does not fabricate quota
percentages. Antigravity must be open because its local RPC stops when
Antigravity is fully closed. The popup tells the user to open Antigravity when
live data is unavailable.

## Install on Ubuntu/Debian

1. Download `Kio-Usage-Monitoring_1.0.0_amd64.deb` from the
   [v1.0.0 release](https://github.com/toanpham2111/agentbar/releases/tag/v1.0.0).
2. Open the downloaded file and select **Install**.
3. Launch **Kio Usage Monitoring** from the application menu.
4. On first launch, choose whether Kio should start automatically when you sign in.

The app runs in the system menu bar and uses no dashboard window. Command-line
installation is also supported:

```bash
sudo apt install ./Kio-Usage-Monitoring_1.0.0_amd64.deb
```

## Development

```bash
python3 -m unittest discover -s tests -q
python3 scripts/build_linux_release.py 1.0.0
```

The Linux runtime uses Python 3, GTK 3, Ayatana AppIndicator, and Pillow. The
release package declares these dependencies so APT installs them automatically.

## Privacy

Provider credentials and RPC tokens remain on the local device and are used only
to request usage from the provider or its local service. Prompts, project source
code, and credentials are not uploaded by Kio Usage Monitoring.

## License

[MIT](LICENSE) © 2026 KIO Digital.
