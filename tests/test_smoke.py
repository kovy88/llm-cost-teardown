import json
import subprocess
import sys

import pytest

from llm_cost_teardown.analyzer import analyze
from llm_cost_teardown.report import render_client_email, render_markdown, to_json
from llm_cost_teardown.samples import write_samples


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    out = tmp_path_factory.mktemp("samples")
    write_samples(out)
    return out


def sample_files(samples):
    return [samples / "openai_usage.json", samples / "anthropic_usage.json", samples / "requests.jsonl"]


def test_sample_costs_reconcile_with_usage(samples):
    a = analyze([*sample_files(samples)[:2], samples / "openai_costs.json", samples / "anthropic_costs.json"])
    rec = a.reconciliation.set_index("vendor")
    assert set(rec.index) == {"openai", "anthropic"}
    assert (rec["diff_pct"].abs() < 0.03).all()
    assert (rec["days"] == 30).all()


def test_samples_end_to_end(samples):
    a = analyze(sample_files(samples), client="Acme")
    assert 15_000 < a.monthly_spend < 25_000
    assert a.guarantee_met
    by_key = {lv.key: lv for lv in a.levers}
    assert by_key["migration"].method == "exact"
    assert by_key["caching"].method == "measured"
    assert by_key["duplicates"].method == "measured"
    assert a.combined["low"] <= a.combined["base"] <= a.combined["high"] < a.monthly_spend
    report = render_markdown(a)
    for heading in ("## Summary", "## Where the money goes", "## Savings levers", "## How the numbers were produced"):
        assert heading in report
    assert "guarantee threshold" not in report
    assert "guarantee threshold" in render_markdown(a, internal=True)
    assert json.loads(to_json(a))["monthly_spend_usd"] == pytest.approx(a.monthly_spend)
    email = render_client_email(a)
    assert "Acme" in email
    assert "Top lever:" in email
    assert "Annual base saving:" in email
    assert "koval.matej88@seznam.cz" in email
    assert "SUCCESSOR = {" in report
    assert "MAX_TOKENS = {" in report
    assert "BATCH_WORKLOADS" in report
    assert "cache_control" in report


def test_aggregates_only_still_produce_a_report(samples):
    a = analyze(sample_files(samples)[:2])
    assert a.requests.empty
    assert {lv.key: lv for lv in a.levers}["duplicates"].method == "not measured"
    assert a.combined["base"] > 0


def test_raw_requests_are_fingerprinted_on_load(samples):
    a = analyze([samples / "requests_raw_small.jsonl"])
    assert a.requests["prefix_hashes"].map(bool).all()


def test_cli_analyze_writes_report(samples, tmp_path):
    report = tmp_path / "r.md"
    cmd = [sys.executable, "-m", "llm_cost_teardown", "analyze", *map(str, sample_files(samples))]
    result = subprocess.run([*cmd, "--report", str(report)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Combined per year" in result.stdout
    assert report.read_text().startswith("# ")
