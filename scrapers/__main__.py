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
import hashlib
import json
import os
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
REGISTRY_PATH = os.path.join(PROJECT_ROOT, "registry.json")

from .adapters.aiken_city import AikenCityAdapter
from .adapters.abbeville import AbbevilleAdapter
from .adapters.abbeville_county import AbbevilleCountyAdapter
from .adapters.allendale_county import AllendaleCountyAdapter
from .adapters.allendale_town import AllendaleTownAdapter
from .adapters.anderson_city import AndersonCityAdapter
from .adapters.anderson_county import AndersonCountyAdapter
from .adapters.bamberg_city import BambergCityAdapter
from .adapters.bamberg_county import BambergCountyAdapter
from .adapters.barnwell_city import BarnwellCityAdapter
from .adapters.beaufort_county import BeaufortCountyAdapter
from .adapters.bishopville_city import BishopvilleCityAdapter
from .adapters.charleston_city import CharlestonCityAdapter
from .adapters.charleston_county import CharlestonCountyAdapter
from .adapters.cherokee_county import CherokeeCountyAdapter
from .adapters.chester_city import ChesterCityAdapter
from .adapters.chester_county import ChesterCountyAdapter
from .adapters.chesterfield_county import ChesterfieldCountyAdapter
from .adapters.chesterfield_town import ChesterfieldTownAdapter
from .adapters.civicplus import CivicPlusAdapter
from .adapters.clarendon_county import ClarendonCountyAdapter
from .adapters.colleton_county import ColletonCountyAdapter
from .adapters.columbia import ColumbiaAdapter
from .adapters.conway_city import ConwayCityAdapter
from .adapters.darlington_city import DarlingtonCityAdapter
from .adapters.darlington_county import DarlingtonCountyAdapter
from .adapters.dillon_city import DillonCityAdapter
from .adapters.dillon_county import DillonCountyAdapter
from .adapters.edgefield_county import EdgefieldCountyAdapter
from .adapters.edgefield_town import EdgefieldTownAdapter
from .adapters.florence_city import FlorenceCityAdapter
from .adapters.florence_county import FlorenceCountyAdapter
from .adapters.gaffney_city import GaffneyCityAdapter
from .adapters.generic_mailto import GenericMailtoAdapter
from .adapters.goose_creek import GooseCreekAdapter
from .adapters.greenville_city import GreenvilleCityAdapter
from .adapters.greenville_county import GreenvilleCountyAdapter
from .adapters.greenwood_city import GreenwoodCityAdapter
from .adapters.greenwood_county import GreenwoodCountyAdapter
from .adapters.hampton_town import HamptonTownAdapter
from .adapters.hilton_head import HiltonHeadAdapter
from .adapters.horry_county import HorryCountyAdapter
from .adapters.kershaw_county import KershawCountyAdapter
from .adapters.kingstree import KingstreeAdapter
from .adapters.laurens_county import LaurensCountyAdapter
from .adapters.lee_county import LeeCountyAdapter
from .adapters.lexington_county import LexingtonCountyAdapter
from .adapters.marion_city import MarionCityAdapter
from .adapters.masc import MascAdapter
from .adapters.marlboro_county import MarlboroCountyAdapter
from .adapters.mccormick_county import McCormickCountyAdapter
from .adapters.mccormick_town import McCormickTownAdapter
from .adapters.moncks_corner import MoncksCornerAdapter
from .adapters.newberry_county import NewberryCountyAdapter
from .adapters.oconee_county import OconeeCountyAdapter
from .adapters.orangeburg_city import OrangeburgCityAdapter
from .adapters.revize import RevizeAdapter
from .adapters.richland_county import RichlandCountyAdapter
from .adapters.rock_hill import RockHillAdapter
from .adapters.saluda_county import SaludaCountyAdapter
from .adapters.scac import ScacAdapter
from .adapters.st_george import StGeorgeAdapter
from .adapters.st_matthews import StMatthewsAdapter
from .adapters.sumter_city import SumterCityAdapter
from .adapters.sumter_county import SumterCountyAdapter
from .adapters.table_adapter import TableAdapter
from .adapters.union_county import UnionCountyAdapter
from .adapters.walhalla_city import WalhallaCityAdapter
from .adapters.winnsboro import WinnsboroAdapter
from .adapters.york_county import YorkCountyAdapter

ADAPTERS = {
    "abbeville_city": AbbevilleAdapter,
    "aiken_city": AikenCityAdapter,
    "abbeville_county": AbbevilleCountyAdapter,
    "allendale_county": AllendaleCountyAdapter,
    "allendale_town": AllendaleTownAdapter,
    "anderson_city": AndersonCityAdapter,
    "anderson_county": AndersonCountyAdapter,
    "bamberg_city": BambergCityAdapter,
    "bamberg_county": BambergCountyAdapter,
    "barnwell_city": BarnwellCityAdapter,
    "beaufort_county": BeaufortCountyAdapter,
    "bishopville_city": BishopvilleCityAdapter,
    "charleston_city": CharlestonCityAdapter,
    "charleston_county": CharlestonCountyAdapter,
    "cherokee_county": CherokeeCountyAdapter,
    "chester_city": ChesterCityAdapter,
    "chester_county": ChesterCountyAdapter,
    "chesterfield_county": ChesterfieldCountyAdapter,
    "chesterfield_town": ChesterfieldTownAdapter,
    "civicplus": CivicPlusAdapter,
    "clarendon_county": ClarendonCountyAdapter,
    "colleton_county": ColletonCountyAdapter,
    "columbia": ColumbiaAdapter,
    "conway_city": ConwayCityAdapter,
    "darlington_city": DarlingtonCityAdapter,
    "darlington_county": DarlingtonCountyAdapter,
    "dillon_city": DillonCityAdapter,
    "dillon_county": DillonCountyAdapter,
    "edgefield_county": EdgefieldCountyAdapter,
    "edgefield_town": EdgefieldTownAdapter,
    "florence_city": FlorenceCityAdapter,
    "florence_county": FlorenceCountyAdapter,
    "gaffney_city": GaffneyCityAdapter,
    "generic_mailto": GenericMailtoAdapter,
    "goose_creek": GooseCreekAdapter,
    "greenville_city": GreenvilleCityAdapter,
    "greenville_county": GreenvilleCountyAdapter,
    "greenwood_city": GreenwoodCityAdapter,
    "greenwood_county": GreenwoodCountyAdapter,
    "hampton_town": HamptonTownAdapter,
    "hilton_head": HiltonHeadAdapter,
    "horry_county": HorryCountyAdapter,
    "kershaw_county": KershawCountyAdapter,
    "kingstree": KingstreeAdapter,
    "laurens_county": LaurensCountyAdapter,
    "lee_county": LeeCountyAdapter,
    "lexington_county": LexingtonCountyAdapter,
    "marion_city": MarionCityAdapter,
    "marlboro_county": MarlboroCountyAdapter,
    "masc": MascAdapter,
    "mccormick_county": McCormickCountyAdapter,
    "mccormick_town": McCormickTownAdapter,
    "moncks_corner": MoncksCornerAdapter,
    "newberry_county": NewberryCountyAdapter,
    "oconee_county": OconeeCountyAdapter,
    "orangeburg_city": OrangeburgCityAdapter,
    "revize": RevizeAdapter,
    "richland_county": RichlandCountyAdapter,
    "rock_hill": RockHillAdapter,
    "saluda_county": SaludaCountyAdapter,
    "scac": ScacAdapter,
    "st_george": StGeorgeAdapter,
    "st_matthews": StMatthewsAdapter,
    "sumter_city": SumterCityAdapter,
    "sumter_county": SumterCountyAdapter,
    "table": TableAdapter,
    "union_county": UnionCountyAdapter,
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
    from .state import update_state_legislators, scrape_executive

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

    try:
        update_state_legislators(source_url, output_path, state_code=state_code)
    except Exception as e:
        print(f"  ERROR scraping state legislators for {state_code}: {e}")
        return

    # Add executive officials
    executives = scrape_executive(state_code)
    if executives:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["executive"] = executives
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Added {len(executives)} executive officials")


def scrape_local(state_code, state_config, jurisdiction_filter=None, dry_run=False):
    """Scrape local council members using jurisdiction adapters.

    Runs the appropriate adapter for each jurisdiction and writes per-jurisdiction
    JSON files to data/{state}/local/{jid}.json.
    """
    jurisdictions = state_config.get("jurisdictions", [])
    results = {}

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

            # Compute hash of members content
            members_json = json.dumps(members, sort_keys=True, ensure_ascii=False)
            data_hash = hashlib.sha256(members_json.encode()).hexdigest()[:16]

            # Check previous file for existing hash
            data_last_changed = date.today().isoformat()
            if os.path.exists(output_path):
                try:
                    with open(output_path, "r", encoding="utf-8") as prev:
                        prev_data = json.load(prev)
                    prev_hash = prev_data.get("meta", {}).get("dataHash", "")
                    if prev_hash == data_hash:
                        # Data unchanged — preserve the previous dataLastChanged
                        data_last_changed = prev_data.get("meta", {}).get(
                            "dataLastChanged", date.today().isoformat()
                        )
                except (json.JSONDecodeError, IOError):
                    pass

            data["meta"]["dataHash"] = data_hash
            data["meta"]["dataLastChanged"] = data_last_changed

            # Add general contact info if adapter provides it
            contact = adapter.get_contact()
            if contact:
                data["meta"]["contact"] = contact

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

            print(f"  Wrote {output_path}")
            results[jid] = {
                "status": "warned" if adapter.warnings else "ok",
                "members": len(members),
                "warnings": adapter.warnings,
            }

        except Exception as e:
            print(f"  ERROR scraping {jid}: {e}")
            results[jid] = {"status": "error", "error": str(e), "members": 0, "warnings": []}

    return results


def scrape_federal(state_code=None, dry_run=False):
    """Scrape federal legislators from unitedstates/congress-legislators.

    Downloads the YAML once and writes per-state federal.json files.
    If state_code is provided, only that state's file is written.
    """
    from .federal import update_federal_legislators

    output_dir = os.path.join(PROJECT_ROOT, "data")

    print(f"\n{'=' * 60}")
    label = f"federal legislators for {state_code}" if state_code else "all federal legislators"
    print(f"Scraping {label}")
    print(f"{'=' * 60}")

    if dry_run:
        print("  Would download: unitedstates/congress-legislators YAML")
        print(f"  Would write: data/*/federal.json")
        return

    try:
        update_federal_legislators(output_dir, state_filter=state_code)
    except Exception as e:
        print(f"  ERROR scraping federal legislators: {e}")


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
        "--federal-only",
        action="store_true",
        help="Only scrape federal legislators (skip state, local, and boundaries)",
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
        "--skip-boundaries",
        action="store_true",
        help="Scrape state and local but skip boundary files",
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
    parser.add_argument(
        "--report",
        metavar="PATH",
        help="Write a JSON report of scrape results to the given path",
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

    all_results = {}

    for state_code, state_config in target_states.items():
        print(f"\n{'#' * 60}")
        print(f"# {state_code}")
        print(f"{'#' * 60}")

        # Determine what to run
        only_flags = [args.state_only, args.local_only, args.boundaries_only, args.federal_only]
        has_only = any(only_flags)

        run_state = not has_only or args.state_only
        run_local = not has_only or args.local_only
        run_boundaries = not has_only or args.boundaries_only
        run_federal = not has_only or args.federal_only

        if args.skip_boundaries:
            run_boundaries = False

        if run_state:
            scrape_state(state_code, state_config, dry_run=args.dry_run)

        if run_federal:
            scrape_federal(state_code=state_code, dry_run=args.dry_run)

        if run_local:
            local_results = scrape_local(
                state_code,
                state_config,
                jurisdiction_filter=args.jurisdiction,
                dry_run=args.dry_run,
            )
            for jid, result in local_results.items():
                all_results[f"{state_code.lower()}:{jid}"] = result

        if run_boundaries:
            scrape_boundaries(state_code, state_config, dry_run=args.dry_run)

    # Build summary from collected results
    total = len(all_results)
    ok = sum(1 for r in all_results.values() if r["status"] == "ok")
    warned = sum(1 for r in all_results.values() if r["status"] == "warned")
    failed = sum(1 for r in all_results.values() if r["status"] == "error")
    summary = {"total": total, "ok": ok, "warned": warned, "failed": failed}

    if all_results:
        print(f"\nSummary: {total} adapters — {ok} ok, {warned} warned, {failed} failed")

    if args.report:
        report = {
            "run_date": date.today().isoformat(),
            "adapters": all_results,
            "summary": summary,
        }
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Report written to {args.report}")

    print(f"\n{'=' * 60}")
    print("Done!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
