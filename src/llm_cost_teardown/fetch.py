"""Export usage and cost data from the vendors' Admin APIs (read-only, stdlib only).

Endpoints, parameters and pagination match the `openai` SDK (`admin.organization.usage`)
and the Anthropic Usage & Cost Admin API reference.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

USER_AGENT = "llm-cost-teardown/0.1 (read-only usage export)"
HOUR_BUCKETS_PER_PAGE = 168
DAY_BUCKETS_PER_PAGE = 31


def _get(url: str, params: list[tuple[str, str]], headers: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", headers={**headers, "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _paginate(url: str, params: list[tuple[str, str]], headers: dict[str, str]) -> list[dict]:
    pages, cursor = [], None
    while True:
        page = _get(url, params + ([("page", cursor)] if cursor else []), headers)
        pages.append(page)
        cursor = page.get("next_page")
        if not page.get("has_more") or not cursor:
            return pages
        time.sleep(0.5)


def _window(days: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    return end - timedelta(days=days), end


def fetch_openai(days: int = 30, api_key: str | None = None) -> dict[str, list[dict]]:
    key = api_key or os.environ["OPENAI_ADMIN_KEY"]
    headers = {"Authorization": f"Bearer {key}"}
    start, end = _window(days)
    base = "https://api.openai.com/v1/organization"
    window = [("start_time", str(int(start.timestamp()))), ("end_time", str(int(end.timestamp())))]
    usage = _paginate(
        f"{base}/usage/completions",
        window
        + [("bucket_width", "1h"), ("limit", str(HOUR_BUCKETS_PER_PAGE))]
        + [("group_by[]", g) for g in ("model", "project_id", "batch", "service_tier")],
        headers,
    )
    costs = _paginate(
        f"{base}/costs",
        window + [("bucket_width", "1d"), ("limit", "180")] + [("group_by[]", g) for g in ("line_item", "project_id")],
        headers,
    )
    return {"openai_usage.json": usage, "openai_costs.json": costs}


def fetch_anthropic(days: int = 30, api_key: str | None = None) -> dict[str, list[dict]]:
    key = api_key or os.environ["ANTHROPIC_ADMIN_KEY"]
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    start, end = _window(days)
    base = "https://api.anthropic.com/v1/organizations"
    window = [
        ("starting_at", start.strftime("%Y-%m-%dT%H:%M:%SZ")),
        ("ending_at", end.strftime("%Y-%m-%dT%H:%M:%SZ")),
    ]
    usage = _paginate(
        f"{base}/usage_report/messages",
        window
        + [("bucket_width", "1h"), ("limit", str(HOUR_BUCKETS_PER_PAGE))]
        + [
            ("group_by[]", g)
            for g in ("model", "workspace_id", "api_key_id", "service_tier", "context_window", "inference_geo")
        ],
        headers,
    )
    costs = _paginate(
        f"{base}/cost_report",
        window + [("limit", str(DAY_BUCKETS_PER_PAGE))] + [("group_by[]", g) for g in ("workspace_id", "description")],
        headers,
    )
    return {"anthropic_usage.json": usage, "anthropic_costs.json": costs}
