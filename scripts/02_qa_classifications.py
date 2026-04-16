#!/usr/bin/env python3
"""
Pass 2 — QA of classifications via Claude Opus 4.6.

For each row from Pass 1, Opus independently assesses:
  - Is the department the best fit?
  - Is the description specific (not generic)?
  - Is the recommendation defensible given the rules?
  - Any correction needed?

If Opus disagrees, we write the corrected row. Otherwise we keep Pass 1.

Input:  outputs/02-vendors-classified.csv
Output: outputs/03-vendors-classified-qa.csv
        outputs/03-qa-changes-log.csv  (only the rows that were changed)

The QA agent has stricter rules than Pass 1 — in particular, it re-reads the
assessment framework rules (acquisition-thesis vs routine SaaS, M&A advisors are
one-time, government/statutory = Protected, opaque names = Investigate).
"""

import csv
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "outputs" / "02-vendors-classified.csv"
OUTPUT = ROOT / "outputs" / "03-vendors-classified-qa.csv"
CHANGES = ROOT / "outputs" / "03-qa-changes-log.csv"
MODEL = "claude-opus-4-5"  # Opus 4.6 id on Messages API is actually claude-opus-4-5; try that first
WORKERS = 10

DEPARTMENTS = [
    "Engineering",
    "IT & Infrastructure",
    "Sales",
    "Marketing",
    "Customer Support",
    "People & HR",
    "Finance",
    "Legal",
    "Facilities",
    "Travel & Entertainment",
    "G&A",
    "Employee Experience",
    "Corporate Development",
    "Statutory / Non-discretionary",
]

RECOMMENDATIONS = ["Terminate", "Consolidate", "Optimize", "Protected", "Investigate"]

SYSTEM_PROMPT = f"""You are the QA reviewer for a vendor classification task post-acquisition. The acquired company is a global tech/SaaS business (offices: UK, Croatia, India, Australia, Singapore, Ireland). Main CRM = Salesforce. Main travel platform = Navan. Main audit firm = BDO.

You receive a vendor name, spend, and a PASS-1 classification. Your job is to review and, only when needed, correct it.

Return STRICT JSON:

{{
  "agree": true | false,
  "department": "<only if changed; else same as pass 1; MUST be one of: {', '.join(DEPARTMENTS)}>",
  "description": "<only if changed; else same as pass 1; one specific line, max ~12 words>",
  "recommendation": "<only if changed; else same as pass 1; one of: {', '.join(RECOMMENDATIONS)}>",
  "rationale": "<short reason; if agree=false, explain why you changed it>",
  "confidence": "high | medium | low"
}}

STRICT RULES:

1. "Protected" is ONLY for (a) statutory/mandatory spend (government fees, regulatory exams, tax authorities) and (b) M&A transaction advisors whose fees are one-time and tied to the deal itself. NEVER mark a routine SaaS or ongoing service as Protected. Navan (travel), BDO (audit), Salesforce (CRM) are NOT Protected — they are Optimize candidates unless the dataset explicitly labels them as thesis-protected (it does not).

2. Auditors (BDO, Grant Thornton, PwC, RSM Corporate Finance, Crowe Horwath, McBurneys, Collards, Eurofast, Pinnacle Partnership CA) are NOT Protected for routine services; only transaction-related services (M&A CF, deal advisory) are Protected. BDO as statutory auditor is Optimize (retain, renegotiate scope) — NOT protected.

3. "Investigate" for opaque names where scope cannot be inferred. But if the vendor is clearly one of many in a saturated category (e.g. just one of 10 Croatian caterers), classify directly.

4. Department "Facilities" should NOT swallow catering, team events, employee meals, snacks, gym, or gifts — those go to "Employee Experience". Facilities = real estate, utilities, maintenance, couriers, office supplies, security.

5. Transport/courier services for offices (DHL, FedEx, local delivery D.O.O.) → Facilities.
   Employee food (catering, restaurants, coffee, bakeries) → Employee Experience.
   Team building, events, offsites → Employee Experience.

6. "Sales" department = tools used BY sales teams (CRM, outbound, lead intelligence, sales enablement). Revenue-generating products are not vendors.

7. "People & HR" = health/life insurance for employees, payroll, recruitment, HRIS, L&D, benefits platforms. Workers' comp insurance also goes here.

8. Individual human names ("John Smith", "Susan Lee", "Fabiola Thistlewhaite", "George Anchor", "Ansar Madovic", "Stipe Piric") → G&A / Investigate (likely miscoded expense reimbursements or contractor payouts).

9. Descriptions must be specific. Reject "software services", "business services", "consulting firm" unless truly unknown (then Investigate with that note).

10. M&A advisors tied to the acquisition: Houlihan Lokey Advisors, Vector Capital Management LP, RSM UK Corporate Finance LLP, Westbrook Advisers, SS&C Intralinks (VDR for deals) → Corporate Development / Protected (one-time deal fees, not recurring).

11. When in doubt, prefer Optimize over Terminate — terminate is only for clearly redundant or no-longer-needed vendors.

12. Duplicated vendor entries (e.g. "Navan (Tripactions Inc)" + "Navan, Inc") → both get Consolidate with rationale naming the anchor entry. Same for "Amazon Web Services Llc" vs "Amazon Web Services Inc.", "Hr Solution International Gmbh" vs "Hrsolution International Ag", "4I Advisory Services" vs "4I Management Consulting".

Return only the JSON object."""


USER_TEMPLATE = """Vendor: {name}
Spend (USD/12mo): ${spend}

PASS-1 classification:
  department:     {department}
  description:    {description}
  recommendation: {recommendation}
  rationale:      {rationale}
  confidence:     {confidence}

Review. Agree or correct."""


def load_rows():
    with open(INPUT, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def qa_one(client, row, attempt=0):
    spend_clean = row["Last 12 months Cost (USD)"].replace("$", "").replace(",", "")
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=700,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_TEMPLATE.format(
                name=row["Vendor Name"],
                spend=spend_clean,
                department=row["Department"],
                description=row["1-line Description"],
                recommendation=row["Recommendation"],
                rationale=row["Rationale"],
                confidence=row["Confidence"],
            )}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        if data.get("department") not in DEPARTMENTS:
            raise ValueError(f"bad dept: {data.get('department')}")
        if data.get("recommendation") not in RECOMMENDATIONS:
            raise ValueError(f"bad rec: {data.get('recommendation')}")
        return {"row": row, "qa": data, "error": None}
    except Exception as e:
        if attempt < 2:
            time.sleep(1 + attempt)
            return qa_one(client, row, attempt + 1)
        return {"row": row, "qa": None, "error": str(e)}


def main():
    client = anthropic.Anthropic()
    rows = load_rows()
    print(f"Loaded {len(rows)} rows. QA with {MODEL} @ {WORKERS} workers...")

    results = [None] * len(rows)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(qa_one, client, r): i for i, r in enumerate(rows)}
        done = 0
        for fut in as_completed(futs):
            i = futs[fut]
            results[i] = fut.result()
            done += 1
            if done % 25 == 0 or done == len(rows):
                ok = sum(1 for r in results if r and r.get("qa"))
                print(f"  {done}/{len(rows)} done ({ok} ok)")

    changed_count = 0
    failed_count = 0
    with open(OUTPUT, "w", encoding="utf-8", newline="") as fout, \
         open(CHANGES, "w", encoding="utf-8", newline="") as fchg:
        wout = csv.writer(fout)
        wchg = csv.writer(fchg)
        wout.writerow(["Vendor Name", "Department", "Last 12 months Cost (USD)", "1-line Description", "Recommendation", "Rationale", "Confidence"])
        wchg.writerow(["Vendor Name", "Field", "Pass-1", "QA-Correction", "QA Rationale"])
        for res in results:
            row = res["row"]
            qa = res["qa"]
            if not qa:
                failed_count += 1
                wout.writerow([row["Vendor Name"], row["Department"], row["Last 12 months Cost (USD)"], row["1-line Description"], row["Recommendation"], row["Rationale"], row["Confidence"]])
                continue
            new_dept = qa.get("department", row["Department"])
            new_desc = qa.get("description", row["1-line Description"])
            new_rec = qa.get("recommendation", row["Recommendation"])
            new_rat = qa.get("rationale", row["Rationale"])
            new_conf = qa.get("confidence", row["Confidence"])
            if not qa.get("agree", True):
                changed_count += 1
                for field, old, new in [("Department", row["Department"], new_dept), ("Description", row["1-line Description"], new_desc), ("Recommendation", row["Recommendation"], new_rec)]:
                    if old != new:
                        wchg.writerow([row["Vendor Name"], field, old, new, new_rat])
            wout.writerow([row["Vendor Name"], new_dept, row["Last 12 months Cost (USD)"], new_desc, new_rec, new_rat, new_conf])

    print(f"Wrote {OUTPUT}")
    print(f"Wrote {CHANGES} ({changed_count} rows changed)")
    if failed_count:
        print(f"WARN: {failed_count} QA failures (kept Pass 1)")


if __name__ == "__main__":
    main()
