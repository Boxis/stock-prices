"""Offline tests for snapshot diffing (purchased / sold detection)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disclosures.diff import diff_snapshots  # noqa: E402
from disclosures.models import AssetRecord  # noqa: E402


def _rec(person_id, name, asset, owner="self", category="Assets", disclosed=""):
    r = AssetRecord(
        source="CIEC", person_id=person_id, person_name=name, role="MP", regime="Code",
        declaration_id="d1", declaration_type="Disclosure Summaries (Code)",
        disclosed_date=disclosed, owner=owner, category=category, asset_name=asset,
    )
    # store snapshots are dict rows with an asset_key column
    d = r.to_dict()
    d["asset_key"] = "|".join(r.key())
    return d


def test_detects_purchase_and_sale():
    old = [
        _rec("p1", "Alice", "Shares of Royal Bank of Canada"),
        _rec("p1", "Alice", "Shares of Shopify"),
    ]
    new = [
        _rec("p1", "Alice", "Shares of Royal Bank of Canada"),
        _rec("p1", "Alice", "Shares of Enbridge", disclosed="2026-06-01"),
    ]
    events = diff_snapshots(old, new, detection_date="2026-06-28")
    kinds = {(e.event_type, e.asset_name) for e in events}
    assert ("sold", "Shares of Shopify") in kinds
    assert ("purchased", "Shares of Enbridge") in kinds
    # purchase uses the disclosed date; sale uses the detection date (approx).
    purchase = next(e for e in events if e.event_type == "purchased")
    sale = next(e for e in events if e.event_type == "sold")
    assert purchase.event_date == "2026-06-01" and purchase.approximate is False
    assert sale.event_date == "2026-06-28" and sale.approximate is True


def test_unchanged_yields_no_events():
    snap = [_rec("p1", "Alice", "Shares of Royal Bank of Canada")]
    assert diff_snapshots(snap, list(snap)) == []


def test_new_person_does_not_dump_purchases():
    # A person only in the new snapshot must not generate spurious 'purchased'.
    old = [_rec("p1", "Alice", "Shares of Royal Bank of Canada")]
    new = [
        _rec("p1", "Alice", "Shares of Royal Bank of Canada"),
        _rec("p2", "Bob", "Shares of Telus"),
    ]
    events = diff_snapshots(old, new)
    assert events == []


def test_spouse_and_self_are_distinct():
    old = [_rec("p1", "Alice", "Shares of Telus", owner="self")]
    new = [_rec("p1", "Alice", "Shares of Telus", owner="spouse")]
    events = diff_snapshots(old, new)
    kinds = {(e.event_type, e.owner) for e in events}
    assert ("sold", "self") in kinds
    assert ("purchased", "spouse") in kinds


def _run_all():
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")


if __name__ == "__main__":
    _run_all()
