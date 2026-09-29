import argparse
import json
import sys
from pathlib import Path

from llm_cost_teardown import pricing


def _analyze(args: argparse.Namespace) -> int:
    from llm_cost_teardown.analyzer import analyze, summary_text
    from llm_cost_teardown.report import render_markdown, to_json

    if (args.report or args.json) and pricing.is_stale() and not args.allow_stale_prices:
        print(
            f"Prices in pricing.py were verified on {pricing.VERIFIED_ON} ({pricing.age_days()} days ago). "
            "Re-verify them before writing a client report, or pass --allow-stale-prices.",
            file=sys.stderr,
        )
        return 2
    batchable = [w.strip() for w in args.batchable.split(",") if w.strip()] if args.batchable else []
    result = analyze(args.files, client=args.client, batchable=batchable)
    print(summary_text(result))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_markdown(result, internal=args.internal))
        print(f"\nReport written to {args.report}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(to_json(result))
        print(f"Summary JSON written to {args.json}")
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

    s = sub.add_parser("samples", help="Regenerate the synthetic sample exports")
    s.add_argument("--out", type=Path, default=Path("data/samples"))
    s.set_defaults(func=_samples)

    args = parser.parse_args()
    sys.exit(args.func(args))
