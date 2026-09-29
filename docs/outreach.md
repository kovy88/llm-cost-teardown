# Outreach templates (no sales fluff)

Rules:

- Always personalise the first line with something specific to them.
- Offer one concrete thing: a free USD estimate in 48 h.
- Never claim results or clients you do not have. Until the first case study exists, point to the sample report and the open-source tool.

## Who to contact

- CTOs / founders of companies with a visible LLM feature: a chat assistant, "AI" in the pricing page, an AI changelog entry.
- Good triggers:
  - job posts mentioning LLM, RAG or "AI cost";
  - a public changelog or blog mentioning an older model (e.g. GPT-4o, Claude Opus 4.1, Sonnet 4.x);
  - a pricing page that limits AI usage per plan (a sign the unit economics hurt).
- Skip insurers entirely (conflict of interest), and skip companies clearly below about $3k/month in LLM spend (the guarantee would not be met).

## Cold email

**Subject:** {product}'s LLM bill: free savings estimate

Hi {first_name},

{one specific line: e.g. "Saw the new AI summary in {product}'s changelog."}

I audit OpenAI / Anthropic API spend. You run one read-only export command (no prompts leave your machine), and within 48 hours I send back a USD estimate of what model migration, prompt caching, batching and routing would save, per feature. Here is what the report looks like: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

If the number is not worth acting on, I will tell you that too. Worth a look?

Matěj
koval.matej88@seznam.cz

## LinkedIn / X DM (≤ 300 characters)

Hi {first_name}, I audit OpenAI/Anthropic API bills. One read-only export, no prompts, USD estimate in 48h. Free. github.com/kovy88/llm-cost-teardown

## Follow-up (4–5 days later, same thread)

Hi {first_name}, one data point in case it helps. Moving from an older Claude/GPT model to its current same-tier successor can be computed exactly from list prices, before touching any code. In the sample report it is the biggest single line: Opus 4.1 to Opus 5.5 cuts that model's cost by 65 %, even after the new tokenizer's ~30 % more tokens. Happy to run it on your export; it takes one command.

## Replies to common objections

**"We already use LiteLLM / Helicone / a gateway."**
Great, that makes it faster: its logs can feed the analysis directly. Gateways show where the money goes. The audit changes the prompts and calls that spend it, and proves with an eval set that quality holds.

**"We can't share data."**
You don't share prompts. The aggregate export is token counts per model and hour. Request logs are optional and get fingerprinted on your machine first (keyed hashes, the key is never saved). Happy to sign an NDA.

**"How do I know the numbers are right?"**
Every lever is labelled exact, measured or scenario. Modelled cost is reconciled against your own cost export. The guarantee is on the audit: under 3× its price in annual savings, you pay nothing.

**"We're too small."**
If your LLM spend is under about $3k/month, the audit probably won't pay for itself. Run the open-source tool yourself: https://github.com/kovy88/llm-cost-teardown

## After a free estimate

Send the report plus a three-line summary:

- the top lever and its saving;
- the annual base saving;
- what the audit would add, i.e. which scenario rows become measured.

Then propose a 20-minute call to walk through it.
