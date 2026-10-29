"""Installed compute and accelerator price-performance, from Epoch's datasets.

Data centers: Epoch tracks a sample of the largest AI data centers from permits,
satellite imagery and disclosures. It is not all the world's compute, and the page says
so. Each site has a dated H100-equivalent timeline; a site's capacity on a day is its
latest timeline value on or before that day (a step function). Rows dated after today
are Epoch's projections and are only ever reported as "planned".
"""

from __future__ import annotations

import bisect

from overhang.race import normalise_org


def site_value_on(timeline: list[dict], day: str) -> float:
    """Step function: last value dated on or before ``day``, else 0."""
    dates = [t["date"] for t in timeline]
    i = bisect.bisect_right(dates, day)
    return timeline[i - 1]["h100e"] if i else 0.0


def by_owner(dc: dict, today: str) -> dict:
    """Current and latest-planned H100e per owner, plus the tracked total over time."""
    sites: dict[str, list[dict]] = {}
    for t in dc["timeline"]:
        sites.setdefault(t["site"], []).append(t)
    for rows in sites.values():
        rows.sort(key=lambda t: t["date"])

    def owner_of(site: str) -> str:
        return normalise_org(dc["owners"].get(site, {}).get("owner"))

    # "Planned" is every site at its final timeline value: finished sites count at what
    # they run now, unfinished ones at Epoch's projection. Shown only for owners with at
    # least one unfinished site; otherwise planned equals current and adds nothing.
    current: dict[str, float] = {}
    final: dict[str, float] = {}
    planned_by: dict[str, str] = {}
    for site, rows in sites.items():
        o = owner_of(site)
        current[o] = current.get(o, 0.0) + site_value_on(rows, today)
        last = rows[-1]
        final[o] = final.get(o, 0.0) + last["h100e"]
        if last["date"] > today:
            planned_by[o] = max(planned_by.get(o, ""), last["date"])
    planned = {o: (final[o], d) for o, d in planned_by.items()}
    # Quarterly sample points for the total line, up to today only.
    years = sorted({t["date"][:4] for t in dc["timeline"]})
    total = []
    for y in range(int(years[0]), int(today[:4]) + 1):
        for md in ("03-31", "06-30", "09-30", "12-31"):
            day = f"{y}-{md}"
            if day > today:
                break
            total.append({"date": day, "value": sum(site_value_on(r, day) for r in sites.values())})
    total.append({"date": today, "value": sum(current.values())})
    rows = [
        {
            "owner": o,
            "current": current.get(o, 0.0),
            "planned": planned.get(o, (None, None))[0],
            "planned_by": planned.get(o, (None, None))[1],
        }
        for o in set(current) | set(planned)
    ]
    rows.sort(key=lambda r: -r["current"])
    return {"owners": rows, "total": [t for t in total if t["value"] > 0], "sites": len(sites)}


def price_performance(chips: list[dict]) -> list[dict]:
    """16-bit FLOP/s per launch-price dollar, for chips with a published price."""
    return [
        {**c, "value": c["value"] / c["price_usd"]}
        for c in chips
        if c.get("price_usd") and c["price_usd"] > 0
    ]
