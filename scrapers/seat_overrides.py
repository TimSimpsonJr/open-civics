"""Per-record manual overrides for seat fields.

Keyed by (jurisdiction_id, member_name). Use this when:
- The source publishes wrong or missing structured data
- Title parsing produces a wrong value the registry hint can't fix
- A specific record needs a hand-curated patch

This is the only stage of the normalization precedence chain that
OVERWRITES existing structured values. Every entry should be reviewed
periodically; if a source becomes parseable, remove the override.

Schema: dict[(jurisdiction_id, name)] = {field: value, ...}
The normalizer applies these last and sets seatSource: "manual".
"""

SEAT_OVERRIDES: dict[tuple[str, str], dict] = {
    # Pickens County chairman: title "Chairman" alone, but they actually
    # represent District 3 (verified 2026-05-17 via pickenscountysc.gov).
    ("county:pickens", "Alex Saitta"): {
        "seatClass": "numbered",
        "seatLabel": "district",
        "seatId": "3",
    },
    # Kershaw County — 6 single-member districts + chairman elected at-large.
    # Primary site behind Akamai for scrapers. Verified against Wayback Machine
    # capture of https://www.kershaw.sc.gov/county-council/council-members
    # (web.archive.org/web/20251110034004) on 2026-05-20.
    ("county:kershaw", "Ben Connell"): {
        "seatClass": "at-large", "seatLabel": None, "seatId": None,
    },
    ("county:kershaw", "Russell Brazell"): {
        "seatClass": "numbered", "seatLabel": "district", "seatId": "1",
    },
    ("county:kershaw", "Sammie Tucker"): {
        "seatClass": "numbered", "seatLabel": "district", "seatId": "2",
    },
    ("county:kershaw", "Derek Shoemake"): {
        "seatClass": "numbered", "seatLabel": "district", "seatId": "3",
    },
    ("county:kershaw", "Jimmy Jones"): {
        "seatClass": "numbered", "seatLabel": "district", "seatId": "4",
    },
    ("county:kershaw", "Brant Tomlinson"): {
        "seatClass": "numbered", "seatLabel": "district", "seatId": "5",
    },
    ("county:kershaw", "Danny Catoe"): {
        "seatClass": "numbered", "seatLabel": "district", "seatId": "6",
    },
}
