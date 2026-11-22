"""Unit and integration test suite for AgentBar."""

from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentbar.cli import main as cli_main
from agentbar.detectors import (
    collect_usage_snapshot,
    detect_antigravity,
    detect_claude_code,
    detect_codex,
    detect_qoder,
)
from agentbar.menubar import create_tray_icon_image
from agentbar.models import (
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
        self.assertIn("AgentBar AI Monitor", desktop_entry)
        self.assertIn("OpenSettings", desktop_entry)

    def test_config_load_and_save(self) -> None:
        from agentbar.config import AgentBarConfig, load_config, save_config

        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "settings.json"
            cfg = AgentBarConfig()
            self.assertTrue(cfg.is_engine_enabled("claude"))
            cfg.set_engine_enabled("claude", False)
            cfg.refresh_interval_sec = 60
            cfg.warning_threshold_percent = 90
            cfg.bar_position = "center"
            save_config(cfg, config_path=cfg_file)

            loaded = load_config(config_path=cfg_file)
            self.assertFalse(loaded.is_engine_enabled("claude"))
            self.assertEqual(loaded.refresh_interval_sec, 60)
            self.assertEqual(loaded.warning_threshold_percent, 90)
            self.assertEqual(loaded.bar_position, "center")


if __name__ == "__main__":
    unittest.main()
