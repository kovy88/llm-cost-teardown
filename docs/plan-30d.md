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
  - 118 tests, including schema checks against the official SDK types.
- [x] Synthetic sample company and [sample report](sample-report.md).
- [x] Client guide: [send-your-data.md](send-your-data.md). Field mapping: [data-formats.md](data-formats.md).
- [x] Dry-run path: `fetch` + `analyze` + `eval` on synthetic data; still do one pass on your own real account.
- [x] Technical article: [article-19k-bill.md](article-19k-bill.md).

- [x] First-client checklist: [engagement.md](engagement.md).

## D6–10: channels

- [ ] Paste [channels.md](channels.md) into Upwork + Malt (fixed $1,900, then answer OpenAI / LLM / RAG / cost jobs).
- [ ] Post the LinkedIn text and the Show HN text from [channels.md](channels.md). Article source: [article-19k-bill.md](article-19k-bill.md).

## D11–20: outreach

- [ ] Send the six drafts in [prospects.md](prospects.md). Fill `{first_name}` from LinkedIn. Track status in that file.
- [ ] Extend the list toward 60 (Product Hunt, YC, StartupJobs). Same rule: a public AI feature, no insurers, skip obvious sub-$3k spend.

## D21–30: first proof

- [ ] Turn the first 3 free estimates into an anonymised case study (with the client's consent).
- [ ] Offer the first paying client a discount in exchange for a reference with before/after invoice numbers.

## Before every client report

- [ ] Re-verify `pricing.py` against the vendor pricing pages and bump `VERIFIED_ON`. The CLI refuses to write reports once the prices are more than 30 days old.
- [ ] Check the Data notes section: unpriced models, unknown service tiers, long-context rows.
