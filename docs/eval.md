# Eval set (quality gate)

The audit's differentiator is not the USD table. It is a frozen 100-query set that must not get worse when you change model, route, or trim output.

The CLI does **not** call any model. The client (or you, with their keys on their machine) produces outputs. This tool only scores them.

## Format

`eval_set.jsonl` — one case per line:

```json
{"id": "intent_001", "workload": "proj_intent_router", "input": "I forgot my password", "checks": [{"type": "exact", "value": "password_reset"}]}
```

`eval_baseline.jsonl` / `eval_candidate.jsonl` — one output per line:

```json
{"id": "intent_001", "model": "gpt-5-mini", "output": "password_reset"}
```

Check types: `exact`, `contains`, `contains_all`, `one_of`, `json_field` (needs `"field"`).

## Commands

```bash
# Score one run
uv run llm-cost-teardown eval data/samples/eval_set.jsonl data/samples/eval_baseline.jsonl

# Gate: candidate must stay within 2 pp of baseline
uv run llm-cost-teardown eval data/samples/eval_set.jsonl data/samples/eval_baseline.jsonl \
  --candidate data/samples/eval_candidate.jsonl --report eval.md
```

Exit code 1 means the gate failed. Attach the same three files to `analyze` to put the gate in the savings report:

```bash
uv run llm-cost-teardown analyze data/samples/*.json data/samples/requests.jsonl \
  --eval-set data/samples/eval_set.jsonl \
  --eval-baseline data/samples/eval_baseline.jsonl \
  --eval-candidate data/samples/eval_candidate.jsonl \
  --client "Acme Helpdesk AI" --report report.md
```

## How to build it from a client

Start from the workloads already in the export. This writes one empty case per workload, dearest first, at most 100. Fill `input` and `checks` with the client before anyone scores it.

```bash
uv run llm-cost-teardown eval-init data/private/*.json -o data/private/eval_set.jsonl
```

1. Sample real user inputs across the expensive workloads (not the prompts' system text; the user turn is enough).
2. Sit with the owner of each feature and write the rubric: exact label, required facts, or JSON field. Drop anything they cannot score in 10 seconds.
3. Freeze 100 items. Run the **current** models once → baseline. Do not touch the set after that.
4. Run the candidate (new model, router, shorter `max_tokens`) → compare.
5. A drop larger than 2 percentage points, or regressions on tickets they care about, blocks that lever.

The synthetic sample set in `data/samples/` is the same shape, built for Acme Helpdesk AI so a prospect can see the gate in [sample-report.md](sample-report.md).
