#!/usr/bin/env python3
"""
Date & Time Utility Tool

Provides timezone-aware datetime operations: current time, format conversion,
timezone shifting, date math, and duration formatting. Uses the `zoneinfo`
module (Python 3.9+) for IANA timezone support.

Design:
- Single `datetime_util` tool with `action` parameter for different operations
- All timestamps are ISO 8601 by default; accepts common format variations
- No external dependencies beyond stdlib (datetime, zoneinfo, pytz optional)
"""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

try:
    from zoneinfo import ZoneInfo, available_timezones
    HAS_ZONEINFO = True
except ImportError:
    HAS_ZONEINFO = False

# Fallback for older Python: try pytz
try:
    import pytz
    HAS_PYTZ = True
except ImportError:
    HAS_PYTZ = False


def tool_error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def _get_tz(tz_name: str) -> Optional[object]:
    """Get a timezone object by IANA name (e.g. 'Asia/Shanghai', 'US/Eastern')."""
    if not tz_name or tz_name.strip().lower() in ("utc", "z", ""):
        return timezone.utc

    tz_name = tz_name.strip()

    if HAS_ZONEINFO and tz_name in available_timezones():
        return ZoneInfo(tz_name)

    if HAS_PYTZ:
        try:
            return pytz.timezone(tz_name)
        except Exception:
            pass

    # Handle common abbreviations/aliases
    aliases = {
        "cst": "Asia/Shanghai",
        "pst": "US/Pacific",
        "est": "US/Eastern",
        "ist": "Asia/Kolkata",
        "jst": "Asia/Tokyo",
        "bst": "Europe/London",
        "cet": "Europe/Paris",
        "aest": "Australia/Sydney",
        "nzst": "Pacific/Auckland",
        "hkt": "Asia/Hong_Kong",
        "sgt": "Asia/Singapore",
    }
    low = tz_name.lower()
    if low in aliases:
        return _get_tz(aliases[low])

    return None


def _parse_datetime(text: str) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Parse a datetime string into a datetime object.
    Supports ISO 8601, common date formats, epoch timestamps.
    """
    text = text.strip()
    if not text:
        return datetime.now(timezone.utc), None

    # Try epoch timestamp (unix seconds)
    try:
        ts = float(text)
        return datetime.fromtimestamp(ts, tz=timezone.utc), None
    except (ValueError, OverflowError, OSError):
        pass

    # Try ISO 8601 and common variants
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y/%m/%d %H:%M:%S",
        "%m/%d/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%d-%b-%Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%B %d, %Y %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822
    ]

    # Clean up: replace 'Z' with +00:00 for strptime compatibility
    cleaned = text
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+0000"
    # Normalize timezone offset format: +HH:MM -> +HHMM
    cleaned = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", cleaned)

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt, None
        except ValueError:
            continue

    return None, f"Could not parse '{text}' as a datetime. Try ISO 8601 format (e.g. '2025-06-14T10:30:00Z')"


def _format_datetime(dt: datetime, tz: object, fmt: str) -> str:
    """Format a datetime with timezone conversion."""
    dt_local = dt.astimezone(tz)
    if fmt == "iso":
        return dt_local.isoformat()
    elif fmt == "date":
        return dt_local.strftime("%Y-%m-%d")
    elif fmt == "time":
        return dt_local.strftime("%H:%M:%S")
    elif fmt == "datetime":
        return dt_local.strftime("%Y-%m-%d %H:%M:%S")
    elif fmt == "rfc2822":
        return dt_local.strftime("%a, %d %b %Y %H:%M:%S %z")
    elif fmt == "unix":
        return str(int(dt_local.timestamp()))
    elif fmt == "human":
        return dt_local.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")
    else:
        return dt_local.strftime(fmt)


def datetime_util_tool(
    action: str = "now",
    timezone: str = "UTC",
    target_timezone: str = "",
    input_time: str = "",
    format: str = "iso",
    add_days: Optional[int] = None,
    add_hours: Optional[int] = None,
    add_minutes: Optional[int] = None,
) -> str:
    """
    Date and time utility.

    Actions:
      now         - Current time in the specified timezone
      convert     - Convert a timestamp from one timezone to another
      difference  - Time between two timestamps
      add         - Add/subtract duration from a timestamp
    """
    action = action.strip().lower()

    # Resolve timezone
    tz_name = timezone.strip() or "UTC"
    tz = _get_tz(tz_name)
    if tz is None:
        return tool_error(f"Unknown timezone '{tz_name}'. Use an IANA name like 'Asia/Shanghai' or 'US/Pacific'")

    target_tz_name = target_timezone.strip() if target_timezone else tz_name
    target_tz = _get_tz(target_tz_name) if target_timezone else tz

    try:
        if action == "now":
            now = datetime.now(tz)
            return json.dumps({
                "timezone": tz_name,
                "iso": now.isoformat(),
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "unix_timestamp": int(now.timestamp()),
                "weekday": now.strftime("%A"),
                "day_of_year": now.timetuple().tm_yday,
                "week_number": now.isocalendar()[1],
            }, ensure_ascii=False, indent=2)

        elif action == "convert":
            if not input_time:
                return tool_error("input_time is required for convert action")
            dt, err = _parse_datetime(input_time)
            if err:
                return tool_error(err)
            converted = _format_datetime(dt, target_tz, format)
            result = {
                "input": input_time,
                "from_timezone": tz_name,
                "to_timezone": target_tz_name,
                "result": converted,
                "format": format,
            }
            if format == "iso" and converted != input_time:
                extra = {
                    "datetime": dt.astimezone(target_tz).strftime("%Y-%m-%d %H:%M:%S"),
                    "date": dt.astimezone(target_tz).strftime("%Y-%m-%d"),
                    "time": dt.astimezone(target_tz).strftime("%H:%M:%S"),
                    "unix_timestamp": int(dt.timestamp()),
                }
                result.update(extra)
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif action == "difference":
            if "|||" not in input_time:
                return tool_error("difference action requires two timestamps separated by '|||' (e.g. '2025-01-01|||2025-06-01')")
            parts = input_time.split("|||", 1)
            dt1, err1 = _parse_datetime(parts[0].strip())
            if err1:
                return tool_error(f"First timestamp: {err1}")
            dt2, err2 = _parse_datetime(parts[1].strip())
            if err2:
                return tool_error(f"Second timestamp: {err2}")

            diff = abs(dt2 - dt1)
            total_seconds = int(diff.total_seconds())
            days, remainder = divmod(total_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)

            return json.dumps({
                "from": parts[0].strip(),
                "to": parts[1].strip(),
                "difference": {
                    "total_seconds": total_seconds,
                    "total_minutes": round(total_seconds / 60, 1),
                    "total_hours": round(total_seconds / 3600, 2),
                    "total_days": round(total_seconds / 86400, 2),
                    "days": days,
                    "hours": hours,
                    "minutes": minutes,
                    "seconds": seconds,
                    "human": f"{days}d {hours}h {minutes}m {seconds}s" if days else f"{hours}h {minutes}m {seconds}s",
                },
            }, ensure_ascii=False, indent=2)

        elif action == "add":
            if not input_time:
                # Use current time if no input
                dt = datetime.now(tz)
            else:
                dt, err = _parse_datetime(input_time)
                if err:
                    return tool_error(err)

            delta = timedelta(
                days=add_days or 0,
                hours=add_hours or 0,
                minutes=add_minutes or 0,
            )
            result_dt = dt + delta

            return json.dumps({
                "input": input_time or "(now)",
                "timezone": tz_name,
                "add": {
                    "days": add_days or 0,
                    "hours": add_hours or 0,
                    "minutes": add_minutes or 0,
                },
                "result": result_dt.astimezone(tz).isoformat(),
                "datetime": result_dt.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
            }, ensure_ascii=False, indent=2)

        else:
            return tool_error(
                f"Unknown action '{action}'. Supported: now, convert, difference, add"
            )

    except Exception as e:
        return tool_error(f"{action} failed: {e}")


def check_datetime_requirements() -> bool:
    """No external requirements -- always available."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

DATETIME_SCHEMA = {
    "name": "datetime_util",
    "description": (
        "Date and time utility: current time in any timezone, convert timestamps "
        "between timezones, compute time differences, and add/subtract durations.\\n\\n"
        "Actions:\\n"
        "- now: current time in the specified timezone\\n"
        "- convert: convert a timestamp between timezones\\n"
        "- difference: time between two timestamps (separate with '|||')\\n"
        "- add: add/subtract days, hours, minutes from a timestamp\\n\\n"
        "Examples:\\n"
        "  datetime_util(action='now', timezone='Asia/Shanghai')\\n"
        "  datetime_util(action='convert', input_time='2025-06-14T10:00:00Z', "
        "target_timezone='Asia/Shanghai')\\n"
        "  datetime_util(action='difference', input_time='2025-01-01|||2025-06-01')\\n"
        "  datetime_util(action='add', input_time='2025-06-14', add_days=7)"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["now", "convert", "difference", "add"],
                "description": "Operation to perform (default: now)",
                "default": "now",
            },
            "timezone": {
                "type": "string",
                "description": (
                    "IANA timezone name for the input or reference timezone "
                    "(default: 'UTC'). Examples: 'Asia/Shanghai', 'US/Pacific', "
                    "'Europe/London', 'Asia/Tokyo', 'Australia/Sydney'. "
                    "Common abbreviations also work: 'CST', 'PST', 'EST', 'IST', 'JST'."
                ),
                "default": "UTC",
            },
            "target_timezone": {
                "type": "string",
                "description": "Target timezone for convert action. Omit to use the same timezone as input.",
            },
            "input_time": {
                "type": "string",
                "description": (
                    "Input timestamp (ISO 8601 preferred, also accepts common formats). "
                    "For 'difference' action, provide two timestamps separated by '|||'. "
                    "For 'add' action, defaults to current time if omitted."
                ),
            },
            "format": {
                "type": "string",
                "enum": ["iso", "date", "time", "datetime", "rfc2822", "unix", "human"],
                "description": (
                    "Output format for convert action (default: iso). "
                    "Use 'human' for readable format like 'Saturday, June 14, 2025 at 10:30:00 AM UTC'."
                ),
                "default": "iso",
            },
            "add_days": {
                "type": "integer",
                "description": "Days to add (negative to subtract). Used with 'add' action.",
            },
            "add_hours": {
                "type": "integer",
                "description": "Hours to add (negative to subtract). Used with 'add' action.",
            },
            "add_minutes": {
                "type": "integer",
                "description": "Minutes to add (negative to subtract). Used with 'add' action.",
            },
        },
        "required": [],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="datetime_util",
    toolset="datetime",
    schema=DATETIME_SCHEMA,
    handler=lambda args, **kw: datetime_util_tool(
        action=args.get("action", "now"),
        timezone=args.get("timezone", "UTC"),
        target_timezone=args.get("target_timezone", ""),
        input_time=args.get("input_time", ""),
        format=args.get("format", "iso"),
        add_days=args.get("add_days"),
        add_hours=args.get("add_hours"),
        add_minutes=args.get("add_minutes"),
    ),
    check_fn=check_datetime_requirements,
    emoji="🕐",
)
