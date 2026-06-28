# stock-prices

Fetch **current and historical stock prices**, compute **performance over a date
range**, and pull in **news that may have driven big price moves** — all from
**free** data sources (Yahoo Finance via `yfinance`, plus Google News RSS).

Core logic lives in importable functions that return `pandas` DataFrames, so the
same code powers a command-line tool *and* interactive notebook use.

## Install

```bash
cd stock-prices
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS/Linux:         source .venv/bin/activate
pip install -r requirements.txt
```

## Command line

Run from inside the `stock-prices/` folder.

Compare several tickers over one shared window:

```bash
python -m stocks.cli --tickers AAPL MSFT GOOG --start 2023-01-01 --end 2024-01-01
```

Per-ticker start dates (portfolio "since I bought it") from a CSV:

```bash
python -m stocks.cli --input examples/portfolio.csv --excel
```

Useful flags: `--end` (default today), `--interval {1d,1wk,1mo}`, `--out DIR`,
`--excel` (one workbook instead of separate CSVs), `--no-charts`, `--no-rss`,
`--news-top-n N`.

### Outputs (written to `output/` by default)

- `performance_summary.csv` — one row per ticker: total return, CAGR,
  annualized volatility, max drawdown, best/worst day.
- `prices.csv` — full daily adjusted OHLCV history (long form).
- `news.csv` — collected headlines (yfinance + Google News RSS).
- `big_moves.csv` — the largest daily moves per ticker with the nearest matching
  headline.
- `prices.png` and, for multiple tickers, `comparison_normalized.png`.
- With `--excel`: a single `report.xlsx` (sheets *Performance / Prices / News /
  BigMoves*).

The performance summary and big-move table are also printed to the console.

## Notebook / Python use

```python
from stocks import get_prices, compute_performance, flag_big_moves, plot_prices

prices = get_prices(["AAPL", "MSFT"], start="2024-01-01", end="2024-06-01")
compute_performance(prices)        # DataFrame, one row per ticker
plot_prices(prices, normalize=True)  # rebased-to-100 comparison, renders inline
flag_big_moves(prices, top_n=5)    # biggest moves + likely news drivers
```

See `examples/explore.ipynb` for a runnable walkthrough.

## Web interface

A FastAPI app (in `webapp/`) wraps the same functions in a browser UI.

```bash
uv run uvicorn webapp.app:app --reload
# then open http://127.0.0.1:8000
```

Enter one or more tickers, a **data range** (start → end) for the chart and
full-range stats, and a separate **investment date** to see returns from that
date to the end. Optionally enter an **investment amount** (applied per ticker)
to also see shares bought, end value, and $ gain/loss. The page shows a price
chart (with a line marking the investment date), the investment-returns table,
full-range performance, and the news / big-move panel.

The form submits via GET, so result URLs are shareable, e.g.
`/?tickers=AAPL,MSFT&start=2026-01-01&invest_date=2026-03-01&amount=10000`.

## Notes & limitations

- Returns use **adjusted close**, so dividends and splits are included.
- Returns are stored as plain decimals (`0.1234` = 12.34%); the CLI formats them
  as percentages for display.
- `yfinance` is an unofficial Yahoo Finance client and can occasionally break or
  rate-limit; rerun if a fetch returns empty.
- **News is best-effort.** `yfinance` news is recent-leaning, not a deep
  historical archive, so big-move matching is strong for recent dates and sparse
  for older ones. The Google News RSS widener helps but is not guaranteed
  complete.
- Not financial advice.

## Tests

```bash
uv run python tests/test_performance.py    # performance math, no network
uv run python tests/test_investment.py     # investment returns, no network
# or, if pytest is installed:
uv run pytest
```
