"""Command-line interface for AgentBar."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .config import (
    get_running_daemon_pid,
    load_config,
    start_background_daemon,
    stop_background_daemon,
    toggle_floating_bar_visibility,
)
from .detectors import collect_usage_snapshot
from .menubar import launch_menubar
from .tui import render_ansi_dashboard, run_live_watch


def _print_install_guide() -> None:
    script_path = Path(__file__).resolve().parent.parent / "agentbar.py"
    print(
        f"""⚡ Kio Usage Monitoring — Background App & Terminal Guide
================================================================

1. Start in Background:
   agentbar start

2. Open Settings UI:
   agentbar settings

3. Stop Background App:
   agentbar stop

4. Live Terminal Monitor (htop style for terminal-only workflow):
   agentbar watch

5. tmux Status Bar (add to ~/.tmux.conf):
   set -g status-interval 15
   set -g status-right "#(python3 {script_path} --tmux)"

6. Linux Waybar (add to ~/.config/waybar/config):
   "custom/agentbar": {{
       "exec": "python3 {script_path} --waybar",
       "return-type": "json",
       "interval": 15,
       "on-click": "agentbar start"
   }}

7. macOS SwiftBar / xbar Menu Bar Plugin:
   Create executable script ~/Library/Application Support/SwiftBar/agentbar.15s.sh:
   #!/usr/bin/env bash
   python3 {script_path} --swiftbar
"""
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentbar",
        description=(
            "Cross-platform Background Menu Bar / System Tray & Terminal Usage Monitor "
            "for Claude Code, OpenAI Codex, Antigravity, Qoder & AI Coding Engines."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=[
            "status",
            "start",
            "stop",
            "toggle-bar",
            "settings",
            "bar",
            "tray",
            "watch",
            "install-guide",
            "install-desktop",
        ],
        help=(
            "Action: 'status' (CLI view), 'start' (run in background / toggle bar), "
            "'stop' (stop background daemon), 'toggle-bar' (hide/show bottom-right floating bar), "
            "'settings' (open Settings UI), 'bar'/'tray' (foreground bar), 'watch' (live TUI), 'install-desktop'"
        ),
    )
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="Enable Kio Usage Monitoring to start automatically on login",
    )
    parser.add_argument(
        "-s",
        "--short",
        action="store_true",
        help="Print single-line menu bar summary",
    )
    parser.add_argument(
        "-c",
        "--compact",
        action="store_true",
        help="Print ultra-compact single-line summary for narrow status bars",
    )
    parser.add_argument(
        "--tmux",
        action="store_true",
        help="Print tmux status-right formatted string with color codes",
    )
    parser.add_argument(
        "--waybar",
        action="store_true",
        help="Print JSON object for Linux Waybar / Polybar custom module",
    )
    parser.add_argument(
        "--swiftbar",
        action="store_true",
        help="Print macOS SwiftBar / xbar menu bar plugin format",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full structured usage telemetry as JSON",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all supported engines including disabled/uninstalled ones",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in terminal output",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Refresh interval in seconds (overrides settings.json)",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "gtk", "pystray"],
        default="auto",
        help="Menu bar UI backend (default: auto)",
    )
    parser.add_argument(
        "--collapsed",
        action="store_true",
        help="Start the Menu Bar widget collapsed (pill only) in the background",
    )
    parser.add_argument(
        "--settings",
        action="store_true",
        help="Open the Menu Bar Popover directly to the Settings panel",
    )
    parser.add_argument(
        "--tab",
        choices=["all", "claude", "codex", "antigravity", "qoder", "settings"],
        default=None,
        help="Open the Menu Bar Popover directly to a specific engine tab",
    )
    parser.add_argument(
        "--screenshot",
        type=str,
        default=None,
        help="Capture a PNG screenshot of the Menu Bar Popover window and exit (for QA testing)",
    )
    parser.add_argument(
        "--auto-close-ms",
        type=int,
        default=None,
        help="Automatically close Menu Bar window after N milliseconds",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"agentbar {__version__}",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "install-guide":
        _print_install_guide()
        return 0

    if args.command == "install-desktop":
        from .packaging import install_desktop_app

        res = install_desktop_app(autostart=args.autostart)
        print("⚡ Kio Usage Monitoring packaged and installed successfully!")
        for k, v in res.items():
            print(f"  - {k}: {v}")
        return 0

    if args.command == "start":
        started_new, pid = start_background_daemon(open_settings=args.settings)
        if started_new:
            print(f"⚡ Kio Usage Monitoring is running in the background (PID: {pid}).")
        else:
            print(f"⚡ Kio Usage Monitoring is already running (PID: {pid}) — toggled window.")
        return 0

    if args.command == "stop":
        stopped = stop_background_daemon()
        if stopped:
            print("⏹ Kio Usage Monitoring stopped.")
        else:
            print("Kio Usage Monitoring is not running.")
        return 0

    if args.command == "toggle-bar":
        new_vis = toggle_floating_bar_visibility()
        state_str = "SHOWN (bottom-right)" if new_vis else "HIDDEN"
        print(f"👁 Bottom-right floating bar is now {state_str}.")
        return 0

    if args.command == "settings":
        existing_pid = get_running_daemon_pid()
        if existing_pid is not None:
            start_background_daemon(open_settings=True)
            print(f"⚙ Opened Kio Usage Monitoring Settings (PID: {existing_pid}).")
            return 0
        return launch_menubar(
            backend=args.backend,
            refresh_interval=args.interval,
            start_expanded=True,
            open_settings=True,
            screenshot_path=args.screenshot,
            auto_close_ms=args.auto_close_ms,
        )

    if args.command == "watch":
        cfg = load_config()
        run_live_watch(interval=float(max(1, args.interval or cfg.refresh_interval_sec)))
        return 0

    if args.command in ("bar", "tray"):
        return launch_menubar(
            backend=args.backend,
            refresh_interval=args.interval,
            start_expanded=not args.collapsed,
            open_settings=args.settings,
            initial_tab=args.tab,
            screenshot_path=args.screenshot,
            auto_close_ms=args.auto_close_ms,
        )

    snapshot = collect_usage_snapshot(include_extra=args.all)

    if args.json:
        print(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.waybar:
        print(json.dumps(snapshot.to_waybar_dict(), ensure_ascii=False))
        return 0

    if args.swiftbar:
        print(snapshot.to_swiftbar_string())
        return 0

    if args.tmux:
        print(snapshot.to_tmux_string())
        return 0

    if args.compact:
        print(snapshot.to_bar_string(compact=True))
        return 0

    if args.short:
        print(snapshot.to_bar_string(compact=False))
        return 0

    use_color = not args.no_color and sys.stdout.isatty()
    print(
        render_ansi_dashboard(
            snapshot,
            show_uninstalled=args.all,
            use_color=use_color,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
