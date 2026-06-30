"""Data model shared across the disclosure scraper."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

# Categories on which it is worth attempting a ticker match (publicly traded
# securities tend to appear here). Liabilities, activities, income, etc. are
# skipped to avoid false matches.
TICKERABLE_CATEGORIES = {
    "assets",
    "declarable assets",
    "investment in private corporations",  # usually private, but occasionally public
}

# Owner values
SELF = "self"
SPOUSE = "spouse"


def normalize_asset_name(name: str) -> str:
    """Loose normalization used for diffing the same asset across snapshots."""
    s = name.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .;,-")
    return s


@dataclass
class AssetRecord:
    """One disclosed line item for a person (their own or their spouse's)."""

    source: str  # "CIEC" | "Senate"
    person_id: str
    person_name: str
    role: str
    regime: str
    declaration_id: str
    declaration_type: str
    disclosed_date: str  # YYYY-MM-DD or ""
    owner: str  # SELF | SPOUSE
    category: str  # "Assets", "Liabilities", ...
    asset_name: str
    source_url: str = ""
    ticker: str = ""
    ticker_confidence: str = ""
    scrape_date: str = ""

    def key(self) -> tuple[str, str, str, str]:
        """Stable identity for diffing across snapshots."""
        return (
            self.person_id,
            self.owner,
            self.category.lower(),
            normalize_asset_name(self.asset_name),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AssetEvent:
    """A change detected between two snapshots."""

    event_type: str  # "purchased" | "sold"
    event_date: str  # YYYY-MM-DD (disclosure date, or detection date for sells)
    approximate: bool
    source: str
    person_id: str
    person_name: str
    role: str
    owner: str
    category: str
    asset_name: str
    ticker: str = ""
    source_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Person:
    """A roster entry."""

    person_id: str
    name: str
    role: str
    source: str
    profile_url: str = ""
    declaration_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["declaration_ids"] = ";".join(self.declaration_ids)
        return d
