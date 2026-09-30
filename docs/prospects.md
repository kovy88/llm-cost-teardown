# First outreach wave

Checked 2026-09-30. No invented inboxes. `{first_name}` stays a placeholder until you confirm the LinkedIn profile yourself. Do not send a guessed name.

Skip insurers. If a reply shows spend under about $3k/month, send the repo and do not sell the audit.

Do not send anything until Generali has confirmed side activity in writing.

## Send order

1. Day 0, these six, in this order: Mews, Productboard, Keboola, Better Stack, ChatBotKit, FAPI. One mail each. Fill `{first_name}` from LinkedIn the same day, then send from koval.matej88@seznam.cz.
2. Day 4, same thread, the follow-up already in [outreach.md](outreach.md): same-tier migration is exact from list prices, Opus 4.1 to Opus 5.5 is the sample's biggest line even after the tokenizer. No second pitch.
3. If they reply: send [send-your-data.md](send-your-data.md). NDA only if they ask. Files go in `data/private/`.
4. When the export arrives:

```bash
uv run llm-cost-teardown analyze data/private/*.json \
  --client "Firma" --report data/private/report.md --internal --email
```

`--email` says whether to sell the audit. Threshold: conservative annual saving of $5,700. Above it, propose 20 minutes. Below it, send the report and stop.
5. Wave 2 (Amio, Everbot) only after one of the six replies, or after 7 days of silence. Perselio and Rossum stay on the watch list.

Tracker: set Status to `sent YYYY-MM-DD` when you send.

| Company | Why they fit | Status | Sent | Reply |
| :--- | :--- | :--- | :--- | :---: |
| Mews | Guest messaging AI at hotel scale, Prague | draft | | |
| Productboard | Spark AI in the product, Prague-founded | draft | | |
| Keboola | Kai, in-product AI data engineer | draft | | |
| Better Stack | AI SRE that builds dashboards from a prompt | draft | | |
| ChatBotKit | Model menu still lists older Opus and GPT-4o | draft | | |
| FAPI | Fapilot + Claude connector; may be under $3k | draft | | |
| Amio | E-commerce shopping assistant, vendor not named on the site | hold | | |
| Everbot | Resells a model menu (GPT-5.5, Claude 4.6 Sonnet) for a flat credit price | hold | | |

## Mews

Trigger: Guest Messaging drafts replies from the property knowledge base and can open tasks. Announced with Mews OS; general availability was 1 August 2026. https://www.mews.com/en/introducing-mews-os

Subject: Mews Guest Messaging: free LLM savings estimate

Hi {first_name},

Saw Guest Messaging in the Mews OS launch: AI replies grounded in the property knowledge base, plus tasks from the thread.

I audit OpenAI / Anthropic API spend. You run one read-only export (no prompts leave your machine), and within 48 hours I send a USD estimate of what model migration, prompt caching, batching and routing would save, per feature. Sample report: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

If the number is not worth acting on, I will tell you that too. Worth a look?

Matěj
koval.matej88@seznam.cz

## Productboard

Trigger: Spark is the AI suite, and on 11 September 2026 they shipped an MCP server so coding agents can create and edit entities. https://support.productboard.com/hc/en-us/articles/360060759874-Productboard-Release-Notes

Subject: Productboard Spark: free LLM savings estimate

Hi {first_name},

Saw the 11 September Spark MCP release: agents can create and edit Productboard entities, not only read specs.

I audit OpenAI / Anthropic API spend. You run one read-only export (no prompts leave your machine), and within 48 hours I send a USD estimate of what model migration, prompt caching, batching and routing would save, per feature. Sample report: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

If the number is not worth acting on, I will tell you that too. Worth a look?

Matěj
koval.matej88@seznam.cz

## Keboola

Trigger: Kai, "your AI data engineer", public beta 9 February 2026. Later changelog entries add custom instructions and tool permissions. https://changelog.keboola.com/archive/

First touch is LinkedIn. If that stays silent, the public inbox on their contact page is talkto@keboola.com. Use it as a fallback, not the opening.

Subject: Keboola Kai: free LLM savings estimate

Hi {first_name},

Saw Kai go to public beta in February, and the later notes on custom instructions and tool permissions. That shape (long system prompt, tools, short user turns) is usually where prompt caching shows up.

I audit OpenAI / Anthropic API spend. You run one read-only export (no prompts leave your machine), and within 48 hours I send a USD estimate per feature. Sample report: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

If the number is not worth acting on, I will tell you that too. Worth a look?

Matěj
koval.matej88@seznam.cz

## Better Stack

Trigger: Changelog #15 (10 August 2026): AI SRE builds a dashboard from a prompt, and the same path works through MCP. https://betterstack.com/community/blog/changelog-15-stop-creating-dashboards/

Subject: Better Stack AI SRE: free LLM savings estimate

Hi {first_name},

Saw changelog #15: AI SRE builds a dashboard from a prompt, and the same thing from Claude Code or Codex via MCP.

I audit OpenAI / Anthropic API spend. You run one read-only export (no prompts leave your machine), and within 48 hours I send a USD estimate of what model migration, prompt caching, batching and routing would save. Sample report: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

If the number is not worth acting on, I will tell you that too. Worth a look?

Matěj
koval.matej88@seznam.cz

## ChatBotKit

Trigger: Their changelog still documents Claude Opus 4.1 and GPT-4o as available models, alongside newer Opus releases. A model menu is the migration lever, computed from list prices before any code change. https://cbk.ai/changelog

Subject: ChatBotKit model menu: free LLM savings estimate

Hi {first_name},

Your changelog still lists Claude Opus 4.1 and GPT-4o next to the newer Opus models. The price gap to the current same-tier model is exact from list prices, including the newer Claude tokenizer, before anyone touches a prompt.

I audit OpenAI / Anthropic API spend. One read-only export (no prompts), and within 48 hours a USD estimate per model. Sample report: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

If the number is not worth acting on, I will tell you that too. Worth a look?

Matěj
koval.matej88@seznam.cz

## FAPI

Trigger: August 2026 post: FAPI connects to Claude and ChatGPT Codex via MCP, and Fapilot usage is metered as Fuel per plan. https://fapi.cz/blog/srpnove-horke-fapi-novinky/

Check spend before pushing the audit. A fuel cap on the plan can mean their own API bill is still small. If it is under about $3k/month, send the repo and stop.

Subject: Fapilot: free LLM savings estimate

Hi {first_name},

Saw the August note: FAPI connects to Claude and Codex through MCP, and Fapilot draws from a Fuel allowance per plan.

I audit OpenAI / Anthropic API spend. You run one read-only export (no prompts leave your machine), and within 48 hours I send a USD estimate. If the bill is too small for a paid audit, I will say so and point you at the open-source tool. Sample report: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

Worth a look?

Matěj
koval.matej88@seznam.cz

## Wave 2 (after the six, not instead of them)

### Amio

Checked https://amio.io on 2026-09-30. The site is an e-commerce shopping assistant: product feeds, web chat, Datart case with a 76% automation rate. It does not name OpenAI or Anthropic, and it does not name a founder. LinkedIn lists Matouš Kučera as CEO; do not use that name until you have opened the profile yourself.

Subject: Amio shopping assistant: free LLM savings estimate

Hi {first_name},

Saw the shopping assistant on amio.io: it answers from the product feed, and the Datart note says 76% of those contacts stay in the bot.

If that bot is billed to an OpenAI or Anthropic account, one read-only export (no prompts) is enough for a USD estimate within 48 hours. If the bill is somewhere else, say so and I will not guess. Sample report: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

Matěj
koval.matej88@seznam.cz

### Everbot

Checked https://everbot.cz/cenik/ on 2026-09-30. The comparison with ChatGPT names GPT-5.5, Claude 4.6 Sonnet and Gemini 3.1 Pro, sold as credits (from 590 Kč / user / month), one login. That is a reseller: their upstream API bill is the product, if they pay OpenAI and Anthropic directly. The site does not name a CTO. LinkedIn lists Jiří Štanglica; confirm the profile before using the name.

Subject: Everbot model menu: free LLM savings estimate

Hi {first_name},

Your pricing page still puts GPT-5.5 and Claude 4.6 Sonnet next to Gemini, and sells them as credits. The gap from an older model to the current same-tier one is exact from list prices, before any prompt change.

If Everbot pays OpenAI or Anthropic directly, one read-only export (no customer prompts) gets you a USD estimate in 48 hours. Sample report: https://github.com/kovy88/llm-cost-teardown/blob/main/docs/sample-report.md

If the number is not worth acting on, I will tell you that too.

Matěj
koval.matej88@seznam.cz

## Watch, do not email yet

- Perselio (Prague). LinkedIn describes a shopping assistant. The company looks too small for the $1,900 audit, and this pass did not confirm a public model or an API bill.
- Rossum. Document AI with its own models, and a public note tying it to Coupa. An OpenAI admin export may not be the bill. Do not lead with them.
- Rohlik. Hiring an AI engineer for production chatbots; the posting mentions LLM cost management (https://jobs.ashbyhq.com/rohlik/6aee5b36-e0f5-44fd-928e-f4a65017a4d7). They likely have an internal team.
- Apify. Hosted-agent tokens go through their OpenRouter proxy, so a vendor admin export may not be the bill.
