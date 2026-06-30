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

## Canadian politician disclosures (`disclosures/`)

Scrapes federal political asset disclosures from the **CIEC public registry**
([ciec-ccie.parl.gc.ca](https://ciec-ccie.parl.gc.ca/en/public-registry)) —
Members of Parliament (Conflict of Interest *Code*) and ministers / public
office holders (Conflict of Interest *Act*) — including spouse/family assets.
It tracks changes over time and exports an Excel workbook with the asset name,
best-effort ticker, owner (self/spouse), dates, and active/sold status.

```bash
# Scrape a few MPs (polite, cached) and export Excel:
uv run python -m disclosures.cli --source ciec --role mp --limit 5

# Multiple roles, full run:
uv run python -m disclosures.cli --source ciec --role mp minister poh \
    --out output/disclosures.xlsx
```

Flags: `--role {mp,minister,poh,gic,staff,parlsec}`, `--limit N`,
`--name <substring>`, `--db <path>`, `--out <xlsx>`, `--delay <seconds>`,
`--refresh` (ignore cache), `--no-tickers`.

**How tracking works (ongoing monitoring):** each run stores a snapshot in a
local SQLite history (`output/disclosures.db`) and diffs it against the previous
run to log **purchased** / **sold** events. Re-running on a schedule is the
monitor — a single run only captures current holdings.

The workbook has three sheets: **Assets** (current holdings + sold rows),
**Events** (purchase/sale log), **People** (roster).

### Important caveats (not bugs)
- **Ministers/POHs must divest** publicly traded securities, so they rarely have
  tickers; the richest stock data is from **MPs**.
- Public summaries carry **no dollar values or share counts** — presence + dates
  only.
- **Sold-date is the detection/disclosure date, not the trade date.**
- Ticker mapping is **best-effort** (curated issuer list + fuzzy match with a
  confidence flag); real estate, private corporations, and trusts stay blank.
- **Senators** (separate Senate Ethics Officer site; no spouse data published)
  are a planned follow-on and not yet scraped.

Scraping is polite: a self-identifying User-Agent, rate limiting, on-disk
caching, and `robots.txt` is honoured. This is public civic-transparency data.

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
