"""Cross-platform Desktop App bundler and Desktop Shortcut installer for AgentBar.

Supports:
- Single-file executable bundling (.pyz zipapp / standalone binary)
- High-DPI App Icon generation (PNG & Windows ICO)
- Linux: ~/Desktop/AgentBar.desktop + ~/.local/share/applications/agentbar.desktop + ~/.local/bin/agentbar (with GNOME gio metadata::trusted)
- macOS: Native AgentBar.app bundle on ~/Desktop/AgentBar.app
- Windows: AgentBar.pyw / .exe + ~/Desktop/AgentBar.lnk shortcut
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import zipapp
from pathlib import Path
from typing import Dict, Optional

from .detectors import collect_usage_snapshot
from .menubar import create_tray_icon_image


def generate_app_icons(project_root: Path) -> Dict[str, Path]:
    """Generate 256x256 PNG and multi-size ICO icons in assets/."""
    assets_dir = project_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    png_path = assets_dir / "agentbar.png"
    ico_path = assets_dir / "agentbar.ico"

    snap = collect_usage_snapshot()
    img = create_tray_icon_image(snap, size=256)
    img.save(png_path, format="PNG")
    img.save(
        ico_path,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    return {"png": png_path, "ico": ico_path}


def build_zipapp_binary(project_root: Path) -> Path:
    """Bundle the entire agentbar package into a single portable executable dist/agentbar."""
    dist_dir = project_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    is_win = platform.system().lower().startswith("win")
    out_name = "agentbar.pyz" if is_win else "agentbar"
    target_bin = dist_dir / out_name

    with tempfile.TemporaryDirectory() as stage_tmp:
        stage_path = Path(stage_tmp)
        shutil.copytree(
            project_root / "agentbar",
            stage_path / "agentbar",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        zipapp.create_archive(
            stage_path,
            target=target_bin,
            interpreter="/usr/bin/env python3" if not is_win else None,
            main="agentbar.cli:main",
            compressed=True,
        )

    target_bin.chmod(target_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target_bin


def build_macos_app_bundle(
    project_root: Path,
    binary_path: Path,
    icon_png: Path,
    output_dir: Optional[Path] = None,
) -> Path:
    """Create a native macOS AgentBar.app bundle."""
    base_dir = output_dir or (project_root / "dist")
    app_dir = base_dir / "AgentBar.app"
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    res_dir = contents_dir / "Resources"

    macos_dir.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)

    # Copy bundled zipapp and icon
    bundled_bin = macos_dir / "agentbar-core"
    shutil.copy2(binary_path, bundled_bin)
    bundled_bin.chmod(0o755)
    shutil.copy2(icon_png, res_dir / "agentbar.png")

    # Launcher script inside Contents/MacOS/AgentBar
    launcher = macos_dir / "AgentBar"
    launcher.write_text(
        '#!/usr/bin/env bash\n'
        'DIR="$(cd "$(dirname "$0")" && pwd)"\n'
        'exec python3 "$DIR/agentbar-core" bar "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)

    info_plist = contents_dir / "Info.plist"
    info_plist.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>AgentBar</string>
    <key>CFBundleDisplayName</key>
    <string>AgentBar AI Usage Monitor</string>
    <key>CFBundleIdentifier</key>
    <string>dev.agentbar.monitor</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>AgentBar</string>
    <key>CFBundleIconFile</key>
    <string>agentbar.png</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
""",
        encoding="utf-8",
    )
    return app_dir


def create_linux_desktop_entry(
    binary_path: Path,
    icon_png: Path,
) -> str:
    """Generate freedesktop.org .desktop file content with Background & Settings Actions."""
    return f"""[Desktop Entry]
Version=1.0
Type=Application
Name=AgentBar AI Monitor
GenericName=AI Coding Engine Usage Bar
Comment=Chạy ngầm theo dõi Quota của Claude Code, Codex, Antigravity, Qoder trên thanh Menu Bar
Exec={binary_path} start
Icon={icon_png}
Terminal=false
Categories=Development;Utility;Monitor;
Keywords=AI;Claude;Codex;Antigravity;Qoder;Token;Usage;Settings;
StartupNotify=false
Actions=ToggleFloatingBar;OpenSettings;StopDaemon;TerminalWatch;

[Desktop Action ToggleFloatingBar]
Name=👁 Hiện / Ẩn Thanh Bar Góc Dưới (Show/Hide Floating Bar)
Exec={binary_path} toggle-bar

[Desktop Action OpenSettings]
Name=⚙ Mở Cài Đặt (Settings)
Exec={binary_path} settings

[Desktop Action StopDaemon]
Name=⏹ Tắt Ứng Dụng Chạy Ngầm (Stop)
Exec={binary_path} stop

[Desktop Action TerminalWatch]
Name=📊 Mở Bảng Theo Dõi Trực Tiếp (Terminal TUI)
Exec={binary_path} watch
Terminal=true
"""


def install_desktop_app(
    project_root: Optional[Path] = None,
    desktop_dir: Optional[Path] = None,
    autostart: bool = False,
) -> Dict[str, str]:
    """Package AgentBar into a single executable and install shortcuts to Desktop & App Menu."""
    root = (project_root or Path(__file__).resolve().parent.parent).resolve()
    icons = generate_app_icons(root)
    bundled_bin = build_zipapp_binary(root)

    home = Path.home()
    desk = desktop_dir or (home / "Desktop")
    sys_name = platform.system().lower()
    result: Dict[str, str] = {
        "bundled_binary": str(bundled_bin),
        "icon_png": str(icons["png"]),
        "icon_ico": str(icons["ico"]),
    }

    # Always build macOS .app bundle inside dist/ for cross-platform distribution
    macos_app = build_macos_app_bundle(root, bundled_bin, icons["png"])
    result["macos_app_bundle"] = str(macos_app)

    if sys_name == "linux":
        # 1. Install CLI binary to ~/.local/bin/agentbar
        local_bin_dir = home / ".local" / "bin"
        local_bin_dir.mkdir(parents=True, exist_ok=True)
        installed_bin = local_bin_dir / "agentbar"
        shutil.copy2(bundled_bin, installed_bin)
        installed_bin.chmod(0o755)
        result["cli_installed"] = str(installed_bin)

        desktop_content = create_linux_desktop_entry(installed_bin, icons["png"])

        # 2. Install to ~/Desktop/AgentBar.desktop
        if desk.is_dir():
            desk_file = desk / "AgentBar.desktop"
            desk_file.write_text(desktop_content, encoding="utf-8")
            desk_file.chmod(0o755)
            # Mark as trusted on Ubuntu GNOME so double-click works immediately
            if shutil.which("gio"):
                try:
                    subprocess.run(
                        ["gio", "set", str(desk_file), "metadata::trusted", "true"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
            result["desktop_shortcut"] = str(desk_file)

        # 3. Install to ~/.local/share/applications/agentbar.desktop
        apps_dir = home / ".local" / "share" / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        app_entry = apps_dir / "agentbar.desktop"
        app_entry.write_text(desktop_content, encoding="utf-8")
        app_entry.chmod(0o755)
        if shutil.which("update-desktop-database"):
            try:
                subprocess.run(
                    ["update-desktop-database", str(apps_dir)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        result["app_menu_shortcut"] = str(app_entry)

        # 4. Optional Autostart on login
        if autostart:
            auto_dir = home / ".config" / "autostart"
            auto_dir.mkdir(parents=True, exist_ok=True)
            auto_file = auto_dir / "agentbar.desktop"
            auto_file.write_text(desktop_content, encoding="utf-8")
            auto_file.chmod(0o755)
            result["autostart_entry"] = str(auto_file)

    elif sys_name == "darwin":
        if desk.is_dir():
            target_app = desk / "AgentBar.app"
            if target_app.exists():
                shutil.rmtree(target_app)
            shutil.copytree(macos_app, target_app)
            result["desktop_shortcut"] = str(target_app)

    elif sys_name.startswith("win"):
        # Create windowless .pyw launcher + Windows Desktop .lnk shortcut
        pyw_path = root / "dist" / "AgentBar.pyw"
        pyw_path.write_text(
            f'import sys\nsys.path.insert(0, r"{root}")\n'
            'from agentbar.cli import main\nsys.exit(main(["bar"]))\n',
            encoding="utf-8",
        )
        result["windows_launcher"] = str(pyw_path)
        if desk.is_dir():
            lnk_path = desk / "AgentBar.lnk"
            ps_cmd = (
                f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{lnk_path}");'
                f'$s.TargetPath="pythonw.exe";'
                f'$s.Arguments=\'"{pyw_path}"\';'
                f'$s.IconLocation="{icons["ico"]}";'
                f'$s.WorkingDirectory="{root}";'
                f'$s.Save()'
            )
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                result["desktop_shortcut"] = str(lnk_path)
            except Exception:
                pass

    return result
