"""Stock price & news toolkit.

Core functions return tidy ``pandas`` DataFrames so they work equally well from
the command line (``python -m stocks.cli``) and inside a Jupyter notebook.

Public functions are imported lazily so that simply importing :mod:`stocks`
(e.g. from the CLI) does not pull in ``matplotlib`` until charts are actually
requested. This lets the CLI choose a headless backend before charts load.
"""

from __future__ import annotations

import importlib

# name -> module that defines it
_LAZY = {
    "get_prices": "stocks.prices",
    "get_current": "stocks.prices",
    "compute_performance": "stocks.performance",
    "get_news": "stocks.news",
    "get_news_rss": "stocks.news",
    "flag_big_moves": "stocks.news",
    "plot_prices": "stocks.charts",
    "build_report": "stocks.report",
}

__all__ = list(_LAZY)


def __getattr__(name):  # PEP 562 lazy attribute loading
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module 'stocks' has no attribute {name!r}")
    module = importlib.import_module(target)
    return getattr(module, name)


def __dir__():
    return sorted(list(globals().keys()) + __all__)
