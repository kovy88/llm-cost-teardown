from datetime import UTC, datetime, timedelta

import pytest
from conftest import anthropic_page, anthropic_result, openai_page, openai_result, write_json, write_jsonl

from llm_cost_teardown import pricing
from llm_cost_teardown.estimators import (
    Context,
    Lever,
    _simulate_cache,
    _stable_prefix_chars,
    combine,
    lever_batch,
    lever_caching,
    lever_duplicates,
    lever_migration,
)
from llm_cost_teardown.usage import load_usage

T0 = datetime(2026, 9, 1, 9, tzinfo=UTC)
SYSTEM = "Policy text. " * 1500  # ~19.5k characters of static instructions


def request_log(tmp, model, n, *, every_s=60, prompt_tokens=6_000, question=lambda i: f"question {i}", vendor=None):
    records = []
    for i in range(n):
        usage = (
            {"input_tokens": prompt_tokens, "output_tokens": 200}
            if model.startswith("claude")
            else {"prompt_tokens": prompt_tokens, "completion_tokens": 200}
        )
        records.append(
            {
                "timestamp": (T0 + timedelta(seconds=i * every_s)).isoformat(),
                "model": model,
                "workload": "chat",
                "usage": usage,
                "request": {"system": SYSTEM, "messages": [{"role": "user", "content": question(i)}]},
            }
        )
    return load_usage(write_jsonl(tmp / f"{model}.jsonl", records)).frame


def simulate(frame, ttl=None, write=None):
    price = pricing.PRICES[frame["model_key"].iloc[0]]
    return _simulate_cache(frame, price, ttl or price.cache_ttl_seconds, write or price.cache_write)


def test_stable_prefix_is_the_shared_system_block(tmp):
    frame = request_log(tmp, "claude-sonnet-4-5", 20)
    chars = _stable_prefix_chars(frame)
    assert chars is not None
    assert chars > 1_000


def test_cache_simulation_hits_on_shared_prefix(tmp):
    frame = request_log(tmp, "claude-sonnet-4-5", 20)
    simulated = simulate(frame)
    current = frame["cost_input"].to_numpy()
    assert simulated[0] > current[0]  # the first call pays the cache-write premium
    assert (simulated[1:] < current[1:] * 0.2).all()  # later calls read ~all of the prompt from cache
    assert simulated.sum() < current.sum() * 0.25


def test_cache_simulation_respects_minimum_prefix(tmp):
    frame = request_log(tmp, "claude-haiku-4-5", 10, prompt_tokens=3_000)  # below the 4096-token minimum
    assert simulate(frame).sum() == pytest.approx(frame["cost_input"].sum())


def test_cache_simulation_respects_ttl(tmp):
    frame = request_log(tmp, "claude-sonnet-4-5", 10, every_s=600)
    assert simulate(frame).sum() == pytest.approx(frame["cost_input"].sum())
    price = pricing.PRICES["claude-sonnet-4-5"]
    assert simulate(frame, ttl=pricing.HOUR, write=price.cache_write_1h).sum() < frame["cost_input"].sum() * 0.5


def test_caching_lever_is_measured_from_logs(tmp):
    frame = request_log(tmp, "claude-sonnet-4-5", 30)
    lever = lever_caching(Context(spend=frame, requests=frame))
    assert lever.method == "measured"
    assert 0 < lever.low < lever.base <= lever.high < frame["cost_usd"].sum() * frame["monthly_factor"].iloc[0]


def test_duplicates_lever_counts_exact_repeats(tmp):
    frame = request_log(tmp, "gpt-4o", 10, question=lambda i: "same question")
    lever = lever_duplicates(Context(spend=frame, requests=frame))
    monthly = (frame["cost_usd"] * frame["monthly_factor"]).sum()
    assert lever.method == "measured"
    assert lever.high == pytest.approx(monthly * 0.9)  # 9 of 10 calls repeat the first one


def test_duplicates_lever_needs_logs(tmp):
    data = load_usage(write_json(tmp / "u.json", openai_page([openai_result(input_tokens=1_000)])))
    lever = lever_duplicates(Context(spend=data.frame, requests=data.requests))
    assert lever.method == "not measured" and lever.high == 0


def test_migration_accounts_for_new_tokenizer(tmp):
    page = anthropic_page([anthropic_result(model="claude-opus-4-1-20250805", uncached_input_tokens=1_000_000)])
    frame = load_usage(write_json(tmp / "a.json", page)).frame
    lever = lever_migration(Context(spend=frame, requests=frame.iloc[0:0]))
    # opus-4-1 $15/M (legacy tokenizer) -> opus-5-5 $4/M on 1.3x as many tokens, 30x monthly factor
    assert lever.base == pytest.approx(30 * (15 - 1.3 * 4))
    assert lever.method == "exact"


def hourly_openai(hours: list[int], project: str) -> dict:
    pages = []
    for day in range(3):
        for h in hours:
            start = int((T0.replace(hour=0) + timedelta(days=day, hours=h)).timestamp())
            pages.append(
                openai_page([openai_result(input_tokens=100_000, project_id=project)], start=start, width=3600)
            )
    return {"object": "page", "data": [b for p in pages for b in p["data"]], "has_more": False}


def test_batch_detects_scheduled_workloads_from_hourly_buckets(tmp):
    nightly = write_json(tmp / "n.json", hourly_openai([2], "proj_nightly"))
    chat = write_json(tmp / "c.json", hourly_openai(list(range(24)), "proj_chat"))
    data = load_usage([nightly, chat])
    lever = lever_batch(Context(spend=data.frame, requests=data.requests))
    assert [row["workload"] for row in lever.table] == ["proj_nightly"]
    assert any("proj_chat" in e for e in lever.evidence)  # listed as a what-if, not counted


def test_batchable_override_is_exact(tmp):
    data = load_usage(write_json(tmp / "c.json", hourly_openai(list(range(24)), "proj_chat")))
    lever = lever_batch(Context(spend=data.frame, requests=data.requests, batchable=frozenset({"proj_chat"})))
    monthly = (data.frame["cost_usd"] * data.frame["monthly_factor"]).sum()
    assert lever.method == "exact"
    assert lever.base == pytest.approx(monthly * 0.5)


def test_combine_stacks_multiplicatively():
    levers = [Lever("a", "a", 50, 50, 50), Lever("b", "b", 50, 50, 50)]
    assert combine(levers, 100)["base"] == pytest.approx(75)
    assert combine([Lever("a", "a", 500, 500, 500)], 100)["high"] == pytest.approx(100)
    assert combine(levers, 0)["base"] == 0
