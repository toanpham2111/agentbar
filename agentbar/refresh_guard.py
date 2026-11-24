"""Rate guards for background UI and data refresh callbacks."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Optional


@dataclass(frozen=True)
class RefreshDecision:
    """Describe which parts of a refresh request may run."""

    render: bool
    fetch: bool


class UiRefreshThrottle:
    """Protect the UI loop from repeated tray and D-Bus refresh callbacks."""

    def __init__(
        self,
        render_interval_sec: float = 0.25,
        fetch_interval_sec: float = 5.0,
    ) -> None:
        if not isfinite(render_interval_sec) or render_interval_sec <= 0:
            raise ValueError("render_interval_sec must be a positive finite number")
        if not isfinite(fetch_interval_sec) or fetch_interval_sec <= 0:
            raise ValueError("fetch_interval_sec must be a positive finite number")
        self.render_interval_sec = render_interval_sec
        self.fetch_interval_sec = fetch_interval_sec
        self._last_render_at: Optional[float] = None
        self._last_fetch_at: Optional[float] = None

    def decide(self, now: float, refresh_in_progress: bool) -> RefreshDecision:
        if not isfinite(now) or now < 0:
            raise ValueError("now must be a non-negative finite timestamp")

        render = (
            self._last_render_at is None
            or now - self._last_render_at >= self.render_interval_sec
        )
        if render:
            self._last_render_at = now

        fetch = not refresh_in_progress and (
            self._last_fetch_at is None
            or now - self._last_fetch_at >= self.fetch_interval_sec
        )
        if fetch:
            self._last_fetch_at = now

        return RefreshDecision(render=render, fetch=fetch)
