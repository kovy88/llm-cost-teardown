"""Savings estimators ("levers").

Each lever returns a monthly USD saving for three scenarios (low / base / high) and states how
the number was obtained:
- exact: follows from the verified price table alone (e.g. same-tier successor model)
- measured: computed from request-level logs
- scenario: an assumption applied to aggregate usage; replace it with a measurement in the audit

Rates measured on request logs are applied per model to the (usually longer) aggregate spend.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from llm_cost_teardown import pricing
from llm_cost_teardown.usage import epoch_seconds, row_scales, tier_multipliers, token_costs, total_input

Triple = tuple[float, float, float]

ROUTING_SCENARIO: Triple = (0.15, 0.30, 0.45)
# Classification / extraction-like calls: short visible answer on a modest prompt.
ROUTING_SHORT_OUTPUT = 120
ROUTING_SHORT_INPUT = 4000
ROUTING_MAX_SHARE = 0.6
CACHE_SCENARIO_HIT: Triple = (0.25, 0.45, 0.65)
CACHE_READS_PER_WRITE = 10
CACHE_REALISATION: Triple = (0.5, 0.8, 1.0)
BATCH_SCENARIO: Triple = (0.05, 0.15, 0.25)
BATCH_CANDIDATE: Triple = (0.5, 0.9, 1.0)
BATCH_NON_CANDIDATE: Triple = (0.0, 0.0, 0.1)
BATCH_CONCENTRATION = 0.6
OUTPUT_SCENARIO: Triple = (0.05, 0.10, 0.20)
OUTPUT_REASONING_HEAVY: Triple = (0.10, 0.20, 0.35)
REASONING_HEAVY_SHARE = 0.4
DUPLICATE_SHARE: Triple = (0.5, 0.8, 1.0)
FAILED_SHARE: Triple = (0.3, 0.5, 0.7)
DUPLICATE_WINDOW_S = 24 * 3600
FAST_SHARE: Triple = (0.25, 0.5, 0.75)


@dataclass
class Lever:
    key: str
    title: str
    low: float = 0.0
    base: float = 0.0
    high: float = 0.0
    method: str = "scenario"
    evidence: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    table: list[dict] = field(default_factory=list)

    def add(self, amounts: Triple) -> None:
        self.low += amounts[0]
        self.base += amounts[1]
        self.high += amounts[2]


@dataclass
class Context:
    spend: pd.DataFrame
    requests: pd.DataFrame
    batchable: frozenset[str] = frozenset()


def monthly(df: pd.DataFrame, column: str = "cost_usd") -> float:
    return float((df[column] * df["monthly_factor"]).sum())


def _scale(shares: Triple, amount: float) -> Triple:
    return (shares[0] * amount, shares[1] * amount, shares[2] * amount)


def _method(measured: int, total: int) -> str:
    if total == 0 or measured == 0:
        return "scenario"
    return "measured" if measured == total else "measured + scenario"


def reprice(df: pd.DataFrame, source_key: str, target_key: str) -> np.ndarray:
    """Monthly input+output cost of `df` if the same traffic ran on `target_key`."""
    price = pricing.PRICES[target_key]
    mult, _ = tier_multipliers(df, price)
    cin, cout = token_costs(df, price, mult, token_scale=pricing.token_ratio(source_key, target_key))
    return (cin + cout) * df["monthly_factor"].to_numpy()


def _priced(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["priced"]]


def _apply_rates(
    ctx: Context, lever: Lever, rates: dict[str, Triple], scenario: Callable[[str, pd.DataFrame], Triple | None]
) -> None:
    """Apply measured per-model rates to spend; fall back to `scenario(model, rows)` elsewhere."""
    measured = total = 0
    for key, df in _priced(ctx.spend).groupby("model_key"):
        cost = monthly(df)
        if key in rates:
            amounts = _scale(rates[key], cost)
            measured += 1
        else:
            amounts = scenario(key, df)
            if amounts is None:
                continue
        total += 1
        lever.add(amounts)
        if amounts[1] >= 1:
            lever.table.append({"model": key, "monthly_cost": cost, "saving_base": amounts[1]})
    lever.method = _method(measured, total)


# ---------------------------------------------------------------- 1. model migration


def lever_migration(ctx: Context) -> Lever:
    lever = Lever(
        "migration",
        "Migrate legacy models to the current model of the same tier",
        method="exact",
        actions=[
            "Swap the model id behind a feature flag, run the eval set on old vs new model, then roll out.",
            "Re-check output length after the switch; newer models can be more verbose or reason longer.",
        ],
    )
    for key, df in _priced(ctx.spend).groupby("model_key"):
        target = pricing.latest_successor(key)
        if target == key or target not in pricing.PRICES:
            continue
        current = monthly(df, "cost_input") + monthly(df, "cost_output")
        after = float(reprice(df, key, target).sum())
        ratio = pricing.token_ratio(key, target)
        note = f" (token count x{ratio:.2f} for the newer tokenizer)" if ratio != 1 else ""
        if after >= current * 0.99:
            lever.evidence.append(f"`{key}` -> `{target}` would not be cheaper{note}; keep for now.")
            continue
        saving = current - after
        lever.add((0.5 * saving, saving, saving))
        lever.table.append({"model": key, "to": target, "monthly_cost": current, "after": after, "saving_base": saving})
        lever.evidence.append(f"`{key}` -> `{target}`: ${current:,.0f} -> ${after:,.0f} per month{note}.")
    return lever


# ---------------------------------------------------------------- 2. routing


def _routing_candidates(requests: pd.DataFrame) -> dict[str, float]:
    shares = {}
    for key, df in _priced(requests).groupby("model_key"):
        visible_output = df["output_tokens"] - df["reasoning_tokens"]
        short = (visible_output <= ROUTING_SHORT_OUTPUT) & (total_input(df) <= ROUTING_SHORT_INPUT)
        cost = df["cost_usd"].sum()
        if cost > 0:
            shares[key] = float(df.loc[short, "cost_usd"].sum() / cost)
    return shares


def lever_routing(ctx: Context) -> Lever:
    lever = Lever(
        "routing",
        "Route simple requests to a cheaper model tier",
        actions=[
            "Add a router (rules on task type / prompt length, or a small classifier) in front of the model call.",
            "Accept the route only where the eval-set score of the cheaper model stays within tolerance.",
        ],
    )
    candidates = _routing_candidates(ctx.requests)
    measured = total = 0
    few_short: list[str] = []
    for key, df in _priced(ctx.spend).groupby("model_key"):
        current = pricing.latest_successor(key)
        price = pricing.PRICES.get(current)
        if price is None or not price.cheaper_tier:
            continue
        on_current = float(reprice(df, key, current).sum())
        on_cheaper = float(reprice(df, key, price.cheaper_tier).sum())
        delta = on_current - on_cheaper
        if delta <= 0:
            continue
        via = f" (after migrating to `{current}`)" if current != key else ""
        if key in candidates:
            c = min(candidates[key], ROUTING_MAX_SHARE)
            shares = (0.5 * c, c, min(c + 0.15, 0.8))
            measured += 1
            if c >= 0.05:
                lever.evidence.append(
                    f"`{key}`: {c:.0%} of spend is short, classification-like calls (<= {ROUTING_SHORT_OUTPUT} "
                    f"visible output tokens, <= {ROUTING_SHORT_INPUT:,} input tokens) -> `{price.cheaper_tier}`{via}."
                )
            else:
                few_short.append(key)
        else:
            shares = ROUTING_SCENARIO
        total += 1
        amounts = _scale(shares, delta)
        lever.add(amounts)
        if amounts[1] >= 1:
            lever.table.append(
                {"model": key, "to": price.cheaper_tier, "monthly_cost": on_current, "saving_base": amounts[1]}
            )
    lever.method = _method(measured, total)
    if few_short:
        lever.evidence.append(
            f"{', '.join(f'`{k}`' for k in few_short)}: under 5% of spend is short, classification-like calls; "
            "routing here depends on which features the eval set shows the cheaper tier can handle."
        )
    if measured:
        lever.evidence.append(
            "Conservative / base count only the measured short calls; optimistic adds 15% of traffic "
            "(easy long-form requests) that the eval set may clear for the cheaper tier."
        )
    if lever.method != "measured" and total:
        lever.evidence.append(
            f"Scenario: {ROUTING_SCENARIO[0]:.0%} / {ROUTING_SCENARIO[1]:.0%} / {ROUTING_SCENARIO[2]:.0%} of traffic "
            "can move one tier down without a quality drop (to be proven with the eval set)."
        )
    return lever


# ---------------------------------------------------------------- 3. prompt caching


def _simulate_cache(df: pd.DataFrame, price: pricing.ModelPrice, ttl: float, write_price: float) -> np.ndarray:
    """Input cost per request if every reusable prefix were cached with ideal breakpoints.

    Hit = longest block prefix already seen within the TTL (and above the model's minimum).
    Write = longest prefix a later request reuses within the TTL, minus what was a hit.
    """
    times = epoch_seconds(df["timestamp"])
    totals = total_input(df)
    hashes = df["prefix_hashes"].tolist()
    chars = df["prefix_chars"].tolist()
    n = len(df)
    tokens_per_char = np.array([totals[i] / chars[i][-1] if chars[i] else 0.0 for i in range(n)])

    def longest(i: int, seen: dict[str, float]) -> float:
        hs, cs = hashes[i], chars[i]
        for k in range(len(hs) - 1, -1, -1):
            t = seen.get(hs[k])
            if t is not None and abs(times[i] - t) <= ttl:
                tokens = cs[k] * tokens_per_char[i]
                return tokens if tokens >= price.min_cacheable_tokens else 0.0
        return 0.0

    hit, reuse = np.zeros(n), np.zeros(n)
    last: dict[str, float] = {}
    for i in range(n):
        if hashes[i]:
            hit[i] = longest(i, last)
            last.update(dict.fromkeys(hashes[i], times[i]))
    nxt: dict[str, float] = {}
    for i in range(n - 1, -1, -1):
        if hashes[i]:
            reuse[i] = longest(i, nxt)
            nxt.update(dict.fromkeys(hashes[i], times[i]))
    write = np.minimum(np.clip(reuse - hit, 0, None), totals - hit)
    rest = totals - hit - write
    mult, _ = tier_multipliers(df, price)
    in_scale, _ = row_scales(df, price, mult)
    return (hit * price.cached_input + write * write_price + rest * price.input) / 1e6 * in_scale


def _stable_prefix_chars(df: pd.DataFrame) -> int | None:
    """Deepest prompt block shared by at least half the logged requests, in characters."""
    rows: list[tuple[list, list]] = []
    for hashes, chars in zip(df["prefix_hashes"], df["prefix_chars"], strict=True):
        if isinstance(hashes, list) and isinstance(chars, list) and hashes and len(hashes) == len(chars):
            rows.append((hashes, chars))
    if len(rows) < 5:
        return None
    depth = max(len(hashes) for hashes, _ in rows)
    best: int | None = None
    for k in range(depth):
        counts: dict[str, int] = {}
        char_at: dict[str, list[int]] = {}
        for hashes, chars in rows:
            if k >= len(hashes):
                continue
            counts[hashes[k]] = counts.get(hashes[k], 0) + 1
            char_at.setdefault(hashes[k], []).append(int(chars[k]))
        if not counts:
            break
        top, n = max(counts.items(), key=lambda item: item[1])
        if n / len(rows) < 0.5:
            break
        best = int(np.median(char_at[top]))
    return best


def _measured_cache_rates(requests: pd.DataFrame, lever: Lever) -> dict[str, Triple]:
    rates = {}
    for key, df in _priced(requests).groupby("model_key"):
        has_fp = df["prefix_hashes"].map(lambda h: isinstance(h, list) and len(h) > 0)
        if has_fp.mean() < 0.5:
            continue
        df = df[has_fp].sort_values("timestamp")
        price = pricing.PRICES[key]
        options = [(price.cache_ttl_seconds, price.cache_write, f"{price.cache_ttl_seconds // 60} min")]
        if price.cache_write_1h is not None:
            options.append((pricing.HOUR, price.cache_write_1h, "1 h"))
        current = df["cost_input"].sum()
        best, label = max(((current - _simulate_cache(df, price, ttl, wp).sum(), lab) for ttl, wp, lab in options))
        best = max(best, 0.0)
        total_cost = df["cost_usd"].sum()
        if total_cost <= 0:
            continue
        rate = best / total_cost
        rates[key] = _scale(CACHE_REALISATION, rate)
        lever.meta.setdefault("cache", {})[key] = {
            "ttl": label,
            "prefix_chars": _stable_prefix_chars(df),
            "vendor": price.vendor,
        }
        hit_now = df["cache_read_tokens"].sum() / max(total_input(df).sum(), 1)
        if rate < 0.01:
            lever.evidence.append(
                f"`{key}`: no repeated prefix reaches the {price.min_cacheable_tokens:,}-token cache minimum; "
                "caching does not pay here unless the shared instructions grow."
            )
        else:
            lever.evidence.append(
                f"`{key}`: cache hits today {hit_now:.0%} of input tokens; replaying the logs with stable prefixes "
                f"({label} TTL) saves {rate:.0%} of this model's spend."
            )
    return rates


def _scenario_cache(lever: Lever) -> Callable[[str, pd.DataFrame], Triple | None]:
    def scenario(key: str, df: pd.DataFrame) -> Triple | None:
        price = pricing.PRICES[key]
        u, r = df["uncached_input_tokens"].sum(), df["cache_read_tokens"].sum()
        w, w1h = df["cache_write_tokens"].sum(), df["cache_write_1h_tokens"].sum()
        total = u + r + w + w1h
        if total == 0:
            return None
        requests = df["requests"].sum()
        if requests > 0 and total / requests < price.min_cacheable_tokens:
            lever.evidence.append(
                f"`{key}`: average prompt is {total / requests:,.0f} tokens, below the "
                f"{price.min_cacheable_tokens:,}-token cache minimum; no caching saving assumed."
            )
            return None
        write_1h = price.cache_write_1h if price.cache_write_1h is not None else price.cache_write
        now = u * price.input + r * price.cached_input + w * price.cache_write + w1h * write_1h
        input_cost = monthly(df, "cost_input")
        out = []
        for target in CACHE_SCENARIO_HIT:
            if target <= r / total:
                out.append(0.0)
                continue
            read = target * total
            write = read / CACHE_READS_PER_WRITE
            new = (total - read - write) * price.input + read * price.cached_input + write * price.cache_write
            out.append(max(0.0, 1 - new / now) * input_cost)
        return (out[0], out[1], out[2])

    return scenario


def lever_caching(ctx: Context) -> Lever:
    lever = Lever(
        "caching",
        "Prompt caching (stable prefix first, dynamic content last)",
        actions=[
            "Order every prompt as tools -> system prompt -> static context -> conversation -> dynamic input.",
            "Remove timestamps, request ids and per-user data from the system prompt; pass them at the end.",
            "Anthropic: put `cache_control` on the last static block (or top-level automatic caching for chats).",
            "OpenAI: keep prefixes byte-identical; set a stable `prompt_cache_key` per prompt template.",
        ],
    )
    rates = _measured_cache_rates(ctx.requests, lever)
    _apply_rates(ctx, lever, rates, _scenario_cache(lever))
    if lever.method != "measured":
        lever.evidence.append(
            f"Scenario for models without request logs: {CACHE_SCENARIO_HIT[0]:.0%} / {CACHE_SCENARIO_HIT[1]:.0%} / "
            f"{CACHE_SCENARIO_HIT[2]:.0%} of input tokens served from cache, one cache write per "
            f"{CACHE_READS_PER_WRITE} reads."
        )
    return lever


# ---------------------------------------------------------------- 4. Batch API


def _hour_concentration(df: pd.DataFrame, weights: pd.Series) -> float:
    by_hour = weights.groupby(df["timestamp"].dt.hour).sum()
    if by_hour.sum() <= 0:
        return 0.0
    return float(by_hour.nlargest(3).sum() / by_hour.sum())


def lever_batch(ctx: Context) -> Lever:
    lever = Lever(
        "batch",
        "Batch API for non-interactive workloads (50 % off)",
        actions=[
            "Move scheduled / back-office jobs (summaries, enrichment, evals, embeddings refresh) to the Batch API.",
            "Keep user-facing chat on the synchronous API; batch results arrive within 24 h.",
        ],
    )
    eligible = _priced(ctx.spend)
    eligible = eligible[eligible["service_tier"] == "standard"]
    measured = total = 0
    others: list[dict] = []
    for (vendor, workload), df in eligible.groupby(["vendor", "workload"]):
        potential = 0.0
        for key, part in df.groupby("model_key"):
            potential += monthly(part) * (1 - pricing.PRICES[key].batch_multiplier)
        if potential <= 0:
            continue
        total += 1
        if ctx.batchable:
            shares = (1.0, 1.0, 1.0) if workload in ctx.batchable else (0.0, 0.0, 0.0)
            measured += 1
        else:
            reqs = ctx.requests[(ctx.requests["vendor"] == vendor) & (ctx.requests["workload"] == workload)]
            if len(reqs) >= 50:
                conc = _hour_concentration(reqs, reqs["weight"])
            elif (df["bucket_seconds"] <= 3600).all():
                conc = _hour_concentration(df, df["cost_usd"])
            else:
                conc = None
            if conc is None:
                shares = BATCH_SCENARIO
            else:
                measured += 1
                if conc >= BATCH_CONCENTRATION:
                    shares = BATCH_CANDIDATE
                    lever.evidence.append(
                        f"`{workload}` ({vendor}): {conc:.0%} of traffic falls in its 3 busiest hours of the day "
                        "- looks like a scheduled job."
                    )
                else:
                    shares = BATCH_NON_CANDIDATE
        amounts = _scale(shares, potential)
        lever.add(amounts)
        row = {"workload": workload, "vendor": vendor, "saving_if_batched": potential, "saving_base": amounts[1]}
        (lever.table if amounts[1] >= 1 else others).append(row)
    if others and not ctx.batchable:
        top = sorted(others, key=lambda r: -r["saving_if_batched"])[:3]
        listed = ", ".join(f"`{r['workload']}` (${r['saving_if_batched']:,.0f})" for r in top)
        lever.evidence.append(
            "Other workloads look interactive. If any of them does not need an answer within seconds, "
            f"batching it saves up to: {listed} per month."
        )
    if ctx.batchable:
        lever.method = "exact"
        lever.evidence.append(f"Workloads confirmed as non-interactive: {', '.join(sorted(ctx.batchable))}.")
    else:
        lever.method = _method(measured, total)
        if measured < total:
            lever.evidence.append(
                f"Scenario for workloads without hourly data: {BATCH_SCENARIO[0]:.0%} / {BATCH_SCENARIO[1]:.0%} / "
                f"{BATCH_SCENARIO[2]:.0%} of non-batch spend is not latency-sensitive."
            )
    return lever


# ---------------------------------------------------------------- 5. output trimming


def lever_output(ctx: Context) -> Lever:
    lever = Lever(
        "output",
        "Trim output and reasoning tokens",
        actions=[
            "Set `max_tokens` / `max_output_tokens` per endpoint from the observed p95, not the model maximum.",
            "Ask for structured output (JSON schema) instead of prose where the answer is parsed by code.",
            "Lower reasoning effort on routine tasks; reserve high effort for the hard tail.",
        ],
    )
    reasoning_share = {}
    for key, df in _priced(ctx.requests).groupby("model_key"):
        out = (df["output_tokens"] * df["weight"]).sum()
        if out > 0:
            reasoning_share[key] = float((df["reasoning_tokens"] * df["weight"]).sum() / out)
    for key, df in _priced(ctx.spend).groupby("model_key"):
        out_cost = monthly(df, "cost_output")
        if out_cost <= 0:
            continue
        share = reasoning_share.get(key)
        shares = OUTPUT_REASONING_HEAVY if share is not None and share >= REASONING_HEAVY_SHARE else OUTPUT_SCENARIO
        if share is not None and share >= REASONING_HEAVY_SHARE:
            lever.evidence.append(f"`{key}`: {share:.0%} of output tokens are reasoning tokens.")
        amounts = _scale(shares, out_cost)
        lever.add(amounts)
        lever.table.append({"model": key, "output_cost": out_cost, "saving_base": amounts[1]})
    for workload, df in ctx.requests.groupby("workload"):
        visible = df["output_tokens"] - df["reasoning_tokens"]
        if len(df) >= 20:
            lever.evidence.append(
                f"`{workload}`: visible output p50 {visible.quantile(0.5):,.0f} / "
                f"p95 {visible.quantile(0.95):,.0f} tokens."
            )
    lever.evidence.append(
        f"Scenario: output spend reduced by {OUTPUT_SCENARIO[0]:.0%} / {OUTPUT_SCENARIO[1]:.0%} / "
        f"{OUTPUT_SCENARIO[2]:.0%} ({OUTPUT_REASONING_HEAVY[1]:.0%} base where reasoning dominates)."
    )
    return lever


# ---------------------------------------------------------------- 6. duplicates & failed calls


def _is_failed(status) -> bool:
    if status is None or (isinstance(status, float) and np.isnan(status)):
        return False
    if isinstance(status, int | float):
        return status >= 400
    return str(status).lower() in ("error", "failed", "timeout", "cancelled")


def lever_duplicates(ctx: Context) -> Lever:
    lever = Lever(
        "duplicates",
        "Remove duplicate calls and paid failures",
        actions=[
            "Cache identical requests in the application (hash of model + prompt + params) for deterministic tasks.",
            "Make retries idempotent; cap retries and stop re-sending the full prompt on client-side timeouts.",
        ],
    )
    rates: dict[str, Triple] = {}
    for key, df in _priced(ctx.requests).groupby("model_key"):
        df = df.sort_values("timestamp")
        times = epoch_seconds(df["timestamp"])
        seen: dict[str, float] = {}
        dup = np.zeros(len(df), dtype=bool)
        for i, h in enumerate(df["request_hash"]):
            if isinstance(h, str):
                if h in seen and times[i] - seen[h] <= DUPLICATE_WINDOW_S:
                    dup[i] = True
                seen[h] = times[i]
        failed = df["status"].map(_is_failed).to_numpy(dtype=bool)
        cost = df["cost_usd"].to_numpy()
        total = cost.sum()
        if total <= 0:
            continue
        dup_rate, fail_rate = cost[dup].sum() / total, cost[failed & ~dup].sum() / total
        rates[key] = tuple(d * dup_rate + f * fail_rate for d, f in zip(DUPLICATE_SHARE, FAILED_SHARE, strict=True))
        if dup_rate > 0.005 or fail_rate > 0.005:
            lever.evidence.append(
                f"`{key}`: {dup_rate:.1%} of spend is exact repeats within 24 h, {fail_rate:.1%} is failed calls."
            )
    if not rates:
        lever.method = "not measured"
        lever.evidence.append("Needs request-level logs; not estimated from aggregate usage.")
        return lever
    _apply_rates(ctx, lever, rates, lambda key, df: None)
    lever.method = "measured"
    return lever


# ---------------------------------------------------------------- 7. fast / priority mode


def lever_fast_mode(ctx: Context) -> Lever:
    lever = Lever(
        "fast_mode",
        "Use fast / priority mode only where latency pays for itself",
        actions=["Limit fast mode to the latency-critical path (e.g. first token of a live chat)."],
    )
    fast = _priced(ctx.spend)
    fast = fast[fast["service_tier"] == "fast"]
    for key, df in fast.groupby("model_key"):
        mult = pricing.PRICES[key].fast_multiplier
        if not mult:
            continue
        premium = monthly(df) * (1 - 1 / mult)
        lever.add(_scale(FAST_SHARE, premium))
        lever.evidence.append(f"`{key}`: ${monthly(df):,.0f}/month runs in fast mode ({mult:g}x price).")
    return lever


LEVERS = [lever_migration, lever_routing, lever_caching, lever_batch, lever_output, lever_duplicates, lever_fast_mode]


def run_levers(ctx: Context) -> list[Lever]:
    from llm_cost_teardown.fixes import apply_fixes

    levers = [fn(ctx) for fn in LEVERS]
    apply_fixes(ctx, levers)
    return levers


def combine(levers: list[Lever], monthly_spend: float) -> dict[str, float]:
    """Stack levers multiplicatively so overlapping savings are not double counted."""
    if monthly_spend <= 0:
        return dict.fromkeys(("low", "base", "high"), 0.0)
    out = {}
    for scenario in ("low", "base", "high"):
        remaining = 1.0
        for lever in levers:
            remaining *= 1 - min(getattr(lever, scenario) / monthly_spend, 1.0)
        out[scenario] = monthly_spend * (1 - remaining)
    return out
