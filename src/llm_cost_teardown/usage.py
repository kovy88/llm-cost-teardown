"""Load vendor usage exports into one normalised frame and price it.

Field names are verified against:
- OpenAI: `openai` SDK types `admin.organization.UsageCompletionsResponse` / `UsageCostsResponse`,
  `CompletionUsage` (Chat Completions) and `responses.ResponseUsage`.
- Anthropic: `anthropic` SDK `types.Usage`; Usage & Cost Admin API reference + the official
  claude-cookbooks `observability/usage_cost_api.ipynb` (the Python SDK has no admin usage types).
See docs/data-formats.md for the full mapping.

Token semantics differ per vendor:
- OpenAI `input_tokens` / `prompt_tokens` INCLUDE cached and cache-write tokens.
- Anthropic `input_tokens` / `uncached_input_tokens` EXCLUDE cache reads and cache writes.
"""

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from llm_cost_teardown import pricing

TOKEN_COLUMNS = [
    "uncached_input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "cache_write_1h_tokens",
    "output_tokens",
]
COLUMNS = [
    "timestamp",
    "bucket_seconds",
    "granularity",
    "vendor",
    "model",
    "model_key",
    "workload",
    "product",
    "service_tier",
    "inference_geo",
    "requests",
    *TOKEN_COLUMNS,
    "reasoning_tokens",
    "web_search_requests",
    "weight",
    "request_hash",
    "prefix_hashes",
    "prefix_chars",
    "status",
    "source",
]


@dataclass
class UsageData:
    frame: pd.DataFrame
    invoiced: pd.DataFrame | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def requests(self) -> pd.DataFrame:
        return self.frame[self.frame["granularity"] == "request"]

    @property
    def buckets(self) -> pd.DataFrame:
        return self.frame[self.frame["granularity"] == "bucket"]


def _int(value) -> int:
    return int(value or 0)


def _ts(value) -> datetime:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _openai_tier(batch, tier) -> str:
    if batch:
        return "batch"
    tier = (tier or "standard").lower()
    return {"default": "standard", "auto": "standard", "priority": "fast"}.get(tier, tier)


def _anthropic_tier(tier, speed=None) -> str:
    if (speed or "").lower() == "fast":
        return "fast"
    tier = (tier or "standard").lower()
    return {"priority_on_demand": "priority", "flex_discount": "flex"}.get(tier, tier)


def _row(**kw) -> dict:
    row = dict.fromkeys(COLUMNS)
    row.update(
        {c: 0 for c in TOKEN_COLUMNS},
        reasoning_tokens=0,
        web_search_requests=0,
        weight=1.0,
        requests=np.nan,
        bucket_seconds=0,
        service_tier="standard",
        workload="all",
        product="chat",
    )
    row.update(kw)
    return row


# ---------------------------------------------------------------- OpenAI Usage / Costs API


def _openai_usage_rows(pages: list[dict], source: str, warnings: list[str]) -> list[dict]:
    rows, skipped = [], {}
    for page in pages:
        for bucket in page.get("data", []):
            start, end = bucket["start_time"], bucket["end_time"]
            for r in bucket.get("results", []):
                obj = r.get("object", "")
                if obj != "organization.usage.completions.result":
                    skipped[obj] = skipped.get(obj, 0) + 1
                    continue
                total_in = _int(r.get("input_tokens"))
                cached = _int(r.get("input_cached_tokens"))
                write = _int(r.get("input_cache_write_tokens"))
                uncached = r.get("input_uncached_tokens")
                uncached = _int(uncached) if uncached is not None else max(total_in - cached - write, 0)
                rows.append(
                    _row(
                        timestamp=_ts(start),
                        bucket_seconds=end - start,
                        granularity="bucket",
                        vendor="openai",
                        model=r.get("model") or "unknown",
                        workload=r.get("project_id") or r.get("api_key_id") or r.get("user_id") or "all",
                        service_tier=_openai_tier(r.get("batch"), r.get("service_tier")),
                        requests=_int(r.get("num_model_requests")),
                        uncached_input_tokens=uncached,
                        cache_read_tokens=cached,
                        cache_write_tokens=write,
                        output_tokens=_int(r.get("output_tokens")),
                        source=source,
                    )
                )
    for obj, n in skipped.items():
        warnings.append(f"{source}: skipped {n} non-completions results ({obj}); not priced.")
    return rows


def _openai_embedding_rows(pages: list[dict], source: str) -> list[dict]:
    """Embeddings usage. Fields match DataResultOrganizationUsageEmbeddingsResult."""
    rows = []
    for page in pages:
        for bucket in page.get("data", []):
            start, end = bucket["start_time"], bucket["end_time"]
            for result in bucket.get("results", []):
                if result.get("object") != "organization.usage.embeddings.result":
                    continue
                rows.append(
                    _row(
                        timestamp=_ts(start),
                        bucket_seconds=end - start,
                        granularity="bucket",
                        vendor="openai",
                        model=result.get("model") or "unknown",
                        workload=result.get("project_id") or result.get("api_key_id") or result.get("user_id") or "all",
                        product="embedding",
                        requests=_int(result.get("num_model_requests")),
                        uncached_input_tokens=_int(result.get("input_tokens")),
                        source=source,
                    )
                )
    return rows


def _openai_cost_rows(pages: list[dict], source: str) -> list[dict]:
    rows = []
    for page in pages:
        for bucket in page.get("data", []):
            for r in bucket.get("results", []):
                amount = r.get("amount") or {}
                rows.append(
                    {
                        "date": _ts(bucket["start_time"]).date(),
                        "vendor": "openai",
                        "line_item": r.get("line_item"),
                        "amount_usd": float(amount.get("value") or 0.0),
                        "source": source,
                    }
                )
    return rows


# ---------------------------------------------------------------- Anthropic Usage / Cost API


def _anthropic_usage_rows(pages: list[dict], source: str, warnings: list[str]) -> list[dict]:
    rows, long_context = [], 0
    for page in pages:
        for bucket in page.get("data", []):
            start, end = _ts(bucket["starting_at"]), _ts(bucket["ending_at"])
            for r in bucket.get("results", []):
                creation = r.get("cache_creation") or {}
                long_context += r.get("context_window") == "200k-1M"
                rows.append(
                    _row(
                        timestamp=start,
                        bucket_seconds=int((end - start).total_seconds()),
                        granularity="bucket",
                        vendor="anthropic",
                        model=r.get("model") or "unknown",
                        workload=r.get("workspace_id") or r.get("api_key_id") or "default",
                        service_tier=_anthropic_tier(r.get("service_tier"), r.get("speed")),
                        inference_geo=r.get("inference_geo"),
                        uncached_input_tokens=_int(r.get("uncached_input_tokens")),
                        cache_read_tokens=_int(r.get("cache_read_input_tokens")),
                        cache_write_tokens=_int(creation.get("ephemeral_5m_input_tokens")),
                        cache_write_1h_tokens=_int(creation.get("ephemeral_1h_input_tokens")),
                        output_tokens=_int(r.get("output_tokens")),
                        web_search_requests=_int((r.get("server_tool_use") or {}).get("web_search_requests")),
                        source=source,
                    )
                )
    if long_context:
        warnings.append(
            f"{source}: {long_context} rows use the 200k-1M context window; priced at standard rates "
            "(check the long-context rate on the pricing page)."
        )
    return rows


def _anthropic_cost_rows(pages: list[dict], source: str) -> list[dict]:
    rows = []
    for page in pages:
        for bucket in page.get("data", []):
            for r in bucket.get("results", []):
                rows.append(
                    {
                        "date": _ts(bucket["starting_at"]).date(),
                        "vendor": "anthropic",
                        "line_item": r.get("description"),
                        # Amount is a decimal string in cents.
                        "amount_usd": float(r.get("amount") or 0.0) / 100,
                        "source": source,
                    }
                )
    return rows


# ---------------------------------------------------------------- request-level logs


def _usage_from_sdk(usage: dict, vendor: str) -> dict:
    """Map a raw `response.usage` dict (any of the three SDK shapes) to normalised tokens."""
    if "prompt_tokens" in usage:  # OpenAI Chat Completions: CompletionUsage
        details = usage.get("prompt_tokens_details") or {}
        cached, write = _int(details.get("cached_tokens")), _int(details.get("cache_write_tokens"))
        out_details = usage.get("completion_tokens_details") or {}
        return {
            "uncached_input_tokens": max(_int(usage["prompt_tokens"]) - cached - write, 0),
            "cache_read_tokens": cached,
            "cache_write_tokens": write,
            "output_tokens": _int(usage.get("completion_tokens")),
            "reasoning_tokens": _int(out_details.get("reasoning_tokens")),
        }
    if vendor == "anthropic":  # anthropic.types.Usage
        creation = usage.get("cache_creation")
        if creation:
            write_5m = _int(creation.get("ephemeral_5m_input_tokens"))
            write_1h = _int(creation.get("ephemeral_1h_input_tokens"))
        else:
            write_5m, write_1h = _int(usage.get("cache_creation_input_tokens")), 0
        return {
            "uncached_input_tokens": _int(usage.get("input_tokens")),
            "cache_read_tokens": _int(usage.get("cache_read_input_tokens")),
            "cache_write_tokens": write_5m,
            "cache_write_1h_tokens": write_1h,
            "output_tokens": _int(usage.get("output_tokens")),
            "reasoning_tokens": _int((usage.get("output_tokens_details") or {}).get("thinking_tokens")),
            "web_search_requests": _int((usage.get("server_tool_use") or {}).get("web_search_requests")),
        }
    # OpenAI Responses API: ResponseUsage
    details = usage.get("input_tokens_details") or {}
    cached, write = _int(details.get("cached_tokens")), _int(details.get("cache_write_tokens"))
    return {
        "uncached_input_tokens": max(_int(usage.get("input_tokens")) - cached - write, 0),
        "cache_read_tokens": cached,
        "cache_write_tokens": write,
        "output_tokens": _int(usage.get("output_tokens")),
        "reasoning_tokens": _int((usage.get("output_tokens_details") or {}).get("reasoning_tokens")),
    }


def _request_rows(lines: Iterable[dict], source: str, warnings: list[str], salt: bytes) -> list[dict]:
    from llm_cost_teardown.fingerprint import fingerprint_request

    rows, missing_usage = [], 0
    for rec in lines:
        usage = rec.get("usage")
        if not isinstance(usage, dict):
            missing_usage += 1
            continue
        model = rec.get("model") or "unknown"
        vendor = rec.get("vendor") or ("anthropic" if model.lower().startswith("claude") else "openai")
        fp = rec.get("fingerprint")
        if fp is None and isinstance(rec.get("request"), dict):
            fp = fingerprint_request(rec["request"], salt)
        fp = fp or {}
        tier = rec.get("service_tier") or usage.get("service_tier")
        sample_rate = float(rec.get("sample_rate") or 1.0)
        rows.append(
            _row(
                timestamp=_ts(rec["timestamp"]),
                granularity="request",
                vendor=vendor,
                model=model,
                workload=rec.get("workload") or rec.get("feature") or "all",
                service_tier=_openai_tier(rec.get("batch"), tier)
                if vendor == "openai"
                else _anthropic_tier(tier, rec.get("speed")),
                inference_geo=usage.get("inference_geo"),
                requests=1,
                weight=1.0 / sample_rate,
                request_hash=fp.get("request_hash"),
                prefix_hashes=fp.get("prefix_hashes"),
                prefix_chars=fp.get("prefix_chars"),
                status=rec.get("status"),
                source=source,
                **_usage_from_sdk(usage, vendor),
            )
        )
    if missing_usage:
        warnings.append(f"{source}: {missing_usage} log lines without a `usage` object were ignored.")
    return rows


# ---------------------------------------------------------------- dispatch


def _read_jsonl(path: Path) -> Iterator[dict]:
    with path.open() as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def _pages(obj) -> list[dict]:
    return obj if isinstance(obj, list) else [obj]


def _first_result(pages: list[dict]) -> dict | None:
    for page in pages:
        for bucket in page.get("data", []):
            for r in bucket.get("results", []):
                return r
    return None


def detect_kind(pages: list[dict]) -> str:
    r = _first_result(pages)
    if r is None:
        return "empty"
    obj = r.get("object", "")
    if obj == "organization.costs.result":
        return "openai_costs"
    if obj == "organization.usage.embeddings.result":
        return "openai_embeddings"
    if obj.startswith("organization.usage."):
        return "openai_usage"
    if "uncached_input_tokens" in r:
        return "anthropic_usage"
    if "amount" in r and "currency" in r:
        return "anthropic_costs"
    return "unknown"


def load_usage(paths: Path | Iterable[Path]) -> UsageData:
    """Load one or more exports (JSON pages, JSONL request logs, normalised CSV)."""
    from llm_cost_teardown.fingerprint import new_salt

    paths = [paths] if isinstance(paths, Path | str) else list(paths)
    # Raw request bodies in different files must share one salt so their prefixes can match.
    salt = new_salt()
    rows: list[dict] = []
    costs: list[dict] = []
    csv_frames: list[pd.DataFrame] = []
    warnings: list[str] = []
    for path in map(Path, paths):
        name = path.name
        if path.suffix == ".jsonl":
            lines = list(_read_jsonl(path))
            if lines and ("checks" in lines[0] or ("output" in lines[0] and "usage" not in lines[0])):
                continue
            rows += _request_rows(lines, name, warnings, salt)
        elif path.suffix == ".csv":
            csv_frames.append(_load_normalised_csv(path))
        else:
            pages = _pages(json.loads(path.read_text()))
            kind = detect_kind(pages)
            if kind == "openai_usage":
                rows += _openai_usage_rows(pages, name, warnings)
            elif kind == "openai_embeddings":
                rows += _openai_embedding_rows(pages, name)
            elif kind == "anthropic_usage":
                rows += _anthropic_usage_rows(pages, name, warnings)
            elif kind == "openai_costs":
                costs += _openai_cost_rows(pages, name)
            elif kind == "anthropic_costs":
                costs += _anthropic_cost_rows(pages, name)
            elif kind == "empty":
                warnings.append(f"{name}: export contains no results.")
            else:
                raise ValueError(f"{name}: unrecognised export format")
    frame = pd.DataFrame(rows, columns=COLUMNS)
    if csv_frames:
        frame = pd.concat([frame, *csv_frames], ignore_index=True) if rows else pd.concat(csv_frames)
    if frame.empty:
        raise ValueError("No usage rows loaded")
    frame = frame.reset_index(drop=True)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["model_key"] = frame["model"].map(pricing.normalize_model)
    unknown = frame.loc[frame["model"] == "unknown", "source"].unique()
    for src in unknown:
        warnings.append(f"{src}: rows without a model; re-export grouped by model.")
    frame["monthly_factor"] = 0.0
    for _, idx in frame.groupby("source").groups.items():
        frame.loc[idx, "monthly_factor"] = 30 / period_days(frame.loc[idx])
    invoiced = pd.DataFrame(costs) if costs else None
    return UsageData(frame=price_frame(frame, warnings), invoiced=invoiced, warnings=warnings)


def _load_normalised_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = {"timestamp", "model", *TOKEN_COLUMNS[:1], "output_tokens"} - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = _row()[col]
    df["vendor"] = df["vendor"].fillna(
        df["model"].str.lower().str.startswith("claude").map({True: "anthropic", False: "openai"})
    )
    df["granularity"] = df["granularity"].fillna("bucket")
    df["source"] = path.name
    for col in [*TOKEN_COLUMNS, "reasoning_tokens", "web_search_requests"]:
        df[col] = df[col].fillna(0).astype("int64")
    return df[COLUMNS]


# ---------------------------------------------------------------- pricing


def tier_multiplier(price: pricing.ModelPrice, tier: str) -> tuple[float, str | None]:
    """Return (multiplier, warning) for a service tier."""
    if tier in ("standard", None):
        return 1.0, None
    if tier == "batch":
        return price.batch_multiplier, None
    if tier == "flex" and price.vendor == "openai":
        return price.batch_multiplier, None
    if tier == "fast" and price.fast_multiplier:
        return price.fast_multiplier, None
    return 1.0, f"service tier '{tier}' priced at standard rates (no verified multiplier)"


def epoch_seconds(timestamps: pd.Series) -> np.ndarray:
    # Unit-safe: pandas 3 parses strings to datetime64[us], older data may be [ns].
    return (timestamps - pd.Timestamp(0, tz="UTC")).dt.total_seconds().to_numpy()


def total_input(df: pd.DataFrame) -> np.ndarray:
    return df[TOKEN_COLUMNS[:4]].sum(axis=1).to_numpy(dtype=float)


def row_scales(
    df: pd.DataFrame, price: pricing.ModelPrice, tier_mult: np.ndarray, token_scale: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """Per-row (input, output) multipliers: tier x geo x sample weight x long-context."""
    base = tier_mult * df["weight"].to_numpy(dtype=float)
    base = base * np.where(df["inference_geo"].to_numpy() == "us", pricing.ANTHROPIC_US_GEO_MULTIPLIER, 1.0)
    in_scale, out_scale = base.copy(), base.copy()
    if price.long_context_threshold:
        # Only request-level rows know the per-request prompt size.
        is_long = (df["granularity"].to_numpy() == "request") & (
            total_input(df) * token_scale > price.long_context_threshold
        )
        in_scale *= np.where(is_long, price.long_context_input_multiplier, 1.0)
        out_scale *= np.where(is_long, price.long_context_output_multiplier, 1.0)
    return in_scale, out_scale


COST_COMPONENTS = ["cost_uncached", "cost_cache_read", "cost_cache_write", "cost_output"]


def cost_components(
    df: pd.DataFrame, price: pricing.ModelPrice, tier_mult: np.ndarray, token_scale: float = 1.0
) -> dict[str, np.ndarray]:
    in_scale, out_scale = row_scales(df, price, tier_mult, token_scale)
    unit = token_scale / 1e6
    write_1h = price.cache_write_1h if price.cache_write_1h is not None else price.cache_write
    return {
        "cost_uncached": df["uncached_input_tokens"].to_numpy() * price.input * unit * in_scale,
        "cost_cache_read": df["cache_read_tokens"].to_numpy() * price.cached_input * unit * in_scale,
        "cost_cache_write": (
            df["cache_write_tokens"].to_numpy() * price.cache_write + df["cache_write_1h_tokens"].to_numpy() * write_1h
        )
        * unit
        * in_scale,
        "cost_output": df["output_tokens"].to_numpy() * price.output * unit * out_scale,
    }


def token_costs(
    df: pd.DataFrame, price: pricing.ModelPrice, tier_mult: np.ndarray, token_scale: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """Return (input_cost, output_cost) arrays for rows priced on `price`."""
    parts = cost_components(df, price, tier_mult, token_scale)
    return parts["cost_uncached"] + parts["cost_cache_read"] + parts["cost_cache_write"], parts["cost_output"]


def tier_multipliers(df: pd.DataFrame, price: pricing.ModelPrice) -> tuple[np.ndarray, set[str]]:
    mults, warns = [], set()
    for tier in df["service_tier"]:
        m, w = tier_multiplier(price, tier)
        mults.append(m)
        if w:
            warns.add(w)
    return np.array(mults, dtype=float), warns


def price_frame(frame: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    for col in COST_COMPONENTS:
        frame[col] = 0.0
    frame["cost_other"] = frame["web_search_requests"] * frame["weight"] * pricing.WEB_SEARCH_USD_PER_1K / 1000
    frame["priced"] = False
    for key, idx in frame.groupby("model_key").groups.items():
        price = pricing.PRICES.get(key)
        if price is None:
            if key != "unknown":
                warnings.append(f"model '{key}' is not in pricing.py; its usage is excluded from costs.")
            continue
        sub = frame.loc[idx]
        mult, warns = tier_multipliers(sub, price)
        warnings.extend(f"{key}: {w}" for w in sorted(warns))
        for col, values in cost_components(sub, price, mult).items():
            frame.loc[idx, col] = values
        frame.loc[idx, "priced"] = True
    frame["cost_input"] = frame["cost_uncached"] + frame["cost_cache_read"] + frame["cost_cache_write"]
    frame["cost_usd"] = frame["cost_input"] + frame["cost_output"] + frame["cost_other"]
    return frame


def period_days(frame: pd.DataFrame) -> float:
    start = frame["timestamp"].min()
    end = (frame["timestamp"] + pd.to_timedelta(frame["bucket_seconds"], unit="s")).max()
    return max((end - start).total_seconds() / 86400, 1 / 24)
