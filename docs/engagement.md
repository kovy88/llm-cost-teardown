# First engagement playbook

What you actually do when someone replies. Keep this next to the terminal.

## 0. Before any paid work

- Employment contract (Generali): side activity allowed in writing.
- Invoicing: OSVČ, USD or CZK invoice, audit price $1,900.
- Send [nda.md](nda.md) if they ask; do not wait on it for the free estimate (aggregate exports have no prompts).

## 1. They want the free estimate (the only promise you make in outreach)

1. Reply with [send-your-data.md](send-your-data.md) and this repo. Admin key stays with them.
2. They send `*_usage.json` and `*_costs.json` (30 days). Put files in `data/private/` (gitignored).
3. Run:

```bash
uv run llm-cost-teardown analyze data/private/*.json \
  --client "{Company}" --report data/private/report.md --internal --email
```

4. Read the **Internal** guarantee line and the printed email. If conservative annual saving is under $5,700, the email already says not to sell the audit. Send that version.
5. Send `report.md` within 48 hours. The `--email` block is the three lines: top lever, annual base saving, which row is still a scenario.
6. Propose a 20-minute call.

## 2. They buy the $1,900 audit

1. Invoice. Work starts when paid (or when you agree to the guarantee-first option).
2. NDA signed if not already.
3. Request logs: they fingerprint on their machine (`llm-cost-teardown fingerprint`). You never need raw prompts.
4. Re-run analyze with logs. Scenario rows should become **measured**.
5. Build the eval set with them ([eval.md](eval.md)). `eval-init` writes one empty case per workload. Freeze the rubric before changing models.
6. Run baseline (current models) and candidate (migrations / routing / shorter output). Gate: candidate pass rate within 2 pp of baseline, no unexplained regressions.
7. For each lever with a real saving: a concrete code change (cache breakpoint, `cache_control` / `prompt_cache_key`, batch job, router rule, `max_tokens`).
8. 2-hour session: walk the report, agree rollout order, leave the eval command they can re-run.
9. Proof plan: invoice 30 days before vs after, eval score before vs after. Put both in writing.

## 3. After

- Ask permission to anonymise the estimate as a case study (numbers + industry, no name).
- Delete `data/private/` when they confirm they have the report, or on request.
- Re-verify `pricing.py` before the next client (`verified_on`).
