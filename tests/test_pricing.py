from datetime import timedelta

import pytest

from llm_cost_teardown import pricing


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("gpt-4o-2024-08-06", "gpt-4o"),
        ("gpt-5.4-2026-03-05", "gpt-5.4"),
        ("gpt-6-astra", "gpt-6-astra"),
        ("gpt-5.6", "gpt-5.6-sol"),
        ("claude-sonnet-4-5-20250929", "claude-sonnet-4-5"),
        ("claude-3-5-haiku-20241022", "claude-haiku-3-5"),
        ("claude-opus-4-20250514", "claude-opus-4"),
        ("anthropic.claude-sonnet-4-5-20250929-v1:0", "claude-sonnet-4-5"),
        ("claude-haiku-4-5@20251001", "claude-haiku-4-5"),
        ("openai/gpt-4.1-mini", "gpt-4.1-mini"),
        ("Claude-Opus-5-5", "claude-opus-5-5"),
    ],
)
def test_normalize_model(raw, key):
    assert pricing.normalize_model(raw) == key
    assert key in pricing.PRICES


def test_verified_on_is_set_and_fresh_rule():
    assert pricing.VERIFIED_ON is not None
    assert not pricing.is_stale(pricing.VERIFIED_ON + timedelta(days=pricing.MAX_AGE_DAYS))
    assert pricing.is_stale(pricing.VERIFIED_ON + timedelta(days=pricing.MAX_AGE_DAYS + 1))


@pytest.mark.parametrize("key", sorted(pricing.PRICES))
def test_price_table_is_consistent(key):
    p = pricing.PRICES[key]
    assert p.vendor in ("openai", "anthropic")
    assert p.tokenizer in pricing.TOKENIZER_SCALE
    for ref in (p.successor, p.cheaper_tier):
        assert ref is None or ref in pricing.PRICES
    if p.successor:
        assert pricing.PRICES[p.successor].vendor == p.vendor
    if p.output == 0:
        assert p.input > 0
        assert p.cached_input == p.input
        assert p.batch_multiplier == 1.0
        return
    assert 0 < p.cached_input < p.input < p.output
    assert p.cache_write >= p.input


def test_successor_chains_terminate():
    for key in pricing.PRICES:
        final = pricing.latest_successor(key)
        assert pricing.PRICES[final].successor is None


def test_tokenizer_ratio():
    assert pricing.token_ratio("claude-sonnet-4-5", "claude-sonnet-5-5") == pytest.approx(1.3)
    assert pricing.token_ratio("claude-sonnet-5-5", "claude-haiku-4-5") == pytest.approx(1 / 1.3)
    assert pricing.token_ratio("gpt-4o", "gpt-6.1-sol") == 1.0


def test_spot_prices_from_vendor_pages():
    assert pricing.PRICES["claude-opus-4-1"].input == 15.0
    assert pricing.PRICES["claude-opus-5-5"].cached_input == 0.20
    assert pricing.PRICES["claude-sonnet-4-5"].cache_write_1h == 6.0
    assert pricing.PRICES["gpt-6.1-sol"].cache_write == 2.50
    assert pricing.PRICES["gpt-4o"].cache_write == pricing.PRICES["gpt-4o"].input
    assert pricing.PRICES["claude-haiku-4-5"].min_cacheable_tokens == 4096
    assert pricing.PRICES["text-embedding-3-small"].input == 0.02
    assert pricing.PRICES["text-embedding-3-large"].input == 0.13
    assert pricing.PRICES["text-embedding-ada-002"].input == 0.10
