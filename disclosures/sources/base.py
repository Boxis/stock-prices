"""Common interface for disclosure sources."""

from __future__ import annotations

from typing import Protocol

from ..fetch import PoliteClient
from ..models import AssetRecord


class DisclosureSource(Protocol):
    name: str

    def scrape(
        self,
        client: PoliteClient,
        roles: list[str],
        limit: int | None = None,
        name_filter: str | None = None,
        refresh: bool = False,
    ) -> list[AssetRecord]:
        ...
