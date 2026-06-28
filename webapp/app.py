"""FastAPI web interface over the stocks toolkit.

Run with::

    uv run uvicorn webapp.app:app --reload

then open http://127.0.0.1:8000

The page is a single GET route: the form fields arrive as query params, so
result URLs are shareable/bookmarkable. All heavy lifting reuses the existing
``stocks`` functions -- this module is just a thin view layer.
"""

from __future__ import annotations

import base64
import html
import io
import os
import re
from datetime import date
from pathlib import Path

# Choose a non-GUI backend before charts (and thus pyplot) are imported.
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402

from stocks.charts import plot_prices  # noqa: E402
from stocks.format import format_for_display  # noqa: E402
from stocks.news import collect_news, flag_big_moves  # noqa: E402
from stocks.performance import compute_investment_returns, compute_performance  # noqa: E402
from stocks.prices import get_prices, normalize_tickers  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Stock Prices & News")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _parse_tickers(raw: str | None) -> list[str]:
    if not raw:
        return []
    return normalize_tickers([s for s in re.split(r"[,\s]+", raw.strip()) if s])


def _parse_float(raw: str | None):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _df_to_html(df: pd.DataFrame, link_cols: tuple[str, ...] = ()) -> str | None:
    """Render a DataFrame to a safe HTML table (text escaped, urls as links)."""
    if df is None or df.empty:
        return None
    disp = format_for_display(df).astype(str)
    for col in disp.columns:
        if col in link_cols:
            disp[col] = disp[col].apply(
                lambda u: (
                    f'<a href="{html.escape(u)}" target="_blank" '
                    f'rel="noopener">open</a>'
                    if u
                    else ""
                )
            )
        else:
            disp[col] = disp[col].apply(html.escape)
    return disp.to_html(index=False, escape=False, classes="data-table", border=0)


def _build_context(
    tickers: str | None,
    start: str | None,
    end: str | None,
    invest_date: str | None,
    amount: str | None,
    interval: str,
    news_top_n: str | None,
) -> dict:
    today = date.today().isoformat()
    top_n = _parse_int(news_top_n, 5)
    ctx = {
        "submitted": False,
        "errors": [],
        "notes": [],
        "today": today,
        "form": {
            "tickers": tickers or "",
            "start": start or "",
            "end": end or today,
            "invest_date": invest_date or "",
            "amount": amount or "",
            "interval": interval or "1d",
            "news_top_n": top_n,
        },
        "chart": None,
        "chart_norm": None,
        "perf_html": None,
        "invest_html": None,
        "moves_html": None,
        "invest_amount": _parse_float(amount),
    }

    symbols = _parse_tickers(tickers)
    if not symbols:
        return ctx  # first visit / empty form -> just show the form

    ctx["submitted"] = True

    if not start:
        ctx["errors"].append("Please provide a start date.")
        return ctx

    try:
        prices = get_prices(symbols, start, end or None, interval or "1d")
    except Exception as exc:
        ctx["errors"].append(f"Could not fetch any price data: {exc}")
        return ctx

    for sym, msg in prices.attrs.get("errors", {}).items():
        ctx["errors"].append(f"{sym}: {msg}")

    # Full-range performance
    ctx["perf_html"] = _df_to_html(compute_performance(prices))

    # Charts
    ctx["chart"] = _fig_to_base64(
        plot_prices(prices, normalize=False, marker_date=invest_date or None)
    )
    if prices["ticker"].nunique() > 1:
        ctx["chart_norm"] = _fig_to_base64(
            plot_prices(prices, normalize=True, marker_date=invest_date or None)
        )

    # Investment returns (investment date -> end)
    if invest_date:
        cutoff = pd.Timestamp(invest_date)
        data_min, data_max = prices["date"].min(), prices["date"].max()
        if cutoff < data_min:
            ctx["notes"].append(
                f"Investment date {invest_date} is before the available data "
                f"({data_min.date()}); using the earliest available price."
            )
        if cutoff > data_max:
            ctx["notes"].append(
                f"Investment date {invest_date} is after the available data "
                f"({data_max.date()}); no holding period to report."
            )
        invest = compute_investment_returns(
            prices, invest_date, amount=ctx["invest_amount"]
        )
        ctx["invest_html"] = _df_to_html(invest)
    else:
        ctx["notes"].append(
            "Enter an investment date to see returns from that date to the end."
        )

    # News / big-move panel
    news_frames = [collect_news(sym) for sym in prices["ticker"].unique()]
    news = pd.concat(news_frames, ignore_index=True) if news_frames else pd.DataFrame()
    moves = flag_big_moves(prices, news, top_n=top_n)
    ctx["moves_html"] = _df_to_html(
        moves[["ticker", "date", "daily_return", "headline", "publisher", "url"]],
        link_cols=("url",),
    )

    return ctx


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    tickers: str | None = None,
    start: str | None = None,
    end: str | None = None,
    invest_date: str | None = None,
    amount: str | None = None,
    interval: str = "1d",
    news_top_n: str | None = None,
):
    ctx = _build_context(
        tickers, start, end, invest_date, amount, interval, news_top_n
    )
    return templates.TemplateResponse(request=request, name="index.html", context=ctx)
