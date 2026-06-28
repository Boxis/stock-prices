"""Offline tests for the performance math (no network required).

Runs under pytest, or directly with ``python tests/test_performance.py``.
"""

from __future__ import annotations

import os
import sys

import pandas as pd

# Allow running directly without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stocks.performance import compute_performance  # noqa: E402


def _synthetic_prices() -> pd.DataFrame:
    # Closes: 100 -> 110 (+10%) -> 99 (-10%) -> 121 (+22.22%)
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


def test_total_return():
    perf = compute_performance(_synthetic_prices()).iloc[0]
    assert abs(perf["total_return"] - 0.21) < 1e-9
    assert perf["start_price"] == 100.0
    assert perf["end_price"] == 121.0


def test_max_drawdown():
    perf = compute_performance(_synthetic_prices()).iloc[0]
    # Largest peak-to-trough: 110 -> 99 == -10%.
    assert abs(perf["max_drawdown"] - (-0.10)) < 1e-9


def test_best_and_worst_day():
    perf = compute_performance(_synthetic_prices()).iloc[0]
    assert abs(perf["best_day_return"] - (121.0 / 99.0 - 1.0)) < 1e-9
    assert abs(perf["worst_day_return"] - (-0.10)) < 1e-9
    assert pd.Timestamp(perf["worst_day"]) == pd.Timestamp("2024-01-04")
    assert pd.Timestamp(perf["best_day"]) == pd.Timestamp("2024-01-05")


def test_trading_days_and_dates():
    perf = compute_performance(_synthetic_prices()).iloc[0]
    assert perf["trading_days"] == 4
    assert pd.Timestamp(perf["start_date"]) == pd.Timestamp("2024-01-02")
    assert pd.Timestamp(perf["end_date"]) == pd.Timestamp("2024-01-05")


def test_multi_ticker_independent_windows():
    a = _synthetic_prices()
    b = _synthetic_prices().copy()
    b["ticker"] = "OTHER"
    b["close"] = [50.0, 55.0, 60.0, 66.0]  # monotonic +32%, no drawdown
    perf = compute_performance(pd.concat([a, b], ignore_index=True))
    assert set(perf["ticker"]) == {"TEST", "OTHER"}
    other = perf[perf["ticker"] == "OTHER"].iloc[0]
    assert abs(other["total_return"] - (66.0 / 50.0 - 1.0)) < 1e-9
    assert abs(other["max_drawdown"]) < 1e-9  # never dropped


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
