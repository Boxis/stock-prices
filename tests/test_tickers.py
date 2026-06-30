"""Offline tests for best-effort asset-name -> ticker mapping."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from disclosures.models import AssetRecord, TICKERABLE_CATEGORIES  # noqa: E402
from disclosures.tickers import annotate_tickers, lookup_ticker  # noqa: E402


def test_matches_common_issuers():
    t, conf = lookup_ticker("1,000 common shares of Royal Bank of Canada")
    assert t == "RY.TO" and conf in {"high", "medium"}

    t, _ = lookup_ticker("Shares of Shopify Inc.")
    assert t == "SHOP.TO"

    t, _ = lookup_ticker("Enbridge Inc.")
    assert t == "ENB.TO"


def test_us_issuer():
    t, _ = lookup_ticker("100 shares of Apple Inc.")
    assert t == "AAPL"


def test_non_public_assets_blank():
    # Real estate / private corps should not match a public ticker.
    assert lookup_ticker("Residential rental property in Quebec City")[0] == ""
    assert lookup_ticker("9264-2529 Quebec Inc., operating as a supermarket")[0] == ""


def test_generic_token_false_positive_guarded():
    # "...International Real Estate Development..." must NOT match "TFI International"
    # just because they share the generic word "International".
    assert lookup_ticker(
        "Promissory note from WEBBCO International Real Estate Development Inc."
    )[0] == ""


def test_industry_word_collisions_guarded():
    # A different issuer that shares only an industry word must NOT match.
    assert lookup_ticker("Shares of Cardinal Energy Ltd.")[0] == ""     # not TC Energy
    assert lookup_ticker("Shares of Arc Resources Ltd.")[0] == ""       # not Cdn Natural Res.
    assert lookup_ticker("Shares of: Verizon Communications")[0] == ""  # not Rogers
    assert lookup_ticker("Stocks: Laurentian Bank of Canada")[0] == ""  # not Royal Bank
    assert lookup_ticker("Gold.")[0] == ""                              # not Barrick Gold


def test_geography_word_collision_guarded():
    # Real estate in a city must not match a bank named after that city.
    assert lookup_ticker(
        "Sole ownership of a residential rental unit located in Montreal, Quebec"
    )[0] == ""  # not Bank of Montreal


def test_short_name_omitting_industry_word_still_matches():
    # The disclosed text often drops the issuer's industry word; still match it.
    assert lookup_ticker("Shares of Cenovus")[0] == "CVE.TO"
    assert lookup_ticker("Shares of Suncor Energy Inc.")[0] == "SU.TO"
    assert lookup_ticker("Shares of TC Energy Corp")[0] == "TRP.TO"


def test_annotate_only_asset_categories():
    recs = [
        AssetRecord("CIEC", "p1", "A", "MP", "Code", "d", "t", "", "self",
                    "Assets", "Shares of Telus"),
        AssetRecord("CIEC", "p1", "A", "MP", "Code", "d", "t", "", "self",
                    "Activities", "Director of Telus"),
    ]
    annotate_tickers(recs, TICKERABLE_CATEGORIES)
    assert recs[0].ticker == "T.TO"          # Assets -> matched
    assert recs[1].ticker == ""              # Activities -> skipped


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
