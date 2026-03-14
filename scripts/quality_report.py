"""
Data quality report for call-your-rep jurisdiction files.

Scans all data/{state}/local/*.json and data/{state}/state.json files
and produces a coverage dashboard showing email, phone, executive,
and contact info availability per jurisdiction.

Usage:
    python scripts/quality_report.py
    python scripts/quality_report.py --json
    python scripts/quality_report.py --summary-only
    python scripts/quality_report.py --state SC
"""

import argparse
import json
import os
import re
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")

PLACE_EXECUTIVE_TITLES = {"mayor"}
COUNTY_EXECUTIVE_TITLES = {"chairman", "chairwoman", "chair", "county supervisor"}


VICE_PREFIXES = {"vice", "vice-", "deputy"}


def _has_title_match(title_lower, targets):
    """Check if a title contains a target role without a vice/deputy prefix."""
    for target in targets:
        # Find target as a whole word in the title
        pattern = r'\b' + re.escape(target) + r'\b'
        match = re.search(pattern, title_lower)
        if not match:
            continue
        # Check that the word before it isn't "vice" or "deputy"
        before = title_lower[:match.start()].strip().rstrip("-").split()
        if before and before[-1] in VICE_PREFIXES:
            continue
        return True
    return False


def check_executive(members, jurisdiction_type):
    """Find the executive title among members based on jurisdiction type."""
    targets = (
        PLACE_EXECUTIVE_TITLES if jurisdiction_type == "place"
        else COUNTY_EXECUTIVE_TITLES
    )
    for member in members:
        title = member.get("title", "")
        title_lower = title.lower()
        if _has_title_match(title_lower, targets):
            return title.split(",")[0].strip()
    return None


def check_contact(meta):
    """Check if meta.contact has phone or email."""
    contact = meta.get("contact", {})
    if not contact or not isinstance(contact, dict):
        return None
    phone = contact.get("phone", "")
    email = contact.get("email", "")
    label = contact.get("label", "")
    parts = []
    if label:
        parts.append(label)
    if phone:
        parts.append(phone)
    if email:
        parts.append(email)
    return " ".join(parts) if parts else None


def analyze_local_file(filepath):
    """Analyze a single local jurisdiction file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    meta = data.get("meta", {})
    members = data.get("members", [])
    jurisdiction = meta.get("jurisdiction", "")

    # Determine jurisdiction type from the jurisdiction field or filename
    if jurisdiction.startswith("place:"):
        jtype = "place"
    elif jurisdiction.startswith("county:"):
        jtype = "county"
    else:
        basename = os.path.basename(filepath)
        if basename.startswith("place-"):
            jtype = "place"
        elif basename.startswith("county-"):
            jtype = "county"
        else:
            jtype = "unknown"

    has_email = any(m.get("email", "").strip() for m in members)
    has_phone = any(m.get("phone", "").strip() for m in members)
    executive = check_executive(members, jtype)
    contact = check_contact(meta)

    # Use filename stem as display name if no jurisdiction in meta
    name = jurisdiction.replace(":", "-") if jurisdiction else (
        os.path.basename(filepath).replace(".json", "")
    )

    return {
        "name": name,
        "label": meta.get("label", ""),
        "state": meta.get("state", ""),
        "members": len(members),
        "has_email": has_email,
        "has_phone": has_phone,
        "executive": executive,
        "contact": contact,
    }


def analyze_state_file(filepath):
    """Analyze a state.json file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    state_code = data.get("meta", {}).get("state", "")
    has_executive = bool(data.get("executive"))

    # Count legislators across chambers (may be list or dict keyed by district)
    total = 0
    for key in ("senate", "house", "members"):
        entries = data.get(key)
        if isinstance(entries, list):
            total += len(entries)
        elif isinstance(entries, dict):
            total += len(entries)

    return {
        "state": state_code,
        "legislators": total,
        "has_executive": has_executive,
    }


def run_report(state_filter=None):
    """Scan all data files and return analysis results."""
    local_results = []
    state_results = []

    for state_code in sorted(os.listdir(DATA_DIR)):
        state_dir = os.path.join(DATA_DIR, state_code)
        if not os.path.isdir(state_dir):
            continue
        if state_filter and state_code.upper() != state_filter.upper():
            continue

        # State file
        state_file = os.path.join(state_dir, "state.json")
        if os.path.isfile(state_file):
            result = analyze_state_file(state_file)
            if result:
                state_results.append(result)

        # Local files
        local_dir = os.path.join(state_dir, "local")
        if not os.path.isdir(local_dir):
            continue

        for filename in sorted(os.listdir(local_dir)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(local_dir, filename)
            result = analyze_local_file(filepath)
            if result:
                local_results.append(result)

    return local_results, state_results


def format_markdown(local_results, state_results):
    """Format results as a markdown table."""
    lines = ["## Data Quality Report\n"]

    # State-level summary
    for sr in state_results:
        exec_status = "yes" if sr["has_executive"] else "no"
        lines.append(
            f"**{sr['state']} state.json:** {sr['legislators']} legislators, "
            f"executive: {exec_status}"
        )
    if state_results:
        lines.append("")

    # Local jurisdiction table
    lines.append(
        "| Jurisdiction | Members | Email | Phone | Executive | Contact |"
    )
    lines.append("|---|---|---|---|---|---|")

    for r in local_results:
        email = "yes" if r["has_email"] else "no"
        phone = "yes" if r["has_phone"] else "no"
        executive = r["executive"] if r["executive"] else "-"
        contact = r["contact"] if r["contact"] else "-"
        members = str(r["members"]) if r["members"] > 0 else "**0**"
        lines.append(
            f"| {r['name']} | {members} | {email} | {phone} "
            f"| {executive} | {contact} |"
        )

    # Summary line
    total = len(local_results)
    with_email = sum(1 for r in local_results if r["has_email"])
    with_phone = sum(1 for r in local_results if r["has_phone"])
    with_exec = sum(1 for r in local_results if r["executive"])
    lines.append(
        f"\n**Coverage:** {total} jurisdictions, {with_email} with email, "
        f"{with_phone} with phone, {with_exec} with executive"
    )

    return "\n".join(lines)


def format_summary(local_results, state_results):
    """Format just the summary totals."""
    total = len(local_results)
    with_email = sum(1 for r in local_results if r["has_email"])
    with_phone = sum(1 for r in local_results if r["has_phone"])
    with_exec = sum(1 for r in local_results if r["executive"])
    with_contact = sum(1 for r in local_results if r["contact"])
    empty = sum(1 for r in local_results if r["members"] == 0)

    parts = [
        f"{total} jurisdictions",
        f"{with_email} with email ({100 * with_email // total}%)" if total else "0 with email",
        f"{with_phone} with phone ({100 * with_phone // total}%)" if total else "0 with phone",
        f"{with_exec} with executive ({100 * with_exec // total}%)" if total else "0 with executive",
        f"{with_contact} with contact info ({100 * with_contact // total}%)" if total else "0 with contact",
    ]
    if empty:
        parts.append(f"{empty} with 0 members")

    for sr in state_results:
        exec_status = "yes" if sr["has_executive"] else "no"
        parts.append(f"{sr['state']} state: {sr['legislators']} legislators (executive: {exec_status})")

    return "Coverage: " + ", ".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Data quality report")
    parser.add_argument(
        "--json", action="store_true",
        help="Output as machine-readable JSON",
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Print only the totals line",
    )
    parser.add_argument(
        "--state", type=str, default=None,
        help="Filter to a single state (e.g., SC)",
    )
    args = parser.parse_args()

    local_results, state_results = run_report(state_filter=args.state)

    if args.json:
        output = {
            "local": local_results,
            "state": state_results,
            "summary": {
                "total_jurisdictions": len(local_results),
                "with_email": sum(1 for r in local_results if r["has_email"]),
                "with_phone": sum(1 for r in local_results if r["has_phone"]),
                "with_executive": sum(1 for r in local_results if r["executive"]),
                "with_contact": sum(1 for r in local_results if r["contact"]),
                "empty_members": sum(1 for r in local_results if r["members"] == 0),
            },
        }
        json.dump(output, sys.stdout, indent=2)
        print()
    elif args.summary_only:
        print(format_summary(local_results, state_results))
    else:
        print(format_markdown(local_results, state_results))


if __name__ == "__main__":
    main()
