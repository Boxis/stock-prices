"""SQLite history store for disclosure snapshots and detected events.

Each run saves a *snapshot* of all scraped AssetRecords. Comparing the latest
two snapshots yields purchased/sold events (see diff.py). The store also tracks
``first_seen`` per (person, asset) so the current-holdings view knows how long
an asset has been disclosed.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from .models import AssetEvent, AssetRecord, normalize_asset_name

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    scope TEXT
);
CREATE TABLE IF NOT EXISTS assets (
    snapshot_id INTEGER NOT NULL,
    source TEXT, person_id TEXT, person_name TEXT, role TEXT, regime TEXT,
    declaration_id TEXT, declaration_type TEXT, disclosed_date TEXT,
    owner TEXT, category TEXT, asset_name TEXT, asset_key TEXT,
    ticker TEXT, ticker_confidence TEXT, source_url TEXT, first_seen TEXT,
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
);
CREATE INDEX IF NOT EXISTS idx_assets_key ON assets(person_id, asset_key);
CREATE TABLE IF NOT EXISTS events (
    event_type TEXT, event_date TEXT, approximate INTEGER,
    source TEXT, person_id TEXT, person_name TEXT, role TEXT,
    owner TEXT, category TEXT, asset_name TEXT, ticker TEXT, source_url TEXT,
    detected_at TEXT
);
"""


class Store:
    def __init__(self, path: str = "output/disclosures.db"):
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- snapshots ----------------------------------------------------------
    def _first_seen(self, person_id: str, asset_key: str, default: str) -> str:
        row = self.conn.execute(
            "SELECT MIN(first_seen) AS fs FROM assets WHERE person_id=? AND asset_key=?",
            (person_id, asset_key),
        ).fetchone()
        return row["fs"] if row and row["fs"] else default

    def save_snapshot(self, records: list[AssetRecord], scope: str = "") -> int:
        created = date.today().isoformat()
        cur = self.conn.execute(
            "INSERT INTO snapshots (created_at, scope) VALUES (?, ?)", (created, scope)
        )
        snap_id = cur.lastrowid
        for r in records:
            akey = "|".join(r.key())
            first_seen = self._first_seen(r.person_id, akey, r.disclosed_date or created)
            self.conn.execute(
                """INSERT INTO assets (snapshot_id, source, person_id, person_name,
                   role, regime, declaration_id, declaration_type, disclosed_date,
                   owner, category, asset_name, asset_key, ticker, ticker_confidence,
                   source_url, first_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    snap_id, r.source, r.person_id, r.person_name, r.role, r.regime,
                    r.declaration_id, r.declaration_type, r.disclosed_date, r.owner,
                    r.category, r.asset_name, akey, r.ticker, r.ticker_confidence,
                    r.source_url, first_seen,
                ),
            )
        self.conn.commit()
        return snap_id

    def snapshot_ids(self) -> list[int]:
        rows = self.conn.execute("SELECT id FROM snapshots ORDER BY id").fetchall()
        return [row["id"] for row in rows]

    def snapshot_records(self, snapshot_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM assets WHERE snapshot_id=?", (snapshot_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # -- events -------------------------------------------------------------
    def save_events(self, events: list[AssetEvent]) -> None:
        detected = date.today().isoformat()
        for e in events:
            self.conn.execute(
                """INSERT INTO events (event_type, event_date, approximate, source,
                   person_id, person_name, role, owner, category, asset_name, ticker,
                   source_url, detected_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    e.event_type, e.event_date, int(e.approximate), e.source,
                    e.person_id, e.person_name, e.role, e.owner, e.category,
                    e.asset_name, e.ticker, e.source_url, detected,
                ),
            )
        self.conn.commit()

    def all_events(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events ORDER BY event_date, person_name"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self.conn.close()
