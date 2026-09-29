"""Turn a raw request body into prompt-free prefix fingerprints.

A fingerprint is enough for caching and duplicate analysis: cumulative keyed hashes of the
prompt blocks in the order the vendor builds the prompt (tools -> system -> messages),
plus cumulative character counts. The prompt text itself never leaves the client.
"""

import hashlib
import hmac
import json
import secrets
from typing import Any

HASH_HEX_CHARS = 16


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _message_blocks(message: dict) -> list[Any]:
    content = message.get("content")
    role = message.get("role", message.get("type", ""))
    if isinstance(content, list) and content:
        return [{"role": role, "part": content[0]}, *content[1:]]
    return [{k: v for k, v in message.items() if k not in ("cache_control", "prompt_cache_breakpoint")}]


def prompt_blocks(request: dict) -> list[Any]:
    """Split a Chat Completions, Responses or Anthropic Messages request into ordered blocks."""
    blocks: list[Any] = []
    if request.get("tools"):
        blocks.append({"tools": request["tools"]})
    for key in ("response_format", "text"):
        if request.get(key):
            blocks.append({key: request[key]})
    system = request.get("system", request.get("instructions"))
    if isinstance(system, list):
        blocks.extend({"system": part} for part in system)
    elif system:
        blocks.append({"system": system})
    messages = request.get("messages", request.get("input", []))
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    for message in messages:
        blocks.extend(_message_blocks(message) if isinstance(message, dict) else [message])
    return blocks


def fingerprint_request(request: dict, salt: bytes) -> dict:
    """Return cumulative prefix hashes/char counts and a full-request hash (for duplicates)."""
    running = hmac.new(salt, digestmod=hashlib.sha256)
    prefix_hashes: list[str] = []
    prefix_chars: list[int] = []
    chars = 0
    for block in prompt_blocks(request):
        text = _canonical(block)
        running.update(text.encode())
        chars += len(text)
        prefix_hashes.append(running.copy().hexdigest()[:HASH_HEX_CHARS])
        prefix_chars.append(chars)
    params = {k: v for k, v in request.items() if k not in ("stream", "metadata", "user", "store")}
    request_hash = hmac.new(salt, _canonical(params).encode(), hashlib.sha256).hexdigest()[:HASH_HEX_CHARS]
    return {"prefix_hashes": prefix_hashes, "prefix_chars": prefix_chars, "request_hash": request_hash}


def new_salt() -> bytes:
    return secrets.token_bytes(32)


def fingerprint_log_line(record: dict, salt: bytes) -> dict:
    """Replace `request` (and any response text) with its fingerprint."""
    out = {k: v for k, v in record.items() if k not in ("request", "response", "output", "choices", "content")}
    if isinstance(record.get("request"), dict):
        out["fingerprint"] = fingerprint_request(record["request"], salt)
    return out
