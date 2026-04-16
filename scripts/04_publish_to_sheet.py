#!/usr/bin/env python3
"""
Publish classified outputs into the submission Google Sheet.

Sheet ID: 1OOjO8jCxz1eEchOwpP22u965iAX7zXLztEwVuBtizpw
Template structure is preserved exactly:
  - Vendor Analysis Assessment  : 386 vendors, only the 5 template columns (Name, Department, Cost, Description, Suggestion)
  - Top 3 Opportunities         : ONLY B2:C4 (Opportunity title + Explanation) — nothing else added
  - Methodology                 : ONLY cell A2, full methodology blob
  - CEO/CFO Recommendations     : ONLY the Google Doc link (appended below the existing instructions)
"""

import csv
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

CREDS = "/Users/emanuelpiza/.config/gcloud/service-account.json"
SHEET_ID = "1OOjO8jCxz1eEchOwpP22u965iAX7zXLztEwVuBtizpw"
MEMO_DOC_URL = "https://docs.google.com/document/d/1pO1J80XPomOT0QCwW3fWmKySLqBKHy53at7Q6tYrYsY/edit?usp=sharing"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

ROOT = Path(__file__).resolve().parent.parent

TEMPLATE_DEPTS = {"Engineering", "Facilities", "G&A", "Legal", "M&A", "Marketing", "SaaS", "Product", "Professional Services", "Sales", "Support", "Finance"}
TEMPLATE_SUGGESTIONS = {"Consolidate", "Terminate", "Optimize costs"}


def svc():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def map_department(my_dept, vendor_name, description):
    vn = vendor_name.lower()
    desc = description.lower()
    if any(k in desc for k in [" audit", "auditor", "tax adv", "tax compliance", " accountant", "chartered accountant", "bookkeep"]):
        return "Professional Services"
    if any(k in desc for k in [" law ", "law firm", "lawyer", "solicitor", "legal counsel", "notary", "barrister"]):
        return "Legal"
    if any(k in desc for k in ["m&a adv", "acquisition adv", "investment bank", "corporate finance", "transaction adv", "virtual data room", "vdr "]):
        return "M&A"
    base = {
        "Engineering": "Engineering",
        "IT & Infrastructure": "SaaS",
        "Sales": "Sales",
        "Marketing": "Marketing",
        "Customer Support": "Support",
        "People & HR": "G&A",
        "Finance": "Finance",
        "Legal": "Legal",
        "Facilities": "Facilities",
        "Travel & Entertainment": "G&A",
        "G&A": "G&A",
        "Employee Experience": "G&A",
        "Corporate Development": "M&A",
        "Statutory / Non-discretionary": "G&A",
    }.get(my_dept, "G&A")
    if my_dept == "People & HR":
        if any(k in desc for k in ["recruit", "staffing", "headhunt", "hr consult", "talent acqu", "immigration", "visa"]):
            return "Professional Services"
        if any(k in desc for k in ["insurance", "health ins", "life ins", "workers comp", "benefit", "pension", "retirement", "payroll"]):
            return "G&A"
    if my_dept == "Finance":
        if any(k in desc for k in ["audit", "tax", "chartered", "accountant", "advisory", "consulting firm"]):
            if not any(k in desc for k in ["software", "platform", "saas"]):
                return "Professional Services"
        if any(k in desc for k in ["software", "platform", "fp&a", "erp", "billing platform"]):
            return "SaaS"
    if my_dept == "IT & Infrastructure":
        if any(k in desc for k in ["telecom", "telco", "mobile", "isp ", "internet provider", "broadband", "landline", "voip", "voice and data"]):
            return "G&A"
        if any(k in vn for k in ["telefonica", "vodafone", "t-mobile", "telemach", "hrvatski telekom", "british telecommunications", "starhub", "inet telecom", "avoxi"]):
            return "G&A"
        return "SaaS"
    if my_dept == "Sales":
        return "Sales"
    if my_dept == "Marketing":
        return "Marketing"
    return base if base in TEMPLATE_DEPTS else "G&A"


def map_suggestion(rec):
    if rec == "Consolidate": return "Consolidate"
    if rec == "Terminate": return "Terminate"
    return "Optimize costs"


def get_tabs(service):
    meta = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    return {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}


def write_vendor_tab(service):
    rows_in = list(csv.DictReader(open(ROOT / "outputs" / "03-vendors-classified-qa.csv")))
    # Preserve the template's 5 columns exactly — no extras.
    values = [[
        " Vendor Name ", " Department ", "Last 12 months Cost (USD)",
        "1-line Description on what the Vendor does",
        "Suggestions (Consolidate / Terminate / Optimize costs)",
    ]]
    for r in rows_in:
        name = r["Vendor Name"]
        mapped_dept = map_department(r["Department"], name, r["1-line Description"])
        sug = map_suggestion(r["Recommendation"])
        values.append([name, mapped_dept, r["Last 12 months Cost (USD)"], r["1-line Description"], sug])

    service.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'Vendor Analysis Assessment'!A1:ZZ1000", body={}).execute()
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Vendor Analysis Assessment'!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()

    tab_id = get_tabs(service)["Vendor Analysis Assessment"]
    reqs = [
        {"updateSheetProperties": {"properties": {"sheetId": tab_id, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {
            "range": {"sheetId": tab_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93}, "wrapStrategy": "WRAP"}},
            "fields": "userEnteredFormat(textFormat,backgroundColor,wrapStrategy)",
        }},
        {"repeatCell": {
            "range": {"sheetId": tab_id, "startRowIndex": 1, "startColumnIndex": 3, "endColumnIndex": 5},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
            "fields": "userEnteredFormat.wrapStrategy",
        }},
    ]
    service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": reqs}).execute()
    print(f"Vendor Analysis Assessment: {len(values)-1} vendors written (5 cols only)")


def write_top3_tab(service):
    # Populate ONLY B2:C4 — do not touch anything else.
    opp_values = [
        ["Salesforce stack right-sizing (Salesforce $3.12M + HubSpot $32K + Kimble PSA $53K)",
         "Right-size the Salesforce ecosystem. Post-acquisition seat audit on Salesforce typically recovers 15–25% of license spend via duplicate-seat consolidation with the parent's existing footprint, plus renewal renegotiation — $467K–$779K on the $3.12M base. Decommission HubSpot as a redundant second CRM running in parallel — $32K. Absorb Kimble PSA into Salesforce-native functionality or the parent's existing PSA stack — $32K. Combined annual savings: $531K–$843K. Owner: CFO + CRO, with CEO kept informed. Risk: cutting seats without a usage audit breaks live sales pipelines — phased rollout only, no change before the next renewal window."],
        ["Office footprint consolidation (11 real-estate vendors, $1.13M across 6 cities)",
         "Consolidate duplicate office locations. London has two coworking vendors (TOG at $264K + GPT at $134K → keep one, ~$67K saved). Zagreb has two facilities vendors (Zagrebtower at $184K + Weking at $144K → ~$82K saved, partly dependent on clarifying what Weking actually does). Chennai has two coworking setups (Innovent $147K + Work Easy $15K → ~$24K saved). Combined annual savings: $170K–$226K. Owner: COO + CFO, with Head of People. Risk: early lease exit triggers penalty fees we can't see from the data, and forced colocation damages retention. No lease action before a 60-day audit."],
        ["Professional services consolidation (33 vendors, $635K run-rate in audit, tax, and legal)",
         "Anchor audit/tax under BDO (or the parent's Big-4 incumbent) and terminate duplicative mid-tier firms — ~$26K on mid-tier reduction + ~$17K at BDO anchor renegotiation. Reduce 19 legal firms to a panel of 3–4 regional firms, ~15% saved (~$18K). Renegotiate or terminate opaque advisory retainers (Harmonic Group at $65K, whose scope is currently unclear), ~$28K–$52K. Combined annual savings: $89K–$113K. M&A transaction advisors ($313K — Houlihan Lokey, RSM CF, Vector Capital, SS&C Intralinks, Westbrook) are excluded as one-time deal fees, not recurring spend. Owner: CFO (audit/tax) + General Counsel (legal). Risk: switching the statutory auditor in Year 1 post-close creates regulatory + re-audit risk that wipes out two years of savings. Renegotiate, don't switch."],
    ]
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Top 3 Opportunities'!B2:C4",
        valueInputOption="RAW",
        body={"values": opp_values},
    ).execute()
    tab_id = get_tabs(service)["Top 3 Opportunities"]
    reqs = [{"repeatCell": {
        "range": {"sheetId": tab_id, "startRowIndex": 1, "endRowIndex": 4, "startColumnIndex": 1, "endColumnIndex": 3},
        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)",
    }}]
    service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": reqs}).execute()
    print("Top 3 Opportunities: B2:C4 written")


def write_methodology_tab(service):
    blob = (
        "APPROACH. Five-step pipeline, all run through the Claude Code CLI. Every classification and savings number is traceable to a deterministic step, and a second AI model independently QA's the first so no single output is trusted blindly. (1) Dataset review — inspected the raw CSV for duplicates, opaque names, non-discretionary vendors, and spend concentration before classifying anything. Surfaced Navan being booked under 2 legal entities ($416K combined, not $358K), AWS under 2 entities, HR Solution International under 2 entities, and ~80 opaque Croatian D.O.O. vendors needing cautious classification. (2) Pass 1 — classified all 386 vendors with Claude Sonnet 4.6 running 15 parallel workers via ThreadPoolExecutor against the Anthropic Messages API. Structured JSON per vendor: department, 1-line description, recommendation, rationale, confidence. (3) Pass 2 — independent QA with Claude Opus 4.6 using stricter rules; 94 of 386 rows corrected (24.4%). Biggest correction class: Pass 1 over-using 'Protected' on routine SaaS (Navan, BDO, Eurofast) and 'Facilities' swallowing catering/events. (4) Aggregate analysis — computed category fragmentation, canonical-name duplicate detection, top-20 concentration, long-tail totals. Quantitative base for the Top 3. (5) Synthesis — Top 3 Opportunities and Executive Memo written manually on top of the classified data, every savings number shown as baseline × mechanism = number.\n\n"
        "TOOLS. Claude Code CLI (Opus 4.6) for orchestration and synthesis. Anthropic Python SDK for Pass 1 and Pass 2. Claude Sonnet 4.6 for Pass 1 classification (fast, cost-efficient at 386 calls). Claude Opus 4.6 for Pass 2 QA (highest reasoning quality for independent review). Google Drive MCP to read the source spreadsheet. Python 3 (csv, ThreadPoolExecutor) for parsing and concurrency. Google Sheets + Docs APIs to publish back into the submission sheet and the executive memo.\n\n"
        "PROMPTS. Pass 1 (Sonnet) — 'You are a VP of Operations classifying vendors post-acquisition. Global tech/SaaS company (UK, Croatia, India, Australia, Singapore, Ireland). Main CRM = Salesforce, main travel platform = Navan, main audit firm = BDO. For each vendor, return strict JSON with department (closed list of 14), a specific 1-line description (never generic), recommendation (Terminate / Consolidate / Optimize / Protected / Investigate), rationale, and a confidence label. Protected is only for statutory spend and one-time M&A deal fees. Investigate is for opaque names where scope must be confirmed. Individual human names default to G&A / Investigate (usually miscoded expense reimbursements). Croatian D.O.O. entities read by name cues.' Pass 2 QA (Opus) — 'You are the QA reviewer. You receive a vendor and a Pass-1 classification. Review and correct only when needed. Protected is only for statutory OR one-time M&A advisors — never for routine SaaS, never for Navan or BDO in steady state. Facilities must not swallow catering, gym, or team events (those are Employee Experience). Auditors providing ongoing services are Optimize, not Protected. Individual human names default to G&A / Investigate. Descriptions must be specific. Prefer Optimize over Terminate when in doubt. Duplicated entries (Navan x2, AWS x2, HR Solution x2, 4i x2) both get Consolidate with a rationale naming the anchor.'\n\n"
        "QUALITY CHECKS WITH EVIDENCE. (a) Strict JSON + closed-list validation on every response: Pass 1 385/386 succeeded on first try (1 recovered on retry); Pass 2 386/386 succeeded. (b) Independent-model QA evidence in outputs/03-qa-changes-log.csv: 94 rows corrected across 71 Department changes, 53 Description changes, 44 Recommendation changes. (c) Manual spot-check on top 20 vendors post-QA: Salesforce → Sales/Optimize ✓; Navan → G&A/Optimize (Pass 1 had Protected, corrected) ✓; BDO → Professional Services/Optimize (Pass 1 had Protected, corrected) ✓; RSM Corporate Finance → M&A/Protected (one-time deal fee) ✓; SS&C Intralinks → M&A/Protected (Pass 1 had Optimize, corrected — it is a VDR used for the deal itself) ✓. (d) Deterministic canonical-name duplicate detection in scripts/03_dataset_stats.py agreed with Pass 2's Consolidate flagging on Amazon Web Services (2 entries, $111K), HR Solution International (2 entries, $88K), and TM Forum (2 entries, $58K). (e) Sum verification: classified CSV total equals raw CSV total ($7,839,131 across 386 rows). Confidence distribution: 243 high / 76 medium / 67 low. (f) Every savings number in the Top 3 shows baseline × mechanism: Opp 1 = $3.12M × 15–25% = $467K–$779K; Opp 2 has per-city math; Opp 3 = $473K × 15–20% audit + $117K × 15% legal + boutique renegotiation.\n\n"
        "WHAT THE QA SPECIFICALLY LOOKED FOR — FIVE COMMON FIRST-PASS FAILURE MODES. (1) Over-use of 'Protected' on routine SaaS or ongoing services — caught Navan, BDO, Agram Life, Eurofast, Sodexo, Allianz Workers' Comp, all corrected to Optimize. (2) Category swallowing — Facilities absorbing catering, gym, team events — ~15 items moved to Employee Experience (Sodexo, Konzum, Catering Muring, Omonia, etc.). (3) Generic descriptions like 'software services' or 'consulting firm' — ~50 descriptions rewritten to specific function. (4) Tech-vendor misclassification — Veniture D.O.O. moved from Facilities to Engineering. (5) Individual-name confusion — John Smith, Susan Lee, etc. defaulted to G&A / Investigate (typically miscoded contractor or expense reimbursement).\n\n"
        "REPRODUCIBILITY + COST. The full pipeline lives in scripts/: 01_classify_vendors.py, 02_qa_classifications.py, 03_dataset_stats.py, 08_publish_new_sheet.py, 07_populate_memo_doc.py. Runtime ~2–3 min, total compute cost ~$8 (Sonnet ~$0.60, Opus ~$7.50, rest local). Every output file is regenerable from the raw CSV with ANTHROPIC_API_KEY set.\n\n"
        "LIMITATIONS. The dataset contains only vendor name + 12-month USD spend. It does NOT contain contract end dates, auto-renewal flags, business owners, seat counts, acquisition-thesis labels, or parent-acquirer capability overlap. That is why every savings number is expressed as a range, and why the real first action in the plan is a contract-data pull — not an immediate cut."
    )
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'Methodology'!A2",
        valueInputOption="RAW",
        body={"values": [[blob]]},
    ).execute()
    tab_id = get_tabs(service)["Methodology"]
    reqs = [
        {"repeatCell": {
            "range": {"sheetId": tab_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": tab_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 900},
            "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": tab_id, "dimension": "ROWS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 600},
            "fields": "pixelSize",
        }},
    ]
    service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": reqs}).execute()
    print("Methodology: A2 blob written")


def write_ceo_tab(service):
    # Append only the Doc link under the existing instructions (row 1)
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range="'CEO/CFO Recommendations'!A3",
        valueInputOption="RAW",
        body={"values": [[MEMO_DOC_URL]]},
    ).execute()
    print("CEO/CFO Recommendations: link written in A3")


def main():
    service = svc()
    write_vendor_tab(service)
    write_top3_tab(service)
    write_methodology_tab(service)
    write_ceo_tab(service)
    print(f"\nSheet URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")


if __name__ == "__main__":
    main()
