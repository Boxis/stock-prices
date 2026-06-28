"""Parse a CIEC declaration "Details" page into AssetRecords.

The page is server-rendered. The relevant markup is::

    <div class="declaration-details-card-title">
      <strong><a href="/en/client?clientId=GUID">NAME</a></strong>
      <span class="text-muted"> &middot; ROLE</span>
    </div>
    ...
    <dl><dt>Declaration type</dt><dd>...</dd>
        <dt>Disclosure date</dt><dd>YYYY-MM-DD</dd>
        <dt>Regime</dt><dd>...</dd>
        <dt>Description</dt><dd>
          <div class="ciec-summary-field">
            <div class="ciec-declaration-disclosurelabel">Assets</div>
            <div class="ciec-declaration-disclosurecontent">
              <div class="ciec-declaration-disclosureitem">free text with <br> lines</div>
            </div>
          </div>
          ... (one field per section; "Spouse's/Common-Law Partner's ..." = spouse)
        </dd></dl>
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .models import SELF, SPOUSE, AssetRecord

SPOUSE_PREFIX = "spouse's/common-law partner's"


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _dl_map(soup: BeautifulSoup) -> dict[str, str]:
    """Map every <dt> label to its <dd> text (Declaration type, etc.)."""
    out: dict[str, str] = {}
    for dt in soup.select("dt"):
        dd = dt.find_next_sibling("dd")
        if dd is not None:
            out[dt.get_text(strip=True)] = dd.get_text(" ", strip=True)
    return out


def _split_entries(item_text: str) -> list[str]:
    """Split a disclosure item into individual asset entries.

    Handles the common "Header:\n- A\n- B" pattern by attaching the header as a
    prefix to each bullet, so each security/company becomes its own row.
    """
    lines = [ln.strip() for ln in item_text.split("\n") if ln.strip()]
    entries: list[str] = []
    prefix = ""
    for ln in lines:
        if ln.endswith(":"):
            prefix = ln[:-1].strip()
            continue
        bullet = ln[1:].strip() if ln.startswith("-") else ln
        if not bullet:
            continue
        entries.append(f"{prefix}: {bullet}" if prefix else bullet)
    if not entries:
        cleaned = " ".join(lines).strip()
        if cleaned:
            entries.append(cleaned)
    return entries


def _cap(text: str) -> str:
    """Capitalize the first character only (keeps 'source(s) of income' sane)."""
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text


def _owner_and_category(label: str) -> tuple[str, str]:
    low = label.strip().lower()
    if low.startswith(SPOUSE_PREFIX):
        category = label.strip()[len(SPOUSE_PREFIX):].strip(" '").strip()
        return SPOUSE, _cap(category or "assets")
    return SELF, _cap(label.strip())


def parse_declaration_details(html: str, source_url: str = "") -> list[AssetRecord]:
    """Parse one Details page into a list of AssetRecords (one per entry)."""
    soup = _soup(html)

    # Identity
    title = soup.select_one(".declaration-details-card-title")
    person_name = ""
    person_id = ""
    role = ""
    if title:
        link = title.select_one('a[href*="clientId="]')
        if link:
            person_name = link.get_text(strip=True)
            m = re.search(r"clientId=([a-f0-9-]+)", link.get("href", ""), re.I)
            if m:
                person_id = m.group(1)
        muted = title.select_one(".text-muted")
        if muted:
            role = muted.get_text(strip=True).lstrip("·· ").strip()

    meta = _dl_map(soup)
    declaration_type = meta.get("Declaration type", "")
    disclosed_date = (meta.get("Disclosure date", "") or "").strip()
    regime = meta.get("Regime", "")

    # declaration_id from the inner description container, or the URL
    decl_id = ""
    inner = soup.select_one('[id][title="Disclosure Summary"], [id][title*="Summary"]')
    if inner and inner.get("id"):
        decl_id = inner["id"].lower()
    if not decl_id:
        m = re.search(r"declarationId=([a-f0-9-]+)", source_url, re.I)
        if m:
            decl_id = m.group(1)

    records: list[AssetRecord] = []
    for field_div in soup.select(".ciec-summary-field"):
        label_el = field_div.select_one(".ciec-declaration-disclosurelabel")
        if not label_el:
            continue
        owner, category = _owner_and_category(label_el.get_text(strip=True))
        for item in field_div.select(".ciec-declaration-disclosureitem"):
            text = item.get_text("\n", strip=True)
            for entry in _split_entries(text):
                records.append(
                    AssetRecord(
                        source="CIEC",
                        person_id=person_id,
                        person_name=person_name,
                        role=role,
                        regime=regime,
                        declaration_id=decl_id,
                        declaration_type=declaration_type,
                        disclosed_date=disclosed_date,
                        owner=owner,
                        category=category,
                        asset_name=entry,
                        source_url=source_url,
                    )
                )
    return records
