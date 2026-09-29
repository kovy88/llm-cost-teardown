# LLM cost teardown - Acme Helpdesk AI

_Generated 2026-09-29 · usage 2026-08-27 to 2026-09-26 (30 days) · list prices verified 2026-09-29_

## Summary

|  | Per month | Per year |
| :--- | ---: | ---: |
| Current API spend (30-day normalised) | $19,114 | $229,368 |
| **Estimated saving (base, 48% of spend)** | **$9,217** | **$110,605** |
| Range (conservative - optimistic) | $5,534 - $11,381 | $66,405 - $136,569 |

Biggest levers:

1. **Migrate legacy models to the current model of the same tier** - $5,330/month (follows from list prices alone)
2. **Prompt caching (stable prefix first, dynamic content last)** - $4,265/month (measured on your usage data)
3. **Trim output and reasoning tokens** - $783/month (scenario assumption on aggregate usage - to be measured in the audit)

Savings are stacked multiplicatively (each lever works on what the previous ones left), so the total is lower than the sum of the rows below. Every model change is validated on an eval set before rollout; the proof of saving is your invoice before vs after.

## Where the money goes

### By model

| Model | Vendor | Cost / month | Share | Requests / month | Input tokens | Cache hit | Output tokens |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `claude-sonnet-4-5` | anthropic | $5,324 | 28% | - | 1.4B | 0% | 76.5M |
| `claude-opus-4-1` | anthropic | $5,005 | 26% | - | 236.0M | 0% | 19.5M |
| `gpt-6-astra` | openai | $3,432 | 18% | 39.1k | 272.0M | 34% | 29.6M |
| `gpt-5.4` | openai | $3,147 | 16% | 237.9k | 1.1B | 29% | 75.3M |
| `gpt-4o` | openai | $1,234 | 6% | 119.2k | 375.0M | 0% | 29.7M |
| `gpt-5-mini` | openai | $506 | 3% | 790.7k | 742.2M | 0% | 160.0M |
| `claude-haiku-4-5` | anthropic | $466 | 2% | - | 270.6M | 0% | 39.2M |

### By workload (project / workspace / feature)

| Workload | Vendor | Main model | Cost / month | Share |
| :--- | :--- | :--- | ---: | ---: |
| `wrkspc_rag_answers` | anthropic | `claude-sonnet-4-5` | $5,324 | 28% |
| `wrkspc_contract_review` | anthropic | `claude-opus-4-1` | $5,005 | 26% |
| `proj_sales_copilot` | openai | `gpt-6-astra` | $3,432 | 18% |
| `proj_support_chat` | openai | `gpt-5.4` | $3,147 | 16% |
| `proj_ticket_summaries` | openai | `gpt-4o` | $1,234 | 6% |
| `proj_intent_router` | openai | `gpt-5-mini` | $506 | 3% |
| `wrkspc_email_drafts` | anthropic | `claude-haiku-4-5` | $466 | 2% |

### By token type

| Token type | Cost / month | Share |
| :--- | ---: | ---: |
| Uncached input | $12,572 | 66% |
| Cache reads | $171 | 1% |
| Cache writes | $340 | 2% |
| Output (incl. reasoning) | $6,031 | 32% |

## Savings levers

| # | Lever | Conservative | Base | Optimistic | Basis |
| ---: | :--- | ---: | ---: | ---: | :--- |
| 1 | Migrate legacy models to the current model of the same tier | $2,665 | $5,330 | $5,330 | exact |
| 2 | Route simple requests to a cheaper model tier | $12 | $24 | $1,475 | measured |
| 3 | Prompt caching (stable prefix first, dynamic content last) | $2,666 | $4,265 | $5,331 | measured |
| 4 | Batch API for non-interactive workloads (50 % off) | $309 | $555 | $1,511 | measured |
| 5 | Trim output and reasoning tokens | $391 | $783 | $1,476 | scenario |
| 6 | Remove duplicate calls and paid failures | $73 | $118 | $151 | measured |

### 1. Migrate legacy models to the current model of the same tier

_Basis: follows from list prices alone._

- `claude-opus-4-1` -> `claude-opus-5-5`: $5,005 -> $1,735 per month (token count x1.30 for the newer tokenizer).
- `claude-sonnet-4-5` -> `claude-sonnet-5-5`: $5,324 -> $4,614 per month (token count x1.30 for the newer tokenizer).
- `gpt-4o` -> `gpt-6.1-sol`: $1,234 -> $1,047 per month.
- `gpt-5-mini` -> `gpt-6-luna`: $506 -> $154 per month.
- `gpt-5.4` -> `gpt-6.1-sol`: $3,147 -> $2,336 per month.

| From | To | Monthly cost now | Base saving / month |
| :--- | :--- | ---: | ---: |
| `claude-opus-4-1` | `claude-opus-5-5` | $5,005 | $3,270 |
| `gpt-5.4` | `gpt-6.1-sol` | $3,147 | $811 |
| `claude-sonnet-4-5` | `claude-sonnet-5-5` | $5,324 | $710 |
| `gpt-5-mini` | `gpt-6-luna` | $506 | $351 |
| `gpt-4o` | `gpt-6.1-sol` | $1,234 | $188 |

What to change:

- Swap the model id behind a feature flag, run the eval set on old vs new model, then roll out.
- Re-check output length after the switch; newer models can be more verbose or reason longer.

### 2. Route simple requests to a cheaper model tier

_Basis: measured on your usage data._

- `claude-opus-4-1`, `claude-sonnet-4-5`, `gpt-4o`, `gpt-5.4`, `gpt-6-astra`: under 5% of spend is short, classification-like calls; routing here depends on which features the eval set shows the cheaper tier can handle.
- Conservative / base count only the measured short calls; optimistic adds 15% of traffic (easy long-form requests) that the eval set may clear for the cheaper tier.

| From | To | Monthly cost now | Base saving / month |
| :--- | :--- | ---: | ---: |
| `gpt-5.4` | `gpt-6-luna` | $2,336 | $16 |
| `gpt-4o` | `gpt-6-luna` | $1,047 | $8.72 |

What to change:

- Add a router (rules on task type / prompt length, or a small classifier) in front of the model call.
- Accept the route only where the eval-set score of the cheaper model stays within tolerance.

### 3. Prompt caching (stable prefix first, dynamic content last)

_Basis: measured on your usage data._

- `claude-haiku-4-5`: no repeated prefix reaches the 4,096-token cache minimum; caching does not pay here unless the shared instructions grow.
- `claude-opus-4-1`: cache hits today 0% of input tokens; replaying the logs with stable prefixes (5 min TTL) saves 45% of this model's spend.
- `claude-sonnet-4-5`: cache hits today 0% of input tokens; replaying the logs with stable prefixes (1 h TTL) saves 22% of this model's spend.
- `gpt-4o`: no repeated prefix reaches the 1,024-token cache minimum; caching does not pay here unless the shared instructions grow.
- `gpt-5-mini`: no repeated prefix reaches the 1,024-token cache minimum; caching does not pay here unless the shared instructions grow.
- `gpt-5.4`: cache hits today 29% of input tokens; replaying the logs with stable prefixes (30 min TTL) saves 48% of this model's spend.
- `gpt-6-astra`: cache hits today 34% of input tokens; replaying the logs with stable prefixes (30 min TTL) saves 11% of this model's spend.

| Model | Monthly cost | Base saving / month |
| :--- | ---: | ---: |
| `claude-opus-4-1` | $5,005 | $1,803 |
| `gpt-5.4` | $3,147 | $1,196 |
| `claude-sonnet-4-5` | $5,324 | $951 |
| `gpt-6-astra` | $3,432 | $306 |
| `gpt-4o` | $1,234 | $9.37 |

What to change:

- Order every prompt as tools -> system prompt -> static context -> conversation -> dynamic input.
- Remove timestamps, request ids and per-user data from the system prompt; pass them at the end.
- Anthropic: put `cache_control` on the last static block (or top-level automatic caching for chats).
- OpenAI: keep prefixes byte-identical; set a stable `prompt_cache_key` per prompt template.

### 4. Batch API for non-interactive workloads (50 % off)

_Basis: measured on your usage data._

- `proj_ticket_summaries` (openai): 100% of traffic falls in its 3 busiest hours of the day - looks like a scheduled job.
- Other workloads look interactive. If any of them does not need an answer within seconds, batching it saves up to: `wrkspc_rag_answers` ($2,662), `wrkspc_contract_review` ($2,503), `proj_sales_copilot` ($1,716) per month.

| Workload | Vendor | Saving if fully batched | Base saving / month |
| :--- | :--- | ---: | ---: |
| `proj_ticket_summaries` | openai | $617 | $555 |

What to change:

- Move scheduled / back-office jobs (summaries, enrichment, evals, embeddings refresh) to the Batch API.
- Keep user-facing chat on the synchronous API; batch results arrive within 24 h.

### 5. Trim output and reasoning tokens

_Basis: scenario assumption on aggregate usage - to be measured in the audit._

- `gpt-5-mini`: 90% of output tokens are reasoning tokens.
- `gpt-6-astra`: 42% of output tokens are reasoning tokens.
- `proj_intent_router`: visible output p50 20 / p95 35 tokens.
- `proj_sales_copilot`: visible output p50 412 / p95 720 tokens.
- `proj_support_chat`: visible output p50 212 / p95 418 tokens.
- `proj_ticket_summaries`: visible output p50 230 / p95 407 tokens.
- `wrkspc_contract_review`: visible output p50 1,763 / p95 3,226 tokens.
- `wrkspc_email_drafts`: visible output p50 288 / p95 467 tokens.
- `wrkspc_rag_answers`: visible output p50 452 / p95 789 tokens.
- Scenario: output spend reduced by 5% / 10% / 20% (20% base where reasoning dominates).

| Model | Output spend / month | Base saving / month |
| :--- | ---: | ---: |
| `gpt-6-astra` | $1,478 | $296 |
| `claude-opus-4-1` | $1,465 | $147 |
| `claude-sonnet-4-5` | $1,147 | $115 |
| `gpt-5.4` | $1,129 | $113 |
| `gpt-5-mini` | $320 | $64 |
| `gpt-4o` | $297 | $30 |
| `claude-haiku-4-5` | $196 | $20 |

What to change:

- Set `max_tokens` / `max_output_tokens` per endpoint from the observed p95, not the model maximum.
- Ask for structured output (JSON schema) instead of prose where the answer is parsed by code.
- Lower reasoning effort on routine tasks; reserve high effort for the hard tail.

### 6. Remove duplicate calls and paid failures

_Basis: measured on your usage data._

- `gpt-4o`: 6.7% of spend is exact repeats within 24 h, 0.0% is failed calls.
- `gpt-5.4`: 0.7% of spend is exact repeats within 24 h, 0.7% is failed calls.

| Model | Monthly cost | Base saving / month |
| :--- | ---: | ---: |
| `gpt-4o` | $1,234 | $66 |
| `gpt-5.4` | $3,147 | $27 |
| `claude-sonnet-4-5` | $5,324 | $25 |

What to change:

- Cache identical requests in the application (hash of model + prompt + params) for deterministic tasks.
- Make retries idempotent; cap retries and stop re-sending the full prompt on client-side timeouts.

## Check against the invoice

| Vendor | Days | Invoiced (cost export) | Modelled from usage | Difference |
| :--- | ---: | ---: | ---: | ---: |
| anthropic | 30 | $10,821 | $10,796 | -0.2% |
| openai | 30 | $8,346 | $8,318 | -0.3% |

Differences come from negotiated discounts, credits, long-context surcharges on aggregate data and usage types outside chat/messages (embeddings, images, audio).

## Quality gate (eval set)

100 queries scored with a deterministic rubric (exact match, required phrases). The set is built with the client from sampled traffic; production prompts stay on their machine.

|  | Pass rate | Models |
| :--- | :--- | :--- |
| Baseline (current) | 92% (92/100) | `claude-haiku-4-5`, `claude-opus-4-1`, `claude-sonnet-4-5`, `gpt-4o`, `gpt-5-mini`, `gpt-5.4`, `gpt-6-astra` |
| Candidate (after levers) | 94% (94/100) | `claude-haiku-4-5`, `claude-opus-5-5`, `claude-sonnet-5-5`, `gpt-6-astra`, `gpt-6-luna`, `gpt-6.1-sol` |
| **Delta / gate (tolerance 2%)** | **+2% · PASS** | candidate must stay within tolerance of baseline |

### By workload

| Workload | Baseline | Candidate | Delta |
| :--- | ---: | ---: | ---: |
| `proj_intent_router` | 88% (22/25) | 92% (23/25) | +4% |
| `proj_sales_copilot` | 100% (5/5) | 100% (5/5) | +0% |
| `proj_support_chat` | 89% (16/18) | 94% (17/18) | +6% |
| `proj_ticket_summaries` | 93% (14/15) | 93% (14/15) | +0% |
| `wrkspc_contract_review` | 100% (10/10) | 100% (10/10) | +0% |
| `wrkspc_email_drafts` | 92% (11/12) | 92% (11/12) | +0% |
| `wrkspc_rag_answers` | 93% (14/15) | 93% (14/15) | +0% |

No regressions: every query the baseline passed, the candidate passed too.

## How the numbers were produced

- Usage is priced with per-model list prices read from the vendor pricing pages on 2026-09-29 (OpenAI and Anthropic, standard tier; batch, fast mode, data residency and long-context rules applied where the export shows them).
- Spend is normalised to 30 days. Rates measured on request logs are applied per model to the full aggregate spend.
- **exact** = follows from list prices (e.g. a same-tier successor model is cheaper, including tokenizer differences); **measured** = replayed on your request logs; **scenario** = stated assumption, to be replaced by a measurement during the audit.
- Prompt caching is replayed per model with the vendor's minimum cacheable length and cache lifetime, assuming the cache breakpoint sits at the end of the stable prefix.
- Model changes (migration, routing) are only recommended where the eval set shows no quality drop.

## Next step

The fixed-price audit ($1,900) turns the scenario rows into measurements: 30 days of usage and prompt logs, a 100-query eval set that proves quality holds, code-level changes per lever and a 2-hour working session. If the audit finds less than 3x its price in annual savings, you pay nothing.

Send a 30-day aggregate export to koval.matej88@seznam.cz (no prompts). Free estimate in 48 hours.
