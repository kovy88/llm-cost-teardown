# LLM Cost Teardown

Fixed-price audit service: analyse a company's OpenAI/Anthropic API usage export, find savings (prompt caching, Batch API, model routing, output trimming), prove quality did not drop with an eval set, and show the saving on the invoice.

## Business context
- Offer: fixed 1 900 USD audit (30 days of usage + logs, USD savings report, 100-query eval set, 2 h consulting). Optional implementation for 20–30 % of 12-month savings.
- Guarantee: if annual saving < 3x audit price, client pays nothing.
- Target: CTO/founder of SaaS/AI startups with 3 000–100 000 USD/month LLM spend. English-first, global.
- Differentiator: eval-backed quality proof + code-level fixes (gateways like LiteLLM/TrueFoundry only show graphs).
- Proof of saving = before/after invoice comparison over 30 days + eval score before/after.

## Rules
- Conflict of interest: employer is Generali. Never work for insurers, never use employer data. Check employment contract re: side activity before first paid job.
- Client data: read-only access, NDA, anonymised exports. Never commit client data (`data/private/` is gitignored).
- API field names/units: do NOT trust vendor prose docs. Verify usage export schemas against a maintained open-source client (e.g. official `openai`/`anthropic` SDK types + real export samples) before writing parsers.
- Pricing tables live in `src/llm_cost_teardown/pricing.py` with a `verified_on` date — never hardcode prices elsewhere and re-verify against the vendor pricing page before every client report.

## Stack
Python 3.12, uv, pandas, pytest, ruff. Use `uv run ruff check --fix && uv run ruff format`, `uv run pytest`.
If an API is needed, FastAPI. Never use pip directly.

## Layout
- `src/llm_cost_teardown/` — analyzer (usage loader, savings estimators, report)
- `docs/offer.md`, `docs/plan-30d.md`, `docs/outreach.md` — sales material
- `docs/send-your-data.md` (client export guide), `docs/data-formats.md` (verified field mapping), `docs/sample-report.md` (regenerate with `analyze data/samples/*.json data/samples/requests.jsonl`)
- `data/samples/` — synthetic sample exports only
