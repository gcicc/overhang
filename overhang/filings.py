"""Money behind the compute: filed revenue of chip makers, filed capex of hyperscalers,
and share prices. Adapted from 02-Maintain/hangar (``hangar/financials.py``).

* **SEC XBRL company facts** (``data.sec.gov``): figures a company signed its name to.
  Chip makers' quarterly revenue (NVDA, AMD, AVGO) and hyperscalers' capital
  expenditure (MSFT, GOOGL, AMZN, META).
* **Yahoo's chart endpoint** for weekly closes, the same keyless call HANGAR uses.

What the filings cannot give, and the page says so:

* Nvidia's data-center revenue is reported as a segment, a dimensional XBRL fact that
  the company-facts API does not carry. Total revenue is the measured series.
* TSMC files IFRS figures in TWD, annually, on a 20-F. It appears in the price index only.

Two XBRL quirks are handled explicitly:

* A company changes concepts over time (Nvidia moved from
  ``RevenueFromContractWithCustomerExcludingAssessedTax`` to ``Revenues``). Every
  candidate concept is read and merged by period, preferring the concept filed most
  recently.
* Q4 is rarely filed as its own fact. It is derived as the fiscal year less the three
  quarters inside it, and marked derived. This is done by date window, not calendar
  quarter, because Nvidia's fiscal year ends in late January.

Capex is a cash-flow item, filed year-to-date in 10-Qs, so it is shown as fiscal-year
totals plus a trailing twelve months: last FY + current YTD - prior-year YTD.
"""

from __future__ import annotations

import os
from datetime import date

from overhang import net

COMPANY_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# SEC asks for a contact address in the User-Agent. Kept out of the source so a public
# repo does not carry a personal address; set SEC_CONTACT locally and as a repo secret.
SEC_CONTACT = os.environ.get("SEC_CONTACT") or "overhang@example.invalid"

CHIPMAKERS = {"NVDA": ("Nvidia", 1045810), "AMD": ("AMD", 2488), "AVGO": ("Broadcom", 1730168)}
HYPERSCALERS = {
    "MSFT": ("Microsoft", 789019),
    "GOOGL": ("Alphabet", 1652044),
    "AMZN": ("Amazon", 1018724),
    "META": ("Meta", 1326801),
}
REVENUE = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"]
CAPEX = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]

# Price index: chip designers, the foundry, and the S&P 500 as the baseline.
QUOTES = {"NVDA": "Nvidia", "AMD": "AMD", "AVGO": "Broadcom", "TSM": "TSMC", "^GSPC": "S&P 500"}

_Q_MIN, _Q_MAX = 80, 100
_Y_MIN, _Y_MAX = 350, 380


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _is_period_we_use(fact: dict) -> bool:
    """A year-long fact counts only from a 10-K.

    Amazon's 10-Qs report trailing-twelve-month figures, which are year-long but are
    not fiscal years; taken as annual they would add a fake "year" every quarter.
    """
    if _Y_MIN <= _days(fact["start"], fact["end"]) <= _Y_MAX:
        return str(fact.get("form", "")).startswith("10-K")
    return True


def merge_facts(facts: dict, concepts: list[str]) -> dict[tuple[str, str], float]:
    """``{(start, end): value}`` across candidate concepts.

    Within a concept the latest filing wins (restatements). Across concepts, the one
    with the most recent period end wins a contested period, because that is the
    concept the company uses now.
    """
    gaap = facts.get("us-gaap", {})
    ranked = []
    for name in concepts:
        rows = [
            f
            for f in gaap.get(name, {}).get("units", {}).get("USD", [])
            if "start" in f and _is_period_we_use(f)
        ]
        if rows:
            ranked.append((max(f["end"] for f in rows), rows))
    ranked.sort(key=lambda r: r[0])  # oldest concept first; newer ones overwrite
    out: dict[tuple[str, str], float] = {}
    for _, rows in ranked:
        per_concept: dict[tuple[str, str], tuple[str, float]] = {}
        for f in rows:
            key = (f["start"], f["end"])
            if key not in per_concept or f.get("filed", "") >= per_concept[key][0]:
                per_concept[key] = (f.get("filed", ""), f["val"])
        out.update({k: v for k, (_, v) in per_concept.items()})
    return out


def quarterly(periods: dict[tuple[str, str], float]) -> list[dict]:
    """Quarterly points by period end, with Q4 derived where the filings imply it."""
    quarters = {k: v for k, v in periods.items() if _Q_MIN <= _days(*k) <= _Q_MAX}
    points = {end: {"end": end, "value": v, "derived": False} for (_, end), v in quarters.items()}
    for (start, end), fy in periods.items():
        if not _Y_MIN <= _days(start, end) <= _Y_MAX or end in points:
            continue
        inside = [v for (s, e), v in quarters.items() if s >= start and e < end]
        if len(inside) == 3:
            points[end] = {"end": end, "value": fy - sum(inside), "derived": True}
    return [points[e] for e in sorted(points)]


def annual(periods: dict[tuple[str, str], float]) -> list[dict]:
    rows = [
        {"end": end, "value": v}
        for (start, end), v in periods.items()
        if _Y_MIN <= _days(start, end) <= _Y_MAX
    ]
    return sorted(rows, key=lambda r: r["end"])


def trailing_twelve_months(periods: dict[tuple[str, str], float]) -> dict | None:
    """Last fiscal year + current year-to-date - the same span a year earlier.

    Returns None when the latest figure is the fiscal year itself (then TTM = FY) or
    when the prior-year comparable is missing.
    """
    years = annual(periods)
    if not years:
        return None
    last_fy = years[-1]
    ytd = [
        (s, e, v)
        for (s, e), v in periods.items()
        if e > last_fy["end"] and _days(last_fy["end"], s) <= 7 and _days(s, e) < _Y_MIN
    ]
    if not ytd:
        return {"value": last_fy["value"], "through": last_fy["end"], "basis": "fiscal year"}
    s, e, v = max(ytd, key=lambda r: r[1])
    span = _days(s, e)
    prior = [
        pv
        for (ps, pe), pv in periods.items()
        if abs(_days(pe, e) - 365) <= 10 and abs(_days(ps, pe) - span) <= 10
    ]
    if not prior:
        return None
    return {"value": last_fy["value"] + v - prior[0], "through": e, "basis": "TTM"}


def fetch_quotes() -> dict:
    """Weekly closes for five years, rebased later; one failure skips one symbol."""
    out = {}
    for symbol, name in QUOTES.items():
        try:
            doc = net.get(YAHOO.format(symbol=symbol), params={"range": "5y", "interval": "1wk"})
            result = doc.json()["chart"]["result"][0]
            closes = result["indicators"]["quote"][0]["close"]
            series = [
                {"date": date.fromtimestamp(ts).isoformat(), "close": round(c, 2)}
                for ts, c in zip(result["timestamp"], closes)
                if c is not None
            ]
            out[symbol] = {"name": name, "series": series}
        except Exception as e:  # noqa: BLE001 - a dead quote must not fail the run
            print(f"  [FAIL] quote {symbol}: {e}")
    if not out:
        raise RuntimeError("no quotes fetched")
    return {"quotes": out, "source_url": "https://finance.yahoo.com/"}


def fetch_filings() -> dict:
    headers_ua = f"overhang/0.1 {SEC_CONTACT}"
    revenue, capex = {}, {}
    for ticker, (name, cik) in {**CHIPMAKERS, **HYPERSCALERS}.items():
        facts = net.get(COMPANY_FACTS.format(cik=cik), user_agent=headers_ua).json()["facts"]
        if ticker in CHIPMAKERS:
            revenue[ticker] = {"name": name, "points": quarterly(merge_facts(facts, REVENUE))}
        else:
            periods = merge_facts(facts, CAPEX)
            capex[ticker] = {
                "name": name,
                "annual": annual(periods),
                "ttm": trailing_twelve_months(periods),
            }
    return {
        "revenue": revenue,
        "capex": capex,
        "source_url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
    }
