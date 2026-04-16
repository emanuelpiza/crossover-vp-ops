# Dataset Challenge — Issues Flagged Before Analysis

**Source file:** `inputs/vendors_raw.csv` (386 rows, $7,839,131 total spend over trailing 12 months, USD)

Every finding below was flagged before any recommendation was built. Each one can change the analysis materially — ignoring them would produce naïve, CFO-dismissable conclusions.

## 1. Duplicate / fragmented vendor identities

Same legal entity appears under multiple names. Without consolidating, spend is under-stated per vendor and consolidation math is wrong.

| Vendor (canonical) | Entries | Combined spend | Implication |
|---|---|---|---|
| **Navan (Tripactions)** | "Navan (Tripactions Inc)" $357,984 + "Navan, Inc" $57,929 | **$415,913** | Same travel platform, two rows. Must be treated as one vendor in negotiation. |
| **Amazon Web Services** | "Amazon Web Services Llc" $106,399 + "Amazon Web Services Inc." $5,153 | **$111,552** | Same cloud provider. |
| **HR Solution International** | "Hr Solution International Gmbh" $80,823 + "Hrsolution International Ag" $6,987 | **$87,810** | Same HR firm, two legal entities. |
| **4i Group (consulting/RPO)** | "4I Advisory Services" $71,860 + "4I Management Consulting Private Limited" $12,117 | **$83,977** | Same boutique group, two engagements. |
| **Bupa (health ins.)** | "Bupa- Supplier" $22,800 + "Bupa Australia" $12,463 | **$35,263** | Same insurer across geographies. |
| **Apple retail** | 4 legal entities (UK, Amer, Pty, Distribution Intl) | **$8,256** | Device purchases, non-strategic. |
| **Amazon retail** | "Amazon.Co.Uk" $1,107 + "Amazon (Aus)" $233 | **$1,340** | Office supplies via Amazon retail. |
| **Acclime** | "Acclime Corporate Services" $5,413 + "Acclime Usa, Inc" $4,995 | **$10,408** | Same corporate services provider. |
| **Catering Muring / Mirakul / others** | Multiple catering DOOs | n/a | Multiple small Croatian catering vendors, likely same function (office food). |
| **TM Forum** | "Tmforum" $57,560 + "Tm Forum" $510 | **$58,070** | Same industry association. |

**Action baked in:** when recommending consolidation/termination, all entries of a duplicated vendor are counted together.

## 2. "Vendors" that are actually not vendors

- **`(Blank)` — $137** — null row, probably an accounting artifact.
- **John Smith — $2,163 / Susan Lee — $1,762 / Fabiola Thistlewhaite — $2,154 / Stipe Piric — $2,302 / Ansar Madovic — $1,732 / George Anchor — $2,107** — Individual names, not corporate entities. Likely contractors, expense reimbursements or former employee payouts miscoded as AP vendors. None should be a "terminate" candidate without confirming what they are.
- **Grad Zagreb / Grad Split / Australian Taxation Office / Cayman Islands Government** — Government/statutory fees (permits, filings, corporate taxes). Not discretionary. Cannot be "terminated."
- **Specijalisticka Ordinacija Medicine Rada × 3 / Ustanova Za Medicinu Rada / Nastavni Zavod Dr. Andrija Štampar** — Croatian occupational health / workplace medical exams, **mandatory by Croatian labor law**. Cannot be cut.
- **Bureau Veritas Croatia ($3,200)** — Statutory inspection/certification body.
- **Green Commute Initiative ($5,402)** — UK cycle-to-work benefit scheme (HMRC-backed employee benefit, not a discretionary SaaS).

**Action:** these are segregated into a "Protected / Non-discretionary" bucket and excluded from the savings headline.

## 3. Missing data points that block hard savings numbers

The dataset has **only** three fields: vendor name, trailing-12-month USD spend, and blank columns for us to fill. It does **not** contain:

- Contract start/end dates
- Auto-renewal flags or notice-period requirements
- Business owner / department / cost center
- Tier/seats/volume behind the spend
- Whether the vendor is flagged as "acquisition thesis protected"
- Whether the acquirer (parent co.) has an in-house replacement capability
- Contract currency (spend is normalized to USD but underlying contracts may be GBP, EUR, HRK/EUR, INR, AUD, SGD — FX exposure matters for negotiation)

**Consequence:** any claim of "terminate in 30 days" is speculative. Every recommendation we make is labeled **Savings** (executable with standard 30-60-day notice) or **Pipeline** (depends on contract data we don't have). Exit fees are assumed unknown and flagged as a material risk.

## 4. Misleading totals / concentration

- **Salesforce alone = $3,117,226 = 39.8% of total spend.** Any "vendor rationalization" program that doesn't touch Salesforce is cosmetic.
- Top 5 vendors (Salesforce, Navan, BDO, TOG UK, Cloudcrossing) = **$4,290,787 = 54.7%** of total.
- Top 13 vendors (>$100K each) = **$5,390,327 = 68.8%** of total.
- Bottom 178 vendors (<$1K each) = $55,358 = 0.7%. *These are not savings opportunities individually; they are a process problem (AP sprawl) that costs more to manage than the savings justify.*

## 5. Suspicious patterns worth investigating

- **Cloudcrossing BVBA — $208,675.** Belgian shell-typical name, no recognizable brand. Could be an IT services / offshore dev shop, a licensing vehicle, or a related-party transaction. Marked **Investigation** — requires counterparty diligence before any action.
- **HR Solution International GmbH — $80,823.** Very high for "HR services" without further specification. Investigate scope.
- **Harmonic Group Limited — $65,418.** Generic name, unknown function — investigate.
- **Cloud Technology Solutions Ltd — $60,661.** Likely a Google Workspace / cloud reseller. Verify whether this is a reseller markup on top of spend we'd pay Google directly.
- **Tmforum — $57,560.** Industry association for telecoms. If this company isn't a telecom, membership is likely vestigial.
- **4i Advisory + 4i Management Consulting — $83,977 combined.** Role overlap with BDO, Grant Thornton, RSM, PwC, Houlihan Lokey, Vector Capital, Westbrook Advisers, RSM UK Corporate Finance — need scope clarification.
- **Westbrook Advisers — $15,360 / Houlihan Lokey — $37,461 / Vector Capital Management — $32,427.** These names read like M&A / corporate finance advisors — likely one-time transaction fees tied to the acquisition itself. **Cannot be extrapolated as recurring run-rate.** Flag and exclude from savings base.
- **RSM UK Corporate Finance ($117,078)** — same pattern. Also likely transaction-driven.

## 6. Geographic fragmentation

Offices or coworking are scattered across at least 6 locations — London (TOG, GPT, WeWork implied, Common Desk), Zagreb (Zagrebtower, Weking, Jones Lang Lasalle NSW is Sydney), Chennai (Innovent Spaces), Singapore (WeWork SG), Sydney (JLL NSW), plus individual-office expenses. **~$1M combined real-estate spend across fragmented leases**, typical of a post-acquisition footprint that wasn't rationalized.

## 7. Fragmented categories (key consolidation candidates)

Raw counts (before consolidation) of vendors by function:

| Function | # vendors | Approx. combined spend | Consolidation opportunity |
|---|---|---|---|
| Audit / Tax / Accounting firms | 18+ | ~$680K | Single Big-4 or single mid-tier |
| Legal firms / notaries | 17+ | ~$130K | Panel of 2–3 firms |
| Recruitment / staffing agencies | 14+ | ~$280K | Master vendor + LinkedIn |
| Real estate / coworking | 12+ | ~$1.05M | Rationalize geographies |
| Health / life insurance brokers | 13+ | ~$400K | Global broker of record |
| Catering / office food | 10+ | ~$25K | One caterer per office |
| Croatian small vendors (D.O.O.) | ~80 | ~$250K | Local AP consolidation |

## 8. Dataset classification confidence

- **High confidence** (recognizable global brand, well-known function): ~60% of rows.
- **Medium confidence** (recognizable brand, function inferred from name): ~25%.
- **Low confidence** (opaque name, Croatian local vendor, or ambiguous role): ~15%. For these I label function from name pattern + spend size and flag ambiguity in the description where meaningful.

## How these issues are handled downstream

1. **Classified CSV (`outputs/02-vendors-classified.csv`)** carries every vendor, even non-discretionary ones, with Department = "Protected / Statutory" where applicable so nothing is hidden.
2. **Duplicated vendors** each keep their row (reversible to the source data), but the recommendation text ties them together and the savings math counts them once.
3. **Unknown-function vendors** get **"Investigation"** rather than a committed recommendation — per the assessment rules, no number is stated until scope is confirmed.
4. **Acquisition-thesis protection** is unknown — every high-spend vendor carries a "confirm thesis status" flag in the memo before any savings is declared final.
5. **Transaction-related advisors** (Houlihan, Vector, Westbrook, RSM CF) are excluded from run-rate savings; they are one-time deal fees.
