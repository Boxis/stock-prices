"""Command-line interface: ``python -m stocks.cli ...``

Examples
--------
Uniform date range across several tickers (comparison)::

    python -m stocks.cli --tickers AAPL MSFT GOOG --start 2023-01-01 --end 2024-01-01

Per-ticker start dates from a CSV (portfolio)::

    python -m stocks.cli --input examples/portfolio.csv --excel
"""

from __future__ import annotations

import argparse
import os
import sys

# Pick a headless backend before any pyplot import happens (charts load later,
# via report). This keeps the CLI from trying to open a GUI window.
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib  # noqa: E402

matplotlib.use("Agg")

import pandas as pd  # noqa: E402

from .report import build_report  # noqa: E402

_PERCENT_COLUMNS = [
    "total_return",
    "cagr",
    "annualized_volatility",
    "max_drawdown",
    "best_day_return",
    "worst_day_return",
    "daily_return",
]
_DATE_COLUMNS = ["start_date", "end_date", "best_day", "worst_day", "news_date"]


def _print_df(df: pd.DataFrame, title: str) -> None:
    print(f"\n=== {title} ===")
    if df is None or df.empty:
        print("(no rows)")
        return
    display = df.copy()
    for col in _PERCENT_COLUMNS:
        if col in display.columns:
            display[col] = display[col].apply(
                lambda v: "" if pd.isna(v) else f"{v * 100:.2f}%"
            )
    for col in _DATE_COLUMNS:
        if col in display.columns:
            display[col] = pd.to_datetime(display[col], errors="coerce").dt.strftime(
                "%Y-%m-%d"
            )
    display = display.fillna("")
    try:
        from tabulate import tabulate

        print(
            tabulate(
                display, headers="keys", tablefmt="github", showindex=False
            )
        )
    except Exception:
        print(display.to_string(index=False))


def _specs_from_args(args) -> list[dict]:
    if args.input:
        df = pd.read_csv(args.input)
        df.columns = [c.strip().lower() for c in df.columns]
        if "ticker" not in df.columns or "start_date" not in df.columns:
            raise SystemExit(
                "CSV must have at least 'ticker' and 'start_date' columns "
                "(optional 'end_date')."
            )
        specs = []
        for _, row in df.iterrows():
            end = row.get("end_date")
            specs.append(
                {
                    "ticker": str(row["ticker"]).strip(),
                    "start": str(row["start_date"]).strip(),
                    "end": None if pd.isna(end) else str(end).strip(),
                }
            )
        return specs

    if not args.tickers or not args.start:
        raise SystemExit(
            "Provide either --input CSV, or --tickers AND --start."
        )
    return [
        {"ticker": t, "start": args.start, "end": args.end} for t in args.tickers
    ]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stocks",
        description="Fetch prices, performance and news for stock tickers "
        "using free data (Yahoo Finance).",
    )
    p.add_argument("--tickers", nargs="+", help="One or more ticker symbols.")
    p.add_argument("--start", help="Start date YYYY-MM-DD (uniform range mode).")
    p.add_argument("--end", help="End date YYYY-MM-DD (default: today).")
    p.add_argument(
        "--input",
        help="CSV with columns ticker,start_date[,end_date] for per-ticker dates.",
    )
    p.add_argument(
        "--interval",
        default="1d",
        choices=["1d", "1wk", "1mo"],
        help="Sampling interval (default 1d).",
    )
    p.add_argument("--out", default="output", help="Output directory.")
    p.add_argument(
        "--excel",
        action="store_true",
        help="Write a single multi-sheet report.xlsx instead of separate CSVs.",
    )
    p.add_argument(
        "--no-charts", action="store_true", help="Skip chart generation."
    )
    p.add_argument(
        "--no-rss",
        action="store_true",
        help="Skip the Google News RSS widener (yfinance news only).",
    )
    p.add_argument(
        "--news-top-n",
        type=int,
        default=5,
        help="Number of largest daily moves to flag per ticker (default 5).",
    )
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    specs = _specs_from_args(args)

    result = build_report(
        specs,
        out_dir=args.out,
        excel=args.excel,
        make_charts=not args.no_charts,
        news_top_n=args.news_top_n,
        interval=args.interval,
        use_rss=not args.no_rss,
    )

    _print_df(result["performance"], "Performance summary")
    _print_df(
        result["big_moves"][
            ["ticker", "date", "daily_return", "headline", "publisher", "url"]
        ],
        "Largest daily moves & possible drivers",
    )

    if result["errors"]:
        print("\nWarnings:")
        for sym, msg in result["errors"].items():
            print(f"  - {sym}: {msg}")

    print(f"\nOutputs written to: {os.path.abspath(args.out)}")
    for path in result["charts"]:
        print(f"  chart: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
