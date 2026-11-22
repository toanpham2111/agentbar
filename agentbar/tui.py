"""Minimalist Terminal CLI Dashboard and Live TUI for AgentBar.

Matches the clean 'Current session / This week' usage layout.
"""

from __future__ import annotations

import curses
import sys
import time
from typing import Optional

from .detectors import collect_usage_snapshot
from .models import UsageSnapshot, ascii_progress_bar

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLUE = "\033[38;2;59;130;246m"
RED = "\033[38;2;229;72;77m"
GRAY = "\033[38;2;142;142;147m"
TRACK = "\033[38;2;55;60;70m"


def _render_colored_bar(percent: float, width: int = 32, use_color: bool = True) -> str:
    clamped = max(0.0, min(100.0, percent))
    filled = int(round((clamped / 100.0) * width))
    empty = max(0, width - filled)
    if not use_color:
        return "━" * filled + "─" * empty
    bar_color = RED if clamped >= 80.0 else BLUE
    return f"{bar_color}{'━' * filled}{TRACK}{'━' * empty}{RESET}"


def render_ansi_dashboard(
    snapshot: UsageSnapshot,
    show_uninstalled: bool = False,
    use_color: bool = True,
) -> str:
    """Render a minimal, clean 'Current session / This week' terminal view."""
    c_reset = RESET if use_color else ""
    c_bold = BOLD if use_color else ""
    c_gray = GRAY if use_color else ""
    c_red = RED if use_color else ""

    lines = []
    engines = snapshot.engines if show_uninstalled else snapshot.installed_engines

    for idx, e in enumerate(engines):
        if not e.installed:
            continue
        if idx > 0:
            lines.append(f"  {c_gray}{'─' * 68}{c_reset}")

        lines.append(f"  {c_bold}{e.name}{c_reset}")
        lines.append("")

        for q in [e.primary_quota, e.secondary_quota]:
            if q is None:
                continue
            pct_int = int(round(q.used_percent))
            bar = _render_colored_bar(q.used_percent, width=32, use_color=use_color)
            pct_color = c_red if q.used_percent >= 80.0 else c_gray
            pct_str = f"{pct_color}{pct_int:>3}% used{c_reset}"

            lines.append(f"  {q.display_title:<22}  {bar}   {pct_str}")
            lines.append(f"  {c_gray}{q.reset_subtitle(snapshot.timestamp)}{c_reset}")
            lines.append("")

    return "\n".join(lines)


def run_live_watch(interval: float = 3.0) -> None:
    """Run an interactive live-refreshing minimal terminal monitor."""
    if not sys.stdout.isatty():
        snap = collect_usage_snapshot()
        print(render_ansi_dashboard(snap, use_color=False))
        return

    try:
        curses.wrapper(_curses_main, interval)
    except Exception:
        try:
            while True:
                snap = collect_usage_snapshot()
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write(render_ansi_dashboard(snap, use_color=True))
                sys.stdout.flush()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("")


def _curses_main(stdscr: "curses._CursesWindow", interval: float) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_BLUE, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)

    last_fetch = 0.0
    snapshot: Optional[UsageSnapshot] = None

    while True:
        now = time.time()
        if snapshot is None or (now - last_fetch) >= interval:
            snapshot = collect_usage_snapshot()
            last_fetch = now

        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()

        def safe_addstr(y: int, x: int, text: str, attr: int = 0) -> None:
            if 0 <= y < max_y - 1 and 0 <= x < max_x - 1:
                clipped = text[: max(0, max_x - x - 1)]
                try:
                    stdscr.addstr(y, x, clipped, attr)
                except curses.error:
                    pass

        row = 1
        for idx, e in enumerate(snapshot.installed_engines):
            if idx > 0:
                safe_addstr(row, 2, "─" * min(68, max_x - 4), curses.A_DIM)
                row += 1
            safe_addstr(row, 2, e.name, curses.A_BOLD)
            row += 2

            for q in [e.primary_quota, e.secondary_quota]:
                if q is None:
                    continue
                pct_int = int(round(q.used_percent))
                bar = ascii_progress_bar(q.used_percent, 28)
                color = (
                    curses.color_pair(2)
                    if q.used_percent >= 80.0
                    else curses.color_pair(1)
                )
                safe_addstr(row, 2, f"{q.display_title:<20}")
                safe_addstr(row, 24, bar, color)
                safe_addstr(row, 55, f"{pct_int:>3}% used", color if q.used_percent >= 80 else curses.A_DIM)
                row += 1
                safe_addstr(row, 2, q.reset_subtitle(snapshot.timestamp), curses.A_DIM)
                row += 2

        safe_addstr(row, 2, "[r] Refresh   [q] Quit", curses.A_DIM)
        stdscr.refresh()

        for _ in range(10):
            ch = stdscr.getch()
            if ch in (ord("q"), ord("Q"), 27):
                return
            if ch in (ord("r"), ord("R")):
                snapshot = collect_usage_snapshot()
                last_fetch = time.time()
                break
            time.sleep(0.1)
