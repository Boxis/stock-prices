"""Offline parser tests against a saved CIEC Details fixture."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disclosures.parse import parse_declaration_details  # noqa: E402

FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "disclosures", "fixtures", "ciec_details_mp.html",
)


def _records():
    html = open(FIXTURE, encoding="utf-8").read()
    return parse_declaration_details(
        html,
        source_url="https://ciec-ccie.parl.gc.ca/en/public-registry/Details"
        "?declarationId=877aeea7-e1b1-4348-bd5d-808c7758fb22",
    )


def test_identity_fields():
    recs = _records()
    assert recs, "expected records"
    r = recs[0]
    assert r.person_name == "Jason Groleau"
    assert r.role == "Member of Parliament"
    assert r.person_id == "f0f4e0ff-7b2a-f011-8195-001dd8b72449"
    assert r.declaration_id == "877aeea7-e1b1-4348-bd5d-808c7758fb22"
    assert r.disclosed_date == "2026-06-26"
    assert r.source == "CIEC"


def test_self_and_spouse_split():
    recs = _records()
    owners = {r.owner for r in recs}
    assert "self" in owners and "spouse" in owners
    spouse_assets = [
        r for r in recs if r.owner == "spouse" and r.category == "Assets"
    ]
    assert spouse_assets, "expected a spouse Assets row"
    assert "residential rental units" in spouse_assets[0].asset_name


def test_categories_aligned_case():
    recs = _records()
    # Self and spouse asset categories should be the same string ("Assets").
    cats = {(r.owner, r.category) for r in recs}
    assert ("self", "Assets") in cats
    assert ("spouse", "Assets") in cats


def test_bullets_split_into_entries():
    recs = _records()
    priv = [r for r in recs if r.category == "Investment in Private Corporations"]
    # Three controlling-interest companies + one significant-interest = 4 rows.
    assert len(priv) >= 4
    assert any("9264-2529 Quebec Inc." in r.asset_name for r in priv)
    assert all(r.asset_name.startswith(("Controlling interest", "Significant interest"))
               for r in priv)


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
