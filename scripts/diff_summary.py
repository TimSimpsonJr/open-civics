"""
Generate a human-readable summary of data changes for PR bodies.

Reads git diff on data/ and summarizes member changes per jurisdiction.

Usage:
    python scripts/diff_summary.py [--report scrape-report.json]

Prints markdown summary to stdout.
"""

import json
import os
import subprocess
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_changed_files():
    """Get list of changed files in data/ from git."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--cached", "data/"],
        capture_output=True, text=True, cwd=ROOT_DIR,
    )
    if result.returncode != 0:
        # Fall back to unstaged diff
        result = subprocess.run(
            ["git", "diff", "--name-only", "data/"],
            capture_output=True, text=True, cwd=ROOT_DIR,
        )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_file_diff_stats(filepath):
    """Get insertions/deletions for a specific file."""
    result = subprocess.run(
        ["git", "diff", "--numstat", "--cached", filepath],
        capture_output=True, text=True, cwd=ROOT_DIR,
    )
    if result.returncode != 0 or not result.stdout.strip():
        result = subprocess.run(
            ["git", "diff", "--numstat", filepath],
            capture_output=True, text=True, cwd=ROOT_DIR,
        )
    if result.stdout.strip():
        parts = result.stdout.strip().split("\t")
        if len(parts) >= 2:
            return int(parts[0] or 0), int(parts[1] or 0)
    return 0, 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Summarize data changes")
    parser.add_argument("--report", help="Path to scrape report JSON")
    args = parser.parse_args()

    changed_files = get_changed_files()
    if not changed_files:
        print("No data changes detected.")
        return

    local_changes = []
    state_changes = []
    boundary_changes = []

    for f in changed_files:
        if "/local/" in f:
            local_changes.append(f)
        elif f.endswith("state.json"):
            state_changes.append(f)
        elif "/boundaries/" in f:
            boundary_changes.append(f)

    lines = ["## Data Update Summary\n"]

    if state_changes:
        lines.append(f"**State legislators:** {len(state_changes)} file(s) updated")
    if local_changes:
        lines.append(f"**Local councils:** {len(local_changes)} jurisdiction(s) changed")
        for f in local_changes[:10]:
            name = os.path.basename(f).replace(".json", "").replace("-", " ").title()
            added, removed = get_file_diff_stats(f)
            lines.append(f"  - {name} (+{added}/-{removed} lines)")
        if len(local_changes) > 10:
            lines.append(f"  - ... and {len(local_changes) - 10} more")
    if boundary_changes:
        names = [os.path.basename(f).replace(".json", "") for f in boundary_changes]
        lines.append(f"**Boundaries:** {len(boundary_changes)} file(s) changed ({', '.join(names[:5])})")

    unchanged = 96 - len(local_changes)  # TODO: derive from registry
    if unchanged > 0:
        lines.append(f"\n**Unchanged:** {unchanged} jurisdiction(s)")

    # Include scrape report summary if provided
    if args.report and os.path.exists(args.report):
        try:
            with open(args.report, "r") as f:
                report = json.load(f)
            summary = report.get("summary", {})
            failed = summary.get("failed", 0)
            warned = summary.get("warned", 0)
            if failed > 0 or warned > 0:
                lines.append(f"\n### Scrape Issues")
                if failed:
                    lines.append(f"**{failed} adapter(s) failed:**")
                    for jid, r in report.get("adapters", {}).items():
                        if r.get("status") == "error":
                            lines.append(f"  - {jid}: {r.get('error', 'unknown')}")
                if warned:
                    lines.append(f"**{warned} adapter(s) with warnings:**")
                    for jid, r in report.get("adapters", {}).items():
                        if r.get("status") == "warned":
                            lines.append(f"  - {jid}: {'; '.join(r.get('warnings', []))}")
        except (json.JSONDecodeError, IOError):
            pass

    print("\n".join(lines))


if __name__ == "__main__":
    main()
