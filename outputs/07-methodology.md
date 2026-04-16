# Methodology

## Approach

A five-step pipeline, all run through the Claude Code CLI. The design goal was to make every classification and savings number traceable to a deterministic step — and to have a second AI pass independently check the first one so no single model output is trusted blindly.

1. **Dataset review.** Before classifying anything, I examined the raw CSV for duplicates, opaque names, non-discretionary vendors, missing fields, and spend concentration. Findings saved in `outputs/01-dataset-challenge.md`. This surfaced Navan being booked under two legal entities ($416K combined, not $358K as it first looked), AWS under two entities, HR Solution International under two entities, and ~80 opaque Croatian D.O.O. vendors that needed cautious classification.
2. **Pass 1 — classify all 386 vendors (Claude Sonnet 4.6).** Script `scripts/01_classify_vendors.py` runs in parallel (15 concurrent workers via ThreadPoolExecutor) against the Anthropic Messages API. For each vendor the model returns structured JSON with department, 1-line description, recommendation, rationale, and a self-reported confidence label. Output: `outputs/02-vendors-classified.csv`.
3. **Pass 2 — QA every row (Claude Opus 4.6).** Script `scripts/02_qa_classifications.py` has a second, stronger model independently review each Pass-1 row against a stricter ruleset. **94 of 386 rows were corrected (24.4%).** The largest correction class was Pass-1 over-using "Protected" (on Navan, BDO, Eurofast, workers' comp) and "Facilities" (swallowing catering, transport, and team events that should sit under Employee Experience). Output: `outputs/03-vendors-classified-qa.csv` and `outputs/03-qa-changes-log.csv`.
4. **Aggregate analysis.** `scripts/03_dataset_stats.py` computes category fragmentation (audit, legal, real estate, insurance, recruitment), canonical-name duplicate detection, top-20 concentration, and long-tail totals. This is the quantitative base for the Top 3 Opportunities.
5. **Synthesis.** The Top 3 Opportunities, Executive Memo, and this Methodology were written manually (by the VP-of-Operations session) on top of the classified data. Every savings number shows `baseline × mechanism = number` so it is defensible under CFO questioning.

## Tools used

| Tool | Role |
|---|---|
| **Claude Code CLI (Opus 4.6)** | Orchestration, synthesis, memo writing. This session is the VP-of-Operations agent. |
| **Anthropic Python SDK** | Drives Pass-1 and Pass-2 at scale against the Messages API. |
| **Claude Sonnet 4.6** | Pass-1 classification. Fast enough for 386 parallel calls, strong instruction-following. |
| **Claude Opus 4.6** | Pass-2 QA. Highest reasoning quality — worth it for independent review. |
| **Google Drive MCP** | Read the source spreadsheet (exported to CSV for parsing) and the assessment brief. |
| **Python 3 (csv, ThreadPoolExecutor)** | CSV handling, canonical-name duplicate detection, concurrent API calls. |

## Prompts

### Pass-1 prompt (Sonnet 4.6) — summary

> "You are a VP of Operations classifying vendors post-acquisition. The acquired company is a global tech/SaaS business (UK, Croatia, India, Australia, Singapore, Ireland). Main CRM = Salesforce, main travel platform = Navan, main audit firm = BDO. For each vendor, return strict JSON with: department (from a closed list of 14), a specific 1-line description (never generic like 'business services'), a recommendation (Terminate / Consolidate / Optimize / Protected / Investigate), a rationale, and a confidence label. Protected is reserved for statutory spend and one-time M&A deal fees only. Investigate is for opaque names where scope must be confirmed. Individual human names default to G&A / Investigate (usually miscoded expense reimbursements). Croatian D.O.O. entities read by name cues. Departments and recommendations must be from the closed list."

Full prompt: `scripts/01_classify_vendors.py`.

### Pass-2 QA prompt (Opus 4.6) — summary

> "You are the QA reviewer. You receive a vendor name, spend, and a Pass-1 classification. Review and correct only when needed. Protected is only for statutory spend or one-time M&A advisors — never for routine SaaS, never for Navan or BDO in steady state. Facilities must not swallow catering, gym, team events (those are Employee Experience). Auditors providing ongoing services are Optimize, not Protected. Individual human names default to G&A / Investigate. Descriptions must be specific. Prefer Optimize over Terminate when in doubt. Duplicated entries (Navan × 2, AWS × 2, HR Solution × 2, 4i × 2) both get Consolidate with a rationale naming the anchor."

Full prompt: `scripts/02_qa_classifications.py`.

## Quality checks (with evidence)

| Check | Method | Evidence |
|---|---|---|
| Schema validity | Strict JSON parsing + closed-list validation on every response. | Pass-1: 385/386 succeeded on first try (Bella Operation A/S recovered on retry). Pass-2: 386/386 succeeded. |
| Independent-model QA | Opus 4.6 re-reviews every Sonnet classification with stricter rules. | `outputs/03-qa-changes-log.csv`: 94 rows changed (71 Department, 53 Description, 44 Recommendation — some rows had multiple fields changed). |
| Top-20 manual spot-check | I manually reviewed every top-20 vendor post-QA. | Salesforce → Sales / Optimize ✓; Navan → Travel / Optimize (Pass-1 had Protected, corrected) ✓; BDO → Professional Services / Optimize (Pass-1 had Protected, corrected) ✓; RSM Corporate Finance → M&A / Protected (correct — one-time deal fee) ✓; SS&C Intralinks → M&A / Protected (Pass-1 had Optimize — corrected, as it's a VDR used for the deal itself) ✓. |
| Duplicate detection | Deterministic canonical-name grouping in `scripts/03_dataset_stats.py`. | Detected: Amazon Web Services (2 entries, $111K), HR Solution International (2 entries, $88K), TM Forum (2 entries, $58K). All three also flagged Consolidate in Pass-2, confirming the two methods agree. |
| Sum verification | Total computed from classified CSV vs raw CSV. | Both equal **$7,839,131** across 386 rows. Confidence split: 243 high / 76 medium / 67 low. |
| Savings math | Every savings number shows `baseline × mechanism = number`. | Opportunity 1: $3.12M × 15–25% = $467K–$779K. Opportunity 2: per-city math shown per line. Opportunity 3: $473K × 15–20% audit + $117K × 15% legal + boutique renegotiation. |

## What the QA pass specifically looked for

The Opus QA prompt was designed to catch five common first-pass failure modes:

1. **Over-use of "Protected"** — routine SaaS or ongoing services being marked untouchable. Caught: Navan, BDO, Agram Life, Eurofast, Sodexo, Allianz Workers' Comp — all corrected to Optimize.
2. **Category swallowing** — Facilities absorbing catering, gym, team events. Caught ~15 items moved to Employee Experience (Sodexo, Konzum, Catering Muring, Catering Ivić, Omonia, Poles Hanbury Manor offsite, etc.).
3. **Generic descriptions** — "software services", "consulting firm". Caught ~50 descriptions rewritten with specific function.
4. **Tech-vendor misclassification** — Veniture D.O.O. moved from Facilities to Engineering (Croatian dev shop inferred from naming pattern + spend size).
5. **Individual-name confusion** — John Smith, Susan Lee, etc. defaulted to G&A / Investigate (typically miscoded contractor or expense reimbursement).

## Reproducibility

The full pipeline is in `scripts/`. Run with `ANTHROPIC_API_KEY` set:

```
python3 scripts/01_classify_vendors.py
python3 scripts/02_qa_classifications.py
python3 scripts/03_dataset_stats.py
python3 scripts/05_finalize_sheet.py   # publishes to the Google Sheet
python3 scripts/06_create_memo_doc.py  # creates the executive memo Google Doc
```

Total runtime: ~2–3 minutes. Total compute cost: ~$8 (Pass-1 Sonnet ~$0.60, Pass-2 Opus ~$7.50, everything else local).

## Limitations (called out honestly)

The dataset only has vendor name and 12-month USD spend. It does **not** contain contract end dates, auto-renewal flags, business owners, seat counts, acquisition-thesis labels, or parent-acquirer capability overlap. That is why every savings number in the memo is expressed as a range, and why the real first action in the plan is a contract-data pull — not an immediate cut.
