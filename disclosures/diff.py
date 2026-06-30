"""Derive purchased/sold events by comparing two snapshots.

To avoid spurious events when a person enters or leaves the scraped scope, only
people present in *both* snapshots are diffed.
"""

from __future__ import annotations

from datetime import date

from .models import AssetEvent


def _index(records: list[dict]) -> dict[str, dict[str, dict]]:
    """person_id -> {asset_key -> record dict}."""
    out: dict[str, dict[str, dict]] = {}
    for r in records:
        out.setdefault(r["person_id"], {})[r["asset_key"]] = r
    return out


def diff_snapshots(
    old: list[dict], new: list[dict], detection_date: str | None = None
) -> list[AssetEvent]:
    detection_date = detection_date or date.today().isoformat()
    old_idx = _index(old)
    new_idx = _index(new)
    people = set(old_idx) & set(new_idx)

    events: list[AssetEvent] = []
    for pid in people:
        old_keys = old_idx[pid]
        new_keys = new_idx[pid]

        for key in new_keys.keys() - old_keys.keys():
            r = new_keys[key]
            disclosed = r.get("disclosed_date") or ""
            events.append(
                AssetEvent(
                    event_type="purchased",
                    event_date=disclosed or detection_date,
                    approximate=not bool(disclosed),
                    source=r.get("source", ""),
                    person_id=pid,
                    person_name=r.get("person_name", ""),
                    role=r.get("role", ""),
                    owner=r.get("owner", ""),
                    category=r.get("category", ""),
                    asset_name=r.get("asset_name", ""),
                    ticker=r.get("ticker", ""),
                    source_url=r.get("source_url", ""),
                )
            )

        for key in old_keys.keys() - new_keys.keys():
            r = old_keys[key]
            events.append(
                AssetEvent(
                    event_type="sold",
                    event_date=detection_date,  # disappearance date, approximate
                    approximate=True,
                    source=r.get("source", ""),
                    person_id=pid,
                    person_name=r.get("person_name", ""),
                    role=r.get("role", ""),
                    owner=r.get("owner", ""),
                    category=r.get("category", ""),
                    asset_name=r.get("asset_name", ""),
                    ticker=r.get("ticker", ""),
                    source_url=r.get("source_url", ""),
                )
            )
    return events
