import argparse
import json
import sys
from pathlib import Path

from llm_cost_teardown import pricing


def _analyze(args: argparse.Namespace) -> int:
    from llm_cost_teardown.analyzer import analyze, summary_text
    from llm_cost_teardown.report import render_client_email, render_markdown, to_json

    if (args.report or args.json) and pricing.is_stale() and not args.allow_stale_prices:
        print(
            f"Prices in pricing.py were verified on {pricing.VERIFIED_ON} ({pricing.age_days()} days ago). "
            "Re-verify them before writing a client report, or pass --allow-stale-prices.",
            file=sys.stderr,
        )
        return 2
    batchable = [w.strip() for w in args.batchable.split(",") if w.strip()] if args.batchable else []
    eval_comparison = None
    eval_flags = (args.eval_set, args.eval_baseline, args.eval_candidate)
    if any(eval_flags) and not all(eval_flags):
        print(
            "--eval-set, --eval-baseline and --eval-candidate must be passed together.",
            file=sys.stderr,
        )
        return 2
    if all(eval_flags):
        from llm_cost_teardown.evals import compare_paths

        eval_comparison = compare_paths(
            args.eval_set, args.eval_baseline, args.eval_candidate, tolerance=args.eval_tolerance
        )
    result = analyze(args.files, client=args.client, batchable=batchable, eval_comparison=eval_comparison)
    print(summary_text(result))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_markdown(result, internal=args.internal))
        print(f"\nReport written to {args.report}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(to_json(result))
        print(f"Summary JSON written to {args.json}")
    if args.email:
        print("\n--- email ---\n")
        print(render_client_email(result))
    return 0


def _fetch(args: argparse.Namespace) -> int:
    from llm_cost_teardown.fetch import fetch_anthropic, fetch_openai

    exports = fetch_openai(args.days) if args.vendor == "openai" else fetch_anthropic(args.days)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, pages in exports.items():
        path = args.out / name
        path.write_text(json.dumps(pages))
        print(f"{path}: {len(pages)} page(s)")
    return 0


def _fingerprint(args: argparse.Namespace) -> int:
    from llm_cost_teardown.fingerprint import fingerprint_log_line, new_salt

    salt = new_salt()
    n = 0
    with args.output.open("w") as dst:
        for path in args.inputs:
            with path.open() as src:
                for line in src:
                    if line.strip():
                        dst.write(json.dumps(fingerprint_log_line(json.loads(line), salt)) + "\n")
                        n += 1
    print(f"{n} lines fingerprinted -> {args.output} (prompt and response text removed; salt not stored)")
    return 0


def _eval(args: argparse.Namespace) -> int:
    from llm_cost_teardown.evals import compare_paths, rate_label, score_paths
    from llm_cost_teardown.report import render_eval_report, table

    if args.candidate:
        comparison = compare_paths(args.eval_set, args.results, args.candidate, tolerance=args.tolerance)
        print(
            f"Eval gate: {rate_label(comparison.baseline)} -> {rate_label(comparison.candidate)} "
            f"({'+' if comparison.delta >= 0 else ''}{comparison.delta:.0%}, "
            f"{'PASS' if comparison.gate_pass else 'FAIL'})"
        )
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(render_eval_report(comparison))
            print(f"Report written to {args.report}")
        return 0 if comparison.gate_pass else 1
    score = score_paths(args.eval_set, args.results)
    print(f"Pass rate: {rate_label(score)}")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            [f"`{w}`", f"{passed}/{n}", f"{passed / n:.0%}"] for w, (passed, n) in sorted(score.by_workload.items())
        ]
        args.report.write_text(
            "# Eval score\n\n"
            + table(["Workload", "Passed", "Rate"], rows, "lrr")
            + f"\n\nOverall: {rate_label(score)}\n"
        )
        print(f"Report written to {args.report}")
    return 0


def _eval_init(args: argparse.Namespace) -> int:
    from llm_cost_teardown.evals import init_eval_set

    rows = init_eval_set(args.files, args.output)
    print(f"{len(rows)} skeleton cases written to {args.output} (fill input and checks before scoring)")
    return 0


def _samples(args: argparse.Namespace) -> int:
    from llm_cost_teardown.samples import write_samples

    for path in write_samples(args.out):
        print(path)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="llm-cost-teardown", description="Find savings in LLM API spend.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="Estimate savings from usage exports and/or request logs")
    a.add_argument("files", nargs="+", type=Path, help="Usage API JSON, cost JSON, request-log JSONL or CSV")
    a.add_argument("--client", default="", help="Client name for the report title")
    a.add_argument("--batchable", help="Comma-separated workloads confirmed as non-interactive")
    a.add_argument("--report", type=Path, help="Write a Markdown report here")
    a.add_argument("--json", type=Path, help="Write a machine-readable summary here")
    a.add_argument("--internal", action="store_true", help="Include the guarantee check in the report")
    a.add_argument("--allow-stale-prices", action="store_true")
    a.add_argument("--email", action="store_true", help="Print the three-line client reply")
    a.add_argument("--eval-set", type=Path, help="Eval JSONL (id, workload, input, checks)")
    a.add_argument("--eval-baseline", type=Path, help="Baseline model outputs JSONL")
    a.add_argument("--eval-candidate", type=Path, help="Candidate model outputs JSONL")
    a.add_argument("--eval-tolerance", type=float, default=0.02, help="Max allowed drop in pass rate")
    a.set_defaults(func=_analyze)

    f = sub.add_parser("fetch", help="Export 30 days of usage + costs via the vendor Admin API")
    f.add_argument("vendor", choices=["openai", "anthropic"])
    f.add_argument("--days", type=int, default=30)
    f.add_argument("--out", type=Path, default=Path("data/private"))
    f.set_defaults(func=_fetch)

    fp = sub.add_parser("fingerprint", help="Strip prompt text from request logs, keep prefix hashes")
    fp.add_argument("inputs", nargs="+", type=Path, help="All logs in one run: hashes only match within a run")
    fp.add_argument("-o", "--output", type=Path, required=True)
    fp.set_defaults(func=_fingerprint)

    e = sub.add_parser("eval", help="Score model outputs against an eval set; compare baseline vs candidate")
    e.add_argument("eval_set", type=Path, help="Eval JSONL with id, input and checks")
    e.add_argument("results", type=Path, help="JSONL with id, model, output (baseline if --candidate is set)")
    e.add_argument("--candidate", type=Path, help="Candidate outputs; compare against results as baseline")
    e.add_argument("--tolerance", type=float, default=0.02)
    e.add_argument("--report", type=Path)
    e.set_defaults(func=_eval)

    init = sub.add_parser("eval-init", help="Write an empty eval JSONL, one case per workload (max 100)")
    init.add_argument("files", nargs="+", type=Path, help="Usage exports to read workload names from")
    init.add_argument("-o", "--output", type=Path, required=True)
    init.set_defaults(func=_eval_init)

    s = sub.add_parser("samples", help="Regenerate the synthetic sample exports")
    s.add_argument("--out", type=Path, default=Path("data/samples"))
    s.set_defaults(func=_samples)

    args = parser.parse_args()
    sys.exit(args.func(args))
