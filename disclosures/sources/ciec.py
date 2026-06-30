"""CIEC public registry scraper (MPs under the Code; ministers/POHs under the Act).

Enumerates declaration "cards" via
``/en/public-registry/cards?affiliationRole=<GUID>&declarationType=<GUID>&page=N``
then fetches and parses each ``Details?declarationId=<GUID>`` page.
GUIDs were captured from the live filter form.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..fetch import PoliteClient
from ..models import AssetRecord
from ..parse import parse_declaration_details

BASE = "https://ciec-ccie.parl.gc.ca"
CARDS_URL = f"{BASE}/en/public-registry/cards"
DETAILS_URL = f"{BASE}/en/public-registry/Details"

ROLE_GUIDS = {
    "mp": "cac94a19-d04e-e111-b8ea-00265535a320",
    "minister": "c8c94a19-d04e-e111-b8ea-00265535a320",
    "poh": "d0c94a19-d04e-e111-b8ea-00265535a320",
    "gic": "c6c94a19-d04e-e111-b8ea-00265535a320",
    "staff": "ccc94a19-d04e-e111-b8ea-00265535a320",
    "parlsec": "d2c94a19-d04e-e111-b8ea-00265535a320",
}

ROLE_LABELS = {
    "mp": "Member of Parliament",
    "minister": "Minister",
    "poh": "Public Office Holder",
    "gic": "Governor in Council Appointee",
    "staff": "Ministerial Staff",
    "parlsec": "Parliamentary Secretary",
}

TYPE_GUIDS = {
    "disclosure_summary_code": "5924f660-7f25-4702-a727-bc15b1b85dba",
    "summary_statement_act": "acdd6784-b1ef-48b5-80ba-08c3c49ef733",
}

# Asset-bearing summary declaration to scrape for each role.
ROLE_SUMMARY_TYPE = {
    "mp": "disclosure_summary_code",
    "minister": "summary_statement_act",
    "poh": "summary_statement_act",
    "gic": "summary_statement_act",
    "staff": "summary_statement_act",
    "parlsec": "summary_statement_act",
}

STATUS_ACTIVE = "ecfdb65d-592d-4649-ad7c-a647f9862634"

name = "CIEC"


def _declaration_ids(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    ids: list[str] = []
    for a in soup.select('a[href*="Details?declarationId="]'):
        m = re.search(r"declarationId=([a-f0-9-]+)", a.get("href", ""), re.I)
        if m:
            ids.append(m.group(1))
    return ids


def iter_detail_ids(
    client: PoliteClient,
    role_guid: str,
    type_guid: str,
    status_guid: str | None = STATUS_ACTIVE,
    max_pages: int = 80,
    refresh: bool = False,
):
    """Yield declaration IDs across paginated cards, stopping when a page adds
    nothing new (also guards against a server that ignores ``page``)."""
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        params = {
            "affiliationRole": role_guid,
            "declarationType": type_guid,
            "page": page,
            "sortBy": "lastName",
            "sortDir": "asc",
        }
        if status_guid:
            params["declarationStatus"] = status_guid
        html = client.get(CARDS_URL, params=params, refresh=refresh)
        new_ids = [d for d in _declaration_ids(html) if d not in seen]
        if not new_ids:
            break
        for d in new_ids:
            seen.add(d)
            yield d


def scrape(
    client: PoliteClient,
    roles: list[str],
    limit: int | None = None,
    name_filter: str | None = None,
    refresh: bool = False,
    status_active: bool = True,
) -> list[AssetRecord]:
    records: list[AssetRecord] = []
    seen_decl: set[str] = set()
    people = 0
    status_guid = STATUS_ACTIVE if status_active else None

    for role in roles:
        if role not in ROLE_GUIDS:
            continue
        role_guid = ROLE_GUIDS[role]
        type_guid = TYPE_GUIDS[ROLE_SUMMARY_TYPE[role]]
        for did in iter_detail_ids(client, role_guid, type_guid, status_guid, refresh=refresh):
            if did in seen_decl:
                continue
            seen_decl.add(did)
            url = f"{DETAILS_URL}?declarationId={did}"
            html = client.get(url, refresh=refresh)
            recs = parse_declaration_details(html, source_url=url)
            if not recs:
                continue
            if name_filter and name_filter.lower() not in recs[0].person_name.lower():
                continue
            for r in recs:
                if not r.role:
                    r.role = ROLE_LABELS.get(role, role)
            records.extend(recs)
            people += 1
            if limit and people >= limit:
                return records
    return records
