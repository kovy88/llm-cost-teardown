# Channel copy (paste, then post)

Nothing here claims a paying client. The only numbers are from the synthetic Acme report.

## LinkedIn

Where a $19k/month LLM bill actually goes.

I priced a synthetic helpdesk (7 features, OpenAI + Anthropic, 30 days) with a local analyzer. Spend: $19,114/month. Stacked saving: $9,217/month, about 48%. Three lines:

1. Same-tier migration, $5,330/month. Exact from list prices. Opus 4.1 to Opus 5.5 is most of it, after a 1.30x token count for the newer Claude tokenizer. Skip the tokenizer and you overstate the saving.
2. Prompt caching, $4,265/month. Measured by replaying the request log against each model's minimum cacheable prefix. Anthropic cache hit in the sample was 0%.
3. Batch API, $555/month. The nightly summary job shows up as two night hours.

Gateways draw the $19k. They do not move the cache breakpoint, put the night job on Batch, or prove the new model still passes a 100-query eval. On the sample set: 92% to 94%, no regressions.

The tool runs on your machine. Aggregate export has no prompts. If the annual saving is under about $6k, the $1,900 audit is the wrong product and the report says so.

Repo and sample report: https://github.com/kovy88/llm-cost-teardown

## Show HN

Title: Show HN: LLM Cost Teardown – USD savings from an OpenAI/Anthropic usage export

I got tired of cost dashboards that stop at a chart. This is a local CLI: it reads the vendor usage and cost exports (read-only, no prompts), prices seven levers, and stacks them so overlapping savings are not added twice.

Migration is exact from the price table, including the Claude tokenizer ratio. Caching is a replay of the request log with each model's minimum prefix and TTL. Batch candidates come from the hourly traffic shape. A separate eval command scores a frozen 100-query set; the gate fails if the candidate pass rate drops more than 2 percentage points. The scorer does not call a model.

Synthetic company in the README ("Acme Helpdesk AI", about $19k/month, 48% stacked base saving): https://github.com/kovy88/llm-cost-teardown

```
uv sync
uv run llm-cost-teardown samples
uv run llm-cost-teardown analyze data/samples/*.json data/samples/requests.jsonl --report report.md
```

On a real account: `llm-cost-teardown fetch openai --days 30` with an admin key that stays on your machine.

I also do this as a fixed $1,900 audit (free estimate from the aggregate export, pay nothing if annual savings are under 3x). Happy to hear where the pricing or the cache replay is wrong.

## Upwork / Malt project

Title: OpenAI / Anthropic API cost audit, fixed price

I estimate what your LLM API bill can drop, in USD, from a 30-day usage export. The admin key stays with you. The export is token counts, not prompts.

Fixed price after the free estimate: $1,900.
If the audit finds less than $5,700 a year in savings, you pay nothing.
You get a savings report, a 100-query eval set that gates model changes, concrete code changes (cache breakpoints, batch job, routing, max_tokens), and a 2-hour working session.

Free first step: one read-only export, estimate in 48 hours. Sample report: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

Search jobs for: OpenAI, Anthropic, LLM, RAG, chatbot, token cost. Quote the fixed price. Do not bid hourly.
