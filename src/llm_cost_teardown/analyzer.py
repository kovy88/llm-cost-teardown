from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from llm_cost_teardown import pricing
from llm_cost_teardown.estimators import Context, Lever, combine, run_levers
from llm_cost_teardown.usage import UsageData, load_usage, period_days, total_input

AUDIT_PRICE_USD = 1900
GUARANTEE_MULTIPLE = 3


@dataclass
class Analysis:
    client: str
    data: UsageData
    spend: pd.DataFrame
    requests: pd.DataFrame
    monthly_spend: float
    levers: list[Lever]
    combined: dict[str, float]
    by_model: pd.DataFrame
    by_workload: pd.DataFrame
    by_token_type: dict[str, float]
    reconciliation: pd.DataFrame | None
    generated_at: datetime
    warnings: list[str] = field(default_factory=list)

    @property
    def annual(self) -> dict[str, float]:
        return {k: v * 12 for k, v in self.combined.items()}

    @property
    def guarantee_met(self) -> bool:
        return bool(self.annual["base"] >= GUARANTEE_MULTIPLE * AUDIT_PRICE_USD)

    @property
    def period(self) -> tuple[pd.Timestamp, pd.Timestamp, float]:
        start = self.spend["timestamp"].min()
        end = (self.spend["timestamp"] + pd.to_timedelta(self.spend["bucket_seconds"], unit="s")).max()
        return start, end, period_days(self.spend)


def _select_spend(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate exports are the spend of record; request logs fill vendors without them."""
    bucket_vendors = set(frame.loc[frame["granularity"] == "bucket", "vendor"])
    keep = (frame["granularity"] == "bucket") | ~frame["vendor"].isin(bucket_vendors)
    return frame[keep]


def _m(df: pd.DataFrame, column: str) -> pd.Series:
    return df[column] * df["monthly_factor"]


def _by_model(spend: pd.DataFrame, total: float) -> pd.DataFrame:
    df = spend.assign(
        m_cost=_m(spend, "cost_usd"),
        m_requests=spend["requests"] * spend["weight"] * spend["monthly_factor"],
        m_input=total_input(spend) * spend["weight"] * spend["monthly_factor"],
        m_cached=spend["cache_read_tokens"] * spend["weight"] * spend["monthly_factor"],
        m_output=spend["output_tokens"] * spend["weight"] * spend["monthly_factor"],
    )
    out = df.groupby(["vendor", "model_key"], as_index=False).agg(
        monthly_cost=("m_cost", "sum"),
        requests=("m_requests", lambda s: s.sum(min_count=1)),
        input_tokens=("m_input", "sum"),
        cached_tokens=("m_cached", "sum"),
        output_tokens=("m_output", "sum"),
        priced=("priced", "all"),
    )
    out["share"] = out["monthly_cost"] / total if total else 0.0
    out["cache_hit"] = out["cached_tokens"] / out["input_tokens"].replace(0, np.nan)
    return out.sort_values("monthly_cost", ascending=False, ignore_index=True)


def _by_workload(spend: pd.DataFrame, total: float) -> pd.DataFrame:
    df = spend.assign(m_cost=_m(spend, "cost_usd"))
    out = df.groupby(["vendor", "workload"], as_index=False).agg(monthly_cost=("m_cost", "sum"))
    top = df.groupby(["vendor", "workload", "model_key"], as_index=False)["m_cost"].sum()
    top = top.sort_values("m_cost").drop_duplicates(["vendor", "workload"], keep="last")
    out = out.merge(top[["vendor", "workload", "model_key"]], on=["vendor", "workload"], how="left")
    out["share"] = out["monthly_cost"] / total if total else 0.0
    return out.sort_values("monthly_cost", ascending=False, ignore_index=True)


def _reconcile(data: UsageData, spend: pd.DataFrame) -> pd.DataFrame | None:
    if data.invoiced is None:
        return None
    rows = []
    for vendor, inv in data.invoiced.groupby("vendor"):
        dates = set(inv["date"])
        ours = spend[(spend["vendor"] == vendor) & spend["timestamp"].dt.date.isin(dates)]
        invoiced, modelled = inv["amount_usd"].sum(), ours["cost_usd"].sum()
        rows.append(
            {
                "vendor": vendor,
                "days": len(dates),
                "invoiced": invoiced,
                "modelled": modelled,
                "diff_pct": (modelled - invoiced) / invoiced if invoiced else np.nan,
            }
        )
    return pd.DataFrame(rows)


def analyze(paths: Path | Iterable[Path], client: str = "", batchable: Iterable[str] = ()) -> Analysis:
    data = load_usage(paths)
    frame = data.frame
    spend = _select_spend(frame)
    requests = frame[frame["granularity"] == "request"]
    monthly_spend = float(_m(spend, "cost_usd").sum())
    ctx = Context(spend=spend, requests=requests, batchable=frozenset(batchable))
    levers = run_levers(ctx)
    warnings = list(dict.fromkeys(data.warnings))
    if pricing.is_stale():
        warnings.insert(
            0,
            f"Prices verified on {pricing.VERIFIED_ON} ({pricing.age_days()} days ago). "
            "Re-verify pricing.py against the vendor pages before sending this report.",
        )
    token_types = {
        "Uncached input": float(_m(spend, "cost_uncached").sum()),
        "Cache reads": float(_m(spend, "cost_cache_read").sum()),
        "Cache writes": float(_m(spend, "cost_cache_write").sum()),
        "Output (incl. reasoning)": float(_m(spend, "cost_output").sum()),
        "Web search": float(_m(spend, "cost_other").sum()),
    }
    return Analysis(
        client=client,
        data=data,
        spend=spend,
        requests=requests,
        monthly_spend=monthly_spend,
        levers=levers,
        combined=combine(levers, monthly_spend),
        by_model=_by_model(spend, monthly_spend),
        by_workload=_by_workload(spend, monthly_spend),
        by_token_type=token_types,
        reconciliation=_reconcile(data, spend),
        generated_at=datetime.now(UTC),
        warnings=warnings,
    )


def summary_text(a: Analysis) -> str:
    start, end, days = a.period
    lines = [
        f"Period: {start:%Y-%m-%d} -> {end:%Y-%m-%d} ({days:.1f} days), prices verified {pricing.VERIFIED_ON}",
        f"Monthly spend (30-day normalised): ${a.monthly_spend:,.0f}",
        "",
        f"{'Lever':<58}{'low':>10}{'base':>10}{'high':>10}  method",
    ]
    for lever in a.levers:
        lines.append(f"{lever.title:<58}{lever.low:>10,.0f}{lever.base:>10,.0f}{lever.high:>10,.0f}  {lever.method}")
    c = a.combined
    lines += [
        f"{'Combined (stacked, not summed) per month':<58}{c['low']:>10,.0f}{c['base']:>10,.0f}{c['high']:>10,.0f}",
        f"{'Combined per year':<58}{c['low'] * 12:>10,.0f}{c['base'] * 12:>10,.0f}{c['high'] * 12:>10,.0f}",
        f"Base saving = {c['base'] / a.monthly_spend:.0%} of spend." if a.monthly_spend else "",
        f"Guarantee (annual base >= {GUARANTEE_MULTIPLE}x ${AUDIT_PRICE_USD:,}): "
        + ("MET" if a.guarantee_met else "NOT MET"),
    ]
    if a.warnings:
        lines += ["", "Warnings:", *(f"- {w}" for w in a.warnings)]
    return "\n".join(lines)
