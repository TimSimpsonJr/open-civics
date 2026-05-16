"""Centralized normalization of seat semantics into structured fields.

Called from both BaseAdapter.normalize() (locals) and scrapers/state.py
(state legislators and executive) so the same logic produces the same
structured fields regardless of source.

See docs/plans/2026-05-16-data-model-normalization-design.md for the
schema definition and the four-stage precedence model.
"""

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class NormalizationContext:
    """Context passed into normalize_member from the caller."""
    level: Literal["state", "local"]
    chamber: Optional[Literal["senate", "house", "executive"]] = None
    jurisdiction_type: Optional[Literal["county", "place"]] = None
    jurisdiction_id: Optional[str] = None
    registry_hints: Optional[dict] = None  # e.g. {"seatClass": "at-large", "partisan": False}


def normalize_member(record: dict, ctx: NormalizationContext) -> dict:
    """Fill missing structured seat fields on a member record.

    Four-stage precedence (see design doc §"Layered precedence"):
        1. Explicit source fields (gap-fill, highest non-override)
        2. Title parsing (gap-fill)
        3. Registry defaults (gap-fill, only for unknown seatClass)
        4. Manual overrides (override-anything)

    Returns the same dict, mutated in place.
    """
    # Stage 1: explicit source fields are already on the record. Nothing to do.
    # Stages 2-4 are implemented in subsequent tasks.
    return record
