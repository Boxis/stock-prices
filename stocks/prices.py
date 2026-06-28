"""Fetch current and historical prices from Yahoo Finance via ``yfinance``.

All prices use adjusted close (``auto_adjust=True``) so that dividends and
splits are reflected in the series -- the honest basis for performance.
"""

from __future__ import annotations

from typing import Iterable, Union

import pandas as pd
import yfinance as yf

TickersArg = Union[str, Iterable[str]]

_PRICE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "volume"]


def normalize_tickers(tickers: TickersArg) -> list[str]:
    """Return a clean, upper-cased list of ticker symbols."""
    if isinstance(tickers, str):
        items = [tickers]
    else:
        items = list(tickers)
    return [str(t).strip().upper() for t in items if str(t).strip()]


def _strip_tz(series: pd.Series) -> pd.Series:
    """Drop timezone info so dates are naive and Excel/CSV friendly."""
    dt = pd.to_datetime(series)
    if getattr(dt.dt, "tz", None) is not None:
        dt = dt.dt.tz_localize(None)
    return dt


def get_prices(
    tickers: TickersArg,
    start,
    end=None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch historical OHLCV prices for one or more tickers.

    Parameters
    ----------
    tickers : str or iterable of str
        A single symbol or a list of symbols.
    start : str or date
        Start date (``YYYY-MM-DD`` or a ``date``). Inclusive.
    end : str or date, optional
        End date. ``None`` means up to today.
    interval : str
        ``1d``, ``1wk`` or ``1mo``.

    Returns
    -------
    DataFrame
        Tidy long form with columns
        ``[date, ticker, open, high, low, close, volume]`` where ``close`` is
        the adjusted close. Any per-ticker fetch problems are recorded in
        ``df.attrs['errors']`` (a ``{ticker: message}`` dict).
    """
    symbols = normalize_tickers(tickers)
    if not symbols:
        raise ValueError("No tickers provided.")

    frames: list[pd.DataFrame] = []
    errors: dict[str, str] = {}

    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(
                start=start, end=end, interval=interval, auto_adjust=True
            )
        except Exception as exc:  # network / parsing issues
            errors[sym] = f"fetch failed: {exc}"
            continue

        if hist is None or hist.empty:
            errors[sym] = "no data returned (check ticker symbol and date range)"
            continue

        df = hist.reset_index()
        date_col = next(
            (c for c in ("Date", "Datetime", "index") if c in df.columns),
            df.columns[0],
        )
        df = df.rename(
            columns={
                date_col: "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        df["date"] = _strip_tz(df["date"])
        df["ticker"] = sym
        frames.append(df[_PRICE_COLUMNS])

    if not frames:
        raise ValueError(f"No price data for any ticker. Details: {errors}")

    result = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )
    result.attrs["errors"] = errors
    return result


def get_current(tickers: TickersArg) -> pd.DataFrame:
    """Return the latest available price per ticker.

    Returns a DataFrame with columns ``[ticker, price, as_of]``.
    """
    symbols = normalize_tickers(tickers)
    rows = []
    for sym in symbols:
        ticker = yf.Ticker(sym)
        price = None
        try:
            info = ticker.fast_info
            price = info.get("last_price") or info.get("lastPrice")
        except Exception:
            price = None
        if price is None:
            try:
                recent = ticker.history(period="5d")
                if not recent.empty:
                    price = float(recent["Close"].iloc[-1])
            except Exception:
                price = None
        rows.append(
            {
                "ticker": sym,
                "price": float(price) if price is not None else None,
                "as_of": pd.Timestamp.now(),
            }
        )
    return pd.DataFrame(rows, columns=["ticker", "price", "as_of"])
