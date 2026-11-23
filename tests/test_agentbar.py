"""Unit and integration test suite for AgentBar."""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from agentbar.cli import main as cli_main
from agentbar.antigravity_quota import (
    find_antigravity_rpc_processes,
    parse_antigravity_quota_summary,
)
from agentbar.detectors import (
    collect_usage_snapshot,
    detect_antigravity,
    detect_claude_code,
    detect_codex,
    detect_qoder,
)
from agentbar.config import AgentBarConfig
from agentbar.packaging import DEBIAN_RUNTIME_DEPENDENCIES, validate_release_version
from agentbar.menubar import (
    _format_bar_from_config,
    create_tray_icon_image,
    find_installed_brand_icon,
    find_installed_provider_icon_dir,
    select_compact_engines,
    should_close_engine_popover,
)
from agentbar.models import (
    EngineUsage,
    RateLimitWindow,
    ascii_progress_bar,
    format_cost,
    format_relative_time,
    format_reset_countdown,
    format_tokens,
)
from agentbar.tui import render_ansi_dashboard


class TestAgentBar(unittest.TestCase):
    def setUp(self) -> None:
        self.fixed_now = 1795350000.0  # Fixed reference timestamp

    def test_formatters(self) -> None:
        self.assertEqual(format_tokens(0), "0")
        self.assertEqual(format_tokens(950), "950")
        self.assertEqual(format_tokens(37420), "37.4K")
        self.assertEqual(format_tokens(250000), "250K")
        self.assertEqual(format_tokens(50259773), "50.3M")
        self.assertEqual(format_tokens(1500000000), "1.50B")

        self.assertEqual(format_cost(0), "$0.00")
        self.assertEqual(format_cost(0.004), "<$0.01")
        self.assertEqual(format_cost(1.256), "$1.26")
        self.assertEqual(format_cost(26.875), "$26.9")

        self.assertEqual(
            format_reset_countdown(int(self.fixed_now + 7500), now_epoch=self.fixed_now),
            "2h 5m",
        )
        self.assertEqual(
            format_reset_countdown(int(self.fixed_now - 10), now_epoch=self.fixed_now),
            "reset",
        )
        self.assertEqual(
            format_relative_time(self.fixed_now - 300, now_epoch=self.fixed_now),
            "5m ago",
        )
        self.assertEqual(len(ascii_progress_bar(50.0, width=10)), 10)

    def test_compact_usage_engine_selection(self) -> None:
        claude = EngineUsage("claude", "Claude Code", "Claude", "", installed=True)
        codex = EngineUsage("codex", "OpenAI Codex", "Codex", "", installed=True)
        engines = [claude, codex]

        self.assertEqual(select_compact_engines(engines, "all"), engines)
        self.assertEqual(select_compact_engines(engines, "claude"), [claude])
        self.assertEqual(select_compact_engines(engines, "unknown"), engines)
        self.assertEqual(select_compact_engines([], "claude"), [])

    def test_provider_icon_activation_toggles_visible_popover(self) -> None:
        self.assertTrue(should_close_engine_popover("codex", True, "codex"))
        self.assertFalse(should_close_engine_popover("codex", False, "codex"))
        self.assertFalse(should_close_engine_popover("claude", True, "codex"))

    def test_compact_bar_uses_live_session_zero_without_weekly_fallback(self) -> None:
        cfg = AgentBarConfig(bar_metric_mode="session")
        claude = EngineUsage("claude", "Claude Code", "Claude", "C", installed=True)
        claude.primary_quota = RateLimitWindow("5h", 0.0, 300, is_estimated=False)
        claude.secondary_quota = RateLimitWindow("7d", 41.0, 10080, is_estimated=False)

        estimated = EngineUsage("antigravity", "Antigravity", "Agy", "A", installed=True)
        estimated.primary_quota = RateLimitWindow("5h", 6.0, 300, is_estimated=True)

        text = _format_bar_from_config(
            type("Snapshot", (), {"engines": [claude, estimated]})(), cfg
        )
        self.assertEqual(text, "C 0% · A --")

    def test_live_only_snapshot_is_parallel_and_preserves_engine_order(self) -> None:
        def fake(engine_id: str) -> EngineUsage:
            time.sleep(0.08)
            return EngineUsage(engine_id, engine_id, engine_id, engine_id[0], installed=True)

        with (
            patch("agentbar.detectors.detect_claude_code", side_effect=lambda **_: fake("claude")),
            patch("agentbar.detectors.detect_codex", side_effect=lambda **_: fake("codex")),
            patch("agentbar.detectors.detect_antigravity", side_effect=lambda **_: fake("antigravity")),
            patch("agentbar.detectors.detect_qoder", side_effect=lambda **_: fake("qoder")),
        ):
            started = time.perf_counter()
            snapshot = collect_usage_snapshot(live_only=True)
            elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.24)
        self.assertEqual(
            [engine.engine_id for engine in snapshot.engines],
            ["claude", "codex", "antigravity", "qoder"],
        )

    def test_live_only_fixture_does_not_invent_quota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir()
            usage = detect_claude_code(
                home_dir=home,
                now_epoch=self.fixed_now,
                live_only=True,
            )

        self.assertTrue(usage.installed)
        self.assertEqual(usage.status, "unavailable")
        self.assertIsNone(usage.primary_quota)
        self.assertIsNone(usage.secondary_quota)

    def test_installed_brand_icon_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            icon = home / ".local/share/icons/hicolor/256x256/apps/kio-usage-monitoring.png"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"png")
            self.assertEqual(find_installed_brand_icon(home), icon)
            icon.unlink()
            self.assertIsNone(find_installed_brand_icon(home))

    def test_installed_provider_icon_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            icon_dir = home / ".local/share/agentbar/providers"
            icon_dir.mkdir(parents=True)
            self.assertEqual(find_installed_provider_icon_dir(home), icon_dir)

    def test_codex_icon_renders_white_on_transparent_background(self) -> None:
        import gi

        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        icon_path = Path(__file__).resolve().parent.parent / "assets/providers/codex.svg"
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(icon_path), 64, 64, True
        )
        pixels = pixbuf.get_pixels()
        channels = pixbuf.get_n_channels()
        visible_white_pixels = 0
        for offset in range(0, len(pixels), channels):
            red, green, blue = pixels[offset : offset + 3]
            alpha = pixels[offset + 3] if channels == 4 else 255
            if alpha > 0 and red > 200 and green > 200 and blue > 200:
                visible_white_pixels += 1
        self.assertGreater(visible_white_pixels, 100)

    def test_detect_claude_code_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            proj_dir = home / ".claude" / "projects" / "demo-app"
            proj_dir.mkdir(parents=True)
            jsonl_file = proj_dir / "session-1.jsonl"

            records = [
                {
                    "timestamp": self.fixed_now - 3600,  # 1h ago (inside 5h, today, 7d)
                    "requestId": "req_1",
                    "message": {
                        "model": "claude-sonnet-4-5",
                        "usage": {
                            "input_tokens": 10000,
                            "cache_creation_input_tokens": 5000,
                            "cache_read_input_tokens": 20000,
                            "output_tokens": 2500,
                        },
                    },
                },
                # Duplicate chunk with same requestId should be deduplicated
                {
                    "timestamp": self.fixed_now - 3599,
                    "requestId": "req_1",
                    "message": {
                        "model": "claude-sonnet-4-5",
                        "usage": {
                            "input_tokens": 10000,
                            "cache_creation_input_tokens": 5000,
                            "cache_read_input_tokens": 20000,
                            "output_tokens": 2500,
                        },
                    },
                },
                {
                    "timestamp": self.fixed_now - (3 * 86400),  # 3 days ago (inside 7d)
                    "requestId": "req_2",
                    "message": {
                        "model": "claude-sonnet-4-5",
                        "usage": {
                            "input_tokens": 50000,
                            "cache_creation_input_tokens": 0,
                            "cache_read_input_tokens": 10000,
                            "output_tokens": 5000,
                        },
                    },
                },
            ]
            with open(jsonl_file, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")

            u = detect_claude_code(home_dir=home, now_epoch=self.fixed_now)
            self.assertTrue(u.installed)
            self.assertEqual(u.tokens_5h, 37500)
            self.assertEqual(u.tokens_today, 37500)
            self.assertEqual(u.tokens_7d, 102500)
            self.assertEqual(u.tokens_total, 102500)
            self.assertEqual(u.breakdown.input_tokens, 60000)
            self.assertEqual(u.breakdown.output_tokens, 7500)
            self.assertEqual(u.breakdown.cached_tokens, 35000)
            self.assertGreater(u.estimated_cost_usd, 0.0)
            self.assertIsNotNone(u.primary_quota)

    def test_detect_codex_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            codex_dir = home / ".codex"
            codex_dir.mkdir(parents=True)

            # Create state_5.sqlite
            db_path = codex_dir / "state_5.sqlite"
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE threads (id TEXT PRIMARY KEY, tokens_used INTEGER, updated_at INTEGER, model TEXT)"
            )
            conn.execute(
                "INSERT INTO threads VALUES ('t1', 45000, ?, 'gpt-5-codex')",
                (int(self.fixed_now - 1800),),
            )
            conn.commit()
            conn.close()

            # Create session jsonl with token_count and rate_limits
            sess_dir = codex_dir / "sessions" / "2026" / "11" / "22"
            sess_dir.mkdir(parents=True)
            jf = sess_dir / "rollout.jsonl"
            event = {
                "timestamp": "2026-11-22T12:00:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 35000,
                            "cached_input_tokens": 8000,
                            "output_tokens": 1500,
                            "reasoning_output_tokens": 500,
                            "total_tokens": 45000,
                        }
                    },
                    "rate_limits": {
                        "plan_type": "plus",
                        "primary": {
                            "used_percent": 18.5,
                            "window_minutes": 300,
                            "resets_at": int(self.fixed_now + 3600),
                        },
                        "secondary": {
                            "used_percent": 84.0,
                            "window_minutes": 10080,
                            "resets_at": int(self.fixed_now + 86400),
                        },
                    },
                },
            }
            with open(jf, "w", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")

            u = detect_codex(home_dir=home, now_epoch=self.fixed_now)
            self.assertTrue(u.installed)
            self.assertEqual(u.tokens_total, 45000)
            self.assertEqual(u.tokens_5h, 45000)
            self.assertIn("plus", u.model_or_plan)
            self.assertIsNotNone(u.primary_quota)
            self.assertIsNotNone(u.secondary_quota)
            self.assertAlmostEqual(u.primary_quota.used_percent, 18.5)
            self.assertAlmostEqual(u.secondary_quota.used_percent, 84.0)
            self.assertEqual(u.menu_bar_badge(compact=False), "Codex 18%")
            self.assertEqual(u.primary_quota.display_title, "Current session")
            self.assertEqual(u.secondary_quota.display_title, "This week")
            self.assertTrue(
                u.primary_quota.reset_subtitle(self.fixed_now).startswith("Resets at ")
            )
            self.assertTrue(
                u.secondary_quota.reset_subtitle(self.fixed_now).startswith("Resets ")
            )

    def test_detect_antigravity_and_qoder_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)

            # Antigravity fixture
            agy_dir = home / ".gemini" / "antigravity"
            log_dir = agy_dir / "brain" / "conv-123" / ".system_generated" / "logs"
            log_dir.mkdir(parents=True)
            tf = log_dir / "transcript.jsonl"
            tf.write_text("x" * 40000, encoding="utf-8")  # ~10,000 tokens

            db_path = agy_dir / "conversation_summaries.db"
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE conversation_summaries (conversation_id TEXT, step_count INTEGER, last_modified_time TEXT)"
            )
            conn.execute(
                "INSERT INTO conversation_summaries VALUES ('conv-123', 42, '2026-11-22T12:00:00Z')"
            )
            conn.commit()
            conn.close()

            agy_u = detect_antigravity(home_dir=home, now_epoch=self.fixed_now)
            self.assertTrue(agy_u.installed)
            self.assertEqual(agy_u.sessions_total, 1)
            self.assertEqual(agy_u.tokens_total, 10000)
            self.assertIn("42 steps", agy_u.model_or_plan)

            # Qoder fixture
            qoder_dir = home / ".qoder"
            (qoder_dir / "agents").mkdir(parents=True)
            (qoder_dir / "skills").mkdir(parents=True)
            (qoder_dir / "agents" / "pm.md").write_text("agent", encoding="utf-8")
            (qoder_dir / "skills" / "s1.md").write_text("skill1", encoding="utf-8")
            (qoder_dir / "skills" / "s2.md").write_text("skill2", encoding="utf-8")

            qoder_u = detect_qoder(home_dir=home, now_epoch=self.fixed_now)
            self.assertTrue(qoder_u.installed)
            self.assertEqual(qoder_u.extra["agents_count"], 1)
            self.assertEqual(qoder_u.extra["skills_count"], 2)

    def test_antigravity_quota_summary_preserves_all_limits(self) -> None:
        payload = {
            "response": {
                "quotaSummary": {
                    "groups": [
                        {
                            "displayName": "Gemini Models",
                            "buckets": [
                                {
                                    "displayName": "Weekly Limit Remaining",
                                    "remainingFraction": 0.93,
                                    "resetTime": self.fixed_now + 6 * 86400,
                                    "window": "7d",
                                },
                                {
                                    "displayName": "Five Hour Limit Remaining",
                                    "remainingFraction": 0.96,
                                    "resetTime": self.fixed_now + 2 * 3600,
                                    "window": "5h",
                                },
                            ],
                        },
                        {
                            "displayName": "Claude and GPT models",
                            "quotaBuckets": [
                                {"title": "Weekly Limit Remaining", "remainingPercent": 100},
                                {"title": "Five Hour Limit Remaining", "remainingPercent": 100},
                            ],
                        },
                        {
                            "displayName": "Gemini 4 Argon",
                            "buckets": [
                                {
                                    "displayName": "Gemini 4 Argon Weekly Limit",
                                    "remainingFraction": 0.04,
                                    "resetTime": self.fixed_now + 5 * 86400,
                                }
                            ],
                        },
                    ]
                }
            }
        }

        parsed = parse_antigravity_quota_summary(payload, self.fixed_now)
        self.assertIsNotNone(parsed)
        primary, secondary, groups = parsed
        self.assertEqual(len(groups), 3)
        self.assertEqual([len(group["items"]) for group in groups], [2, 2, 1])
        self.assertEqual(groups[0]["items"][0]["remaining_percent"], 93)
        self.assertEqual(groups[2]["items"][0]["remaining_percent"], 4)
        self.assertAlmostEqual(primary.used_percent, 4.0)
        self.assertAlmostEqual(secondary.used_percent, 96.0)

    def test_antigravity_quota_summary_rejects_invalid_payload(self) -> None:
        self.assertIsNone(parse_antigravity_quota_summary({}, self.fixed_now))
        invalid = {"groups": [{"displayName": "Gemini", "buckets": [{}]}]}
        self.assertIsNone(parse_antigravity_quota_summary(invalid, self.fixed_now))

        top_level = {
            "response": {
                "buckets": [
                    {
                        "displayName": "Weekly Limit Remaining",
                        "remainingFraction": 0.5,
                        "window": "7d",
                    }
                ]
            }
        }
        parsed = parse_antigravity_quota_summary(top_level, self.fixed_now)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed[2][0]["items"][0]["remaining_percent"], 50)

    def test_antigravity_process_selection_ignores_vscode_codeium(self) -> None:
        output = "\n".join(
            [
                "toan 100 0 0 codeium/language_server --ide_name vscode --csrf_token wrong",
                "toan 200 0 0 /opt/antigravity/language_server --database_dir /home/toan/.gemini/antigravity --csrf_token right",
            ]
        )
        self.assertEqual(find_antigravity_rpc_processes(output), [("200", "right")])

    def test_release_version_and_linux_dependencies(self) -> None:
        self.assertEqual(validate_release_version("v1.0.0"), "1.0.0")
        self.assertIn("python3-gi", DEBIAN_RUNTIME_DEPENDENCIES)
        self.assertIn("gir1.2-ayatanaappindicator3-0.1", DEBIAN_RUNTIME_DEPENDENCIES)

    def test_release_version_rejects_prerelease_and_empty_values(self) -> None:
        for invalid in ("", "1.0", "1.0.0-beta", "latest"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_release_version(invalid)

    def test_snapshot_outputs_and_cli(self) -> None:
        snap = collect_usage_snapshot()
        self.assertGreaterEqual(len(snap.installed_engines), 1)

        bar_str = snap.to_bar_string()
        self.assertIn("%", bar_str)

        waybar = snap.to_waybar_dict()
        self.assertIn("text", waybar)
        self.assertIn("tooltip", waybar)

        swiftbar = snap.to_swiftbar_string()
        self.assertIn("---", swiftbar)

        tmux_str = snap.to_tmux_string()
        self.assertIn("#[", tmux_str)

        ansi_table = render_ansi_dashboard(snap, use_color=False)
        self.assertIn("Current session", ansi_table)
        self.assertIn("This week", ansi_table)

        # Verify Tray Icon PIL image creation
        img = create_tray_icon_image(snap)
        self.assertEqual(img.size, (64, 64))

        # Verify CLI JSON mode
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main(["--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(buf.getvalue())
        self.assertIn("engines", parsed)
        self.assertIn("bar_text", parsed)

    def test_packaging_and_desktop_bundle(self) -> None:
        from agentbar.packaging import (
            build_macos_app_bundle,
            build_zipapp_binary,
            create_linux_desktop_entry,
            generate_app_icons,
        )

        project_root = Path(__file__).resolve().parent.parent
        icons = generate_app_icons(project_root)
        self.assertTrue(icons["png"].is_file())
        self.assertTrue(icons["ico"].is_file())

        binary = build_zipapp_binary(project_root)
        self.assertTrue(binary.is_file())

        with tempfile.TemporaryDirectory() as tmp:
            app_bundle = build_macos_app_bundle(
                project_root, binary, icons["png"], output_dir=Path(tmp)
            )
            self.assertTrue((app_bundle / "Contents" / "Info.plist").is_file())
            self.assertTrue((app_bundle / "Contents" / "MacOS" / "AgentBar").is_file())

        desktop_entry = create_linux_desktop_entry(binary, icons["png"])
        self.assertIn("[Desktop Entry]", desktop_entry)
        self.assertIn("Name=Kio Usage Monitoring", desktop_entry)
        self.assertIn("Icon=kio-usage-monitoring", desktop_entry)
        self.assertIn("OpenSettings", desktop_entry)

    def test_config_load_and_save(self) -> None:
        from agentbar.config import AgentBarConfig, load_config, save_config

        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "settings.json"
            cfg = AgentBarConfig()
            self.assertTrue(cfg.is_engine_enabled("claude"))
            self.assertFalse(cfg.autostart_on_login)
            self.assertFalse(cfg.autostart_prompted)
            cfg.set_engine_enabled("claude", False)
            cfg.autostart_on_login = True
            cfg.autostart_prompted = True
            cfg.refresh_interval_sec = 60
            cfg.warning_threshold_percent = 90
            cfg.bar_position = "center"
            save_config(cfg, config_path=cfg_file)

            loaded = load_config(config_path=cfg_file)
            self.assertFalse(loaded.is_engine_enabled("claude"))
            self.assertTrue(loaded.autostart_on_login)
            self.assertTrue(loaded.autostart_prompted)
            self.assertEqual(loaded.refresh_interval_sec, 60)
            self.assertEqual(loaded.warning_threshold_percent, 90)
            self.assertEqual(loaded.bar_position, "center")


if __name__ == "__main__":
    unittest.main()
