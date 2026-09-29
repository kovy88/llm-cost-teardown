# 30-day plan

## Blockers before any outreach

- [ ] Check the employment contract (Generali) regarding side activity. This must happen before the first paid job, and ideally before publishing under your own name.
- [ ] Choose a licence and publish the repo (it currently has no remote). Then fill `<repo-url>` in `README.md` and `docs/send-your-data.md`.
- [ ] Contact channel: an email and booking link in the README, the outreach templates and the report CTA.
- [ ] NDA template ready.
- [ ] Sole-proprietor (OSVČ) / invoicing set up.

## D1–5: product

- [x] Open-source analyzer:
  - loaders for OpenAI / Anthropic usage and costs plus request logs;
  - 7 savings levers;
  - Markdown/JSON report;
  - `fetch` and `fingerprint` commands;
  - 104 tests, including schema checks against the official SDK types.
- [x] Synthetic sample company and [sample report](sample-report.md).
- [x] Client guide: [send-your-data.md](send-your-data.md). Field mapping: [data-formats.md](data-formats.md).
- [ ] Dry run on your own real account, even a small one. Check the reconciliation row against your invoice.
- [ ] Technical article with numbers from the sample: "Where a $19k/month LLM bill goes and how to cut 48 % of it". Cover the tokenizer effect on migration, cache minimums per model, and batch detection from the hourly traffic shape.

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
