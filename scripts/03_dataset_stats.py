#!/usr/bin/env python3
"""
Generates aggregate stats on the QA-classified dataset.
Output: outputs/04-stats.json + outputs/04-stats.md
"""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "outputs" / "03-vendors-classified-qa.csv"
OUT_JSON = ROOT / "outputs" / "04-stats.json"
OUT_MD = ROOT / "outputs" / "04-stats.md"


def parse_spend(s):
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def canon_name(n):
    n = n.lower()
    n = re.sub(r"\b(ltd|llc|inc|gmbh|limited|pty|d\.o\.o\.|uk|usa|australia|llp|corporation|inc\.|corp|company|co\.|s\.r\.o\.|a/s|a\.g\.|ag|pvt|private|ireland|international|operations|services)\b", "", n)
    n = re.sub(r"[^a-z]", "", n)
    return n.strip()


def main():
    rows = list(csv.DictReader(open(INPUT)))

    stats = {}
    stats["total_vendors"] = len(rows)
    stats["total_spend_usd"] = sum(parse_spend(r["Last 12 months Cost (USD)"]) for r in rows)

    # by dept
    dept = defaultdict(lambda: {"count": 0, "spend": 0.0})
    for r in rows:
        d = r["Department"]
        s = parse_spend(r["Last 12 months Cost (USD)"])
        dept[d]["count"] += 1
        dept[d]["spend"] += s
    stats["by_department"] = {k: v for k, v in sorted(dept.items(), key=lambda x: -x[1]["spend"])}

    # by recommendation
    rec = defaultdict(lambda: {"count": 0, "spend": 0.0})
    for r in rows:
        d = r["Recommendation"]
        s = parse_spend(r["Last 12 months Cost (USD)"])
        rec[d]["count"] += 1
        rec[d]["spend"] += s
    stats["by_recommendation"] = {k: v for k, v in sorted(rec.items(), key=lambda x: -x[1]["spend"])}

    # by confidence
    conf = Counter(r["Confidence"] for r in rows)
    stats["by_confidence"] = dict(conf)

    # concentration — top vendors
    top = sorted(rows, key=lambda r: -parse_spend(r["Last 12 months Cost (USD)"]))
    stats["top_20"] = [
        {"name": r["Vendor Name"], "spend": parse_spend(r["Last 12 months Cost (USD)"]), "dept": r["Department"], "rec": r["Recommendation"]}
        for r in top[:20]
    ]
    top_spend = sum(parse_spend(r["Last 12 months Cost (USD)"]) for r in top[:20])
    stats["top_20_spend_share"] = top_spend / stats["total_spend_usd"]

    # long-tail
    tail = [r for r in rows if parse_spend(r["Last 12 months Cost (USD)"]) < 1000]
    stats["long_tail_under_1k"] = {"count": len(tail), "spend": sum(parse_spend(r["Last 12 months Cost (USD)"]) for r in tail)}

    # duplicates — same canonical root
    groups = defaultdict(list)
    for r in rows:
        groups[canon_name(r["Vendor Name"])].append(r)
    dupes = {k: v for k, v in groups.items() if len(v) >= 2 and k}
    stats["duplicate_groups"] = []
    for k, v in sorted(dupes.items(), key=lambda x: -sum(parse_spend(r["Last 12 months Cost (USD)"]) for r in x[1])):
        total = sum(parse_spend(r["Last 12 months Cost (USD)"]) for r in v)
        if total >= 1000 and len(v) >= 2:
            stats["duplicate_groups"].append({
                "root": k,
                "total_spend": total,
                "entries": [{"name": r["Vendor Name"], "spend": parse_spend(r["Last 12 months Cost (USD)"])} for r in v],
            })

    # investigation-flagged spend
    inv = [r for r in rows if r["Recommendation"] == "Investigate"]
    inv.sort(key=lambda r: -parse_spend(r["Last 12 months Cost (USD)"]))
    stats["investigation_top_10"] = [
        {"name": r["Vendor Name"], "spend": parse_spend(r["Last 12 months Cost (USD)"]), "dept": r["Department"], "desc": r["1-line Description"]}
        for r in inv[:10]
    ]
    stats["investigation_total_spend"] = sum(parse_spend(r["Last 12 months Cost (USD)"]) for r in inv)

    # consolidate-flagged
    cons = [r for r in rows if r["Recommendation"] == "Consolidate"]
    stats["consolidate_total_spend"] = sum(parse_spend(r["Last 12 months Cost (USD)"]) for r in cons)
    stats["consolidate_count"] = len(cons)

    # category breakdowns (audit/legal/recruitment/RE/insurance)
    def match_any(r, patterns):
        n = (r["Vendor Name"] + " " + r["1-line Description"]).lower()
        return any(p in n for p in patterns)

    categories = {
        "audit_tax_accounting": ["audit", "tax", "accountan", "chartered"],
        "legal": ["law", "lawyer", "solicit", "legal", "notary"],
        "real_estate_coworking": ["office", "coworking", "space", "properties", "lease", "tower", "wework", "cbre", "jones lang"],
        "insurance": ["insurance", "insur", "health", "life", "worker"],
        "recruitment": ["recruit", "talent", "staffing", "headhunt", "mason frank", "cedar recruit"],
        "sales_tools": ["salesforce", "hubspot", "outreach", "cognism", "lusha", "semrush", "uberflip", "6sense", "ariba", "yoxel"],
    }
    stats["category_fragmentation"] = {}
    for cat, pats in categories.items():
        vs = [r for r in rows if match_any(r, pats)]
        stats["category_fragmentation"][cat] = {
            "count": len(vs),
            "spend": sum(parse_spend(r["Last 12 months Cost (USD)"]) for r in vs),
            "vendors": [{"name": r["Vendor Name"], "spend": parse_spend(r["Last 12 months Cost (USD)"])} for r in sorted(vs, key=lambda x: -parse_spend(x["Last 12 months Cost (USD)"]))],
        }

    with open(OUT_JSON, "w") as f:
        json.dump(stats, f, indent=2)

    # markdown report
    lines = [
        "# Dataset Stats (post-QA classifications)",
        "",
        f"- Total vendors: **{stats['total_vendors']}**",
        f"- Total spend (T12M): **${stats['total_spend_usd']:,.0f}**",
        f"- Top-20 vendors = **{stats['top_20_spend_share']:.1%}** of spend",
        f"- Long-tail (<$1K each): **{stats['long_tail_under_1k']['count']}** vendors, **${stats['long_tail_under_1k']['spend']:,.0f}** (AP-sprawl only)",
        f"- Spend flagged for **Investigate**: **${stats['investigation_total_spend']:,.0f}** (cannot commit to savings until mapped)",
        f"- Spend flagged for **Consolidate**: **${stats['consolidate_total_spend']:,.0f}** across **{stats['consolidate_count']}** vendors",
        "",
        "## By Department",
        "",
        "| Department | Vendors | Spend |",
        "|---|---:|---:|",
    ]
    for k, v in stats["by_department"].items():
        lines.append(f"| {k} | {v['count']} | ${v['spend']:,.0f} |")
    lines += ["", "## By Recommendation", "", "| Recommendation | Vendors | Spend |", "|---|---:|---:|"]
    for k, v in stats["by_recommendation"].items():
        lines.append(f"| {k} | {v['count']} | ${v['spend']:,.0f} |")
    lines += ["", "## Top 20 Vendors", "", "| # | Vendor | Spend | Department | Recommendation |", "|---|---|---:|---|---|"]
    for i, v in enumerate(stats["top_20"], 1):
        lines.append(f"| {i} | {v['name']} | ${v['spend']:,.0f} | {v['dept']} | {v['rec']} |")
    lines += ["", "## Duplicate Vendor Groups (combined ≥ $1K)", "", "| Root key | # entries | Combined spend | Entries |", "|---|---:|---:|---|"]
    for g in stats["duplicate_groups"]:
        ents = "; ".join(f"{e['name']} (${e['spend']:,.0f})" for e in g["entries"])
        lines.append(f"| {g['root']} | {len(g['entries'])} | ${g['total_spend']:,.0f} | {ents} |")
    lines += ["", "## Category Fragmentation"]
    for cat, data in stats["category_fragmentation"].items():
        lines.append(f"\n### {cat} — {data['count']} vendors, ${data['spend']:,.0f}")
        lines.append("")
        for v in data["vendors"][:15]:
            lines.append(f"- {v['name']} — ${v['spend']:,.0f}")
    OUT_MD.write_text("\n".join(lines))
    print(f"Wrote {OUT_JSON} and {OUT_MD}")


if __name__ == "__main__":
    main()
