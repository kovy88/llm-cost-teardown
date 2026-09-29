"""Synthetic sample exports for a fictional company ("Acme Helpdesk AI").

Produces files in the exact vendor formats the loader reads:
- openai_usage.json / anthropic_usage.json  vendor usage pages
- openai_costs.json / anthropic_costs.json  vendor cost pages
- requests.jsonl                            fingerprinted request log
- requests_raw_small.jsonl                  a few raw log lines, to demo `fingerprint`
- eval_set.jsonl / eval_baseline.jsonl / eval_candidate.jsonl  100-query quality gate

All text is random filler. Never put client data in data/samples/.
"""

import json
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from llm_cost_teardown.eval_samples import write_eval_samples
from llm_cost_teardown.fingerprint import fingerprint_log_line

WORDS = (
    "account billing invoice refund order shipping delay password reset login error plan upgrade "
    "downgrade cancel renew contract clause liability termination payment term notice party agreement "
    "customer ticket priority escalate resolve summary sentiment product feature request bug report "
    "integration api webhook export import dashboard report metric revenue pipeline lead deal quote "
    "discount region team member role permission policy data privacy retention security audit log"
).split()

BUSINESS_HOURS = [
    0.2,
    0.1,
    0.1,
    0.1,
    0.2,
    0.4,
    0.8,
    1.5,
    2.6,
    3.2,
    3.4,
    3.3,
    3.0,
    3.2,
    3.3,
    3.1,
    2.7,
    2.0,
    1.4,
    1.0,
    0.7,
    0.5,
    0.4,
    0.3,
]
NIGHTLY = [0.0, 6.0, 5.0, 1.0] + [0.0] * 20


@dataclass(frozen=True)
class Workload:
    name: str
    vendor: str
    model: str
    requests_per_day: int
    system_tokens: int
    user_tokens: int
    output_tokens: int
    tools_tokens: int = 0
    context_tokens: int = 0  # unique per request (retrieved docs, ticket body)
    session_context_tokens: int = 0  # shared by all turns of a session (a contract)
    turns: int = 1
    carry_history: bool = False
    reasoning_tokens: int = 0
    cache_hit_today: float = 0.0
    cache_write_today: float = 0.0
    hours: tuple[float, ...] = tuple(BUSINESS_HOURS)
    sample_rate: float = 0.05
    duplicate_rate: float = 0.0
    failure_rate: float = 0.0


WORKLOADS = [
    Workload(
        "proj_support_chat",
        "openai",
        "gpt-5.4-2026-03-05",
        9000,
        system_tokens=2000,
        tools_tokens=1500,
        user_tokens=120,
        output_tokens=300,
        reasoning_tokens=80,
        turns=4,
        carry_history=True,
        cache_hit_today=0.30,
        failure_rate=0.01,
    ),
    Workload(
        "proj_ticket_summaries",
        "openai",
        "gpt-4o-2024-08-06",
        4000,
        system_tokens=600,
        context_tokens=2200,
        user_tokens=40,
        output_tokens=250,
        hours=tuple(NIGHTLY),
        duplicate_rate=0.06,
    ),
    Workload(
        "proj_intent_router",
        "openai",
        "gpt-5-mini-2025-08-07",
        30000,
        system_tokens=700,
        user_tokens=150,
        output_tokens=190,
        reasoning_tokens=170,
        sample_rate=0.02,
    ),
    Workload(
        "proj_sales_copilot",
        "openai",
        "gpt-6-astra",
        1500,
        system_tokens=1800,
        tools_tokens=1200,
        context_tokens=3000,
        user_tokens=200,
        output_tokens=700,
        reasoning_tokens=300,
        cache_hit_today=0.35,
        cache_write_today=0.10,
        sample_rate=0.2,
    ),
    Workload(
        "wrkspc_rag_answers",
        "anthropic",
        "claude-sonnet-4-5-20250929",
        6000,
        system_tokens=2600,
        context_tokens=5000,
        user_tokens=200,
        output_tokens=450,
        sample_rate=0.1,
        failure_rate=0.005,
    ),
    Workload(
        "wrkspc_contract_review",
        "anthropic",
        "claude-opus-4-1-20250805",
        400,
        system_tokens=3000,
        session_context_tokens=18000,
        user_tokens=150,
        output_tokens=1800,
        turns=4,
        sample_rate=1.0,
    ),
    Workload(
        "wrkspc_email_drafts",
        "anthropic",
        "claude-haiku-4-5-20251001",
        5000,
        system_tokens=1200,
        context_tokens=600,
        user_tokens=80,
        output_tokens=280,
    ),
]


def _text(rng: random.Random, n_tokens: int) -> str:
    return " ".join(rng.choices(WORDS, k=max(1, int(n_tokens * 4 / 7))))


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _noisy(rng: random.Random, mean: float, spread: float = 0.35) -> int:
    return max(1, int(rng.lognormvariate(math.log(mean), spread)))


class _Static:
    """Per-workload fixed prompt parts (same bytes on every request)."""

    def __init__(self, w: Workload, rng: random.Random):
        self.system = f"You are the {w.name} assistant. " + _text(rng, w.system_tokens)
        self.tools = (
            [
                {
                    "type": "function",
                    "function": {"name": f"tool_{i}", "description": _text(rng, w.tools_tokens // 6), "parameters": {}},
                }
                for i in range(6)
            ]
            if w.tools_tokens
            else []
        )


def _request_body(w: Workload, static: _Static, content: list[str], history: list[tuple[str, str]]) -> dict:
    if w.vendor == "anthropic":
        messages = []
        for user, assistant in history:
            messages += [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
        messages.append({"role": "user", "content": [{"type": "text", "text": c} for c in content]})
        body = {"model": w.model, "max_tokens": 4096, "system": static.system, "messages": messages}
    else:
        messages = [{"role": "system", "content": static.system}]
        for user, assistant in history:
            messages += [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
        messages.append({"role": "user", "content": [{"type": "text", "text": c} for c in content]})
        body = {"model": w.model, "messages": messages}
    if static.tools:
        body["tools"] = static.tools
    return body


def _usage(w: Workload, body: dict, output: int, reasoning: int) -> dict:
    prompt = _tokens(json.dumps(body.get("tools", []))) if body.get("tools") else 0
    prompt += _tokens(body["system"]) if "system" in body else 0
    for m in body["messages"]:
        content = m["content"]
        prompt += sum(_tokens(c["text"]) for c in content) if isinstance(content, list) else _tokens(content)
    if w.vendor == "anthropic":
        return {
            "input_tokens": prompt,
            "output_tokens": output,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
            "service_tier": "standard",
        }
    cached = (int(prompt * w.cache_hit_today) // 128) * 128 if prompt >= 1024 else 0
    write = int(prompt * w.cache_write_today) if prompt >= 1024 else 0
    return {
        "prompt_tokens": prompt,
        "completion_tokens": output,
        "total_tokens": prompt + output,
        "prompt_tokens_details": {"cached_tokens": cached, "cache_write_tokens": write},
        "completion_tokens_details": {"reasoning_tokens": reasoning},
    }


def _start_time(rng: random.Random, w: Workload, day: datetime) -> datetime:
    hour = rng.choices(range(24), weights=w.hours)[0]
    return day + timedelta(hours=hour, seconds=rng.uniform(0, 3600))


def generate_requests(day: datetime, seed: int = 7) -> list[dict]:
    """Raw request-level log records (with request bodies) for one day, session-sampled."""
    rng = random.Random(seed)
    records = []
    for w in WORKLOADS:
        static = _Static(w, rng)
        sessions = max(1, round(w.requests_per_day * w.sample_rate / w.turns))
        for _ in range(sessions):
            t = _start_time(rng, w, day)
            session_ctx = _text(rng, _noisy(rng, w.session_context_tokens)) if w.session_context_tokens else None
            history: list[tuple[str, str]] = []
            for _turn in range(w.turns):
                content = [session_ctx] if session_ctx else []
                if w.context_tokens:
                    content.append(_text(rng, _noisy(rng, w.context_tokens)))
                content.append(_text(rng, _noisy(rng, w.user_tokens)))
                body = _request_body(w, static, content, history if w.carry_history else [])
                reasoning = _noisy(rng, w.reasoning_tokens) if w.reasoning_tokens else 0
                output = _noisy(rng, w.output_tokens - w.reasoning_tokens) + reasoning
                failed = rng.random() < w.failure_rate
                record = {
                    "timestamp": t.isoformat().replace("+00:00", "Z"),
                    "vendor": w.vendor,
                    "model": w.model,
                    "workload": w.name,
                    "sample_rate": w.sample_rate,
                    "status": "timeout" if failed else 200,
                    "usage": _usage(w, body, output, reasoning),
                    "request": body,
                }
                records.append(record)
                if failed or rng.random() < w.duplicate_rate:
                    retry = dict(
                        record,
                        status=200,
                        timestamp=(t + timedelta(seconds=rng.uniform(20, 900))).isoformat().replace("+00:00", "Z"),
                    )
                    records.append(retry)
                if w.carry_history:
                    history.append((content[-1], _text(rng, output - reasoning)))
                t += timedelta(seconds=rng.uniform(30, 180))
    records.sort(key=lambda r: r["timestamp"])
    return records


def _means(records: list[dict]) -> dict[str, dict[str, float]]:
    """Average per-request tokens by workload, from the request log, to keep both views consistent."""
    sums: dict[str, dict[str, float]] = {}
    for r in records:
        u = r["usage"]
        if "prompt_tokens" in u:
            cached = u["prompt_tokens_details"]["cached_tokens"]
            write = u["prompt_tokens_details"]["cache_write_tokens"]
            row = {"input": u["prompt_tokens"], "cached": cached, "write": write, "output": u["completion_tokens"]}
        else:
            row = {"input": u["input_tokens"], "cached": 0, "write": 0, "output": u["output_tokens"]}
        acc = sums.setdefault(r["workload"], {"n": 0, "input": 0, "cached": 0, "write": 0, "output": 0})
        acc["n"] += 1
        for k, v in row.items():
            acc[k] += v
    return {name: {k: v / acc["n"] for k, v in acc.items() if k != "n"} for name, acc in sums.items()}


def _pages(buckets: list[dict], per_page: int, cursor_prefix: str) -> list[dict]:
    pages = []
    for i in range(0, len(buckets), per_page):
        has_more = i + per_page < len(buckets)
        pages.append(
            {
                "data": buckets[i : i + per_page],
                "has_more": has_more,
                "next_page": f"{cursor_prefix}{i + per_page}" if has_more else None,
            }
        )
    return pages


def generate_usage_exports(start: datetime, days: int, means: dict[str, dict[str, float]], seed: int = 11):
    """OpenAI and Anthropic Usage API pages with hourly buckets."""
    rng = random.Random(seed)
    openai_buckets, anthropic_buckets = [], []
    for h in range(days * 24):
        t0 = start + timedelta(hours=h)
        weekday_factor = 0.55 if t0.weekday() >= 5 else 1.0
        oa, an = [], []
        for w in WORKLOADS:
            weight = w.hours[t0.hour] / sum(w.hours)
            factor = 1.0 if w.hours == tuple(NIGHTLY) else weekday_factor
            n = int(w.requests_per_day * weight * factor * rng.uniform(0.85, 1.15))
            if n == 0:
                continue
            m = means[w.name]
            total_in, cached, write = int(n * m["input"]), int(n * m["cached"]), int(n * m["write"])
            output = int(n * m["output"])
            if w.vendor == "openai":
                oa.append(
                    {
                        "object": "organization.usage.completions.result",
                        "input_tokens": total_in,
                        "input_cached_tokens": cached,
                        "input_cache_write_tokens": write,
                        "input_uncached_tokens": total_in - cached - write,
                        "output_tokens": output,
                        "input_audio_tokens": 0,
                        "output_audio_tokens": 0,
                        "num_model_requests": n,
                        "project_id": w.name,
                        "user_id": None,
                        "api_key_id": None,
                        "model": w.model,
                        "batch": False,
                        "service_tier": "default",
                    }
                )
            else:
                an.append(
                    {
                        "uncached_input_tokens": total_in,
                        "cache_creation": {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0},
                        "cache_read_input_tokens": 0,
                        "output_tokens": output,
                        "server_tool_use": {"web_search_requests": 0},
                        "account_id": None,
                        "api_key_id": None,
                        "workspace_id": w.name,
                        "model": w.model,
                        "service_tier": "standard",
                        "context_window": "0-200k",
                        "inference_geo": "not_available",
                    }
                )
        t1 = t0 + timedelta(hours=1)
        openai_buckets.append(
            {"object": "bucket", "start_time": int(t0.timestamp()), "end_time": int(t1.timestamp()), "results": oa}
        )
        anthropic_buckets.append(
            {
                "starting_at": t0.isoformat().replace("+00:00", "Z"),
                "ending_at": t1.isoformat().replace("+00:00", "Z"),
                "results": an,
            }
        )
    openai_pages = [dict(p, object="page") for p in _pages(openai_buckets, 168, "page_")]
    return openai_pages, _pages(anthropic_buckets, 168, "page_")


def generate_cost_exports(usage_paths: list[Path], seed: int = 11) -> tuple[dict, dict]:
    """Daily cost-report pages derived from the usage exports, with small billing noise per line."""
    from llm_cost_teardown.usage import load_usage

    rng = random.Random(seed)
    frame = load_usage(usage_paths).frame
    frame = frame.assign(day=frame["timestamp"].dt.floor("D"))
    daily = frame.groupby(["vendor", "day", "workload", "model"], as_index=False)["cost_usd"].sum()
    buckets: dict[str, dict[datetime, list[dict]]] = {"openai": {}, "anthropic": {}}
    for r in daily.itertuples():
        amount = r.cost_usd * rng.uniform(0.985, 1.02)
        if r.vendor == "openai":
            result = {
                "object": "organization.costs.result",
                "amount": {"value": round(amount, 6), "currency": "usd"},
                "line_item": f"{r.model}, input+output",
                "project_id": r.workload,
            }
        else:
            result = {
                "currency": "USD",
                "amount": f"{amount * 100:.4f}",
                "workspace_id": r.workload,
                "description": f"{r.model} tokens",
                "cost_type": "tokens",
                "model": r.model,
            }
        buckets[r.vendor].setdefault(r.day.to_pydatetime(), []).append(result)

    def iso(d: datetime) -> str:
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")

    openai_costs = {
        "object": "page",
        "data": [
            {
                "object": "bucket",
                "start_time": int(d.timestamp()),
                "end_time": int((d + timedelta(days=1)).timestamp()),
                "results": results,
            }
            for d, results in sorted(buckets["openai"].items())
        ],
        "has_more": False,
        "next_page": None,
    }
    anthropic_costs = {
        "data": [
            {"starting_at": iso(d), "ending_at": iso(d + timedelta(days=1)), "results": results}
            for d, results in sorted(buckets["anthropic"].items())
        ],
        "has_more": False,
        "next_page": None,
    }
    return openai_costs, anthropic_costs


def write_samples(out_dir: Path, end: datetime | None = None, days: int = 30) -> list[Path]:
    end = (end or datetime(2026, 9, 26, tzinfo=UTC)).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = generate_requests(end - timedelta(days=1))
    openai_pages, anthropic_pages = generate_usage_exports(start, days, _means(raw))
    paths = {
        "openai_usage.json": json.dumps(openai_pages, separators=(",", ":")),
        "anthropic_usage.json": json.dumps(anthropic_pages, separators=(",", ":")),
    }
    salt = b"synthetic-sample-salt"
    paths["requests.jsonl"] = "\n".join(json.dumps(fingerprint_log_line(r, salt)) for r in raw) + "\n"
    small = [r for r in raw if r["workload"] in ("proj_intent_router", "wrkspc_email_drafts")][:40]
    paths["requests_raw_small.jsonl"] = "\n".join(json.dumps(r) for r in small) + "\n"
    written = []
    for name, content in paths.items():
        path = out_dir / name
        path.write_text(content)
        written.append(path)
    openai_costs, anthropic_costs = generate_cost_exports(written[:2])
    for name, pages in (("openai_costs.json", openai_costs), ("anthropic_costs.json", anthropic_costs)):
        path = out_dir / name
        path.write_text(json.dumps(pages, separators=(",", ":")))
        written.append(path)
    written.extend(write_eval_samples(out_dir))
    return written
