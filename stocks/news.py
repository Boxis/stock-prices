"""News fetching and alignment to large price moves.

Two free sources are used:

* ``yfinance`` ``Ticker.news`` -- convenient but recent-leaning (it is not a
  deep historical archive).
* Google News RSS search -- no API key, returns dated results, used to widen
  coverage. This is best-effort, not guaranteed complete.

``flag_big_moves`` finds the largest daily moves per ticker and attaches the
nearest news item within a small window, suggesting what may have driven each
move.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd

NEWS_COLUMNS = ["ticker", "date", "headline", "publisher", "url"]

_USER_AGENT = "Mozilla/5.0 (compatible; stock-prices/1.0)"


def _strip_tz(dt: pd.Series) -> pd.Series:
    out = pd.to_datetime(dt, utc=True, errors="coerce")
    return out.dt.tz_localize(None)


def _parse_yf_item(item: dict, sym: str) -> dict:
    """Handle both the legacy flat schema and the newer nested 'content'."""
    content = item.get("content") if isinstance(item, dict) else None
    if content:  # yfinance >= ~0.2.40
        provider = content.get("provider") or {}
        canonical = content.get("canonicalUrl") or {}
        click = content.get("clickThroughUrl") or {}
        return {
            "ticker": sym,
            "date": content.get("pubDate") or content.get("displayTime"),
            "headline": content.get("title"),
            "publisher": provider.get("displayName"),
            "url": canonical.get("url") or click.get("url"),
        }
    # legacy schema
    ts = item.get("providerPublishTime")
    date = pd.to_datetime(ts, unit="s", utc=True) if ts else pd.NaT
    return {
        "ticker": sym,
        "date": date,
        "headline": item.get("title"),
        "publisher": item.get("publisher"),
        "url": item.get("link"),
    }


def get_news(ticker: str, limit: int = 20) -> pd.DataFrame:
    """Fetch recent news for a single ticker from yfinance.

    Returns a DataFrame with columns ``[ticker, date, headline, publisher, url]``
    sorted newest first. Never raises on network issues -- returns empty instead.
    """
    import yfinance as yf

    sym = str(ticker).strip().upper()
    try:
        items = yf.Ticker(sym).news or []
    except Exception:
        items = []

    rows = [_parse_yf_item(it, sym) for it in items[:limit] if isinstance(it, dict)]
    df = pd.DataFrame(rows, columns=NEWS_COLUMNS)
    if not df.empty:
        df["date"] = _strip_tz(df["date"])
        df = df.dropna(subset=["headline"]).sort_values(
            "date", ascending=False, na_position="last"
        )
    return df.reset_index(drop=True)


def get_news_rss(query: str, limit: int = 25, timeout: int = 15) -> pd.DataFrame:
    """Best-effort Google News RSS search. No API key required.

    Returns ``[date, headline, publisher, url]`` (no ticker column). Returns an
    empty DataFrame on any failure.
    """
    cols = ["date", "headline", "publisher", "url"]
    encoded = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search?q={encoded}"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = resp.read()
        root = ET.fromstring(payload)
    except Exception:
        return pd.DataFrame(columns=cols)

    rows = []
    for item in root.iter("item"):
        rows.append(
            {
                "date": item.findtext("pubDate"),
                "headline": item.findtext("title"),
                "publisher": item.findtext("source"),
                "url": item.findtext("link"),
            }
        )
        if len(rows) >= limit:
            break

    df = pd.DataFrame(rows, columns=cols)
    if not df.empty:
        df["date"] = _strip_tz(df["date"])
        df = df.sort_values("date", ascending=False, na_position="last")
    return df.reset_index(drop=True)


def collect_news(ticker: str, use_rss: bool = True, limit: int = 20) -> pd.DataFrame:
    """Combine yfinance news and (optionally) Google News RSS for one ticker."""
    sym = str(ticker).strip().upper()
    frames = [get_news(sym, limit=limit)]
    if use_rss:
        rss = get_news_rss(f"{sym} stock", limit=limit)
        if not rss.empty:
            rss = rss.copy()
            rss["ticker"] = sym
            frames.append(rss[NEWS_COLUMNS])
    combined = pd.concat(frames, ignore_index=True)
    if not combined.empty:
        combined = combined.drop_duplicates(subset=["headline"]).reset_index(drop=True)
    return combined


def _nearest_news(news_df: pd.DataFrame, when, window_days: int = 1):
    """Return the news row closest to ``when`` within ``window_days``, or None."""
    if news_df is None or news_df.empty or pd.isna(when):
        return None
    nd = news_df.dropna(subset=["date"]).copy()
    if nd.empty:
        return None
    move_day = pd.Timestamp(when).normalize()
    nd["day_diff"] = (nd["date"].dt.normalize() - move_day).abs().dt.days
    within = nd[nd["day_diff"] <= window_days]
    if within.empty:
        return None
    return within.loc[within["day_diff"].idxmin()]


def flag_big_moves(
    prices: pd.DataFrame,
    news: pd.DataFrame | None = None,
    top_n: int = 5,
    window_days: int = 1,
    use_rss: bool = True,
) -> pd.DataFrame:
    """Identify each ticker's largest daily moves and attach nearby news.

    Parameters
    ----------
    prices : DataFrame
        Tidy price frame from :func:`stocks.prices.get_prices`.
    news : DataFrame, optional
        Pre-fetched news (columns ``[ticker, date, headline, publisher, url]``).
        If ``None``, news is fetched per ticker via :func:`collect_news`.
    top_n : int
        Number of largest absolute daily moves to report per ticker.
    window_days : int
        Calendar-day window for matching a headline to a move.

    Returns
    -------
    DataFrame with columns
    ``[ticker, date, close, daily_return, headline, news_date, publisher, url]``.
    """
    out_cols = [
        "ticker",
        "date",
        "close",
        "daily_return",
        "headline",
        "news_date",
        "publisher",
        "url",
    ]
    rows = []
    for sym, group in prices.groupby("ticker", sort=False):
        g = group.sort_values("date").copy()
        g["daily_return"] = g["close"].astype(float).pct_change()
        moves = g.dropna(subset=["daily_return"]).copy()
        if moves.empty:
            continue
        moves["abs_return"] = moves["daily_return"].abs()
        top = moves.nlargest(top_n, "abs_return")

        if news is not None and not news.empty:
            sym_news = news[news["ticker"] == sym]
        else:
            sym_news = collect_news(sym, use_rss=use_rss)

        for _, move in top.sort_values("date").iterrows():
            match = _nearest_news(sym_news, move["date"], window_days)
            rows.append(
                {
                    "ticker": sym,
                    "date": move["date"],
                    "close": round(float(move["close"]), 4),
                    "daily_return": float(move["daily_return"]),
                    "headline": None if match is None else match["headline"],
                    "news_date": None if match is None else match["date"],
                    "publisher": None if match is None else match["publisher"],
                    "url": None if match is None else match["url"],
                }
            )

    return pd.DataFrame(rows, columns=out_cols)
