"""One-shot script: backfill normalized seat fields into existing data files.

Walks data/{state}/state.json and data/{state}/local/*.json, applies
scrapers.normalize.normalize_member() to every record, and writes the
files back. Idempotent — safe to run repeatedly.

Run before npm publish so the published data has the new fields without
requiring a full re-scrape.

Usage:
    python scripts/backfill_normalized_fields.py
"""

import hashlib
import json
import os
import sys
from datetime import date

# Make scrapers importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.normalize import normalize_member, NormalizationContext


def load_registry():
    with open("registry.json", encoding="utf-8") as f:
        return json.load(f)


def _preset_state_seat_fields(rec: dict, office: str, chamber_label: str):
    """Pre-populate stage-1 seat fields from the existing structured district.

    Tagged seatSource: "source" because the district came from OpenStates'
    structured column originally (preserved across re-runs via record state).
    """
    district = (rec.get("district") or "").strip()
    rec.setdefault("title",
                   f"{chamber_label}, District {district}" if district else chamber_label)
    rec.setdefault("office", office)
    rec.setdefault("seatClass", "numbered" if district else "unknown")
    rec.setdefault("seatLabel", "district" if district else None)
    rec.setdefault("seatId", district if district else None)
    rec.setdefault("seatSource", "source")
    rec.setdefault("leadership", None)
    rec.setdefault("vacant", False)
    rec.setdefault("partisan", True)


def backfill_state(state_code: str):
    path = f"data/{state_code.lower()}/state.json"
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Senate
    ctx_senate = NormalizationContext(level="state", chamber="senate")
    for _district, rec in data.get("senate", {}).items():
        _preset_state_seat_fields(rec, "state-senator", "State Senator")
        normalize_member(rec, ctx_senate)

    # House
    ctx_house = NormalizationContext(level="state", chamber="house")
    for _district, rec in data.get("house", {}).items():
        _preset_state_seat_fields(rec, "state-representative", "State Representative")
        normalize_member(rec, ctx_house)

    # Executive — office inferred from existing title; partisan stays True
    ctx_exec = NormalizationContext(level="state", chamber="executive")
    for rec in data.get("executive", []):
        existing_title = rec.get("title", "").lower()
        if "lieutenant governor" in existing_title or "lt. gov" in existing_title:
            rec.setdefault("office", "lt-governor")
        elif "governor" in existing_title:
            rec.setdefault("office", "governor")
        rec.setdefault("seatClass", "at-large")
        rec.setdefault("seatLabel", None)
        rec.setdefault("seatId", None)
        rec.setdefault("seatSource", "source")
        rec.setdefault("leadership", None)
        rec.setdefault("vacant", False)
        rec.setdefault("partisan", True)
        normalize_member(rec, ctx_exec)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  Backfilled {path}")


def backfill_local(state_code: str, registry: dict):
    local_dir = f"data/{state_code.lower()}/local"
    if not os.path.isdir(local_dir):
        return

    state_data = registry.get("states", {}).get(state_code.upper(), {})
    j_index = {j["id"]: j for j in state_data.get("jurisdictions", [])}
    today = date.today().isoformat()

    for fname in sorted(os.listdir(local_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(local_dir, fname)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        jid = data.get("meta", {}).get("jurisdiction", "")
        jtype = "county" if jid.startswith("county:") else "place" if jid.startswith("place:") else None
        hints = j_index.get(jid, {}).get("councilDefaults")
        ctx = NormalizationContext(
            level="local",
            jurisdiction_type=jtype,
            jurisdiction_id=jid,
            registry_hints=hints,
        )
        for rec in data.get("members", []):
            normalize_member(rec, ctx)

        # Recompute dataHash; if it changed, bump dataLastChanged to today.
        members = data.get("members", [])
        members_json = json.dumps(members, sort_keys=True, ensure_ascii=False)
        new_hash = hashlib.sha256(members_json.encode()).hexdigest()[:16]
        meta = data.setdefault("meta", {})
        prev_hash = meta.get("dataHash", "")
        if prev_hash != new_hash:
            meta["dataHash"] = new_hash
            meta["dataLastChanged"] = today

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Backfilled {path}")


def main():
    registry = load_registry()
    for state_code in sorted(registry.get("states", {}).keys()):
        print(f"Backfilling {state_code}...")
        backfill_state(state_code)
        backfill_local(state_code, registry)
    print("Done.")


if __name__ == "__main__":
    main()
