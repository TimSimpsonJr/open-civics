"""
Validate all JSON data files before deployment.

Checks that data files conform to expected schemas and contain sane values.
Run after scraping or editing data:

    python validate.py

Exit code 0 = all checks pass, 1 = validation errors found.
"""

import json
import os
import re
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")

errors = []
warnings = []


def error(file, msg):
    errors.append(f"  ERROR [{file}]: {msg}")


def warn(file, msg):
    warnings.append(f"  WARN  [{file}]: {msg}")


def load_json(path, label=None):
    label = label or path
    if not os.path.exists(path):
        error(label, "File not found")
        return None
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            error(label, f"Invalid JSON: {e}")
            return None


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\(\d{3}\) \d{3}-\d{4}$")

# US bounding box (continental)
US_BOUNDS = {"lat_min": 24.0, "lat_max": 50.0, "lng_min": -125.0, "lng_max": -66.0}

# Per-state expected counts for sanity checks
STATE_EXPECTED_COUNTS = {
    "SC": {"senate": 46, "house": 124},
}


def validate_state_json(data, state_code, filepath):
    """Validate a state.json file with meta block + senate/house."""
    label = filepath

    if not isinstance(data, dict):
        error(label, "Root must be an object")
        return

    # Validate meta block
    meta = data.get("meta")
    if not isinstance(meta, dict):
        error(label, "Missing 'meta' block")
    else:
        for field in ("state", "level", "lastUpdated", "source"):
            if not meta.get(field):
                error(label, f"meta: missing '{field}'")
        if meta.get("state") and meta["state"] != state_code:
            error(label, f"meta.state is '{meta['state']}', expected '{state_code}'")

    # Validate chambers
    for chamber in ("senate", "house"):
        if chamber not in data:
            error(label, f"Missing '{chamber}' key")
            continue

        members = data[chamber]
        if not isinstance(members, dict):
            error(label, f"'{chamber}' must be an object keyed by district number")
            continue

        # Sanity check: drop detection
        expected_counts = STATE_EXPECTED_COUNTS.get(state_code, {})
        expected = expected_counts.get(chamber)
        if expected and len(members) < expected * 0.5:
            error(label, f"'{chamber}' has {len(members)} members, expected ~{expected} (>50% drop)")

        for district, member in members.items():
            prefix = f"{chamber}[{district}]"

            if not district.isdigit():
                error(label, f"{prefix}: district key must be numeric, got '{district}'")

            if not member.get("name"):
                error(label, f"{prefix}: missing 'name'")

            if not member.get("district"):
                warn(label, f"{prefix}: missing 'district' field")

            email = member.get("email", "")
            if email and not EMAIL_RE.match(email):
                warn(label, f"{prefix}: invalid email format '{email}'")

            phone = member.get("phone", "")
            if phone and not PHONE_RE.match(phone):
                warn(label, f"{prefix}: unexpected phone format '{phone}'")

            party = member.get("party", "")
            if party and party not in ("R", "D", "I"):
                warn(label, f"{prefix}: unexpected party '{party}'")

    # Validate executive (optional)
    executive = data.get("executive")
    if executive is not None:
        if not isinstance(executive, list):
            error(label, "'executive' must be a list")
        else:
            for i, member in enumerate(executive):
                prefix = f"executive[{i}]"
                if not member.get("name"):
                    error(label, f"{prefix}: missing 'name'")
                if not member.get("title"):
                    error(label, f"{prefix}: missing 'title'")
                email = member.get("email", "")
                if email and not EMAIL_RE.match(email):
                    warn(label, f"{prefix}: invalid email format '{email}'")
                phone = member.get("phone", "")
                if phone and not PHONE_RE.match(phone):
                    warn(label, f"{prefix}: unexpected phone format '{phone}'")


def validate_federal_json(data, state_code, filepath):
    """Validate a federal.json file with meta block + senate/house."""
    label = filepath

    if not isinstance(data, dict):
        error(label, "Root must be an object")
        return

    # Validate meta block
    meta = data.get("meta")
    if not isinstance(meta, dict):
        error(label, "Missing 'meta' block")
    else:
        for field in ("state", "level", "lastUpdated", "source"):
            if not meta.get(field):
                error(label, f"meta: missing '{field}'")
        if meta.get("state") and meta["state"] != state_code:
            error(label, f"meta.state is '{meta['state']}', expected '{state_code}'")
        if meta.get("level") != "federal":
            error(label, f"meta.level is '{meta['level']}', expected 'federal'")

    # Validate senate (expect exactly 2 senators per state)
    senate = data.get("senate")
    if not isinstance(senate, dict):
        error(label, "Missing or invalid 'senate' key")
    else:
        if len(senate) < 1:
            warn(label, "Senate has 0 members")
        elif len(senate) > 2:
            warn(label, f"Senate has {len(senate)} members, expected at most 2")
        for key, member in senate.items():
            prefix = f"senate[{key}]"
            if not member.get("name"):
                error(label, f"{prefix}: missing 'name'")
            party = member.get("party", "")
            if party and party not in ("R", "D", "I"):
                warn(label, f"{prefix}: unexpected party '{party}'")

    # Validate house
    house = data.get("house")
    if not isinstance(house, dict):
        error(label, "Missing or invalid 'house' key")
    else:
        if len(house) < 1:
            warn(label, "House has 0 members")
        for key, member in house.items():
            prefix = f"house[{key}]"
            if not member.get("name"):
                error(label, f"{prefix}: missing 'name'")
            party = member.get("party", "")
            if party and party not in ("R", "D", "I"):
                warn(label, f"{prefix}: unexpected party '{party}'")


def validate_local_file(data, filepath):
    """Validate a single local council JSON file with meta + members."""
    label = filepath

    if not isinstance(data, dict):
        error(label, "Root must be an object")
        return

    # Validate meta block
    meta = data.get("meta")
    if not isinstance(meta, dict):
        error(label, "Missing 'meta' block")
    else:
        for field in ("state", "level", "jurisdiction", "label", "lastUpdated", "adapter"):
            if not meta.get(field):
                error(label, f"meta: missing '{field}'")

        jurisdiction = meta.get("jurisdiction", "")
        if jurisdiction and not re.match(r"^(county|place):.+$", jurisdiction):
            warn(label, f"Unexpected jurisdiction format: '{jurisdiction}'")

        contact = meta.get("contact")
        if contact is not None:
            if not isinstance(contact, dict):
                error(label, "meta.contact must be an object")
            else:
                phone = contact.get("phone", "")
                if phone and not PHONE_RE.match(phone):
                    warn(label, f"meta.contact.phone: unexpected format '{phone}'")
                email = contact.get("email", "")
                if email and not EMAIL_RE.match(email):
                    warn(label, f"meta.contact.email: invalid format '{email}'")

    # Validate members
    members = data.get("members")
    if not isinstance(members, list):
        error(label, "'members' must be a list")
        return

    if len(members) == 0:
        warn(label, "Council has 0 members")

    for i, member in enumerate(members):
        prefix = f"members[{i}]"

        if not member.get("name"):
            error(label, f"{prefix}: missing 'name'")

        if not member.get("title"):
            warn(label, f"{prefix}: missing 'title'")

        title = member.get("title", "").lower()
        admin_keywords = (
            "clerk", "administrator", "manager", "secretary",
            "treasurer", "attorney", "director", "assistant",
            "staff", "deputy", "coordinator", "supervisor",
        )
        if any(kw in title for kw in admin_keywords):
            warn(label, f"{prefix}: title '{member['title']}' looks like admin staff, not elected official")

        email = member.get("email", "")
        if email and not EMAIL_RE.match(email):
            warn(label, f"{prefix}: invalid email format '{email}'")

        phone = member.get("phone", "")
        if phone and not PHONE_RE.match(phone):
            warn(label, f"{prefix}: unexpected phone format '{phone}'")


def validate_registry(data):
    """Validate registry.json structure and content."""
    label = "registry.json"

    if not isinstance(data, dict):
        error(label, "Root must be an object")
        return

    states = data.get("states")
    if not isinstance(states, dict):
        error(label, "Missing 'states' object")
        return

    for state_code, state_data in states.items():
        prefix = f"states.{state_code}"

        # Validate state boundaries
        boundaries = state_data.get("stateBoundaries", [])
        if not isinstance(boundaries, list) or len(boundaries) == 0:
            error(label, f"{prefix}: missing or empty 'stateBoundaries'")

        for i, entry in enumerate(boundaries):
            bp = f"{prefix}.stateBoundaries[{i}]"
            for field in ("id", "name", "source", "url", "districtField", "file"):
                if not entry.get(field):
                    error(label, f"{bp}: missing '{field}'")

            source = entry.get("source", "")
            if source and source not in ("tiger", "arcgis", "scrfa"):
                error(label, f"{bp}: invalid source '{source}'")

        # Validate jurisdictions
        jurisdictions = state_data.get("jurisdictions", [])
        if not isinstance(jurisdictions, list):
            error(label, f"{prefix}: 'jurisdictions' must be a list")
        else:
            for i, j in enumerate(jurisdictions):
                jp = f"{prefix}.jurisdictions[{i}]"

                for field in ("id", "name", "type", "county"):
                    if not j.get(field):
                        error(label, f"{jp}: missing '{field}'")

                jtype = j.get("type", "")
                if jtype and jtype not in ("county", "place"):
                    warn(label, f"{jp}: unexpected type '{jtype}'")

                boundary = j.get("boundary")
                if boundary:
                    for field in ("source", "url", "file"):
                        if not boundary.get(field):
                            error(label, f"{jp}.boundary: missing '{field}'")
                    # districtField required unless config block present (e.g. SCRFA sources)
                    if not boundary.get("districtField") and not boundary.get("config"):
                        error(label, f"{jp}.boundary: missing 'districtField' (or 'config')")


def validate_boundary_files(registry, state_code, state_dir):
    """Validate that referenced boundary GeoJSON files exist and are valid."""
    boundaries_dir = os.path.join(state_dir, "boundaries")
    if not os.path.isdir(boundaries_dir):
        warn(f"data/{state_code}/boundaries/", "Boundaries directory not found, skipping")
        return

    state_data = registry.get("states", {}).get(state_code, {})

    # Collect all referenced boundary files
    files = set()
    for entry in state_data.get("stateBoundaries", []):
        if entry.get("file"):
            files.add(entry["file"])
    for j in state_data.get("jurisdictions", []):
        boundary = j.get("boundary")
        if boundary and boundary.get("file"):
            files.add(boundary["file"])

    for filename in sorted(files):
        filepath = os.path.join(boundaries_dir, filename)
        rel_path = f"data/{state_code}/boundaries/{filename}"

        if not os.path.exists(filepath):
            warn(rel_path, "Referenced boundary file does not exist")
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                geojson = json.load(f)
        except json.JSONDecodeError as e:
            error(rel_path, f"Invalid JSON: {e}")
            continue

        if geojson.get("type") != "FeatureCollection":
            error(rel_path, "Must be a GeoJSON FeatureCollection")
            continue

        features = geojson.get("features", [])
        if len(features) == 0:
            error(rel_path, "FeatureCollection has 0 features")
            continue

        for fi, feature in enumerate(features):
            if feature.get("type") != "Feature":
                error(rel_path, f"features[{fi}]: type must be 'Feature'")
                continue

            props = feature.get("properties", {})
            if "district" not in props:
                error(rel_path, f"features[{fi}]: missing properties.district")

            geom = feature.get("geometry", {})
            geom_type = geom.get("type", "")
            if geom_type not in ("Polygon", "MultiPolygon"):
                error(rel_path, f"features[{fi}]: unexpected geometry type '{geom_type}'")

            # Check coordinates are within US bounding box
            coords = geom.get("coordinates", [])
            if coords:
                first_coord = coords
                while isinstance(first_coord, list) and len(first_coord) > 0 and isinstance(first_coord[0], list):
                    first_coord = first_coord[0]
                if isinstance(first_coord, list) and len(first_coord) >= 2:
                    lng, lat = first_coord[0], first_coord[1]
                    b = US_BOUNDS
                    if not (b["lng_min"] <= lng <= b["lng_max"] and b["lat_min"] <= lat <= b["lat_max"]):
                        warn(rel_path, f"features[{fi}]: coordinates ({lng}, {lat}) outside US bounds")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Validating data files...\n")

    # Load registry
    registry_path = os.path.join(ROOT_DIR, "registry.json")
    registry = load_json(registry_path, "registry.json")
    if registry is not None:
        validate_registry(registry)
        print("  Checked registry.json")

    # Discover state directories
    if not os.path.isdir(DATA_DIR):
        error("data/", "Data directory not found")
    else:
        for state_code in sorted(os.listdir(DATA_DIR)):
            state_dir = os.path.join(DATA_DIR, state_code)
            if not os.path.isdir(state_dir):
                continue

            state_upper = state_code.upper()

            # Validate state.json
            state_json_path = os.path.join(state_dir, "state.json")
            state_label = f"data/{state_code}/state.json"
            state_data = load_json(state_json_path, state_label)
            if state_data is not None:
                validate_state_json(state_data, state_upper, state_label)
                print(f"  Checked {state_label}")

            # Validate federal.json
            federal_json_path = os.path.join(state_dir, "federal.json")
            federal_label = f"data/{state_code}/federal.json"
            if os.path.exists(federal_json_path):
                federal_data = load_json(federal_json_path, federal_label)
                if federal_data is not None:
                    validate_federal_json(federal_data, state_upper, federal_label)
                    print(f"  Checked {federal_label}")

            # Validate local council files
            local_dir = os.path.join(state_dir, "local")
            if os.path.isdir(local_dir):
                for local_file in sorted(os.listdir(local_dir)):
                    if not local_file.endswith(".json"):
                        continue
                    local_path = os.path.join(local_dir, local_file)
                    local_label = f"data/{state_code}/local/{local_file}"
                    local_data = load_json(local_path, local_label)
                    if local_data is not None:
                        validate_local_file(local_data, local_label)
                print(f"  Checked data/{state_code}/local/ ({len(os.listdir(local_dir))} files)")

            # Validate boundary files
            if registry is not None:
                validate_boundary_files(registry, state_upper, state_dir)
                print(f"  Checked data/{state_code}/boundaries/")

    # Report results
    print()
    if warnings:
        print(f"{len(warnings)} warning(s):")
        for w in warnings:
            print(w)
        print()

    if errors:
        print(f"{len(errors)} error(s):")
        for e in errors:
            print(e)
        print("\nValidation FAILED.")
        sys.exit(1)
    else:
        print("All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
