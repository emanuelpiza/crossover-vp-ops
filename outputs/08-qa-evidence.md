# Quality Check — Evidence of Validation

This document is the evidence trail for the quality-check step referenced in the Methodology tab. Every classification in the submission spreadsheet went through two independent AI passes (Claude Sonnet 4.6 → Claude Opus 4.6 as QA) plus targeted manual spot-checks. The log below shows what was checked, what was corrected, and how the final output was verified.

## 1. Schema validity

Every model response was forced through strict JSON parsing + closed-list validation (department from a 14-value list; recommendation from a 5-value list). Invalid outputs were retried up to 3 times.

- **Pass-1 (Sonnet 4.6):** 385/386 succeeded on the first attempt. 1 retry succeeded (Bella Operation A/S — the model initially put "Investigate" in the department field instead of the recommendation field).
- **Pass-2 (Opus 4.6):** 386/386 succeeded.

## 2. Independent-model QA pass

A second, stronger model (Opus 4.6) re-reviewed every Pass-1 row against a stricter rule set and returned either `agree: true` or a corrected classification. Full log: `outputs/03-qa-changes-log.csv`.

**Correction rate: 94 of 386 rows (24.4%).**

Breakdown of what was corrected:

| Field | Corrections |
|---|---:|
| Department | 71 |
| Description | 53 |
| Recommendation | 44 |

(Some rows had more than one field corrected.)

### The five most common first-pass failure modes the QA pass specifically looked for

1. **Over-classification of "Protected"** — Pass-1 marked routine SaaS and ongoing services as untouchable. Caught: Navan (travel platform), BDO (statutory auditor), Agram Life, Eurofast, Sodexo, Allianz Workers' Comp — all corrected to Optimize. These are negotiable, not protected.
2. **"Facilities" swallowing unrelated categories** — Pass-1 dumped catering, team events, and employee meals into Facilities. ~15 items moved to Employee Experience (Sodexo Svc India, Konzum Plus, Catering Muring, Catering Ivić, Omonia, Poles Hanbury Manor offsite, etc.).
3. **Generic descriptions** — "software services", "consulting firm", "business services provider" rewritten to specific function. ~50 descriptions fixed.
4. **Tech-vendor misclassification** — Croatian dev-shop-typical names moved from Facilities to Engineering (e.g., Veniture D.O.O. — inferred from naming pattern + spend size).
5. **Individual human names** — "John Smith", "Susan Lee", "Fabiola Thistlewhaite", etc. defaulted to G&A / Investigate. These are almost always miscoded contractor payments or expense reimbursements in AP systems, not vendors in the usual sense.

## 3. Manual spot-check on the top 20 vendors post-QA

Every vendor over $60K spend was manually verified by the VP-of-Operations session against the final classification. Highlights:

| Vendor | Spend | Department / Suggestion | Verification |
|---|---:|---|---|
| Salesforce UK | $3,117,226 | Sales / Optimize | Correct — stated main CRM, core platform |
| Navan (Tripactions) | $357,984 | G&A / Optimize | Pass-1 marked Protected, QA corrected — travel platforms are negotiable, not protected |
| BDO LLP | $343,081 | Professional Services / Optimize | Pass-1 marked Protected, QA corrected — statutory auditors are negotiable (renegotiate scope, don't switch mid-integration) |
| RSM UK Corporate Finance | $117,078 | M&A / Protected | Correct — one-time deal fee, not recurring |
| SS&C Intralinks | $39,966 | M&A / Protected | Pass-1 marked Optimize, QA corrected — this is a VDR used for the deal itself |
| 4i Advisory Services | $71,860 | M&A / Protected | Correct — deal-related advisory |
| Cloudcrossing BVBA | $208,675 | SaaS / Optimize (flagged Investigate in rationale) | Correct to flag for scope clarification — opaque vendor name, no recognizable brand at this spend level |

## 4. Deterministic duplicate detection

A separate Python script (`scripts/03_dataset_stats.py`) grouped vendors by canonical name (stripping suffixes like Ltd, LLC, Inc, GmbH, D.O.O., Pty, A/S, Ireland, International, Operations, Services) and flagged any groups with combined spend ≥ $1K. Results:

| Group | Entries | Combined spend |
|---|---:|---:|
| Amazon Web Services | 2 (Llc + Inc.) | $111,552 |
| HR Solution International | 2 (GmbH + AG) | $87,810 |
| TM Forum | 2 (Tmforum + Tm Forum) | $58,070 |
| Navan | 2 (Tripactions Inc + Navan Inc) | $415,913 |
| 4i | 2 (Advisory + Management Consulting) | $83,977 |
| Apple retail | 4 (UK, Amer, Pty, Distribution) | $8,256 |
| Bupa | 2 (Supplier + Australia) | $35,263 |
| Acclime | 2 (Corporate Services + USA Inc) | $10,408 |

**Cross-validation:** each of these duplicate groups was also flagged "Consolidate" by the Pass-2 QA model without that model being told about the deterministic grouping output. Two independent methods agreed, which is a strong signal.

## 5. Sum verification

- Raw CSV total: **$7,839,131** across 386 rows.
- Classified CSV total after Pass-2: **$7,839,131** across 386 rows. ✓ Equal.
- Confidence distribution post-QA: **243 high / 76 medium / 67 low**.

## 6. Savings-math verification

Every savings number in the Top 3 tab shows `baseline × mechanism = number`:

| Opportunity | Baseline | Mechanism | Savings |
|---|---:|---|---:|
| 1. Salesforce seat recovery | $3,117,226 | 15–25% post-M&A seat reduction | $467K–$779K |
| 1. HubSpot decommission | $32,187 | 100% (redundant CRM) | $32K |
| 1. Kimble absorption | $52,825 | ~60% (native replacement) | $32K |
| 2. London consolidation | $397,328 | keep 1 of 2, ~17% net | $67K |
| 2. Zagreb consolidation | $327,847 | ~25% reduction | $82K |
| 2. Chennai consolidation | $162,261 | ~15% reduction | $24K |
| 3. Audit non-anchor reduction | $130,000 | 20% | $26K |
| 3. BDO scope renegotiation | $343,081 | 5% | $17K |
| 3. Legal panel consolidation | $117,465 | 15% | $18K |
| 3. Advisory renegotiation | $65,418 | 50% midpoint | $28K–$52K |

No opaque extrapolations, no rounding cheats, no compound math without declaring the components.

## 7. What the quality check did NOT catch

Honest caveat: the dataset contains only vendor name + USD spend. The quality check cannot catch:

- Whether a vendor is acquisition-thesis-protected (CEO confirmation needed before top-20 action).
- Whether a contract auto-renewed recently (locks the saving to Year 2).
- Exact exit fees on lease terminations.
- Whether Harmonic Group and similar opaque vendors are legitimate strategic engagements or vestigial spend.

Those are listed as open risks/investigation items in the memo and the Top 3 rationale, not buried.
