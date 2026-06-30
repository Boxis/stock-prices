"""CLI: scrape disclosures -> store snapshot -> diff -> export Excel.

Examples
--------
    python -m disclosures.cli --source ciec --role mp --limit 5
    python -m disclosures.cli --source ciec --role mp minister poh --out output/disclosures.xlsx

Re-running is the "monitor": each run snapshots current holdings and diffs
against the previous run to log purchased/sold events.
"""

from __future__ import annotations

import argparse
from datetime import date

from .excel import write_workbook
from .fetch import PoliteClient
from .models import TICKERABLE_CATEGORIES
from .sources import ciec
from .store import Store
from .tickers import annotate_tickers


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="disclosures",
        description="Scrape Canadian political asset disclosures, track changes, "
        "export Excel.",
    )
    p.add_argument("--source", choices=["ciec"], default="ciec",
                   help="Disclosure source (Senate to come).")
    p.add_argument("--role", nargs="+", default=["mp"],
                   choices=list(ciec.ROLE_GUIDS.keys()),
                   help="Roles to scrape (default: mp). Only 'mp' itemizes "
                        "assets; Act roles (minister/poh/gic/staff/parlsec) "
                        "divest into blind trusts and yield no asset rows.")
    p.add_argument("--limit", type=int, default=None,
                   help="Max people to scrape (for testing / incremental runs).")
    p.add_argument("--name", default=None,
                   help="Only include people whose name contains this substring.")
    p.add_argument("--db", default="output/disclosures.db", help="SQLite history path.")
    p.add_argument("--out", default="output/disclosures.xlsx", help="Excel output path.")
    p.add_argument("--delay", type=float, default=1.5,
                   help="Seconds between requests (politeness).")
    p.add_argument("--refresh", action="store_true",
                   help="Ignore the on-disk cache and refetch.")
    p.add_argument("--no-tickers", action="store_true",
                   help="Skip best-effort ticker mapping.")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    scrape_date = date.today().isoformat()

    # Only MPs (Code) publicly itemize holdings. Act roles divest into blind
    # trusts and publish only a compliance attestation -> no asset rows.
    act_roles = [r for r in args.role if r != "mp"]
    if act_roles:
        print(f"Note: {', '.join(act_roles)} file under the Conflict of Interest "
              "Act and divest into blind trusts -- their summary statements carry "
              "no itemized assets, so they contribute no rows. Use --role mp for "
              "asset data.")

    client = PoliteClient(delay=args.delay)
    print(f"Scraping {args.source} for roles={args.role} (limit={args.limit})...")
    records = ciec.scrape(
        client, roles=args.role, limit=args.limit, name_filter=args.name,
        refresh=args.refresh,
    )
    for r in records:
        r.scrape_date = scrape_date
    print(f"  parsed {len(records)} records "
          f"from {len({r.person_id for r in records})} people")

    if not args.no_tickers:
        annotate_tickers(records, TICKERABLE_CATEGORIES)
        matched = sum(1 for r in records if r.ticker)
        print(f"  ticker matches: {matched}")

    store = Store(args.db)
    prior_ids = store.snapshot_ids()
    snap_id = store.save_snapshot(records, scope=",".join(args.role))

    events = []
    if prior_ids:
        from .diff import diff_snapshots

        old = store.snapshot_records(prior_ids[-1])
        new = store.snapshot_records(snap_id)
        events = diff_snapshots(old, new, detection_date=scrape_date)
        store.save_events(events)
        purchased = sum(1 for e in events if e.event_type == "purchased")
        sold = sum(1 for e in events if e.event_type == "sold")
        print(f"  changes since last run: {purchased} purchased, {sold} sold")
    else:
        print("  first snapshot (no prior run to diff against)")

    write_workbook(
        args.out,
        latest_records=store.snapshot_records(snap_id),
        events=store.all_events(),
        scrape_date=scrape_date,
    )
    store.close()
    print(f"Excel written to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
