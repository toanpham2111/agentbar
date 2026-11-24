"""Regression tests for background refresh and tray signal storms."""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path
from typing import Any

from agentbar.file_cache import copy_file_if_changed
from agentbar.refresh_guard import PopoverRenderCache, UiRefreshThrottle
from agentbar.sni_indicator import LinuxTopPanelIndicator


class _FakeGLib:
    @staticmethod
    def Variant(signature: str, value: Any) -> tuple[str, Any]:
        return signature, value


class _FakeConnection:
    def __init__(self) -> None:
        self.signals: list[tuple[Any, ...]] = []

    def emit_signal(self, *args: Any) -> None:
        self.signals.append(args)


def _make_indicator() -> LinuxTopPanelIndicator:
    indicator = LinuxTopPanelIndicator.__new__(LinuxTopPanelIndicator)
    indicator.GLib = _FakeGLib()
    indicator.conn = _FakeConnection()
    indicator.label = "--"
    indicator.indicator_id = "agentbar-codex"
    indicator.revision = 1
    indicator.menu_items = []
    indicator._last_panel_fingerprint = None
    indicator.on_toggle_popover = lambda: None
    indicator.on_toggle_floating_bar = lambda: None
    indicator.on_refresh = lambda: None
    indicator.on_quit = lambda: None
    indicator.on_activate_tab = lambda _tab: None
    return indicator


class TestUiRefreshThrottle(unittest.TestCase):
    def test_first_refresh_runs_then_burst_is_throttled(self) -> None:
        throttle = UiRefreshThrottle(render_interval_sec=0.25, fetch_interval_sec=5.0)

        first = throttle.decide(now=10.0, refresh_in_progress=False)
        burst = throttle.decide(now=10.1, refresh_in_progress=False)
        render_only = throttle.decide(now=10.3, refresh_in_progress=False)

        self.assertEqual((first.render, first.fetch), (True, True))
        self.assertEqual((burst.render, burst.fetch), (False, False))
        self.assertEqual((render_only.render, render_only.fetch), (True, False))

    def test_in_progress_refresh_blocks_duplicate_fetch(self) -> None:
        throttle = UiRefreshThrottle(render_interval_sec=0.25, fetch_interval_sec=5.0)
        throttle.decide(now=20.0, refresh_in_progress=False)

        blocked = throttle.decide(now=25.1, refresh_in_progress=True)
        resumed = throttle.decide(now=25.2, refresh_in_progress=False)

        self.assertFalse(blocked.fetch)
        self.assertTrue(resumed.fetch)

    def test_invalid_intervals_and_timestamps_are_rejected(self) -> None:
        for value in (0.0, -1.0, math.inf, math.nan):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    UiRefreshThrottle(render_interval_sec=value)

        throttle = UiRefreshThrottle()
        for value in (-1.0, math.inf, math.nan):
            with self.subTest(timestamp=value):
                with self.assertRaises(ValueError):
                    throttle.decide(now=value, refresh_in_progress=False)


class TestPopoverRenderCache(unittest.TestCase):
    def test_hidden_popover_never_rebuilds(self) -> None:
        cache = PopoverRenderCache()

        self.assertFalse(cache.should_rebuild(visible=False, content_key=("all", 1)))
        self.assertFalse(cache.should_rebuild(visible=False, content_key=("all", 2)))

    def test_visible_popover_rebuilds_only_when_content_changes(self) -> None:
        cache = PopoverRenderCache()

        self.assertTrue(cache.should_rebuild(visible=True, content_key=("all", 1)))
        self.assertFalse(cache.should_rebuild(visible=True, content_key=("all", 1)))
        self.assertTrue(cache.should_rebuild(visible=True, content_key=("codex", 1)))
        self.assertTrue(cache.should_rebuild(visible=True, content_key=("codex", 2)))

    def test_none_is_a_valid_content_key(self) -> None:
        cache = PopoverRenderCache()

        self.assertTrue(cache.should_rebuild(visible=True, content_key=None))
        self.assertFalse(cache.should_rebuild(visible=True, content_key=None))


class TestFileCache(unittest.TestCase):
    def test_missing_target_is_copied_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.bin"
            target = Path(tmp) / "cache" / "target.bin"
            source.write_bytes(b"logo")

            self.assertTrue(copy_file_if_changed(source, target))
            self.assertEqual(target.read_bytes(), b"logo")
            self.assertFalse(copy_file_if_changed(source, target))

    def test_same_size_changed_content_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.bin"
            target = Path(tmp) / "target.bin"
            source.write_bytes(b"new1")
            target.write_bytes(b"old1")

            self.assertTrue(copy_file_if_changed(source, target))
            self.assertEqual(target.read_bytes(), b"new1")

    def test_missing_source_raises_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                copy_file_if_changed(
                    Path(tmp) / "missing.bin",
                    Path(tmp) / "target.bin",
                )


class TestLinuxPanelIdempotence(unittest.TestCase):
    def test_unchanged_panel_does_not_rebuild_or_emit_signals(self) -> None:
        indicator = _make_indicator()
        lines = [{"engine_id": "codex", "label": "Codex - Session: 10%"}]

        indicator.update_panel("10%", lines)
        first_revision = indicator.revision
        first_signal_count = len(indicator.conn.signals)
        indicator.update_panel("10%", [dict(lines[0])])

        self.assertEqual(first_signal_count, 4)
        self.assertEqual(indicator.revision, first_revision)
        self.assertEqual(len(indicator.conn.signals), first_signal_count)

    def test_changed_panel_rebuilds_and_emits_signals(self) -> None:
        indicator = _make_indicator()

        indicator.update_panel("10%", [])
        first_revision = indicator.revision
        indicator.update_panel("11%", [])

        self.assertGreater(indicator.revision, first_revision)
        self.assertEqual(len(indicator.conn.signals), 8)


if __name__ == "__main__":
    unittest.main()
