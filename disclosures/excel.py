"""Build the Excel workbook (Assets / Events / People) from the store."""

from __future__ import annotations

import pandas as pd

ASSET_COLUMNS = [
    "person_name", "role", "source", "asset_name", "ticker", "ticker_confidence",
    "owner", "category", "declaration_type", "disclosed_date", "first_seen",
    "status", "sold_date", "source_url", "scrape_date",
]


def _assets_frame(latest_records: list[dict], events: list[dict], scrape_date: str) -> pd.DataFrame:
    """Current holdings (latest snapshot) plus rows for assets later sold."""
    rows = []
    latest_keys = {(r["person_id"], r["asset_key"]) for r in latest_records}

    for r in latest_records:
        rows.append(
            {
                "person_name": r["person_name"], "role": r["role"], "source": r["source"],
                "asset_name": r["asset_name"], "ticker": r["ticker"],
                "ticker_confidence": r["ticker_confidence"], "owner": r["owner"],
                "category": r["category"], "declaration_type": r["declaration_type"],
                "disclosed_date": r["disclosed_date"], "first_seen": r["first_seen"],
                "status": "active", "sold_date": "", "source_url": r["source_url"],
                "scrape_date": scrape_date,
            }
        )

    # Append sold assets (in events as 'sold', not currently held).
    for e in events:
        if e["event_type"] != "sold":
            continue
        rows.append(
            {
                "person_name": e["person_name"], "role": e["role"], "source": e["source"],
                "asset_name": e["asset_name"], "ticker": e["ticker"],
                "ticker_confidence": "", "owner": e["owner"], "category": e["category"],
                "declaration_type": "", "disclosed_date": "", "first_seen": "",
                "status": "sold", "sold_date": e["event_date"], "source_url": e["source_url"],
                "scrape_date": scrape_date,
            }
        )
    return pd.DataFrame(rows, columns=ASSET_COLUMNS)


def write_workbook(path: str, latest_records: list[dict], events: list[dict], scrape_date: str) -> None:
    assets = _assets_frame(latest_records, events, scrape_date)

    events_df = pd.DataFrame(events)
    if not events_df.empty:
        events_df = events_df[
            ["event_type", "event_date", "approximate", "person_name", "role",
             "owner", "category", "asset_name", "ticker", "source", "source_url"]
        ]

    people_df = (
        assets[["person_name", "role", "source"]]
        .drop_duplicates()
        .sort_values(["source", "person_name"])
        if not assets.empty
        else pd.DataFrame(columns=["person_name", "role", "source"])
    )

    with pd.ExcelWriter(path) as writer:
        assets.to_excel(writer, sheet_name="Assets", index=False)
        (events_df if not events_df.empty else pd.DataFrame(
            columns=["event_type", "event_date", "person_name", "asset_name"]
        )).to_excel(writer, sheet_name="Events", index=False)
        people_df.to_excel(writer, sheet_name="People", index=False)
