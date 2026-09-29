# Offer: LLM Cost Teardown

**For:** CTOs / founders of SaaS and AI products spending 3,000–100,000 USD per month on OpenAI and/or Anthropic APIs.
**Price:** 1,900 USD fixed.
**Guarantee:** if the audit finds less than 3× its price (5,700 USD) in annual savings, you pay nothing.
**Optional implementation:** a fixed price, or 25 % of the first 12 months of savings (20–30 % depending on scope).

## Free first step: estimate in 48 hours

1. You export 30 days of aggregate usage with one command. The admin key stays with you, and there is no prompt text. See [send-your-data.md](send-your-data.md).
2. Within 48 h you get a report like [sample-report.md](sample-report.md):
   - current spend by model, feature and token type;
   - the saving per lever as a low / base / high range;
   - the basis for each lever: exact, measured or scenario.
3. If the saving is not worth acting on, the report says so, and we stop there.

## The audit (about 2 weeks)

| Deliverable | What it is |
| :--- | :--- |
| Savings report in USD | Every lever measured on your request logs (fingerprinted, no prompt text), per feature, reconciled against your cost export |
| 100-query eval set | Built from your real traffic, with a scoring rubric agreed with you. It gates every model change (migration, routing, shorter output) |
| Code-level changes | Concrete diffs or PR descriptions per lever: prompt reordering for caching, `cache_control` / `prompt_cache_key`, batch job, router rules, `max_tokens` limits |
| 2 h working session | Walk through the levers with your team and agree the rollout order |
| Proof plan | Invoice comparison 30 days before vs. after, and eval score before vs. after |

## Levers

1. **Model migration:** move to the current model of the same tier. The saving is exact from list prices, and the tokenizer difference is included (Claude's newer tokenizer produces about 30 % more tokens).
2. **Prompt caching:** stable prefix first, dynamic content last, with the right breakpoints and TTL. It is replayed per model with the vendor's minimum cacheable length and cache lifetime.
3. **Batch API (50 % off):** for scheduled and back-office workloads. These are detected from the hourly traffic shape.
4. **Model routing:** send short, classification-like calls to a cheaper tier, but only where the eval set shows no quality drop.
5. **Output and reasoning trimming:** `max_tokens` set from the observed p95, structured output, and lower reasoning effort on routine tasks.
6. **Duplicate calls and paid failures:** exact repeats within 24 h, retries and discarded results.
7. **Fast / priority mode:** keep the premium only on the latency-critical path.

## Why not a gateway dashboard

Gateways and observability tools (LiteLLM, Helicone, TrueFoundry…) show where the money goes. This audit changes the code that spends it and proves with an eval set that quality did not drop. The proof of saving is your invoice, not a dashboard.

## Not included

- Access to your production systems or accounts. We work only from exports you send.
- Ongoing monitoring. That is available as a separate retainer if wanted.
- Fine-tuning or self-hosting projects. These may be recommended, but they are scoped separately.

## Evidence to cite (verify each source before using it)

- ProjectDiscovery: 59 % LLM cost cut via caching (their April 2026 blog)
- RouteLLM (ICLR 2025): 95 % of GPT-4 quality while routing only 14–26 % of queries to the strong model
