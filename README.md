# LLM Cost Teardown

Find out how much of your OpenAI / Anthropic API bill you can cut: in USD, per lever, from your own usage export. The analyzer runs on your machine, and your prompts never leave it.

## What the report looks like

Excerpt from [`docs/sample-report.md`](docs/sample-report.md). It was generated from a synthetic company ("Acme Helpdesk AI", 7 LLM features, about $19k/month):

|  | Per month | Per year |
| :--- | ---: | ---: |
| Current API spend | $19,114 | $229,368 |
| **Estimated saving (base, 48 % of spend)** | **$9,217** | **$110,605** |
| Range (conservative – optimistic) | $5,534 – $11,381 | $66,405 – $136,569 |

Biggest levers found in the sample:

- **Migration to the current same-tier model** saves $5,330/month. `claude-opus-4-1` → `claude-opus-5-5` alone is $3,270, after accounting for the new tokenizer's ~30 % more tokens.
- **Prompt caching** saves $4,265/month. This is measured by replaying the request log with each model's minimum cacheable length and cache lifetime.
- **Batch API** saves $555/month. The nightly ticket-summary job is detected from its hourly traffic shape.

Each number has a basis:

- **exact**: follows from list prices alone.
- **measured**: replayed on your logs.
- **scenario**: a stated assumption. The paid audit replaces these with measurements.

## Try it in 60 seconds

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url> && cd llm-cost-teardown
uv sync
uv run llm-cost-teardown samples      # writes synthetic exports to data/samples/
uv run llm-cost-teardown analyze data/samples/*.json data/samples/requests.jsonl --report report.md
```

## Run it on your own data

```bash
# 1. Export 30 days of usage + costs (read-only GET calls to the vendor's usage/cost reports)
OPENAI_ADMIN_KEY=sk-admin-... uv run llm-cost-teardown fetch openai --days 30
ANTHROPIC_ADMIN_KEY=sk-ant-admin-... uv run llm-cost-teardown fetch anthropic --days 30

# 2. Analyze (files land in data/private/, which is gitignored)
uv run llm-cost-teardown analyze data/private/*.json --report data/private/report.md
```

Aggregate exports alone give you:

- the full cost breakdown;
- the migration saving;
- batch candidates;
- scenario estimates for caching, routing and output trimming.

To get *measured* caching, duplicate-call and routing numbers, add a request log (a sample is enough). See [`docs/send-your-data.md`](docs/send-your-data.md).

## What it looks for

| Lever | From aggregate usage | With request logs |
| :--- | :--- | :--- |
| Migrate legacy models to the current same-tier model | exact (price table + tokenizer ratio) | exact |
| Prompt caching | scenario (skipped where prompts are below the cache minimum) | measured: replay with vendor minimum prefix and TTL (5 min / 1 h / 30 min) |
| Batch API (50 % off) | measured from hourly traffic shape | measured |
| Route simple calls to a cheaper tier | scenario | measured share of short, classification-like calls |
| Trim output / reasoning tokens | scenario (reasoning share shown) | scenario, with p50/p95 output length per feature |
| Duplicate calls and paid failures | not measured | measured: exact repeats within 24 h, failed calls |
| Fast / priority mode premium | exact, when the export shows the tier | exact |

Levers are stacked multiplicatively, so overlapping savings are never counted twice.

## Privacy

- **Aggregate exports** contain token counts per model, project/workspace and hour. They contain no prompt text.
- **Request logs** can be passed through `llm-cost-teardown fingerprint` before they leave your machine. The command:
  - replaces every prompt with keyed hashes of its cumulative blocks (tools, then system, then messages), using HMAC-SHA256 with a random salt that is never stored;
  - keeps character counts;
  - drops response text.

  The result still shows that two requests share their first 18,000 characters, but not what those characters say.
- **Admin keys** stay with you. `fetch` only calls the usage and cost report endpoints, and you decide which JSON files to send.

## How much to trust the numbers

- Prices live in one table, [`pricing.py`](src/llm_cost_teardown/pricing.py), with a `verified_on` date (currently 2026-09-29). The CLI refuses to write a report when the prices are more than 30 days old.
- Export field names and units are checked against the official `openai` and `anthropic` SDK types. The tests fail if a field disappears.
  - One vendor difference matters here: OpenAI's `input_tokens` *includes* cached tokens, while Anthropic's `input_tokens` *excludes* them.
- When you include the cost export, the report puts modelled cost next to invoiced cost, so any pricing gap is visible before a single saving is claimed.
- Known limits:
  - List prices only, so negotiated discounts and credits show up as a reconciliation gap.
  - Only chat/messages usage is priced. Embeddings, images and audio are skipped with a warning.
  - Long-context surcharges are only visible in request logs.

## The audit

The tool gives an estimate. The fixed-price audit turns it into savings on your invoice:

- **$1,900 fixed.** Covers 30 days of usage and prompt logs, a USD savings report, a 100-query eval set that proves quality holds, code-level changes per lever, and a 2-hour working session.
- **Guarantee:** if the audit finds less than 3× its price in annual savings, you pay nothing.
- **Proof:** your invoice for 30 days before vs. after, plus the eval score before vs. after.
- **Free first step:** send an aggregate export and get the savings estimate within 48 hours.

Contact: _add email / booking link_

## Development

```bash
uv sync
uv run ruff check --fix && uv run ruff format
uv run pytest
```

| Path | Content |
| :--- | :--- |
| `src/llm_cost_teardown/pricing.py` | Verified price table (the only place prices live) |
| `src/llm_cost_teardown/usage.py` | Loaders for OpenAI / Anthropic exports and request logs; pricing of each row |
| `src/llm_cost_teardown/estimators.py` | Savings levers and how they stack |
| `src/llm_cost_teardown/report.py` | Markdown / JSON report |
| `src/llm_cost_teardown/fetch.py` | Admin API export (stdlib only) |
| `src/llm_cost_teardown/fingerprint.py` | Prompt-free prefix hashing |
| `src/llm_cost_teardown/samples.py` | Synthetic sample company |
| `docs/data-formats.md` | Field-by-field mapping of every supported export |
