"""Windows & macOS Bottom-Right Floating Bar + Tabbed Popover + System Tray Controller.

On Windows and macOS (MacBook):
- Displays a sleek dark floating bar anchored at the bottom-right corner of the screen.
- Clicking the floating bar toggles the full Tabbed Popover (All | Claude | Codex | Agy | ⚙) right above it.
- Clicking the '[−]' button on the bar (or 'Show / Hide Bottom-Right Bar' in the System Tray / Menu Bar,
  or running `agentbar toggle-bar`) hides or shows the bottom-right floating bar at any time.
"""

from __future__ import annotations

import threading
import time
import webbrowser
from typing import Any, Optional

from .config import AgentBarConfig, load_config, save_config
from .detectors import collect_usage_snapshot
from .models import EngineUsage, RateLimitWindow, UsageSnapshot, format_reset_countdown


def run_win_mac_bottom_bar(
    refresh_interval: Optional[int] = None,
    start_expanded: bool = False,
    open_settings: bool = False,
    initial_tab: Optional[str] = None,
) -> int:
    """Run the Bottom-Right Floating Bar + Popover + System Tray on Windows & macOS."""
    try:
        import tkinter as tk
    except ImportError:
        # Fallback to pystray-only if tkinter is unavailable
        from .menubar import run_pystray_menubar

        return run_pystray_menubar(refresh_interval=refresh_interval or 15)

    from .menubar import _format_bar_from_config, create_tray_icon_image

    class WinMacBottomBarApp:
        def __init__(self) -> None:
            self.config: AgentBarConfig = load_config()
            if refresh_interval is not None:
                self.config.refresh_interval_sec = max(5, refresh_interval)
            self.snapshot: UsageSnapshot = collect_usage_snapshot()

            # On Windows & macOS, default to showing the bottom-right floating bar
            self.bar_visible: bool = True
            self.popover_visible: bool = start_expanded or open_settings or bool(initial_tab)
            self.selected_view: str = (
                initial_tab
                if initial_tab
                else ("settings" if open_settings else "all")
            )
            self.codex_recent_tab: str = "5h"

            self.root = tk.Tk()
            self.root.title("Kio Usage Monitoring")
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.configure(bg="#18181a")

            self.screen_w = self.root.winfo_screenwidth()
            self.screen_h = self.root.winfo_screenheight()

            # 1. Bottom-Right Floating Bar Pill Frame
            self.pill_frame = tk.Frame(
                self.root,
                bg="#18181a",
                highlightbackground="#2e2e32",
                highlightthickness=1,
            )
            self.pill_frame.pack(fill="both", expand=True)

            self.pill_btn = tk.Button(
                self.pill_frame,
                text="",
                bg="#18181a",
                fg="#ededef",
                activebackground="#242428",
                activeforeground="#ffffff",
                bd=0,
                padx=12,
                pady=5,
                font=("Sans", 10, "bold"),
                command=self.toggle_popover,
                cursor="hand2",
            )
            self.pill_btn.pack(side="left")

            self.hide_bar_btn = tk.Button(
                self.pill_frame,
                text="×",
                bg="#18181a",
                fg="#8e8e93",
                activebackground="#242428",
                activeforeground="#ffffff",
                bd=0,
                padx=6,
                pady=5,
                font=("Sans", 10),
                command=self.hide_floating_bar,
                cursor="hand2",
            )
            self.hide_bar_btn.pack(side="right")

            # Allow dragging the bottom-right floating bar
            self._drag_x = 0
            self._drag_y = 0
            self.pill_btn.bind("<ButtonPress-3>", self._start_drag)
            self.pill_btn.bind("<B3-Motion>", self._on_drag)

            # 2. Expandable Popover Toplevel right above the Bottom-Right Bar
            self.pop_win = tk.Toplevel(self.root)
            self.pop_win.title("Kio Usage Monitoring")
            self.pop_win.overrideredirect(True)
            self.pop_win.attributes("-topmost", True)
            self.pop_win.configure(
                bg="#18181a",
                highlightbackground="#2c2c30",
                highlightthickness=1,
            )
            self.pop_container = tk.Frame(self.pop_win, bg="#18181a")
            self.pop_container.pack(fill="both", expand=True)

            if not self.popover_visible:
                self.pop_win.withdraw()

            self._start_system_tray_thread()
            self.refresh_ui()
            self._schedule_refresh()

        def _start_drag(self, event: Any) -> None:
            self._drag_x = event.x
            self._drag_y = event.y

        def _on_drag(self, event: Any) -> None:
            x = self.root.winfo_x() + (event.x - self._drag_x)
            y = self.root.winfo_y() + (event.y - self._drag_y)
            self.root.geometry(f"+{x}+{y}")

        def _position_windows(self) -> None:
            self.root.update_idletasks()
            pill_w = max(240, self.root.winfo_reqwidth())
            pill_h = max(32, self.root.winfo_reqheight())
            pill_x = max(20, self.screen_w - pill_w - 24)
            pill_y = max(20, self.screen_h - pill_h - 58)
            self.root.geometry(f"{pill_w}x{pill_h}+{pill_x}+{pill_y}")

            if self.popover_visible:
                self.pop_win.update_idletasks()
                pop_w = 540
                pop_h = max(260, self.pop_win.winfo_reqheight())
                pop_x = max(20, self.screen_w - pop_w - 24)
                pop_y = max(20, pill_y - pop_h - 10)
                self.pop_win.geometry(f"{pop_w}x{pop_h}+{pop_x}+{pop_y}")

        def show_floating_bar(self) -> None:
            self.bar_visible = True
            self.config.show_floating_bar = True
            save_config(self.config)
            self.root.deiconify()
            self._position_windows()

        def hide_floating_bar(self) -> None:
            self.bar_visible = False
            self.config.show_floating_bar = False
            save_config(self.config)
            self.popover_visible = False
            self.pop_win.withdraw()
            self.root.withdraw()

        def toggle_floating_bar(self) -> None:
            if self.bar_visible:
                self.hide_floating_bar()
            else:
                self.show_floating_bar()

        def toggle_popover(self) -> None:
            if not self.bar_visible:
                self.show_floating_bar()
            self.popover_visible = not self.popover_visible
            if self.popover_visible:
                self.refresh_ui()
                self.pop_win.deiconify()
                self._position_windows()
            else:
                self.pop_win.withdraw()

        def select_tab(self, tab_id: str) -> None:
            self.selected_view = tab_id
            self.popover_visible = True
            if not self.bar_visible:
                self.show_floating_bar()
            self.refresh_ui()
            self.pop_win.deiconify()
            self._position_windows()

        def _schedule_refresh(self) -> None:
            interval_ms = max(5, self.config.refresh_interval_sec) * 1000
            self.root.after(interval_ms, self._periodic_tick)

        def _periodic_tick(self) -> None:
            self.refresh_ui()
            self._schedule_refresh()

        def refresh_ui(self, force_refresh: bool = False) -> None:
            self.snapshot = collect_usage_snapshot(force_refresh=force_refresh)
            arrow = "▾" if self.popover_visible else "▴"
            bar_str = _format_bar_from_config(self.snapshot, self.config)
            self.pill_btn.configure(text=f"{bar_str}   {arrow}")

            for widget in self.pop_container.winfo_children():
                widget.destroy()

            # Top Navigation Bar
            nav = tk.Frame(self.pop_container, bg="#18181a", padx=16, pady=10)
            nav.pack(fill="x")

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
                is_act = self.selected_view == tab_id
                btn = tk.Button(
                    nav,
                    text=tab_title,
                    bg="#27272b" if is_act else "#18181a",
                    fg="#ffffff" if is_act else "#8e8e93",
                    bd=0,
                    padx=8,
                    pady=3,
                    font=("Sans", 9, "bold" if is_act else "normal"),
                    command=lambda t=tab_id: self.select_tab(t),
                    cursor="hand2",
                )
                btn.pack(side="left", padx=2)

            for lbl, cmd in [
                ("✕", self.root.quit),
                ("−", self.toggle_popover),
                ("↻", lambda: self.refresh_ui(force_refresh=True)),
                ("⚙", lambda: self.select_tab("settings")),
            ]:
                ib = tk.Button(
                    nav,
                    text=lbl,
                    bg="#18181a",
                    fg="#8e8e93",
                    bd=0,
                    padx=6,
                    pady=2,
                    command=cmd,
                    cursor="hand2",
                )
                ib.pack(side="right", padx=2)

            tk.Frame(self.pop_container, bg="#262629", height=1).pack(fill="x")

            body = tk.Frame(self.pop_container, bg="#18181a", padx=20, pady=14)
            body.pack(fill="both", expand=True)

            if self.selected_view == "settings":
                self._render_tk_settings(body)
            else:
                engines_to_show = [
                    e
                    for e in enabled_engines
                    if self.selected_view in ("all", e.engine_id)
                ]
                for idx, e in enumerate(engines_to_show):
                    if idx > 0:
                        tk.Frame(body, bg="#252528", height=1).pack(fill="x", pady=10)
                    self._render_tk_engine_summary(body, e)

            self._position_windows()

        def _render_tk_engine_summary(self, parent: Any, e: EngineUsage) -> None:
            tk.Label(
                parent,
                text=e.name,
                bg="#18181a",
                fg="#a1a1aa",
                font=("Sans", 9, "bold"),
                anchor="w",
            ).pack(fill="x", pady=(0, 8))

            quotas = [q for q in [e.primary_quota, e.secondary_quota, getattr(e, "tertiary_quota", None)] if q is not None]
            if not quotas:
                quotas = [RateLimitWindow("5h", 0.0, 300)]
            thresh = float(self.config.warning_threshold_percent)

            for q in quotas:
                row = tk.Frame(parent, bg="#18181a")
                row.pack(fill="x", pady=6)

                left = tk.Frame(row, bg="#18181a", width=165)
                left.pack(side="left", fill="y")
                tk.Label(
                    left,
                    text=q.display_title,
                    bg="#18181a",
                    fg="#ededef",
                    font=("Sans", 10, "bold"),
                    anchor="w",
                ).pack(fill="x")
                tk.Label(
                    left,
                    text=q.reset_subtitle(self.snapshot.timestamp),
                    bg="#18181a",
                    fg="#8e8e93",
                    font=("Sans", 9),
                    anchor="w",
                ).pack(fill="x")

                is_high = q.used_percent >= thresh
                canvas = tk.Canvas(
                    row,
                    width=250,
                    height=14,
                    bg="#18181a",
                    highlightthickness=0,
                )
                canvas.pack(side="left", padx=12)
                track_c = "#4a2224" if is_high else "#263142"
                fill_c = "#e5484d" if is_high else "#3b82f6"
                canvas.create_rectangle(0, 5, 250, 10, fill=track_c, outline="")
                if q.used_percent > 0:
                    fw = max(5, int((min(100.0, q.used_percent) / 100.0) * 250))
                    canvas.create_rectangle(0, 5, fw, 10, fill=fill_c, outline="")

                pct_int = int(round(q.used_percent))
                tk.Label(
                    row,
                    text=f"{pct_int}% used",
                    bg="#18181a",
                    fg=fill_c if is_high else "#9ca3af",
                    font=("Sans", 9),
                    anchor="e",
                    width=10,
                ).pack(side="right")

        def _render_tk_settings(self, parent: Any) -> None:
            tk.Label(
                parent,
                text="Bottom-Right Floating Bar & Settings",
                bg="#18181a",
                fg="#a1a1aa",
                font=("Sans", 9, "bold"),
                anchor="w",
            ).pack(fill="x", pady=(0, 8))

            row_hide = tk.Frame(parent, bg="#18181a")
            row_hide.pack(fill="x", pady=5)
            tk.Label(
                row_hide,
                text="Bottom-Right Floating Bar Visibility",
                bg="#18181a",
                fg="#ededef",
                font=("Sans", 10),
                anchor="w",
            ).pack(side="left")
            tk.Button(
                row_hide,
                text="Hide Bar to Tray",
                bg="#27272b",
                fg="#ededef",
                bd=0,
                padx=10,
                pady=3,
                command=self.hide_floating_bar,
                cursor="hand2",
            ).pack(side="right")

            for eng_id, eng_name in [
                ("claude", "Claude Code"),
                ("codex", "OpenAI Codex"),
                ("antigravity", "Antigravity"),
                ("qoder", "Qoder"),
                ("system", "System Resources"),
            ]:
                is_on = self.config.is_engine_enabled(eng_id)
                r = tk.Frame(parent, bg="#18181a")
                r.pack(fill="x", pady=4)
                tk.Label(
                    r,
                    text=eng_name,
                    bg="#18181a",
                    fg="#ededef",
                    font=("Sans", 10),
                ).pack(side="left")
                tk.Button(
                    r,
                    text="ON" if is_on else "OFF",
                    bg="#3b82f6" if is_on else "#27272b",
                    fg="#ffffff" if is_on else "#8e8e93",
                    bd=0,
                    padx=10,
                    pady=2,
                    command=lambda eid=eng_id, cur=is_on: (
                        self.config.set_engine_enabled(eid, not cur),
                        save_config(self.config),
                        self.refresh_ui(),
                    ),
                    cursor="hand2",
                ).pack(side="right")

        def _start_system_tray_thread(self) -> None:
            """Run pystray in a background thread so user can always Hide/Show the bottom-right bar."""
            try:
                import pystray
            except ImportError:
                return

            def _tray_worker() -> None:
                menu = pystray.Menu(
                    pystray.MenuItem(
                        "👁 Show / Hide Bottom-Right Bar",
                        lambda icon, item: self.root.after(0, self.toggle_floating_bar),
                        default=True,
                    ),
                    pystray.MenuItem(
                        "📊 Open / Hide Usage Dashboard",
                        lambda icon, item: self.root.after(0, self.toggle_popover),
                    ),
                    pystray.MenuItem(
                        "⚙ Settings...",
                        lambda icon, item: self.root.after(
                            0, lambda: self.select_tab("settings")
                        ),
                    ),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem(
                        "↻ Refresh Now",
                        lambda icon, item: self.root.after(
                            0, lambda: self.refresh_ui(force_refresh=True)
                        ),
                    ),
                    pystray.MenuItem(
                        "✕ Quit Kio Usage Monitoring",
                        lambda icon, item: (
                            icon.stop(),
                            self.root.after(0, self.root.quit),
                        ),
                    ),
                )
                tray_icon = pystray.Icon(
                    "agentbar",
                    create_tray_icon_image(self.snapshot),
                    title="Kio Usage Monitoring — Click to Show/Hide",
                    menu=menu,
                )
                tray_icon.run()

            t = threading.Thread(target=_tray_worker, daemon=True)
            t.start()

        def run(self) -> int:
            self.root.mainloop()
            return 0

    app = WinMacBottomBarApp()
    return app.run()
