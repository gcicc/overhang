"""Compute each claim's status from its horizon, today's date and curated evidence.

A claim's status comes only from the data (SPEC D5). It is one of:

- ``achieved``          a curated resolution links it to a dated Superhuman Ledger
                        event; the lag versus the horizon is reported in years
- ``undated``           no horizon was given, so nothing can come due
- ``open``              the horizon window has not started
- ``window_open``       today is inside the horizon window
- ``passed_unverified`` the window has closed and no evidence resolves it

There is no "missed" status. The page has evidence that a deadline passed, but no
evidence that the thing did not happen, so it says exactly that.
"""

from __future__ import annotations

import csv
from datetime import date

from overhang.curated import CURATED, CuratedError
from overhang.trend import to_year

STATUS_LABEL = {
    "achieved": "achieved",
    "undated": "undated",
    "open": "open",
    "window_open": "window open",
    "passed_unverified": "deadline passed: outcome unverified",
}


def load_resolutions(superhuman_ids: set[str], claim_ids: set[str]) -> dict[str, dict]:
    """``data/curated/resolutions.csv``: claim_id -> superhuman_id, with a stated rationale."""
    out = {}
    with (CURATED / "resolutions.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            where = f"resolutions.csv[{r.get('claim_id')}]"
            if r["claim_id"] not in claim_ids:
                raise CuratedError(f"{where}: unknown claim_id")
            if r["superhuman_id"] not in superhuman_ids:
                raise CuratedError(f"{where}: unknown superhuman_id {r['superhuman_id']!r}")
            if not r.get("rationale", "").strip():
                raise CuratedError(f"{where}: missing rationale")
            out[r["claim_id"]] = r
    return out


def claim_status(claim: dict, today: date, resolution: dict | None, events: dict) -> dict:
    lo, hi = claim.get("horizon_lo"), claim.get("horizon_hi")
    if resolution:
        ev = events[resolution["superhuman_id"]]
        lag = None
        if hi:
            lag = round(to_year(ev["date"]) - to_year(hi), 1)
        return {
            "status": "achieved",
            "label": STATUS_LABEL["achieved"],
            "evidence": {"id": ev["id"], "date": ev["date"], "achievement": ev["achievement"]},
            "lag_years": lag,
            "rationale": resolution["rationale"],
        }
    if not hi:
        status = "undated"
    elif today.isoformat() < lo:
        status = "open"
    elif today.isoformat() <= hi:
        status = "window_open"
    else:
        status = "passed_unverified"
    return {"status": status, "label": STATUS_LABEL[status]}
