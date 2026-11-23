"""Parsing helpers for Antigravity's local quota RPC responses."""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import RateLimitWindow


QuotaResult = Tuple[RateLimitWindow, RateLimitWindow, List[Dict[str, Any]]]


def find_antigravity_rpc_processes(ps_output: str) -> List[Tuple[str, str]]:
    """Return Antigravity language-server PID/token pairs, best match first."""
    candidates: List[Tuple[int, str, str]] = []
    for line in ps_output.splitlines():
        if "language_server" not in line or "--csrf_token" not in line:
            continue
        token_match = re.search(r"--csrf_token(?:=|\s+)([a-zA-Z0-9_-]+)", line)
        parts = line.split()
        if not token_match or len(parts) < 2 or not parts[1].isdigit():
            continue

        lowered = line.lower()
        score = 0
        if ".gemini/antigravity" in lowered:
            score += 8
        if "/opt/antigravity" in lowered or "ide_name antigravity" in lowered:
            score += 6
        if "cloudcode" in lowered:
            score += 2
        if ".codeium" in lowered or "ide_name vscode" in lowered:
            score -= 8
        candidates.append((score, parts[1], token_match.group(1)))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [(pid, token) for score, pid, token in candidates if score > 0]


def parse_antigravity_quota_summary(data: Any, now: float) -> Optional[QuotaResult]:
    """Normalize every quota group and bucket returned by Antigravity."""
    groups = _find_groups(data)
    standalone_buckets = _find_standalone_buckets(data)
    if not groups and standalone_buckets:
        groups = [{"displayName": "Model limits", "buckets": standalone_buckets}]
    if not groups:
        return None

    normalized_groups: List[Dict[str, Any]] = []
    windows: Dict[str, List[Tuple[float, Optional[int]]]] = {"5h": [], "7d": []}

    for group in groups:
        items: List[Dict[str, Any]] = []
        for bucket in _bucket_list(group):
            item = _normalize_bucket(bucket, now)
            if item is None:
                continue
            items.append(item)
            window = item["window"]
            if window in windows:
                windows[window].append(
                    (100.0 - float(item["remaining_percent"]), item["reset_time"])
                )

        if not items:
            continue
        normalized_groups.append(
            {
                "group_title": _text(group, "displayName", "display_name", "title", "name"),
                "group_description": _text(group, "description", "subtitle"),
                "items": items,
            }
        )

    if not normalized_groups:
        return None

    primary = _aggregate_window("5h", windows["5h"], 300)
    secondary = _aggregate_window("7d", windows["7d"], 10080)
    return primary, secondary, normalized_groups


def _find_groups(data: Any) -> List[Dict[str, Any]]:
    candidates: List[List[Dict[str, Any]]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if _normalized_key(key) in {"groups", "quotagroups", "userquotagroups"}:
                    if isinstance(child, list):
                        group_list = [entry for entry in child if isinstance(entry, dict)]
                        if group_list:
                            candidates.append(group_list)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return max(candidates, key=len, default=[])


def _find_standalone_buckets(data: Any) -> List[Dict[str, Any]]:
    candidates: List[List[Dict[str, Any]]] = []

    def visit(value: Any) -> None:
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            if _normalized_key(key) in {"buckets", "quotabuckets"} and isinstance(child, list):
                bucket_list = [entry for entry in child if isinstance(entry, dict)]
                if bucket_list:
                    candidates.append(bucket_list)
            elif isinstance(child, dict):
                visit(child)

    visit(data)
    return max(candidates, key=len, default=[])


def _bucket_list(group: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for key in ("buckets", "quotaBuckets", "quota_buckets", "items", "limits"):
        value = group.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
    return []


def _normalize_bucket(bucket: Dict[str, Any], now: float) -> Optional[Dict[str, Any]]:
    remaining = _remaining_percent(bucket)
    if remaining is None:
        return None

    title = _text(bucket, "displayName", "display_name", "title", "name")
    subtitle = _text(bucket, "description", "subtitle")
    reset_time = _parse_timestamp(
        _value(bucket, "resetTime", "reset_time", "resetsAt", "resets_at")
    )
    window = _quota_window(bucket, title, reset_time, now)
    if not subtitle and remaining < 100 and reset_time:
        subtitle = _refresh_text(reset_time, now, window == "7d")

    return {
        "bucket_id": str(_value(bucket, "bucketId", "bucket_id", "id") or ""),
        "title": title or ("Weekly Limit Remaining" if window == "7d" else "Five Hour Limit Remaining"),
        "subtitle": subtitle,
        "remaining_percent": remaining,
        "reset_time": reset_time,
        "window": window,
    }


def _remaining_percent(bucket: Dict[str, Any]) -> Optional[int]:
    fraction = _value(bucket, "remainingFraction", "remaining_fraction")
    percent = _value(bucket, "remainingPercent", "remaining_percent")
    try:
        raw = float(fraction) * 100.0 if fraction is not None else float(percent)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, int(round(raw))))


def _quota_window(
    bucket: Dict[str, Any], title: str, reset_time: Optional[int], now: float
) -> str:
    raw = str(_value(bucket, "window", "windowType", "window_type", "period") or "").lower()
    searchable = f"{raw} {title.lower()}"
    if any(marker in searchable for marker in ("5h", "five hour", "five-hour")):
        return "5h"
    if any(marker in searchable for marker in ("7d", "week", "weekly")):
        return "7d"
    if reset_time is not None and reset_time - now <= 5 * 3600 + 300:
        return "5h"
    return "7d"


def _aggregate_window(
    label: str, values: List[Tuple[float, Optional[int]]], window_minutes: int
) -> RateLimitWindow:
    if not values:
        return RateLimitWindow(label, 0.0, window_minutes, None, is_estimated=False)
    used_percent, reset_time = max(values, key=lambda item: item[0])
    return RateLimitWindow(
        label=label,
        used_percent=round(max(0.0, min(100.0, used_percent)), 1),
        window_minutes=window_minutes,
        resets_at=reset_time,
        is_estimated=False,
    )


def _refresh_text(reset_ts: int, now: float, weekly: bool) -> str:
    diff = max(0, int(reset_ts - now))
    days, remainder = divmod(diff, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = max(1, remainder // 60)
    kind = "weekly limit" if weekly else "5-hour limit"
    if days:
        return f"You have used some of your {kind}, it will fully refresh in {days} days, {hours} hours."
    if hours:
        return f"You have used some of your {kind}, it will fully refresh in {hours} hours, {minutes} minutes."
    return f"You have used some of your {kind}, it will fully refresh in {minutes} minutes."


def _parse_timestamp(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return int(numeric / 1000.0 if numeric > 4_102_444_800 else numeric)
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.isdigit():
        return _parse_timestamp(int(raw))
    try:
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        parsed = datetime.datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return int(parsed.timestamp())
    except ValueError:
        return None


def _text(data: Dict[str, Any], *keys: str) -> str:
    value = _value(data, *keys)
    return str(value).strip() if value is not None else ""


def _value(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z]", "", str(value).lower())
