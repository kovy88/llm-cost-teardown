"""Model price table (USD per 1M tokens) and prompt-caching rules.

Every number here was read from the vendor pages in SOURCES on VERIFIED_ON.
Do not ship a client report while VERIFIED_ON is older than MAX_AGE_DAYS (see `is_stale`).
Never hardcode prices anywhere else in the codebase.
"""

import re
from dataclasses import dataclass
from datetime import date

VERIFIED_ON = date(2026, 9, 29)
MAX_AGE_DAYS = 30

SOURCES = {
    "openai": [
        "https://developers.openai.com/api/docs/pricing",
        "https://developers.openai.com/api/docs/models/<model-id>",
        "https://developers.openai.com/api/docs/guides/prompt-caching",
    ],
    "anthropic": [
        "https://docs.claude.com/en/docs/about-claude/pricing",
        "https://docs.claude.com/en/docs/about-claude/models/overview",
        "https://docs.claude.com/en/docs/build-with-claude/prompt-caching",
    ],
}

# Claude 4.7+ tokenizer produces ~30 % more tokens for the same text than Sonnet 4.6 and earlier
# (Anthropic pricing page). Used when repricing traffic on a different model.
TOKENIZER_SCALE = {"openai": 1.0, "claude-legacy": 1.0, "claude-2026": 1.3}

WEB_SEARCH_USD_PER_1K = 10.0
ANTHROPIC_US_GEO_MULTIPLIER = 1.1

MIN_30 = 30 * 60
MIN_5 = 5 * 60
HOUR = 60 * 60


@dataclass(frozen=True)
class ModelPrice:
    vendor: str
    input: float
    cached_input: float
    cache_write: float
    output: float
    tokenizer: str
    # Anthropic 1-hour cache writes; OpenAI has a single write price.
    cache_write_1h: float | None = None
    batch_multiplier: float = 0.5
    # Fast / priority mode multiplier; None = not verified, priced at standard with a warning.
    fast_multiplier: float | None = None
    # Whole request is repriced when input tokens exceed the threshold.
    long_context_threshold: int | None = None
    long_context_input_multiplier: float = 1.0
    long_context_output_multiplier: float = 1.0
    min_cacheable_tokens: int = 1024
    cache_ttl_seconds: int = MIN_5
    # Same-tier model that replaces this one (migration lever). Validate with the eval set.
    successor: str | None = None
    # Next cheaper tier for routing simple traffic. Validate with the eval set.
    cheaper_tier: str | None = None
    notes: str = ""


def _embedding(inp: float) -> ModelPrice:
    """Input-only embedding price. Model cards read 2026-09-30 show the Batch API price equal to standard."""
    return ModelPrice(
        "openai",
        inp,
        inp,
        inp,
        0.0,
        tokenizer="openai",
        batch_multiplier=1.0,
        min_cacheable_tokens=10**12,
        notes="Input only. No batch discount: the model card lists the same Batch API price.",
    )


def _openai_legacy(inp: float, cached: float, out: float, **kw) -> ModelPrice:
    """OpenAI models before GPT-5.6: no cache-write surcharge."""
    return ModelPrice("openai", inp, cached, inp, out, tokenizer="openai", **kw)


def _openai_2026(inp: float, cached: float, out: float, **kw) -> ModelPrice:
    """GPT-5.6 and later: cache writes 1.25x, 1,024-token minimum, >=30 min cache lifetime."""
    kw.setdefault("long_context_threshold", 272_000)
    kw.setdefault("long_context_input_multiplier", 2.0)
    kw.setdefault("long_context_output_multiplier", 1.5)
    kw.setdefault("cache_ttl_seconds", MIN_30)
    return ModelPrice("openai", inp, cached, inp * 1.25, out, tokenizer="openai", **kw)


def _claude(
    inp: float, cached: float, out: float, *, min_cache: int, tokenizer: str = "claude-2026", **kw
) -> ModelPrice:
    """Claude: 5m write 1.25x, 1h write 2x, batch 50 %."""
    return ModelPrice(
        "anthropic",
        inp,
        cached,
        inp * 1.25,
        out,
        tokenizer=tokenizer,
        cache_write_1h=inp * 2,
        min_cacheable_tokens=min_cache,
        cache_ttl_seconds=MIN_5,
        **kw,
    )


_LONG_272K = {
    "long_context_threshold": 272_000,
    "long_context_input_multiplier": 2.0,
    "long_context_output_multiplier": 1.5,
}

PRICES: dict[str, ModelPrice] = {
    # --- OpenAI, GPT-6 family (pricing page, "Flagship models" table) ---
    "gpt-6-astra": _openai_2026(10.00, 1.00, 50.00, fast_multiplier=2.0, cheaper_tier="gpt-6.1-sol"),
    "gpt-6.1-sol": _openai_2026(2.00, 0.10, 10.00, fast_multiplier=2.0, cheaper_tier="gpt-6-luna"),
    "gpt-6-luna": _openai_2026(0.10, 0.01, 0.50, fast_multiplier=2.0),
    # --- OpenAI, GPT-5.6 family (model pages) ---
    "gpt-5.6-sol": _openai_2026(
        4.00, 0.40, 20.00, successor="gpt-6.1-sol", notes="Promotional price through >= 2026-11-21"
    ),
    "gpt-5.6-terra": _openai_2026(2.00, 0.20, 12.00, successor="gpt-6.1-sol"),
    "gpt-5.6-luna": _openai_2026(0.20, 0.02, 1.20, successor="gpt-6-luna"),
    # --- OpenAI, earlier GPT-5.x (model pages) ---
    "gpt-5.5": _openai_legacy(5.00, 0.50, 30.00, cache_ttl_seconds=MIN_30, successor="gpt-6.1-sol", **_LONG_272K),
    "gpt-5.4": _openai_legacy(2.50, 0.25, 15.00, cache_ttl_seconds=MIN_30, successor="gpt-6.1-sol", **_LONG_272K),
    "gpt-5.4-mini": _openai_legacy(0.75, 0.075, 4.50, successor="gpt-6-luna"),
    "gpt-5.4-nano": _openai_legacy(0.20, 0.02, 1.25, successor="gpt-6-luna"),
    "gpt-5.2": _openai_legacy(1.75, 0.175, 14.00, cache_ttl_seconds=MIN_30, successor="gpt-6.1-sol"),
    "gpt-5.1": _openai_legacy(1.25, 0.125, 10.00, cache_ttl_seconds=MIN_30, successor="gpt-6.1-sol"),
    "gpt-5": _openai_legacy(1.25, 0.125, 10.00, cache_ttl_seconds=MIN_30, successor="gpt-6.1-sol"),
    "gpt-5-mini": _openai_legacy(0.25, 0.025, 2.00, successor="gpt-6-luna"),
    "gpt-5-nano": _openai_legacy(0.05, 0.005, 0.40, successor="gpt-6-luna"),
    # --- OpenAI, GPT-4.x and o-series (model pages) ---
    "gpt-4.1": _openai_legacy(2.00, 0.50, 8.00, cache_ttl_seconds=MIN_30, successor="gpt-6.1-sol"),
    "gpt-4.1-mini": _openai_legacy(0.40, 0.10, 1.60, successor="gpt-6-luna"),
    "gpt-4.1-nano": _openai_legacy(0.10, 0.025, 0.40, successor="gpt-6-luna"),
    "gpt-4o": _openai_legacy(2.50, 1.25, 10.00, successor="gpt-6.1-sol"),
    "gpt-4o-mini": _openai_legacy(0.15, 0.075, 0.60, successor="gpt-6-luna"),
    "o3": _openai_legacy(2.00, 0.50, 8.00, successor="gpt-6.1-sol"),
    "o4-mini": _openai_legacy(1.10, 0.275, 4.40, successor="gpt-6-luna"),
    # --- Anthropic (pricing page "Model pricing"; minimums from prompt-caching page) ---
    "claude-fable-5-1": _claude(10.00, 0.25, 50.00, min_cache=512, cheaper_tier="claude-opus-5-5"),
    "claude-mythos-5-1": _claude(10.00, 0.25, 50.00, min_cache=512, notes="Limited availability"),
    "claude-fable-5": _claude(10.00, 1.00, 50.00, min_cache=512, successor="claude-fable-5-1"),
    "claude-mythos-5": _claude(10.00, 1.00, 50.00, min_cache=512, notes="Limited availability"),
    "claude-opus-5-5": _claude(4.00, 0.20, 20.00, min_cache=512, fast_multiplier=2.0, cheaper_tier="claude-sonnet-5-5"),
    "claude-opus-5": _claude(5.00, 0.50, 25.00, min_cache=512, fast_multiplier=2.0, successor="claude-opus-5-5"),
    "claude-opus-4-8": _claude(5.00, 0.50, 25.00, min_cache=1024, fast_multiplier=2.0, successor="claude-opus-5-5"),
    "claude-opus-4-7": _claude(5.00, 0.50, 25.00, min_cache=2048, successor="claude-opus-5-5"),
    "claude-opus-4-6": _claude(
        5.00, 0.50, 25.00, min_cache=4096, tokenizer="claude-legacy", successor="claude-opus-5-5"
    ),
    "claude-opus-4-5": _claude(
        5.00, 0.50, 25.00, min_cache=4096, tokenizer="claude-legacy", successor="claude-opus-5-5"
    ),
    "claude-opus-4-1": _claude(
        15.00, 1.50, 75.00, min_cache=1024, tokenizer="claude-legacy", successor="claude-opus-5-5", notes="Retired"
    ),
    "claude-opus-4": _claude(
        15.00, 1.50, 75.00, min_cache=1024, tokenizer="claude-legacy", successor="claude-opus-5-5", notes="Retired"
    ),
    "claude-sonnet-5-5": _claude(2.00, 0.20, 10.00, min_cache=512, cheaper_tier="claude-haiku-4-5"),
    "claude-sonnet-5": _claude(2.00, 0.20, 10.00, min_cache=1024, successor="claude-sonnet-5-5"),
    "claude-sonnet-4-6": _claude(
        3.00, 0.30, 15.00, min_cache=1024, tokenizer="claude-legacy", successor="claude-sonnet-5-5"
    ),
    "claude-sonnet-4-5": _claude(
        3.00, 0.30, 15.00, min_cache=1024, tokenizer="claude-legacy", successor="claude-sonnet-5-5"
    ),
    "claude-sonnet-4": _claude(
        3.00, 0.30, 15.00, min_cache=1024, tokenizer="claude-legacy", successor="claude-sonnet-5-5", notes="Retired"
    ),
    "claude-haiku-4-5": _claude(1.00, 0.10, 5.00, min_cache=4096, tokenizer="claude-legacy"),
    "claude-haiku-3-5": _claude(
        0.80, 0.08, 4.00, min_cache=2048, tokenizer="claude-legacy", successor="claude-haiku-4-5", notes="Retired"
    ),
    # --- OpenAI embeddings (model cards, 2026-09-30). Input only. ---
    "text-embedding-3-small": _embedding(0.02),
    "text-embedding-3-large": _embedding(0.13),
    "text-embedding-ada-002": _embedding(0.10),
}

ALIASES = {
    "gpt-5.6": "gpt-5.6-sol",
    "claude-3-5-haiku": "claude-haiku-3-5",
    "claude-opus-4-0": "claude-opus-4",
    "claude-sonnet-4-0": "claude-sonnet-4",
}

_SNAPSHOT_SUFFIX = re.compile(r"(-\d{4}-\d{2}-\d{2}|-\d{8}|@\d{8}|-v\d+(:\d+)?)$")
_VENDOR_PREFIX = re.compile(r"^(openai|anthropic|us\.anthropic|eu\.anthropic|global\.anthropic)[./]")


def normalize_model(model: str) -> str:
    """Map a raw model string (snapshot, Bedrock/Vertex/gateway id) to a PRICES key."""
    key = _VENDOR_PREFIX.sub("", model.strip().lower())
    while True:
        stripped = _SNAPSHOT_SUFFIX.sub("", key)
        if stripped == key:
            break
        key = stripped
    return ALIASES.get(key, key)


def get_price(model: str) -> ModelPrice | None:
    return PRICES.get(normalize_model(model))


def token_ratio(from_model: str, to_model: str) -> float:
    """How many tokens the same text costs on `to_model` per token on `from_model`."""
    src, dst = get_price(from_model), get_price(to_model)
    if src is None or dst is None:
        return 1.0
    return TOKENIZER_SCALE[dst.tokenizer] / TOKENIZER_SCALE[src.tokenizer]


def latest_successor(model: str) -> str:
    """Follow the successor chain to the current model of the same tier."""
    key = normalize_model(model)
    seen = {key}
    while (price := PRICES.get(key)) and price.successor and price.successor not in seen:
        key = price.successor
        seen.add(key)
    return key


def age_days(today: date | None = None) -> int:
    return ((today or date.today()) - VERIFIED_ON).days


def is_stale(today: date | None = None) -> bool:
    return age_days(today) > MAX_AGE_DAYS
