#!/usr/bin/env python3
"""
JSON Processing Tool - Validate, Format, Extract, Transform

Provides structured JSON manipulation without cluttering the conversation with
raw shell output. Covers validation, formatting, path extraction (jq-like),
schema inference, and diff/comparison.

Design:
- Single `json_process` tool with a `mode` parameter for different actions
- No external dependencies beyond stdlib (json, jsonschema optional)
- All operations produce clean, structured output the agent can read directly
"""

import json
from typing import Any, Dict, List, Optional, Tuple

# Max input size to prevent context flooding
MAX_INPUT_CHARS = 100_000


def tool_error(message: str) -> str:
    """Return a structured error response."""
    return json.dumps({"error": message}, ensure_ascii=False)


def _safe_load(text: str) -> Tuple[Optional[Any], Optional[str]]:
    """Try to parse text as JSON. Returns (parsed, None) or (None, error)."""
    text = text.strip()
    if not text:
        return None, "Empty input"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error at line {e.lineno}, col {e.colno}: {e.msg}"


def _format_json(data: Any, indent: int = 2, sort_keys: bool = False) -> str:
    """Format JSON with pretty printing."""
    return json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False)


def _compact_json(data: Any) -> str:
    """Compact single-line JSON."""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _json_extract(data: Any, path: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Extract value at a dot-separated or bracket-notation path.
    Examples: "users.0.name", "data['items'][0]", "results[0].id"
    """
    if not path or not path.strip():
        return data, None

    current = data
    # Tokenize path: handle dot.separated and bracket[0] notations
    # Normalize: replace brackets with dots, remove quotes
    normalized = path.strip()
    normalized = normalized.replace("[", ".").replace("]", "")
    normalized = normalized.replace("'", "").replace('"', "")
    parts = [p for p in normalized.split(".") if p]

    for part in parts:
        if current is None:
            return None, f"Path '{path}' hit null at part '{part}'"
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return None, f"Key '{part}' not found at path '{path}'"
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None, f"Index {idx} out of range (len={len(current)}) at path '{path}'"
            except ValueError:
                return None, f"Cannot index list with non-integer '{part}' at path '{path}'"
        else:
            return None, f"Cannot traverse into {type(current).__name__} at path '{path}'"

    return current, None


def _json_keys(data: Any, prefix: str = "") -> List[str]:
    """Recursively list all keys/paths in a JSON structure."""
    paths = []
    if isinstance(data, dict):
        for k, v in data.items():
            full = f"{prefix}.{k}" if prefix else str(k)
            paths.append(full)
            paths.extend(_json_keys(v, full))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            full = f"{prefix}[{i}]"
            paths.extend(_json_keys(v, full))
    return paths


def _infer_type(v: Any) -> str:
    t = type(v).__name__
    if t == "NoneType":
        return "null"
    return t


def _json_schema(data: Any, depth: int = 0, max_depth: int = 5) -> Dict:
    """
    Infer a lightweight schema from JSON data. Depth-limited to prevent
    explosion on deeply nested structures.
    """
    if depth > max_depth:
        return {"type": "any (max depth reached)"}

    if data is None:
        return {"type": "null"}
    if isinstance(data, bool):
        return {"type": "boolean"}
    if isinstance(data, int):
        return {"type": "integer"}
    if isinstance(data, float):
        return {"type": "number"}
    if isinstance(data, str):
        if len(data) > 200:
            return {"type": "string", "length": len(data), "preview": data[:200]}
        return {"type": "string", "length": len(data)}
    if isinstance(data, list):
        if not data:
            return {"type": "array", "items": None, "count": 0}
        item_types = {}
        for item in data:
            t = json.dumps(_inf_type_flat(item))
            item_types[t] = item_types.get(t, 0) + 1
        most_common = max(item_types, key=item_types.get)
        return {
            "type": "array",
            "count": len(data),
            "item_types": {_inf_type_flat(data[0])["type"]: item_types.get(most_common, 0)},
            "sample": data[0] if len(data) > 0 else None,
        }
    if isinstance(data, dict):
        if not data:
            return {"type": "object", "keys": 0}
        schema = {"type": "object", "keys": len(data), "properties": {}}
        for k, v in data.items():
            schema["properties"][k] = _json_schema(v, depth + 1, max_depth)
        return schema

    return {"type": _infer_type(data)}


def _inf_type_flat(data: Any) -> Dict:
    """Simplified type inference for array item type counting."""
    if data is None:
        return {"type": "null"}
    if isinstance(data, bool):
        return {"type": "boolean"}
    if isinstance(data, int):
        return {"type": "integer"}
    if isinstance(data, float):
        return {"type": "number"}
    if isinstance(data, str):
        return {"type": "string"}
    if isinstance(data, list):
        return {"type": "array"}
    if isinstance(data, dict):
        return {"type": "object"}
    return {"type": _infer_type(data)}


def _compare_json(a: Any, b: Any, path: str = "$") -> List[str]:
    """Recursively diff two JSON values."""
    diffs = []
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        diffs.append(f"{path}: type mismatch ({type(a).__name__} vs {type(b).__name__})")
        return diffs
    if isinstance(a, dict):
        all_keys = set(a.keys()) | set(b.keys())
        for k in sorted(all_keys):
            new_path = f"{path}.{k}"
            if k not in a:
                diffs.append(f"{new_path}: missing in left (only in right)")
            elif k not in b:
                diffs.append(f"{new_path}: missing in right (only in left)")
            else:
                diffs.extend(_compare_json(a[k], b[k], new_path))
    elif isinstance(a, list):
        max_len = max(len(a), len(b))
        for i in range(max_len):
            new_path = f"{path}[{i}]"
            if i >= len(a):
                diffs.append(f"{new_path}: missing in left (only in right)")
            elif i >= len(b):
                diffs.append(f"{new_path}: missing in right (only in left)")
            else:
                diffs.extend(_compare_json(a[i], b[i], new_path))
    elif a != b:
        sa = json.dumps(a, ensure_ascii=False) if not isinstance(a, str) else f'"{a}"'
        sb = json.dumps(b, ensure_ascii=False) if not isinstance(b, str) else f'"{b}"'
        if len(sa) > 200:
            sa = sa[:200] + "..."
        if len(sb) > 200:
            sb = sb[:200] + "..."
        diffs.append(f"{path}: {sa} != {sb}")
    return diffs


def json_process_tool(text: str = "",
                      mode: str = "validate",
                      indent: int = 2,
                      path: str = "",
                      query: str = "",
                      sort_keys: bool = False,
                      compact: bool = False) -> str:
    """
    Process JSON data. Main entry point for the tool.

    Modes:
      validate   - Check if text is valid JSON, return type info
      format     - Pretty-print JSON with configurable indentation
      compact    - Minify JSON to single line
      extract    - Extract value at a dot/bracket path
      paths      - List all keys/paths in the JSON structure
      schema     - Infer lightweight schema from JSON data
      diff       - Compare two JSON strings (pipe-delimited text with '|||')
    """
    if len(text) > MAX_INPUT_CHARS:
        return tool_error(f"Input exceeds maximum size of {MAX_INPUT_CHARS:,} chars")

    if not text.strip():
        return tool_error("No input provided. Pass JSON text to process.")

    mode = mode.strip().lower()

    # Diff mode takes two JSON inputs separated by |||
    if mode == "diff":
        if "|||" not in text:
            return tool_error("Diff mode requires two JSON inputs separated by '|||'")
        left_text, right_text = text.split("|||", 1)
        left, err_l = _safe_load(left_text)
        if err_l:
            return tool_error(f"Left input: {err_l}")
        right, err_r = _safe_load(right_text)
        if err_r:
            return tool_error(f"Right input: {err_r}")

        diffs = _compare_json(left, right)
        if not diffs:
            return json.dumps({"mode": "diff", "equal": True}, ensure_ascii=False)
        return json.dumps({
            "mode": "diff",
            "equal": False,
            "differences": diffs[:50],
            "total": len(diffs),
            "truncated": len(diffs) > 50,
        }, ensure_ascii=False, indent=2)

    # Single-input modes
    parsed, err = _safe_load(text)
    if err:
        return json.dumps({"mode": mode, "valid": False, "error": err}, ensure_ascii=False)

    if mode == "validate":
        return json.dumps({
            "mode": "validate",
            "valid": True,
            "type": type(parsed).__name__,
            "size_chars": len(text),
        }, ensure_ascii=False)

    elif mode == "format":
        return _format_json(parsed, indent=indent, sort_keys=sort_keys)

    elif mode == "compact":
        return _compact_json(parsed)

    elif mode == "extract":
        if not path:
            return _format_json(parsed)
        value, err = _json_extract(parsed, path)
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)
        return _format_json(value)

    elif mode == "paths":
        paths = _json_keys(parsed)
        return json.dumps({
            "paths": paths,
            "total": len(paths),
        }, ensure_ascii=False, indent=2)

    elif mode == "schema":
        schema = _json_schema(parsed)
        return json.dumps(schema, ensure_ascii=False, indent=2)

    else:
        return tool_error(f"Unknown mode '{mode}'. Supported: validate, format, compact, extract, paths, schema, diff")


def check_json_requirements() -> bool:
    """No external requirements -- always available."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

JSON_SCHEMA = {
    "name": "json_process",
    "description": (
        "Process JSON data: validate, pretty-print, minify, extract paths, "
        "infer schema, or diff two JSON structures. "
        "Modes:\\n"
        "- validate: check if text is valid JSON, return type info\\n"
        "- format: pretty-print with configurable indentation\\n"
        "- compact: minify to single line\\n"
        "- extract: get value at a dot/bracket path (e.g. 'users.0.name')\\n"
        "- paths: list all keys/paths in the structure\\n"
        "- schema: infer lightweight schema (types, structure)\\n"
        "- diff: compare two JSON inputs (separate with '|||')\\n\\n"
        "Use this instead of piping through jq in terminal for simple "
        "operations -- it produces cleaner output and handles errors gracefully."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "JSON text to process. For diff mode, include two JSON texts separated by '|||'",
            },
            "mode": {
                "type": "string",
                "enum": ["validate", "format", "compact", "extract", "paths", "schema", "diff"],
                "description": "Operation to perform (default: validate)",
                "default": "validate",
            },
            "indent": {
                "type": "integer",
                "description": "Indentation spaces for format mode (default: 2)",
                "default": 2,
            },
            "path": {
                "type": "string",
                "description": "Dot/bracket path to extract (e.g. 'users.0.name', 'data[\"items\"][0]'). Used in extract mode.",
            },
            "sort_keys": {
                "type": "boolean",
                "description": "Sort object keys alphabetically in format mode",
                "default": False,
            },
        },
        "required": ["text"],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="json_process",
    toolset="json_processing",
    schema=JSON_SCHEMA,
    handler=lambda args, **kw: json_process_tool(
        text=args.get("text", ""),
        mode=args.get("mode", "validate"),
        indent=args.get("indent", 2),
        path=args.get("path", ""),
        sort_keys=args.get("sort_keys", False),
    ),
    check_fn=check_json_requirements,
    emoji="🔧",
)
