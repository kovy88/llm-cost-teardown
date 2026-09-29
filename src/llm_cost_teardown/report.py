import json
import math

import pandas as pd

from llm_cost_teardown import pricing
from llm_cost_teardown.analyzer import Analysis
from llm_cost_teardown.estimators import Lever
from llm_cost_teardown.evals import Comparison, rate_label, regressions, workload_rows
from llm_cost_teardown.meta import AUDIT_PRICE_USD, CONTACT_EMAIL, GUARANTEE_MULTIPLE

METHOD_NOTE = {
    "exact": "follows from list prices alone",
    "measured": "measured on your usage data",
    "measured + scenario": "measured where the data allows, scenario elsewhere",
    "scenario": "scenario assumption on aggregate usage - to be measured in the audit",
    "not measured": "needs request-level logs",
}


def money(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    if abs(x) < 0.005:
        return "$0"
    return f"${x:,.0f}" if abs(x) >= 10 else f"${x:,.2f}"


def tokens(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    for unit, div in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(x) >= div:
            return f"{x / div:,.1f}{unit}"
    return f"{x:,.0f}"


def pct(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:.0%}"


def table(headers: list[str], rows: list[list[str]], align: str = "") -> str:
    align = align or "l" + "r" * (len(headers) - 1)
    sep = ["---:" if a == "r" else ":---" for a in align]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(sep) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _lever_table(lever: Lever) -> str:
    if not lever.table:
        return ""
    rows = sorted(lever.table, key=lambda r: -r.get("saving_base", 0))[:10]
    if lever.key in ("migration", "routing"):
        return table(
            ["From", "To", "Monthly cost now", "Base saving / month"],
            [[f"`{r['model']}`", f"`{r['to']}`", money(r["monthly_cost"]), money(r["saving_base"])] for r in rows],
            "llrr",
        )
    if lever.key == "batch":
        return table(
            ["Workload", "Vendor", "Saving if fully batched", "Base saving / month"],
            [[f"`{r['workload']}`", r["vendor"], money(r["saving_if_batched"]), money(r["saving_base"])] for r in rows],
            "llrr",
        )
    if lever.key == "output":
        return table(
            ["Model", "Output spend / month", "Base saving / month"],
            [[f"`{r['model']}`", money(r["output_cost"]), money(r["saving_base"])] for r in rows],
        )
    return table(
        ["Model", "Monthly cost", "Base saving / month"],
        [[f"`{r['model']}`", money(r["monthly_cost"]), money(r["saving_base"])] for r in rows],
    )


def _eval_section(c: Comparison) -> list[str]:
    gate = "PASS" if c.gate_pass else "FAIL"
    sign = "+" if c.delta >= 0 else ""
    baseline_models = ", ".join(f"`{m}`" for m in c.baseline.models) or "baseline"
    candidate_models = ", ".join(f"`{m}`" for m in c.candidate.models) or "candidate"
    lines = [
        "## Quality gate (eval set)",
        "",
        f"{c.baseline.n} queries scored with a deterministic rubric (exact match, required phrases). "
        "The set is built with the client from sampled traffic; production prompts stay on their machine.",
        "",
        table(
            ["", "Pass rate", "Models"],
            [
                ["Baseline (current)", rate_label(c.baseline), baseline_models],
                ["Candidate (after levers)", rate_label(c.candidate), candidate_models],
                [
                    f"**Delta / gate (tolerance {pct(c.tolerance)})**",
                    f"**{sign}{c.delta:.0%} · {gate}**",
                    "candidate must stay within tolerance of baseline",
                ],
            ],
            "lll",
        ),
        "",
        "### By workload",
        "",
        table(
            ["Workload", "Baseline", "Candidate", "Delta"],
            [[f"`{w}`", b, cand, delta] for w, b, cand, delta in workload_rows(c)],
            "lrrr",
        ),
        "",
    ]
    dropped = regressions(c)
    if dropped:
        lines += [
            "Items the candidate failed that the baseline passed:",
            "",
            *[f"- `{item.id}` ({item.workload}): {', '.join(item.failed_checks)}" for item in dropped[:8]],
            "",
        ]
    elif c.gate_pass:
        lines += [
            "No regressions: every query the baseline passed, the candidate passed too.",
            "",
        ]
    return lines


def render_markdown(a: Analysis, internal: bool = False) -> str:
    start, end, days = a.period
    c = a.combined
    spend = a.monthly_spend
    title = f"LLM cost teardown - {a.client}" if a.client else "LLM cost teardown"
    out = [
        f"# {title}",
        "",
        f"_Generated {a.generated_at:%Y-%m-%d} · usage {start:%Y-%m-%d} to {end:%Y-%m-%d} ({days:.0f} days) · "
        f"list prices verified {pricing.VERIFIED_ON}_",
        "",
        "## Summary",
        "",
        table(
            ["", "Per month", "Per year"],
            [
                ["Current API spend (30-day normalised)", money(spend), money(spend * 12)],
                [
                    f"**Estimated saving (base, {pct(c['base'] / spend if spend else 0)} of spend)**",
                    f"**{money(c['base'])}**",
                    f"**{money(c['base'] * 12)}**",
                ],
                [
                    "Range (conservative - optimistic)",
                    f"{money(c['low'])} - {money(c['high'])}",
                    f"{money(c['low'] * 12)} - {money(c['high'] * 12)}",
                ],
            ],
        ),
        "",
    ]
    ranked = sorted((lv for lv in a.levers if lv.base > 0), key=lambda lv: -lv.base)
    if ranked:
        out += ["Biggest levers:", ""]
        out += [
            f"{i}. **{lv.title}** - {money(lv.base)}/month ({METHOD_NOTE.get(lv.method, lv.method)})"
            for i, lv in enumerate(ranked[:3], 1)
        ]
        out.append("")
    out += [
        "Savings are stacked multiplicatively (each lever works on what the previous ones left), "
        "so the total is lower than the sum of the rows below. Every model change is validated on an "
        "eval set before rollout; the proof of saving is your invoice before vs after.",
        "",
    ]
    if internal:
        threshold = GUARANTEE_MULTIPLE * AUDIT_PRICE_USD
        out += [
            "> **Internal:** guarantee threshold (annual base saving >= "
            f"{GUARANTEE_MULTIPLE}x {money(AUDIT_PRICE_USD)} = {money(threshold)}): "
            f"**{'MET' if a.guarantee_met else 'NOT MET'}** (annual base {money(c['base'] * 12)}, "
            f"conservative {money(c['low'] * 12)}).",
            "",
        ]

    out += ["## Where the money goes", "", "### By model", ""]
    out.append(
        table(
            [
                "Model",
                "Vendor",
                "Cost / month",
                "Share",
                "Requests / month",
                "Input tokens",
                "Cache hit",
                "Output tokens",
            ],
            [
                [
                    f"`{r.model_key}`" + ("" if r.priced else " (unpriced)"),
                    r.vendor,
                    money(r.monthly_cost),
                    pct(r.share),
                    tokens(r.requests),
                    tokens(r.input_tokens),
                    pct(r.cache_hit),
                    tokens(r.output_tokens),
                ]
                for r in a.by_model.itertuples()
            ],
            "llrrrrrr",
        )
    )
    out += ["", "### By workload (project / workspace / feature)", ""]
    out.append(
        table(
            ["Workload", "Vendor", "Main model", "Cost / month", "Share"],
            [
                [f"`{r.workload}`", r.vendor, f"`{r.model_key}`", money(r.monthly_cost), pct(r.share)]
                for r in a.by_workload.head(10).itertuples()
            ],
            "lllrr",
        )
    )
    out += ["", "### By token type", ""]
    out.append(
        table(
            ["Token type", "Cost / month", "Share"],
            [[k, money(v), pct(v / spend if spend else 0)] for k, v in a.by_token_type.items() if v > 0],
        )
    )

    levers = [lv for lv in a.levers if lv.high > 0 or lv.evidence]
    out += ["", "## Savings levers", ""]
    out.append(
        table(
            ["#", "Lever", "Conservative", "Base", "Optimistic", "Basis"],
            [
                [str(i), lv.title, money(lv.low), money(lv.base), money(lv.high), lv.method]
                for i, lv in enumerate(levers, 1)
            ],
            "rlrrrl",
        )
    )
    out.append("")
    for i, lv in enumerate(levers, 1):
        out += [f"### {i}. {lv.title}", "", f"_Basis: {METHOD_NOTE.get(lv.method, lv.method)}._", ""]
        if lv.evidence:
            out += [f"- {e}" for e in lv.evidence] + [""]
        lever_table = _lever_table(lv)
        if lever_table:
            out += [lever_table, ""]
        if lv.actions and lv.base > 0:
            out += ["What to change:", ""] + [f"- {x}" for x in lv.actions] + [""]

    if a.reconciliation is not None and not a.reconciliation.empty:
        out += ["## Check against the invoice", ""]
        out.append(
            table(
                ["Vendor", "Days", "Invoiced (cost export)", "Modelled from usage", "Difference"],
                [
                    [r.vendor, str(r.days), money(r.invoiced), money(r.modelled), f"{r.diff_pct:+.1%}"]
                    for r in a.reconciliation.itertuples()
                ],
            )
        )
        out += [
            "",
            "Differences come from negotiated discounts, credits, long-context surcharges on aggregate data "
            "and usage types outside chat/messages (embeddings, images, audio).",
            "",
        ]

    if a.eval_comparison is not None:
        out += _eval_section(a.eval_comparison)

    out += [
        "## How the numbers were produced",
        "",
        f"- Usage is priced with per-model list prices read from the vendor pricing pages on "
        f"{pricing.VERIFIED_ON} (OpenAI and Anthropic, standard tier; batch, fast mode, data residency "
        "and long-context rules applied where the export shows them).",
        "- Spend is normalised to 30 days. Rates measured on request logs are applied per model to the full "
        "aggregate spend.",
        "- **exact** = follows from list prices (e.g. a same-tier successor model is cheaper, including tokenizer "
        "differences); **measured** = replayed on your request logs; **scenario** = stated assumption, "
        "to be replaced by a measurement during the audit.",
        "- Prompt caching is replayed per model with the vendor's minimum cacheable length and cache lifetime, "
        "assuming the cache breakpoint sits at the end of the stable prefix.",
        "- Model changes (migration, routing) are only recommended where the eval set shows no quality drop.",
        "",
    ]
    if a.warnings:
        out += ["## Data notes", ""] + [f"- {w}" for w in a.warnings] + [""]
    out += [
        "## Next step",
        "",
        f"The fixed-price audit ({money(AUDIT_PRICE_USD)}) turns the scenario rows into measurements: 30 days of "
        "usage and prompt logs, a 100-query eval set that proves quality holds, code-level changes per lever and "
        f"a 2-hour working session. If the audit finds less than "
        f"{GUARANTEE_MULTIPLE}x its price in annual savings, you pay nothing.",
        "",
        f"Send a 30-day aggregate export to {CONTACT_EMAIL} (no prompts). Free estimate in 48 hours.",
        "",
    ]
    return "\n".join(out)


def render_eval_report(c: Comparison) -> str:
    body = _eval_section(c)
    body[0] = "# Eval comparison"
    return "\n".join(body) + "\n"


def to_json(a: Analysis) -> str:
    start, end, days = a.period

    def records(df: pd.DataFrame) -> list[dict]:
        return json.loads(df.to_json(orient="records"))

    payload = {
        "client": a.client,
        "generated_at": a.generated_at.isoformat(),
        "prices_verified_on": pricing.VERIFIED_ON.isoformat(),
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
        "monthly_spend_usd": a.monthly_spend,
        "saving_monthly_usd": a.combined,
        "saving_annual_usd": a.annual,
        "guarantee_met": a.guarantee_met,
        "levers": [
            {
                "key": lv.key,
                "title": lv.title,
                "low": lv.low,
                "base": lv.base,
                "high": lv.high,
                "method": lv.method,
                "evidence": lv.evidence,
            }
            for lv in a.levers
        ],
        "by_model": records(a.by_model),
        "by_workload": records(a.by_workload),
        "by_token_type": a.by_token_type,
        "warnings": a.warnings,
    }
    if a.eval_comparison is not None:
        ev = a.eval_comparison
        payload["eval"] = {
            "baseline_rate": ev.baseline.rate,
            "candidate_rate": ev.candidate.rate,
            "delta": ev.delta,
            "gate_pass": ev.gate_pass,
            "tolerance": ev.tolerance,
            "n": ev.baseline.n,
        }
    return json.dumps(payload, indent=2)
