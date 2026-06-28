"""Orchestration: turn a list of ticker/date specs into tables, charts, files.

A *spec* is a dict ``{"ticker": "AAPL", "start": "2024-01-01", "end": None}``.
Because each ticker is fetched against its own spec, per-ticker start dates work
out of the box (the portfolio use case), while passing the same start/end for
every ticker covers the comparison use case.
"""

from __future__ import annotations

import os

import pandas as pd

from .charts import plot_prices
from .news import collect_news, flag_big_moves
from .performance import compute_performance
from .prices import get_prices


def build_report(
    specs: list[dict],
    out_dir: str = "output",
    excel: bool = False,
    make_charts: bool = True,
    news_top_n: int = 5,
    interval: str = "1d",
    use_rss: bool = True,
) -> dict:
    """Fetch everything and write outputs to ``out_dir``.

    Returns a dict with keys ``prices``, ``performance``, ``news``,
    ``big_moves`` (all DataFrames), plus ``errors`` and ``charts`` (list of
    written PNG paths).
    """
    os.makedirs(out_dir, exist_ok=True)

    frames: list[pd.DataFrame] = []
    errors: dict[str, str] = {}
    for spec in specs:
        sym = str(spec["ticker"]).strip().upper()
        try:
            part = get_prices(sym, spec["start"], spec.get("end"), interval)
            frames.append(part)
            errors.update(part.attrs.get("errors", {}))
        except Exception as exc:
            errors[sym] = str(exc)

    if not frames:
        raise ValueError(f"No price data could be fetched. Details: {errors}")

    prices = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )

    performance = compute_performance(prices)

    news_frames = [
        collect_news(sym, use_rss=use_rss) for sym in prices["ticker"].unique()
    ]
    news = (
        pd.concat(news_frames, ignore_index=True)
        if news_frames
        else pd.DataFrame()
    )

    big_moves = flag_big_moves(prices, news, top_n=news_top_n)

    chart_paths: list[str] = []
    if make_charts:
        price_chart = os.path.join(out_dir, "prices.png")
        plot_prices(prices, normalize=False, save_path=price_chart)
        chart_paths.append(price_chart)
        if prices["ticker"].nunique() > 1:
            compare_chart = os.path.join(out_dir, "comparison_normalized.png")
            plot_prices(prices, normalize=True, save_path=compare_chart)
            chart_paths.append(compare_chart)

    if excel:
        xlsx_path = os.path.join(out_dir, "report.xlsx")
        with pd.ExcelWriter(xlsx_path) as writer:
            performance.to_excel(writer, sheet_name="Performance", index=False)
            prices.to_excel(writer, sheet_name="Prices", index=False)
            news.to_excel(writer, sheet_name="News", index=False)
            big_moves.to_excel(writer, sheet_name="BigMoves", index=False)
    else:
        performance.to_csv(
            os.path.join(out_dir, "performance_summary.csv"), index=False
        )
        prices.to_csv(os.path.join(out_dir, "prices.csv"), index=False)
        news.to_csv(os.path.join(out_dir, "news.csv"), index=False)
        big_moves.to_csv(os.path.join(out_dir, "big_moves.csv"), index=False)

    return {
        "prices": prices,
        "performance": performance,
        "news": news,
        "big_moves": big_moves,
        "errors": errors,
        "charts": chart_paths,
    }
