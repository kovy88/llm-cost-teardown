import numpy as np
import pandas as pd
import pytest
from conftest import anthropic_page, anthropic_result, openai_page, openai_result, write_json, write_jsonl

from llm_cost_teardown.usage import detect_kind, epoch_seconds, load_usage


def one_row(data):
    assert len(data.frame) == 1
    return data.frame.iloc[0]


def test_openai_input_tokens_include_cache(tmp):
    page = openai_page([openai_result(input_tokens=10_000, input_cached_tokens=6_000, output_tokens=1_000)])
    row = one_row(load_usage(write_json(tmp / "u.json", page)))
    assert row["uncached_input_tokens"] == 4_000
    assert row["cache_read_tokens"] == 6_000
    # gpt-4o: 2.50 input, 1.25 cached, 10.00 output per 1M
    assert row["cost_usd"] == pytest.approx((4_000 * 2.5 + 6_000 * 1.25 + 1_000 * 10) / 1e6)


def test_openai_uncached_field_excludes_cache_writes(tmp):
    result = openai_result(
        model="gpt-6.1-sol",
        input_tokens=10_000,
        input_cached_tokens=6_000,
        input_cache_write_tokens=1_000,
        input_uncached_tokens=3_000,
    )
    row = one_row(load_usage(write_json(tmp / "u.json", openai_page([result]))))
    assert (row["uncached_input_tokens"], row["cache_read_tokens"], row["cache_write_tokens"]) == (3_000, 6_000, 1_000)


def test_openai_batch_is_half_price(tmp):
    rows = [openai_result(input_tokens=1_000_000, batch=b, project_id=f"p{b}") for b in (False, True)]
    frame = load_usage(write_json(tmp / "u.json", openai_page(rows))).frame.set_index("service_tier")
    assert frame.loc["batch", "cost_usd"] == pytest.approx(frame.loc["standard", "cost_usd"] / 2)


def test_openai_non_completion_results_are_skipped(tmp):
    page = openai_page(
        [openai_result(input_tokens=100), {"object": "organization.usage.embeddings.result", "input_tokens": 5}]
    )
    data = load_usage(write_json(tmp / "u.json", page))
    assert len(data.frame) == 1
    assert any("embeddings" in w for w in data.warnings)


def test_anthropic_input_tokens_exclude_cache(tmp):
    result = anthropic_result(
        uncached_input_tokens=1_000,
        cache_read_input_tokens=10_000,
        cache_creation={"ephemeral_5m_input_tokens": 2_000, "ephemeral_1h_input_tokens": 1_000},
        output_tokens=500,
    )
    row = one_row(load_usage(write_json(tmp / "a.json", anthropic_page([result]))))
    # claude-sonnet-4-5: 3 input, 0.30 read, 3.75 5m write, 6 1h write, 15 output per 1M
    expected = (1_000 * 3 + 10_000 * 0.3 + 2_000 * 3.75 + 1_000 * 6 + 500 * 15) / 1e6
    assert row["cost_usd"] == pytest.approx(expected)
    assert row["workload"] == "wrkspc_a"


def test_anthropic_us_inference_geo_premium(tmp):
    rows = [
        anthropic_result(uncached_input_tokens=1_000_000, inference_geo=geo, workspace_id=geo)
        for geo in ("global", "us")
    ]
    frame = load_usage(write_json(tmp / "a.json", anthropic_page(rows))).frame.set_index("workload")
    assert frame.loc["us", "cost_usd"] == pytest.approx(frame.loc["global", "cost_usd"] * 1.1)


def test_anthropic_long_context_rows_are_flagged(tmp):
    page = anthropic_page([anthropic_result(uncached_input_tokens=300_000, context_window="200k-1M")])
    data = load_usage(write_json(tmp / "a.json", page))
    assert any("200k-1M" in w for w in data.warnings)


def test_anthropic_docs_example_response_parses(tmp):
    # Response example from the Get Messages Usage Report API reference.
    page = {
        "data": [
            {
                "ending_at": "2025-08-02T00:00:00Z",
                "results": [
                    {
                        "account_id": "user_01WCz1FkmYMm4gnmykNKUu3Q",
                        "api_key_id": "apikey_01Rj2N8SVvo6BePZj99NhmiT",
                        "cache_creation": {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0},
                        "cache_read_input_tokens": 200,
                        "context_window": "0-200k",
                        "inference_geo": "global",
                        "model": "claude-opus-5",
                        "output_tokens": 500,
                        "server_tool_use": {"web_search_requests": 10},
                        "service_account_id": "svac_01Hk3R9TWxq7CfQak00OiVw4",
                        "service_tier": "standard",
                        "uncached_input_tokens": 1500,
                        "workspace_id": "wrkspc_01JwQvzr7rXLA5AGx3HKfFUJ",
                    }
                ],
                "starting_at": "2025-08-01T00:00:00Z",
            }
        ],
        "has_more": True,
        "next_page": "page_MjAyNS0wNS0xNFQwMDowMDowMFo=",
    }
    row = one_row(load_usage(write_json(tmp / "a.json", page)))
    # claude-opus-5: 5 input, 0.50 read, 25 output per 1M; web search $10 / 1k
    assert row["cost_usd"] == pytest.approx((1_500 * 5 + 200 * 0.5 + 500 * 25) / 1e6 + 10 * 10 / 1000)


def test_cost_exports_are_parsed_into_usd(tmp):
    oa = {
        "object": "page",
        "data": [
            {
                "object": "bucket",
                "start_time": 1_788_000_000,
                "end_time": 1_788_086_400,
                "results": [{"object": "organization.costs.result", "amount": {"value": 12.5, "currency": "usd"}}],
            }
        ],
    }
    an = anthropic_page([{"amount": "12345.67", "currency": "USD", "description": "Claude Sonnet 4.5 input"}])
    usage = write_json(tmp / "u.json", openai_page([openai_result(input_tokens=1)]))
    data = load_usage([usage, write_json(tmp / "oc.json", oa), write_json(tmp / "ac.json", an)])
    by_vendor = data.invoiced.groupby("vendor")["amount_usd"].sum()
    assert by_vendor["openai"] == pytest.approx(12.5)
    assert by_vendor["anthropic"] == pytest.approx(123.4567)


def test_embeddings_are_priced_and_do_not_change_chat_levers(tmp):
    from llm_cost_teardown.analyzer import analyze

    chat = write_json(tmp / "chat.json", openai_page([openai_result(input_tokens=1_000_000, output_tokens=1_000)]))
    embed = write_json(
        tmp / "embed.json",
        openai_page(
            [
                {
                    "object": "organization.usage.embeddings.result",
                    "input_tokens": 50_000_000,
                    "num_model_requests": 1_000,
                    "model": "text-embedding-3-small",
                    "project_id": "proj_rag",
                }
            ]
        ),
    )
    costs = write_json(
        tmp / "costs.json",
        {
            "object": "page",
            "data": [
                {
                    "object": "bucket",
                    "start_time": 1_788_000_000,
                    "end_time": 1_788_086_400,
                    "results": [{"object": "organization.costs.result", "amount": {"value": 3.5, "currency": "usd"}}],
                }
            ],
        },
    )
    chat_only = analyze([chat])
    both = analyze([chat, embed, costs])
    # 50M tokens * $0.02 / 1M = $1 for the day, normalised to 30 days.
    assert both.monthly_spend == pytest.approx(chat_only.monthly_spend + 30)

    def cache_base(result):
        return next(lever for lever in result.levers if lever.key == "caching").base

    assert cache_base(both) == pytest.approx(cache_base(chat_only))
    assert both.reconciliation.iloc[0]["modelled"] == pytest.approx(both.spend["cost_usd"].sum())
    report_models = set(both.by_model["model_key"])
    assert "text-embedding-3-small" in report_models


def test_detect_kind():
    assert detect_kind([openai_page([openai_result()])]) == "openai_usage"
    assert detect_kind([anthropic_page([anthropic_result()])]) == "anthropic_usage"
    assert detect_kind([{"data": []}]) == "empty"
    embedding = openai_page(
        [{"object": "organization.usage.embeddings.result", "input_tokens": 1, "model": "text-embedding-3-small"}]
    )
    assert detect_kind([embedding]) == "openai_embeddings"


def test_request_log_sample_weight_and_long_context(tmp):
    records = [
        {
            "timestamp": "2026-09-01T10:00:00Z",
            "model": "gpt-5.4",
            "sample_rate": 0.1,
            "usage": {"prompt_tokens": 1_000, "completion_tokens": 100},
        },
        {
            "timestamp": "2026-09-01T10:01:00Z",
            "model": "gpt-5.4",
            "usage": {"prompt_tokens": 300_000, "completion_tokens": 1_000},
        },
    ]
    frame = load_usage(write_jsonl(tmp / "r.jsonl", records)).frame
    # gpt-5.4: 2.50 input / 15 output; >272K prompt: input x2, output x1.5
    assert frame.loc[0, "cost_usd"] == pytest.approx(10 * (1_000 * 2.5 + 100 * 15) / 1e6)
    assert frame.loc[1, "cost_usd"] == pytest.approx((300_000 * 2.5 * 2 + 1_000 * 15 * 1.5) / 1e6)


def test_unknown_model_is_reported_not_priced(tmp):
    page = openai_page([openai_result(model="my-finetune", input_tokens=1_000)])
    data = load_usage(write_json(tmp / "u.json", page))
    assert not data.frame["priced"].any()
    assert any("my-finetune" in w for w in data.warnings)


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_epoch_seconds_is_unit_safe(unit):
    ts = pd.Series(pd.to_datetime(["2026-09-01T00:00:00Z", "2026-09-01T00:10:00Z"], utc=True)).dt.as_unit(unit)
    assert np.diff(epoch_seconds(ts))[0] == pytest.approx(600)


def test_monthly_factor_normalises_period(tmp):
    page = openai_page([openai_result(input_tokens=1_000)], width=86_400)
    assert one_row(load_usage(write_json(tmp / "u.json", page)))["monthly_factor"] == pytest.approx(30)
