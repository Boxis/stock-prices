"""Canadian politician disclosure scraper.

Scrapes federal political asset disclosures (Conflict of Interest and Ethics
Commissioner registry, and later the Senate Ethics Officer), tracks how holdings
change over time via a local SQLite history, maps asset names to tickers
best-effort, and exports an Excel workbook.

Public data, civic-transparency use. The HTTP client identifies itself, rate
limits, caches responses, and honours robots.txt.
"""
