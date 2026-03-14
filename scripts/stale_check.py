"""
Check for stale local council data.

Reads all data/{state}/local/*.json files and flags any where
meta.dataLastChanged is older than the threshold (default 90 days).

Usage:
    python scripts/stale_check.py [--threshold 90]

Exits 0 always (informational only). Prints stale jurisdictions to stdout.
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")


def find_stale_files(data_dir, threshold_days=90):
    """Find local council data files where the last change is older than threshold.

    Scans data_dir/{state}/local/*.json for files where
    meta.dataLastChanged (or meta.lastUpdated fallback) is older than
    threshold_days from today.

    Returns a list of dicts with jurisdiction, label, dataLastChanged,
    and daysSinceChange keys.
    """
    cutoff = date.today() - timedelta(days=threshold_days)
    stale = []

    if not os.path.isdir(data_dir):
        return stale

    for state_code in sorted(os.listdir(data_dir)):
        local_dir = os.path.join(data_dir, state_code, "local")
        if not os.path.isdir(local_dir):
            continue

        for filename in sorted(os.listdir(local_dir)):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(local_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue

            meta = data.get("meta", {})
            last_changed = meta.get("dataLastChanged", meta.get("lastUpdated", ""))
            if not last_changed:
                continue

            try:
                last_date = date.fromisoformat(last_changed)
            except ValueError:
                continue

            if last_date < cutoff:
                days_stale = (date.today() - last_date).days
                stale.append({
                    "jurisdiction": meta.get("jurisdiction", filename),
                    "label": meta.get("label", ""),
                    "dataLastChanged": last_changed,
                    "daysSinceChange": days_stale,
                })

    return stale


def main():
    parser = argparse.ArgumentParser(description="Check for stale council data")
    parser.add_argument(
        "--threshold", type=int, default=90,
        help="Days since last data change to consider stale (default: 90)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON instead of plain text",
    )
    args = parser.parse_args()

    stale = find_stale_files(DATA_DIR, threshold_days=args.threshold)

    if args.json:
        json.dump(stale, sys.stdout, indent=2)
    elif stale:
        print(f"Found {len(stale)} stale jurisdiction(s) (>{args.threshold} days unchanged):\n")
        for s in stale:
            print(f"  {s['label']} ({s['jurisdiction']}): last changed {s['dataLastChanged']} ({s['daysSinceChange']} days ago)")
    else:
        print(f"No stale data found (threshold: {args.threshold} days)")


if __name__ == "__main__":
    main()
