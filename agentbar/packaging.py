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
import re
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


DEBIAN_RUNTIME_DEPENDENCIES = (
    "python3 (>= 3.8), python3-gi, python3-pil, gir1.2-gtk-3.0, "
    "gir1.2-ayatanaappindicator3-0.1"
)


def validate_release_version(version: str) -> str:
    """Validate a stable semantic version accepted by Debian package metadata."""
    normalized = version.strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not re.fullmatch(r"\d+\.\d+\.\d+", normalized):
        raise ValueError("Release version must use MAJOR.MINOR.PATCH")
    return normalized


def generate_app_icons(project_root: Path) -> Dict[str, Path]:
    """Use the branded PNG and generate its multi-size Windows ICO variant."""
    from PIL import Image

    assets_dir = project_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    png_path = assets_dir / "agentbar.png"
    ico_path = assets_dir / "agentbar.ico"

    if png_path.is_file():
        img = Image.open(png_path).convert("RGBA")
    else:
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


def build_linux_deb(
    project_root: Path,
    version: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """Build a click-installable Debian package for the GTK menu-bar app."""
    release_version = validate_release_version(version)
    if platform.system().lower() != "linux":
        raise RuntimeError("The Debian package must be built on Linux")
    if shutil.which("dpkg-deb") is None:
        raise RuntimeError("dpkg-deb is required to build the Linux installer")

    root = project_root.resolve()
    destination = (output_dir or (root / "release")).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    icons = generate_app_icons(root)
    bundled_binary = build_zipapp_binary(root)
    architecture = subprocess.check_output(
        ["dpkg", "--print-architecture"], text=True, timeout=5
    ).strip()
    package_path = destination / f"Kio-Usage-Monitoring_{release_version}_{architecture}.deb"

    with tempfile.TemporaryDirectory() as stage_tmp:
        stage = Path(stage_tmp) / "kio-usage-monitoring"
        control_dir = stage / "DEBIAN"
        bin_dir = stage / "usr" / "bin"
        apps_dir = stage / "usr" / "share" / "applications"
        icon_dir = stage / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
        provider_dir = stage / "usr" / "share" / "kio-usage-monitoring" / "providers"
        for directory in (control_dir, bin_dir, apps_dir, icon_dir):
            directory.mkdir(parents=True, exist_ok=True)

        installed_binary = bin_dir / "kio-usage-monitoring"
        shutil.copy2(bundled_binary, installed_binary)
        installed_binary.chmod(0o755)
        (bin_dir / "agentbar").symlink_to("kio-usage-monitoring")
        shutil.copy2(icons["png"], icon_dir / "kio-usage-monitoring.png")

        provider_source = root / "assets" / "providers"
        if provider_source.is_dir():
            shutil.copytree(provider_source, provider_dir)

        desktop_entry = """[Desktop Entry]
Version=1.0
Type=Application
Name=Kio Usage Monitoring
GenericName=AI Usage Monitor
Comment=Monitor AI provider usage from the system menu bar
Exec=/usr/bin/kio-usage-monitoring start
Icon=kio-usage-monitoring
Terminal=false
Categories=Development;Utility;Monitor;
Keywords=AI;Claude;Codex;Antigravity;Qoder;Usage;
StartupNotify=false
"""
        (apps_dir / "kio-usage-monitoring.desktop").write_text(
            desktop_entry, encoding="utf-8"
        )
        installed_size = max(
            1,
            sum(path.stat().st_size for path in stage.rglob("*") if path.is_file())
            // 1024,
        )
        control_text = f"""Package: kio-usage-monitoring
Version: {release_version}
Section: utils
Priority: optional
Architecture: {architecture}
Depends: {DEBIAN_RUNTIME_DEPENDENCIES}
Installed-Size: {installed_size}
Maintainer: KIO Digital
Description: Lightweight AI usage monitor for the Linux menu bar
 Monitors verified usage signals for Claude Code, OpenAI Codex,
 Google Antigravity, and Qoder without a dashboard window.
"""
        (control_dir / "control").write_text(control_text, encoding="utf-8")
        subprocess.run(
            ["dpkg-deb", "--build", "--root-owner-group", str(stage), str(package_path)],
            check=True,
            timeout=60,
        )

    return package_path


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
    <string>Kio Usage Monitoring</string>
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
Name=Kio Usage Monitoring
GenericName=AI Usage Monitor
Comment=Monitor Claude Code, Codex, Antigravity, Qoder, and System Resources from the menu bar
Exec={binary_path} start
Icon=kio-usage-monitoring
Terminal=false
Categories=Development;Utility;Monitor;
Keywords=AI;Claude;Codex;Antigravity;Qoder;Token;Usage;Settings;System;CPU;RAM;Disk;
StartupNotify=false
Actions=ToggleFloatingBar;OpenSettings;StopDaemon;TerminalWatch;

[Desktop Action ToggleFloatingBar]
Name=👁 Show / Hide Floating Bar
Exec={binary_path} toggle-bar

[Desktop Action OpenSettings]
Name=⚙ Open Settings
Exec={binary_path} settings

[Desktop Action StopDaemon]
Name=⏹ Stop Background App
Exec={binary_path} stop

[Desktop Action TerminalWatch]
Name=📊 Open Live Terminal Monitor
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
    sys_name = platform.system().lower()
    desk = desktop_dir
    if desk is None:
        if sys_name.startswith("win"):
            desk_candidates = []
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
                )
                val, _ = winreg.QueryValueEx(key, "Desktop")
                winreg.CloseKey(key)
                expanded = os.path.expandvars(str(val))
                if Path(expanded).is_dir():
                    desk_candidates.append(Path(expanded))
            except Exception:
                pass
            onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer") or os.environ.get("OneDriveCommercial")
            if onedrive and (Path(onedrive) / "Desktop").is_dir():
                desk_candidates.append(Path(onedrive) / "Desktop")
            desk_candidates.append(home / "Desktop")
            desk = next((d for d in desk_candidates if d.is_dir()), home / "Desktop")
        else:
            desk = home / "Desktop"
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

        installed_icon = home / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "kio-usage-monitoring.png"
        installed_icon.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icons["png"], installed_icon)
        result["icon_installed"] = str(installed_icon)

        provider_source = root / "assets" / "providers"
        provider_target = home / ".local" / "share" / "agentbar" / "providers"
        if provider_source.is_dir():
            provider_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(provider_source, provider_target, dirs_exist_ok=True)
            result["provider_icons_installed"] = str(provider_target)

        desktop_content = create_linux_desktop_entry(installed_bin, icons["png"])

        # 2. Install the branded desktop shortcut
        if desk.is_dir():
            desk_file = desk / "Kio Usage Monitoring.desktop"
            legacy_desk_file = desk / "AgentBar.desktop"
            if legacy_desk_file.is_file() and legacy_desk_file != desk_file:
                legacy_desk_file.replace(desk_file)
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

        # 3. Install the branded app menu entry
        apps_dir = home / ".local" / "share" / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        app_entry = apps_dir / "kio-usage-monitoring.desktop"
        legacy_app_entry = apps_dir / "agentbar.desktop"
        if legacy_app_entry.is_file() and legacy_app_entry != app_entry:
            legacy_app_entry.replace(app_entry)
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
        py_exe = Path(sys.executable)
        pyw_exe = py_exe.with_name("pythonw.exe")
        target_exe = str(pyw_exe) if pyw_exe.is_file() else str(py_exe)
        ico_path = str(icons["ico"])

        target_desks = [desk]
        local_desk = home / "Desktop"
        if local_desk.is_dir() and local_desk not in target_desks:
            target_desks.append(local_desk)

        import base64

        def _run_ps_script(script_text: str) -> None:
            try:
                enc = base64.b64encode(script_text.encode("utf-16le")).decode("ascii")
                subprocess.run(
                    ["powershell", "-NoProfile", "-EncodedCommand", enc],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

        for d in target_desks:
            if not d.is_dir():
                continue
            for lnk_name in ("Kio Usage Monitoring.lnk", "AgentBar.lnk"):
                lnk_file = d / lnk_name
                ps_script = (
                    f"$ws = New-Object -ComObject WScript.Shell\n"
                    f"$s = $ws.CreateShortcut('{lnk_file}')\n"
                    f"$s.TargetPath = '{target_exe}'\n"
                    f"$s.Arguments = '\"{pyw_path}\"'\n"
                    f"$s.IconLocation = '{ico_path}'\n"
                    f"$s.WorkingDirectory = '{root}'\n"
                    f"$s.Save()\n"
                )
                _run_ps_script(ps_script)
            result["desktop_shortcut"] = str(d / "Kio Usage Monitoring.lnk")

        start_programs = home / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if start_programs.is_dir():
            start_lnk = start_programs / "Kio Usage Monitoring.lnk"
            ps_script = (
                f"$ws = New-Object -ComObject WScript.Shell\n"
                f"$s = $ws.CreateShortcut('{start_lnk}')\n"
                f"$s.TargetPath = '{target_exe}'\n"
                f"$s.Arguments = '\"{pyw_path}\"'\n"
                f"$s.IconLocation = '{ico_path}'\n"
                f"$s.WorkingDirectory = '{root}'\n"
                f"$s.Save()\n"
            )
            _run_ps_script(ps_script)
            result["app_menu_shortcut"] = str(start_lnk)

    return result
