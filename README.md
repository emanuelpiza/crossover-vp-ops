# Vendor Analysis Assessment — VP of Operations

Post-acquisition vendor spend analysis on 386 vendors / $7,839,131 trailing-12-month spend. Deliverables: classified vendor list + Top 3 savings opportunities + methodology + 1-page executive memo for the CEO and CFO.

**Submission sheet:** https://docs.google.com/spreadsheets/d/1OOjO8jCxz1eEchOwpP22u965iAX7zXLztEwVuBtizpw/edit
**Executive memo Google Doc:** https://docs.google.com/document/d/1pO1J80XPomOT0QCwW3fWmKySLqBKHy53at7Q6tYrYsY/edit

## Result summary

- **Baseline:** $7,839,131 / T12M / 386 vendors (sum-verified, USD).
- **Top-3 combined annual savings:** **$790K – $1,182K** (10.1%–15.1% of base).

| # | Opportunity | Annual savings |
|---|---|---:|
| 1 | Salesforce stack right-sizing (+ HubSpot decom + Kimble absorption) | $531K – $843K |
| 2 | Real-estate footprint consolidation (6 cities, 11 vendors) | $170K – $226K |
| 3 | Professional services consolidation (audit / tax / legal) | $89K – $113K |

## How this was built

1. **Dataset review** — duplicates, opaque names, statutory vendors, and concentration patterns flagged before any classification (`outputs/01-dataset-challenge.md`). Surfaced Navan booked under two entities ($416K combined), AWS under two entities, and ~80 opaque Croatian D.O.O. vendors that needed cautious classification.
2. **Pass-1 classification (Claude Sonnet 4.6)** — all 386 vendors classified in parallel via the Anthropic Python SDK, 15 concurrent workers.
3. **Pass-2 QA (Claude Opus 4.6)** — independent review of every Pass-1 row with stricter rules. **94 of 386 rows corrected (24.4%)**; log in `outputs/03-qa-changes-log.csv`.
4. **Aggregate stats** — duplicate detection, category fragmentation, long-tail analysis (`outputs/04-stats.md`).
5. **Synthesis** — Top 3 Opportunities, Executive Memo, and Methodology written manually on top of the classified data, with every savings number showing `baseline × mechanism = number`.

## Folder

```
vendor-analysis-assessment/
├── README.md                                ← this file
├── docs/
│   └── 01-assessment-brief.md               ← original recruiter brief
├── inputs/
│   └── vendors_raw.csv                      ← decoded CSV from the source Google Sheet
├── scripts/
│   ├── 01_classify_vendors.py               ← Pass-1: Sonnet 4.6 classification
│   ├── 02_qa_classifications.py             ← Pass-2: Opus 4.6 QA
│   ├── 03_dataset_stats.py                  ← aggregate stats + duplicate detection
│   ├── 04_publish_to_sheet.py               ← writes outputs back into the submission Google Sheet
│   └── 05_populate_memo_doc.py              ← writes the executive memo into the Google Doc
└── outputs/
    ├── 01-dataset-challenge.md              ← issues flagged before classification
    ├── 03-vendors-classified-qa.csv         ← FINAL classified list (after QA)
    ├── 03-qa-changes-log.csv                ← the 94 rows Opus corrected
    ├── 04-stats.json / 04-stats.md          ← machine- and human-readable stats
    ├── 05-top-3-opportunities.md            ← Top 3 synthesis (full version)
    ├── 06-executive-memo.md                 ← 1-page memo for CEO / CFO
    └── 07-methodology.md                    ← full methodology write-up
```

## Reproduce

```bash
export ANTHROPIC_API_KEY=...            # ~$8 total compute cost
pip install anthropic google-auth google-api-python-client

python3 scripts/01_classify_vendors.py     # Pass-1: 386 vendors via Sonnet 4.6
python3 scripts/02_qa_classifications.py   # Pass-2: QA via Opus 4.6
python3 scripts/03_dataset_stats.py        # stats + duplicate detection
python3 scripts/04_publish_to_sheet.py     # writes back into the submission Sheet
python3 scripts/05_populate_memo_doc.py    # writes the memo into the Google Doc
```

Total runtime ~2–3 min. Idempotent — safe to re-run.

## Compute cost

| Stage | Model | Calls | Approx. cost |
|---|---|---:|---:|
| Pass-1 classification | Sonnet 4.6 | 386 | ~$0.60 |
| Pass-2 QA | Opus 4.6 | 386 | ~$7.50 |
| Stats + publishing | local | — | $0 |
| **Total** | | | **~$8.10** |

## Why the output is defensible

- Every savings number shows `baseline × mechanism = number` (e.g. Opportunity 1 = $3.12M × 15–25% = $467K–$779K).
- Duplicate vendor entries (Navan × 2, AWS × 2, HR Solution × 2, 4i × 2) are counted once in savings math.
- M&A transaction advisors excluded from the run-rate base as one-time deal fees.
- Auditor switching mid-integration rejected as net-negative (regulatory + re-audit risk).
- 94/386 first-pass classifications were corrected by an independent QA model — documented and reproducible.
