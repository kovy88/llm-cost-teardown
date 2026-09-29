import json
from pathlib import Path

import pytest


def write_json(path: Path, obj) -> Path:
    path.write_text(json.dumps(obj))
    return path


def write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def openai_page(results: list[dict], start: int = 1_788_000_000, width: int = 86_400) -> dict:
    return {
        "object": "page",
        "data": [{"object": "bucket", "start_time": start, "end_time": start + width, "results": results}],
        "has_more": False,
        "next_page": None,
    }


def openai_result(**kw) -> dict:
    base = {
        "object": "organization.usage.completions.result",
        "input_tokens": 0,
        "output_tokens": 0,
        "num_model_requests": 1,
        "model": "gpt-4o-2024-08-06",
        "batch": False,
        "service_tier": "default",
    }
    return base | kw


def anthropic_page(results: list[dict], start: str = "2026-09-01T00:00:00Z", end: str = "2026-09-02T00:00:00Z"):
    return {"data": [{"starting_at": start, "ending_at": end, "results": results}], "has_more": False}


def anthropic_result(**kw) -> dict:
    base = {
        "uncached_input_tokens": 0,
        "cache_creation": {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0},
        "cache_read_input_tokens": 0,
        "output_tokens": 0,
        "server_tool_use": {"web_search_requests": 0},
        "model": "claude-sonnet-4-5-20250929",
        "service_tier": "standard",
        "workspace_id": "wrkspc_a",
    }
    return base | kw


@pytest.fixture
def tmp(tmp_path: Path) -> Path:
    return tmp_path
