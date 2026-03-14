"""
Scrape representative data for US jurisdictions.

Usage:
    python -m scrapers                           # scrape all
    python -m scrapers --state SC                # one state
    python -m scrapers --state SC --state-only   # state legislators only
    python -m scrapers --state SC --local-only   # local councils only
    python -m scrapers --state SC --boundaries-only
    python -m scrapers --jurisdiction county:greenville
    python -m scrapers --dry-run
"""

import argparse
import json
import os
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
REGISTRY_PATH = os.path.join(PROJECT_ROOT, "registry.json")

from .adapters.anderson_county import AndersonCountyAdapter
from .adapters.barnwell_city import BarnwellCityAdapter
from .adapters.bishopville_city import BishopvilleCityAdapter
from .adapters.charleston_city import CharlestonCityAdapter
from .adapters.charleston_county import CharlestonCountyAdapter
from .adapters.cherokee_county import CherokeeCountyAdapter
from .adapters.chesterfield_county import ChesterfieldCountyAdapter
from .adapters.civicplus import CivicPlusAdapter
from .adapters.colleton_county import ColletonCountyAdapter
from .adapters.darlington_city import DarlingtonCityAdapter
from .adapters.darlington_county import DarlingtonCountyAdapter
from .adapters.florence_city import FlorenceCityAdapter
from .adapters.florence_county import FlorenceCountyAdapter
from .adapters.gaffney_city import GaffneyCityAdapter
from .adapters.generic_mailto import GenericMailtoAdapter
from .adapters.greenville_city import GreenvilleCityAdapter
from .adapters.greenville_county import GreenvilleCountyAdapter
from .adapters.greenwood_city import GreenwoodCityAdapter
from .adapters.greenwood_county import GreenwoodCountyAdapter
from .adapters.horry_county import HorryCountyAdapter
from .adapters.kingstree import KingstreeAdapter
from .adapters.laurens_county import LaurensCountyAdapter
from .adapters.lee_county import LeeCountyAdapter
from .adapters.marion_city import MarionCityAdapter
from .adapters.moncks_corner import MoncksCornerAdapter
from .adapters.newberry_county import NewberryCountyAdapter
from .adapters.orangeburg_city import OrangeburgCityAdapter
from .adapters.revize import RevizeAdapter
from .adapters.richland_county import RichlandCountyAdapter
from .adapters.saluda_county import SaludaCountyAdapter
from .adapters.st_george import StGeorgeAdapter
from .adapters.table_adapter import TableAdapter
from .adapters.walhalla_city import WalhallaCityAdapter
from .adapters.winnsboro import WinnsboroAdapter
from .adapters.york_county import YorkCountyAdapter

ADAPTERS = {
    "anderson_county": AndersonCountyAdapter,
    "barnwell_city": BarnwellCityAdapter,
    "bishopville_city": BishopvilleCityAdapter,
    "charleston_city": CharlestonCityAdapter,
    "charleston_county": CharlestonCountyAdapter,
    "cherokee_county": CherokeeCountyAdapter,
    "chesterfield_county": ChesterfieldCountyAdapter,
    "civicplus": CivicPlusAdapter,
    "colleton_county": ColletonCountyAdapter,
    "darlington_city": DarlingtonCityAdapter,
    "darlington_county": DarlingtonCountyAdapter,
    "florence_city": FlorenceCityAdapter,
    "florence_county": FlorenceCountyAdapter,
    "gaffney_city": GaffneyCityAdapter,
    "generic_mailto": GenericMailtoAdapter,
    "greenville_city": GreenvilleCityAdapter,
    "greenville_county": GreenvilleCountyAdapter,
    "greenwood_city": GreenwoodCityAdapter,
    "greenwood_county": GreenwoodCountyAdapter,
    "horry_county": HorryCountyAdapter,
    "kingstree": KingstreeAdapter,
    "laurens_county": LaurensCountyAdapter,
    "lee_county": LeeCountyAdapter,
    "marion_city": MarionCityAdapter,
    "moncks_corner": MoncksCornerAdapter,
    "newberry_county": NewberryCountyAdapter,
    "orangeburg_city": OrangeburgCityAdapter,
    "revize": RevizeAdapter,
    "richland_county": RichlandCountyAdapter,
    "saluda_county": SaludaCountyAdapter,
    "st_george": StGeorgeAdapter,
    "table": TableAdapter,
    "walhalla_city": WalhallaCityAdapter,
    "winnsboro": WinnsboroAdapter,
    "york_county": YorkCountyAdapter,
}


def load_registry():
    """Load and return the registry.json data."""
    if not os.path.exists(REGISTRY_PATH):
        print(f"ERROR: Registry not found at {REGISTRY_PATH}")
        sys.exit(1)

    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_adapter(entry):
    """Return an adapter instance for a jurisdiction entry, or None for manual."""
    adapter_name = entry.get("adapter")
    if not adapter_name or adapter_name == "manual":
        return None

    adapter_cls = ADAPTERS.get(adapter_name)
    if adapter_cls is None:
        print(f"  WARNING: Unknown adapter '{adapter_name}' for {entry.get('id', '?')}")
        return None

    return adapter_cls(entry)


def scrape_state(state_code, state_config, dry_run=False):
    """Scrape state legislators from OpenStates.

    Downloads the OpenStates CSV and writes a state.json file with
    senate and house members keyed by district number.
    """
    from .state import update_state_legislators

    source_url = state_config.get("openStatesUrl")
    if not source_url:
        print(f"  No openStatesUrl configured for {state_code}, skipping state scrape")
        return

    output_dir = os.path.join(PROJECT_ROOT, "data", state_code.lower())
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "state.json")

    print(f"\n{'=' * 60}")
    print(f"Scraping state legislators for {state_code}")
    print(f"{'=' * 60}")

    if dry_run:
        print(f"  Would download: {source_url}")
        print(f"  Would write: {output_path}")
        return

    update_state_legislators(source_url, output_path, state_code=state_code)


def scrape_local(state_code, state_config, jurisdiction_filter=None, dry_run=False):
    """Scrape local council members using jurisdiction adapters.

    Runs the appropriate adapter for each jurisdiction and writes per-jurisdiction
    JSON files to data/{state}/local/{jid}.json.
    """
    jurisdictions = state_config.get("jurisdictions", [])

    output_dir = os.path.join(PROJECT_ROOT, "data", state_code.lower(), "local")
    os.makedirs(output_dir, exist_ok=True)

    for entry in jurisdictions:
        jid = entry.get("id", "")
        label = entry.get("name", jid)

        # Filter if a specific jurisdiction was requested
        if jurisdiction_filter and jid != jurisdiction_filter:
            continue

        adapter_name = entry.get("adapter", "manual")

        print(f"\n{'=' * 60}")
        print(f"Scraping {label} ({jid})")
        print(f"{'=' * 60}")

        if adapter_name == "manual":
            print(f"  Adapter: manual (skipping)")
            continue

        adapter = get_adapter(entry)
        if adapter is None:
            continue

        # Build output filename from jurisdiction ID (e.g., county:greenville -> county-greenville.json)
        safe_id = jid.replace(":", "-")
        output_path = os.path.join(output_dir, f"{safe_id}.json")

        if dry_run:
            print(f"  Adapter: {adapter_name}")
            print(f"  Would scrape: {entry.get('url', '?')}")
            print(f"  Would write: {output_path}")
            continue

        try:
            members = adapter.scrape()
            print(f"  Scraped {len(members)} members")

            data = {
                "meta": {
                    "state": state_code,
                    "level": "local",
                    "jurisdiction": jid,
                    "label": label,
                    "lastUpdated": date.today().isoformat(),
                    "adapter": adapter_name,
                },
                "members": members,
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

            print(f"  Wrote {output_path}")

        except Exception as e:
            print(f"  ERROR scraping {jid}: {e}")


def scrape_boundaries(state_code, state_config, dry_run=False):
    """Build boundary GeoJSON files for a state."""
    from .boundaries import build_all_boundaries

    output_dir = os.path.join(PROJECT_ROOT, "data", state_code.lower(), "boundaries")

    print(f"\n{'=' * 60}")
    print(f"Building boundaries for {state_code}")
    print(f"{'=' * 60}")

    build_all_boundaries(state_config, output_dir, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape representative data for US jurisdictions."
    )
    parser.add_argument(
        "--state",
        help="Two-letter state code to scrape (default: all states in registry)",
    )
    parser.add_argument(
        "--state-only",
        action="store_true",
        help="Only scrape state legislators (skip local councils and boundaries)",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only scrape local councils (skip state legislators and boundaries)",
    )
    parser.add_argument(
        "--boundaries-only",
        action="store_true",
        help="Only build boundary files (skip state and local scraping)",
    )
    parser.add_argument(
        "--jurisdiction",
        help="Scrape a single jurisdiction by ID (e.g., county:greenville)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without actually scraping or writing files",
    )

    args = parser.parse_args()

    registry = load_registry()
    states = registry.get("states", {})

    if not states:
        print("ERROR: No states found in registry.json")
        sys.exit(1)

    # Determine which states to process
    if args.state:
        state_code = args.state.upper()
        if state_code not in states:
            print(f"ERROR: State '{state_code}' not found in registry.json")
            print(f"Available states: {', '.join(sorted(states.keys()))}")
            sys.exit(1)
        target_states = {state_code: states[state_code]}
    else:
        target_states = states

    # If --jurisdiction is specified, imply --local-only and --state
    if args.jurisdiction:
        args.local_only = True

    for state_code, state_config in target_states.items():
        print(f"\n{'#' * 60}")
        print(f"# {state_code}")
        print(f"{'#' * 60}")

        # Determine what to run
        run_state = not args.local_only and not args.boundaries_only
        run_local = not args.state_only and not args.boundaries_only
        run_boundaries = not args.state_only and not args.local_only

        if args.state_only:
            run_state = True
            run_local = False
            run_boundaries = False
        elif args.local_only:
            run_state = False
            run_local = True
            run_boundaries = False
        elif args.boundaries_only:
            run_state = False
            run_local = False
            run_boundaries = True

        if run_state:
            scrape_state(state_code, state_config, dry_run=args.dry_run)

        if run_local:
            scrape_local(
                state_code,
                state_config,
                jurisdiction_filter=args.jurisdiction,
                dry_run=args.dry_run,
            )

        if run_boundaries:
            scrape_boundaries(state_code, state_config, dry_run=args.dry_run)

    print(f"\n{'=' * 60}")
    print("Done!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
