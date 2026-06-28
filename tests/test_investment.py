"""Offline tests for compute_investment_returns (no network required).

Runs under pytest, or directly with ``python tests/test_investment.py``.
"""

from __future__ import annotations

import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stocks.performance import compute_investment_returns  # noqa: E402


def _synthetic_prices() -> pd.DataFrame:
    # Closes: 100, 110, 99, 121 on 4 consecutive days.
    dates = pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    )
    closes = [100.0, 110.0, 99.0, 121.0]
    return pd.DataFrame(
        {
            "date": dates,
            "ticker": "TEST",
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000] * 4,
        }
    )


def test_pct_return_from_investment_date():
    # Invest on day 2 (price 110) -> end 121 => +10%.
    row = compute_investment_returns(_synthetic_prices(), "2024-01-03").iloc[0]
    assert abs(row["pct_return"] - 0.10) < 1e-9
    assert row["buy_price"] == 110.0
    assert row["end_price"] == 121.0
    assert pd.Timestamp(row["invest_date"]) == pd.Timestamp("2024-01-03")


def test_invest_date_snaps_to_next_trading_day():
    # 2024-01-03 is a trading day in the fixture; a weekend/gap date should snap
    # forward to the first available row >= that date.
    row = compute_investment_returns(_synthetic_prices(), "2024-01-02").iloc[0]
    assert pd.Timestamp(row["invest_date"]) == pd.Timestamp("2024-01-02")
    # A date between rows snaps to the next available row.
    row2 = compute_investment_returns(_synthetic_prices(), "2024-01-03").iloc[0]
    assert pd.Timestamp(row2["invest_date"]) == pd.Timestamp("2024-01-03")


def test_amount_math():
    row = compute_investment_returns(
        _synthetic_prices(), "2024-01-03", amount=11000.0
    ).iloc[0]
    # 11000 / 110 = 100 shares; end value 100 * 121 = 12100; gain 1100.
    assert math.isclose(row["shares"], 100.0)
    assert math.isclose(row["invested"], 11000.0)
    assert math.isclose(row["end_value"], 12100.0)
    assert math.isclose(row["gain_loss"], 1100.0)


def test_no_amount_leaves_dollar_columns_nan():
    row = compute_investment_returns(_synthetic_prices(), "2024-01-03").iloc[0]
    assert pd.isna(row["shares"])
    assert pd.isna(row["end_value"])
    assert pd.isna(row["gain_loss"])


def test_invest_date_after_data_returns_empty():
    out = compute_investment_returns(_synthetic_prices(), "2030-01-01")
    assert out.empty


def test_multi_ticker():
    a = _synthetic_prices()
    b = _synthetic_prices().copy()
    b["ticker"] = "OTHER"
    b["close"] = [50.0, 55.0, 60.0, 66.0]
    out = compute_investment_returns(
        pd.concat([a, b], ignore_index=True), "2024-01-03", amount=1000.0
    )
    assert set(out["ticker"]) == {"TEST", "OTHER"}
    other = out[out["ticker"] == "OTHER"].iloc[0]
    # Invest at 55 -> end 66 => +20%.
    assert abs(other["pct_return"] - 0.20) < 1e-9


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
