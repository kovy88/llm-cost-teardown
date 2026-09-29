import json
import subprocess
import sys
from pathlib import Path

from llm_cost_teardown.analyzer import analyze
from llm_cost_teardown.eval_samples import build_eval_bundle, write_eval_samples
from llm_cost_teardown.evals import check_passes, compare_paths, regressions, score_records
from llm_cost_teardown.report import render_eval_report, render_markdown
from llm_cost_teardown.samples import write_samples


def test_check_types():
    assert check_passes("Password_Reset", {"type": "exact", "value": "password_reset"})
    assert check_passes("Refund order 1842 today", {"type": "contains_all", "value": ["1842", "refund"]})
    assert not check_passes("hello", {"type": "contains_all", "value": ["1842", "refund"]})
    assert check_passes("billing_question", {"type": "one_of", "value": ["billing_question", "refund"]})
    assert check_passes('{"intent": "refund"}', {"type": "json_field", "field": "intent", "value": "refund"})


def test_missing_result_fails():
    cases = [{"id": "a", "workload": "w", "checks": [{"type": "exact", "value": "yes"}]}]
    score = score_records(cases, [])
    assert score.n == 1 and score.passed == 0
    assert score.items[0].missing


def test_sample_eval_is_100_and_gate_passes(tmp_path: Path):
    cases, baseline, candidate = build_eval_bundle()
    assert len(cases) == 100
    written = write_eval_samples(tmp_path)
    assert {p.name for p in written} == {"eval_set.jsonl", "eval_baseline.jsonl", "eval_candidate.jsonl"}
    comparison = compare_paths(*written)
    assert comparison.baseline.n == 100
    assert comparison.candidate.rate >= comparison.baseline.rate
    assert comparison.gate_pass
    assert not regressions(comparison)
    assert 0.85 <= comparison.baseline.rate <= 0.97
    md = render_eval_report(comparison)
    assert "PASS" in md
    assert "No regressions" in md


def test_gate_fails_when_candidate_drops(tmp_path: Path):
    cases = [
        {"id": "1", "workload": "w", "checks": [{"type": "exact", "value": "ok"}]},
        {"id": "2", "workload": "w", "checks": [{"type": "exact", "value": "ok"}]},
    ]
    (tmp_path / "set.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cases))
    (tmp_path / "base.jsonl").write_text('{"id":"1","output":"ok"}\n{"id":"2","output":"ok"}\n')
    (tmp_path / "cand.jsonl").write_text('{"id":"1","output":"ok"}\n{"id":"2","output":"no"}\n')
    comparison = compare_paths(tmp_path / "set.jsonl", tmp_path / "base.jsonl", tmp_path / "cand.jsonl")
    assert not comparison.gate_pass
    assert len(regressions(comparison)) == 1


def test_analyze_embeds_eval(tmp_path: Path):
    out = tmp_path / "s"
    write_samples(out)
    comparison = compare_paths(out / "eval_set.jsonl", out / "eval_baseline.jsonl", out / "eval_candidate.jsonl")
    a = analyze(
        [out / "openai_usage.json", out / "anthropic_usage.json", out / "requests.jsonl"],
        client="Acme",
        eval_comparison=comparison,
    )
    report = render_markdown(a)
    assert "## Quality gate (eval set)" in report
    assert "koval.matej88@seznam.cz" in report
    assert "PASS" in report


def test_eval_jsonl_is_not_loaded_as_usage(tmp_path: Path):
    write_samples(tmp_path)
    a = analyze([tmp_path / "openai_usage.json", tmp_path / "eval_set.jsonl", tmp_path / "eval_baseline.jsonl"])
    assert a.requests.empty
    assert a.monthly_spend > 0


def test_cli_eval_gate(tmp_path: Path):
    write_eval_samples(tmp_path)
    cmd = [
        sys.executable,
        "-m",
        "llm_cost_teardown",
        "eval",
        str(tmp_path / "eval_set.jsonl"),
        str(tmp_path / "eval_baseline.jsonl"),
        "--candidate",
        str(tmp_path / "eval_candidate.jsonl"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "PASS" in result.stdout
