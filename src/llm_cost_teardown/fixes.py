"""Code sketches for each savings lever, filled from the usage that produced the number.

The sketch names the models and workloads in this export. It is a starting diff, not a patch
that applies cleanly to a client's repository.
"""

import math

import pandas as pd

from llm_cost_teardown import pricing
from llm_cost_teardown.estimators import ROUTING_SHORT_INPUT, ROUTING_SHORT_OUTPUT, Context, Lever
from llm_cost_teardown.usage import total_input

ANTHROPIC_TTL = {"5 min": "5m", "1 h": "1h"}
# Skip a cache sketch when the measured saving is rounding error next to the model's bill.
MIN_CACHE_SKETCH_USD = 50


def apply_fixes(ctx: Context, levers: list[Lever]) -> None:
    by_key = {lever.key: lever for lever in levers}
    _migration(ctx, by_key["migration"])
    _routing(ctx, by_key["routing"])
    _caching(ctx, by_key["caching"])
    _batch(by_key["batch"])
    _output(ctx, by_key["output"])
    _duplicates(by_key["duplicates"])
    _fast(ctx, by_key["fast_mode"])


def _workloads(ctx: Context, model_key: str) -> str:
    frame = ctx.spend[ctx.spend["model_key"] == model_key]
    if frame.empty:
        return ""
    ranked = frame.groupby("workload")["cost_usd"].sum().sort_values(ascending=False)
    names = [str(name) for name in ranked.head(2).index if name and name != "all"]
    return ", ".join(names)


def _migration(ctx: Context, lever: Lever) -> None:
    rows = [row for row in lever.table if row.get("to") and row.get("saving_base", 0) >= 1]
    if not rows:
        return
    lines = ["SUCCESSOR = {"]
    for row in sorted(rows, key=lambda item: -item["saving_base"])[:8]:
        where = _workloads(ctx, row["model"])
        comment = f"  # {where}" if where else ""
        lines.append(f'    "{row["model"]}": "{row["to"]}",{comment}')
    lines += [
        "}",
        "",
        "def model_for(current: str, enabled: bool) -> str:",
        '    """Swap behind a flag. Turn the flag on only after the eval gate passes."""',
        "    return SUCCESSOR.get(current, current) if enabled else current",
    ]
    lever.snippets.append("\n".join(lines))


def _routing(ctx: Context, lever: Lever) -> None:
    if ctx.requests.empty or lever.base < 1:
        return
    lines = ["ROUTE = {"]
    priced = ctx.requests[ctx.requests["priced"]]
    grouped = priced.groupby(["workload", "model_key"])
    for (workload, key), frame in grouped:
        target = _cheaper(str(key))
        if target is None or _short_share(frame) < 0.2:
            continue
        lines.append(f'    "{workload}": "{target}",  # was {key}')
    if len(lines) == 1:
        return
    lines += [
        "}",
        "",
        "def routed(workload: str, default: str) -> str:",
        "    return ROUTE.get(workload, default)",
    ]
    lever.snippets.append("\n".join(lines))


def _cheaper(model_key: str) -> str | None:
    current = pricing.latest_successor(model_key)
    price = pricing.PRICES.get(current)
    if price is None or not price.cheaper_tier:
        return None
    return price.cheaper_tier


def _short_share(frame: pd.DataFrame) -> float:
    cost = frame["cost_usd"].sum()
    if cost <= 0:
        return 0.0
    visible = frame["output_tokens"] - frame["reasoning_tokens"]
    short = (visible <= ROUTING_SHORT_OUTPUT) & (total_input(frame) <= ROUTING_SHORT_INPUT)
    return float(frame.loc[short, "cost_usd"].sum() / cost)


def _caching(ctx: Context, lever: Lever) -> None:
    saved = {row["model"] for row in lever.table if row.get("saving_base", 0) >= MIN_CACHE_SKETCH_USD}
    anthropic, openai = [], []
    for key, spec in (lever.meta.get("cache") or {}).items():
        if key not in saved:
            continue
        (anthropic if spec["vendor"] == "anthropic" else openai).append((key, spec))
    if anthropic:
        lever.snippets.append(_anthropic_cache(anthropic))
    if openai:
        lever.snippets.append(_openai_cache(ctx, openai))


def _anthropic_cache(rows: list[tuple[str, dict]]) -> str:
    lines = ["# cache_control on the last static block. prefix_chars is the repeated prefix in the logs."]
    lines.append("CACHE = {")
    for key, spec in sorted(rows):
        ttl = ANTHROPIC_TTL.get(spec["ttl"], "5m")
        chars = _chars(spec.get("prefix_chars"))
        lines.append(f'    "{key}": {{"ttl": "{ttl}", "prefix_chars": {chars}}},')
    lines += [
        "}",
        "",
        "def cached_system(model: str, static: str, dynamic: str) -> list[dict]:",
        "    spec = CACHE[model]",
        "    return [",
        '        {"type": "text", "text": static, "cache_control": {"type": "ephemeral", "ttl": spec["ttl"]}},',
        '        {"type": "text", "text": dynamic},',
        "    ]",
    ]
    return "\n".join(lines)


def _openai_cache(ctx: Context, rows: list[tuple[str, dict]]) -> str:
    lines = ["# prompt_cache_key per template. The prefix must stay byte-identical for the TTL below."]
    lines.append("PROMPT_CACHE_KEY = {")
    for key, spec in sorted(rows):
        where = _workloads(ctx, key).split(",")[0].strip() or key
        cache_key = where.removeprefix("proj_").removeprefix("wrkspc_").replace("_", "-")
        chars = _chars(spec.get("prefix_chars"))
        lines.append(f'    "{key}": "{cache_key}",  # {spec["ttl"]} TTL, prefix {chars} chars')
    lines.append("}")
    return "\n".join(lines)


def _chars(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "None"
    return f"{int(value):,}".replace(",", "_")


def _batch(lever: Lever) -> None:
    rows = [row for row in lever.table if row.get("saving_base", 0) >= 1]
    if not rows:
        return
    by_vendor: dict[str, list[str]] = {}
    for row in rows:
        by_vendor.setdefault(row["vendor"], []).append(str(row["workload"]))
    if names := by_vendor.get("openai"):
        listed = ",\n".join(f'    "{name}"' for name in names)
        lever.snippets.append(
            "\n".join(
                [
                    f"BATCH_WORKLOADS = {{\n{listed},\n}}",
                    "",
                    "def submit_openai(client, jsonl_path: str):",
                    '    uploaded = client.files.create(file=open(jsonl_path, "rb"), purpose="batch")',
                    "    return client.batches.create(",
                    "        input_file_id=uploaded.id,",
                    '        endpoint="/v1/chat/completions",',
                    '        completion_window="24h",',
                    "    )",
                ]
            )
        )
    if names := by_vendor.get("anthropic"):
        listed = ", ".join(f'"{name}"' for name in names)
        lever.snippets.append(
            "\n".join(
                [
                    f"ANTHROPIC_BATCH = [{listed}]",
                    "",
                    "def submit_anthropic(client, requests: list[dict]):",
                    "    return client.messages.batches.create(requests=requests)",
                ]
            )
        )


def _output(ctx: Context, lever: Lever) -> None:
    if ctx.requests.empty or lever.base < 1:
        return
    lines = ["# p95 of output tokens, including reasoning, with 10% headroom.", "MAX_TOKENS = {"]
    for workload, frame in ctx.requests.groupby("workload"):
        if len(frame) < 20:
            continue
        p95 = int(math.ceil(float(frame["output_tokens"].quantile(0.95)) * 1.1))
        if p95 <= 0:
            continue
        lines.append(f'    "{workload}": {p95},')
    if len(lines) == 2:
        return
    lines.append("}")
    lever.snippets.append("\n".join(lines))


def _duplicates(lever: Lever) -> None:
    rows = [row for row in lever.table if row.get("saving_base", 0) >= 1]
    if not rows:
        return
    models = ", ".join(f"`{row['model']}`" for row in rows[:4])
    lever.snippets.append(
        "\n".join(
            [
                f"# Exact repeat within 24h is paid spend on {models}.",
                "def once(cache: dict, key: str, create, **params):",
                "    hit = cache.get(key)",
                "    if hit is not None:",
                "        return hit",
                "    result = create(**params)",
                "    cache[key] = result",
                "    return result",
            ]
        )
    )


def _fast(ctx: Context, lever: Lever) -> None:
    if lever.base < 1:
        return
    fast = ctx.spend[(ctx.spend["service_tier"] == "fast") & ctx.spend["priced"]]
    models = sorted({str(model) for model in fast["model_key"].unique()})
    if not models:
        return
    listed = ", ".join(f'"{model}"' for model in models)
    lever.snippets.append(
        "\n".join(
            [
                f"FAST_PREMIUM = [{listed}]",
                "FAST_ONLY: set[str] = set()  # workloads that actually need the latency",
                "",
                "def tier_for(workload: str) -> str:",
                '    return "priority" if workload in FAST_ONLY else "default"',
            ]
        )
    )
