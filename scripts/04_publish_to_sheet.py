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


def _build_formatted_cell(markdown_text):
    """Convert a string with **bold** markers into a Sheets API cell with textFormatRuns.
    Returns a dict suitable for rows[].values[] in an updateCells request."""
    plain = []
    runs = []
    i = 0
    pos = 0
    current_bold = False
    # seed a default (non-bold) run at 0
    runs.append({"startIndex": 0, "format": {"bold": False}})
    while i < len(markdown_text):
        if markdown_text[i:i+2] == "**":
            # toggle bold
            current_bold = not current_bold
            runs.append({"startIndex": pos, "format": {"bold": current_bold}})
            i += 2
        else:
            plain.append(markdown_text[i])
            pos += 1
            i += 1
    # dedupe consecutive runs with same format
    cleaned = []
    for r in runs:
        if cleaned and cleaned[-1]["format"] == r["format"]:
            continue
        cleaned.append(r)
    return {
        "userEnteredValue": {"stringValue": "".join(plain)},
        "textFormatRuns": cleaned,
        "userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"},
    }


def write_top3_tab(service):
    # Short titles (B2:B4) + rich explanations with bold + line breaks (C2:C4)
    titles = [
        "Salesforce stack right-sizing",
        "Office footprint consolidation",
        "Professional services consolidation",
    ]
    explanations = [
        (
            "**Annual savings: $531K – $843K.** Owner: CFO + CRO, CEO informed.\n\n"
            "Covers **Salesforce ($3.12M) + HubSpot ($32K, a redundant second CRM) + Kimble PSA ($53K)** — 40.9% of total vendor spend.\n\n"
            "**Mechanism:**\n"
            "• Salesforce seat audit: post-acquisition seat audits typically recover 15–25% of license spend via duplicate-seat consolidation with the parent's existing Salesforce footprint + renewal renegotiation → **$467K–$779K** on the $3.12M base.\n"
            "• HubSpot decommission: remove as duplicate CRM after a 30-day usage audit → **$32K**.\n"
            "• Kimble PSA absorption: fold into Salesforce-native functionality or the parent's existing PSA stack → **$32K**.\n\n"
            "**Risk:** cutting Salesforce seats without a usage audit breaks live sales pipelines. Phased rollout only; no change before the next renewal window."
        ),
        (
            "**Annual savings: $170K – $226K.** Owner: COO + CFO, with Head of People.\n\n"
            "**11 real-estate vendors, $1.13M across 6 cities.** Consolidate duplicate locations:\n\n"
            "• **London:** TOG ($264K) + GPT ($134K) → keep one, sublease the other → **~$67K**.\n"
            "• **Zagreb:** Zagrebtower ($184K) + Weking ($144K, scope currently unclear) → ~25% reduction on combined → **~$82K**.\n"
            "• **Chennai:** Innovent ($147K) + Work Easy ($15K) → collapse into one → **~$24K**.\n\n"
            "**Risk:** early lease exit triggers penalty fees not visible in the dataset; forced colocation damages retention. No lease action before a 60-day break-clause + headcount audit."
        ),
        (
            "**Annual savings: $89K – $113K.** Owner: CFO (audit/tax) + General Counsel (legal).\n\n"
            "**33 audit, tax, and legal vendors totaling $635K recurring.** M&A transaction advisors ($313K — Houlihan Lokey, RSM CF, Vector Capital, SS&C Intralinks, Westbrook) excluded as one-time deal fees.\n\n"
            "**Mechanism:**\n"
            "• Anchor audit/tax under BDO (or the parent's Big-4 incumbent) and terminate mid-tier duplicates (Grant Thornton, Crowe Horwath, Collards, Eurofast, etc.) → **~$26K** + BDO scope renegotiation **~$17K**.\n"
            "• Reduce 19 legal firms to a panel of 3–4 regional firms → **~$18K**.\n"
            "• Renegotiate or terminate opaque advisory retainers (Harmonic Group at $65K, scope unclear) → **$28K–$52K**.\n\n"
            "**Risk:** switching the statutory auditor in Year 1 post-close creates regulatory + re-audit risk that wipes out two years of savings. Renegotiate scope within BDO; do not switch."
        ),
    ]

    tab_id = get_tabs(service)["Top 3 Opportunities"]

    # First clear any prior content in B2:C4
    service.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range="'Top 3 Opportunities'!B2:C4", body={}).execute()

    # Build updateCells request for B2:C4 with rich text
    rows = []
    for i in range(3):
        rows.append({
            "values": [
                {
                    "userEnteredValue": {"stringValue": titles[i]},
                    "userEnteredFormat": {"textFormat": {"bold": True}, "wrapStrategy": "WRAP", "verticalAlignment": "TOP"},
                },
                _build_formatted_cell(explanations[i]),
            ]
        })
    reqs = [{
        "updateCells": {
            "range": {"sheetId": tab_id, "startRowIndex": 1, "endRowIndex": 4, "startColumnIndex": 1, "endColumnIndex": 3},
            "rows": rows,
            "fields": "userEnteredValue,textFormatRuns,userEnteredFormat",
        }
    }, {
        "updateDimensionProperties": {
            "range": {"sheetId": tab_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 260},
            "fields": "pixelSize",
        }
    }, {
        "updateDimensionProperties": {
            "range": {"sheetId": tab_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3},
            "properties": {"pixelSize": 700},
            "fields": "pixelSize",
        }
    }, {
        "updateDimensionProperties": {
            "range": {"sheetId": tab_id, "dimension": "ROWS", "startIndex": 1, "endIndex": 4},
            "properties": {"pixelSize": 280},
            "fields": "pixelSize",
        }
    }]
    service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": reqs}).execute()
    print("Top 3 Opportunities: B2:C4 written with formatted rich text")


def write_methodology_tab(service):
    blob = (
        "APPROACH. Five-step pipeline built and run inside the Claude Code CLI. (1) Dataset review before classifying — identified duplicate vendor entries (Navan booked under 2 legal entities for $416K combined, AWS under 2 entities, HR Solution International under 2 entities) and ~80 opaque Croatian D.O.O. vendors that needed cautious handling. (2) First-pass classification of all 386 vendors with Claude Sonnet 4.6, 15 parallel workers via ThreadPoolExecutor against the Anthropic Messages API, returning structured JSON per vendor (department, 1-line description, suggestion, rationale, confidence). (3) Independent second-pass QA with Claude Opus 4.6 reviewing every row under stricter rules — this corrected 94 of 386 rows (24.4%). (4) Aggregate analysis in Python — duplicate detection by canonical-name grouping, top-20 concentration, category fragmentation, long-tail totals. (5) Manual synthesis of the Top 3 Opportunities and the Executive Memo on top of the classified data, with every savings number shown as baseline x mechanism = number.\n\n"
        "TOOLS. Claude Code CLI (Opus 4.6) for orchestration and synthesis. Anthropic Python SDK for Pass 1 and Pass 2 at scale. Claude Sonnet 4.6 for Pass 1 (fast and cost-efficient for 386 calls). Claude Opus 4.6 for Pass 2 QA (highest reasoning quality for independent review). Google Drive MCP to read the source spreadsheet. Python 3 (csv, ThreadPoolExecutor) for parsing and concurrency. Google Sheets and Docs APIs to publish results back into the submission spreadsheet and the executive memo.\n\n"
        "PROMPTS. Pass 1 system prompt (Sonnet 4.6): 'You are a VP of Operations classifying vendors post-acquisition. The acquired company is a global tech/SaaS business with offices across UK, Croatia, India, Australia, Singapore, and Ireland. Main CRM is Salesforce, main travel platform is Navan, main audit firm is BDO. For each vendor, return strict JSON with: department (from a closed list), a specific 1-line description (never generic like business services), a suggestion (Terminate, Consolidate, Optimize, Protected, or Investigate), a short rationale, and a confidence label. Individual human names default to G&A / Investigate because they are usually miscoded expense reimbursements. Croatian D.O.O. entities read by name cues. Never output a department or suggestion outside the closed list.' Pass 2 QA prompt (Opus 4.6): 'You are the QA reviewer. You receive a vendor with its Pass-1 classification. Review and correct only when needed. Protected is only for statutory spend or one-time M&A deal advisors — never for routine SaaS, never for ongoing audit services. Facilities must not swallow catering, gym, or team events (those are Employee Experience). Descriptions must be specific. Prefer Optimize over Terminate when in doubt. Duplicated entries (Navan x2, AWS x2, HR Solution x2, 4i x2) both get Consolidate with rationale naming the anchor.' Full prompts in scripts/01_classify_vendors.py and scripts/02_qa_classifications.py.\n\n"
        "HOW WE VALIDATED AND QUALITY-CHECKED. (a) Strict JSON + closed-list schema validation on every model response. Pass 1 succeeded on 385 of 386 first tries (1 retry succeeded); Pass 2 succeeded on 386 of 386. (b) Independent-model QA as above — Opus 4.6 corrected 94 of 386 Pass-1 rows. Evidence lives in outputs/03-qa-changes-log.csv (71 department changes, 53 description changes, 44 suggestion changes; some rows had more than one field corrected). (c) Manual spot-check on the top 20 vendors by spend: Salesforce -> Sales/Optimize (correct); Navan -> G&A/Optimize (Pass 1 mislabeled as Protected, QA corrected); BDO -> Professional Services/Optimize (Pass 1 mislabeled as Protected, QA corrected); RSM Corporate Finance -> M&A/Protected (correct, one-time deal fee); SS&C Intralinks -> M&A/Protected (Pass 1 had Optimize, QA corrected — it is a virtual data room used for the deal itself). (d) Deterministic duplicate detection in scripts/03_dataset_stats.py agreed independently with Pass 2's Consolidate flagging on Amazon Web Services ($111K combined), HR Solution International ($88K), TM Forum ($58K), Navan ($416K), and 4i ($84K). Two methods agreeing is a strong signal. (e) Sum verification: classified CSV total equals raw CSV total ($7,839,131 across 386 rows). Confidence distribution: 243 high, 76 medium, 67 low. (f) Every savings number in the Top 3 tab shows baseline x mechanism — e.g. Opportunity 1 = $3.12M x 15-25% = $467K-$779K; Opportunity 2 has per-city math; Opportunity 3 = $130K x 20% + $343K x 5% + $117K x 15% + $65K x ~50%. Full evidence trail in outputs/08-qa-evidence.md in the GitHub repo.\n\n"
        "WHAT THE QA PASS SPECIFICALLY LOOKED FOR. Five common first-pass failure modes were targeted. (1) Over-labeling of Protected on routine SaaS or ongoing services — caught Navan, BDO, Agram Life, Eurofast, Sodexo, Allianz Workers' Comp, all corrected to Optimize. (2) Facilities swallowing unrelated categories — ~15 items moved to Employee Experience (Sodexo India, Konzum Plus, Catering Muring, Omonia, Poles Hanbury Manor, etc.). (3) Generic descriptions like 'software services' or 'consulting firm' — ~50 descriptions rewritten to specific function. (4) Tech-vendor misclassification — Veniture D.O.O. moved from Facilities to Engineering based on Croatian dev-shop naming pattern + spend size. (5) Individual human names — John Smith, Susan Lee, Fabiola Thistlewhaite, etc. defaulted to G&A / Investigate as likely miscoded contractor payouts or expense reimbursements.\n\n"
        "REPRODUCIBILITY AND COST. Full pipeline checked into scripts/: 01_classify_vendors.py, 02_qa_classifications.py, 03_dataset_stats.py, 04_publish_to_sheet.py, 05_populate_memo_doc.py. Total runtime ~2-3 minutes. Total compute cost ~$8 (Sonnet 4.6 ~$0.60, Opus 4.6 ~$7.50, everything else local). Every output file is regenerable from the raw CSV with ANTHROPIC_API_KEY set.\n\n"
        "LIMITATIONS. The dataset has vendor name + 12-month USD spend only. It does not contain contract end dates, auto-renewal flags, business owners, seat counts, or parent-acquirer capability overlap. That is why every savings number is expressed as a range and why the first action in the plan is a contract-data pull, not an immediate cut."
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
