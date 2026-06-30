"""Best-effort mapping of disclosed asset names to stock tickers.

Disclosure summaries are free text (e.g. "1,000 common shares of Royal Bank of
Canada"). We strip the boilerplate and fuzzy-match the remaining company name
against a curated reference of common Canadian (TSX) and large U.S. issuers.
Anything below the confidence threshold (real estate, private corporations,
trusts, mutual funds) is left blank -- this is intentional.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

# Curated reference: company name -> ticker. Not exhaustive; extend as needed.
COMPANY_TICKERS: dict[str, str] = {
    # Canadian banks / financials
    "Royal Bank of Canada": "RY.TO",
    "Toronto-Dominion Bank": "TD.TO",
    "Bank of Nova Scotia": "BNS.TO",
    "Scotiabank": "BNS.TO",
    "Bank of Montreal": "BMO.TO",
    "Canadian Imperial Bank of Commerce": "CM.TO",
    "National Bank of Canada": "NA.TO",
    "Manulife Financial": "MFC.TO",
    "Sun Life Financial": "SLF.TO",
    "Power Corporation of Canada": "POW.TO",
    "Brookfield Corporation": "BN.TO",
    "Brookfield Asset Management": "BAM.TO",
    "Intact Financial": "IFC.TO",
    "Fairfax Financial": "FFH.TO",
    "Great-West Lifeco": "GWO.TO",
    # Energy / utilities
    "Enbridge": "ENB.TO",
    "TC Energy": "TRP.TO",
    "Suncor Energy": "SU.TO",
    "Canadian Natural Resources": "CNQ.TO",
    "Cenovus Energy": "CVE.TO",
    "Imperial Oil": "IMO.TO",
    "Pembina Pipeline": "PPL.TO",
    "Fortis": "FTS.TO",
    "Tourmaline Oil": "TOU.TO",
    # Industrials / rail / materials
    "Canadian National Railway": "CNR.TO",
    "Canadian Pacific Kansas City": "CP.TO",
    "Nutrien": "NTR.TO",
    "Barrick Gold": "ABX.TO",
    "Agnico Eagle Mines": "AEM.TO",
    "Franco-Nevada": "FNV.TO",
    "Wheaton Precious Metals": "WPM.TO",
    "Teck Resources": "TECK.B.TO",
    "Magna International": "MG.TO",
    "Waste Connections": "WCN.TO",
    "TFI International": "TFII.TO",
    # Telecom / media
    "BCE": "BCE.TO",
    "Bell Canada": "BCE.TO",
    "Telus": "T.TO",
    "Rogers Communications": "RCI.B.TO",
    "Thomson Reuters": "TRI.TO",
    "Quebecor": "QBR.B.TO",
    # Consumer / retail
    "Loblaw Companies": "L.TO",
    "Alimentation Couche-Tard": "ATD.TO",
    "Dollarama": "DOL.TO",
    "Restaurant Brands International": "QSR.TO",
    "Metro Inc": "MRU.TO",
    "George Weston": "WN.TO",
    "Saputo": "SAP.TO",
    # Tech
    "Shopify": "SHOP.TO",
    "Constellation Software": "CSU.TO",
    "Open Text": "OTEX.TO",
    "CGI Inc": "GIB.A.TO",
    "Descartes Systems": "DSG.TO",
    # Major U.S.
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Amazon": "AMZN",
    "Alphabet": "GOOGL",
    "Google": "GOOGL",
    "Meta Platforms": "META",
    "Tesla": "TSLA",
    "NVIDIA": "NVDA",
    "Berkshire Hathaway": "BRK-B",
    "JPMorgan Chase": "JPM",
    "Johnson & Johnson": "JNJ",
    "Coca-Cola": "KO",
    "Walmart": "WMT",
    "Visa": "V",
}

# Boilerplate to strip before matching.
_STRIP_PATTERNS = [
    r"^\s*[\d,\.]+\s+(common\s+|preferred\s+|class\s+[a-z]\s+)?(shares?|units?)\s+(of|in)\s+",
    r"^\s*(shares?|units?|stock|holdings?|investment)\s+(of|in)\s+",
    r"^\s*(common|preferred)\s+shares?\s+(of|in)\s+",
    r"^\s*(controlling|significant|minority)\s+interest\s+in:?\s*",
    r"\b(inc|inc\.|incorporated|corp|corp\.|corporation|ltd|ltd\.|limited|company|co\.|plc)\b",
]

# Categories where it makes sense to even try (set by the caller, but the
# default normalizer is category-agnostic).


# Generic words that must NOT, on their own, justify a match (they inflate
# token-set similarity, e.g. "...International..." -> "TFI International").
_GENERIC_TOKENS = {
    "international", "group", "holdings", "holding", "corporation", "corp",
    "company", "inc", "ltd", "limited", "plc", "the", "of", "and",
    "real", "estate", "development", "properties", "property", "services",
    "service", "systems", "system", "capital", "financial", "fund", "trust",
    "investments", "investment", "enterprises",
    # Industry words: common across many issuers, so they must not be *required*
    # to confirm a match (e.g. "Cenovus" == "Cenovus Energy") nor *justify* one
    # on their own (e.g. "Cardinal Energy" must not become "TC Energy").
    "energy", "metals", "resources", "communications",
}


def _distinctive_tokens(name: str) -> list[str]:
    toks = re.split(r"[^a-z0-9]+", name.lower())
    return [t for t in toks if len(t) >= 3 and t not in _GENERIC_TOKENS]


def _match_is_credible(company_name: str, cleaned: str) -> bool:
    """Every distinctive token of the matched company must appear in the asset name.

    Requiring *all* distinctive tokens (not just one) is what stops cross-company
    collisions on a single shared word -- e.g. a "...Real Estate in Montreal"
    note matching "Bank of Montreal", "Arc Resources" matching "Canadian Natural
    Resources", or "Gold." matching "Barrick Gold".
    """
    tokens = _distinctive_tokens(company_name)
    if not tokens:
        return True  # nothing distinctive to verify; fall back to the score
    low = cleaned.lower()
    return all(t in low for t in tokens)


def _clean_name(asset_name: str) -> str:
    s = asset_name.strip()
    for pat in _STRIP_PATTERNS:
        s = re.sub(pat, "", s, flags=re.IGNORECASE)
    # cut trailing location/descriptor clauses after a comma
    s = s.split(",")[0]
    s = re.sub(r"\s+", " ", s).strip(" .,:;-")
    return s


def lookup_ticker(asset_name: str, min_score: float = 86.0) -> tuple[str, str]:
    """Return (ticker, confidence) for an asset name; ('', '') if no match.

    confidence is "high" (>=92) or "medium" (>=min_score). Matches below
    ``min_score`` are dropped: at scale they are almost always industry- or
    geography-word collisions (e.g. an "Energy" company matching "TC Energy"),
    so a blank is more useful than a wrong ticker.
    """
    cleaned = _clean_name(asset_name)
    if len(cleaned) < 3:
        return "", ""

    match = process.extractOne(
        cleaned,
        COMPANY_TICKERS.keys(),
        scorer=fuzz.token_set_ratio,
    )
    if not match:
        return "", ""
    name, score, _ = match
    if score < min_score:
        return "", ""
    if not _match_is_credible(name, cleaned):
        return "", ""
    confidence = "high" if score >= 92 else "medium"
    return COMPANY_TICKERS[name], confidence


def annotate_tickers(records, tickerable_categories) -> None:
    """Fill ticker/ticker_confidence in-place for records in asset categories."""
    for r in records:
        if r.category.lower() in tickerable_categories:
            r.ticker, r.ticker_confidence = lookup_ticker(r.asset_name)
