#!/usr/bin/env python3
"""
Populates the executive memo Google Doc with native headings, bullets, and TABLES.

Parses outputs/06-executive-memo.md and renders it as a real Google Doc with:
  - H1/H2/H3 headings
  - Bullet lists
  - Native tables (insertTable + per-cell text insertion in reverse order)
  - Bold runs inside text
  - Tight margins + small default font to fit one page

Prerequisite: the Doc is shared with claude-docs@novo-1241.iam.gserviceaccount.com as Editor.
"""

from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

CREDS = "/Users/emanuelpiza/.config/gcloud/service-account.json"
DOC_ID = "1pO1J80XPomOT0QCwW3fWmKySLqBKHy53at7Q6tYrYsY"
SCOPES = ["https://www.googleapis.com/auth/documents"]
ROOT = Path(__file__).resolve().parent.parent


def parse_bold(raw):
    out = []
    bold_ranges = []
    i = 0
    offset = 0
    while i < len(raw):
        if raw[i:i+2] == "**":
            end = raw.find("**", i+2)
            if end == -1:
                out.append(raw[i]); i += 1; offset += 1; continue
            inner = raw[i+2:end]
            b_start = offset
            out.append(inner)
            offset += len(inner)
            bold_ranges.append((b_start, offset))
            i = end + 2
        else:
            out.append(raw[i]); offset += 1; i += 1
    return "".join(out), bold_ranges


def parse_markdown(md):
    blocks = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].rstrip()
        if not s:
            i += 1; continue
        if s.startswith("# "):
            text, br = parse_bold(s[2:])
            blocks.append({"type": "heading1", "text": text, "bold": br}); i += 1
        elif s.startswith("## "):
            text, br = parse_bold(s[3:])
            blocks.append({"type": "heading2", "text": text, "bold": br}); i += 1
        elif s.startswith("### "):
            text, br = parse_bold(s[4:])
            blocks.append({"type": "heading3", "text": text, "bold": br}); i += 1
        elif s.startswith("- "):
            items = []
            while i < len(lines) and lines[i].rstrip().startswith("- "):
                text, br = parse_bold(lines[i].rstrip()[2:])
                items.append({"text": text, "bold": br})
                i += 1
            blocks.append({"type": "bullets", "items": items})
        elif s.startswith("|"):
            table_rows = []
            while i < len(lines) and lines[i].rstrip().startswith("|"):
                row = [c.strip() for c in lines[i].rstrip().strip("|").split("|")]
                if not all(set(c.replace(":", "").replace("-", "").replace(" ", "")) == set() for c in row):
                    table_rows.append(row)
                i += 1
            if table_rows:
                blocks.append({"type": "table", "rows": table_rows})
        else:
            text, br = parse_bold(s)
            blocks.append({"type": "para", "text": text, "bold": br}); i += 1
    return blocks


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    svc = build("docs", "v1", credentials=creds)

    md = (ROOT / "outputs" / "06-executive-memo.md").read_text()
    blocks = parse_markdown(md)

    # Clear existing doc
    doc = svc.documents().get(documentId=DOC_ID).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1
    if end_index > 1:
        svc.documents().batchUpdate(documentId=DOC_ID, body={"requests": [
            {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index}}}
        ]}).execute()

    cursor = 1
    pending = []

    def flush():
        nonlocal pending
        if pending:
            svc.documents().batchUpdate(documentId=DOC_ID, body={"requests": pending}).execute()
            pending = []

    def emit_text(text, style=None, bold_ranges=None, bullet=False):
        nonlocal cursor, pending
        start = cursor
        pending.append({"insertText": {"location": {"index": start}, "text": text + "\n"}})
        end = start + len(text) + 1
        if style:
            pending.append({"updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": {"namedStyleType": style},
                "fields": "namedStyleType",
            }})
        if bold_ranges:
            for b_start, b_end in bold_ranges:
                pending.append({"updateTextStyle": {
                    "range": {"startIndex": start + b_start, "endIndex": start + b_end},
                    "textStyle": {"bold": True},
                    "fields": "bold",
                }})
        if bullet:
            pending.append({"createParagraphBullets": {
                "range": {"startIndex": start, "endIndex": end},
                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
            }})
        cursor = end

    for blk in blocks:
        t = blk["type"]
        if t == "heading1":
            emit_text(blk["text"], style="HEADING_1", bold_ranges=blk["bold"])
        elif t == "heading2":
            emit_text(blk["text"], style="HEADING_2", bold_ranges=blk["bold"])
        elif t == "heading3":
            emit_text(blk["text"], style="HEADING_3", bold_ranges=blk["bold"])
        elif t == "para":
            emit_text(blk["text"], bold_ranges=blk["bold"])
        elif t == "bullets":
            for item in blk["items"]:
                emit_text(item["text"], bold_ranges=item["bold"], bullet=True)
        elif t == "table":
            flush()
            rows = blk["rows"]
            n_rows = len(rows)
            n_cols = max(len(r) for r in rows)
            svc.documents().batchUpdate(documentId=DOC_ID, body={"requests": [
                {"insertTable": {"rows": n_rows, "columns": n_cols, "location": {"index": cursor}}}
            ]}).execute()
            doc = svc.documents().get(documentId=DOC_ID).execute()
            cell_starts = []
            last_end = None
            for elem in doc["body"]["content"]:
                if "table" in elem and elem.get("startIndex", -1) >= cursor:
                    for row in elem["table"]["tableRows"]:
                        for cell in row["tableCells"]:
                            cell_starts.append(cell["content"][0]["startIndex"])
                    last_end = elem.get("endIndex")
                    break
            flat = []
            for r in rows:
                padded = r + [""] * (n_cols - len(r))
                for c in padded:
                    flat.append(parse_bold(c))
            cell_reqs = []
            for i in range(len(cell_starts) - 1, -1, -1):
                pos = cell_starts[i]
                plain, br = flat[i]
                if plain:
                    cell_reqs.append({"insertText": {"location": {"index": pos}, "text": plain}})
                    for b_start, b_end in br:
                        cell_reqs.append({"updateTextStyle": {
                            "range": {"startIndex": pos + b_start, "endIndex": pos + b_end},
                            "textStyle": {"bold": True},
                            "fields": "bold",
                        }})
                # Bold entire first row (headers)
                if i < n_cols and plain:
                    cell_reqs.append({"updateTextStyle": {
                        "range": {"startIndex": pos, "endIndex": pos + len(plain)},
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }})
            if cell_reqs:
                svc.documents().batchUpdate(documentId=DOC_ID, body={"requests": cell_reqs}).execute()
            if last_end:
                cursor = last_end

    flush()

    # Margins + default small font
    svc.documents().batchUpdate(documentId=DOC_ID, body={"requests": [
        {"updateDocumentStyle": {
            "documentStyle": {
                "marginTop":    {"magnitude": 36, "unit": "PT"},
                "marginBottom": {"magnitude": 36, "unit": "PT"},
                "marginLeft":   {"magnitude": 54, "unit": "PT"},
                "marginRight":  {"magnitude": 54, "unit": "PT"},
            },
            "fields": "marginTop,marginBottom,marginLeft,marginRight",
        }},
        {"updateTextStyle": {
            "range": {"startIndex": 1, "endIndex": cursor},
            "textStyle": {"fontSize": {"magnitude": 9, "unit": "PT"}},
            "fields": "fontSize",
        }},
    ]}).execute()

    print(f"Populated {DOC_ID}")
    print(f"URL: https://docs.google.com/document/d/{DOC_ID}/edit")


if __name__ == "__main__":
    main()
