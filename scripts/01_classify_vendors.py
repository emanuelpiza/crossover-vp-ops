#!/usr/bin/env python3
"""
Pass 1 — Vendor classification via Claude Sonnet 4.6.

Input:  inputs/vendors_raw.csv
Output: outputs/02-vendors-classified.csv

For each vendor we ask the model to return a JSON with:
  - department  (one of a closed list)
  - description (one concise line, specific, max ~12 words)
  - recommendation (Terminate | Consolidate | Optimize | Protected | Investigate)
  - rationale   (short, defensible, cites overlap/duplicate vendors when relevant)
  - confidence  (high | medium | low)

Parallelism: ThreadPoolExecutor, 15 workers (conservative re: rate limits).
"""

import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "inputs" / "vendors_raw.csv"
OUTPUT = ROOT / "outputs" / "02-vendors-classified.csv"
MODEL = "claude-sonnet-4-5"  # Sonnet 4.6 id for Messages API
WORKERS = 15

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

SYSTEM_PROMPT = f"""You are a VP of Operations classifying vendors after an acquisition. The acquired company is a global tech/SaaS business with offices across UK, Croatia (Zagreb/Split), India (Chennai), Australia (Sydney/Melbourne), Singapore, and Ireland. The main CRM is Salesforce. The main travel platform is Navan. The main audit firm is BDO.

For each vendor I give you, return STRICT JSON with these keys:

{{
  "department": "<one of: {', '.join(DEPARTMENTS)}>",
  "description": "<one concise line, max ~12 words, specific function — NEVER generic like 'business services'>",
  "recommendation": "<one of: {', '.join(RECOMMENDATIONS)}>",
  "rationale": "<one short sentence defending the recommendation; if consolidate, name the anchor vendor; if investigate, state what must be confirmed>",
  "confidence": "<high | medium | low>"
}}

RULES:

1. Use "Terminate" only when the vendor is clearly non-essential, duplicative of a larger anchor, or the function is no longer needed post-M&A.
2. Use "Consolidate" when multiple vendors serve the same function and one anchor dominates (e.g. HubSpot → consolidate into Salesforce; Zapier → consolidate into Workato; Amazon Web Services Inc. → consolidate into Amazon Web Services Llc).
3. Use "Optimize" for vendors that stay but have room to cut spend (renegotiate, right-size, reduce seats).
4. Use "Protected" for statutory/mandatory spend (government fees, Croatian occupational-health medical exams, tax authorities, regulatory filings) AND for M&A transaction advisors whose fees are one-time (Houlihan Lokey, Vector Capital Mgmt, RSM UK Corporate Finance, Westbrook Advisers).
5. Use "Investigate" when the vendor name is opaque, the function is ambiguous, or scope must be confirmed before any action (e.g. "Cloudcrossing BVBA", "Harmonic Group Limited"). Do not guess.
6. Individual human names (e.g. "John Smith", "Susan Lee") are almost always misbooked contractor payouts or expense reimbursements — classify as Investigate with department G&A, low confidence.
7. Croatian D.O.O. entities are usually local offices vendors: catering, transport, maintenance, small IT, event services. Use name cues.
8. Never output a department outside the closed list. Never output a recommendation outside the closed list.
9. Descriptions must be specific. "Cloud services" is bad. "AWS cloud infrastructure (EC2/S3/RDS)" is good. "UK commercial law firm — contracts and M&A" is good.
10. If the vendor is clearly one of several for the same function, mention that in rationale (e.g. "one of 18 audit/accounting firms — consolidate under BDO").

Return ONLY the JSON object, no prose, no markdown fences."""

USER_TEMPLATE = """Vendor name: {name}
Trailing-12-month spend (USD): ${spend}

Classify this vendor. Return only the JSON."""


def load_vendors():
    out = []
    with open(INPUT, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            if len(row) < 3:
                continue
            name = row[0].strip()
            spend_raw = row[2].strip().replace("$", "").replace(",", "").replace('"', "")
            try:
                spend = float(spend_raw)
            except ValueError:
                spend = 0.0
            if name:
                out.append({"name": name, "spend": spend})
    return out


def classify_one(client, vendor, attempt=0):
    try:
        msg = client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_TEMPLATE.format(name=vendor["name"], spend=f"{vendor['spend']:,.0f}")}],
        )
        raw = msg.content[0].text.strip()
        # strip markdown fences just in case
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        # validation
        if data.get("department") not in DEPARTMENTS:
            raise ValueError(f"bad dept: {data.get('department')}")
        if data.get("recommendation") not in RECOMMENDATIONS:
            raise ValueError(f"bad rec: {data.get('recommendation')}")
        data["_ok"] = True
        return {**vendor, **data}
    except Exception as e:
        if attempt < 2:
            time.sleep(1 + attempt)
            return classify_one(client, vendor, attempt + 1)
        return {**vendor, "department": "G&A", "description": "CLASSIFICATION FAILED", "recommendation": "Investigate", "rationale": f"error: {e}", "confidence": "low", "_ok": False}


def main():
    client = anthropic.Anthropic()
    vendors = load_vendors()
    print(f"Loaded {len(vendors)} vendors. Classifying with {MODEL} @ {WORKERS} workers...")

    results = [None] * len(vendors)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(classify_one, client, v): i for i, v in enumerate(vendors)}
        done = 0
        for fut in as_completed(futs):
            i = futs[fut]
            results[i] = fut.result()
            done += 1
            if done % 25 == 0 or done == len(vendors):
                ok = sum(1 for r in results if r and r.get("_ok"))
                print(f"  {done}/{len(vendors)} done ({ok} ok)")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Vendor Name", "Department", "Last 12 months Cost (USD)", "1-line Description", "Recommendation", "Rationale", "Confidence"])
        for r in results:
            w.writerow([
                r["name"],
                r["department"],
                f"${r['spend']:,.0f}",
                r["description"],
                r["recommendation"],
                r["rationale"],
                r["confidence"],
            ])
    print(f"Wrote {OUTPUT}")

    failed = [r for r in results if not r.get("_ok")]
    if failed:
        print(f"WARN: {len(failed)} failed classifications:")
        for r in failed[:10]:
            print(f"  - {r['name']}: {r['rationale']}")


if __name__ == "__main__":
    main()
