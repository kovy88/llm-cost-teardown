# How to send your usage data

For the free estimate we only need **aggregate usage and cost for the last 30 days**. This is token counts per model, project and hour. It contains no prompts, no responses and no end-user data.

Request logs are optional. They turn the caching, duplicate-call and routing estimates from assumptions into measurements, and they can be fingerprinted so that no prompt text is included.

## Step 1: aggregate export (about 5 minutes)

You run the export yourself, and the admin key never leaves your machine.

```bash
git clone <repo-url> && cd llm-cost-teardown && uv sync

# OpenAI: an organization Admin API key (not a project key)
OPENAI_ADMIN_KEY=sk-admin-... uv run llm-cost-teardown fetch openai --days 30

# Anthropic: an Admin API key (sk-ant-admin...)
ANTHROPIC_ADMIN_KEY=sk-ant-admin-... uv run llm-cost-teardown fetch anthropic --days 30
```

This writes four JSON files into `data/private/`:

- `openai_usage.json`
- `openai_costs.json`
- `anthropic_usage.json`
- `anthropic_costs.json`

Open them if you like. They contain token counts, model names, project/workspace/API-key IDs and daily cost lines. Send them over a channel you trust. You can revoke the admin key right after the export.

**What the command calls** (read-only `GET` requests, source in [`fetch.py`](../src/llm_cost_teardown/fetch.py)):

| Vendor | Endpoint | Grouped by |
| :--- | :--- | :--- |
| OpenAI | `/v1/organization/usage/completions` (hourly) | model, project, batch, service tier |
| OpenAI | `/v1/organization/costs` (daily) | line item, project |
| Anthropic | `/v1/organizations/usage_report/messages` (hourly) | model, workspace, API key, service tier, context window, inference geo |
| Anthropic | `/v1/organizations/cost_report` (daily) | workspace, description |

If you would rather not run our code, the same data can be pulled with `curl` from the endpoints above. Tell us and we will send the exact commands.

**Tip:** if every feature uses its own OpenAI project, Anthropic workspace or API key, the report breaks the savings down per feature. If everything runs under one key, the report still works, just per model.

## Step 2 (optional): request logs

Request logs let us replay your traffic. We can then see which prompts share a prefix, how often it repeats within the cache lifetime, which calls are exact duplicates, and how long the answers are.

A few days of traffic, or a 5–20 % sample, is enough. Log one JSON line per call:

```python
import json, random, time

SAMPLE_RATE = 0.1
log = open("llm_requests.jsonl", "a")


def logged_call(create, vendor: str, workload: str, **params):
    response = create(**params)
    if random.random() < SAMPLE_RATE:
        log.write(
            json.dumps(
                {
                    "timestamp": time.time(),
                    "vendor": vendor,
                    "model": response.model,
                    "workload": workload,  # your feature name, e.g. "support_chat"
                    "sample_rate": SAMPLE_RATE,
                    "usage": response.usage.model_dump(),
                    "request": params,  # removed by the fingerprint step below
                }
            )
            + "\n"
        )
    return response


# OpenAI Chat Completions / Responses
logged_call(openai_client.chat.completions.create, "openai", "support_chat", model="gpt-5.4", messages=messages)
# Anthropic Messages
logged_call(
    anthropic_client.messages.create,
    "anthropic",
    "rag_answers",
    model="claude-sonnet-5-5",
    max_tokens=1024,
    system=system,
    messages=messages,
)
```

Then strip the prompt text before the file leaves your machine:

```bash
uv run llm-cost-teardown fingerprint llm_requests*.jsonl -o requests.fingerprinted.jsonl
```

Each `request` is replaced by a fingerprint like this:

```json
{"prefix_hashes": ["9f2c1d0a7b3e4f55", "0c4b7e21d9a8f310", "..."], "prefix_chars": [4210, 18532, 18911], "request_hash": "5be0c1f2a9d47e08"}
```

The hashes use a random key that is generated for this run and never saved. We can tell that two requests share their first 18,532 characters, but not what those characters are. Response text is dropped as well. Only `usage`, the model, the timestamp and your workload label remain.

## What we never ask for

- API keys (admin or otherwise), or access to your accounts.
- Prompt or response text, customer data, or production database access.

## How we handle what you send

- It is used only for your audit, under NDA if you want one, and is never committed to any repository.
- It is deleted when the engagement ends, or earlier on request.
- The report contains only aggregate numbers, model names and the workload labels you chose.
