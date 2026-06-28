"""Matplotlib price charts.

The backend is left to the caller: the CLI selects a headless backend before
importing this module, while a notebook keeps its inline backend so charts
render in-cell.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def plot_prices(
    prices: pd.DataFrame,
    normalize: bool = False,
    save_path: str | None = None,
    title: str | None = None,
    show: bool = False,
):
    """Plot adjusted close over time for each ticker in ``prices``.

    Parameters
    ----------
    normalize : bool
        If True, rebase each series to 100 at its first point so multiple
        tickers can be compared on one axis.
    save_path : str, optional
        If given, the figure is written to this path (PNG).
    show : bool
        If True, call ``plt.show()`` (useful for interactive sessions).

    Returns the matplotlib ``Figure``.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    for sym, group in prices.groupby("ticker", sort=False):
        g = group.sort_values("date")
        y = g["close"].astype(float)
        if normalize and len(y) and y.iloc[0]:
            y = y / y.iloc[0] * 100.0
        ax.plot(g["date"], y, label=sym, linewidth=1.5)

    ax.set_xlabel("Date")
    ax.set_ylabel("Price rebased to 100" if normalize else "Adjusted close")
    ax.set_title(
        title
        or ("Normalized price comparison (rebased to 100)" if normalize else "Price history")
    )
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=120)
    if show:
        plt.show()
    return fig
