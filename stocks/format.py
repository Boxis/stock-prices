"""Shared display formatting for DataFrames.

Turns the raw decimal/dollar/date values produced by the analysis functions
into human-readable strings. Used by both the CLI (before printing) and the web
app (before ``DataFrame.to_html``). Always returns a copy -- the input is left
untouched so the numeric data stays usable.
"""

from __future__ import annotations

import pandas as pd

# Decimals stored as fractions (0.1234 -> "12.34%").
PERCENT_COLUMNS = {
    "total_return",
    "cagr",
    "annualized_volatility",
    "max_drawdown",
    "best_day_return",
    "worst_day_return",
    "daily_return",
    "pct_return",
}

# Rendered as YYYY-MM-DD.
DATE_COLUMNS = {
    "date",
    "start_date",
    "end_date",
    "invest_date",
    "best_day",
    "worst_day",
    "news_date",
    "as_of",
}

# Rendered as $#,##0.00.
CURRENCY_COLUMNS = {
    "start_price",
    "end_price",
    "buy_price",
    "price",
    "invested",
    "end_value",
    "gain_loss",
}

# Rendered with 4 decimal places.
SHARES_COLUMNS = {"shares"}


def format_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with known columns formatted as strings."""
    if df is None or df.empty:
        return df.copy() if df is not None else df

    out = df.copy()
    for col in out.columns:
        if col in PERCENT_COLUMNS:
            out[col] = out[col].apply(
                lambda v: "" if pd.isna(v) else f"{v * 100:.2f}%"
            )
        elif col in CURRENCY_COLUMNS:
            out[col] = out[col].apply(
                lambda v: "" if pd.isna(v) else f"${v:,.2f}"
            )
        elif col in SHARES_COLUMNS:
            out[col] = out[col].apply(
                lambda v: "" if pd.isna(v) else f"{v:,.4f}"
            )
        elif col in DATE_COLUMNS:
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime(
                "%Y-%m-%d"
            )
    return out.fillna("")
