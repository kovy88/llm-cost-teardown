# First outreach wave

Six companies with a public LLM feature, checked 2026-09-30. No invented names or inboxes. Find the person on LinkedIn (CTO, head of engineering, or the founder who posts about the AI feature), put their first name in the greeting, and send from koval.matej88@seznam.cz.

Skip insurers. If a reply shows spend under about $3k/month, send them the repo and do not sell the audit.

Tracker: edit the Status cell when you send (`sent YYYY-MM-DD`), when they reply, when an estimate goes out.

| Company | Why they fit | Status | Sent | Reply |
| :--- | :--- | :--- | :--- | :---: |
| Mews | Guest messaging AI at hotel scale, Prague | draft | | |
| Productboard | Spark AI in the product, Prague-founded | draft | | |
| Keboola | Kai, in-product AI data engineer | draft | | |
| Better Stack | AI SRE that builds dashboards from a prompt | draft | | |
| ChatBotKit | Model menu still lists older Opus and GPT-4o | draft | | |
| FAPI | Fapilot + Claude connector; may be under $3k | draft | | |

Watch, do not lead with these: Rohlik is hiring an AI engineer for production chatbots and the posting mentions LLM cost management (https://jobs.ashbyhq.com/rohlik/6aee5b36-e0f5-44fd-928e-f4a65017a4d7). They likely have an internal team. Apify bills hosted-agent tokens through their own OpenRouter proxy, so a vendor admin export may not be the bill.

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
