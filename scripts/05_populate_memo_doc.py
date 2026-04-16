#!/usr/bin/env python3
"""
Populates the user-provided Google Doc with the executive memo.
Requires the Doc to be shared with claude-docs@novo-1241.iam.gserviceaccount.com as Editor.
"""

import re
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

CREDS = "/Users/emanuelpiza/.config/gcloud/service-account.json"
DOC_ID = "1pO1J80XPomOT0QCwW3fWmKySLqBKHy53at7Q6tYrYsY"
SCOPES = ["https://www.googleapis.com/auth/documents"]
ROOT = Path(__file__).resolve().parent.parent


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    svc = build("docs", "v1", credentials=creds)

    md = (ROOT / "outputs" / "06-executive-memo.md").read_text()

    # Get existing content length to clear it
    doc = svc.documents().get(documentId=DOC_ID).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1  # last newline position

    reqs = []
    if end_index > 1:
        reqs.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index}}})

    # Build a series of inserts with formatting
    # Approach: insert plain text first, then apply styles by ranges
    plain_lines = []
    styles = []  # (start, end, style) once we know final offsets

    cursor = 1  # Docs positions are 1-indexed; body starts at 1
    lines = md.splitlines()

    # First pass: collect text and record heading/bold ranges
    text_parts = []
    pending_styles = []

    def emit(text, heading=None, bold_ranges=None):
        nonlocal cursor
        start = cursor
        text_parts.append(text)
        cursor += len(text)
        if heading:
            pending_styles.append(("paragraph", start, cursor, heading))
        if bold_ranges:
            for b_start, b_end in bold_ranges:
                pending_styles.append(("text", start + b_start, start + b_end, "bold"))

    def parse_bold(raw):
        """Strip **...** markers and return (plain, bold_ranges)."""
        out = []
        bold_ranges = []
        i = 0
        offset = 0
        while i < len(raw):
            if raw[i:i+2] == "**":
                end = raw.find("**", i+2)
                if end == -1:
                    out.append(raw[i])
                    i += 1
                    offset += 1
                    continue
                inner = raw[i+2:end]
                b_start = offset
                out.append(inner)
                offset += len(inner)
                bold_ranges.append((b_start, offset))
                i = end + 2
            else:
                out.append(raw[i])
                offset += 1
                i += 1
        return "".join(out), bold_ranges

    for ln in lines:
        s = ln.rstrip()
        if s.startswith("# "):
            text, br = parse_bold(s[2:])
            emit(text + "\n", heading="HEADING_1", bold_ranges=br)
        elif s.startswith("## "):
            text, br = parse_bold(s[3:])
            emit(text + "\n", heading="HEADING_2", bold_ranges=br)
        elif s.startswith("### "):
            text, br = parse_bold(s[4:])
            emit(text + "\n", heading="HEADING_3", bold_ranges=br)
        elif s.startswith("- "):
            text, br = parse_bold(s[2:])
            emit("• " + text + "\n", bold_ranges=[(b[0]+2, b[1]+2) for b in br])
        elif s.startswith("---"):
            emit("─────────────\n")
        elif s.startswith("|"):
            # Flatten table rows as pipe-separated lines (simple readable form)
            text, br = parse_bold(s)
            emit(text + "\n", bold_ranges=br)
        elif s == "":
            emit("\n")
        else:
            text, br = parse_bold(s)
            emit(text + "\n", bold_ranges=br)

    full_text = "".join(text_parts)

    reqs.append({"insertText": {"location": {"index": 1}, "text": full_text}})

    # Apply styles (paragraph styles need to be after the insert since offsets are relative)
    for kind, start, end, style in pending_styles:
        if kind == "paragraph":
            reqs.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": style},
                    "fields": "namedStyleType",
                }
            })
        elif kind == "text" and style == "bold":
            reqs.append({
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "textStyle": {"bold": True},
                    "fields": "bold",
                }
            })

    # Tighten margins + set default font to 10pt so it fits one page
    reqs.append({
        "updateDocumentStyle": {
            "documentStyle": {
                "marginTop":    {"magnitude": 36, "unit": "PT"},
                "marginBottom": {"magnitude": 36, "unit": "PT"},
                "marginLeft":   {"magnitude": 54, "unit": "PT"},
                "marginRight":  {"magnitude": 54, "unit": "PT"},
            },
            "fields": "marginTop,marginBottom,marginLeft,marginRight",
        }
    })
    reqs.append({
        "updateTextStyle": {
            "range": {"startIndex": 1, "endIndex": cursor},
            "textStyle": {"fontSize": {"magnitude": 10, "unit": "PT"}},
            "fields": "fontSize",
        }
    })

    svc.documents().batchUpdate(documentId=DOC_ID, body={"requests": reqs}).execute()
    print(f"Populated {DOC_ID}")
    print(f"URL: https://docs.google.com/document/d/{DOC_ID}/edit")


if __name__ == "__main__":
    main()
