"""Regenerate a local-council data file from a saved HTML snapshot.

Usage:
  python scripts/refresh_from_snapshot.py <jurisdiction_id> <snapshot_path>

Used as a fallback when live scraping is blocked (Cloudflare, Akamai, etc.)
but a saved snapshot exists in tests/fixtures/snapshots/.

The script loads the adapter for the given jurisdiction from registry.json,
runs parse() + normalize() + validate() against the snapshot HTML, and
writes the result to data/<state>/local/<jurisdiction>.json with the same
meta block that scrapers.__main__ would produce (including a SHA256
dataHash and dataLastChanged that preserves the prior value when the
content is unchanged).

See also `scripts/refresh_snapshots.py`, which goes the OTHER direction:
fetches live HTML from URLs and refreshes the saved snapshot files. This
script is the inverse: replays a saved snapshot into a data file.
"""
import hashlib
import json
import os
import sys
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scrapers.__main__ import ADAPTERS, load_registry  # noqa: E402


def main(jid: str, snapshot_path: str) -> None:
    registry = load_registry()
    entry = None
    state_code = None
    for code, state in registry["states"].items():
        for j in state.get("jurisdictions", []):
            if j["id"] == jid:
                entry = j
                state_code = code
                break
        if entry is not None:
            break

    if entry is None:
        sys.exit(f"jurisdiction {jid!r} not found in registry")

    adapter_name = entry["adapter"]
    if adapter_name not in ADAPTERS:
        sys.exit(f"adapter {adapter_name!r} not registered in scrapers/__main__.py")

    adapter_cls = ADAPTERS[adapter_name]
    adapter = adapter_cls(entry)

    with open(snapshot_path, "r", encoding="utf-8") as f:
        html = f.read()

    adapter._html = html  # Mirror BaseAdapter.scrape() so get_contact() can read it
    raw = adapter.parse(html)
    members = adapter.normalize(raw)
    adapter.validate(members)

    members_json = json.dumps(members, sort_keys=True, ensure_ascii=False)
    data_hash = hashlib.sha256(members_json.encode()).hexdigest()[:16]

    out = os.path.join(
        PROJECT_ROOT, "data", state_code.lower(), "local",
        f"{jid.replace(':', '-')}.json",
    )

    today = date.today().isoformat()
    data_last_changed = today
    if os.path.exists(out):
        try:
            with open(out, "r", encoding="utf-8") as prev:
                prev_data = json.load(prev)
            prev_hash = prev_data.get("meta", {}).get("dataHash", "")
            if prev_hash == data_hash:
                data_last_changed = prev_data.get("meta", {}).get(
                    "dataLastChanged", today
                )
        except (json.JSONDecodeError, IOError):
            pass

    data = {
        "meta": {
            "state": state_code,
            "level": "local",
            "jurisdiction": jid,
            "label": entry["name"],
            "lastUpdated": today,
            "adapter": adapter_name,
            "dataHash": data_hash,
            "dataLastChanged": data_last_changed,
        },
        "members": members,
    }

    contact = adapter.get_contact()
    if contact:
        data["meta"]["contact"] = contact

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {out}")


# Positional args for now; Task 4 (docs/plans/2026-05-16-followup-districted-scraper-bugs-plan.md)
# refactors to argparse when it adds a --civicplus-supplement flag.
if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python scripts/refresh_from_snapshot.py "
                 "<jurisdiction_id> <snapshot_path>")
    main(sys.argv[1], sys.argv[2])
