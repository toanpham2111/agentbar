"""Persistent configuration, autostart, and background daemon manager for AgentBar."""

from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def get_config_path() -> Path:
    return Path.home() / ".config" / "agentbar" / "settings.json"


def get_pid_path() -> Path:
    return Path.home() / ".cache" / "agentbar" / "agentbar.pid"


def get_autostart_desktop_path() -> Path:
    return Path.home() / ".config" / "autostart" / "agentbar.desktop"


@dataclass
class AgentBarConfig:
    """User-configurable settings for AgentBar."""

    enabled_engines: Dict[str, bool] = field(
        default_factory=lambda: {
            "claude": True,
            "codex": True,
            "antigravity": True,
            "qoder": False,
        }
    )
    autostart_on_login: bool = False
    autostart_prompted: bool = False
    start_collapsed: bool = True
    desktop_notifications: bool = True
    refresh_interval_sec: int = 30
    warning_threshold_percent: int = 80
    bar_position: str = "bottom-right"  # "bottom-right", "right", "center", "left"
    bar_metric_mode: str = "session"  # "session", "highest", "compact"
    show_floating_bar: bool = field(
        default_factory=lambda: platform.system().lower() != "linux"
    )

    def is_engine_enabled(self, engine_id: str) -> bool:
        return bool(self.enabled_engines.get(engine_id, True))

    def set_engine_enabled(self, engine_id: str, enabled: bool) -> None:
        self.enabled_engines[engine_id] = bool(enabled)


def load_config(config_path: Optional[Path] = None) -> AgentBarConfig:
    """Load settings from ~/.config/agentbar/settings.json, or return defaults."""
    path = config_path or get_config_path()
    cfg = AgentBarConfig()
    if not path.is_file():
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw.get("enabled_engines"), dict):
            for k, v in raw["enabled_engines"].items():
                cfg.enabled_engines[str(k)] = bool(v)
        if "autostart_on_login" in raw:
            cfg.autostart_on_login = bool(raw["autostart_on_login"])
        if "autostart_prompted" in raw:
            cfg.autostart_prompted = bool(raw["autostart_prompted"])
        if "start_collapsed" in raw:
            cfg.start_collapsed = bool(raw["start_collapsed"])
        if "desktop_notifications" in raw:
            cfg.desktop_notifications = bool(raw["desktop_notifications"])
        if "refresh_interval_sec" in raw:
            cfg.refresh_interval_sec = max(5, int(raw["refresh_interval_sec"]))
        if "warning_threshold_percent" in raw:
            cfg.warning_threshold_percent = max(
                10, min(99, int(raw["warning_threshold_percent"]))
            )
        if raw.get("bar_position") in ("bottom-right", "left", "center", "right"):
            cfg.bar_position = str(raw["bar_position"])
        if raw.get("bar_metric_mode") in ("session", "highest", "compact"):
            cfg.bar_metric_mode = str(raw["bar_metric_mode"])
        if "show_floating_bar" in raw:
            cfg.show_floating_bar = bool(raw["show_floating_bar"])
    except Exception:
        pass
    return cfg


def save_config(cfg: AgentBarConfig, config_path: Optional[Path] = None) -> Path:
    """Save settings to ~/.config/agentbar/settings.json and sync OS autostart."""
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
    if config_path is None:
        sync_os_autostart(cfg.autostart_on_login)
    return path


def sync_os_autostart(enabled: bool) -> None:
    """Enable or disable OS login autostart entry."""
    sys_name = platform.system().lower()
    home = Path.home()

    if sys_name == "linux":
        auto_file = get_autostart_desktop_path()
        if enabled:
            auto_file.parent.mkdir(parents=True, exist_ok=True)
            current_entry = Path(sys.argv[0]).resolve()
            candidates = (
                current_entry,
                home / ".local" / "bin" / "agentbar",
                Path("/usr/bin/kio-usage-monitoring"),
            )
            bin_path = next((path for path in candidates if path.is_file()), candidates[1])
            content = (
                "[Desktop Entry]\n"
                "Version=1.0\n"
                "Type=Application\n"
                "Name=Kio Usage Monitoring\n"
                "Comment=Background AI usage monitoring\n"
                f"Exec={bin_path} bar --collapsed\n"
                "Icon=kio-usage-monitoring\n"
                "Terminal=false\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            auto_file.write_text(content, encoding="utf-8")
            auto_file.chmod(0o755)
        else:
            if auto_file.is_file():
                try:
                    auto_file.unlink()
                except OSError:
                    pass
    elif sys_name == "darwin":
        plist_path = home / "Library" / "LaunchAgents" / "dev.agentbar.monitor.plist"
        if enabled:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            bin_path = home / ".local" / "bin" / "agentbar"
            plist_path.write_text(
                f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>dev.agentbar.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>{bin_path}</string>
        <string>bar</string>
        <string>--collapsed</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
""",
                encoding="utf-8",
            )
        elif plist_path.is_file():
            try:
                plist_path.unlink()
            except OSError:
                pass


def get_running_daemon_pid() -> Optional[int]:
    """Return PID of running AgentBar background process if alive."""
    pid_file = get_pid_path()
    if not pid_file.is_file():
        return None
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        if pid <= 0:
            return None
        os.kill(pid, 0)
        return pid
    except Exception:
        try:
            pid_file.unlink()
        except OSError:
            pass
        return None


def write_current_pid() -> None:
    pid_file = get_pid_path()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()), encoding="utf-8")


def remove_current_pid() -> None:
    pid_file = get_pid_path()
    if pid_file.is_file():
        try:
            if int(pid_file.read_text(encoding="utf-8").strip()) == os.getpid():
                pid_file.unlink()
        except Exception:
            pass


def start_background_daemon(open_settings: bool = False) -> Tuple[bool, int]:
    """Start AgentBar Menu Bar app in the background, or signal existing instance."""
    existing_pid = get_running_daemon_pid()
    if existing_pid is not None and existing_pid != os.getpid():
        # Signal running instance to toggle popover (SIGUSR1) or open settings (SIGUSR2)
        sig = getattr(signal, "SIGUSR2" if open_settings else "SIGUSR1", None)
        if sig is not None:
            try:
                os.kill(existing_pid, sig)
            except OSError:
                pass
        return (False, existing_pid)

    entry_script = Path(sys.argv[0]).resolve()
    valid_entry_names = ("agentbar", "agentbar.py", "kio-usage-monitoring")
    if not entry_script.is_file() or entry_script.name not in valid_entry_names:
        which_agentbar = shutil.which("agentbar")
        which_kio = shutil.which("kio-usage-monitoring")
        candidates = (
            Path(which_agentbar) if which_agentbar else None,
            Path(which_kio) if which_kio else None,
            Path.home() / ".local" / "bin" / "agentbar",
            Path("/usr/bin/kio-usage-monitoring"),
            Path("/usr/local/bin/agentbar"),
            Path(__file__).resolve().parent.parent / "agentbar.py",
        )
        resolved_candidates = tuple(p for p in candidates if p is not None)
        entry_script = next(
            (path for path in resolved_candidates if path.is_file()),
            Path(__file__).resolve().parent.parent / "agentbar.py",
        )
    cmd = [sys.executable, str(entry_script), "bar"]
    cfg = load_config()
    if cfg.start_collapsed and not open_settings:
        cmd.append("--collapsed")
    if open_settings:
        cmd.append("--settings")

    log_dir = Path.home() / ".cache" / "agentbar"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = open(log_dir / "daemon.log", "a", encoding="utf-8")

    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    time.sleep(0.25)
    return (True, proc.pid)


def toggle_floating_bar_visibility() -> bool:
    """Toggle show_floating_bar in config and signal running daemon (SIGHUP)."""
    cfg = load_config()
    cfg.show_floating_bar = not cfg.show_floating_bar
    save_config(cfg)
    pid = get_running_daemon_pid()
    if pid is not None and hasattr(signal, "SIGHUP"):
        try:
            os.kill(pid, signal.SIGHUP)
        except OSError:
            pass
    return cfg.show_floating_bar


def stop_background_daemon() -> bool:
    """Stop the running AgentBar background daemon if active."""
    pid = get_running_daemon_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(15):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except OSError:
                break
    except OSError:
        pass
    pid_file = get_pid_path()
    if pid_file.is_file():
        try:
            pid_file.unlink()
        except OSError:
            pass
    return True
