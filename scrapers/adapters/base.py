"""Base adapter for scraping council member data."""

import abc
import re
from datetime import date


def deobfuscate_cf_email(encoded: str) -> str:
    """Decode a Cloudflare-obfuscated email address.

    Cloudflare email protection encodes emails as hex strings where the
    first two hex chars are the XOR key and subsequent pairs are the
    encoded characters. Found in href="/cdn-cgi/l/email-protection#HEXSTRING"
    and data-cfemail="HEXSTRING" attributes.
    """
    try:
        key = int(encoded[:2], 16)
        return "".join(
            chr(int(encoded[i:i+2], 16) ^ key)
            for i in range(2, len(encoded), 2)
        )
    except (ValueError, IndexError):
        return ""


def normalize_phone(phone_raw: str) -> str:
    """Normalize a US phone number to (NNN) NNN-NNNN format.

    Handles common formats: 803-212-6016, 803.212.6016, (803) 212-6016,
    8032126016, etc. Returns the original string if no 10-digit number found.
    """
    if not phone_raw or not phone_raw.strip():
        return ""
    phone_raw = phone_raw.strip()
    match = re.search(r"\(?(\d{3})\)?[\s.\-]*(\d{3})[\s.\-]*(\d{4})", phone_raw)
    if match:
        return f"({match.group(1)}) {match.group(2)}-{match.group(3)}"
    return phone_raw


class BaseAdapter(abc.ABC):
    """Abstract base class for jurisdiction scraper adapters."""

    def __init__(self, entry: dict):
        self.entry = entry
        self.id = entry["id"]
        self.url = entry.get("url", "")
        self.config = entry.get("adapterConfig", {})

    @abc.abstractmethod
    def fetch(self) -> str:
        """Fetch raw page content. Return HTML string."""

    @abc.abstractmethod
    def parse(self, html: str) -> list[dict]:
        """Parse HTML into raw member records."""

    def normalize(self, raw: list[dict]) -> list[dict]:
        """Map raw records to the unified schema.
        Subclasses may override for custom normalization.
        Default passes through with required metadata fields.
        """
        today = date.today().isoformat()
        for record in raw:
            record.setdefault("source", self.adapter_name())
            record.setdefault("lastUpdated", today)
            if record.get("phone"):
                record["phone"] = normalize_phone(record["phone"])
        return raw

    def validate(self, records: list[dict]) -> list[dict]:
        """Validate normalized records have required fields.

        Prints warnings for missing data but does not remove records.
        Raises ValueError if no records were produced.
        """
        if not records:
            raise ValueError(
                f"{self.adapter_name()} adapter for '{self.id}' produced 0 records"
            )

        for i, record in enumerate(records):
            if not record.get("name"):
                print(f"  WARNING: {self.id} record[{i}] has no name")
            if not record.get("title"):
                print(f"  WARNING: {self.id} record[{i}] ({record.get('name', '?')}) has no title")
            if not record.get("email") and not record.get("phone"):
                print(f"  WARNING: {self.id} record[{i}] ({record.get('name', '?')}) has no email or phone")

        return records

    def scrape(self) -> list[dict]:
        """Full pipeline: fetch -> parse -> normalize -> validate."""
        html = self.fetch()
        raw = self.parse(html)
        normalized = self.normalize(raw)
        return self.validate(normalized)

    def adapter_name(self) -> str:
        """Return the adapter name for the source field."""
        return self.__class__.__name__.lower().replace("adapter", "")
