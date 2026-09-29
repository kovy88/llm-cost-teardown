# Data formats

How every supported export maps onto the normalised frame in `usage.py`. Field names and units are verified against the sources listed below, not against vendor prose docs. Re-check them when you bump the `openai` or `anthropic` SDK. `tests/test_schema_vs_sdk.py` fails if a field the loaders read disappears from the SDK types.

## Normalised frame

There is one row per aggregate bucket (`granularity = "bucket"`) or per logged request (`granularity = "request"`).

| Column | Meaning |
| :--- | :--- |
| `timestamp`, `bucket_seconds` | Bucket start (UTC) and width; 0 for requests |
| `vendor`, `model`, `model_key` | Raw model id and the normalised key into `pricing.PRICES` |
| `workload` | OpenAI `project_id` (else `api_key_id` / `user_id`), Anthropic `workspace_id` (else `api_key_id`), or the log's `workload` / `feature` |
| `service_tier` | `standard`, `batch`, `flex`, `fast`, `priority`, `scale` |
| `inference_geo` | Anthropic only; `us` costs 1.1x |
| `requests` | OpenAI `num_model_requests`; NaN for Anthropic buckets (the report has no request count); 1 for log lines |
| `uncached_input_tokens` | Input billed at the full input rate |
| `cache_read_tokens` | Input served from cache |
| `cache_write_tokens` | Input written to cache (Anthropic: 5-minute TTL; OpenAI: any) |
| `cache_write_1h_tokens` | Anthropic 1-hour cache writes (2x input) |
| `output_tokens` | All output, including reasoning / thinking |
| `reasoning_tokens` | Subset of output (request logs only) |
| `web_search_requests` | Anthropic server-side web search |
| `weight` | 1 / `sample_rate` for sampled logs |
| `prefix_hashes`, `prefix_chars`, `request_hash` | Fingerprint (see below) |

The input total is always `uncached + cache_read + cache_write + cache_write_1h`.

## OpenAI Usage API: completions

`GET /v1/organization/usage/completions`. The type is `openai.types.admin.organization.UsageCompletionsResponse`, and its results have `object = "organization.usage.completions.result"`.

| Field | Column | Note |
| :--- | :--- | :--- |
| `start_time`, `end_time` (unix s) | `timestamp`, `bucket_seconds` | `fetch` uses `bucket_width=1h`, `limit=168` |
| `input_tokens` | (total) | **Includes** cached and cache-write tokens |
| `input_cached_tokens` | `cache_read_tokens` | |
| `input_cache_write_tokens` | `cache_write_tokens` | Billed at 1.25x from GPT-5.6 on; free before |
| `input_uncached_tokens` | `uncached_input_tokens` | Excludes cache writes. When absent, `input_tokens - cached - cache_write` is used |
| `output_tokens` | `output_tokens` | |
| `num_model_requests` | `requests` | |
| `batch` | `service_tier = batch` | Requires `group_by[]=batch` |
| `service_tier` | `service_tier` | `default` / `auto` map to `standard`. `priority` maps to `fast`: OpenAI returns `priority` for Fast-mode requests (per `ChatCompletion.service_tier` docstring) |

Other result objects on the same page (embeddings, images, audio…) are skipped with a warning.

The query string uses bracket arrays (`group_by[]=model`), matching the SDK's `array_format="brackets"`.

## OpenAI Costs API

`GET /v1/organization/costs`. The type is `UsageCostsResponse`, and its results have `object = "organization.costs.result"`.

| Field | Use |
| :--- | :--- |
| `amount.value`, `amount.currency` | USD amount for the day (`bucket_width=1d`, `limit` ≤ 180) |
| `line_item`, `project_id` | Kept for the reconciliation table |

## Anthropic Usage Report

`GET /v1/organizations/usage_report/messages`. The Python SDK has no types for it. Fields are verified against the API reference (response example included as a test fixture) and the official `anthropics/claude-cookbooks` `observability/usage_cost_api.ipynb`.

| Field | Column | Note |
| :--- | :--- | :--- |
| `starting_at`, `ending_at` (RFC 3339) | `timestamp`, `bucket_seconds` | `1h` buckets, `limit` ≤ 168 |
| `uncached_input_tokens` | `uncached_input_tokens` | **Excludes** cache reads and writes |
| `cache_read_input_tokens` | `cache_read_tokens` | |
| `cache_creation.ephemeral_5m_input_tokens` | `cache_write_tokens` | 1.25x input |
| `cache_creation.ephemeral_1h_input_tokens` | `cache_write_1h_tokens` | 2x input |
| `output_tokens` | `output_tokens` | |
| `server_tool_use.web_search_requests` | `web_search_requests` | $10 / 1k |
| `service_tier` | `service_tier` | `priority_on_demand` maps to `priority`, `flex_discount` maps to `flex` |
| `inference_geo` | `inference_geo` | `global`, `us`, `not_available` |
| `context_window` | (warning) | Rows in `200k-1M` are flagged, not repriced |
| `workspace_id`, `api_key_id`, `model` | `workload`, `model` | `workspace_id` is null for the default workspace |

`group_by[]` used by `fetch`: `model`, `workspace_id`, `api_key_id`, `service_tier`, `context_window`, `inference_geo`.

## Anthropic Cost Report

`GET /v1/organizations/cost_report` returns daily buckets (`limit` ≤ 31).

| Field | Use |
| :--- | :--- |
| `amount` | **Decimal string in cents**, divided by 100 |
| `currency`, `description`, `workspace_id` | Reconciliation table |

## Request logs (JSONL)

One JSON object per line. Only `timestamp`, `model` and `usage` are required.

```json
{
  "timestamp": "2026-09-01T10:00:00Z",
  "vendor": "openai",
  "model": "gpt-5.4",
  "workload": "support_chat",
  "service_tier": "default",
  "sample_rate": 0.1,
  "status": "ok",
  "usage": {"prompt_tokens": 5200, "completion_tokens": 310, "prompt_tokens_details": {"cached_tokens": 4096}},
  "request": {"model": "gpt-5.4", "messages": [{"role": "system", "content": "..."}]}
}
```

- `timestamp` is ISO 8601 or unix seconds.
- `vendor` is optional. It is inferred from the model id (`claude*` means Anthropic).
- `workload` (or `feature`) is any label for the product feature.
- `sample_rate` is the fraction of calls you log. Each line then counts `1 / sample_rate` times.
- `status` can be an HTTP code or `error` / `failed` / `timeout` / `cancelled`. Mark calls whose billed result you discarded.
- `usage` is `response.usage` exactly as the SDK returns it (`.model_dump()`). Three shapes are recognised:

  | SDK type | Detected by | Input semantics |
  | :--- | :--- | :--- |
  | `openai.types.CompletionUsage` (Chat Completions) | `prompt_tokens` | `prompt_tokens` includes `prompt_tokens_details.cached_tokens` and `.cache_write_tokens` |
  | `openai.types.responses.ResponseUsage` (Responses) | `input_tokens` + vendor openai | `input_tokens` includes `input_tokens_details.cached_tokens` and `.cache_write_tokens` |
  | `anthropic.types.Usage` (Messages) | vendor anthropic | `input_tokens` excludes `cache_read_input_tokens` and `cache_creation` |

  Reasoning output is read from `completion_tokens_details.reasoning_tokens` / `output_tokens_details.reasoning_tokens` (OpenAI) and `output_tokens_details.thinking_tokens` (Anthropic).
- `request` is the request body you sent. It is fingerprinted on load, or before sending with `llm-cost-teardown fingerprint`, which replaces it with `fingerprint`.

### Fingerprint

`fingerprint.py` splits the request in the order the vendor builds the prompt:

1. `tools`
2. `response_format` / `text`
3. `system` / `instructions`
4. each message or content part

For each block it stores:

- `prefix_hashes[i]`: HMAC-SHA256 (16 hex chars) of the canonical JSON of blocks `0..i`;
- `prefix_chars[i]`: cumulative character count;
- `request_hash`: hash of the full request minus `stream`, `metadata`, `user`, `store` (used for duplicate detection).

The salt is random per run and never written. Fingerprint all log files in one run, so equal prefixes get equal hashes.

## Normalised CSV

This is for exports from gateways or warehouses. The columns are the names of the normalised frame above. The required ones are `timestamp`, `model`, `uncached_input_tokens` and `output_tokens`. Missing optional columns get defaults (`vendor` is inferred, and `granularity` defaults to `bucket`).

## Sources (checked 2026-09-29)

- `openai` Python SDK:
  - `types/admin/organization/usage_completions_response.py`
  - `usage_costs_response.py`
  - `types/completion_usage.py`
  - `types/responses/response_usage.py`
  - `types/chat/chat_completion.py`
- `anthropic` Python SDK: `types/usage.py`.
- Anthropic API reference: *Get Messages Usage Report*, *Get Cost Report*.
- `anthropics/claude-cookbooks`: `observability/usage_cost_api.ipynb` (real response output).
- Prices: see `SOURCES` in `pricing.py`.
