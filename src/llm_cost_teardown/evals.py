"""Score a 100-query eval set and gate model changes.

The scorer is deterministic: it does not call any model. You (or a client) produce the
outputs; this module only checks them against the agreed rubric and compares baseline
vs candidate. That is the quality proof the audit sells.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

EVAL_TOLERANCE = 0.02


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON") from exc
    return rows


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def check_passes(output: str, check: dict) -> bool:
    kind = check.get("type") or check.get("kind") or "contains"
    value = check.get("value")
    text = output or ""
    if kind == "exact":
        return _norm(text) == _norm(str(value))
    if kind == "contains":
        return _norm(str(value)) in _norm(text)
    if kind == "contains_all":
        values = value if isinstance(value, list) else [value]
        hay = _norm(text)
        return all(_norm(str(v)) in hay for v in values)
    if kind == "one_of":
        values = value if isinstance(value, list) else [value]
        needle = _norm(text)
        return any(needle == _norm(str(v)) for v in values)
    if kind == "json_field":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return False
        return str(payload.get(check["field"])) == str(value)
    raise ValueError(f"unknown check type {kind!r}")


@dataclass
class ItemScore:
    id: str
    workload: str
    passed: bool
    failed_checks: list[str]
    model: str = ""
    missing: bool = False


@dataclass
class EvalScore:
    n: int
    passed: int
    by_workload: dict[str, tuple[int, int]]
    items: list[ItemScore]
    models: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.passed / self.n if self.n else 0.0


@dataclass
class Comparison:
    baseline: EvalScore
    candidate: EvalScore
    tolerance: float = EVAL_TOLERANCE

    @property
    def delta(self) -> float:
        return self.candidate.rate - self.baseline.rate

    @property
    def gate_pass(self) -> bool:
        return self.candidate.rate + 1e-12 >= self.baseline.rate - self.tolerance


def score_records(cases: list[dict], results: list[dict]) -> EvalScore:
    by_id = {str(r["id"]): r for r in results if "id" in r}
    items: list[ItemScore] = []
    by_workload: dict[str, list[bool]] = defaultdict(list)
    models: list[str] = []
    for case in cases:
        cid = str(case["id"])
        workload = str(case.get("workload") or "all")
        rec = by_id.get(cid)
        if rec is None:
            item = ItemScore(cid, workload, False, ["missing output"], missing=True)
        else:
            output = str(rec.get("output") or "")
            failed = [
                f"{c.get('type') or c.get('kind')}:{c.get('field') or c.get('value')}"
                for c in case.get("checks") or []
                if not check_passes(output, c)
            ]
            model = str(rec.get("model") or "")
            if model:
                models.append(model)
            item = ItemScore(cid, workload, not failed, failed, model=model)
        items.append(item)
        by_workload[workload].append(item.passed)
    return EvalScore(
        n=len(items),
        passed=sum(i.passed for i in items),
        by_workload={k: (sum(v), len(v)) for k, v in by_workload.items()},
        items=items,
        models=sorted(set(models)),
    )


def score_paths(eval_set: Path, results: Path) -> EvalScore:
    return score_records(_read_jsonl(eval_set), _read_jsonl(results))


def compare_paths(
    eval_set: Path,
    baseline: Path,
    candidate: Path,
    tolerance: float = EVAL_TOLERANCE,
) -> Comparison:
    cases = _read_jsonl(eval_set)
    return Comparison(
        baseline=score_records(cases, _read_jsonl(baseline)),
        candidate=score_records(cases, _read_jsonl(candidate)),
        tolerance=tolerance,
    )


def _rate(score: EvalScore) -> str:
    return f"{score.rate:.0%} ({score.passed}/{score.n})"


def rate_label(score: EvalScore) -> str:
    return _rate(score)


def workload_rows(c: Comparison) -> list[tuple[str, str, str, str]]:
    workloads = sorted(set(c.baseline.by_workload) | set(c.candidate.by_workload))
    rows = []
    for w in workloads:
        b, cand = c.baseline.by_workload.get(w), c.candidate.by_workload.get(w)
        rows.append((w, _fmt_wl(b), _fmt_wl(cand), _fmt_delta(b, cand)))
    return rows


def regressions(c: Comparison) -> list[ItemScore]:
    passed_baseline = {item.id for item in c.baseline.items if item.passed}
    return [item for item in c.candidate.items if not item.passed and item.id in passed_baseline]


def _fmt_wl(pair: tuple[int, int] | None) -> str:
    if not pair:
        return "-"
    passed, n = pair
    return f"{passed / n:.0%} ({passed}/{n})"


def _fmt_delta(base: tuple[int, int] | None, cand: tuple[int, int] | None) -> str:
    if not base or not cand:
        return "-"
    delta = cand[0] / cand[1] - base[0] / base[1]
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.0%}"
