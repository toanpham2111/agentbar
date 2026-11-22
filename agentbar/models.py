"""Data models and formatting utilities for AgentBar."""

from __future__ import annotations

import datetime
import platform
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def format_tokens(count: int) -> str:
    """Format token count into compact human-readable string (e.g. 37.4K, 1.2M)."""
    if count < 0:
        count = 0
    if count < 1_000:
        return str(count)
    if count < 1_000_000:
        val = count / 1_000.0
        return f"{val:.1f}K" if val < 100 else f"{int(round(val))}K"
    if count < 1_000_000_000:
        val = count / 1_000_000.0
        return f"{val:.2f}M" if val < 10 else f"{val:.1f}M"
    val = count / 1_000_000_000.0
    return f"{val:.2f}B"


def format_cost(usd: float) -> str:
    """Format estimated USD cost."""
    if usd <= 0:
        return "$0.00"
    if usd < 0.01:
        return "<$0.01"
    if usd < 10:
        return f"${usd:.2f}"
    return f"${usd:.1f}"


def format_reset_countdown(
    resets_at_epoch: Optional[int], now_epoch: Optional[float] = None
) -> str:
    """Format seconds remaining until rate limit window resets."""
    if not resets_at_epoch:
        return "—"
    now = now_epoch if now_epoch is not None else time.time()
    diff = int(resets_at_epoch - now)
    if diff <= 0:
        return "reset"
    days = diff // 86400
    hours = (diff % 86400) // 3600
    minutes = (diff % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_reset_clock_time(
    resets_at_epoch: Optional[int],
    is_weekly: bool = False,
    now_epoch: Optional[float] = None,
) -> str:
    """Format reset timestamp like 'Resets at 11:50 PM' or 'Resets Saturday 3:00 PM'."""
    now = now_epoch if now_epoch is not None else time.time()
    if not resets_at_epoch or resets_at_epoch <= now:
        # Roll forward to the next window boundary so user always sees a clean reset time
        window_sec = 7 * 86400 if is_weekly else 5 * 3600
        if resets_at_epoch and resets_at_epoch > 0:
            steps = int((now - resets_at_epoch) // window_sec) + 1
            target_ts = resets_at_epoch + steps * window_sec
        else:
            target_ts = int(now + window_sec)
    else:
        target_ts = int(resets_at_epoch)

    dt = datetime.datetime.fromtimestamp(target_ts)
    hour_12 = dt.strftime("%I").lstrip("0") or "12"
    minute_str = dt.strftime("%M")
    ampm = dt.strftime("%p")
    time_part = f"{hour_12}:{minute_str} {ampm}"

    if is_weekly:
        weekday = dt.strftime("%A")
        return f"Resets {weekday} {time_part}"
    return f"Resets at {time_part}"


def format_relative_time(
    epoch_sec: Optional[float], now_epoch: Optional[float] = None
) -> str:
    """Format a past timestamp as relative time (e.g. '4m ago', '2h ago')."""
    if not epoch_sec or epoch_sec <= 0:
        return "never"
    now = now_epoch if now_epoch is not None else time.time()
    diff = int(now - epoch_sec)
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    days = diff // 86400
    if days < 30:
        return f"{days}d ago"
    return f"{days // 30}mo ago"


def ascii_progress_bar(percent: float, width: int = 24) -> str:
    """Render a sleek thin Unicode line progress bar."""
    clamped = max(0.0, min(100.0, percent))
    filled = int(round((clamped / 100.0) * width))
    empty = max(0, width - filled)
    return "━" * filled + "─" * empty


@dataclass
class RateLimitWindow:
    """Represents a rate-limit or quota usage window (Current session or This week)."""

    label: str  # e.g. "5h", "7d"
    used_percent: float  # 0.0 to 100.0
    window_minutes: int = 300
    resets_at: Optional[int] = None
    is_estimated: bool = False

    @property
    def is_weekly(self) -> bool:
        return self.window_minutes >= 1440 or self.label in ("7d", "week", "weekly")

    @property
    def display_title(self) -> str:
        return "This week" if self.is_weekly else "Current session"

    def reset_in(self, now_epoch: Optional[float] = None) -> str:
        return format_reset_countdown(self.resets_at, now_epoch=now_epoch)

    def reset_subtitle(self, now_epoch: Optional[float] = None) -> str:
        return format_reset_clock_time(
            self.resets_at, is_weekly=self.is_weekly, now_epoch=now_epoch
        )


@dataclass
class TokenBreakdown:
    """Detailed breakdown of input, output, cached, and reasoning tokens."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cached_tokens
            + self.reasoning_tokens
        )


@dataclass
class EngineUsage:
    """Normalized usage & installation telemetry for a single AI coding engine."""

    engine_id: str
    name: str
    short_name: str
    icon: str
    installed: bool = False
    binary_path: Optional[str] = None
    data_dir: Optional[str] = None
    model_or_plan: str = "—"
    status: str = "not_found"
    tokens_5h: int = 0
    tokens_today: int = 0
    tokens_7d: int = 0
    tokens_total: int = 0
    breakdown: TokenBreakdown = field(default_factory=TokenBreakdown)
    primary_quota: Optional[RateLimitWindow] = None
    secondary_quota: Optional[RateLimitWindow] = None
    estimated_cost_usd: float = 0.0
    sessions_total: int = 0
    sessions_today: int = 0
    last_active_ts: Optional[float] = None
    metric_label: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def last_active_str(self, now_epoch: Optional[float] = None) -> str:
        return format_relative_time(self.last_active_ts, now_epoch=now_epoch)

    def highest_quota_percent(self) -> float:
        vals = []
        if self.primary_quota is not None:
            vals.append(self.primary_quota.used_percent)
        if self.secondary_quota is not None:
            vals.append(self.secondary_quota.used_percent)
        return max(vals) if vals else 0.0

    def menu_bar_badge(self, compact: bool = False) -> str:
        """Clean minimal badge for the top menu bar: e.g. 'Claude 48% · Codex 84%'."""
        if not self.installed:
            return ""
        p = int(round(self.primary_quota.used_percent)) if self.primary_quota else 0
        s = int(round(self.secondary_quota.used_percent)) if self.secondary_quota else 0
        shown = p if p > 0 else s
        if compact:
            return f"{self.short_name}:{shown}%"
        return f"{self.short_name} {shown}%"


@dataclass
class UsageSnapshot:
    """Complete snapshot of all detected AI coding engines on the system."""

    engines: List[EngineUsage]
    timestamp: float = field(default_factory=time.time)
    os_name: str = field(
        default_factory=lambda: f"{platform.system()} {platform.release()}"
    )

    @property
    def installed_engines(self) -> List[EngineUsage]:
        return [e for e in self.engines if e.installed]

    @property
    def total_tokens_all_engines(self) -> int:
        return sum(e.tokens_total for e in self.installed_engines)

    @property
    def total_tokens_today(self) -> int:
        return sum(e.tokens_today for e in self.installed_engines)

    @property
    def total_cost_usd(self) -> float:
        return sum(e.estimated_cost_usd for e in self.installed_engines)

    def to_bar_string(self, compact: bool = False, separator: str = "  ·  ") -> str:
        """Single-line string for Menu Bar / Waybar / tmux / Top Bar Pill."""
        badges = [
            e.menu_bar_badge(compact=compact)
            for e in self.installed_engines
            if e.menu_bar_badge(compact=compact)
        ]
        if not badges:
            return "AgentBar"
        return separator.join(badges)

    def to_tmux_string(self) -> str:
        """Formatted string with tmux color codes for status-right."""
        parts = []
        for e in self.installed_engines:
            pct = e.highest_quota_percent()
            if pct >= 80:
                color = "#[fg=red,bold]"
            elif pct >= 50:
                color = "#[fg=yellow]"
            else:
                color = "#[fg=cyan]"
            badge = e.menu_bar_badge(compact=True)
            parts.append(f"{color}{badge}#[default]")
        return " · ".join(parts) if parts else "AgentBar"

    def to_waybar_dict(self) -> Dict[str, Any]:
        """JSON payload compatible with Linux Waybar / Polybar custom modules."""
        text = self.to_bar_string(compact=False)
        lines = []
        max_pct = 0.0
        for e in self.installed_engines:
            max_pct = max(max_pct, e.highest_quota_percent())
            p_pct = int(round(e.primary_quota.used_percent)) if e.primary_quota else 0
            s_pct = int(round(e.secondary_quota.used_percent)) if e.secondary_quota else 0
            p_rst = e.primary_quota.reset_subtitle(self.timestamp) if e.primary_quota else ""
            s_rst = e.secondary_quota.reset_subtitle(self.timestamp) if e.secondary_quota else ""
            lines.append(
                f"{e.name}\n"
                f"  Current session: {p_pct}% used ({p_rst})\n"
                f"  This week:       {s_pct}% used ({s_rst})"
            )

        css_class = "normal"
        if max_pct >= 80:
            css_class = "critical"
        elif max_pct >= 50:
            css_class = "warning"

        return {
            "text": text,
            "tooltip": "\n\n".join(lines),
            "class": css_class,
            "percentage": int(round(max_pct)),
        }

    def to_swiftbar_string(self) -> str:
        """Native macOS SwiftBar / xbar plugin output format."""
        out = [f"{self.to_bar_string(compact=True)} | font=SFProText size=12"]
        out.append("---")
        for e in self.installed_engines:
            out.append(f"{e.name} | bold=true")
            for q in [e.primary_quota, e.secondary_quota]:
                if q is None:
                    continue
                pct = int(round(q.used_percent))
                bar = ascii_progress_bar(pct, 16)
                color = "#e5484d" if pct >= 80 else "#e5e5e5"
                out.append(f"{q.display_title}: {bar}  {pct}% used | color={color}")
                out.append(f"{q.reset_subtitle(self.timestamp)} | size=11 color=#8e8e93")
            out.append("---")
        out.append("Refresh | refresh=true")
        return "\n".join(out)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "os_name": self.os_name,
            "bar_text": self.to_bar_string(),
            "total_tokens": self.total_tokens_all_engines,
            "total_tokens_today": self.total_tokens_today,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "engines": [asdict(e) for e in self.engines],
        }
