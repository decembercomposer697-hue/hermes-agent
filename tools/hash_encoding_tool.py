#!/usr/bin/env python3
"""
Hash & Encoding Utility Tool

Provides common hashing, encoding, and text transformation operations:
- MD5, SHA-1, SHA-256, SHA-512 hashing
- Base64 encode/decode
- Hex encode/decode
- URL encode/decode
- Character/word/line counting
- String case transformations

No external dependencies beyond stdlib (hashlib, base64, urllib).
"""

import base64
import hashlib
import json
import urllib.parse


MAX_INPUT_CHARS = 500_000


def tool_error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def _compute_hash(text: str, algorithm: str, encoding: str = "utf-8") -> str:
    """Compute hash of text using the given algorithm."""
    data = text.encode(encoding)
    h = hashlib.new(algorithm, data)
    return h.hexdigest()


def hash_tool(
    text: str = "",
    mode: str = "sha256",
    encoding: str = "utf-8",
    format: str = "hex",
) -> str:
    """
    Hash, encode, or transform text.

    Modes:
      hash algorithms: md5, sha1, sha256, sha512
      encode types:    base64_encode, base64_decode, hex_encode, hex_decode,
                       url_encode, url_decode
      stats:           character/word/line count
      case:            upper, lower, capitalize, title, swapcase
    """
    if not text:
        return tool_error("No input text provided.")

    if len(text) > MAX_INPUT_CHARS:
        return tool_error(f"Input exceeds maximum size of {MAX_INPUT_CHARS:,} chars")

    mode = mode.strip().lower()
    result = ""

    try:
        # --- Hash modes ---
        if mode in ("md5", "sha1", "sha256", "sha512"):
            digest = _compute_hash(text, mode, encoding)
            result = digest

        # --- Base64 ---
        elif mode == "base64_encode":
            result = base64.b64encode(text.encode(encoding)).decode("ascii")

        elif mode == "base64_decode":
            try:
                decoded = base64.b64decode(text)
                result = decoded.decode(encoding)
            except Exception:
                # Maybe it's base64url?
                decoded = base64.urlsafe_b64decode(text + "==")
                result = decoded.decode(encoding)

        # --- Hex ---
        elif mode == "hex_encode":
            result = text.encode(encoding).hex()

        elif mode == "hex_decode":
            try:
                result = bytes.fromhex(text).decode(encoding)
            except ValueError as e:
                return tool_error(f"Hex decode error: {e}")

        # --- URL ---
        elif mode == "url_encode":
            result = urllib.parse.quote(text, safe="")

        elif mode == "url_decode":
            result = urllib.parse.unquote(text)

        # --- Stats ---
        elif mode == "stats":
            lines = text.split("\n")
            words = text.split()
            chars = len(text)
            non_space_chars = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
            result = json.dumps({
                "characters": chars,
                "non_space_characters": non_space_chars,
                "words": len(words),
                "lines": len(lines),
                "max_line_length": max(len(l) for l in lines) if lines else 0,
            }, indent=2, ensure_ascii=False)

        # --- Case transformations ---
        elif mode == "upper":
            result = text.upper()
        elif mode == "lower":
            result = text.lower()
        elif mode == "capitalize":
            result = text.capitalize()
        elif mode == "title":
            result = text.title()
        elif mode == "swapcase":
            result = text.swapcase()

        else:
            return tool_error(
                f"Unknown mode '{mode}'. Supported modes: md5, sha1, sha256, sha512, "
                "base64_encode, base64_decode, hex_encode, hex_decode, "
                "url_encode, url_decode, stats, upper, lower, capitalize, title, swapcase"
            )

    except Exception as e:
        return tool_error(f"{mode} failed: {e}")

    return json.dumps({
        "mode": mode,
        "result": result,
        "result_length": len(result),
    }, ensure_ascii=False)


def check_hash_requirements() -> bool:
    """No external requirements -- always available."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

HASH_SCHEMA = {
    "name": "hash_encode",
    "description": (
        "Hash, encode, decode, or transform text. "
        "Use this instead of piping through openssl/shasum/base64 in terminal.\\n\\n"
        "Modes:\\n"
        "- md5, sha1, sha256, sha512: compute hash digest\\n"
        "- base64_encode, base64_decode: Base64 encoding\\n"
        "- hex_encode, hex_decode: hex string conversion\\n"
        "- url_encode, url_decode: URL percent-encoding\\n"
        "- stats: count chars, words, lines\\n"
        "- upper, lower, capitalize, title, swapcase: case transforms\\n\\n"
        "Example: hash_encode(text='hello world', mode='sha256')"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to hash, encode, decode, or transform",
            },
            "mode": {
                "type": "string",
                "enum": [
                    "md5", "sha1", "sha256", "sha512",
                    "base64_encode", "base64_decode",
                    "hex_encode", "hex_decode",
                    "url_encode", "url_decode",
                    "stats", "upper", "lower", "capitalize", "title", "swapcase",
                ],
                "description": "Operation to perform (default: sha256)",
                "default": "sha256",
            },
            "encoding": {
                "type": "string",
                "description": "Text encoding for hash/encode operations (default: utf-8)",
                "default": "utf-8",
            },
        },
        "required": ["text"],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="hash_encode",
    toolset="hash_encoding",
    schema=HASH_SCHEMA,
    handler=lambda args, **kw: hash_tool(
        text=args.get("text", ""),
        mode=args.get("mode", "sha256"),
        encoding=args.get("encoding", "utf-8"),
    ),
    check_fn=check_hash_requirements,
    emoji="🔐",
)
