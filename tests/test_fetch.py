import io
import json
import urllib.parse

import pytest

from llm_cost_teardown import fetch


@pytest.fixture
def calls(monkeypatch):
    seen: list[tuple[str, dict, dict]] = []

    def fake_urlopen(req, timeout):
        url = urllib.parse.urlsplit(req.full_url)
        query = urllib.parse.parse_qs(url.query)
        seen.append((url.path, query, dict(req.header_items())))
        more = "page" not in query
        body = {"data": [], "has_more": more, "next_page": "cursor-2" if more else None}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    return seen


def test_openai_fetch_paginates_with_admin_key(calls, monkeypatch):
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "sk-admin-test")
    exports = fetch.fetch_openai(days=30)
    assert set(exports) == {"openai_usage.json", "openai_embeddings.json", "openai_costs.json"}
    assert all(len(pages) == 2 for pages in exports.values())
    path, query, headers = calls[0]
    assert path == "/v1/organization/usage/completions"
    assert query["group_by[]"] == ["model", "project_id", "batch", "service_tier"]
    assert query["bucket_width"] == ["1h"]
    assert headers["Authorization"] == "Bearer sk-admin-test"
    assert calls[1][1]["page"] == ["cursor-2"]
    assert calls[2][0] == "/v1/organization/usage/embeddings"
    assert calls[2][1]["group_by[]"] == ["model", "project_id"]
    assert "batch" not in calls[2][1]
    assert calls[4][0] == "/v1/organization/costs"


def test_anthropic_fetch_uses_admin_headers(calls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_ADMIN_KEY", "sk-ant-admin-test")
    exports = fetch.fetch_anthropic(days=7)
    assert set(exports) == {"anthropic_usage.json", "anthropic_costs.json"}
    path, query, headers = calls[0]
    assert path == "/v1/organizations/usage_report/messages"
    assert "inference_geo" in query["group_by[]"]
    assert int(query["limit"][0]) <= 168
    assert headers["X-api-key"] == "sk-ant-admin-test"
    assert headers["Anthropic-version"] == "2023-06-01"
    assert calls[2][0] == "/v1/organizations/cost_report"
