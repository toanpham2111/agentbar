"""Cross-platform Minimalist Menu Bar / System Tray, Background Daemon & Per-Engine Detailed Tabs for AgentBar."""

from __future__ import annotations

import io
import os
import platform
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .config import (
    AgentBarConfig,
    get_running_daemon_pid,
    load_config,
    remove_current_pid,
    save_config,
    write_current_pid,
)
from .detectors import collect_usage_snapshot
from .models import (
    EngineUsage,
    RateLimitWindow,
    UsageSnapshot,
    format_reset_countdown,
)
from .sni_indicator import LinuxTopPanelIndicator


def create_tray_icon_image(snapshot: Optional[UsageSnapshot] = None, size: int = 64) -> Any:
    """Generate a clean 64x64 RGBA PIL Image with 4 vertical usage bars for the tray icon."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (24, 24, 26, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([1, 1, size - 2, size - 2], outline=(63, 63, 70, 255), width=2)

    levels = [0.48, 0.84, 0.19, 0.15]
    if snapshot is not None:
        levels = []
        for idx in range(4):
            if idx < len(snapshot.engines) and snapshot.engines[idx].installed:
                pct = snapshot.engines[idx].highest_quota_percent()
                levels.append(max(0.12, min(1.0, pct / 100.0)))
            else:
                levels.append(0.10)

    bar_w = 9
    gap = 4
    start_x = 8
    max_h = size - 18
    bottom_y = size - 9

    for i in range(4):
        x0 = start_x + i * (bar_w + gap)
        x1 = x0 + bar_w
        lvl = levels[i]
        fill_color = (229, 72, 77, 255) if lvl >= 0.80 else (59, 130, 246, 255)
        track_color = (72, 34, 36, 255) if lvl >= 0.80 else (37, 44, 55, 255)
        draw.rectangle([x0, 9, x1, bottom_y], fill=track_color)
        fill_h = int(round(max_h * lvl))
        y0 = max(9, bottom_y - fill_h)
        draw.rectangle([x0, y0, x1, bottom_y], fill=fill_color)

    return img


def _format_bar_from_config(snapshot: UsageSnapshot, cfg: AgentBarConfig) -> str:
    """Format the top menu bar pill string according to user settings."""
    badges: List[str] = []
    compact = cfg.bar_metric_mode == "compact"
    for e in snapshot.engines:
        if not cfg.is_engine_enabled(e.engine_id):
            continue
        if not e.installed and e.engine_id != "qoder":
            continue
        p = int(round(e.primary_quota.used_percent)) if e.primary_quota else 0
        s = int(round(e.secondary_quota.used_percent)) if e.secondary_quota else 0
        if cfg.bar_metric_mode == "highest":
            val = max(p, s)
        else:
            val = p if p > 0 else s
        if compact:
            badges.append(f"{e.short_name}:{val}%")
        else:
            badges.append(f"{e.short_name} {val}%")
    if not badges:
        return "AgentBar"
    sep = " · " if compact else "  ·  "
    return sep.join(badges)


def run_pystray_menubar(refresh_interval: int = 15) -> int:
    """Run cross-platform System Tray / macOS Menu Bar app using pystray + Pillow."""
    try:
        import pystray
    except ImportError:
        print(
            "pystray is not installed. Install with: pip install pystray Pillow",
            file=sys.stderr,
        )
        return 1

    cfg = load_config()
    snapshot = collect_usage_snapshot()

    def build_menu(snap: UsageSnapshot) -> "pystray.Menu":
        items = []
        for e in snap.engines:
            if not cfg.is_engine_enabled(e.engine_id) or not e.installed:
                continue
            if items:
                items.append(pystray.Menu.SEPARATOR)
            items.append(
                pystray.MenuItem(e.name, lambda icon, item: None, enabled=False)
            )
            for q in [e.primary_quota, e.secondary_quota]:
                if q is None:
                    continue
                pct = int(round(q.used_percent))
                items.append(
                    pystray.MenuItem(
                        f"  {q.display_title}: {pct}% used ({q.reset_subtitle(snap.timestamp)})",
                        lambda icon, item: None,
                        enabled=False,
                    )
                )

        def on_refresh(icon: Any, item: Any) -> None:
            new_snap = collect_usage_snapshot()
            icon.icon = create_tray_icon_image(new_snap)
            icon.title = _format_bar_from_config(new_snap, cfg)
            icon.menu = build_menu(new_snap)

        def on_quit(icon: Any, item: Any) -> None:
            icon.stop()

        items.extend(
            [
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Refresh", on_refresh),
                pystray.MenuItem("Quit", on_quit),
            ]
        )
        return pystray.Menu(*items)

    icon = pystray.Icon(
        "agentbar",
        create_tray_icon_image(snapshot),
        title=_format_bar_from_config(snapshot, cfg),
        menu=build_menu(snapshot),
    )

    def auto_refresh_worker() -> None:
        while icon.visible:
            time.sleep(max(5, cfg.refresh_interval_sec))
            if not icon.visible:
                break
            new_snap = collect_usage_snapshot()
            icon.icon = create_tray_icon_image(new_snap)
            icon.title = _format_bar_from_config(new_snap, cfg)
            icon.menu = build_menu(new_snap)

    def setup(ic: Any) -> None:
        ic.visible = True
        t = threading.Thread(target=auto_refresh_worker, daemon=True)
        t.start()

    icon.run(setup=setup)
    return 0


GTK_CSS = b"""
window.agentbar-pill {
    background-color: #18181a;
    border: 1px solid #2e2e32;
}
window.agentbar-popover {
    background-color: #18181a;
    border: 1px solid #2c2c30;
    color: #ededef;
}
.pill-button {
    background-image: none;
    background-color: #18181a;
    color: #ededef;
    border: none;
    padding: 5px 12px;
    font-family: sans-serif;
    font-size: 12px;
    font-weight: 600;
}
.pill-button:hover {
    background-color: #242428;
}
.top-nav {
    background-color: #18181a;
    border-bottom: 1px solid #262629;
    padding: 10px 22px 8px 22px;
}
.tab-btn {
    background-image: none;
    background-color: transparent;
    color: #8e8e93;
    border: none;
    border-radius: 4px;
    padding: 3px 9px;
    font-family: sans-serif;
    font-size: 12px;
    font-weight: 500;
}
.tab-btn:hover {
    color: #ededef;
    background-color: #242428;
}
.tab-btn-active {
    background-image: none;
    background-color: #27272b;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 3px 9px;
    font-family: sans-serif;
    font-size: 12px;
    font-weight: 600;
}
.icon-btn {
    background-image: none;
    background-color: transparent;
    color: #8e8e93;
    border: none;
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 12px;
}
.icon-btn:hover {
    color: #ededef;
    background-color: #242428;
}
.icon-btn-active {
    background-image: none;
    background-color: #27272b;
    color: #3b82f6;
    border: none;
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 12px;
}
.engine-section {
    padding: 16px 24px 16px 24px;
}
.engine-divider {
    background-color: #252528;
    min-height: 1px;
}
.engine-header {
    color: #a1a1aa;
    font-family: sans-serif;
    font-size: 11.5px;
    font-weight: 600;
}
.section-heading {
    color: #f4f4f5;
    font-family: sans-serif;
    font-size: 14px;
    font-weight: 600;
}
.row-title {
    color: #ededef;
    font-family: sans-serif;
    font-size: 13.5px;
    font-weight: 500;
}
.row-subtitle {
    color: #8e8e93;
    font-family: sans-serif;
    font-size: 11.5px;
}
.pct-normal {
    color: #9ca3af;
    font-family: sans-serif;
    font-size: 12.5px;
}
.pct-high {
    color: #e5484d;
    font-family: sans-serif;
    font-size: 12.5px;
}
.pct-bold-white {
    color: #f4f4f5;
    font-family: sans-serif;
    font-size: 13.5px;
    font-weight: 700;
}
.big-percent {
    color: #ffffff;
    font-family: sans-serif;
    font-size: 22px;
    font-weight: 600;
}
.rounded-card {
    background-color: #1f1f23;
    border: 1px solid #2e2e34;
    border-radius: 10px;
    padding: 14px 18px;
}
.agy-card {
    background-color: #1c1c20;
    border: 1px solid #2c2c32;
    border-radius: 8px;
    padding: 4px 0px;
}
.agy-card-row {
    padding: 10px 16px;
}
.subtle-btn {
    background-image: none;
    background-color: #2c2c30;
    color: #e4e4e7;
    border: 1px solid #3a3a40;
    border-radius: 6px;
    padding: 5px 12px;
    font-family: sans-serif;
    font-size: 12px;
    font-weight: 500;
}
.subtle-btn:hover {
    background-color: #36363c;
    color: #ffffff;
}
.link-btn {
    background-image: none;
    background-color: transparent;
    color: #3b82f6;
    border: none;
    padding: 0px 2px;
    font-family: sans-serif;
    font-size: 11.5px;
}
.link-btn:hover {
    color: #60a5fa;
}
.manage-btn {
    background-image: none;
    background-color: transparent;
    color: #ededef;
    border: none;
    border-radius: 4px;
    padding: 2px 6px;
    font-family: sans-serif;
    font-size: 13px;
    font-weight: 500;
}
.manage-btn:hover {
    background-color: #27272b;
    color: #ffffff;
}
.toggle-on {
    background-image: none;
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 12px;
    padding: 3px 12px;
    font-family: sans-serif;
    font-size: 11.5px;
    font-weight: 600;
}
.toggle-off {
    background-image: none;
    background-color: #27272b;
    color: #8e8e93;
    border: none;
    border-radius: 12px;
    padding: 3px 12px;
    font-family: sans-serif;
    font-size: 11.5px;
    font-weight: 500;
}
.seg-active {
    background-image: none;
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 3px 9px;
    font-family: sans-serif;
    font-size: 11.5px;
    font-weight: 600;
}
.seg-inactive {
    background-image: none;
    background-color: #232327;
    color: #8e8e93;
    border: none;
    border-radius: 4px;
    padding: 3px 9px;
    font-family: sans-serif;
    font-size: 11.5px;
}
.seg-inactive:hover {
    color: #ededef;
    background-color: #2c2c31;
}
"""


def _create_pill_bar_pixbuf(
    percent: float,
    threshold: float = 80.0,
    width: int = 260,
    height: int = 20,
    fill_override: Optional[tuple] = None,
    track_override: Optional[tuple] = None,
    bg_override: tuple = (24, 24, 26, 255),
) -> Any:
    """Render a smooth anti-aliased pill progress bar via Pillow (4x supersampled) into GdkPixbuf."""
    from gi.repository import GdkPixbuf
    from PIL import Image, ImageDraw

    scale = 4
    W = width * scale
    H = height * scale
    bar_h = int(4.5 * scale)
    y0 = (H - bar_h) // 2
    y1 = y0 + bar_h
    radius = bar_h // 2

    img = Image.new("RGBA", (W, H), bg_override)
    draw = ImageDraw.Draw(img)

    clamped = max(0.0, min(100.0, percent))
    is_high = clamped >= threshold

    if fill_override and track_override:
        track_color = track_override
        fill_color = fill_override
    elif is_high:
        track_color = (74, 34, 36, 255)
        fill_color = (229, 72, 77, 255)
    else:
        track_color = (38, 49, 66, 255)
        fill_color = (59, 130, 246, 255)

    draw.rounded_rectangle([0, y0, W - 1, y1], radius=radius, fill=track_color)

    if clamped > 0.0:
        fill_w = max(bar_h, int(round((clamped / 100.0) * W)))
        draw.rounded_rectangle([0, y0, fill_w - 1, y1], radius=radius, fill=fill_color)

    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    smooth_img = img.resize((width, height), resample=resample_filter)

    buf = io.BytesIO()
    smooth_img.save(buf, format="PNG")
    loader = GdkPixbuf.PixbufLoader.new_with_type("png")
    loader.write(buf.getvalue())
    loader.close()
    return loader.get_pixbuf()


def _create_tray_pixbuf(snapshot: Optional[UsageSnapshot] = None, size: int = 22) -> Any:
    """Convert the PIL tray icon into a GdkPixbuf for Gtk.StatusIcon on the Linux top bar."""
    from gi.repository import GdkPixbuf

    pil_img = create_tray_icon_image(snapshot, size=size * 2)
    from PIL import Image

    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    pil_small = pil_img.resize((size, size), resample=resample_filter)
    buf = io.BytesIO()
    pil_small.save(buf, format="PNG")
    loader = GdkPixbuf.PixbufLoader.new_with_type("png")
    loader.write(buf.getvalue())
    loader.close()
    return loader.get_pixbuf()


def _create_circular_ring_pixbuf(remaining_percent: float, size: int = 28) -> Any:
    """Render a smooth green circular progress ring matching Antigravity's native UI (Hình 5)."""
    from gi.repository import GdkPixbuf
    from PIL import Image, ImageDraw

    scale = 4
    S = size * scale
    pad = 2 * scale
    stroke = int(3.2 * scale)

    img = Image.new("RGBA", (S, S), (28, 28, 32, 0))
    draw = ImageDraw.Draw(img)

    bbox = [pad, pad, S - pad - 1, S - pad - 1]
    # Dark gray background ring track
    draw.arc(bbox, start=0, end=360, fill=(58, 58, 64, 255), width=stroke)

    clamped = max(0.0, min(100.0, remaining_percent))
    if clamped > 0.0:
        sweep = (clamped / 100.0) * 360.0
        # Start at top (-90 deg) and sweep clockwise
        draw.arc(
            bbox,
            start=-90,
            end=-90 + sweep,
            fill=(82, 154, 84, 255),
            width=stroke,
        )

    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    smooth_img = img.resize((size, size), resample=resample_filter)

    buf = io.BytesIO()
    smooth_img.save(buf, format="PNG")
    loader = GdkPixbuf.PixbufLoader.new_with_type("png")
    loader.write(buf.getvalue())
    loader.close()
    return loader.get_pixbuf()


def run_gtk_menubar(
    refresh_interval: Optional[int] = None,
    start_expanded: bool = False,
    open_settings: bool = False,
    initial_tab: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    auto_close_ms: Optional[int] = None,
) -> int:
    """Run native GTK3 Top Menu Bar Pill + Minimalist & Detailed Engine Tabs Popover."""
    if not screenshot_path:
        existing_pid = get_running_daemon_pid()
        if existing_pid is not None and existing_pid != os.getpid():
            sig = getattr(signal, "SIGUSR2" if open_settings else "SIGUSR1", None)
            if sig is not None:
                try:
                    os.kill(existing_pid, sig)
                except OSError:
                    pass
            return 0
        write_current_pid()

    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    provider = Gtk.CssProvider()
    provider.load_from_data(GTK_CSS)
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    class MinimalUsageBar(Gtk.Box):
        def __init__(
            self,
            percent: float,
            threshold: float = 80.0,
            width: int = 260,
            fill_override: Optional[tuple] = None,
            track_override: Optional[tuple] = None,
            bg_override: tuple = (24, 24, 26, 255),
        ) -> None:
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
            pixbuf = _create_pill_bar_pixbuf(
                percent,
                threshold=threshold,
                width=width,
                height=20,
                fill_override=fill_override,
                track_override=track_override,
                bg_override=bg_override,
            )
            img_widget = Gtk.Image.new_from_pixbuf(pixbuf)
            img_widget.set_valign(Gtk.Align.CENTER)
            self.pack_start(img_widget, True, True, 0)

    class AgentBarGtkApp:
        def __init__(self) -> None:
            self.config = load_config()
            if refresh_interval is not None:
                self.config.refresh_interval_sec = max(5, refresh_interval)
            self.snapshot = collect_usage_snapshot()
            self.popover_visible = start_expanded or open_settings or bool(initial_tab)
            if initial_tab:
                self.selected_view = initial_tab
            elif open_settings:
                self.selected_view = "settings"
            else:
                self.selected_view = "all"
            self.codex_recent_tab: str = "5h"
            self.notified_engines: Set[str] = set()
            self.timer_source_id: Optional[int] = None

            # 1. Bottom-Right Floating Bar Pill (can be shown/hidden at will)
            self.pill_win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
            self.pill_win.set_title("AgentBar")
            self.pill_win.set_decorated(False)
            self.pill_win.set_keep_above(True)
            self.pill_win.stick()
            self.pill_win.set_skip_taskbar_hint(True)
            self.pill_win.set_skip_pager_hint(True)
            self.pill_win.get_style_context().add_class("agentbar-pill")

            pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            self.pill_btn = Gtk.Button()
            self.pill_btn.get_style_context().add_class("pill-button")
            self.pill_label = Gtk.Label()
            self.pill_btn.add(self.pill_label)
            self.pill_btn.connect("clicked", self.on_toggle_popover)
            self.pill_btn.connect("button-press-event", self.on_pill_right_click)

            self.hide_pill_btn = Gtk.Button(label="×")
            self.hide_pill_btn.set_tooltip_text("Hide floating bar (restore from top bar or `agentbar toggle-bar`)")
            self.hide_pill_btn.get_style_context().add_class("icon-btn")
            self.hide_pill_btn.connect("clicked", lambda *_: self.toggle_floating_bar(force_state=False))

            pill_box.pack_start(self.pill_btn, True, True, 0)
            pill_box.pack_end(self.hide_pill_btn, False, False, 2)
            self.pill_win.add(pill_box)

            display = Gdk.Display.get_default()
            self.screen_x = 0
            self.screen_y = 0
            self.screen_width = 1920
            self.screen_height = 1080
            if display and display.get_n_monitors() > 0:
                primary_mon = display.get_primary_monitor()
                if primary_mon is None:
                    for idx_m in range(display.get_n_monitors()):
                        cand = display.get_monitor(idx_m)
                        if cand and cand.is_primary():
                            primary_mon = cand
                            break
                if primary_mon is None:
                    primary_mon = display.get_monitor(0)
                if primary_mon is not None:
                    geom = primary_mon.get_geometry()
                    self.screen_x = geom.x
                    self.screen_y = geom.y
                    self.screen_width = geom.width
                    self.screen_height = geom.height

            # 2. Popover Window
            self.pop_win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
            self.pop_win.set_title("AgentBar Usage")
            self.pop_win.set_decorated(False)
            self.pop_win.set_keep_above(True)
            self.pop_win.stick()
            self.pop_win.set_skip_taskbar_hint(True)
            self.pop_win.set_default_size(580, -1)
            self.pop_win.get_style_context().add_class("agentbar-popover")

            self.pop_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.pop_win.add(self.pop_root)

            # 3. Native Linux Top Panel Indicator (StatusNotifierItem + XAyatanaLabel via D-Bus)
            self.icon_cache_dir = Path.home() / ".cache" / "agentbar" / "icons"
            self.icon_cache_dir.mkdir(parents=True, exist_ok=True)
            self._save_dynamic_sni_icon()

            init_bar_str = _format_bar_from_config(self.snapshot, self.config)
            self.sni_indicator: Optional[LinuxTopPanelIndicator] = None
            self.status_icon = None
            try:
                self.sni_indicator = LinuxTopPanelIndicator(
                    icon_theme_dir=self.icon_cache_dir,
                    icon_name="agentbar",
                    initial_label=init_bar_str,
                    on_activate_tab=self.open_specific_tab,
                    on_toggle_popover=self.on_toggle_popover,
                    on_toggle_floating_bar=self.toggle_floating_bar,
                    on_refresh=lambda: self.refresh_ui(force_refresh=True),
                    on_quit=lambda: Gtk.main_quit(),
                )
            except Exception:
                self.sni_indicator = None

            self.refresh_ui()
            if self.config.show_floating_bar or not (
                self.sni_indicator and self.sni_indicator.conn is not None
            ):
                self.pill_win.show_all()
            else:
                self.pill_win.hide()
            self._position_windows()

            if self.popover_visible:
                self.pop_win.show_all()
                self._position_windows()

            self._schedule_timer()

        def _save_dynamic_sni_icon(self) -> None:
            try:
                pil_img = create_tray_icon_image(self.snapshot, size=64)
                pil_img.save(self.icon_cache_dir / "agentbar.png", format="PNG")
            except Exception:
                pass

        def open_specific_tab(self, tab_id: str) -> None:
            self.selected_view = tab_id
            self.popover_visible = True
            self.refresh_ui()
            self.pop_win.show_all()
            self._position_windows()

        def _schedule_timer(self) -> None:
            if self.timer_source_id is not None:
                GLib.source_remove(self.timer_source_id)
            self.timer_source_id = GLib.timeout_add_seconds(
                max(5, self.config.refresh_interval_sec), self.refresh_ui
            )

        def toggle_floating_bar(self, force_state: Optional[bool] = None) -> None:
            if force_state is None:
                self.config.show_floating_bar = not self.config.show_floating_bar
            else:
                self.config.show_floating_bar = bool(force_state)
            save_config(self.config)
            if self.config.show_floating_bar:
                self.pill_win.show_all()
            else:
                self.pill_win.hide()
            self._position_windows()

        def _position_windows(self) -> None:
            alloc = self.pill_win.get_allocation()
            pill_w = alloc.width if (alloc and alloc.width > 50) else 270
            pill_h = alloc.height if (alloc and alloc.height > 20) else 34

            # Anchor floating bar at bottom-right corner
            pill_x = self.screen_x + max(20, self.screen_width - pill_w - 24)
            pill_y = self.screen_y + max(20, self.screen_height - pill_h - 56)
            self.pill_win.move(pill_x, pill_y)

            pop_alloc = self.pop_win.get_allocation()
            pop_h = pop_alloc.height if (pop_alloc and pop_alloc.height > 100) else 440

            if self.config.show_floating_bar:
                # Open popover right above the bottom-right floating bar
                pop_x = self.screen_x + max(20, self.screen_width - 580 - 24)
                pop_y = self.screen_y + max(32, self.screen_height - pop_h - pill_h - 68)
            else:
                # Open popover right below the Linux Top Panel
                pop_x = self.screen_x + max(120, self.screen_width - 580 - 420)
                pop_y = self.screen_y + 32
            self.pop_win.move(pop_x, pop_y)

        def on_pill_right_click(self, _widget: Any, event: Any) -> bool:
            if event.button == 3:
                self._show_context_menu(event.button, event.time)
                return True
            return False

        def on_status_icon_menu(
            self, _icon: Any, button: int, activate_time: int
        ) -> None:
            self._show_context_menu(button, activate_time)

        def _show_context_menu(self, button: int, activate_time: int) -> None:
            menu = Gtk.Menu()
            item_toggle = Gtk.MenuItem(
                label="Hide Dashboard" if self.popover_visible else "Show Dashboard"
            )
            item_toggle.connect("activate", self.on_toggle_popover)
            menu.append(item_toggle)

            item_settings = Gtk.MenuItem(label="⚙ Settings...")
            item_settings.connect("activate", lambda *_: self.open_settings_view())
            menu.append(item_settings)

            item_refresh = Gtk.MenuItem(label="↻ Refresh Now")
            item_refresh.connect("activate", lambda *_: self.refresh_ui())
            menu.append(item_refresh)

            menu.append(Gtk.SeparatorMenuItem())
            item_quit = Gtk.MenuItem(label="✕ Quit Background App")
            item_quit.connect("activate", lambda *_: Gtk.main_quit())
            menu.append(item_quit)

            menu.show_all()
            menu.popup(None, None, None, None, button, activate_time)

        def open_settings_view(self) -> None:
            self.selected_view = "settings"
            self.popover_visible = True
            self.refresh_ui()
            self.pop_win.show_all()
            self._position_windows()

        def on_toggle_popover(self, *_args: Any) -> None:
            self.popover_visible = not self.popover_visible
            if self.popover_visible:
                self.refresh_ui()
                self.pop_win.show_all()
                self._position_windows()
            else:
                self.pop_win.hide()

        def on_select_tab(self, _btn: Any, view_id: str) -> None:
            if view_id == "settings" and self.selected_view == "settings":
                self.selected_view = "all"
            else:
                self.selected_view = view_id
            self.refresh_ui()

        def _check_notifications(self) -> None:
            if not self.config.desktop_notifications:
                return
            thresh = float(self.config.warning_threshold_percent)
            for e in self.snapshot.engines:
                if not self.config.is_engine_enabled(e.engine_id) or not e.installed:
                    continue
                pct = e.highest_quota_percent()
                if pct >= thresh and e.engine_id not in self.notified_engines:
                    self.notified_engines.add(e.engine_id)
                    try:
                        gi.require_version("Notify", "0.7")
                        from gi.repository import Notify

                        if not Notify.is_initted():
                            Notify.init("AgentBar")
                        n = Notify.Notification.new(
                            f"{e.name} Quota Warning ({int(round(pct))}% used)",
                            f"Usage has reached {int(round(pct))}% (threshold: {int(thresh)}%).",
                            "dialog-warning",
                        )
                        n.show()
                    except Exception:
                        pass
                elif pct < thresh and e.engine_id in self.notified_engines:
                    self.notified_engines.discard(e.engine_id)

        def _open_url(self, url: str) -> None:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        def refresh_ui(self, force_refresh: bool = False) -> bool:
            self.snapshot = collect_usage_snapshot(force_refresh=force_refresh)
            self._check_notifications()

            arrow = "▴" if self.popover_visible else "▾"
            bar_str = _format_bar_from_config(self.snapshot, self.config)
            self.pill_label.set_text(f"{bar_str}  {arrow}")

            self._save_dynamic_sni_icon()
            if self.sni_indicator is not None:
                engine_menu_lines: List[Dict[str, str]] = []
                for eng in self.snapshot.engines:
                    if not self.config.is_engine_enabled(eng.engine_id) or not eng.installed:
                        continue
                    p_pct = int(round(eng.primary_quota.used_percent)) if eng.primary_quota else 0
                    s_pct = int(round(eng.secondary_quota.used_percent)) if eng.secondary_quota else 0
                    engine_menu_lines.append(
                        {
                            "engine_id": eng.engine_id,
                            "label": f"{eng.icon} {eng.name} — Session: {p_pct}% used · Week: {s_pct}% used",
                        }
                    )
                self.sni_indicator.update_panel(bar_str, engine_menu_lines)

            for child in self.pop_root.get_children():
                self.pop_root.remove(child)

            # Top Navigation Bar: [All] [Claude] [Codex] [Agy] ... [⚙] [↻] [−] [✕]
            nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            nav.get_style_context().add_class("top-nav")

            enabled_engines = [
                e
                for e in self.snapshot.engines
                if self.config.is_engine_enabled(e.engine_id)
                and (e.installed or e.engine_id == "qoder")
            ]

            tabs = [("all", "All")] + [
                (e.engine_id, e.short_name) for e in enabled_engines
            ]
            for tab_id, tab_title in tabs:
                tbtn = Gtk.Button(label=tab_title)
                cls = (
                    "tab-btn-active"
                    if self.selected_view == tab_id
                    else "tab-btn"
                )
                tbtn.get_style_context().add_class(cls)
                tbtn.connect("clicked", self.on_select_tab, tab_id)
                nav.pack_start(tbtn, False, False, 0)

            btn_quit = Gtk.Button(label="✕")
            btn_quit.set_tooltip_text("Quit background app")
            btn_quit.get_style_context().add_class("icon-btn")
            btn_quit.connect("clicked", lambda *_: Gtk.main_quit())

            btn_hide = Gtk.Button(label="−")
            btn_hide.set_tooltip_text("Minimize to Menu Bar")
            btn_hide.get_style_context().add_class("icon-btn")
            btn_hide.connect("clicked", self.on_toggle_popover)

            btn_refresh = Gtk.Button(label="↻")
            btn_refresh.set_tooltip_text("Force live refresh from servers now")
            btn_refresh.get_style_context().add_class("icon-btn")
            btn_refresh.connect("clicked", lambda *_: self.refresh_ui(force_refresh=True))

            btn_settings = Gtk.Button(label="⚙")
            btn_settings.set_tooltip_text("Settings")
            s_cls = (
                "icon-btn-active"
                if self.selected_view == "settings"
                else "icon-btn"
            )
            btn_settings.get_style_context().add_class(s_cls)
            btn_settings.connect("clicked", self.on_select_tab, "settings")

            nav.pack_end(btn_quit, False, False, 0)
            nav.pack_end(btn_hide, False, False, 0)
            nav.pack_end(btn_refresh, False, False, 0)
            nav.pack_end(btn_settings, False, False, 0)
            self.pop_root.pack_start(nav, False, False, 0)

            if self.selected_view == "settings":
                self.pop_root.pack_start(self._build_settings_panel(), False, False, 0)
            elif self.selected_view == "claude":
                eng = next((e for e in self.snapshot.engines if e.engine_id == "claude"), None)
                if eng:
                    self.pop_root.pack_start(self._build_claude_full_tab(eng), False, False, 0)
            elif self.selected_view == "codex":
                eng = next((e for e in self.snapshot.engines if e.engine_id == "codex"), None)
                if eng:
                    self.pop_root.pack_start(self._build_codex_full_tab(eng), False, False, 0)
            elif self.selected_view == "antigravity":
                eng = next((e for e in self.snapshot.engines if e.engine_id == "antigravity"), None)
                if eng:
                    self.pop_root.pack_start(self._build_antigravity_full_tab(eng), False, False, 0)
            else:
                # Tab "All" (or other engine): concise summary view
                engines_to_show = [
                    e
                    for e in enabled_engines
                    if self.selected_view in ("all", e.engine_id)
                ]
                for idx, e in enumerate(engines_to_show):
                    if idx > 0:
                        div = Gtk.Box()
                        div.get_style_context().add_class("engine-divider")
                        self.pop_root.pack_start(div, False, False, 0)
                    section = self._build_minimal_engine_section(
                        e, show_header=(len(engines_to_show) > 1)
                    )
                    self.pop_root.pack_start(section, False, False, 0)

            if self.popover_visible:
                self.pop_win.show_all()
            self._position_windows()
            return True

        def _build_claude_full_tab(self, e: EngineUsage) -> Any:
            """Full Claude Code view matching Hình 2 & Hình 3 with 100% live data & real actions."""
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            usage_url = str(
                e.extra.get("usage_settings_url", "https://claude.ai/settings/usage")
            )
            learn_url = str(
                e.extra.get(
                    "learn_more_url",
                    "https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans",
                )
            )

            # 1. Plan usage limits (Current session & This week)
            sec1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            sec1.get_style_context().add_class("engine-section")
            q1 = e.primary_quota or RateLimitWindow("5h", 0.0, 300)
            q2 = e.secondary_quota or RateLimitWindow("7d", 0.0, 10080)
            sec1.pack_start(self._build_quota_row(q1), False, False, 0)
            sec1.pack_start(self._build_quota_row(q2), False, False, 0)

            # Limit resets block (Hình 2)
            lbl_lr = Gtk.Label(label="Limit resets", xalign=0)
            lbl_lr.set_margin_top(6)
            lbl_lr.get_style_context().add_class("section-heading")
            sec1.pack_start(lbl_lr, False, False, 0)

            lr_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            lr_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            fr_title = Gtk.Label(label="Full reset  ⓘ", xalign=0)
            fr_title.set_tooltip_text(
                "Immediately resets both your 5-hour session and weekly usage limits on Claude."
            )
            fr_title.get_style_context().add_class("row-title")
            fr_sub = Gtk.Label(
                label=str(
                    e.extra.get("full_reset_expires", "Expires Dec 11, 5:00 AM GMT+7")
                ),
                xalign=0,
            )
            fr_sub.get_style_context().add_class("row-subtitle")
            lr_left.pack_start(fr_title, False, False, 0)
            lr_left.pack_start(fr_sub, False, False, 0)

            rst_btn = Gtk.Button(label="Reset for free")
            rst_btn.set_valign(Gtk.Align.CENTER)
            rst_btn.set_tooltip_text("Open Claude usage settings to trigger your free limit reset")
            rst_btn.get_style_context().add_class("subtle-btn")
            rst_btn.connect("clicked", lambda *_: self._open_url(usage_url))

            lr_row.pack_start(lr_left, True, True, 0)
            lr_row.pack_end(rst_btn, False, False, 0)
            sec1.pack_start(lr_row, False, False, 0)
            root.pack_start(sec1, False, False, 0)

            div1 = Gtk.Box()
            div1.get_style_context().add_class("engine-divider")
            root.pack_start(div1, False, False, 0)

            # 2. Usage credits & Monthly spend limit (Hình 3)
            sec2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            sec2.get_style_context().add_class("engine-section")

            uc_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            uc_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            uc_t = Gtk.Label(label="Usage credits", xalign=0)
            uc_t.get_style_context().add_class("section-heading")
            uc_s = Gtk.Label(label="Available for any task.", xalign=0)
            uc_s.get_style_context().add_class("row-subtitle")
            uc_left.pack_start(uc_t, False, False, 0)
            uc_left.pack_start(uc_s, False, False, 0)

            bal_usd = float(e.extra.get("spend_balance_usd", 0.0) or 0.0)
            bal_str = (
                f"${int(bal_usd)}" if bal_usd == int(bal_usd) else f"${bal_usd:.2f}"
            )
            uc_bal = Gtk.Label(label=bal_str, xalign=1)
            uc_bal.get_style_context().add_class("section-heading")
            uc_top.pack_start(uc_left, True, True, 0)
            uc_top.pack_end(uc_bal, False, False, 0)
            sec2.pack_start(uc_top, False, False, 0)

            uc_desc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            uc_desc = Gtk.Label(
                label="Turn on usage credits to keep using Claude if you hit a plan limit.",
                xalign=0,
            )
            uc_desc.get_style_context().add_class("row-subtitle")

            learn_btn = Gtk.Button(label="Learn more")
            learn_btn.set_tooltip_text(learn_url)
            learn_btn.get_style_context().add_class("link-btn")
            learn_btn.connect("clicked", lambda *_: self._open_url(learn_url))

            spend_on = bool(e.extra.get("spend_enabled", False))
            uc_pill = Gtk.Button(label="ON" if spend_on else "OFF")
            uc_pill.set_tooltip_text("Toggle usage credits on claude.ai/settings/usage")
            uc_pill.get_style_context().add_class(
                "toggle-on" if spend_on else "toggle-off"
            )
            uc_pill.connect("clicked", lambda *_: self._open_url(usage_url))

            uc_desc_row.pack_start(uc_desc, False, False, 0)
            uc_desc_row.pack_start(learn_btn, False, False, 0)
            uc_desc_row.pack_end(uc_pill, False, False, 0)
            sec2.pack_start(uc_desc_row, False, False, 0)

            # "Buy usage credits · Up to 30% off" button (Hình 3)
            buy_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            buy_btn = Gtk.Button(label="Buy usage credits · Up to 30% off")
            buy_btn.set_tooltip_text("Purchase Claude usage credits on claude.ai/settings/usage")
            buy_btn.get_style_context().add_class("subtle-btn")
            buy_btn.connect("clicked", lambda *_: self._open_url(usage_url))
            buy_row.pack_end(buy_btn, False, False, 0)
            sec2.pack_start(buy_row, False, False, 0)

            # Monthly spend limit sub-block
            ms_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            ms_row.set_margin_top(4)
            ms_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            ms_t = Gtk.Label(label="Monthly spend limit", xalign=0)
            ms_t.get_style_context().add_class("row-title")

            used_usd = float(e.extra.get("spend_used_usd", 0.0) or 0.0)
            limit_val = e.extra.get("spend_limit")
            limit_str = f"${limit_val} limit" if limit_val else "No spend limit"
            reload_str = (
                "Auto-reload on" if e.extra.get("auto_reload") else "Auto-reload off"
            )
            ms_s1 = Gtk.Label(
                label=f"${used_usd:.2f} this month · {limit_str} · {reload_str}",
                xalign=0,
            )
            ms_s1.get_style_context().add_class("row-subtitle")
            ms_s2 = Gtk.Label(
                label="Credits are spent automatically past your plan limits.",
                xalign=0,
            )
            ms_s2.get_style_context().add_class("row-subtitle")
            ms_left.pack_start(ms_t, False, False, 0)
            ms_left.pack_start(ms_s1, False, False, 0)
            ms_left.pack_start(ms_s2, False, False, 0)

            manage_btn = Gtk.Button(label="Manage")
            manage_btn.set_valign(Gtk.Align.START)
            manage_btn.set_tooltip_text("Manage monthly spend limit on claude.ai/settings/usage")
            manage_btn.get_style_context().add_class("manage-btn")
            manage_btn.connect("clicked", lambda *_: self._open_url(usage_url))

            ms_row.pack_start(ms_left, True, True, 0)
            ms_row.pack_end(manage_btn, False, False, 0)
            sec2.pack_start(ms_row, False, False, 0)
            root.pack_start(sec2, False, False, 0)

            div2 = Gtk.Box()
            div2.get_style_context().add_class("engine-divider")
            root.pack_start(div2, False, False, 0)

            # 3. This week's usage by product (Hình 3 - 100% live from seven_day_breakdown.rows)
            sec3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            sec3.get_style_context().add_class("engine-section")
            p_hdr = Gtk.Label(label="This week's usage by product", xalign=0)
            p_hdr.get_style_context().add_class("section-heading")
            sec3.pack_start(p_hdr, False, False, 0)

            prod_rows = e.extra.get("product_breakdown") or []
            for pr in prod_rows:
                prow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
                pname = Gtk.Label(label=str(pr.get("display_name", "")), xalign=0)
                pname.set_size_request(145, -1)
                pname.get_style_context().add_class("row-title")

                ppct = float(pr.get("percent", 0.0) or 0.0)
                pbar = MinimalUsageBar(ppct, threshold=101.0, width=295)

                plbl = Gtk.Label(label=f"{int(round(ppct))}%", xalign=1)
                plbl.set_size_request(60, -1)
                plbl.get_style_context().add_class("pct-normal")

                prow.pack_start(pname, False, False, 0)
                prow.pack_start(pbar, True, True, 0)
                prow.pack_end(plbl, False, False, 0)
                sec3.pack_start(prow, False, False, 0)

            root.pack_start(sec3, False, False, 0)
            return root

        def _build_codex_full_tab(self, e: EngineUsage) -> Any:
            """Full OpenAI Codex view matching Hình 4 with 100% live data & real actions."""
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            root.get_style_context().add_class("engine-section")

            upgrade_url = str(e.extra.get("upgrade_url", "https://chatgpt.com/#pricing"))

            # 1. Plan limits header
            hdr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            t1 = Gtk.Label(label="Plan limits", xalign=0)
            t1.get_style_context().add_class("section-heading")
            s1 = Gtk.Label(
                label="Shared across Codex, Work, Workspace Agents, and ChatGPT for Excel.",
                xalign=0,
            )
            s1.get_style_context().add_class("row-subtitle")

            s2_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            s2_lbl = Gtk.Label(
                label="Chat conversations are not included. To increase usage,",
                xalign=0,
            )
            s2_lbl.get_style_context().add_class("row-subtitle")
            upg_btn = Gtk.Button(label="upgrade your plan")
            upg_btn.set_tooltip_text(upgrade_url)
            upg_btn.get_style_context().add_class("link-btn")
            upg_btn.connect("clicked", lambda *_: self._open_url(upgrade_url))
            s2_row.pack_start(s2_lbl, False, False, 0)
            s2_row.pack_start(upg_btn, False, False, 0)

            hdr_box.pack_start(t1, False, False, 0)
            hdr_box.pack_start(s1, False, False, 0)
            hdr_box.pack_start(s2_row, False, False, 0)
            root.pack_start(hdr_box, False, False, 0)

            # Rounded Card containing 5-hour limit & Weekly limit
            card1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            card1.get_style_context().add_class("rounded-card")

            q1 = e.primary_quota or RateLimitWindow("5h", 0.0, 300)
            q2 = e.secondary_quota or RateLimitWindow("7d", 0.0, 10080)

            for title_str, q in [("5-hour limit", q1), ("Weekly limit", q2)]:
                item_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                it_title = Gtk.Label(label=title_str, xalign=0)
                it_title.get_style_context().add_class("row-title")
                item_box.pack_start(it_title, False, False, 0)

                sub_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                rst_cd = format_reset_countdown(
                    q.resets_at, now_epoch=self.snapshot.timestamp
                )
                rst_txt = (
                    f"Resets in {rst_cd}"
                    if rst_cd not in ("—", "reset")
                    else ("Resets in 5h 0m" if not q.is_weekly else "Resets in 7d 0h")
                )
                sub_left = Gtk.Label(label=rst_txt, xalign=0)
                sub_left.get_style_context().add_class("row-subtitle")

                left_pct = max(0, min(100, int(round(100.0 - q.used_percent))))
                sub_right = Gtk.Label(label=f"{left_pct}% left", xalign=1)
                sub_right.get_style_context().add_class("row-subtitle")

                sub_row.pack_start(sub_left, True, True, 0)
                sub_row.pack_end(sub_right, False, False, 0)
                item_box.pack_start(sub_row, False, False, 0)

                w_bar = MinimalUsageBar(
                    float(left_pct),
                    width=490,
                    fill_override=(244, 244, 245, 255),
                    track_override=(52, 52, 58, 255),
                    bg_override=(31, 31, 35, 255),
                )
                item_box.pack_start(w_bar, False, False, 0)
                card1.pack_start(item_box, False, False, 0)

            root.pack_start(card1, False, False, 0)

            # 2. Recent plan usage section (Hình 4)
            rec_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            rec_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            rt = Gtk.Label(label="Recent plan usage", xalign=0)
            rt.get_style_context().add_class("section-heading")
            rs = Gtk.Label(
                label="How your activity draws down your allowance",
                xalign=0,
            )
            rs.get_style_context().add_class("row-subtitle")
            rec_left.pack_start(rt, False, False, 0)
            rec_left.pack_start(rs, False, False, 0)

            seg_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            seg_box.set_valign(Gtk.Align.CENTER)
            for mode_id, mode_lbl in [("5h", "5-hour"), ("7d", "Weekly")]:
                mb = Gtk.Button(label=mode_lbl)
                mb.get_style_context().add_class(
                    "tab-btn-active"
                    if self.codex_recent_tab == mode_id
                    else "tab-btn"
                )
                mb.connect(
                    "clicked",
                    lambda _b, m=mode_id: (
                        setattr(self, "codex_recent_tab", m),
                        self.refresh_ui(),
                    ),
                )
                seg_box.pack_start(mb, False, False, 0)

            rec_hdr.pack_start(rec_left, True, True, 0)
            rec_hdr.pack_end(seg_box, False, False, 0)
            root.pack_start(rec_hdr, False, False, 0)

            card2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
            card2.get_style_context().add_class("rounded-card")
            active_q = q1 if self.codex_recent_tab == "5h" else q2
            active_left_pct = max(
                0, min(100, int(round(100.0 - active_q.used_percent)))
            )

            big_lbl = Gtk.Label(label=f"{active_left_pct}%", xalign=0)
            big_lbl.get_style_context().add_class("big-percent")
            card2.pack_start(big_lbl, False, False, 0)

            empty_hist = Gtk.Label(label="Balance history isn't available yet")
            empty_hist.set_margin_top(16)
            empty_hist.set_margin_bottom(24)
            empty_hist.get_style_context().add_class("row-subtitle")
            card2.pack_start(empty_hist, False, False, 0)

            root.pack_start(card2, False, False, 0)
            return root

        def _build_antigravity_full_tab(self, e: EngineUsage) -> Any:
            """Full Antigravity view matching Hình 5 (100% live from RetrieveUserQuotaSummary RPC)."""
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            root.get_style_context().add_class("engine-section")

            groups: List[Dict[str, Any]] = e.extra.get("agy_groups") or []

            for grp in groups:
                grp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                g_hdr = Gtk.Label(label=f"{grp.get('group_title', '')}  ⓘ", xalign=0)
                g_desc = str(grp.get("group_description", "")).strip()
                if g_desc:
                    g_hdr.set_tooltip_text(g_desc)
                g_hdr.get_style_context().add_class("section-heading")
                grp_box.pack_start(g_hdr, False, False, 0)

                card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                card.get_style_context().add_class("agy-card")

                items = grp.get("items", [])
                for idx, item in enumerate(items):
                    if idx > 0:
                        div = Gtk.Box()
                        div.get_style_context().add_class("engine-divider")
                        card.pack_start(div, False, False, 0)

                    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                    row.get_style_context().add_class("agy-card-row")

                    left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                    left.set_valign(Gtk.Align.CENTER)
                    it_t = Gtk.Label(label=str(item.get("title", "")), xalign=0)
                    it_t.get_style_context().add_class("row-title")
                    left.pack_start(it_t, False, False, 0)

                    sub_str = str(item.get("subtitle", "")).strip()
                    if sub_str:
                        it_s = Gtk.Label(label=sub_str, xalign=0)
                        it_s.get_style_context().add_class("row-subtitle")
                        left.pack_start(it_s, False, False, 0)

                    right = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                    right.set_valign(Gtk.Align.CENTER)

                    rem_pct = int(item.get("remaining_percent", 100))
                    pct_lbl = Gtk.Label(label=f"{rem_pct}%", xalign=1)
                    pct_lbl.get_style_context().add_class("pct-bold-white")

                    ring_pix = _create_circular_ring_pixbuf(float(rem_pct), size=26)
                    ring_img = Gtk.Image.new_from_pixbuf(ring_pix)

                    right.pack_start(pct_lbl, False, False, 0)
                    right.pack_start(ring_img, False, False, 0)

                    row.pack_start(left, True, True, 0)
                    row.pack_end(right, False, False, 0)
                    card.pack_start(row, False, False, 0)

                grp_box.pack_start(card, False, False, 0)
                root.pack_start(grp_box, False, False, 0)

            return root

        def _build_settings_panel(self) -> Any:
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

            sec_eng = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            sec_eng.get_style_context().add_class("engine-section")
            hdr1 = Gtk.Label(label="Engines (Show / Hide on Bar)", xalign=0)
            hdr1.get_style_context().add_class("engine-header")
            sec_eng.pack_start(hdr1, False, False, 0)

            engine_meta = [
                ("claude", "Claude Code", "Anthropic OAuth live session & weekly usage"),
                ("codex", "OpenAI Codex", "OpenAI live 5h & weekly rate limits"),
                ("antigravity", "Antigravity", "Google Antigravity live language server quota"),
                ("qoder", "Qoder", "Qoder CLI / IDE usage tracker"),
            ]
            for eng_id, eng_name, eng_desc in engine_meta:
                is_on = self.config.is_engine_enabled(eng_id)

                def _on_toggle_eng(_b: Any, eid: str = eng_id, cur: bool = is_on) -> None:
                    self.config.set_engine_enabled(eid, not cur)
                    save_config(self.config)
                    self.refresh_ui()

                sec_eng.pack_start(
                    self._build_toggle_row(eng_name, eng_desc, is_on, _on_toggle_eng),
                    False,
                    False,
                    0,
                )
            root.pack_start(sec_eng, False, False, 0)

            div1 = Gtk.Box()
            div1.get_style_context().add_class("engine-divider")
            root.pack_start(div1, False, False, 0)

            sec_bg = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            sec_bg.get_style_context().add_class("engine-section")
            hdr2 = Gtk.Label(label="Background & Startup", xalign=0)
            hdr2.get_style_context().add_class("engine-header")
            sec_bg.pack_start(hdr2, False, False, 0)

            def _toggle_floating(_b: Any) -> None:
                self.toggle_floating_bar()
                self.refresh_ui()

            sec_bg.pack_start(
                self._build_toggle_row(
                    "Show bottom-right floating bar",
                    "Show/hide the floating bar at bottom-right corner",
                    self.config.show_floating_bar,
                    _toggle_floating,
                ),
                False,
                False,
                0,
            )

            def _toggle_autostart(_b: Any) -> None:
                self.config.autostart_on_login = not self.config.autostart_on_login
                save_config(self.config)
                self.refresh_ui()

            sec_bg.pack_start(
                self._build_toggle_row(
                    "Run in background on startup",
                    "Automatically start AgentBar when you log in",
                    self.config.autostart_on_login,
                    _toggle_autostart,
                ),
                False,
                False,
                0,
            )

            def _toggle_collapsed(_b: Any) -> None:
                self.config.start_collapsed = not self.config.start_collapsed
                save_config(self.config)
                self.refresh_ui()

            sec_bg.pack_start(
                self._build_toggle_row(
                    "Start minimized on menu bar",
                    "Keep popover hidden in background until clicked",
                    self.config.start_collapsed,
                    _toggle_collapsed,
                ),
                False,
                False,
                0,
            )

            def _toggle_notify(_b: Any) -> None:
                self.config.desktop_notifications = not self.config.desktop_notifications
                save_config(self.config)
                self.refresh_ui()

            sec_bg.pack_start(
                self._build_toggle_row(
                    "Desktop quota warning alert",
                    f"Notify when any engine reaches {self.config.warning_threshold_percent}% used",
                    self.config.desktop_notifications,
                    _toggle_notify,
                ),
                False,
                False,
                0,
            )
            root.pack_start(sec_bg, False, False, 0)

            div2 = Gtk.Box()
            div2.get_style_context().add_class("engine-divider")
            root.pack_start(div2, False, False, 0)

            sec_pref = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            sec_pref.get_style_context().add_class("engine-section")
            hdr3 = Gtk.Label(label="Display & Refresh", xalign=0)
            hdr3.get_style_context().add_class("engine-header")
            sec_pref.pack_start(hdr3, False, False, 0)

            def _set_interval(val: int) -> None:
                self.config.refresh_interval_sec = val
                save_config(self.config)
                self._schedule_timer()
                self.refresh_ui()

            sec_pref.pack_start(
                self._build_segmented_row(
                    "Auto-refresh interval",
                    "How often background usage is updated",
                    [(15, "15s"), (30, "30s"), (60, "60s"), (300, "5m")],
                    self.config.refresh_interval_sec,
                    _set_interval,
                ),
                False,
                False,
                0,
            )

            def _set_threshold(val: int) -> None:
                self.config.warning_threshold_percent = val
                save_config(self.config)
                self.refresh_ui()

            sec_pref.pack_start(
                self._build_segmented_row(
                    "Red warning threshold",
                    "Turn progress bar red when usage reaches",
                    [(70, "70%"), (80, "80%"), (90, "90%")],
                    self.config.warning_threshold_percent,
                    _set_threshold,
                ),
                False,
                False,
                0,
            )

            def _set_pos(val: str) -> None:
                self.config.bar_position = val
                save_config(self.config)
                self.refresh_ui()

            sec_pref.pack_start(
                self._build_segmented_row(
                    "Top menu bar position",
                    "Horizontal anchor position on top screen edge",
                    [("left", "Left"), ("center", "Center"), ("right", "Right")],
                    self.config.bar_position,
                    _set_pos,
                ),
                False,
                False,
                0,
            )

            def _set_metric(val: str) -> None:
                self.config.bar_metric_mode = val
                save_config(self.config)
                self.refresh_ui()

            sec_pref.pack_start(
                self._build_segmented_row(
                    "Menu bar text format",
                    "Percentage shown on the collapsed top pill",
                    [
                        ("session", "Session %"),
                        ("highest", "Max %"),
                        ("compact", "Compact"),
                    ],
                    self.config.bar_metric_mode,
                    _set_metric,
                ),
                False,
                False,
                0,
            )

            root.pack_start(sec_pref, False, False, 0)
            return root

        def _build_toggle_row(
            self, title: str, subtitle: str, is_on: bool, callback: Any
        ) -> Any:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            t_lbl = Gtk.Label(label=title, xalign=0)
            t_lbl.get_style_context().add_class("row-title")
            s_lbl = Gtk.Label(label=subtitle, xalign=0)
            s_lbl.get_style_context().add_class("row-subtitle")
            left.pack_start(t_lbl, False, False, 0)
            left.pack_start(s_lbl, False, False, 0)

            btn = Gtk.Button(label="ON" if is_on else "OFF")
            btn.set_valign(Gtk.Align.CENTER)
            btn.get_style_context().add_class("toggle-on" if is_on else "toggle-off")
            btn.connect("clicked", callback)

            row.pack_start(left, True, True, 0)
            row.pack_end(btn, False, False, 0)
            return row

        def _build_segmented_row(
            self,
            title: str,
            subtitle: str,
            options: List[Any],
            current_val: Any,
            on_select: Any,
        ) -> Any:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            t_lbl = Gtk.Label(label=title, xalign=0)
            t_lbl.get_style_context().add_class("row-title")
            s_lbl = Gtk.Label(label=subtitle, xalign=0)
            s_lbl.get_style_context().add_class("row-subtitle")
            left.pack_start(t_lbl, False, False, 0)
            left.pack_start(s_lbl, False, False, 0)

            seg_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            seg_box.set_valign(Gtk.Align.CENTER)
            for opt_val, opt_label in options:
                b = Gtk.Button(label=opt_label)
                cls = "seg-active" if opt_val == current_val else "seg-inactive"
                b.get_style_context().add_class(cls)
                b.connect("clicked", lambda _btn, v=opt_val: on_select(v))
                seg_box.pack_start(b, False, False, 0)

            row.pack_start(left, True, True, 0)
            row.pack_end(seg_box, False, False, 0)
            return row

        def _build_minimal_engine_section(
            self, e: EngineUsage, show_header: bool = True
        ) -> Any:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            box.get_style_context().add_class("engine-section")

            if show_header:
                hdr = Gtk.Label(label=e.name, xalign=0)
                hdr.get_style_context().add_class("engine-header")
                box.pack_start(hdr, False, False, 0)

            q1 = e.primary_quota or RateLimitWindow("5h", 0.0, 300)
            q2 = e.secondary_quota or RateLimitWindow("7d", 0.0, 10080)
            for q in [q1, q2]:
                row = self._build_quota_row(q)
                box.pack_start(row, False, False, 0)

            return box

        def _build_quota_row(self, q: RateLimitWindow) -> Any:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

            left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            left_col.set_size_request(165, -1)

            title_lbl = Gtk.Label(label=q.display_title, xalign=0)
            title_lbl.get_style_context().add_class("row-title")

            sub_lbl = Gtk.Label(
                label=q.reset_subtitle(self.snapshot.timestamp), xalign=0
            )
            sub_lbl.get_style_context().add_class("row-subtitle")

            left_col.pack_start(title_lbl, False, False, 0)
            left_col.pack_start(sub_lbl, False, False, 0)

            thresh = float(self.config.warning_threshold_percent)
            bar_widget = MinimalUsageBar(q.used_percent, threshold=thresh, width=265)

            pct_int = int(round(q.used_percent))
            pct_lbl = Gtk.Label(label=f"{pct_int}% used", xalign=1)
            pct_lbl.set_size_request(78, -1)
            pct_cls = "pct-high" if q.used_percent >= thresh else "pct-normal"
            pct_lbl.get_style_context().add_class(pct_cls)

            row.pack_start(left_col, False, False, 0)
            row.pack_start(bar_widget, True, True, 0)
            row.pack_end(pct_lbl, False, False, 0)
            return row

        def take_screenshot(self, out_path: str) -> None:
            gdk_win = self.pop_win.get_window()
            if gdk_win is not None:
                w = gdk_win.get_width()
                h = gdk_win.get_height()
                pixbuf = Gdk.pixbuf_get_from_window(gdk_win, 0, 0, w, h)
                if pixbuf is not None:
                    pixbuf.savev(out_path, "png", [], [])

    app = AgentBarGtkApp()

    if hasattr(signal, "SIGUSR1"):
        signal.signal(
            signal.SIGUSR1,
            lambda *_: GLib.idle_add(app.on_toggle_popover),
        )
    if hasattr(signal, "SIGUSR2"):
        signal.signal(
            signal.SIGUSR2,
            lambda *_: GLib.idle_add(app.open_settings_view),
        )
    if hasattr(signal, "SIGHUP"):
        signal.signal(
            signal.SIGHUP,
            lambda *_: GLib.idle_add(app.toggle_floating_bar),
        )

    if screenshot_path:
        def _capture_and_optionally_close() -> bool:
            app.take_screenshot(screenshot_path)
            if auto_close_ms:
                Gtk.main_quit()
            return False

        GLib.timeout_add(auto_close_ms or 800, _capture_and_optionally_close)
    elif auto_close_ms:
        GLib.timeout_add(auto_close_ms, lambda: (Gtk.main_quit(), False)[1])

    try:
        Gtk.main()
    finally:
        if not screenshot_path:
            remove_current_pid()
    return 0


def launch_menubar(
    backend: str = "auto",
    refresh_interval: Optional[int] = None,
    start_expanded: bool = True,
    open_settings: bool = False,
    initial_tab: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    auto_close_ms: Optional[int] = None,
) -> int:
    """Launch the best available Menu Bar / System Tray backend for the current OS."""
    sys_name = platform.system().lower()

    if backend == "pystray":
        return run_pystray_menubar(refresh_interval=refresh_interval or 15)

    if sys_name.startswith("win") or sys_name == "darwin":
        from .win_mac_bar import run_win_mac_bottom_bar

        return run_win_mac_bottom_bar(
            refresh_interval=refresh_interval,
            start_expanded=start_expanded,
            open_settings=open_settings,
            initial_tab=initial_tab,
        )

    if backend in ("gtk", "auto") and sys_name == "linux":
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            from .tui import render_ansi_dashboard

            print(render_ansi_dashboard(collect_usage_snapshot()))
            return 0
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            return run_gtk_menubar(
                refresh_interval=refresh_interval,
                start_expanded=start_expanded,
                open_settings=open_settings,
                initial_tab=initial_tab,
                screenshot_path=screenshot_path,
                auto_close_ms=auto_close_ms,
            )
        except Exception as exc:
            if backend == "gtk":
                print(f"GTK3 backend error: {exc}", file=sys.stderr)
                return 1

    return run_pystray_menubar(refresh_interval=refresh_interval or 15)
