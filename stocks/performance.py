"""Performance metrics computed from a tidy price DataFrame.

Returns (``total_return``, ``cagr``, ``annualized_volatility``,
``max_drawdown``, ``best_day_return``, ``worst_day_return``) are stored as
plain decimals (0.1234 == 12.34%) so they stay easy to work with downstream.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252

PERFORMANCE_COLUMNS = [
    "ticker",
    "start_date",
    "end_date",
    "start_price",
    "end_price",
    "total_return",
    "cagr",
    "annualized_volatility",
    "max_drawdown",
    "best_day",
    "best_day_return",
    "worst_day",
    "worst_day_return",
    "trading_days",
]


def _metrics_for_ticker(ticker: str, group: pd.DataFrame) -> dict:
    g = group.sort_values("date")
    closes = g["close"].astype(float)
    dates = g["date"]

    start_price = float(closes.iloc[0])
    end_price = float(closes.iloc[-1])
    start_date = dates.iloc[0]
    end_date = dates.iloc[-1]

    total_return = end_price / start_price - 1.0 if start_price else np.nan

    span_days = (end_date - start_date).days
    years = span_days / 365.25 if span_days > 0 else np.nan
    if years and years > 0 and start_price > 0:
        cagr = (end_price / start_price) ** (1.0 / years) - 1.0
    else:
        cagr = np.nan

    daily = closes.pct_change().dropna()
    if len(daily) > 1:
        volatility = float(daily.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
    else:
        volatility = np.nan

    running_max = closes.cummax()
    drawdown = closes / running_max - 1.0
    max_drawdown = float(drawdown.min()) if not drawdown.empty else np.nan

    if not daily.empty:
        best_idx = daily.idxmax()
        worst_idx = daily.idxmin()
        best_day = g.loc[best_idx, "date"]
        worst_day = g.loc[worst_idx, "date"]
        best_day_return = float(daily.loc[best_idx])
        worst_day_return = float(daily.loc[worst_idx])
    else:
        best_day = worst_day = pd.NaT
        best_day_return = worst_day_return = np.nan

    return {
        "ticker": ticker,
        "start_date": start_date,
        "end_date": end_date,
        "start_price": round(start_price, 4),
        "end_price": round(end_price, 4),
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": volatility,
        "max_drawdown": max_drawdown,
        "best_day": best_day,
        "best_day_return": best_day_return,
        "worst_day": worst_day,
        "worst_day_return": worst_day_return,
        "trading_days": int(len(g)),
    }


def compute_performance(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute one row of performance metrics per ticker.

    ``prices`` is the tidy DataFrame returned by
    :func:`stocks.prices.get_prices`. Each ticker is evaluated over whatever
    date window is present for it, which is what makes per-ticker start dates
    work automatically.
    """
    if prices.empty:
        return pd.DataFrame(columns=PERFORMANCE_COLUMNS)

    rows = [
        _metrics_for_ticker(sym, group)
        for sym, group in prices.groupby("ticker", sort=False)
    ]
    return pd.DataFrame(rows, columns=PERFORMANCE_COLUMNS)
