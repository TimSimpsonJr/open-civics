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
}
