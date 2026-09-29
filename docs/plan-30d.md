# 30-day plan

## Blockers before any outreach

- [x] Choose a licence and publish the repo (MIT). Contact: koval.matej88@seznam.cz.
- [x] NDA template: [nda.md](nda.md).
- [x] Eval harness + 100-query sample set (quality gate in the report).
- [ ] Sole-proprietor (OSVČ) / invoicing set up.
- [ ] Check the employment contract (Generali) regarding side activity. This must happen before the first paid job.

## D1–5: product

- [x] Open-source analyzer:
  - loaders for OpenAI / Anthropic usage and costs plus request logs;
  - 7 savings levers;
  - Markdown/JSON report;
  - `fetch` and `fingerprint` commands;
  - 111 tests, including schema checks against the official SDK types.
- [x] Synthetic sample company and [sample report](sample-report.md).
- [x] Client guide: [send-your-data.md](send-your-data.md). Field mapping: [data-formats.md](data-formats.md).
- [x] Dry-run path: `fetch` + `analyze` + `eval` on synthetic data; still do one pass on your own real account.
- [x] Technical article: [article-19k-bill.md](article-19k-bill.md).

- [x] First-client checklist: [engagement.md](engagement.md).

## D6–10: channels

- [ ] Upwork + Malt profiles with a fixed-price "project catalogue" (free estimate, then the 1,900 USD audit). Every day, answer jobs matching OpenAI / LLM / RAG / cost / chatbot, and quote a fixed price.
- [ ] Post the article (LinkedIn, Hacker News "Show HN" for the tool, r/LocalLLaMA / r/OpenAI where relevant).

## D11–20: outreach

- [ ] Reach 60 companies with public AI features, using the templates in [outreach.md](outreach.md). Sources: Product Hunt, the YC list, CzechInvest / StartupJobs.
- [ ] Track them in a simple sheet: company, trigger, contact, date, reply, estimate sent, call.

## D21–30: first proof

- [ ] Turn the first 3 free estimates into an anonymised case study (with the client's consent).
- [ ] Offer the first paying client a discount in exchange for a reference with before/after invoice numbers.

## Before every client report

- [ ] Re-verify `pricing.py` against the vendor pricing pages and bump `VERIFIED_ON`. The CLI refuses to write reports once the prices are more than 30 days old.
- [ ] Check the Data notes section: unpriced models, unknown service tiers, long-context rows.
